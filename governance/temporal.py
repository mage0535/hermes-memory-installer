import os
import sqlite3
from pathlib import Path

from runtime_paths import RuntimePaths


def _enabled(name):
    value = os.getenv(name, "false").lower()
    if value in {"true", "1", "yes"}: return True
    if value in {"false", "0", "no"}: return False
    raise ValueError(f"invalid boolean for {name}")


def temporal_retrieve(query, db_path: str | Path | None = None, mode: str = "current", now: str | None = None):
    if not _enabled("TEMPORAL_TRUTH_ENABLED"):
        return query
    if mode not in {"current", "historical"}:
        raise ValueError("mode must be current or historical")
    db = Path(db_path) if db_path is not None else RuntimePaths.from_agent_home().governance_db
    if not db.exists():
        return []
    now = now or "9999-12-31T23:59:59+00:00"
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT memory_id, fact_key, valid_from, valid_to, superseded_by
            FROM memory_policy
            WHERE fact_key LIKE ? OR memory_id LIKE ?
            ORDER BY coalesce(valid_from, '') DESC, memory_id""",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
    results = []
    for row in rows:
        expired = bool(row["valid_to"] and row["valid_to"] <= now)
        superseded = bool(row["superseded_by"])
        status = "superseded" if superseded else "expired" if expired else "current"
        if mode == "current" and status != "current":
            continue
        results.append(
            {
                "memory_id": row["memory_id"],
                "fact_key": row["fact_key"],
                "valid_from": row["valid_from"],
                "valid_to": row["valid_to"],
                "superseded_by": row["superseded_by"],
                "status": status,
            }
        )
    return results
