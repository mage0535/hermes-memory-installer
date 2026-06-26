#!/usr/bin/env python3
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

from recall_samples import DEFAULT_SAMPLE_CASES, evaluate_recall_samples

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))


def import_module(module_name: str, *candidates: str):
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        for candidate in candidates:
            path = SCRIPT_DIR / candidate
            if not path.exists():
                continue
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            if spec is None or spec.loader is None:
                continue
            spec.loader.exec_module(module)  # type: ignore[attr-defined]
            return module
        raise


guardian = import_module("memory_guardian", "memory_guardian.remote.py")
injector = import_module("tiered_context_injector", "tiered_context_injector.py", "tiered_context_injector.remote.py")


DEFAULT_EXTRA_QUERIES = [
    "agent config provider",
    "gateway restart error switching model",
    "deployment script workflow",
    "open source automation tools",
]
FAST_QUERIES = [
    "模型用量",
    "recent sessions",
]
OPTIONAL_SAMPLE_QUERIES = {
    case.query for case in DEFAULT_SAMPLE_CASES if not case.required_for_acceptance
}


def build_queries(mode: str = "full") -> list[str]:
    configured = [
        part.strip()
        for part in os.environ.get("MEMORY_ACCEPTANCE_EXTRA_QUERIES", "").replace("\n", ",").split(",")
    ]
    if mode == "fast":
        ordered = FAST_QUERIES + configured
    else:
        ordered = [case.query for case in DEFAULT_SAMPLE_CASES] + DEFAULT_EXTRA_QUERIES + configured
    seen = set()
    queries = []
    for query in ordered:
        if not query or query in seen:
            continue
        seen.add(query)
        queries.append(query)
    return queries


def run_recall_checks(mode: str = "full") -> list[dict]:
    rows = []
    for query in build_queries(mode):
        started = time.perf_counter()
        l2_started = time.perf_counter()
        l2 = injector.get_l2(query, top=5)
        l2_elapsed = round(time.perf_counter() - l2_started, 3)
        l3_started = time.perf_counter()
        l3, live_used, live_count = injector.get_l3(query, top=5)
        l3_elapsed = round(time.perf_counter() - l3_started, 3)
        fusion_started = time.perf_counter()
        fused = injector.rrf_fuse([l2, l3], query)
        fusion_elapsed = round(time.perf_counter() - fusion_started, 3)
        knowledge_rows = [item for item in fused if "knowledge" in item.get("sources", [])]
        rows.append(
            {
                "query": query,
                "intent": injector.classify_query_intent(query),
                "l2_count": len(l2),
                "l3_count": len(l3),
                "live_hindsight_used": bool(live_used),
                "live_hindsight_results": int(live_count),
                "knowledge_hit": bool(knowledge_rows),
                "knowledge_top_title": knowledge_rows[0]["data"].get("title") if knowledge_rows else None,
                "top_titles": [item["data"].get("title") for item in fused[:3]],
                "top_sources": [item.get("sources") for item in fused[:3]],
                "timings": {
                    "l2_s": l2_elapsed,
                    "l3_s": l3_elapsed,
                    "fusion_s": fusion_elapsed,
                    "total_s": round(time.perf_counter() - started, 3),
                },
            }
        )
    return rows


def _flatten_top_sources(row: dict) -> list[str]:
    flattened = []
    for item in row.get("top_sources", []):
        if isinstance(item, list):
            flattened.extend(str(source) for source in item)
        elif item:
            flattened.append(str(item))
    return flattened


def evaluate_payload(payload: dict, mode: str = "full") -> tuple[bool, list[str]]:
    errors = []
    guardian_status = payload.get("guardian") or {}
    if guardian_status.get("level") == "critical":
        errors.append("guardian level is critical")
    if int(guardian_status.get("failed_operations") or 0) > 0:
        errors.append("guardian failed_operations is non-zero")

    recalls = payload.get("recalls") or []
    if not recalls:
        return False, ["no recall checks were produced"]

    for row in recalls:
        query = row.get("query") or "<unknown>"
        if query in OPTIONAL_SAMPLE_QUERIES:
            continue
        if int(row.get("l2_count") or 0) <= 0 and int(row.get("l3_count") or 0) <= 0:
            errors.append(f"{query}: no L2/L3 recall candidates")
        if not row.get("top_titles"):
            errors.append(f"{query}: fused recall returned no top titles")

    if mode == "full":
        sample_ok, sample_errors = evaluate_recall_samples(payload, DEFAULT_SAMPLE_CASES)
        if not sample_ok:
            errors.extend(sample_errors)

    for row in recalls:
        query = row.get("query") or "<unknown>"
        if query == "agent memory architecture" and "knowledge" not in _flatten_top_sources(row):
            errors.append(f"{query}: expected top sources to contain knowledge")

    return len(errors) == 0, errors


def bucket_acceptance_errors(errors: list[str]) -> dict[str, int]:
    buckets: dict[str, int] = {}
    for error in errors:
        text = error.lower()
        if "guardian" in text:
            bucket = "guardian"
        elif "hindsight" in text or "lag" in text:
            bucket = "hindsight_lag"
        elif "knowledge" in text:
            bucket = "knowledge_recall"
        elif "recall" in text or "candidate" in text or "top title" in text:
            bucket = "recall_coverage"
        else:
            bucket = "acceptance_error"
        buckets[bucket] = buckets.get(bucket, 0) + 1
    return dict(sorted(buckets.items()))


def validate_runtime_config() -> list[str]:
    configured_home = os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME")
    configured_state = os.environ.get("MEMORY_STATE_DB_PATH")
    state_db = Path(configured_state).expanduser() if configured_state else injector.STATE_DB
    if not configured_home and not configured_state and not state_db.exists():
        return [
            "AGENT_HOME, HERMES_HOME, or MEMORY_STATE_DB_PATH must be set for production acceptance checks"
        ]
    if configured_state and not state_db.exists():
        return [f"MEMORY_STATE_DB_PATH does not exist: {state_db}"]
    return []


def collect_recall_checks(mode: str) -> list[dict]:
    try:
        return run_recall_checks(mode)
    except TypeError:
        return run_recall_checks()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fast", "full"], default=os.environ.get("MEMORY_ACCEPTANCE_MODE", "full"))
    args = parser.parse_args([] if argv is None else argv)

    config_errors = validate_runtime_config()
    if config_errors:
        print(json.dumps({"ok": False, "errors": config_errors}, ensure_ascii=False, indent=2))
        return 2
    _, guardian_status = guardian.monitor(verbose=False)
    payload = {
        "guardian": {
            "pending_consolidation": guardian_status.get("pending_consolidation"),
            "failed_consolidation": guardian_status.get("failed_consolidation"),
            "pending_operations": guardian_status.get("pending_operations"),
            "failed_operations": guardian_status.get("failed_operations"),
            "pending_consolidation_trend": guardian_status.get("pending_consolidation_trend"),
            "pending_consolidation_sticky": guardian_status.get("pending_consolidation_sticky"),
            "pending_consolidation_nonzero_run": guardian_status.get("pending_consolidation_nonzero_run"),
            "hindsight_sync_lag_seconds": guardian_status.get("hindsight_sync_lag_seconds"),
            "node_limit": guardian_status.get("node_limit"),
            "usage_pct": guardian_status.get("usage_pct"),
            "level": guardian_status.get("level"),
        },
        "mode": args.mode,
        "recalls": collect_recall_checks(args.mode),
    }
    ok, errors = evaluate_payload(payload, args.mode)
    payload["ok"] = ok
    payload["errors"] = errors
    payload["reason_buckets"] = bucket_acceptance_errors(errors)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
