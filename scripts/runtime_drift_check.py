#!/usr/bin/env python3
"""Write a runtime drift status artifact using the installed hermes-memory CLI."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".agent"))).expanduser()
DEFAULT_OUTPUT = AGENT_HOME / "metrics" / "runtime-drift-latest.json"


def run_cli(repo_root: str | None) -> tuple[int, dict | None, str]:
    command = ["hermes-memory", "drift-check", "--format", "json"]
    if repo_root:
        command.extend(["--repo-root", repo_root])
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        return 127, None, "hermes-memory command not found"
    except subprocess.TimeoutExpired:
        return 124, None, "hermes-memory drift-check timed out"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = None
    return result.returncode, payload, result.stderr.strip()


def fallback_payload(returncode: int, error: str) -> dict:
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status": "action-needed",
        "ok": False,
        "reasons": [{"code": "drift_check_unavailable", "severity": "action-needed", "detail": error}],
        "returncode": returncode,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    returncode, payload, stderr = run_cli(args.repo_root or None)
    if payload is None:
        payload = fallback_payload(returncode, stderr or "invalid drift-check output")
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") in {"healthy", "degraded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
