from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class MemoryPolicy:
    memory_id: str
    importance_score: float
    tier: str
    policy_confidence: float
    source_layer: str
    provenance: str
    promotion_reason: str | None = None
    eviction_candidate: bool = False
    fact_key: str | None = None
    conflict_group: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    superseded_by: str | None = None


SCHEMA = """CREATE TABLE IF NOT EXISTS memory_policy (
memory_id TEXT PRIMARY KEY, importance_score REAL NOT NULL,
tier TEXT NOT NULL CHECK(tier IN ('core','mtm','archive')),
policy_confidence REAL NOT NULL, source_layer TEXT NOT NULL,
provenance TEXT NOT NULL, promotion_reason TEXT,
eviction_candidate INTEGER NOT NULL DEFAULT 0,
fact_key TEXT, conflict_group TEXT, valid_from TEXT, valid_to TEXT, superseded_by TEXT,
created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""

POLICY_COLUMNS = {
    "fact_key": "TEXT",
    "conflict_group": "TEXT",
    "valid_from": "TEXT",
    "valid_to": "TEXT",
    "superseded_by": "TEXT",
}


def sanitize_provenance(value: str) -> str:
    value = re.sub(r"\b(?:sk|ghp|github_pat)-?[A-Za-z0-9_-]{12,}\b", "[REDACTED]", value)
    return re.sub(r"(https?|postgresql)://[^/@\s]+@", r"\1://[REDACTED]@", value)


def ensure_policy_schema(db_path: str | Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(SCHEMA)
        existing = {row[1] for row in conn.execute("PRAGMA table_info(memory_policy)")}
        for name, column_type in POLICY_COLUMNS.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE memory_policy ADD COLUMN {name} {column_type}")


def upsert_policy(db_path: str | Path, policy: MemoryPolicy) -> None:
    ensure_policy_schema(db_path)
    now = datetime.now(timezone.utc).isoformat()
    values = (
        policy.memory_id, policy.importance_score, policy.tier, policy.policy_confidence,
        policy.source_layer, sanitize_provenance(policy.provenance), policy.promotion_reason,
        int(policy.eviction_candidate), policy.fact_key, policy.conflict_group,
        policy.valid_from, policy.valid_to, policy.superseded_by, now, now,
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute("""INSERT INTO memory_policy (
        memory_id, importance_score, tier, policy_confidence, source_layer, provenance,
        promotion_reason, eviction_candidate, fact_key, conflict_group, valid_from,
        valid_to, superseded_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(memory_id) DO UPDATE SET importance_score=excluded.importance_score,
        tier=excluded.tier, policy_confidence=excluded.policy_confidence,
        source_layer=excluded.source_layer, provenance=excluded.provenance,
        promotion_reason=excluded.promotion_reason, eviction_candidate=excluded.eviction_candidate,
        fact_key=excluded.fact_key, conflict_group=excluded.conflict_group,
        valid_from=excluded.valid_from, valid_to=excluded.valid_to,
        superseded_by=excluded.superseded_by,
        updated_at=excluded.updated_at""", values)


def decay(policy: MemoryPolicy, fact_type: str, threshold: float = .2) -> MemoryPolicy:
    confidence = max(0.0, policy.policy_confidence - {"observation": .05, "world": .02, "experience": .01}.get(fact_type, .02))
    return MemoryPolicy(**{**policy.__dict__, "policy_confidence": confidence, "eviction_candidate": confidence < threshold})


def _policy_from_row(row: sqlite3.Row) -> MemoryPolicy:
    return MemoryPolicy(
        memory_id=row["memory_id"],
        importance_score=row["importance_score"],
        tier=row["tier"],
        policy_confidence=row["policy_confidence"],
        source_layer=row["source_layer"],
        provenance=row["provenance"],
        promotion_reason=row["promotion_reason"],
        eviction_candidate=bool(row["eviction_candidate"]),
        fact_key=row["fact_key"],
        conflict_group=row["conflict_group"],
        valid_from=row["valid_from"],
        valid_to=row["valid_to"],
        superseded_by=row["superseded_by"],
    )


def current_policies(db_path: str | Path, now: str | None = None) -> list[MemoryPolicy]:
    ensure_policy_schema(db_path)
    now = now or datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT * FROM memory_policy
            WHERE superseded_by IS NULL
            AND (valid_to IS NULL OR valid_to > ?)
            ORDER BY tier, importance_score DESC, memory_id""",
            (now,),
        ).fetchall()
    return [_policy_from_row(row) for row in rows]


def policy_by_memory_id(db_path: str | Path, now: str | None = None) -> dict[str, MemoryPolicy]:
    return {policy.memory_id: policy for policy in current_policies(db_path, now=now)}


def inactive_policy_ids(db_path: str | Path, now: str | None = None) -> set[str]:
    ensure_policy_schema(db_path)
    now = now or datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        return {
            row[0]
            for row in conn.execute(
                """SELECT memory_id FROM memory_policy
                WHERE superseded_by IS NOT NULL
                OR (valid_to IS NOT NULL AND valid_to <= ?)""",
                (now,),
            ).fetchall()
        }


def apply_policy_to_candidates(
    db_path: str | Path,
    candidates: list[dict],
    now: str | None = None,
) -> list[dict]:
    policies = policy_by_memory_id(db_path, now=now)
    inactive_ids = inactive_policy_ids(db_path, now=now)
    ranked: list[dict] = []
    for item in candidates:
        memory_id = str(item.get("session_id") or item.get("object_id") or item.get("slug") or "")
        normalized_id = memory_id.removeprefix("hindsight:")
        if memory_id in inactive_ids or normalized_id in inactive_ids:
            continue
        policy = policies.get(memory_id)
        if not policy and memory_id.startswith("hindsight:"):
            policy = policies.get(normalized_id)
        adjusted = dict(item)
        base_score = float(adjusted.get("score", adjusted.get("rrf_score", 0.0)) or 0.0)
        if policy:
            tier_boost = {"core": 0.45, "mtm": 0.18, "archive": 0.02}.get(policy.tier, 0.0)
            adjusted["score"] = round(base_score + tier_boost + (policy.importance_score / 20.0) + (policy.policy_confidence / 10.0), 6)
            adjusted["policy_tier"] = policy.tier
            adjusted["policy_confidence"] = policy.policy_confidence
        else:
            adjusted["score"] = base_score
        ranked.append(adjusted)
    return sorted(ranked, key=lambda row: float(row.get("score", 0.0)), reverse=True)
