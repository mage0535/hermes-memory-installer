#!/usr/bin/env python3
"""Trace arbitrary sidecar task runs into LangSmith with minimal code changes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
import time


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


def publish_langsmith(task_name: str, payload: dict) -> dict:
    from langsmith import traceable

    project_name = os.environ.get("LANGSMITH_PROJECT", "hermes-memory-installer")

    @traceable(run_type="tool", name=task_name, project_name=project_name)
    def _emit() -> dict:
        return payload

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
