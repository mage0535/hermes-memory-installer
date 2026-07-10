#!/usr/bin/env python3
"""Trace arbitrary sidecar task runs into LangSmith with minimal code changes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


INCLUDE_RAW_OUTPUT = os.environ.get("LANGSMITH_INCLUDE_RAW_OUTPUT", "").lower() in {"1", "true", "yes"}


def run_task(command: list[str], timeout: int) -> dict:
    started = time.time()
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    elapsed = round(time.time() - started, 3)
    return {
        "command": command,
        "returncode": result.returncode,
        "elapsed_s": elapsed,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-2000:],
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def _safe_command(command: list[str]) -> list[str]:
    safe = []
    for part in command:
        if part.endswith(".py") or "/" in part or "\\" in part:
            safe.append(Path(part).name)
        elif part.startswith("-"):
            safe.append(part)
        else:
            safe.append(f"arg:{hashlib.sha256(part.encode('utf-8')).hexdigest()[:12]}")
    return safe


def business_summary(payload: dict) -> dict:
    stdout_tail = str(payload.get("stdout_tail") or "")
    summary = {
        "execution_ok": int(payload.get("returncode") or 0) == 0,
        "business_ok": None,
        "business_status": None,
        "business_error_count": 0,
        "business_reason_buckets": {},
    }
    if not stdout_tail.strip():
        summary["business_ok"] = summary["execution_ok"]
        summary["business_status"] = "success" if summary["execution_ok"] else "execution_failed"
        return summary
    try:
        parsed = json.loads(stdout_tail)
    except json.JSONDecodeError:
        summary["business_ok"] = summary["execution_ok"]
        summary["business_status"] = "success" if summary["execution_ok"] else "execution_failed"
        return summary
    candidate = parsed.get("report") if isinstance(parsed, dict) and isinstance(parsed.get("report"), dict) else parsed
    if not isinstance(candidate, dict):
        summary["business_ok"] = summary["execution_ok"]
        summary["business_status"] = "success" if summary["execution_ok"] else "execution_failed"
        return summary
    if "ok" in candidate:
        summary["business_ok"] = bool(candidate.get("ok"))
    elif "status" in candidate:
        summary["business_ok"] = str(candidate.get("status")) in {"success", "healthy", "noop", "dry_run", "consolidated"}
    else:
        summary["business_ok"] = summary["execution_ok"]
    summary["business_status"] = str(candidate.get("status") or ("success" if summary["business_ok"] else "business_failed"))
    errors = candidate.get("errors") if isinstance(candidate.get("errors"), list) else []
    summary["business_error_count"] = len(errors)
    reason_buckets = candidate.get("reason_buckets")
    if isinstance(reason_buckets, dict):
        summary["business_reason_buckets"] = reason_buckets
    return summary


def sanitize_task_payload(payload: dict) -> dict:
    stdout_tail = payload.get("stdout_tail") or ""
    stderr_tail = payload.get("stderr_tail") or ""
    summary = business_summary(payload)
    sanitized = {
        "command": _safe_command(payload.get("command") or []),
        "command_hash": hashlib.sha256(" ".join(payload.get("command") or []).encode("utf-8")).hexdigest()[:16],
        "returncode": payload.get("returncode"),
        "elapsed_s": payload.get("elapsed_s"),
        "stdout_len": len(stdout_tail),
        "stderr_len": len(stderr_tail),
        "stderr_present": bool(stderr_tail),
        "captured_at": payload.get("captured_at"),
        **summary,
    }
    if INCLUDE_RAW_OUTPUT:
        sanitized["stdout_tail"] = stdout_tail
        sanitized["stderr_tail"] = stderr_tail
    return sanitized


def publish_langsmith(task_name: str, payload: dict) -> dict:
    from langsmith import traceable

    project_name = os.environ.get("LANGSMITH_PROJECT", "hermes-memory-installer")
    safe_payload = sanitize_task_payload(payload)

    @traceable(run_type="tool", name=task_name, project_name=project_name)
    def _emit() -> dict:
        return safe_payload

    result = _emit()
    return {"published": True, "project": project_name, "result": result}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-name", required=True)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("command is required")

    payload = run_task(command, args.timeout)
    published = None
    if os.environ.get("LANGSMITH_API_KEY"):
        published = publish_langsmith(args.task_name, payload)
    print(json.dumps({"task": payload, "langsmith": published}, ensure_ascii=False, indent=2))
    return payload["returncode"]


if __name__ == "__main__":
    raise SystemExit(main())
