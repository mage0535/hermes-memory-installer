import sqlite3

import pytest

from governance.policy import MemoryPolicy, current_policies, ensure_policy_schema, sanitize_provenance, upsert_policy


def test_schema_and_upsert_are_idempotent(tmp_path):
    db = tmp_path / "gov.db"
    ensure_policy_schema(db)
    policy = MemoryPolicy("m1", 4.0, "core", .8, "hindsight", "source")
    upsert_policy(db, policy)
    upsert_policy(db, policy)
    with sqlite3.connect(db) as conn:
        assert conn.execute("select count(*) from memory_policy").fetchone()[0] == 1
        columns = {row[1] for row in conn.execute("pragma table_info(memory_policy)")}
    assert {"fact_key", "conflict_group", "valid_from", "valid_to", "superseded_by"} <= columns
    assert "object_confidence" not in columns


@pytest.mark.parametrize("value", ["sk-live-abcdefghijklmnopqrstuvwxyz", "postgresql://alice:secret@db.example/test", "https://bob:secret@example.test/path"])
def test_sanitize_provenance_redacts_credentials(value):
    sanitized = sanitize_provenance(value)
    assert "secret" not in sanitized and "sk-live" not in sanitized
    assert "[REDACTED]" in sanitized


def test_current_policies_filters_superseded_and_expired(tmp_path):
    db = tmp_path / "gov.db"
    upsert_policy(db, MemoryPolicy("current", 4.0, "core", .9, "hindsight", "source", fact_key="server"))
    upsert_policy(db, MemoryPolicy("old", 3.0, "archive", .5, "hindsight", "source", fact_key="server", superseded_by="current"))
    upsert_policy(db, MemoryPolicy("expired", 3.0, "archive", .5, "hindsight", "source", fact_key="topic", valid_to="2000-01-01T00:00:00+00:00"))

    active = current_policies(db)

    assert [policy.memory_id for policy in active] == ["current"]
