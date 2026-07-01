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


SCHEMA = """CREATE TABLE IF NOT EXISTS memory_policy (
memory_id TEXT PRIMARY KEY, importance_score REAL NOT NULL,
tier TEXT NOT NULL CHECK(tier IN ('core','mtm','archive')),
policy_confidence REAL NOT NULL, source_layer TEXT NOT NULL,
provenance TEXT NOT NULL, promotion_reason TEXT,
eviction_candidate INTEGER NOT NULL DEFAULT 0,
created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""


def sanitize_provenance(value: str) -> str:
    value = re.sub(r"\b(?:sk|ghp|github_pat)-?[A-Za-z0-9_-]{12,}\b", "[REDACTED]", value)
    return re.sub(r"(https?|postgresql)://[^/@\s]+@", r"\1://[REDACTED]@", value)


def ensure_policy_schema(db_path: str | Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(SCHEMA)


def upsert_policy(db_path: str | Path, policy: MemoryPolicy) -> None:
    ensure_policy_schema(db_path)
    now = datetime.now(timezone.utc).isoformat()
    values = (policy.memory_id, policy.importance_score, policy.tier, policy.policy_confidence,
              policy.source_layer, sanitize_provenance(policy.provenance), policy.promotion_reason,
              int(policy.eviction_candidate), now, now)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""INSERT INTO memory_policy VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(memory_id) DO UPDATE SET importance_score=excluded.importance_score,
        tier=excluded.tier, policy_confidence=excluded.policy_confidence,
        source_layer=excluded.source_layer, provenance=excluded.provenance,
        promotion_reason=excluded.promotion_reason, eviction_candidate=excluded.eviction_candidate,
        updated_at=excluded.updated_at""", values)


def decay(policy: MemoryPolicy, fact_type: str, threshold: float = .2) -> MemoryPolicy:
    confidence = max(0.0, policy.policy_confidence - {"observation": .05, "world": .02, "experience": .01}.get(fact_type, .02))
    return MemoryPolicy(**{**policy.__dict__, "policy_confidence": confidence, "eviction_candidate": confidence < threshold})
