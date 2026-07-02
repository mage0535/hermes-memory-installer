import json
import sqlite3

from gbrain_edges.hindsight_feeder import build_candidates_from_governance
from governance.temporal import temporal_retrieve
from mtm.consolidator import MidTermMemory, consolidate


def test_gbrain_feeder_builds_candidates_from_governance(tmp_path):
    db = tmp_path / "gov.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE memory_objects (object_id TEXT, title TEXT, entity_type TEXT, source_kind TEXT, conflict_group TEXT, valid_from TEXT)")
        conn.executemany(
            "INSERT INTO memory_objects VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("project-alpha", "Project Alpha", "project", "hindsight", "alpha", "2026-01-01"),
                ("project-alpha-note", "Project Alpha Note", "project", "session", "alpha", "2026-01-02"),
                ("project-beta", "Project Beta", "project", "hindsight", "beta", "2026-01-03"),
            ],
        )

    candidates = build_candidates_from_governance(db)

    planned_edges = {(edge.source, edge.target, edge.edge_type) for edge in candidates}
    assert ("project-alpha", "project-alpha-note", "semantic") in planned_edges
    assert ("project-alpha", "project-alpha-note", "temporal") in planned_edges
    assert ("project-alpha", "project-alpha-note", "structure") in planned_edges


def test_gbrain_feeder_uses_entity_type_when_conflict_groups_are_unique(tmp_path):
    db = tmp_path / "gov.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE memory_objects (object_id TEXT, title TEXT, entity_type TEXT, source_kind TEXT, conflict_group TEXT, valid_from TEXT)")
        conn.executemany(
            "INSERT INTO memory_objects VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("alpha-1", "Alpha One", "project", "hindsight", "unique-a", "2026-01-01"),
                ("alpha-2", "Alpha Two", "project", "session", "unique-b", "2026-01-02"),
            ],
        )

    candidates = build_candidates_from_governance(db)

    assert any(edge.edge_type == "structure" for edge in candidates)


def test_temporal_retrieve_filters_current_and_marks_historical(tmp_path, monkeypatch):
    db = tmp_path / "gov.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE memory_policy (memory_id TEXT, fact_key TEXT, valid_from TEXT, valid_to TEXT, superseded_by TEXT)")
        conn.executemany(
            "INSERT INTO memory_policy VALUES (?, ?, ?, ?, ?)",
            [
                ("current", "server", "2026-01-01T00:00:00+00:00", None, None),
                ("old", "server", "2025-01-01T00:00:00+00:00", "2025-12-31T00:00:00+00:00", "current"),
            ],
        )
    monkeypatch.setenv("TEMPORAL_TRUTH_ENABLED", "true")

    current = temporal_retrieve("server", db_path=db, mode="current", now="2026-07-01T00:00:00+00:00")
    historical = temporal_retrieve("server", db_path=db, mode="historical", now="2026-07-01T00:00:00+00:00")

    assert [item["memory_id"] for item in current] == ["current"]
    assert {item["status"] for item in historical} == {"current", "superseded"}


def test_mtm_consolidates_and_promotes_high_value_items(tmp_path, monkeypatch):
    store = tmp_path / "mtm.jsonl"
    db = tmp_path / "gov.db"
    mtm = MidTermMemory(store)
    mtm.retain("API key storage policy should be remembered", source="test")
    mtm.retain("minor transient log line", source="test")
    monkeypatch.setenv("MTM_ENABLED", "true")

    result = consolidate(store_path=store, governance_db=db, apply=True)

    assert result["status"] == "consolidated"
    assert result["promoted"] == 1
    rows = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["status"] == "promoted"
