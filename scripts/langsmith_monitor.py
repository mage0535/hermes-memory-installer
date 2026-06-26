#!/usr/bin/env python3
"""Optional LangSmith-backed monitor for memory sidecar gray or production runs."""

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


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_QUERIES = (
    "agent memory architecture",
    "policy memory",
    "recent sessions",
)
CHILD_PYTHON = os.environ.get("MONITOR_CHILD_PYTHON", sys.executable)
INCLUDE_QUERY_TEXT = os.environ.get("LANGSMITH_INCLUDE_QUERY_TEXT", "").lower() in {"1", "true", "yes"}
MONITOR_ACCEPTANCE_MODE = os.environ.get("MEMORY_MONITOR_ACCEPTANCE_MODE", "fast")


def query_identity(query: str) -> dict:
    identity = {
        "query_hash": hashlib.sha256(query.encode("utf-8")).hexdigest()[:16],
        "query_length": len(query),
    }
    if INCLUDE_QUERY_TEXT:
        identity["query"] = query
    return identity


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
    acceptance = run_json_command(
        [CHILD_PYTHON, str(SCRIPT_DIR / "sidecar_acceptance_check.py"), "--mode", MONITOR_ACCEPTANCE_MODE],
        timeout=300,
    )
    storage_cross_check = None
    cross_check_script = SCRIPT_DIR / "memory_storage_cross_check.py"
    if cross_check_script.exists():
        storage_cross_check = run_json_command([CHILD_PYTHON, str(cross_check_script)], timeout=120)
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
        "storage_cross_check": storage_cross_check,
        "recalls": recall_rows,
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


def sanitize_recall_row(row: dict) -> dict:
    sanitized = query_identity(str(row.get("query", "")))
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    fused = payload.get("fused") if isinstance(payload.get("fused"), list) else []
    sanitized.update(
        {
            "returncode": row.get("returncode"),
            "elapsed_s": row.get("elapsed_s"),
            "stderr_present": bool(row.get("stderr")),
            "command": _safe_command(row.get("command") or []),
            "l2_count": payload.get("l2_count"),
            "l3_count": payload.get("l3_count"),
            "live_hindsight_used": payload.get("live_hindsight_used"),
            "live_hindsight_results": payload.get("live_hindsight_results"),
            "fused_count": len(fused),
            "top_source_sets": [item.get("sources") for item in fused[:5] if isinstance(item, dict)],
        }
    )
    return sanitized


def sanitize_acceptance(acceptance: dict) -> dict:
    payload = acceptance.get("payload") if isinstance(acceptance.get("payload"), dict) else {}
    errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
    recalls = payload.get("recalls") if isinstance(payload.get("recalls"), list) else []
    sanitized_recalls = []
    for row in recalls:
        if not isinstance(row, dict):
            continue
        out = query_identity(str(row.get("query", "")))
        out.update(
            {
                "intent": row.get("intent"),
                "l2_count": row.get("l2_count"),
                "l3_count": row.get("l3_count"),
                "live_hindsight_used": row.get("live_hindsight_used"),
                "live_hindsight_results": row.get("live_hindsight_results"),
                "knowledge_hit": row.get("knowledge_hit"),
                "top_source_sets": row.get("top_sources") or [],
                "timings": row.get("timings") or {},
            }
        )
        sanitized_recalls.append(out)
    return {
        "returncode": acceptance.get("returncode"),
        "elapsed_s": acceptance.get("elapsed_s"),
        "stderr_present": bool(acceptance.get("stderr")),
        "command": _safe_command(acceptance.get("command") or []),
        "ok": payload.get("ok"),
        "mode": payload.get("mode"),
        "error_count": len(errors),
        "reason_buckets": payload.get("reason_buckets") or {},
        "error_categories": sorted({str(error).split(":", 1)[0] for error in errors})[:10],
        "guardian": payload.get("guardian") or {},
        "recalls": sanitized_recalls,
    }


def sanitize_command_result(result: dict | None) -> dict | None:
    if not isinstance(result, dict):
        return None
    return {
        "returncode": result.get("returncode"),
        "elapsed_s": result.get("elapsed_s"),
        "stderr_present": bool(result.get("stderr")),
        "command": _safe_command(result.get("command") or []),
        "payload": result.get("payload") if isinstance(result.get("payload"), dict) else {},
    }


def sanitize_snapshot(snapshot: dict) -> dict:
    return {
        "captured_at": snapshot.get("captured_at"),
        "queries": [query_identity(str(query)) for query in snapshot.get("queries", [])],
        "acceptance": sanitize_acceptance(snapshot.get("acceptance") or {}),
        "storage_cross_check": sanitize_command_result(snapshot.get("storage_cross_check")),
        "recalls": [
            sanitize_recall_row(row)
            for row in snapshot.get("recalls", [])
            if isinstance(row, dict)
        ],
    }


def publish_langsmith(snapshot: dict) -> dict:
    from langsmith import traceable

    project_name = os.environ.get("LANGSMITH_PROJECT", "hermes-memory-installer")
    safe_snapshot = sanitize_snapshot(snapshot)

    @traceable(run_type="chain", name="memory-sidecar-monitor", project_name=project_name)
    def _emit() -> dict:
        return safe_snapshot

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
