import importlib.util
import json
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def load_script(name: str):
    path = REPO / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def test_session_to_gbrain_discovers_mcp_token_from_config(monkeypatch, tmp_path):
    script = load_script("session_to_gbrain")
    agent_home = tmp_path / "agent"
    agent_home.mkdir()
    (agent_home / "config.yaml").write_text(
        "mcp_servers:\n  gbrain:\n    url: http://127.0.0.1:8787/mcp\n    headers:\n      Authorization: Bearer test-token-123\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("GBRAIN_MCP_TOKEN", raising=False)
    monkeypatch.setenv("AGENT_HOME", str(agent_home))

    assert script._discover_gbrain_token() == "test-token-123"


def test_session_to_gbrain_skips_request_dumps_by_default(monkeypatch, tmp_path):
    script = load_script("session_to_gbrain")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "request_dump_1.json").write_text("{}", encoding="utf-8")
    (sessions_dir / "session_1.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(script, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(script, "INCLUDE_REQUEST_DUMPS", False)

    rows = script.get_unprocessed_sessions(set(), batch_size=10)

    assert [item.name for item in rows] == ["session_1.json"]


def test_langsmith_task_wrapper_marks_business_failure_from_json_stdout():
    wrapper = load_script("langsmith_task_wrapper")
    payload = {
        "command": ["/agent/scripts/sidecar_acceptance_check.py"],
        "returncode": 1,
        "elapsed_s": 1.0,
        "stdout_tail": json.dumps({"ok": False, "reason_buckets": {"guardian": 1}, "errors": ["guardian level is critical"]}),
        "stderr_tail": "",
        "captured_at": "2026-01-01T00:00:00+00:00",
    }

    sanitized = wrapper.sanitize_task_payload(payload)

    assert sanitized["execution_ok"] is False
    assert sanitized["business_ok"] is False
    assert sanitized["business_reason_buckets"] == {"guardian": 1}


def test_langsmith_trend_report_separates_execution_and_business_success():
    trend = load_script("langsmith_trend_report")

    class FakeRun:
        def __init__(self, name, status, outputs=None, error=None):
            self.name = name
            self.status = status
            self.outputs = outputs or {}
            self.error = error
            self.start_time = None
            self.end_time = None

    runs = [
        FakeRun(
            "memory-sidecar-monitor",
            "success",
            {
                "acceptance": {"returncode": 0, "execution_ok": True, "business_ok": False, "payload": {"ok": False, "errors": ["guardian level is critical"], "guardian": {"level": "critical"}}},
                "recalls": [],
            },
        ),
        FakeRun(
            "session_to_gbrain",
            "success",
            {"returncode": 1, "execution_ok": False, "business_ok": False, "elapsed_s": 2.0},
        ),
    ]

    report = trend.build_trend_report(runs)

    assert report["monitor"]["execution_ok_rate"] == 1.0
    assert report["monitor"]["acceptance_ok_rate"] == 0.0
    assert report["tasks"]["session_to_gbrain"]["success_rate"] == 1.0
    assert report["tasks"]["session_to_gbrain"]["business_success_rate"] == 0.0


def test_alert_queue_emits_only_transition_and_resolved_notifications():
    alert_queue = load_script("alert_queue")
    previous = {
        "alerts": {
            "langsmith-trend:hindsight_lag": {
                "source": "langsmith-trend",
                "code": "hindsight_lag",
                "severity": "action-needed",
            }
        }
    }
    current = [
        {
            "captured_at": "2026-01-01T00:00:00+00:00",
            "source": "gbrain-stale",
            "code": "gbrain_stale_action_needed",
            "severity": "action-needed",
            "detail": {},
        }
    ]

    notifications = alert_queue.diff_notifications(previous, current)

    codes = {row["code"] for row in notifications}
    assert "gbrain_stale_action_needed" in codes
    assert "hindsight_lag_resolved" in codes


def test_memory_guardian_overflow_grace_avoids_false_critical(monkeypatch):
    monkeypatch.setenv("MEMORY_GUARDIAN_NODE_LIMIT", "20000")
    guardian = load_script("memory_guardian")
    monkeypatch.setattr(
        guardian,
        "hs",
        lambda method, path, body=None, timeout=10: {
            "/stats": {
                "total_documents": 100,
                "total_nodes": 20162,
                "total_observations": 500,
                "pending_consolidation": 0,
                "failed_consolidation": 0,
                "pending_operations": 0,
                "failed_operations": 0,
                "last_consolidated_at": "2026-07-10T01:00:00+00:00",
            },
            "/entities": {"items": []},
        }[path],
    )
    monkeypatch.setattr(guardian, "read_governance_meta", lambda: {})
    monkeypatch.setattr(guardian, "summarize_guardian_history", lambda window=12: {})

    _, cap = guardian.monitor(verbose=False)

    assert cap["level"] == "action"
    assert cap["overflow_grace_nodes"] >= 100


def test_gbrain_stale_report_marks_auto_fix_attempt(monkeypatch):
    stale = load_script("gbrain_stale_maintenance")
    health_calls = 0

    def fake_run(command, timeout=300):
        nonlocal health_calls
        if command[-1] == "health":
            health_calls += 1
            if health_calls > 1:
                return {
                    "returncode": 0,
                    "stdout": "Health score: 10/10\nMissing embeddings: 0\nStale pages: 0\nOrphan pages: 0\n",
                    "stderr": "",
                }
            return {
                "returncode": 0,
                "stdout": "Health score: 6/10\nMissing embeddings: 147\nStale pages: 296\nOrphan pages: 31\n",
                "stderr": "",
            }
        return {
            "returncode": 0,
            "stdout": "Embedded 12 chunks" if "embed" in command else "",
            "stderr": "",
        }

    monkeypatch.setattr(stale, "run", fake_run)
    monkeypatch.setattr(stale, "actual_orphan_count", lambda: 0)

    report = stale.build_report(refresh_embeddings=True, reindex_code=False, output="")

    assert report["auto_fix_attempted"] is True
    assert report["auto_fix_succeeded"] is True
    assert report["auto_fix_failed"] is False


def test_gbrain_stale_targets_missing_embedding_slugs_before_embed_all(monkeypatch):
    stale = load_script("gbrain_stale_maintenance")
    health_calls = 0

    def fake_run(command, timeout=300):
        nonlocal health_calls
        if command[-1] == "health":
            health_calls += 1
            if health_calls > 1:
                return {
                    "returncode": 0,
                    "stdout": "Health score: 8/10\nMissing embeddings: 0\nStale pages: 922\nOrphan pages: 1\n",
                    "stderr": "",
                }
            return {
                "returncode": 0,
                "stdout": "Health score: 6/10\nMissing embeddings: 1\nStale pages: 922\nOrphan pages: 1\n",
                "stderr": "",
            }
        if command[:3] == ["gbrain", "embed", "--slugs"]:
            return {"returncode": 0, "stdout": "hub-orphans-sessions: embedded 1 chunks\n", "stderr": ""}
        if command[:3] == ["gbrain-embed", "embed", "--stale"]:
            return {"returncode": 0, "stdout": "Embedded 0 chunks (0 stale found)\n", "stderr": ""}
        if command == [stale.GBRAIN_DEORPHAN_BIN]:
            return {"returncode": 0, "stdout": "Orphans reported: 1\nOrphans to index: 0\n", "stderr": ""}
        raise AssertionError(command)

    monkeypatch.setattr(stale, "run", fake_run)
    monkeypatch.setattr(stale, "actual_orphan_count", lambda: 0)
    monkeypatch.setattr(stale, "find_missing_embedding_slugs", lambda limit=10: ["hub-orphans-sessions"])

    report = stale.build_report(refresh_embeddings=True, reindex_code=False, output="", stale_budget=100, missing_budget=0)

    names = [action["name"] for action in report["actions"]]
    assert "embed_missing_slugs" in names
    assert "embed_all" not in names
    assert report["status"] == "healthy"
    assert report["auto_fix_succeeded"] is True


def test_gbrain_stale_embeds_missing_slugs_created_by_deorphan(monkeypatch):
    stale = load_script("gbrain_stale_maintenance")
    health_calls = 0
    commands = []

    def fake_run(command, timeout=300):
        nonlocal health_calls
        commands.append(command)
        if command[-1] == "health":
            health_calls += 1
            if health_calls == 1:
                return {
                    "returncode": 0,
                    "stdout": "Health score: 8/10\nMissing embeddings: 0\nStale pages: 0\nOrphan pages: 1\n",
                    "stderr": "",
                }
            if health_calls == 2:
                return {
                    "returncode": 0,
                    "stdout": "Health score: 6/10\nMissing embeddings: 1\nStale pages: 0\nOrphan pages: 1\n",
                    "stderr": "",
                }
            return {
                "returncode": 0,
                "stdout": "Health score: 8/10\nMissing embeddings: 0\nStale pages: 0\nOrphan pages: 1\n",
                "stderr": "",
            }
        if command == [stale.GBRAIN_DEORPHAN_BIN]:
            return {"returncode": 0, "stdout": "Orphans reported: 1\nOrphans to index: 1\n", "stderr": ""}
        if command[:3] == ["gbrain", "embed", "--slugs"]:
            return {"returncode": 0, "stdout": "hub-orphans-sessions: embedded 1 chunks\n", "stderr": ""}
        raise AssertionError(command)

    monkeypatch.setattr(stale, "run", fake_run)
    monkeypatch.setattr(stale, "actual_orphan_count", lambda: 0)
    monkeypatch.setattr(stale, "find_missing_embedding_slugs", lambda limit=10: ["hub-orphans-sessions"])

    report = stale.build_report(refresh_embeddings=True, reindex_code=False, output="", stale_budget=100, missing_budget=0)

    assert ["gbrain", "embed", "--slugs", "hub-orphans-sessions"] in commands
    assert report["status"] == "healthy"
    assert report["auto_fix_succeeded"] is True


def test_gbrain_stale_refresh_uses_budgeted_stale_command(monkeypatch):
    stale = load_script("gbrain_stale_maintenance")
    commands = []
    health_calls = 0

    def fake_run(command, timeout=300):
        nonlocal health_calls
        commands.append(command)
        if command[-1] == "health":
            health_calls += 1
            return {
                "returncode": 0,
                "stdout": "Health score: 8/10\nMissing embeddings: 0\nStale pages: 918\nOrphan pages: 0\n",
                "stderr": "",
            }
        return {"returncode": 0, "stdout": "Embedded 50 chunks", "stderr": ""}

    monkeypatch.setattr(stale, "run", fake_run)
    monkeypatch.setattr(stale, "actual_orphan_count", lambda: 0)

    report = stale.build_report(refresh_embeddings=True, reindex_code=False, output="", stale_budget=50)

    assert ["gbrain-embed", "embed", "--stale", "--limit", "50"] in commands
    assert ["gbrain-embed", "embed", "--all"] not in commands
    assert report["refresh_budget"] == {"stale": 50, "missing": 0}


def test_gbrain_deorphan_index_returns_explicit_link_plan(tmp_path):
    script = load_script("gbrain_deorphan_index")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    orphans = [
        {"slug": "session-alpha", "title": "Alpha"},
        {"slug": "session-beta", "title": "Beta"},
    ]

    slugs, plan = script.write_index_pages(out_dir, orphans)

    assert slugs == ["hub-orphans-sessions"]
    assert plan == {"hub-orphans-sessions": ["session-alpha", "session-beta"]}


def test_gbrain_stale_filters_generated_orphan_indexes(monkeypatch):
    stale = load_script("gbrain_stale_maintenance")

    def fake_run(command, timeout=300):
        if command[-2:] == ["orphans", "--json"]:
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "orphans": [
                            {"slug": "hub-orphan-index"},
                            {"slug": "hub-orphans-sessions"},
                            {"slug": "real-page"},
                        ]
                    }
                ),
                "stderr": "",
            }
        if command[-2:] == ["orphans", "--count"]:
            return {"returncode": 0, "stdout": "3", "stderr": ""}
        return {"returncode": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(stale, "run", fake_run)

    assert stale.actual_orphan_count() == 1


def test_gbrain_stale_classifies_non_actionable_stale_pages_as_info():
    stale = load_script("gbrain_stale_maintenance")
    health = {"stale_pages": 10, "missing_embeddings": 0, "orphan_pages": 0, "orphan_pages_actual": 0}
    effects = {"stale_pages_changed": False, "embed_stale_found_chunks": 1, "reindex_code_failures": None}

    rows = stale.classify_health(health, effects)

    assert rows[0]["code"] == "stale_health_counter_not_embedding_stale"
    assert rows[0]["severity"] == "info"


def test_gbrain_stale_status_only_uses_previous_panel_only_evidence(monkeypatch, tmp_path):
    stale = load_script("gbrain_stale_maintenance")
    previous = tmp_path / "gbrain-stale-latest.json"
    previous.write_text(
        json.dumps(
            {
                "classifications": [
                    {"code": "stale_health_counter_not_embedding_stale", "severity": "info", "count": 1108},
                    {"code": "reported_orphans_counter_discrepancy", "severity": "info", "count": 1},
                ],
                "after": {"missing_embeddings": 0, "orphan_pages_actual": 0},
            }
        ),
        encoding="utf-8",
    )

    def fake_run(command, timeout=300):
        if command[-1] == "health":
            return {
                "returncode": 0,
                "stdout": "Health score: 8/10\nMissing embeddings: 0\nStale pages: 1108\nOrphan pages: 1\n",
                "stderr": "",
            }
        if command == [stale.GBRAIN_DEORPHAN_BIN]:
            return {"returncode": 0, "stdout": "Orphans reported: 1\nOrphans to index: 0\n", "stderr": ""}
        raise AssertionError(command)

    monkeypatch.setattr(stale, "run", fake_run)
    monkeypatch.setattr(stale, "actual_orphan_count", lambda: 0)

    report = stale.build_report(refresh_embeddings=False, reindex_code=False, output="", previous_report_path=previous)

    assert report["status"] == "healthy"
    assert report["ok"] is True
    assert {row["severity"] for row in report["classifications"]} == {"info"}
