from pathlib import Path
import importlib.util
import json


REPO = Path(__file__).resolve().parent.parent


def load_script(name: str):
    path = REPO / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


class FakeRun:
    def __init__(self, name, status, outputs=None, start_time=None, end_time=None, error=None):
        self.name = name
        self.status = status
        self.outputs = outputs or {}
        self.start_time = start_time
        self.end_time = end_time
        self.error = error


def test_langsmith_monitor_exists_and_targets_acceptance_and_recall():
    content = (REPO / "scripts" / "langsmith_monitor.py").read_text(encoding="utf-8")
    assert "sidecar_acceptance_check.py" in content
    assert "tiered_context_injector.py" in content
    assert "LANGSMITH_PROJECT" in content
    assert "traceable" in content


def test_langsmith_monitor_defaults_to_full_acceptance_and_production_guardian_limit(monkeypatch):
    monkeypatch.delenv("MEMORY_MONITOR_ACCEPTANCE_MODE", raising=False)
    monkeypatch.delenv("MEMORY_GUARDIAN_NODE_LIMIT", raising=False)
    monitor = load_script("langsmith_monitor")

    env = monitor.child_env()

    assert monitor.MONITOR_ACCEPTANCE_MODE == "full"
    assert env["MEMORY_GUARDIAN_NODE_LIMIT"] == "30000"


def test_langsmith_task_wrapper_exists_and_uses_traceable():
    content = (REPO / "scripts" / "langsmith_task_wrapper.py").read_text(encoding="utf-8")
    assert "traceable" in content
    assert "task_name" in content
    assert "subprocess.run" in content


def test_langsmith_publish_can_be_disabled_by_env(monkeypatch):
    monitor = load_script("langsmith_monitor")
    wrapper = load_script("langsmith_task_wrapper")
    trend = load_script("langsmith_trend_report")

    monkeypatch.setenv("LANGSMITH_PUBLISH", "false")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")

    assert monitor.should_publish_langsmith(no_langsmith=False) is False
    assert wrapper.should_publish_langsmith() is False
    assert trend.should_publish_langsmith(publish_requested=True) is False


def test_langsmith_monitor_sanitizes_recall_text_before_publish():
    monitor = load_script("langsmith_monitor")
    snapshot = {
        "captured_at": "2026-01-01T00:00:00+00:00",
        "queries": ["private person relationship"],
        "acceptance": {
            "returncode": 0,
            "elapsed_s": 1.0,
            "payload": {
                "ok": True,
                "errors": [],
                "guardian": {"usage_pct": 50},
                "recalls": [
                    {
                        "query": "private person relationship",
                        "intent": "relationship",
                        "l2_count": 1,
                        "l3_count": 1,
                        "knowledge_hit": False,
                        "top_titles": ["secret title"],
                        "top_sources": [["object"]],
                    }
                ],
            },
            "command": ["/agent/scripts/sidecar_acceptance_check.py"],
            "stderr": "",
        },
        "recalls": [
            {
                "query": "private person relationship",
                "returncode": 0,
                "elapsed_s": 0.2,
                "payload": {
                    "query": "private person relationship",
                    "fused": [{"sources": ["object"], "title": "secret title"}],
                    "l2_count": 1,
                    "l3_count": 1,
                },
                "command": ["/agent/scripts/tiered_context_injector.py", "--test", "private person relationship"],
                "stderr": "",
            }
        ],
    }

    sanitized = monitor.sanitize_snapshot(snapshot)
    rendered = str(sanitized)

    assert "secret title" not in rendered
    assert "private person relationship" not in rendered
    assert sanitized["queries"][0]["query_hash"]
    assert sanitized["recalls"][0]["top_source_sets"] == [["object"]]


def test_langsmith_task_wrapper_sanitizes_raw_output_by_default():
    wrapper = load_script("langsmith_task_wrapper")
    payload = {
        "command": ["/agent/scripts/session_to_gbrain.py", "--resume"],
        "returncode": 0,
        "elapsed_s": 1.2,
        "stdout_tail": "private memory text",
        "stderr_tail": "",
        "captured_at": "2026-01-01T00:00:00+00:00",
    }

    sanitized = wrapper.sanitize_task_payload(payload)

    assert "stdout_tail" not in sanitized
    assert "stderr_tail" not in sanitized
    assert sanitized["stdout_len"] == len("private memory text")
    assert sanitized["command"] == ["session_to_gbrain.py", "--resume"]


