#!/usr/bin/env python3
"""Tests for KMM knowledge note integration into memory governance."""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path
import sys
import importlib
import time

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import memory_governance_rebuild as mgr
import tiered_context_injector as injector
import archive_sessions


def test_parse_knowledge_note_extracts_metadata(tmp_path: Path):
    note = tmp_path / "personal" / "memory-system.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        """---
title: Memory System Architecture
tags:
  - memory
  - architecture
---

# Memory System Architecture

This note explains how KMM and the sidecar share durable knowledge.

It also captures retrieval constraints and graph indexing hints.
""",
        encoding="utf-8",
    )

    parsed = mgr.parse_knowledge_note(note, tmp_path)
    assert parsed is not None
    assert parsed["title"] == "Memory System Architecture"
    assert "memory" in parsed["tags"]
    assert parsed["source_path"] == "personal/memory-system.md"
    assert "share durable knowledge" in parsed["summary"]


def test_build_knowledge_note_rows_indexes_markdown_notes(tmp_path: Path, monkeypatch):
    notes_dir = tmp_path / "knowledge" / "notes"
    note = notes_dir / "shared" / "retrieval-playbook.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        """# Retrieval Playbook

Use Hindsight for durable facts, gbrain for graph traversal, and notes for curated project knowledge.
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(mgr, "KNOWLEDGE_NOTES_DIR", notes_dir)
    rows, fts_rows = mgr.build_knowledge_note_rows(indexed_at=123.0)

    assert len(rows) == 1
    assert len(fts_rows) == 1
    assert rows[0][0].startswith("note:")
    assert rows[0][2] == "Retrieval Playbook"
    assert "curated project knowledge" in rows[0][3]


def test_resolve_knowledge_notes_dir_falls_back_to_legacy_kmm_layout(tmp_path: Path, monkeypatch):
    legacy_dir = tmp_path / "knowledge" / "wiki" / "wiki"
    (legacy_dir / "concepts").mkdir(parents=True)
    monkeypatch.setattr(mgr, "AGENT_HOME", tmp_path)
    monkeypatch.setattr(mgr, "KNOWLEDGE_NOTES_DIR", tmp_path / "knowledge" / "notes")

    resolved = mgr.resolve_knowledge_notes_dir()
    assert resolved == legacy_dir


