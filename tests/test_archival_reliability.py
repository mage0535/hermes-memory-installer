#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import session_to_gbrain


def test_mcp_tool_error_is_not_treated_as_success(monkeypatch):
    class Response:
        def read(self):
            return json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "isError": True,
                        "content": [{"type": "text", "text": "write rejected"}],
                    },
                }
            ).encode("utf-8")

    monkeypatch.setattr(session_to_gbrain._urllib, "urlopen", lambda *args, **kwargs: Response())

    try:
        session_to_gbrain._mcp_call("put_page", {"slug": "x", "content": "y"})
    except subprocess.CalledProcessError as exc:
        assert "write rejected" in str(exc)
    else:
        raise AssertionError("MCP tool errors must fail the archive operation")


def test_gbrain_page_exists_uses_shared_bridge_and_handles_failure(monkeypatch):
    calls = []

    def fail(args, input_text=None):
        calls.append(args)
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(session_to_gbrain, "run_gbrain", fail)

    assert session_to_gbrain.gbrain_page_exists("missing-page") is False
    assert calls == [["get", "missing-page"]]


def test_failed_gbrain_page_is_not_reported_as_created(monkeypatch):
    info = {
        "session_id": "session-1",
        "title": "Test session",
        "created_at": "2026-06-19T10:00:00+08:00",
        "topics": [],
        "summary": "A durable memory",
        "first_msg": "Remember this",
        "user_msgs": 1,
        "assistant_msgs": 1,
        "size": 100,
    }
    monkeypatch.setattr(session_to_gbrain, "ensure_gbrain_page", lambda *args, **kwargs: False)

    assert session_to_gbrain.create_gbrain_page(info) is None


def test_gbrain_page_frontmatter_escapes_user_title(monkeypatch):
    info = {
        "session_id": "session-quote",
        "title": 'Deploy "gray"\nwithout downtime',
        "created_at": "2026-06-19T10:00:00+08:00",
        "topics": [],
        "summary": "A durable memory",
        "first_msg": "Remember this",
        "user_msgs": 1,
        "assistant_msgs": 1,
        "size": 100,
    }
    captured = {}

    def capture_page(slug, content, tags, timeline_entry=None):
        captured["content"] = content
        return True

    monkeypatch.setattr(session_to_gbrain, "ensure_gbrain_page", capture_page)

    assert session_to_gbrain.create_gbrain_page(info) == "session-session-quote"
    frontmatter = captured["content"].split("---", 2)[1]
    payload = yaml.safe_load(frontmatter)
    assert payload["title"] == 'Deploy "gray"\nwithout downtime'


def test_session_extraction_normalizes_content_blocks(tmp_path: Path):
    session_file = tmp_path / "session_blocks.json"
    session_file.write_text(
        json.dumps(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Remember project alpha"},
                            {"type": "tool_result", "content": "ignored tool payload"},
                        ],
                    },
                    {
                        "role": "assistant",
                        "content": {"text": "Project alpha is ready for gray testing."},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    info = session_to_gbrain.extract_session_info(session_file)

    assert info is not None
    assert info["first_msg"] == "Remember project alpha"
    assert info["summary"] == "Project alpha is ready for gray testing."


def test_session_extraction_rejects_unrecoverable_json(tmp_path: Path):
    session_file = tmp_path / "session_broken.json"
    session_file.write_text('{"messages": [{"role": "user", "content": "unfinished"', encoding="utf-8")

    info = session_to_gbrain.extract_session_info(session_file)

    assert info is None
    assert not session_file.with_suffix(".json.repaired").exists()


def test_failed_gbrain_page_does_not_advance_checkpoint(monkeypatch, tmp_path: Path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    session_file = sessions_dir / "session_failed.json"
    session_file.write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "user", "content": "Remember this"},
                    {"role": "assistant", "content": "This must be archived"},
                ]
            }
        ),
        encoding="utf-8",
    )
    checkpoint = tmp_path / "checkpoint.json"
    monkeypatch.setattr(session_to_gbrain, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(session_to_gbrain, "CHECKPOINT_FILE", checkpoint)
    monkeypatch.setattr(session_to_gbrain, "create_topic_hubs", lambda **kwargs: [])
    monkeypatch.setattr(session_to_gbrain, "create_gbrain_page", lambda info, dry_run=False: None)
    monkeypatch.setattr(sys, "argv", ["session_to_gbrain.py", "--batch=1"])

    result = session_to_gbrain.main()

    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert result == 1
    assert "session_failed.json" not in payload["processed_sessions"]


def test_dry_run_does_not_advance_checkpoint(monkeypatch, tmp_path: Path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "session_dry.json").write_text(
        json.dumps({"messages": [{"role": "user", "content": "Preview only"}]}),
        encoding="utf-8",
    )
    checkpoint = tmp_path / "checkpoint.json"
    monkeypatch.setattr(session_to_gbrain, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(session_to_gbrain, "CHECKPOINT_FILE", checkpoint)
    monkeypatch.setattr(session_to_gbrain, "create_topic_hubs", lambda **kwargs: [])
    monkeypatch.setattr(sys, "argv", ["session_to_gbrain.py", "--batch=1", "--dry-run"])

    result = session_to_gbrain.main()

    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["processed_sessions"] == []
