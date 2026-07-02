from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from runtime_paths import RuntimePaths

from .policy import MemoryPolicy, decay, sanitize_provenance, upsert_policy


def _score_row(row: sqlite3.Row) -> tuple[float, str, float]:
    text = f"{row['title'] or ''} {row['summary'] or ''}".casefold()
    source = str(row["source_kind"] or "")
    entity = str(row["entity_type"] or "")
    score = 2.0
    if source == "hindsight":
        score += 0.8
    if entity in {"config", "person", "project", "preference"}:
        score += 0.9
    if any(token in text for token in ("api", "key", "config", "password", "server", "preference")):
        score += 0.8
    score = min(5.0, max(1.0, score))
    tier = "core" if score >= 4.0 else "mtm" if score >= 3.0 else "archive"
    confidence = min(1.0, 0.45 + score / 10.0)
    return score, tier, confidence


def _memory_object_rows(db_path: str | Path) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")
        }
        if "memory_objects" not in tables:
            return []
        return conn.execute(
            """SELECT object_id, title, summary, source_kind, entity_type,
            conflict_group, valid_from, valid_to FROM memory_objects"""
        ).fetchall()


def inject_from_governance(
    db_path: str | Path | None = None,
    apply: bool = False,
    sanitize: bool = True,
) -> dict:
    db = Path(db_path) if db_path is not None else RuntimePaths.from_agent_home().governance_db
    policies: list[MemoryPolicy] = []
    for row in _memory_object_rows(db):
        importance, tier, confidence = _score_row(row)
        provenance = f"{row['source_kind'] or 'unknown'}:{row['object_id']}"
        if sanitize:
            provenance = sanitize_provenance(provenance)
        policies.append(
            MemoryPolicy(
                memory_id=str(row["object_id"]),
                importance_score=importance,
                tier=tier,
                policy_confidence=confidence,
                source_layer=str(row["source_kind"] or "governance"),
                provenance=provenance,
                promotion_reason="heuristic_importance" if tier == "core" else None,
                fact_key=str(row["entity_type"] or row["object_id"]),
                conflict_group=row["conflict_group"],
                valid_from=row["valid_from"],
                valid_to=row["valid_to"],
            )
        )
    if apply:
        for policy in policies:
            upsert_policy(db, policy)
    return {"source": "governance", "mode": "apply" if apply else "dry-run", "proposed": len(policies)}


def apply_decay(db_path: str | Path | None = None, apply: bool = False) -> dict:
    from .policy import current_policies

    db = Path(db_path) if db_path is not None else RuntimePaths.from_agent_home().governance_db
    changed = [decay(policy, "observation") for policy in current_policies(db)]
    if apply:
        for policy in changed:
            upsert_policy(db, policy)
    return {"mode": "apply" if apply else "dry-run", "decayed": len(changed)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="governance")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--sanitize-provenance", action="store_true", default=True)
    parser.add_argument("--no-sanitize-provenance", dest="sanitize_provenance", action="store_false")
    parser.add_argument("--allow-unsafe-provenance", action="store_true")
    parser.add_argument("--decay", action="store_true")
    parser.add_argument("--db-path")
    args = parser.parse_args(argv)
    if not args.sanitize_provenance and not args.allow_unsafe_provenance:
        parser.error("unsafe provenance requires --allow-unsafe-provenance")
    if args.decay:
        payload = apply_decay(args.db_path, apply=args.apply)
    else:
        payload = inject_from_governance(args.db_path, apply=args.apply, sanitize=args.sanitize_provenance)
    payload["sanitize_provenance"] = args.sanitize_provenance
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