def test_langsmith_trend_report_extracts_structured_metrics_only():
    trend = load_script("langsmith_trend_report")
    runs = [
        FakeRun(
            "memory-sidecar-monitor",
            "success",
            {
                "acceptance": {"ok": True, "elapsed_s": 3.5, "guardian": {"level": "ok", "usage_pct": 63}},
                "storage_cross_check": {
                    "payload": {
                        "ok": True,
                        "gbrain": {"health_score": 8, "missing_embeddings": 0, "orphan_pages_actual": 0},
                    }
                },
                "recalls": [{"elapsed_s": 0.2}, {"elapsed_s": 1.4, "top_titles": ["private title"]}],
            },
        ),
        FakeRun(
            "memory-sidecar-monitor",
            "success",
            {
                "acceptance": {
                    "elapsed_s": 4.5,
                    "payload": {"ok": True, "guardian": {"level": "ok", "usage_pct": 64}},
                },
                "recalls": [],
            },
        ),
        FakeRun(
            "memory-sidecar-monitor",
            "success",
            {
                "acceptance": {
                    "elapsed_s": 5.5,
                    "payload": {
                        "ok": False,
                        "errors": ["recent sessions: fused recall returned no top titles"],
                        "guardian": {"level": "ok", "usage_pct": 64, "hindsight_sync_lag_seconds": 7200},
                    },
                },
                "recalls": [],
            },
        ),
        FakeRun("session_to_gbrain", "success", {"returncode": 0, "elapsed_s": 2.0, "stdout_tail": "private text"}),
        FakeRun("archive_sessions", "error", {"returncode": 1, "elapsed_s": 5.0}),
    ]

    report = trend.build_trend_report(runs)
    rendered = str(report)

    assert report["run_count"] == 5
    assert report["error_count"] == 1
    assert report["monitor"]["count"] == 3
    assert report["monitor"]["acceptance_ok_rate"] == 0.667
    assert report["monitor"]["recent_acceptance_ok_rate"] == 0.667
    assert report["monitor"]["latest_acceptance_ok"] is True
    assert report["monitor"]["latest_gbrain_health_score"] == 8
    assert report["monitor"]["latest_guardian_usage_pct"] == 63
    assert report["monitor"]["failure_reasons"] == {"recall_coverage": 1}
    assert report["monitor"]["lag"]["latest_s"] == 7200
    assert report["monitor"]["lag"]["status"] == "degraded"
    assert report["performance"]["slowest_task_by_p95"]["name"] == "archive_sessions"
    assert report["tasks"]["session_to_gbrain"]["count"] == 1
    assert "private title" not in rendered
    assert "private text" not in rendered


def test_langsmith_trend_local_monitor_loader_unwraps_wrapper_snapshot(tmp_path):
    trend = load_script("langsmith_trend_report")
    path = tmp_path / "monitor.json"
    path.write_text(
        json.dumps(
            {
                "snapshot": {
                    "acceptance": {
                        "returncode": 0,
                        "payload": {"ok": True, "guardian": {"level": "ok", "usage_pct": 72}},
                    },
                    "recalls": [],
                },
                "langsmith": {"published": True},
            }
        ),
        encoding="utf-8",
    )

    run = trend.load_local_monitor_run(str(path))
    report = trend.build_trend_report([run])

    assert report["monitor"]["recent_acceptance_ok_rate"] == 1.0
    assert report["monitor"]["latest_guardian_level"] == "ok"


def test_langsmith_trend_separates_current_acceptance_from_historical_failures():
    trend = load_script("langsmith_trend_report")
    runs = [
        FakeRun(
            "memory-sidecar-monitor",
            "success",
            {
                "acceptance": {
                    "returncode": 0,
                    "business_ok": True,
                    "payload": {"ok": True, "guardian": {"level": "ok", "hindsight_sync_lag_seconds": 120}},
                },
                "recalls": [],
            },
        ),
        FakeRun(
            "memory-sidecar-monitor",
            "success",
            {
                "acceptance": {
                    "returncode": 1,
                    "business_ok": False,
                    "payload": {"ok": False, "errors": ["guardian level is critical"]},
                },
                "recalls": [],
            },
        ),
        FakeRun(
            "memory-sidecar-monitor",
            "success",
            {
                "acceptance": {
                    "returncode": 1,
                    "business_ok": False,
                    "payload": {"ok": False, "errors": ["guardian level is critical"]},
                },
                "recalls": [],
            },
        ),
    ]

    report = trend.build_trend_report(runs)

    assert report["monitor"]["latest_acceptance_ok"] is True
    assert report["monitor"]["current_acceptance_ok_rate"] == 1.0
    assert report["monitor"]["historical_acceptance_failure_count"] == 2
    assert report["monitor"]["current_failure_reasons"] == {}


def test_langsmith_trend_classifies_weak_recalls_by_cause():
    trend = load_script("langsmith_trend_report")
    report = trend.build_trend_report(
        [
            FakeRun(
                "memory-sidecar-monitor",
                "success",
                {
                    "acceptance": {
                        "returncode": 0,
                        "payload": {
                            "ok": True,
                            "recalls": [
                                {
                                    "intent": "relationship",
                                    "l2_count": 0,
                                    "l3_count": 0,
                                    "live_hindsight_used": True,
                                    "live_hindsight_results": 0,
                                    "timings": {"l3_s": 21.0},
                                },
                                {
                                    "intent": "knowledge",
                                    "l2_count": 0,
                                    "l3_count": 0,
                                    "live_hindsight_used": False,
                                    "live_hindsight_results": 0,
                                    "timings": {"l3_s": 0.2},
                                },
                            ],
                        },
                    },
                    "recalls": [],
                },
            )
        ]
    )

    weak = report["monitor"]["latest_weak_recalls"]
    assert weak[0]["reason"] == "retrieval_timeout"
    assert weak[1]["reason"] == "no_seed_data"
