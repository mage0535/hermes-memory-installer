#!/usr/bin/env python3
"""Optional LangSmith-backed monitor for memory sidecar gray or production runs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_QUERIES = (
    "agent memory architecture",
    "policy memory",
    "recent sessions",
)
CHILD_PYTHON = os.environ.get("MONITOR_CHILD_PYTHON", sys.executable)


def run_json_command(command: list[str], timeout: int = 180) -> dict:
    started = time.time()
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    elapsed = round(time.time() - started, 3)
    payload: dict[str, object]
    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {"raw_stdout": result.stdout[:2000]}
    return {
        "returncode": result.returncode,
        "elapsed_s": elapsed,
        "payload": payload,
        "stderr": result.stderr[:1000],
        "command": command,
    }


def collect_snapshot(queries: tuple[str, ...]) -> dict:
    acceptance = run_json_command([CHILD_PYTHON, str(SCRIPT_DIR / "sidecar_acceptance_check.py")], timeout=300)
    recall_rows = []
    for query in queries:
        recall_rows.append(
            {
                "query": query,
                **run_json_command(
                    [CHILD_PYTHON, str(SCRIPT_DIR / "tiered_context_injector.py"), "--test", query],
                    timeout=180,
                ),
            }
        )
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "queries": list(queries),
        "acceptance": acceptance,
        "recalls": recall_rows,
    }


def publish_langsmith(snapshot: dict) -> dict:
    from langsmith import traceable

    project_name = os.environ.get("LANGSMITH_PROJECT", "hermes-memory-installer")

    @traceable(run_type="chain", name="memory-sidecar-monitor", project_name=project_name)
    def _emit() -> dict:
        return snapshot

    result = _emit()
    return {"project": project_name, "published": True, "result": result}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="")
    parser.add_argument("--no-langsmith", action="store_true")
    args = parser.parse_args()

    queries = tuple(
        item.strip()
        for item in os.environ.get("MEMORY_MONITOR_QUERIES", ",".join(DEFAULT_QUERIES)).split(",")
        if item.strip()
    ) or DEFAULT_QUERIES

    snapshot = collect_snapshot(queries)
    if args.output:
        Path(args.output).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    published = None
    if not args.no_langsmith and os.environ.get("LANGSMITH_API_KEY"):
        published = publish_langsmith(snapshot)

    final = {"snapshot": snapshot, "langsmith": published}
    print(json.dumps(final, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
