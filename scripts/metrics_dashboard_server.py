#!/usr/bin/env python3
"""Serve the metrics dashboard behind a token gate."""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import metrics_dashboard


AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
METRICS_DIR = AGENT_HOME / "metrics"
DEFAULT_TOKEN_FILE = AGENT_HOME / "private" / "dashboard-token"


def load_token(token: str, token_file: Path) -> str:
    if token:
        return token.strip()
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    return ""


def authorized(headers: Any, query: dict[str, list[str]], token: str) -> bool:
    if not token:
        return False
    auth = headers.get("Authorization", "")
    if auth == f"Bearer {token}":
        return True
    return query.get("token", [""])[0] == token


def make_handler(metrics_dir: Path, token: str) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        server_version = "HermesMetricsDashboard/1.0"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/health":
                payload = {"ok": bool(token), "auth_required": True}
                self._send(200 if token else 503, json.dumps(payload).encode("utf-8"), "application/json")
                return
            if parsed.path not in {"/", "/dashboard"}:
                self._send(404, b"not found", "text/plain; charset=utf-8")
                return
            if not authorized(self.headers, query, token):
                self._send(401, b"unauthorized", "text/plain; charset=utf-8")
                return
            body = metrics_dashboard.render_dashboard(metrics_dir).encode("utf-8")
            self._send(200, body, "text/html; charset=utf-8")

    return DashboardHandler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("MEMORY_DASHBOARD_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MEMORY_DASHBOARD_PORT", "9500")))
    parser.add_argument("--metrics-dir", default=str(METRICS_DIR))
    parser.add_argument("--token", default=os.environ.get("MEMORY_DASHBOARD_TOKEN", ""))
    parser.add_argument("--token-file", default=str(DEFAULT_TOKEN_FILE))
    args = parser.parse_args()

    token = load_token(args.token, Path(args.token_file).expanduser())
    server = ThreadingHTTPServer((args.host, args.port), make_handler(Path(args.metrics_dir).expanduser(), token))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
