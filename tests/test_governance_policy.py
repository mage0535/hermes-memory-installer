import sqlite3

import pytest

from governance.policy import MemoryPolicy, ensure_policy_schema, sanitize_provenance, upsert_policy


def test_schema_and_upsert_are_idempotent(tmp_path):
    db = tmp_path / "gov.db"
    ensure_policy_schema(db)
    policy = MemoryPolicy("m1", 4.0, "core", .8, "hindsight", "source")
    upsert_policy(db, policy)
    upsert_policy(db, policy)
    with sqlite3.connect(db) as conn:
        assert conn.execute("select count(*) from memory_policy").fetchone()[0] == 1
        columns = {row[1] for row in conn.execute("pragma table_info(memory_policy)")}
    assert not {"valid_from", "valid_to", "conflict_group", "object_confidence"} & columns


@pytest.mark.parametrize("value", ["sk-live-abcdefghijklmnopqrstuvwxyz", "postgresql://alice:secret@db.example/test", "https://bob:secret@example.test/path"])
def test_sanitize_provenance_redacts_credentials(value):
    sanitized = sanitize_provenance(value)
    assert "secret" not in sanitized and "sk-live" not in sanitized
    assert "[REDACTED]" in sanitized
