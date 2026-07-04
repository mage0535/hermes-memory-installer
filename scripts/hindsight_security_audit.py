#!/usr/bin/env python3
"""Audit the Hindsight local API exposure without reading memory content."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
DEFAULT_OUTPUT = AGENT_HOME / "metrics" / "hindsight-security-latest.json"
DEFAULT_URL = os.environ.get("HINDSIGHT_BASE_URL", "http://127.0.0.1:8890")


def tcp_connect(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def listening_rows(port: int) -> list[str]:
    try:
        result = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True, timeout=5)
    except Exception:
        return []
    return [line for line in result.stdout.splitlines() if f":{port} " in line]


def local_address(row: str) -> str:
    parts = row.split()
    return parts[3] if len(parts) > 3 else ""


def build_report(base_url: str, public_host: str = "") -> dict:
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    rows = listening_rows(port)
    local_addresses = [local_address(row) for row in rows]
    localhost_bound = any(addr.startswith("127.0.0.1:") or addr.startswith("[::1]:") for addr in local_addresses)
    wildcard_bound = any(addr.startswith("0.0.0.0:") or addr.startswith("*:") or addr.startswith("[::]:") for addr in local_addresses)
    local_reachable = tcp_connect(host, port)
    public_reachable = tcp_connect(public_host, port) if public_host else False
    token_configured = bool(
        os.environ.get("HINDSIGHT_API_KEY")
        or os.environ.get("HINDSIGHT_AUTH_TOKEN")
        or os.environ.get("MEMORY_HINDSIGHT_TOKEN")
    )
    findings = []
    if public_reachable:
        findings.append({"code": "hindsight_publicly_reachable", "severity": "action-needed"})
    if wildcard_bound and not localhost_bound:
        findings.append({"code": "hindsight_wildcard_bind", "severity": "action-needed"})
    if not local_reachable:
        findings.append({"code": "hindsight_local_unreachable", "severity": "action-needed"})
    if not token_configured:
        findings.append({"code": "hindsight_token_not_configured", "severity": "info"})

    status = "healthy"
    if any(item["severity"] == "action-needed" for item in findings):
        status = "action-needed"
    elif any(item["severity"] == "degraded" for item in findings):
        status = "degraded"

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": status == "healthy",
        "base_url_host": host,
        "port": port,
        "local_reachable": local_reachable,
        "public_reachable": public_reachable,
        "localhost_bound": localhost_bound,
        "wildcard_bound": wildcard_bound,
        "token_configured": token_configured,
        "local_addresses": local_addresses,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_URL)
    parser.add_argument("--public-host", default=os.environ.get("HERMES_PUBLIC_HOST", ""))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    report = build_report(args.base_url, args.public_host)
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"healthy", "degraded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
