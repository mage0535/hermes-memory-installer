import json
import sqlite3
import sys
from pathlib import Path

from memory_ops.shadow_log import analyze_shadow_log, record_shadow_event

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import tiered_context_injector as injector


def test_shadow_event_records_policy_delta_without_query_or_text(tmp_path):
    db = tmp_path / "memory_governance.db"
    log_path = tmp_path / "shadow.jsonl"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """CREATE TABLE memory_policy (
            memory_id TEXT PRIMARY KEY, importance_score REAL, tier TEXT,
            policy_confidence REAL, source_layer TEXT, provenance TEXT,
            promotion_reason TEXT, eviction_candidate INTEGER,
            fact_key TEXT, conflict_group TEXT, valid_from TEXT, valid_to TEXT,
            superseded_by TEXT, created_at TEXT, updated_at TEXT
            )"""
        )
        conn.execute(
            """INSERT INTO memory_policy VALUES (
            'm2', 5.0, 'core', 1.0, 'governance', 'safe',
            'important', 0, NULL, NULL, NULL, NULL, NULL, 'now', 'now'
            )"""
        )
    candidates = [
        {"session_id": "m1", "score": 0.90, "title": "raw title", "snippet": "raw secret text"},
        {"session_id": "m2", "score": 0.20, "title": "raw title", "snippet": "raw secret text"},
    ]

    event = record_shadow_event("server password query", candidates, db, log_path, top_k=2)

    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert event["changed"] is True
    assert payload["query_hash"]
    assert payload["before_top_ids"] == ["m1", "m2"]
    assert payload["after_top_ids"] == ["m2", "m1"]
    assert payload["promoted_ids"] == ["m2"]
    assert payload["demoted_ids"] == ["m1"]
    serialized = json.dumps(payload)
    assert "server password query" not in serialized
    assert "raw secret text" not in serialized
    assert "raw title" not in serialized


def test_shadow_analysis_summarizes_7_day_decision(tmp_path):
    log_path = tmp_path / "shadow.jsonl"
    rows = [
        {"changed": True, "elapsed_ms": 3.0, "promoted_ids": ["m2"], "demoted_ids": ["m1"], "before_top_ids": ["m1"], "after_top_ids": ["m2"]},
        {"changed": False, "elapsed_ms": 2.0, "promoted_ids": [], "demoted_ids": [], "before_top_ids": ["m3"], "after_top_ids": ["m3"]},
        {"changed": True, "elapsed_ms": 4.0, "promoted_ids": ["m2"], "demoted_ids": ["m4"], "before_top_ids": ["m4"], "after_top_ids": ["m2"]},
    ]
    log_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    report = analyze_shadow_log(log_path, min_events=3)

    assert report["events"] == 3
    assert report["changed_events"] == 2
    assert report["change_rate"] == 0.6667
    assert report["avg_elapsed_ms"] == 3.0
    assert report["top_promoted_ids"][0] == {"memory_id": "m2", "count": 2}
    assert report["recommendation"] == "enable_policy_ranking_gray"


def test_tiered_context_shadow_log_does_not_change_returned_candidates(tmp_path, monkeypatch):
    db = tmp_path / "memory_governance.db"
    log_path = tmp_path / "shadow.jsonl"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """CREATE TABLE memory_policy (
            memory_id TEXT PRIMARY KEY, importance_score REAL, tier TEXT,
            policy_confidence REAL, source_layer TEXT, provenance TEXT,
            promotion_reason TEXT, eviction_candidate INTEGER,
            fact_key TEXT, conflict_group TEXT, valid_from TEXT, valid_to TEXT,
            superseded_by TEXT, created_at TEXT, updated_at TEXT
            )"""
        )
        conn.execute(
            """INSERT INTO memory_policy VALUES (
            'm2', 5.0, 'core', 1.0, 'governance', 'safe',
            'important', 0, NULL, NULL, NULL, NULL, NULL, 'now', 'now'
            )"""
        )
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", db)
    monkeypatch.setenv("MEMORY_POLICY_SHADOW_LOG_ENABLED", "true")
    monkeypatch.setenv("MEMORY_POLICY_SHADOW_LOG_PATH", str(log_path))
    monkeypatch.delenv("MEMORY_POLICY_RANKING_ENABLED", raising=False)
    candidates = [
        {"session_id": "m1", "layer": "hub", "score": 0.90, "title": "raw title", "snippet": "raw text"},
        {"session_id": "m2", "layer": "hub", "score": 0.20, "title": "raw title", "snippet": "raw text"},
    ]

    returned = injector.trim_l3_candidates("private query", candidates, top=2)

    assert [item["session_id"] for item in returned] == ["m1", "m2"]
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["after_top_ids"] == ["m2", "m1"]
    assert "private query" not in json.dumps(payload)
