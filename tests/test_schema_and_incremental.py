#!/usr/bin/env python3
"""Tests for schema adapters and incremental rebuild helpers."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import memory_governance_rebuild as mgr
import auto_session_summary
import state_db_schema
import tiered_context_injector as injector


def test_detect_state_schema_supports_alternate_message_and_session_columns(tmp_path: Path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                summary TEXT,
                origin TEXT,
                started_at REAL,
                updated_at REAL,
                message_count INTEGER,
                prompt_tokens INTEGER,
                completion_tokens INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                text TEXT,
                created_at REAL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        schema = state_db_schema.detect_state_schema(conn)
    finally:
        conn.close()

    assert schema.session_source == "origin"
    assert schema.session_ended_at == "updated_at"
    assert schema.message_content == "text"
    assert schema.message_timestamp == "created_at"
    assert schema.session_input_tokens == "prompt_tokens"
    assert schema.session_output_tokens == "completion_tokens"
    assert schema.session_model == ""
    assert schema.session_tool_call_count == ""
    assert schema.message_tool_name == ""


def test_detect_state_schema_uses_sql_fallbacks_when_optional_columns_are_missing(tmp_path: Path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        schema = state_db_schema.detect_state_schema(conn)
    finally:
        conn.close()

    assert schema.session_source == ""
    assert schema.session_ended_at == ""
    assert schema.session_started_at == ""
    assert schema.session_summary == ""
    assert schema.session_title == ""
    assert schema.message_timestamp == ""


def test_validate_state_schema_reports_missing_required_tables(tmp_path: Path):
    conn = sqlite3.connect(str(tmp_path / "empty.db"))
    try:
        try:
            state_db_schema.validate_state_schema(conn)
        except ValueError as exc:
            message = str(exc)
        else:
            raise AssertionError("expected incompatible state schema to be rejected")
    finally:
        conn.close()

    assert "sessions" in message
    assert "messages" in message


def test_semantic_index_replacement_preserves_old_rows_when_embedding_fails(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "memory_governance.db"
    conn = sqlite3.connect(str(db_path))
    try:
        mgr.ensure_schema(conn)
        conn.execute(
            "INSERT INTO canonical_semantic_index (memory_id, chunk_index, chunk_text, embedding, indexed_at) VALUES (?, ?, ?, ?, ?)",
            ("old-memory", 0, "old text", b"old-vector", 1.0),
        )
        conn.commit()
        monkeypatch.setattr(mgr, "EMBEDDING_API_URL", "http://embedding.invalid")
        monkeypatch.setattr(mgr, "_get_embedding", lambda text: None)
        object_rows = [
            (
                "new-memory", "canonical", "project", "session", "New", "New text",
                "", "", "", "active", 0.9, 1.0, "", "", "v1", "group", "", "", 2.0,
            )
        ]

        replaced = mgr.replace_canonical_semantic_index(conn, object_rows)

        assert replaced is False
        rows = conn.execute(
            "SELECT memory_id, chunk_text FROM canonical_semantic_index ORDER BY memory_id"
        ).fetchall()
        assert rows == [("old-memory", "old text")]
    finally:
        conn.close()


def test_semantic_index_replacement_swaps_rows_only_after_all_embeddings_succeed(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "memory_governance.db"
    conn = sqlite3.connect(str(db_path))
    try:
        mgr.ensure_schema(conn)
        conn.execute(
            "INSERT INTO canonical_semantic_index (memory_id, chunk_index, chunk_text, embedding, indexed_at) VALUES (?, ?, ?, ?, ?)",
            ("old-memory", 0, "old text", b"old-vector", 1.0),
        )
        conn.commit()
        monkeypatch.setattr(mgr, "EMBEDDING_API_URL", "http://embedding.invalid")
        monkeypatch.setattr(mgr, "_get_embeddings", lambda texts: [[1.0, 0.0] for _ in texts], raising=False)
        object_rows = [
            (
                "new-memory", "canonical", "project", "session", "New", "New text",
                "", "", "", "active", 0.9, 1.0, "", "", "v1", "group", "", "", 2.0,
            )
        ]

        replaced = mgr.replace_canonical_semantic_index(conn, object_rows)

        assert replaced is True
        rows = conn.execute(
            "SELECT memory_id, chunk_text FROM canonical_semantic_index ORDER BY memory_id"
        ).fetchall()
        assert rows == [("new-memory", "New New text")]
    finally:
        conn.close()


def test_get_embedding_returns_none_when_embedding_request_fails(monkeypatch):
    monkeypatch.setattr(mgr, "EMBEDDING_API_URL", "http://embedding.invalid")
    monkeypatch.setattr(mgr.urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    result = mgr._get_embedding("agent memory architecture")

    assert result is None


def test_semantic_index_replacement_batches_embedding_requests(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "memory_governance.db"
    conn = sqlite3.connect(str(db_path))
    try:
        mgr.ensure_schema(conn)
        monkeypatch.setattr(mgr, "EMBEDDING_API_URL", "http://embedding.invalid")
        monkeypatch.setattr(mgr, "EMBEDDING_BATCH_SIZE", 2)
        monkeypatch.setattr(
            mgr,
            "_get_embedding",
            lambda text: (_ for _ in ()).throw(AssertionError("single-item embedding path should not be used")),
        )

        batch_calls: list[list[str]] = []

        def fake_get_embeddings(texts: list[str]) -> list[list[float]] | None:
            batch_calls.append(list(texts))
            return [[1.0, 0.0] for _ in texts]

        monkeypatch.setattr(mgr, "_get_embeddings", fake_get_embeddings, raising=False)
        object_rows = [
            ("memory-1", "canonical", "project", "session", "First", "Alpha text", "", "", "", "active", 0.9, 1.0, "", "", "v1", "group", "", "", 2.0),
            ("memory-2", "canonical", "project", "session", "Second", "Beta text", "", "", "", "active", 0.8, 1.0, "", "", "v1", "group", "", "", 2.0),
        ]

        replaced = mgr.replace_canonical_semantic_index(conn, object_rows)

        assert replaced is True
        assert batch_calls == [["First Alpha text", "Second Beta text"]]
    finally:
        conn.close()


def test_semantic_index_replacement_rejects_mixed_dimensions(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "memory_governance.db"
    conn = sqlite3.connect(str(db_path))
    try:
        mgr.ensure_schema(conn)
        conn.execute(
            "INSERT INTO canonical_semantic_index (memory_id, chunk_index, chunk_text, embedding, indexed_at) VALUES (?, ?, ?, ?, ?)",
            ("old-memory", 0, "old text", mgr._pack_embedding([1.0, 0.0]), 1.0),
        )
        conn.commit()
        monkeypatch.setattr(mgr, "EMBEDDING_API_URL", "http://embedding.invalid")
        monkeypatch.setattr(mgr, "_get_embeddings", lambda texts: [[1.0, 0.0], [1.0, 0.0, 0.0]])
        object_rows = [
            ("memory-1", "canonical", "project", "session", "First", "Alpha", "", "", "", "active", 0.9, 1.0, "", "", "v1", "group", "", "", 2.0),
            ("memory-2", "canonical", "project", "session", "Second", "Beta", "", "", "", "active", 0.8, 1.0, "", "", "v1", "group", "", "", 2.0),
        ]

        replaced = mgr.replace_canonical_semantic_index(conn, object_rows)

        assert replaced is False
        rows = conn.execute("SELECT memory_id FROM canonical_semantic_index").fetchall()
        assert rows == [("old-memory",)]
    finally:
        conn.close()


def test_query_canonical_semantic_skips_dimension_mismatch(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "memory_governance.db"
    conn = sqlite3.connect(str(db_path))
    try:
        mgr.ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO memory_objects (
                object_id, object_type, entity_type, source_kind, title, summary, entities,
                hub_ids, source_refs, status, confidence, freshness, valid_from, valid_to,
                version_tag, conflict_group, last_seen_at, search_text, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("old-model", "canonical", "project", "session", "Old model", "deployment memory", "", "", "", "active", 0.8, 1.0, "", "", "", "", "1.0", "old model deployment memory", 1.0),
        )
        conn.execute(
            "INSERT INTO canonical_semantic_index (memory_id, chunk_index, chunk_text, embedding, indexed_at) VALUES (?, ?, ?, ?, ?)",
            ("old-model", 0, "Old model deployment memory", mgr._pack_embedding([1.0, 0.0, 0.0]), 1.0),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(mgr, "EMBEDDING_API_URL", "http://embedding.invalid")
    monkeypatch.setattr(mgr, "GOVERNANCE_DB", db_path)
    monkeypatch.setattr(mgr, "_get_embedding", lambda text: [1.0, 0.0])

    assert mgr.query_canonical_semantic("deployment memory", top=3) == []


def test_query_canonical_semantic_prefilters_to_direct_text_matches(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "memory_governance.db"
    conn = sqlite3.connect(str(db_path))
    try:
        mgr.ensure_schema(conn)
        conn.executemany(
            """
            INSERT INTO memory_objects (
                object_id, object_type, entity_type, source_kind, title, summary, entities,
                hub_ids, source_refs, status, confidence, freshness, valid_from, valid_to,
                version_tag, conflict_group, last_seen_at, search_text, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("alpha-memory", "canonical", "project", "session", "Alpha project", "alpha deployment memory", "", "", "", "active", 0.8, 1.0, "", "", "", "", "1.0", "Alpha project alpha deployment memory", 1.0),
                ("beta-memory", "canonical", "project", "session", "Beta project", "unrelated beta memory", "", "", "", "active", 0.8, 1.0, "", "", "", "", "1.0", "Beta project unrelated beta memory", 1.0),
            ],
        )
        conn.executemany(
            "INSERT INTO canonical_semantic_index (memory_id, chunk_index, chunk_text, embedding, indexed_at) VALUES (?, ?, ?, ?, ?)",
            [
                ("alpha-memory", 0, "Alpha project deployment memory", mgr._pack_embedding([1.0, 0.0]), 1.0),
                ("beta-memory", 0, "Beta project deployment memory", mgr._pack_embedding([0.99, 0.01]), 1.0),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(mgr, "EMBEDDING_API_URL", "http://embedding.invalid")
    monkeypatch.setattr(mgr, "GOVERNANCE_DB", db_path)
    monkeypatch.setattr(mgr, "_get_embedding", lambda text: [1.0, 0.0])

    rows = mgr.query_canonical_semantic("alpha deployment", top=3)

    assert rows
    assert rows[0]["memory_id"] == "alpha-memory"
    assert all(row["memory_id"] != "beta-memory" for row in rows)


def test_query_canonical_semantic_uses_fts_search_text_candidates(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "memory_governance.db"
    conn = sqlite3.connect(str(db_path))
    try:
        mgr.ensure_schema(conn)
        conn.executemany(
            """
            INSERT INTO memory_objects (
                object_id, object_type, entity_type, source_kind, title, summary, entities,
                hub_ids, source_refs, status, confidence, freshness, valid_from, valid_to,
                version_tag, conflict_group, last_seen_at, search_text, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("fts-memory", "canonical", "project", "session", "Generic title", "Generic summary", "", "", "", "active", 0.8, 1.0, "", "", "", "", "1.0", "shadow-token project memory", 1.0),
                ("other-memory", "canonical", "project", "session", "Other title", "Other summary", "", "", "", "active", 0.8, 1.0, "", "", "", "", "1.0", "other project memory", 1.0),
            ],
        )
        conn.executemany(
            """
            INSERT INTO memory_objects_fts (
                object_id, object_type, entity_type, title, summary, entities, hub_ids, search_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("fts-memory", "canonical", "project", "Generic title", "Generic summary", "", "", "shadow-token project memory"),
                ("other-memory", "canonical", "project", "Other title", "Other summary", "", "", "other project memory"),
            ],
        )
        conn.executemany(
            "INSERT INTO canonical_semantic_index (memory_id, chunk_index, chunk_text, embedding, indexed_at) VALUES (?, ?, ?, ?, ?)",
            [
                ("fts-memory", 0, "Completely unrelated chunk text", mgr._pack_embedding([0.8, 0.2]), 1.0),
                ("other-memory", 0, "Completely unrelated chunk text", mgr._pack_embedding([1.0, 0.0]), 1.0),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(mgr, "EMBEDDING_API_URL", "http://embedding.invalid")
    monkeypatch.setattr(mgr, "GOVERNANCE_DB", db_path)
    monkeypatch.setattr(mgr, "_get_embedding", lambda text: [1.0, 0.0])

    rows = mgr.query_canonical_semantic("shadow-token", top=3)

    assert rows
    assert rows[0]["memory_id"] == "fts-memory"
    assert all(row["memory_id"] != "other-memory" for row in rows)


def test_compute_knowledge_notes_signature_changes_when_note_changes(tmp_path: Path):
    notes_dir = tmp_path / "knowledge" / "notes"
    note = notes_dir / "sample.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Sample\n\nhello", encoding="utf-8")

    first = mgr.compute_knowledge_notes_signature(notes_dir)
    note.write_text("# Sample\n\nhello world", encoding="utf-8")
    second = mgr.compute_knowledge_notes_signature(notes_dir)

    assert first
    assert second
    assert first != second


def test_compute_knowledge_notes_signature_detects_same_size_same_mtime_rewrite(tmp_path: Path):
    notes_dir = tmp_path / "knowledge" / "notes"
    note = notes_dir / "sample.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Sample\n\nalpha", encoding="utf-8")
    original_stat = note.stat()

    first = mgr.compute_knowledge_notes_signature(notes_dir)
    note.write_text("# Sample\n\nbravo", encoding="utf-8")
    os.utime(note, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    second = mgr.compute_knowledge_notes_signature(notes_dir)

    assert note.stat().st_size == original_stat.st_size
    assert note.stat().st_mtime_ns == original_stat.st_mtime_ns
    assert first != second


def test_refresh_knowledge_note_index_reuses_existing_rows_when_signature_unchanged(tmp_path: Path, monkeypatch):
    notes_dir = tmp_path / "knowledge" / "notes"
    note = notes_dir / "guide.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Guide\n\nstable body", encoding="utf-8")

    db_path = tmp_path / "memory_governance.db"
    conn = sqlite3.connect(str(db_path))
    try:
        mgr.ensure_schema(conn)
        monkeypatch.setattr(mgr, "KNOWLEDGE_NOTES_DIR", notes_dir)

        first = mgr.refresh_knowledge_note_index(conn, indexed_at=100.0)
        assert first["reused"] is False
        assert first["count"] == 1

        def fail_build(*args, **kwargs):
            raise AssertionError("knowledge rows should be reused when signature is unchanged")

        monkeypatch.setattr(mgr, "build_knowledge_note_rows", fail_build)
        second = mgr.refresh_knowledge_note_index(conn, indexed_at=200.0)
        assert second["reused"] is True
        assert second["count"] == 1
    finally:
        conn.close()


def test_auto_session_summary_works_with_alternate_schema(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                summary TEXT,
                origin TEXT,
                started_at REAL,
                updated_at REAL,
                message_count INTEGER,
                prompt_tokens INTEGER,
                completion_tokens INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                text TEXT,
                created_at REAL
            )
            """
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("s1", "Project update", None, "codex", 1.0, 2.0, 4, 120, 80),
        )
        conn.executemany(
            "INSERT INTO messages (session_id, role, text, created_at) VALUES (?, ?, ?, ?)",
            [
                ("s1", "user", "Please summarize project alpha blockers", 1.1),
                ("s1", "assistant", "Blocked by schema drift in the adapter layer", 1.2),
                ("s1", "user", "Need a durable summary for the next session", 1.3),
                ("s1", "assistant", "Summary will mention the adapter migration work", 1.4),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(auto_session_summary, "STATE_DB", db_path)
    assert auto_session_summary.main() == 0

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT summary FROM sessions WHERE id = 's1'").fetchone()
        assert row is not None
        assert "Session recap" in row[0]
        assert "project alpha blockers" in row[0]
    finally:
        conn.close()


def test_tiered_context_l2_works_with_alternate_schema(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                summary TEXT,
                origin TEXT,
                started_at REAL,
                updated_at REAL,
                end_reason TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                text TEXT,
                created_at REAL
            )
            """
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("alt-1", "Agent Memory Architecture", "Knowledge routing", "codex", 1.0, 2.0, ""),
        )
        conn.execute(
            "INSERT INTO messages (session_id, role, text, created_at) VALUES (?, ?, ?, ?)",
            ("alt-1", "user", "Need the agent memory architecture summary", 1.5),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(injector, "STATE_DB", db_path)
    rows = injector.get_l2("agent memory architecture", top=3)
    assert rows
    assert rows[0]["session_id"] == "alt-1"


def test_governance_rebuild_works_with_alternate_schema(monkeypatch, tmp_path: Path):
    state_db = tmp_path / "state.db"
    gov_db = tmp_path / "memory_governance.db"
    conn = sqlite3.connect(str(state_db))
    try:
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                summary TEXT,
                origin TEXT,
                started_at REAL,
                updated_at REAL,
                messages_count INTEGER,
                prompt_tokens INTEGER,
                completion_tokens INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                text TEXT,
                created_at REAL
            )
            """
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g1", "Adapter Migration", "Schema compatibility work", "codex", 10.0, 20.0, 3, 140, 90),
        )
        conn.executemany(
            "INSERT INTO messages (session_id, role, text, created_at) VALUES (?, ?, ?, ?)",
            [
                ("g1", "user", "Need governance rebuild to support alternate state schema", 10.5),
                ("g1", "assistant", "Will adapt rebuild queries to origin/text/updated_at", 11.0),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(mgr, "STATE_DB", state_db)
    monkeypatch.setattr(mgr, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(mgr, "fetch_hindsight_memories", lambda: [])
    monkeypatch.setattr(mgr, "embed_canonical_objects", lambda conn, rows: None)

    stats = mgr.rebuild_index(force=True)
    assert stats["rebuilt"] is True
    assert stats["sessions_indexed"] == 1

    conn = sqlite3.connect(str(gov_db))
    try:
        row = conn.execute("SELECT source, title, first_user FROM session_index WHERE session_id = 'g1'").fetchone()
        assert row is not None
        assert row[0] == "codex"
        assert row[1] == "Adapter Migration"
        assert "alternate state schema" in row[2]
    finally:
        conn.close()
