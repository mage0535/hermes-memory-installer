#!/usr/bin/env python3
"""Receive local action-needed webhooks and optionally forward them outward."""

from __future__ import annotations

import argparse
import json
import os
import threading
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


def write_status(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def forward_payload(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return {"status": response.status, "reason": response.reason}


def make_handler(queue_path: Path, status_path: Path, forward_url: str, timeout: int) -> type[BaseHTTPRequestHandler]:
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
                    forward_result = forward_payload(forward_url, payload, timeout)
                except Exception as exc:
                    forward_result = {"error": str(exc)}
            row["forward"] = forward_result

            with lock:
                append_jsonl(queue_path, row)
                write_status(
                    status_path,
                    {
                        "captured_at": utc_now(),
                        "ok": forward_result is None or "error" not in forward_result,
                        "status": "healthy" if forward_result is None or "error" not in forward_result else "degraded",
                        "queue": str(queue_path),
                        "external_forward_configured": bool(forward_url),
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
    parser.add_argument("--forward-timeout", type=int, default=10)
    args = parser.parse_args()

    queue_path = Path(args.queue).expanduser()
    status_path = Path(args.status_output).expanduser()
    handler = make_handler(queue_path, status_path, args.forward_url, args.forward_timeout)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    write_status(
        status_path,
        {
            "captured_at": utc_now(),
            "ok": True,
            "status": "healthy",
            "bind": f"{args.host}:{args.port}",
            "queue": str(queue_path),
            "external_forward_configured": bool(args.forward_url),
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
