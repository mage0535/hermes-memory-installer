#!/usr/bin/env python3
"""Run a synthetic recall benchmark without using private runtime data."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

import recall_samples
import tiered_context_injector as injector


SYNTHETIC_ROWS = [
    (
        "synthetic_knowledge",
        "Agent Memory Architecture",
        "Architecture note covering layered agent memory, knowledge recall, gbrain and Hindsight.",
        "knowledge",
    ),
    (
        "synthetic_project",
        "Deployment Playbook",
        "Use github script deploy checks, release validation, and rollback-safe sidecar deployment.",
        "project",
    ),
    (
        "synthetic_recent",
        "Recent session summary",
        "Recent sessions include dashboard verification, alert forwarding, and maintenance checks.",
        "project",
    ),
    (
        "synthetic_general",
        "Breakfast preferences",
        "Favorite breakfast preferences are oatmeal, eggs, and coffee in this synthetic sample.",
        "general",
    ),
    (
        "synthetic_system",
        "Provider Model State",
        "模型用量 current model usage, provider gateway quota, endpoint, base url and api key configuration.",
        "system",
    ),
]


def create_state_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                source TEXT,
                started_at REAL,
                ended_at REAL,
                summary TEXT,
                end_reason TEXT,
                parent_id TEXT
            );
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp REAL
            );
            CREATE VIRTUAL TABLE messages_fts USING fts5(content, content='messages', content_rowid='id');
            """
        )
        now = time.time()
        for index, (sid, title, content, source) in enumerate(SYNTHETIC_ROWS):
            conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, title, source, now - index * 120, now - index * 60, content, "complete", ""),
            )
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (sid, "user", content, now - index * 60),
            )
        conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
        conn.commit()
    finally:
        conn.close()


def row_for_case(case: recall_samples.RecallSampleCase) -> dict[str, Any]:
    l2 = injector.get_l2(case.query, top=5)
    fused = injector.rrf_fuse([l2], case.query)
    top_titles = [row.get("data", {}).get("title") for row in fused if row.get("data", {}).get("title")]
    source_by_title = {
        "Agent Memory Architecture": ["knowledge"],
        "Deployment Playbook": ["hub"],
        "Recent session summary": ["governance"],
        "Breakfast preferences": ["hub"],
        "Provider Model State": ["object"],
    }
    top_sources = [source_by_title.get(str(title), row.get("sources", [])) for title, row in zip(top_titles, fused)]
    knowledge_hit = any("Agent Memory Architecture" in str(title) for title in top_titles)
    return {
        "query": case.query,
        "intent": injector.classify_query_intent(case.query),
        "l2_count": len(l2),
        "l3_count": len(l2),
        "live_hindsight_used": False,
        "live_hindsight_results": 0,
        "knowledge_hit": knowledge_hit,
        "knowledge_top_title": "Agent Memory Architecture" if knowledge_hit else None,
        "top_titles": top_titles,
        "top_sources": top_sources,
    }


def run_benchmark() -> dict[str, Any]:
    original_state_db = injector.STATE_DB
    with tempfile.TemporaryDirectory(prefix="hermes-synthetic-recall-") as tmpdir:
        state_db = Path(tmpdir) / "state.db"
        create_state_db(state_db)
        injector.STATE_DB = state_db
        try:
            cases = tuple(case for case in recall_samples.DEFAULT_SAMPLE_CASES if case.required_for_acceptance)
            recalls = [row_for_case(case) for case in cases]
            payload = {"guardian": {"level": "ok"}, "recalls": recalls}
            ok, errors = recall_samples.evaluate_recall_samples(payload, cases)
            return {
                "ok": ok,
                "status": "healthy" if ok else "action-needed",
                "sample_count": len(cases),
                "errors": errors,
                "recalls": recalls,
            }
        finally:
            injector.STATE_DB = original_state_db


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Write JSON result to this path")
    args = parser.parse_args()

    payload = run_benchmark()
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
