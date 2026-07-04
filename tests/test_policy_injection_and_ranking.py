import sqlite3

from governance.inject_policy import inject_from_governance
from governance.policy import apply_policy_to_candidates, current_policies


def create_governance_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """CREATE TABLE memory_objects (
            object_id TEXT PRIMARY KEY,
            title TEXT,
            summary TEXT,
            source_kind TEXT,
            entity_type TEXT,
            conflict_group TEXT,
            valid_from TEXT,
            valid_to TEXT
            )"""
        )
        conn.executemany(
            "INSERT INTO memory_objects VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("m1", "API config", "current API configuration", "hindsight", "config", "api", "2026-01-01T00:00:00+00:00", None),
                ("m2", "Old API config", "old API configuration", "hindsight", "config", "api", "2025-01-01T00:00:00+00:00", "2025-12-31T00:00:00+00:00"),
                ("m3", "Daily note", "low value observation", "session", "observation", None, None, None),
            ],
        )


def test_inject_from_governance_writes_policy_rows(tmp_path):
    db = tmp_path / "gov.db"
    create_governance_db(db)

    result = inject_from_governance(db, apply=True)

    assert result["mode"] == "apply"
    assert result["proposed"] == 3
    policies = current_policies(db, now="2026-07-01T00:00:00+00:00")
    ids = {policy.memory_id for policy in policies}
    assert "m1" in ids
    assert "m2" not in ids


def test_apply_policy_to_candidates_boosts_core_and_filters_expired(tmp_path):
    db = tmp_path / "gov.db"
    create_governance_db(db)
    inject_from_governance(db, apply=True)
    candidates = [
        {"session_id": "m3", "title": "Daily note", "score": 0.9},
        {"session_id": "m1", "title": "API config", "score": 0.4},
        {"session_id": "m2", "title": "Old API config", "score": 0.95},
    ]

    ranked = apply_policy_to_candidates(db, candidates, now="2026-07-01T00:00:00+00:00")

    assert [item["session_id"] for item in ranked] == ["m1", "m3"]
    assert ranked[0]["policy_tier"] == "core"
