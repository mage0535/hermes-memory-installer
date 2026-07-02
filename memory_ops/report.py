from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from runtime_paths import RuntimePaths


def _latest_eval(logs_dir: Path) -> dict:
    candidates = sorted(logs_dir.glob("memory-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        return {"latest_file": None, "reports": []}
    latest = candidates[0]
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"latest_file": str(latest), "reports": [], "error": "invalid_json"}
    return {"latest_file": str(latest), "reports": payload.get("reports", [])}


def _policy_state(db_path: Path) -> dict:
    if not db_path.exists():
        return {"rows": 0, "eviction_candidates": 0}
    with sqlite3.connect(db_path) as conn:
        try:
            row = conn.execute("select count(*), coalesce(sum(eviction_candidate), 0) from memory_policy").fetchone()
        except sqlite3.Error:
            return {"rows": 0, "eviction_candidates": 0, "error": "policy_table_missing"}
    return {"rows": int(row[0]), "eviction_candidates": int(row[1])}


def _mtm_state(sidecar_home: Path) -> dict:
    path = sidecar_home / "mtm.jsonl"
    if not path.exists():
        return {"items": 0, "pending": 0, "promoted": 0}
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            return {"items": len(rows), "pending": 0, "promoted": 0, "error": "invalid_jsonl"}
    return {
        "items": len(rows),
        "pending": sum(1 for row in rows if row.get("status") == "pending"),
        "promoted": sum(1 for row in rows if row.get("status") == "promoted"),
    }


def build_ops_report(agent_home: str | Path | None = None, edge_plan: dict | None = None) -> dict:
    paths = RuntimePaths.from_agent_home(agent_home)
    return {
        "agent_home": str(paths.agent_home),
        "eval": _latest_eval(paths.logs_dir),
        "policy": _policy_state(paths.governance_db),
        "gbrain_edges": edge_plan or {"mode": "dry-run", "planned_edges": 0},
        "mtm": _mtm_state(paths.sidecar_home),
        "feature_flags": {"TEMPORAL_TRUTH_ENABLED": False, "MTM_ENABLED": False},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-home")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    payload = build_ops_report(args.agent_home)
    text = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
