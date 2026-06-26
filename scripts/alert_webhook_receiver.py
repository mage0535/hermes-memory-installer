#!/usr/bin/env python3
"""Receive local action-needed webhooks and optionally forward them outward."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
METRICS_DIR = AGENT_HOME / "metrics"
DEFAULT_QUEUE = METRICS_DIR / "inbound-alert-webhook.jsonl"
DEFAULT_STATUS = METRICS_DIR / "webhook-receiver-latest.json"


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


def write_status(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def format_alert_text(payload: dict[str, Any]) -> str:
    alerts = payload.get("alerts") or []
    lines = [
        f"Hermes Memory alert: {payload.get('status', 'unknown')}",
        f"captured_at: {payload.get('captured_at', utc_now())}",
        f"alert_count: {payload.get('alert_count', len(alerts))}",
    ]
    for item in alerts[:8]:
        lines.append(f"- {item.get('severity', 'unknown')} {item.get('source', 'unknown')}:{item.get('code', 'unknown')}")
    if len(alerts) > 8:
        lines.append(f"- ... {len(alerts) - 8} more")
    return "\n".join(lines)


def build_forward_body(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = kind.lower().strip()
    text = format_alert_text(payload)
    if normalized == "telegram":
        chat_id = os.environ.get("MEMORY_ALERT_TELEGRAM_CHAT_ID", "")
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


def forward_payload(url: str, payload: dict[str, Any], timeout: int, kind: str = "") -> dict[str, Any]:
    body = build_forward_body(infer_forward_kind(url, kind), payload)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return {"status": response.status, "reason": response.reason}


def make_handler(
    queue_path: Path,
    status_path: Path,
    forward_url: str,
    timeout: int,
    forward_kind: str = "",
    max_lines: int = 5000,
) -> type[BaseHTTPRequestHandler]:
    lock = threading.Lock()

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
                try:
                    forward_result = forward_payload(forward_url, payload, timeout, forward_kind)
                except Exception as exc:
                    forward_result = {"error": str(exc)}
            row["forward"] = forward_result

            with lock:
                append_jsonl(queue_path, row)
                rotated = rotate_jsonl(queue_path, max_lines)
                write_status(
                    status_path,
                    {
                        "captured_at": utc_now(),
                        "ok": forward_result is None or "error" not in forward_result,
                        "status": "healthy" if forward_result is None or "error" not in forward_result else "degraded",
                        "queue": str(queue_path),
                        "queue_max_lines": max_lines,
                        "queue_rotated": rotated,
                        "external_forward_configured": bool(forward_url),
                        "external_forward_kind": infer_forward_kind(forward_url, forward_kind) if forward_url else None,
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
    parser.add_argument("--status-output", default=str(DEFAULT_STATUS))
    parser.add_argument("--forward-url", default=os.environ.get("MEMORY_ALERT_FORWARD_URL", ""))
    parser.add_argument("--forward-kind", default=os.environ.get("MEMORY_ALERT_FORWARD_KIND", ""))
    parser.add_argument("--forward-timeout", type=int, default=10)
    parser.add_argument("--max-lines", type=int, default=int(os.environ.get("MEMORY_ALERT_QUEUE_MAX_LINES", "5000")))
    args = parser.parse_args()

    queue_path = Path(args.queue).expanduser()
    status_path = Path(args.status_output).expanduser()
    handler = make_handler(
        queue_path,
        status_path,
        args.forward_url,
        args.forward_timeout,
        args.forward_kind,
        args.max_lines,
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
            "queue_max_lines": args.max_lines,
            "external_forward_configured": bool(args.forward_url),
            "external_forward_kind": infer_forward_kind(args.forward_url, args.forward_kind) if args.forward_url else None,
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
