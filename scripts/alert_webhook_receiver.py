#!/usr/bin/env python3
"""Receive local action-needed webhooks and optionally forward them outward."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
METRICS_DIR = AGENT_HOME / "metrics"
DEFAULT_QUEUE = METRICS_DIR / "inbound-alert-webhook.jsonl"
DEFAULT_DEAD_LETTER = METRICS_DIR / "failed-alert-webhook.jsonl"
DEFAULT_STATUS = METRICS_DIR / "webhook-receiver-latest.json"
DEFAULT_TELEGRAM_LANG_MAP = AGENT_HOME / "private" / "telegram-chat-languages.json"
DEFAULT_RECIPIENTS = AGENT_HOME / "private" / "alert-recipients.json"


SEVERITY_LABELS = {
    "zh": {
        "action-needed": "⚠️ 需处理",
        "degraded": "⚡ 性能下降",
        "info": "ℹ️ 信息",
        "healthy": "✅ 正常",
        "unknown": "未知",
    },
    "en": {
        "action-needed": "⚠️ Action needed",
        "degraded": "⚡ Degraded",
        "info": "ℹ️ Info",
        "healthy": "✅ Healthy",
        "unknown": "Unknown",
    },
}

TEXT = {
    "zh": {
        "title": "Hermes 记忆系统告警",
        "captured_at": "捕获时间",
        "alert_count": "告警数",
        "more": "- 还有 {count} 条",
    },
    "en": {
        "title": "Hermes Memory alert",
        "captured_at": "Captured at",
        "alert_count": "Alert count",
        "more": "- {count} more",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def rotate_jsonl(path: Path, max_lines: int) -> bool:
    if max_lines <= 0 or not path.exists():
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    if len(lines) <= max_lines:
        return False
    archive = path.with_suffix(path.suffix + ".1")
    archive.write_text("\n".join(lines[:-max_lines]).rstrip() + "\n", encoding="utf-8")
    path.write_text("\n".join(lines[-max_lines:]).rstrip() + "\n", encoding="utf-8")
    return True


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def write_status(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_lang(value: str | None) -> str:
    lowered = str(value or "").strip().lower()
    if lowered.startswith("zh"):
        return "zh"
    if lowered.startswith("en"):
        return "en"
    return ""


def default_lang() -> str:
    for key in ("MEMORY_ALERT_LANG", "MEMORY_UI_LANG", "LANGUAGE", "LC_ALL", "LANG"):
        resolved = normalize_lang(os.environ.get(key, ""))
        if resolved:
            return resolved
    return "zh"


def payload_lang(payload: dict[str, Any]) -> str:
    for key in ("lang", "preferred_lang", "user_lang"):
        resolved = normalize_lang(payload.get(key))
        if resolved:
            return resolved
    return default_lang()


def load_telegram_lang_map(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_TELEGRAM_LANG_MAP
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def telegram_chat_lang(chat_id: str, path: Path | None = None) -> str:
    payload = load_telegram_lang_map(path)
    chat = payload.get(str(chat_id))
    if isinstance(chat, dict):
        resolved = normalize_lang(chat.get("lang"))
        if resolved:
            return resolved
    return ""


def telegram_chat_id(payload: dict[str, Any]) -> str:
    for key in ("telegram_chat_id", "chat_id"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    env_chat = os.environ.get("MEMORY_ALERT_TELEGRAM_CHAT_ID", "")
    return str(env_chat).strip()


def load_recipients(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_RECIPIENTS
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def severity_rank(value: str) -> int:
    mapping = {"info": 0, "healthy": 0, "degraded": 1, "warning": 1, "action-needed": 2, "critical": 2}
    return mapping.get(str(value or "").lower(), 0)


def forward_targets(kind: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = kind.lower().strip()
    if normalized != "telegram":
        return []
    configured = load_recipients().get("telegram")
    targets: list[dict[str, Any]] = []
    payload_severity = str(payload.get("status") or "info")
    if isinstance(configured, list):
        for row in configured:
            if not isinstance(row, dict) or not row.get("chat_id") or row.get("enabled", True) is False:
                continue
            min_severity = str(row.get("min_severity") or "info")
            if severity_rank(payload_severity) < severity_rank(min_severity):
                continue
            recipient_lang = normalize_lang(row.get("lang")) or telegram_chat_lang(str(row["chat_id"]))
            body = build_forward_body("telegram", {**payload, "telegram_chat_id": str(row["chat_id"]), "lang": recipient_lang or payload.get("lang")})
            targets.append({"chat_id": str(row["chat_id"]), "lang": recipient_lang or "", "body": body})
    if targets:
        return targets
    chat_id = telegram_chat_id(payload)
    if not chat_id:
        return []
    lang = telegram_chat_lang(chat_id)
    body = build_forward_body("telegram", {**payload, "telegram_chat_id": chat_id, "lang": lang or payload.get("lang")})
    return [{"chat_id": chat_id, "lang": lang or "", "body": body}]


def severity_label(severity: str, lang: str) -> str:
    return SEVERITY_LABELS[lang].get(severity, severity or SEVERITY_LABELS[lang]["unknown"])


def format_alert_text(payload: dict[str, Any], lang: str | None = None) -> str:
    resolved_lang = normalize_lang(lang) or payload_lang(payload)
    copy = TEXT[resolved_lang]
    alerts = payload.get("alerts") or []
    status = str(payload.get("status", "unknown"))
    label = severity_label(status, resolved_lang)
    lines = [
        f"{copy['title']}: {label}",
        f"{copy['captured_at']}: {payload.get('captured_at', utc_now())}",
        f"{copy['alert_count']}: {payload.get('alert_count', len(alerts))}",
    ]
    for item in alerts[:8]:
        sev = str(item.get("severity", "unknown"))
        label = severity_label(sev, resolved_lang)
        lines.append(f"- {label} {item.get('source', 'unknown')}:{item.get('code', 'unknown')}")
        detail = item.get("detail") if isinstance(item.get("detail"), dict) else {}
        reason = detail.get("reason")
        action = detail.get("recommended_action")
        if reason:
            lines.append(f"  {'原因' if resolved_lang == 'zh' else 'Reason'}: {reason}")
        if action:
            lines.append(f"  {'建议' if resolved_lang == 'zh' else 'Suggested action'}: {action}")
    if len(alerts) > 8:
        lines.append(copy["more"].format(count=len(alerts) - 8))
    return "\n".join(lines)


def build_forward_body(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = kind.lower().strip()
    lang = ""
    if normalized == "telegram":
        chat_id = telegram_chat_id(payload)
        if chat_id:
            lang = telegram_chat_lang(chat_id)
    text = format_alert_text(payload, lang=lang)
    if normalized == "telegram":
        chat_id = telegram_chat_id(payload)
        if not chat_id:
            raise ValueError("MEMORY_ALERT_TELEGRAM_CHAT_ID is required for telegram forwarding")
        return {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if normalized == "slack":
        return {"text": text}
    if normalized in {"feishu", "lark"}:
        return {"msg_type": "text", "content": {"text": text}}
    if normalized == "dingtalk":
        return {"msgtype": "text", "text": {"content": text}}
    return payload


def infer_forward_kind(url: str, explicit_kind: str) -> str:
    if explicit_kind:
        return explicit_kind
    lowered = url.lower()
    if "api.telegram.org" in lowered:
        return "telegram"
    if "hooks.slack.com" in lowered:
        return "slack"
    if "open.feishu.cn" in lowered or "open.larksuite.com" in lowered:
        return "feishu"
    if "dingtalk.com" in lowered:
        return "dingtalk"
    return "generic"


def forward_payload_once(url: str, payload: dict[str, Any], timeout: int, kind: str = "") -> dict[str, Any]:
    body = build_forward_body(infer_forward_kind(url, kind), payload)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return {"status": response.status, "reason": response.reason}


def forward_payload(
    url: str,
    payload: dict[str, Any],
    timeout: int,
    kind: str = "",
    attempts: int = 3,
    backoff_s: float = 1.0,
) -> dict[str, Any]:
    attempts = max(1, attempts)
    inferred_kind = infer_forward_kind(url, kind)
    if inferred_kind == "telegram":
        targets = forward_targets("telegram", payload)
        if not targets:
            return {"error": "forward_failed", "attempts": 0, "errors": [{"error": "missing_telegram_target"}]}
        results = []
        for target in targets:
            target_payload = {**payload, "telegram_chat_id": target["chat_id"], "lang": target["lang"] or payload.get("lang")}
            target_errors = []
            for attempt in range(1, attempts + 1):
                try:
                    result = forward_payload_once(url, target_payload, timeout, inferred_kind)
                    result["attempts"] = attempt
                    result["chat_id"] = target["chat_id"]
                    results.append(result)
                    break
                except urllib.error.HTTPError as exc:
                    error = {"attempt": attempt, "status": exc.code, "reason": exc.reason, "chat_id": target["chat_id"]}
                except Exception as exc:
                    error = {"attempt": attempt, "error": str(exc), "chat_id": target["chat_id"]}
                target_errors.append(error)
                if attempt < attempts and backoff_s > 0:
                    time.sleep(backoff_s * attempt)
            else:
                results.append({"error": "forward_failed", "attempts": attempts, "errors": target_errors, "chat_id": target["chat_id"]})
        failures = [row for row in results if row.get("error")]
        if failures:
            return {"error": "forward_failed", "attempts": attempts, "results": results, "errors": failures}
        return {"status": 200, "reason": "OK", "attempts": max((row.get("attempts") or 1) for row in results), "results": results}
    errors = []
    for attempt in range(1, attempts + 1):
        try:
            result = forward_payload_once(url, payload, timeout, inferred_kind)
            result["attempts"] = attempt
            return result
        except urllib.error.HTTPError as exc:
            error = {"attempt": attempt, "status": exc.code, "reason": exc.reason}
        except Exception as exc:
            error = {"attempt": attempt, "error": str(exc)}
        errors.append(error)
        if attempt < attempts and backoff_s > 0:
            time.sleep(backoff_s * attempt)
    return {"error": "forward_failed", "attempts": attempts, "errors": errors}


def replay_dead_letters(
    dead_letter_path: Path,
    forward_url: str,
    timeout: int,
    forward_kind: str = "",
    attempts: int = 3,
    backoff_s: float = 1.0,
    max_replay: int = 100,
    dry_run: bool = False,
) -> dict[str, Any]:
    rows = read_jsonl(dead_letter_path)
    selected = rows[: max(0, max_replay)]
    untouched = rows[len(selected) :]
    replayed = []
    remaining = []
    if not forward_url and selected and not dry_run:
        return {"ok": False, "status": "action-needed", "error": "missing_forward_url", "total": len(rows), "selected": len(selected)}

    for row in selected:
        payload = row.get("payload", row)
        if dry_run:
            result = {"dry_run": True}
        else:
            result = forward_payload(forward_url, payload, timeout, forward_kind, attempts, backoff_s)
        replayed.append({"received_at": row.get("received_at"), "result": result})
        if not dry_run and "error" in result:
            row["last_replay"] = {"attempted_at": utc_now(), "result": result}
            remaining.append(row)
    if not dry_run:
        write_jsonl(dead_letter_path, remaining + untouched)

    failed = sum(1 for item in replayed if "error" in item["result"])
    return {
        "ok": failed == 0,
        "status": "healthy" if failed == 0 else "degraded",
        "total": len(rows),
        "selected": len(selected),
        "replayed": len(replayed),
        "failed": failed,
        "remaining": len(remaining) + len(untouched) if not dry_run else len(rows),
        "dry_run": dry_run,
        "results": replayed,
    }


def make_handler(
    queue_path: Path,
    status_path: Path,
    forward_url: str,
    timeout: int,
    forward_kind: str = "",
    max_lines: int = 5000,
    dead_letter_path: Path | None = None,
    retry_attempts: int = 3,
    retry_backoff_s: float = 1.0,
) -> type[BaseHTTPRequestHandler]:
    lock = threading.Lock()
    dead_letter = dead_letter_path or DEFAULT_DEAD_LETTER

    class AlertWebhookHandler(BaseHTTPRequestHandler):
        server_version = "HermesAlertWebhook/1.0"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def _write_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._write_json(200, {"ok": True, "status": "healthy"})
                return
            self._write_json(404, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path not in {"/", "/alerts"}:
                self._write_json(404, {"ok": False, "error": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._write_json(400, {"ok": False, "error": "invalid_content_length"})
                return
            if length <= 0 or length > 2_000_000:
                self._write_json(400, {"ok": False, "error": "invalid_payload_size"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._write_json(400, {"ok": False, "error": "invalid_json"})
                return

            row = {
                "received_at": utc_now(),
                "remote": self.client_address[0],
                "payload": payload,
            }
            forward_result: dict[str, Any] | None = None
            if forward_url:
                forward_result = forward_payload(
                    forward_url,
                    payload,
                    timeout,
                    forward_kind,
                    retry_attempts,
                    retry_backoff_s,
                )
            row["forward"] = forward_result

            with lock:
                append_jsonl(queue_path, row)
                rotated = rotate_jsonl(queue_path, max_lines)
                dead_letter_written = False
                if forward_result and "error" in forward_result:
                    append_jsonl(dead_letter, row)
                    rotate_jsonl(dead_letter, max_lines)
                    dead_letter_written = True
                write_status(
                    status_path,
                    {
                        "captured_at": utc_now(),
                        "ok": forward_result is None or "error" not in forward_result,
                        "status": "healthy" if forward_result is None or "error" not in forward_result else "degraded",
                        "queue": str(queue_path),
                        "queue_max_lines": max_lines,
                        "queue_rotated": rotated,
                        "dead_letter": str(dead_letter),
                        "dead_letter_written": dead_letter_written,
                        "external_forward_configured": bool(forward_url),
                        "external_forward_kind": infer_forward_kind(forward_url, forward_kind) if forward_url else None,
                        "retry_attempts": retry_attempts,
                        "retry_backoff_s": retry_backoff_s,
                        "last_forward": forward_result,
                    },
                )
            self._write_json(202, {"ok": True, "queued": True, "forward": forward_result})

    return AlertWebhookHandler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("MEMORY_ALERT_WEBHOOK_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MEMORY_ALERT_WEBHOOK_PORT", "9499")))
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    parser.add_argument("--dead-letter", default=str(DEFAULT_DEAD_LETTER))
    parser.add_argument("--status-output", default=str(DEFAULT_STATUS))
    parser.add_argument("--forward-url", default=os.environ.get("MEMORY_ALERT_FORWARD_URL", ""))
    parser.add_argument("--forward-kind", default=os.environ.get("MEMORY_ALERT_FORWARD_KIND", ""))
    parser.add_argument("--forward-timeout", type=int, default=10)
    parser.add_argument("--retry-attempts", type=int, default=int(os.environ.get("MEMORY_ALERT_FORWARD_RETRY_ATTEMPTS", "3")))
    parser.add_argument("--retry-backoff-s", type=float, default=float(os.environ.get("MEMORY_ALERT_FORWARD_RETRY_BACKOFF_S", "1.0")))
    parser.add_argument("--max-lines", type=int, default=int(os.environ.get("MEMORY_ALERT_QUEUE_MAX_LINES", "5000")))
    parser.add_argument("--replay-dead-letter", action="store_true", help="Replay rows from the dead-letter queue and exit")
    parser.add_argument("--max-replay", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", default=str(METRICS_DIR / "dead-letter-replay-latest.json"))
    args = parser.parse_args()

    queue_path = Path(args.queue).expanduser()
    status_path = Path(args.status_output).expanduser()
    if args.replay_dead_letter:
        payload = replay_dead_letters(
            Path(args.dead_letter).expanduser(),
            args.forward_url,
            args.forward_timeout,
            args.forward_kind,
            args.retry_attempts,
            args.retry_backoff_s,
            args.max_replay,
            args.dry_run,
        )
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1

    handler = make_handler(
        queue_path,
        status_path,
        args.forward_url,
        args.forward_timeout,
        args.forward_kind,
        args.max_lines,
        Path(args.dead_letter).expanduser(),
        args.retry_attempts,
        args.retry_backoff_s,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    write_status(
        status_path,
        {
            "captured_at": utc_now(),
            "ok": True,
            "status": "healthy",
            "bind": f"{args.host}:{args.port}",
            "queue": str(queue_path),
            "dead_letter": str(Path(args.dead_letter).expanduser()),
            "queue_max_lines": args.max_lines,
            "external_forward_configured": bool(args.forward_url),
            "external_forward_kind": infer_forward_kind(args.forward_url, args.forward_kind) if args.forward_url else None,
            "retry_attempts": args.retry_attempts,
            "retry_backoff_s": args.retry_backoff_s,
        },
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
