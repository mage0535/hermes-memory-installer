#!/usr/bin/env python3
import importlib
import importlib.util
import json
import sys
from pathlib import Path

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


QUERIES = [
    "hermes gateway provider",
    "gateway restart error switching model",
    "github script deploy",
    "search open source automation tools",
    "模型用量",
    "kiki",
]


def run_recall_checks() -> list[dict]:
    rows = []
    for query in QUERIES:
        l2 = injector.get_l2(query, top=5)
        l3, live_used, live_count = injector.get_l3(query, top=5)
        fused = injector.rrf_fuse([l2, l3], query)
        rows.append(
            {
                "query": query,
                "intent": injector.classify_query_intent(query),
                "l2_count": len(l2),
                "l3_count": len(l3),
                "live_hindsight_used": bool(live_used),
                "live_hindsight_results": int(live_count),
                "top_titles": [item["data"].get("title") for item in fused[:3]],
                "top_sources": [item.get("sources") for item in fused[:3]],
            }
        )
    return rows


def main() -> int:
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
            "level": guardian_status.get("level"),
        },
        "recalls": run_recall_checks(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
