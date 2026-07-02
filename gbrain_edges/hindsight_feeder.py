import argparse
import json
import sqlite3
from pathlib import Path

from runtime_paths import RuntimePaths
from .models import EdgeCandidate
from .planner import apply_edges, plan_edges


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value.strip().lower()).strip("-")


def build_candidates_from_governance(db_path: str | Path | None = None, limit: int = 500) -> list[EdgeCandidate]:
    db = Path(db_path) if db_path is not None else RuntimePaths.from_agent_home().governance_db
    if not db.exists():
        return []
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        if "memory_objects" not in tables:
            return []
        rows = conn.execute(
            """SELECT object_id, title, entity_type, source_kind, conflict_group, valid_from
            FROM memory_objects
            WHERE object_id IS NOT NULL
            LIMIT ?""",
            (limit,),
        ).fetchall()
    candidates: list[EdgeCandidate] = []
    by_group: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        group = row["conflict_group"] or row["entity_type"] or ""
        if group:
            by_group.setdefault(str(group), []).append(row)
    for group_rows in by_group.values():
        ordered = sorted(group_rows, key=lambda row: str(row["valid_from"] or ""))
        for left, right in zip(ordered, ordered[1:]):
            source, target = _slug(str(left["object_id"])), _slug(str(right["object_id"]))
            if source and target:
                candidates.append(EdgeCandidate(source, target, "semantic", 0.8, "governance"))
                if left["valid_from"] or right["valid_from"]:
                    candidates.append(EdgeCandidate(source, target, "temporal", 0.65, "governance"))
    return candidates


def main(argv=None):
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True)
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--db-path")
    args = parser.parse_args(argv)
    planned = plan_edges(build_candidates_from_governance(args.db_path, args.limit), set(), args.limit)
    print(json.dumps({"mode": "apply" if args.apply else "dry-run", "planned": len(planned)}))
    return apply_edges(planned, apply=args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