def test_query_governance_knowledge_returns_indexed_notes(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "memory_governance.db"
    monkeypatch.setattr(mgr, "GOVERNANCE_DB", db_path)
    monkeypatch.setattr(mgr, "ensure_governance_db", lambda force=False, max_age_seconds=mgr.DEFAULT_MAX_AGE_SECONDS: {"rebuilt": False})

    conn = sqlite3.connect(str(db_path))
    try:
        mgr.ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO knowledge_note_index (
                note_id, source_path, title, summary, tags, search_text, indexed_at, modified_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "note:playbook",
                "shared/retrieval-playbook.md",
                "Retrieval Playbook",
                "Curated note about graph recall and durable memory for project delivery.",
                "memory, retrieval, project",
                "Retrieval Playbook Curated note about graph recall and durable memory for project delivery.",
                123.0,
                122.0,
            ),
        )
        conn.execute(
            """
            INSERT INTO knowledge_note_index_fts (
                note_id, source_path, title, summary, tags, search_text
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "note:playbook",
                "shared/retrieval-playbook.md",
                "Retrieval Playbook",
                "Curated note about graph recall and durable memory for project delivery.",
                "memory, retrieval, project",
                "Retrieval Playbook Curated note about graph recall and durable memory for project delivery.",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    rows = mgr.query_governance_knowledge("project retrieval memory", top=3)
    assert rows
    assert rows[0]["layer"] == "knowledge"
    assert rows[0]["title"] == "Retrieval Playbook"


def test_l3_layer_plan_includes_knowledge_for_project_queries():
    plan = injector.l3_layer_plan("project retrieval playbook", top=5)
    assert any(layer == "knowledge" for layer, _ in plan)


def test_env_overrides_allow_gray_runtime_paths(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MEMORY_GOVERNANCE_DB_PATH", str(tmp_path / "gray-governance.db"))
    monkeypatch.setenv("MEMORY_KNOWLEDGE_NOTES_DIR", str(tmp_path / "gray-notes"))
    monkeypatch.setenv("MEMORY_OUTPUT_CONTEXT_PATH", str(tmp_path / "gray-context.md"))
    monkeypatch.setenv("MEMORY_OUTPUT_RECALL_PATH", str(tmp_path / "gray-recall.md"))

    mgr_reloaded = importlib.reload(mgr)
    injector_reloaded = importlib.reload(injector)
    try:
        assert mgr_reloaded.GOVERNANCE_DB == tmp_path / "gray-governance.db"
        assert mgr_reloaded.KNOWLEDGE_NOTES_DIR == tmp_path / "gray-notes"
        assert injector_reloaded.OUTPUT_CONTEXT == tmp_path / "gray-context.md"
        assert injector_reloaded.OUTPUT_RECALL == tmp_path / "gray-recall.md"
    finally:
        monkeypatch.delenv("MEMORY_GOVERNANCE_DB_PATH", raising=False)
        monkeypatch.delenv("MEMORY_KNOWLEDGE_NOTES_DIR", raising=False)
        monkeypatch.delenv("MEMORY_OUTPUT_CONTEXT_PATH", raising=False)
        monkeypatch.delenv("MEMORY_OUTPUT_RECALL_PATH", raising=False)
        importlib.reload(mgr)
        importlib.reload(injector)


def test_get_l3_returns_empty_when_no_state_or_governance(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(injector, "STATE_DB", tmp_path / "missing-state.db")
    monkeypatch.setattr(mgr, "STATE_DB", tmp_path / "missing-state.db")
    monkeypatch.setattr(mgr, "GOVERNANCE_DB", tmp_path / "missing-governance.db")
    monkeypatch.setattr(injector.governance_rebuild, "STATE_DB", tmp_path / "missing-state.db")
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", tmp_path / "missing-governance.db")
    monkeypatch.setattr(injector, "_GOVERNANCE_READY", False)
    monkeypatch.setattr(injector, "_QUERY_CACHE", {})

    rows, live_used, live_count = injector.get_l3("agent memory architecture", top=5)
    assert rows == []
    assert live_used is False
    assert live_count == 0


def test_get_l3_uses_configurable_live_hindsight_timeout(monkeypatch, tmp_path: Path):
    gov_db = tmp_path / "memory_governance.db"
    gov_db.write_text("placeholder", encoding="utf-8")
    monkeypatch.setattr(injector, "STATE_DB", tmp_path / "missing-state.db")
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(injector, "LIVE_HINDSIGHT_CIRCUIT_PATH", tmp_path / "live-hindsight-circuit.json", raising=False)
    monkeypatch.setattr(injector, "cached_governance_query", lambda *args, **kwargs: [])
    monkeypatch.setattr(injector, "should_use_live_hindsight", lambda query, candidates, top: True)
    monkeypatch.setattr(injector, "should_use_expensive_fallbacks", lambda query, candidates, top: False)
    monkeypatch.setattr(injector, "LIVE_HINDSIGHT_TIMEOUT_S", 2.0, raising=False)
    monkeypatch.setattr(injector, "LIVE_HINDSIGHT_ENABLED", True, raising=False)
    observed = {}

    def fake_urlopen(request, timeout=0):
        observed["timeout"] = timeout
        raise TimeoutError("slow hindsight")

    monkeypatch.setattr(injector.urllib.request, "urlopen", fake_urlopen)

    rows, live_used, live_count = injector.get_l3("朋友关系", top=5)

    assert rows == []
    assert live_used is True
    assert live_count == 0
    assert observed["timeout"] == 2.0


def test_get_l3_opens_live_hindsight_circuit_after_timeout(monkeypatch, tmp_path: Path):
    gov_db = tmp_path / "memory_governance.db"
    gov_db.write_text("placeholder", encoding="utf-8")
    circuit = tmp_path / "live-hindsight-circuit.json"
    monkeypatch.setattr(injector, "STATE_DB", tmp_path / "missing-state.db")
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(injector, "LIVE_HINDSIGHT_CIRCUIT_PATH", circuit, raising=False)
    monkeypatch.setattr(injector, "cached_governance_query", lambda *args, **kwargs: [])
    monkeypatch.setattr(injector, "should_use_live_hindsight", lambda query, candidates, top: True)
    monkeypatch.setattr(injector, "should_use_expensive_fallbacks", lambda query, candidates, top: False)
    monkeypatch.setattr(injector, "LIVE_HINDSIGHT_ENABLED", True, raising=False)

    def fake_urlopen(request, timeout=0):
        raise TimeoutError("slow hindsight")

    monkeypatch.setattr(injector.urllib.request, "urlopen", fake_urlopen)

    rows, live_used, live_count = injector.get_l3("agent memory architecture", top=5)

    assert rows == []
    assert live_used is True
    assert live_count == 0
    assert json.loads(circuit.read_text(encoding="utf-8"))["state"] == "open"


def test_get_l3_skips_live_hindsight_when_circuit_is_open(monkeypatch, tmp_path: Path):
    gov_db = tmp_path / "memory_governance.db"
    gov_db.write_text("placeholder", encoding="utf-8")
    circuit = tmp_path / "live-hindsight-circuit.json"
    circuit.write_text(json.dumps({"state": "open", "open_until": time.time() + 600}), encoding="utf-8")
    monkeypatch.setattr(injector, "STATE_DB", tmp_path / "missing-state.db")
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(injector, "LIVE_HINDSIGHT_CIRCUIT_PATH", circuit, raising=False)
    monkeypatch.setattr(injector, "cached_governance_query", lambda *args, **kwargs: [])
    monkeypatch.setattr(injector, "should_use_live_hindsight", lambda query, candidates, top: True)
    monkeypatch.setattr(injector, "should_use_expensive_fallbacks", lambda query, candidates, top: False)
    monkeypatch.setattr(injector, "LIVE_HINDSIGHT_ENABLED", True, raising=False)

    def fail_urlopen(request, timeout=0):
        raise AssertionError("live Hindsight should be skipped while the circuit is open")

    monkeypatch.setattr(injector.urllib.request, "urlopen", fail_urlopen)

    rows, live_used, live_count = injector.get_l3("agent memory architecture", top=5)

    assert rows == []
    assert live_used is False
    assert live_count == 0


def test_get_l3_skips_live_hindsight_by_default(monkeypatch, tmp_path: Path):
    gov_db = tmp_path / "memory_governance.db"
    gov_db.write_text("placeholder", encoding="utf-8")
    monkeypatch.setattr(injector, "STATE_DB", tmp_path / "missing-state.db")
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(injector, "LIVE_HINDSIGHT_CIRCUIT_PATH", tmp_path / "live-hindsight-circuit.json", raising=False)
    monkeypatch.setattr(injector, "LIVE_HINDSIGHT_ENABLED", False, raising=False)
    monkeypatch.setattr(injector, "cached_governance_query", lambda *args, **kwargs: [])
    monkeypatch.setattr(injector, "should_use_live_hindsight", lambda query, candidates, top: True)
    monkeypatch.setattr(injector, "should_use_expensive_fallbacks", lambda query, candidates, top: False)

    def fail_urlopen(request, timeout=0):
        raise AssertionError("foreground live Hindsight must be opt-in")

    monkeypatch.setattr(injector.urllib.request, "urlopen", fail_urlopen)

    rows, live_used, live_count = injector.get_l3("agent memory architecture", top=5)

    assert rows == []
    assert live_used is False
    assert live_count == 0


def test_cached_governance_query_invalidates_when_governance_db_changes(monkeypatch, tmp_path: Path):
    gov_db = tmp_path / "memory_governance.db"
    gov_db.write_text("v1", encoding="utf-8")
    monkeypatch.setattr(injector.governance_rebuild, "STATE_DB", tmp_path / "missing-state.db")
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(injector, "_GOVERNANCE_READY", False)
    monkeypatch.setattr(injector, "_QUERY_CACHE", {})
    monkeypatch.setattr(injector, "_ORIGINAL_ENSURE_GOVERNANCE_DB", lambda force=False, max_age_seconds=0: {"rebuilt": False})

    fetch_count = {"value": 0}

    def fetcher(query: str, top: int = 0):
        fetch_count["value"] += 1
        return [{"layer": "knowledge", "title": f"result-{fetch_count['value']}", "snippet": query}]

    first = injector.cached_governance_query("knowledge", "agent memory architecture", 3, fetcher)
    assert first[0]["title"] == "result-1"
    assert fetch_count["value"] == 1

    time.sleep(0.01)
    gov_db.write_text("v2", encoding="utf-8")

    second = injector.cached_governance_query("knowledge", "agent memory architecture", 3, fetcher)
    assert second[0]["title"] == "result-2"
    assert fetch_count["value"] == 2


def test_cached_governance_query_does_not_rebuild_inline_by_default(monkeypatch, tmp_path: Path):
    gov_db = tmp_path / "memory_governance.db"
    gov_db.write_text("v1", encoding="utf-8")
    monkeypatch.setattr(injector.governance_rebuild, "STATE_DB", tmp_path / "state.db")
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(injector, "_GOVERNANCE_READY", False)
    monkeypatch.setattr(injector, "_QUERY_CACHE", {})
    monkeypatch.setattr(injector, "RECALL_INLINE_GOVERNANCE_REBUILD", False, raising=False)

    def fail_rebuild(force=False, max_age_seconds=0):
        raise AssertionError("recall should not rebuild governance inline")

    monkeypatch.setattr(injector, "_ORIGINAL_ENSURE_GOVERNANCE_DB", fail_rebuild)

    rows = injector.cached_governance_query(
        "knowledge",
        "agent memory architecture",
        3,
        lambda query, top=0: [{"layer": "knowledge", "title": query, "snippet": str(top)}],
    )

    assert rows[0]["title"] == "agent memory architecture"


def test_cached_governance_query_can_rebuild_inline_when_enabled(monkeypatch, tmp_path: Path):
    gov_db = tmp_path / "memory_governance.db"
    gov_db.write_text("v1", encoding="utf-8")
    monkeypatch.setattr(injector.governance_rebuild, "STATE_DB", tmp_path / "state.db")
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(injector, "_GOVERNANCE_READY", False)
    monkeypatch.setattr(injector, "_QUERY_CACHE", {})
    monkeypatch.setattr(injector, "RECALL_INLINE_GOVERNANCE_REBUILD", True, raising=False)
    calls = {"value": 0}

    def count_rebuild(force=False, max_age_seconds=0):
        calls["value"] += 1
        return {"rebuilt": False}

    monkeypatch.setattr(injector, "_ORIGINAL_ENSURE_GOVERNANCE_DB", count_rebuild)

    injector.cached_governance_query("knowledge", "agent memory architecture", 3, lambda query, top=0: [])

    assert calls["value"] == 1


def test_cached_governance_query_evicts_oldest_entries_when_cache_is_bounded(monkeypatch, tmp_path: Path):
    gov_db = tmp_path / "memory_governance.db"
    gov_db.write_text("v1", encoding="utf-8")
    monkeypatch.setattr(injector.governance_rebuild, "STATE_DB", tmp_path / "missing-state.db")
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(injector, "_GOVERNANCE_READY", False)
    monkeypatch.setattr(injector, "_QUERY_CACHE", {})
    monkeypatch.setattr(injector, "_ORIGINAL_ENSURE_GOVERNANCE_DB", lambda force=False, max_age_seconds=0: {"rebuilt": False})
    monkeypatch.setattr(injector, "QUERY_CACHE_MAX_ENTRIES", 1, raising=False)

    fetch_count = {"value": 0}

    def fetcher(query: str, top: int = 0):
        fetch_count["value"] += 1
        return [{"layer": "knowledge", "title": f"{query}-{fetch_count['value']}", "snippet": query}]

    injector.cached_governance_query("knowledge", "q1", 3, fetcher)
    injector.cached_governance_query("knowledge", "q2", 3, fetcher)
    injector.cached_governance_query("knowledge", "q1", 3, fetcher)

    assert fetch_count["value"] == 3


def test_get_l2_falls_back_when_messages_fts_is_missing(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                summary TEXT,
                source TEXT,
                started_at REAL,
                ended_at REAL,
                end_reason TEXT,
                parent_session_id TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp REAL
            )
            """
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("s1", "Agent Memory Architecture", "Structured memory design", "cli", 1.0, 2.0, "", None),
        )
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            ("s1", "user", "Tell me about agent memory architecture", 1.5),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(injector, "STATE_DB", db_path)
    rows = injector.get_l2("agent memory architecture", top=3)
    assert rows
    assert rows[0]["session_id"] == "s1"


def test_archive_sessions_handles_missing_state_meta_table(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                source TEXT,
                user_id TEXT,
                model TEXT,
                title TEXT,
                started_at REAL,
                ended_at REAL,
                end_reason TEXT,
                message_count INTEGER,
                tool_call_count INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp REAL,
                tool_name TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setattr(archive_sessions, "STATE_DB", str(db_path))
    conn = archive_sessions.connect_db()
    try:
        watermark = archive_sessions.get_watermark(conn)
        assert watermark == 0
        archive_sessions.set_watermark(conn, 123.0)
        assert archive_sessions.get_watermark(conn) == 123.0
    finally:
        conn.close()


def test_archive_sessions_does_not_advance_watermark_when_publish_fails(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                source TEXT,
                title TEXT,
                started_at REAL,
                ended_at REAL,
                end_reason TEXT,
                message_count INTEGER,
                tool_call_count INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                model TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp REAL,
                tool_name TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("s1", "codex", "Test", 100.0, 200.0, "complete", 1, 0, 1, 1, "model"),
        )
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp, tool_name) VALUES (?, ?, ?, ?, ?)",
            ("s1", "user", "remember this", 110.0, ""),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(archive_sessions, "STATE_DB", str(db_path))
    conn = archive_sessions.connect_db()
    try:
        sessions = archive_sessions.fetch_sessions(
            conn,
            older_than_days=0,
            watermark=0,
            batch_size=20,
            all_sessions=False,
        )
        ok, published, max_ts = archive_sessions.publish_sessions(conn, sessions, lambda page: False)
        assert ok is False
        assert published == []
        assert max_ts == 0
        assert archive_sessions.get_watermark(conn) == 0
    finally:
        conn.close()


def test_publish_page_with_retry_handles_transient_failure(monkeypatch):
    attempts = {"count": 0}

    def flaky_publish(page):
        attempts["count"] += 1
        return attempts["count"] > 1

    monkeypatch.setattr(archive_sessions, "publish_page", flaky_publish)
    monkeypatch.setattr(archive_sessions.time, "sleep", lambda _: None)

    ok = archive_sessions.publish_page_with_retry({"slug": "demo"}, retries=1, delay=0)

    assert ok is True
    assert attempts["count"] == 2


def test_archive_connect_db_sets_busy_timeout(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "state.db"
    db_path.touch()
    monkeypatch.setattr(archive_sessions, "STATE_DB", str(db_path))

    conn = archive_sessions.connect_db()
    try:
        timeout_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    finally:
        conn.close()

    assert timeout_ms >= 30000


def test_archive_publish_sessions_emits_progress_for_each_session(tmp_path: Path, monkeypatch, capsys):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                source TEXT,
                title TEXT,
                started_at REAL,
                ended_at REAL,
                end_reason TEXT,
                message_count INTEGER,
                tool_call_count INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                model TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp REAL,
                tool_name TEXT
            )
            """
        )
        for idx in range(2):
            session_id = f"s{idx + 1}"
            conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, "codex", "Test", 100.0 + idx, 200.0 + idx, "complete", 1, 0, 1, 1, "model"),
            )
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp, tool_name) VALUES (?, ?, ?, ?, ?)",
                (session_id, "user", "remember this", 110.0 + idx, ""),
            )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(archive_sessions, "STATE_DB", str(db_path))
    conn = archive_sessions.connect_db()
    try:
        sessions = archive_sessions.fetch_sessions(
            conn,
            older_than_days=0,
            watermark=0,
            batch_size=20,
            all_sessions=False,
        )
        ok, published, max_ts = archive_sessions.publish_sessions(conn, sessions, lambda page: True)
    finally:
        conn.close()

    stderr = capsys.readouterr().err
    assert ok is True
    assert len(published) == 2
    assert max_ts == 101.0
    assert "Publishing session 1/2: session-s1" in stderr
    assert "Published session 2/2: session-s2" in stderr


def test_archive_cursor_does_not_skip_sessions_with_same_timestamp(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                source TEXT,
                title TEXT,
                started_at REAL,
                ended_at REAL,
                end_reason TEXT,
                message_count INTEGER,
                tool_call_count INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                model TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp REAL,
                tool_name TEXT
            )
            """
        )
        for session_id in ("a", "b"):
            conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, "codex", session_id, 100.0, 200.0, "complete", 0, 0, 0, 0, "model"),
            )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(archive_sessions, "STATE_DB", str(db_path))
    conn = archive_sessions.connect_db()
    try:
        first = archive_sessions.fetch_sessions(
            conn, older_than_days=0, watermark=0, batch_size=1, all_sessions=False
        )
        assert [row["id"] for row in first] == ["a"]
        archive_sessions.set_archive_cursor(conn, 100.0, "a")
        timestamp, session_id = archive_sessions.get_archive_cursor(conn)
        second = archive_sessions.fetch_sessions(
            conn,
            older_than_days=0,
            watermark=timestamp,
            batch_size=1,
            all_sessions=False,
            cursor_session_id=session_id,
        )
        assert [row["id"] for row in second] == ["b"]
    finally:
        conn.close()
