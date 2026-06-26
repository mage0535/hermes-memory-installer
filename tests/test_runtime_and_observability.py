#!/usr/bin/env python3
"""Tests for runtime config, ranking, and observability helpers."""

from __future__ import annotations

from pathlib import Path
from http.server import ThreadingHTTPServer
import importlib
import json
import os
import sqlite3
import subprocess
import sys
import threading
import urllib.request
import urllib.error

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import memory_family_registry as family_registry
import memory_guardian as guardian
import recall_samples
import sidecar_acceptance_check as acceptance_check
import tiered_context_injector as injector
import alert_queue
import alert_webhook_receiver
import metrics_dashboard
import metrics_dashboard_server
import openmetrics_exporter
import gbrain_stale_maintenance
import profile_isolation_soak
import synthetic_recall_benchmark


def test_atomic_write_text_replaces_complete_file(monkeypatch, tmp_path: Path):
    target = tmp_path / "context.md"
    target.write_text("old\n", encoding="utf-8")
    real_replace = os.replace
    replace_calls = []

    def tracked_replace(src, dst):
        replace_calls.append((Path(src), Path(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(injector.os, "replace", tracked_replace)

    injector.atomic_write_text(target, "new content\n")

    assert target.read_text(encoding="utf-8") == "new content\n"
    assert replace_calls
    assert replace_calls[0][1] == target


def test_generate_writes_context_and_proactive_recall(monkeypatch, tmp_path: Path):
    context_path = tmp_path / "TIERED_CONTEXT.md"
    recall_path = tmp_path / "PROACTIVE_RECALL.md"
    monkeypatch.setattr(injector, "OUTPUT_CONTEXT", context_path)
    monkeypatch.setattr(injector, "OUTPUT_RECALL", recall_path)
    monkeypatch.setattr(injector, "get_l1", lambda: [])
    monkeypatch.setattr(
        injector,
        "get_l2",
        lambda query: [
            {
                "session_id": "session-1",
                "title": "Deployment Memory",
                "snippet": "Use a gray deployment first.",
                "layer": "fts5",
                "score": 0.8,
            }
        ],
    )
    monkeypatch.setattr(injector, "get_l3", lambda query: ([], False, 0))
    monkeypatch.setattr(injector, "record_recall_metrics", lambda *args, **kwargs: None)
    monkeypatch.setattr(injector, "adjust_with_feedback", lambda rows: rows)
    monkeypatch.setattr(injector, "route_context", lambda rows, query: {"decision": "inject", "count": len(rows)})

    injector.generate(["deployment safety"])

    assert context_path.exists()
    assert recall_path.exists()
    assert "Recall: deployment safety" in context_path.read_text(encoding="utf-8")
    recall_text = recall_path.read_text(encoding="utf-8")
    assert "Proactive Recall" in recall_text
    assert "deployment safety" in recall_text
    assert "Deployment Memory" in recall_text


def test_knowledge_query_promotes_knowledge_layer_for_architecture_queries():
    fused = [
        {
            "rrf_score": 0.061,
            "sources": ["hub"],
            "data": {"title": "Coding And Tooling Memory", "snippet": "general coding hub", "slug": "hub:coding"},
        },
        {
            "rrf_score": 0.058,
            "sources": ["object"],
            "data": {"title": "General Agent Notes", "snippet": "generic project memory", "slug": "object:1"},
        },
        {
            "rrf_score": 0.055,
            "sources": ["knowledge"],
            "data": {
                "title": "Agent Memory Architecture",
                "snippet": "Structured wiki note about layered memory architecture and knowledge recall.",
                "slug": "note:concepts/agent_memory.md",
            },
        },
    ]

    reranked = injector.rerank_fused("agent memory architecture", fused)
    assert reranked[0]["sources"] == ["knowledge"]
    assert reranked[0]["data"]["title"] == "Agent Memory Architecture"


def test_system_query_prefers_object_over_hindsight_for_usage_queries():
    fused = [
        {
            "rrf_score": 0.061,
            "sources": ["hindsight"],
            "data": {"title": "Recent memory summary", "snippet": "generic system memory"},
        },
        {
            "rrf_score": 0.059,
            "sources": ["object"],
            "data": {"title": "当前模型用量", "snippet": "provider usage and gateway quota details"},
        },
    ]

    reranked = injector.rerank_fused("模型用量", fused)
    assert reranked[0]["sources"] == ["object"]
    assert reranked[0]["data"]["title"] == "当前模型用量"


def test_system_query_object_search_has_expansion_terms():
    content = (REPO / "scripts" / "memory_governance_rebuild.py").read_text(encoding="utf-8")
    for term in ("model", "usage", "provider", "gateway", "quota", "endpoint", "api key", "base url"):
        assert f'"{term}"' in content
    for term in ("模型", "用量", "配置", "网关"):
        assert f'"{term}"' in content


def test_system_query_prefers_authoritative_object_even_when_hindsight_scores_higher():
    fused = [
        {
            "rrf_score": 0.09,
            "sources": ["hindsight"],
            "data": {
                "title": "Personal conversation summary",
                "snippet": "model usage wording appears in an unrelated private conversation",
            },
        },
        {
            "rrf_score": 0.052,
            "sources": ["object"],
            "data": {
                "title": "Provider Model State: deepseek",
                "snippet": "current model provider gateway quota endpoint usage details",
            },
        },
    ]

    reranked = injector.rerank_fused("model usage", fused)
    assert reranked[0]["sources"] == ["object"]
    assert reranked[0]["data"]["title"] == "Provider Model State: deepseek"


def test_system_query_skips_live_hindsight_when_authoritative_object_exists():
    candidates = [
        {
            "layer": "object",
            "title": "Gateway Endpoint Configuration",
            "snippet": "current provider base url endpoint api gateway configuration",
            "score": 0.9,
        }
    ]

    assert injector.should_use_live_hindsight("model usage", candidates, top=5) is False


def test_recent_query_skips_live_hindsight_when_cached_candidates_are_sufficient():
    candidates = [
        {"layer": "object", "title": f"Recent session {idx}", "snippet": "recent sessions summary", "score": 0.9}
        for idx in range(5)
    ]

    assert injector.should_use_live_hindsight("recent sessions", candidates, top=5) is False


def test_knowledge_queries_have_dedicated_intent():
    assert injector.classify_query_intent("agent memory architecture") == "knowledge"
    assert injector.classify_query_intent("retrieval playbook") == "knowledge"


def test_chinese_system_queries_are_classified_without_mojibake_markers():
    assert family_registry.is_system_query_text("模型用量") is True
    assert injector.classify_query_intent("模型用量") == "system"
    assert injector.classify_query_intent("重启 Hermes 网关") == "system"


def test_acceptance_check_tracks_knowledge_hit_metadata():
    content = (REPO / "scripts" / "sidecar_acceptance_check.py").read_text(encoding="utf-8")
    assert "knowledge_hit" in content
    assert "knowledge_top_title" in content


def test_acceptance_query_set_is_deduplicated_and_extensible(monkeypatch):
    monkeypatch.setenv("MEMORY_ACCEPTANCE_EXTRA_QUERIES", "github script deploy,custom gray probe,agent memory architecture")

    queries = acceptance_check.build_queries()

    assert queries.count("github script deploy") == 1
    assert queries.count("agent memory architecture") == 1
    assert "custom gray probe" in queries


def test_acceptance_check_fails_when_required_knowledge_query_misses():
    payload = {
        "guardian": {"level": "ok"},
        "recalls": [
            {
                "query": "agent memory architecture",
                "intent": "knowledge",
                "l2_count": 2,
                "l3_count": 2,
                "live_hindsight_used": False,
                "live_hindsight_results": 0,
                "knowledge_hit": False,
                "knowledge_top_title": None,
                "top_titles": ["Generic Memory Notes"],
                "top_sources": [["hub"]],
            }
        ],
    }

    ok, errors = acceptance_check.evaluate_payload(payload)
    assert ok is False
    assert any("agent memory architecture" in error for error in errors)


def test_acceptance_check_allows_historical_failed_consolidation_when_guardian_is_ok():
    payload = {
        "guardian": {
            "level": "ok",
            "failed_consolidation": 3,
            "pending_consolidation": 3,
        },
        "recalls": [
            {
                "query": "agent memory architecture",
                "intent": "knowledge",
                "l2_count": 2,
                "l3_count": 2,
                "live_hindsight_used": False,
                "live_hindsight_results": 0,
                "knowledge_hit": True,
                "knowledge_top_title": "Agent Memory Architecture",
                "top_titles": ["Agent Memory Architecture"],
                "top_sources": [["knowledge"]],
            },
            {
                "query": next(case.query for case in recall_samples.DEFAULT_SAMPLE_CASES if case.expected_intent == "system"),
                "intent": "system",
                "l2_count": 1,
                "l3_count": 1,
                "live_hindsight_used": False,
                "live_hindsight_results": 0,
                "knowledge_hit": False,
                "knowledge_top_title": None,
                "top_titles": ["当前模型用量"],
                "top_sources": [["object"]],
            },
        ],
    }

    ok, errors = acceptance_check.evaluate_payload(payload)
    assert all("failed_consolidation" not in error for error in errors)


def test_acceptance_check_passes_when_required_queries_meet_thresholds():
    payload = {
        "guardian": {"level": "ok"},
        "recalls": [
            {
                "query": "agent memory architecture",
                "intent": "knowledge",
                "l2_count": 2,
                "l3_count": 3,
                "live_hindsight_used": False,
                "live_hindsight_results": 0,
                "knowledge_hit": True,
                "knowledge_top_title": "Agent Memory Architecture",
                "top_titles": ["Agent Memory Architecture"],
                "top_sources": [["knowledge"]],
            },
            {
                "query": "模型用量",
                "intent": "system",
                "l2_count": 1,
                "l3_count": 1,
                "live_hindsight_used": False,
                "live_hindsight_results": 0,
                "knowledge_hit": False,
                "knowledge_top_title": None,
                "top_titles": ["当前模型用量"],
                "top_sources": [["object"]],
            }
            ,
            {
                "query": "github script deploy",
                "intent": "project",
                "l2_count": 1,
                "l3_count": 2,
                "live_hindsight_used": False,
                "live_hindsight_results": 0,
                "knowledge_hit": False,
                "knowledge_top_title": None,
                "top_titles": ["Deployment Playbook"],
                "top_sources": [["hub"]],
            },
                {
                    "query": "recent sessions",
                    "intent": "recent",
                    "l2_count": 1,
                    "l3_count": 1,
                "live_hindsight_used": False,
                "live_hindsight_results": 0,
                "knowledge_hit": False,
                "knowledge_top_title": None,
                "top_titles": ["Recent session summary"],
                "top_sources": [["governance"]],
            },
            {
                "query": "朋友关系",
                "intent": "relationship",
                "l2_count": 0,
                "l3_count": 1,
                "live_hindsight_used": False,
                "live_hindsight_results": 0,
                "knowledge_hit": False,
                "knowledge_top_title": None,
                "top_titles": ["朋友关系纪要"],
                "top_sources": [["object"]],
            },
            {
                "query": "favorite breakfast preferences",
                "intent": "general",
                "l2_count": 1,
                "l3_count": 0,
                "live_hindsight_used": False,
                "live_hindsight_results": 0,
                "knowledge_hit": False,
                "knowledge_top_title": None,
                "top_titles": ["Breakfast preferences"],
                "top_sources": [["hub"]],
            },
        ],
    }

    ok, errors = acceptance_check.evaluate_payload(payload)
    assert ok is True
    assert errors == []


def test_acceptance_error_buckets_group_operator_reasons():
    errors = [
        "guardian level is critical",
        "recent sessions: fused recall returned no top titles",
        "agent memory architecture: expected top sources to contain knowledge",
    ]

    assert acceptance_check.bucket_acceptance_errors(errors) == {
        "guardian": 1,
        "knowledge_recall": 1,
        "recall_coverage": 1,
    }


def test_fast_acceptance_skips_l3_slow_path(monkeypatch):
    monkeypatch.setattr(
        acceptance_check.injector,
        "get_l2",
        lambda query, top=5: [{"session_id": "s", "title": "T", "snippet": "S", "layer": "fts5", "score": 1.0}],
    )

    def fail_l3(*args, **kwargs):
        raise AssertionError("fast acceptance must not call L3")

    monkeypatch.setattr(acceptance_check.injector, "get_l3", fail_l3)
    monkeypatch.setattr(
        acceptance_check.injector,
        "rrf_fuse",
        lambda groups, query: [{"sources": ["fts5"], "data": {"title": "T"}}],
    )

    rows = acceptance_check.run_recall_checks("fast")

    assert rows
    assert all(row["l3_count"] == 0 for row in rows)
    assert all(row["timings"]["l3_s"] == 0.0 for row in rows)


def test_alert_queue_treats_historical_failures_as_info(tmp_path: Path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "runtime-drift-latest.json").write_text(
        json.dumps({"status": "healthy", "reasons": []}),
        encoding="utf-8",
    )
    (metrics / "langsmith-trend-latest.json").write_text(
        json.dumps(
            {
                "monitor": {
                    "acceptance_ok_rate": 0.5,
                    "recent_acceptance_ok_rate": 1.0,
                    "failure_reasons": {"guardian": 1},
                    "recent_failures": [],
                    "lag": {"status": "healthy"},
                }
            }
        ),
        encoding="utf-8",
    )
    (metrics / "gbrain-stale-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
    (metrics / "hindsight-security-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")

    status, alerts = alert_queue.build_alerts(metrics)

    assert status == "healthy"
    assert alerts == [
        {
            "captured_at": alerts[0]["captured_at"],
            "source": "langsmith-trend",
            "code": "historical_acceptance_failures",
            "severity": "info",
            "detail": {"acceptance_ok_rate": 0.5, "failure_reasons": {"guardian": 1}, "recent_failures": []},
        }
    ]


def test_alert_webhook_receiver_queues_payload(tmp_path: Path):
    queue = tmp_path / "inbound.jsonl"
    status = tmp_path / "status.json"
    handler = alert_webhook_receiver.make_handler(queue, status, "", 1)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/alerts"
        request = urllib.request.Request(
            url,
            data=json.dumps({"status": "action-needed", "alerts": [{"code": "x"}]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 202
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    rows = [json.loads(line) for line in queue.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["payload"]["status"] == "action-needed"
    assert json.loads(status.read_text(encoding="utf-8"))["status"] == "healthy"


def test_alert_webhook_receiver_rotates_queue(tmp_path: Path):
    queue = tmp_path / "inbound.jsonl"
    for index in range(5):
        alert_webhook_receiver.append_jsonl(queue, {"index": index})

    rotated = alert_webhook_receiver.rotate_jsonl(queue, 2)

    assert rotated is True
    assert [json.loads(line)["index"] for line in queue.read_text(encoding="utf-8").splitlines()] == [3, 4]
    assert [json.loads(line)["index"] for line in (tmp_path / "inbound.jsonl.1").read_text(encoding="utf-8").splitlines()] == [0, 1, 2]


def test_alert_webhook_receiver_formats_telegram_payload(monkeypatch):
    monkeypatch.setenv("MEMORY_ALERT_TELEGRAM_CHAT_ID", "12345")

    body = alert_webhook_receiver.build_forward_body(
        "telegram",
        {"status": "action-needed", "alert_count": 1, "alerts": [{"severity": "action-needed", "source": "runtime", "code": "x"}]},
    )

    assert body["chat_id"] == "12345"
    assert "Hermes Memory alert" in body["text"]


def test_alert_webhook_receiver_retries_forward(monkeypatch):
    calls = {"count": 0}

    def flaky_forward(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("temporary failure")
        return {"status": 200, "reason": "OK"}

    monkeypatch.setattr(alert_webhook_receiver, "forward_payload_once", flaky_forward)
    monkeypatch.setattr(alert_webhook_receiver.time, "sleep", lambda _: None)

    result = alert_webhook_receiver.forward_payload("http://example.test", {"status": "action-needed"}, 1, attempts=2)

    assert result["status"] == 200
    assert result["attempts"] == 2


def test_alert_webhook_receiver_writes_dead_letter_on_forward_failure(tmp_path: Path, monkeypatch):
    queue = tmp_path / "inbound.jsonl"
    dead_letter = tmp_path / "failed.jsonl"
    status = tmp_path / "status.json"
    monkeypatch.setattr(
        alert_webhook_receiver,
        "forward_payload",
        lambda *args, **kwargs: {"error": "forward_failed", "attempts": 1},
    )
    handler = alert_webhook_receiver.make_handler(
        queue,
        status,
        "http://example.test",
        1,
        dead_letter_path=dead_letter,
        retry_attempts=1,
        retry_backoff_s=0,
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/alerts",
            data=json.dumps({"status": "action-needed"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 202
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert dead_letter.exists()
    assert json.loads(status.read_text(encoding="utf-8"))["dead_letter_written"] is True


def test_alert_webhook_receiver_replays_dead_letter_successfully(tmp_path: Path, monkeypatch):
    dead_letter = tmp_path / "failed.jsonl"
    alert_webhook_receiver.append_jsonl(dead_letter, {"received_at": "t1", "payload": {"status": "action-needed"}})
    monkeypatch.setattr(alert_webhook_receiver, "forward_payload", lambda *args, **kwargs: {"status": 200, "attempts": 1})

    report = alert_webhook_receiver.replay_dead_letters(
        dead_letter,
        "http://example.test",
        timeout=1,
        attempts=1,
        backoff_s=0,
    )

    assert report["ok"] is True
    assert report["replayed"] == 1
    assert report["remaining"] == 0
    assert dead_letter.read_text(encoding="utf-8") == ""


def test_metrics_dashboard_renders_status_cards(tmp_path: Path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "runtime-drift-latest.json").write_text(json.dumps({"status": "healthy", "ok": True}), encoding="utf-8")
    (metrics / "health-summary-latest.json").write_text(
        json.dumps(
            {
                "status": "healthy",
                "ok": True,
                "alert_count": 1,
                "alerts": [{"code": "historical_acceptance_failures", "severity": "info", "detail": {"recent_failures": [{"run_name": "memory-sidecar-monitor"}]}}],
            }
        ),
        encoding="utf-8",
    )
    (metrics / "langsmith-trend-latest.json").write_text(
        json.dumps(
            {
                "run_count": 5,
                "monitor": {
                    "recent_acceptance_ok_rate": 1.0,
                    "acceptance_ok_rate": 0.9,
                    "lag": {"status": "healthy"},
                    "recent_failures": [{"run_name": "memory-sidecar-monitor", "reasons": ["guardian"]}],
                },
            }
        ),
        encoding="utf-8",
    )
    (metrics / "gbrain-stale-latest.json").write_text(
        json.dumps({"status": "healthy", "ok": True, "after": {"health_score": 9, "stale_pages": 47}}),
        encoding="utf-8",
    )
    (metrics / "hindsight-security-latest.json").write_text(
        json.dumps({"status": "healthy", "ok": True}),
        encoding="utf-8",
    )
    (metrics / "webhook-receiver-latest.json").write_text(
        json.dumps({"status": "healthy", "ok": True, "last_forward": {"status": 200, "reason": "OK", "attempts": 1}}),
        encoding="utf-8",
    )

    html = metrics_dashboard.render_dashboard(metrics, lang="zh")
    html_en = metrics_dashboard.render_dashboard(metrics, lang="en")

    assert 'lang="zh-CN"' in html
    assert "#section-alerts" in html
    assert "#section-components" in html
    assert "historical_acceptance_failures" in html
    assert "47" in html
    assert "HTTP 200" in html
    assert "{&#x27;status&#x27;: 200" not in html
    assert "Hermes Memory Dashboard" in html_en
    assert "Runtime Drift" in html_en
    assert "Language" in html_en
    assert "Success, HTTP 200, 1 attempt(s)" in html_en
    payload = metrics_dashboard.build_dashboard_payload(metrics)
    assert payload["artifacts"][0]["name"] == "Runtime Drift"


def test_metrics_dashboard_server_requires_token(tmp_path: Path):
    handler = metrics_dashboard_server.make_handler(tmp_path, "secret")
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            urllib.request.urlopen(f"{base}/dashboard", timeout=5)
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("dashboard should require a token")
        with urllib.request.urlopen(f"{base}/dashboard?token=secret", timeout=5) as response:
            assert response.status == 200
            body = response.read().decode("utf-8")
            assert 'lang="zh-CN"' in body
            assert "#section-alerts" in body
        with urllib.request.urlopen(f"{base}/dashboard?token=secret&lang=en", timeout=5) as response:
            assert response.status == 200
            body = response.read().decode("utf-8")
            assert "Hermes Memory Dashboard" in body
            assert "Language" in body
        with urllib.request.urlopen(f"{base}/api/status?token=secret", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
            assert "artifacts" in payload
        with urllib.request.urlopen(f"{base}/metrics?token=secret", timeout=5) as response:
            text = response.read().decode("utf-8")
            assert response.status == 200
            assert "hermes_memory_component_status" in text
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_metrics_dashboard_infers_langsmith_healthy_without_top_level_status():
    summary = metrics_dashboard.summarize(
        "LangSmith Trend",
        {
            "run_count": 3,
            "monitor": {
                "recent_acceptance_ok_rate": 1.0,
                "acceptance_ok_rate": 0.9,
                "lag": {"status": "healthy"},
            },
        },
    )

    assert summary["status"] == "healthy"
    assert summary["ok"] is True


def test_openmetrics_exporter_counts_alert_queues(tmp_path: Path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "health-summary-latest.json").write_text(json.dumps({"status": "healthy", "alert_count": 2}), encoding="utf-8")
    (metrics / "webhook-receiver-latest.json").write_text(
        json.dumps({"status": "degraded", "last_forward": {"error": "forward_failed", "attempts": 3}}),
        encoding="utf-8",
    )
    (metrics / "gbrain-stale-latest.json").write_text(
        json.dumps(
            {
                "status": "healthy",
                "after": {"health_score": 9},
                "classifications": [{"category": "upstream_gbrain_gap"}],
            }
        ),
        encoding="utf-8",
    )
    (metrics / "inbound-alert-webhook.jsonl").write_text("{}\n{}\n", encoding="utf-8")
    (metrics / "failed-alert-webhook.jsonl").write_text("{}\n", encoding="utf-8")

    text = openmetrics_exporter.render_openmetrics(metrics)

    assert 'hermes_memory_alert_count 2' in text
    assert 'hermes_memory_webhook_queue_lines{queue="inbound"} 2' in text
    assert 'hermes_memory_webhook_queue_lines{queue="dead_letter"} 1' in text
    assert 'hermes_memory_gbrain_upstream_gap_active 1' in text


def test_synthetic_recall_benchmark_passes_public_dataset():
    payload = synthetic_recall_benchmark.run_benchmark()

    assert payload["ok"] is True
    assert payload["sample_count"] >= 5
    assert payload["errors"] == []


def test_gbrain_stale_upstream_gap_is_explicit_for_panel_only_debt():
    classifications = [
        {
            "code": "stale_health_counter_not_embedding_stale",
            "severity": "info",
            "count": 47,
        }
    ]

    gap = gbrain_stale_maintenance.upstream_gap(classifications)

    assert gap["active"] is True
    assert "JSON" in gap["required_capability"]
    assert gap["public_request"] == "docs/gbrain-stale-upstream-request.md"


def test_manifest_respects_agent_home_per_profile(tmp_path: Path):
    homes = [tmp_path / "agent-a", tmp_path / "agent-b"]
    outputs = []
    for home in homes:
        (home / "scripts").mkdir(parents=True)
        env = {**os.environ, "AGENT_HOME": str(home)}
        result = subprocess.run(
            [
                sys.executable,
                str(REPO / "bin" / "hermes-memory"),
                "manifest",
                "--format",
                "json",
                "--repo-root",
                str(REPO),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        outputs.append(json.loads(result.stdout))

    assert outputs[0]["agent_home"] == str(homes[0])
    assert outputs[1]["agent_home"] == str(homes[1])
    assert outputs[0]["scripts_dir"] != outputs[1]["scripts_dir"]


def test_profile_isolation_soak_uses_separate_agent_homes():
    report = profile_isolation_soak.soak(REPO, iterations=1, interval_s=0, timeout=20)

    assert report["ok"] is True
    assert len({row["profile"] for row in report["runs"]}) == 2


def test_dashboard_info_command_does_not_print_token(tmp_path: Path):
    token_file = tmp_path / "dashboard-token"
    token_file.write_text("secret-token", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "bin" / "hermes-memory"),
            "dashboard-info",
            "--token-file",
            str(token_file),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["token_configured"] is True
    assert "secret-token" not in result.stdout
    assert payload["token_file"] == str(token_file)


def test_recall_sample_suite_enforces_intent_and_source_thresholds():
    payload = {
        "guardian": {"level": "ok"},
        "recalls": [
            {
                "query": "agent memory architecture",
                "intent": "knowledge",
                "l2_count": 3,
                "l3_count": 5,
                "top_titles": ["Agent Memory Architecture"],
                "top_sources": [["knowledge"]],
                "knowledge_hit": True,
                "knowledge_top_title": "Agent Memory Architecture",
            },
            {
                "query": "模型用量",
                "intent": "system",
                "l2_count": 1,
                "l3_count": 1,
                "top_titles": ["当前模型用量"],
                "top_sources": [["object"]],
                "knowledge_hit": False,
                "knowledge_top_title": None,
            },
            {
                "query": "github script deploy",
                "intent": "project",
                "l2_count": 1,
                "l3_count": 2,
                "top_titles": ["Deployment Playbook"],
                "top_sources": [["hub"]],
                "knowledge_hit": False,
                "knowledge_top_title": None,
            },
            {
                "query": "recent sessions",
                "intent": "recent",
                "l2_count": 1,
                "l3_count": 1,
                "top_titles": ["Recent session summary"],
                "top_sources": [["governance"]],
                "knowledge_hit": False,
                "knowledge_top_title": None,
            },
            {
                "query": "朋友关系",
                "intent": "relationship",
                "l2_count": 0,
                "l3_count": 1,
                "top_titles": ["朋友关系纪要"],
                "top_sources": [["object"]],
                "knowledge_hit": False,
                "knowledge_top_title": None,
            },
            {
                "query": "favorite breakfast preferences",
                "intent": "general",
                "l2_count": 1,
                "l3_count": 0,
                "top_titles": ["Breakfast preferences"],
                "top_sources": [["hub"]],
                "knowledge_hit": False,
                "knowledge_top_title": None,
            },
        ],
    }

    ok, errors = recall_samples.evaluate_recall_samples(payload, recall_samples.DEFAULT_SAMPLE_CASES)
    assert ok is True
    assert errors == []


def test_recall_sample_suite_reports_missing_required_source():
    payload = {
        "guardian": {"level": "ok"},
        "recalls": [
            {
                "query": "agent memory architecture",
                "intent": "knowledge",
                "l2_count": 1,
                "l3_count": 2,
                "top_titles": ["Generic Notes"],
                "top_sources": [["hub"]],
                "knowledge_hit": False,
                "knowledge_top_title": None,
            }
        ],
    }

    ok, errors = recall_samples.evaluate_recall_samples(payload, recall_samples.DEFAULT_SAMPLE_CASES)
    assert ok is False
    assert any("expected source" in error for error in errors)


def test_default_recall_suite_covers_major_intent_families():
    intents = {sample.expected_intent for sample in recall_samples.DEFAULT_SAMPLE_CASES}
    assert len(recall_samples.DEFAULT_SAMPLE_CASES) >= 6
    assert {"knowledge", "system", "project", "relationship", "recent", "general"}.issubset(intents)


def test_optional_recall_samples_do_not_block_acceptance_without_domain_data():
    optional = recall_samples.RecallSampleCase(
        query="private-domain-query",
        expected_intent="relationship",
        min_l3=1,
        required_for_acceptance=False,
    )
    payload = {
        "recalls": [
            {
                "query": "private-domain-query",
                "intent": "relationship",
                "l2_count": 0,
                "l3_count": 0,
                "top_titles": [],
                "top_sources": [],
            }
        ]
    }

    ok, errors = recall_samples.evaluate_recall_samples(payload, (optional,))

    assert ok is True
    assert errors == []


def test_default_recall_suite_requires_project_and_recent_queries():
    payload = {
        "guardian": {"level": "ok"},
        "recalls": [
            {
                "query": "agent memory architecture",
                "intent": "knowledge",
                "l2_count": 2,
                "l3_count": 2,
                "top_titles": ["Agent Memory Architecture"],
                "top_sources": [["knowledge"]],
                "knowledge_hit": True,
                "knowledge_top_title": "Agent Memory Architecture",
            },
            {
                "query": "模型用量",
                "intent": "system",
                "l2_count": 1,
                "l3_count": 1,
                "top_titles": ["当前模型用量"],
                "top_sources": [["object"]],
                "knowledge_hit": False,
                "knowledge_top_title": None,
            },
        ],
    }

    ok, errors = recall_samples.evaluate_recall_samples(payload, recall_samples.DEFAULT_SAMPLE_CASES)

    assert ok is False
    assert any("github script deploy: missing recall sample" in error for error in errors)
    assert any("recent sessions: missing recall sample" in error for error in errors)


def test_default_recall_suite_requires_relationship_and_general_queries():
    payload = {
        "guardian": {"level": "ok"},
        "recalls": [
            {
                "query": "agent memory architecture",
                "intent": "knowledge",
                "l2_count": 2,
                "l3_count": 2,
                "top_titles": ["Agent Memory Architecture"],
                "top_sources": [["knowledge"]],
                "knowledge_hit": True,
                "knowledge_top_title": "Agent Memory Architecture",
            },
            {
                "query": "模型用量",
                "intent": "system",
                "l2_count": 1,
                "l3_count": 1,
                "top_titles": ["当前模型用量"],
                "top_sources": [["object"]],
                "knowledge_hit": False,
                "knowledge_top_title": None,
            },
            {
                "query": "github script deploy",
                "intent": "project",
                "l2_count": 1,
                "l3_count": 1,
                "top_titles": ["Deployment Playbook"],
                "top_sources": [["hub"]],
                "knowledge_hit": False,
                "knowledge_top_title": None,
            },
            {
                "query": "recent sessions",
                "intent": "recent",
                "l2_count": 1,
                "l3_count": 1,
                "top_titles": ["Recent session summary"],
                "top_sources": [["governance"]],
                "knowledge_hit": False,
                "knowledge_top_title": None,
            },
        ],
    }

    ok, errors = recall_samples.evaluate_recall_samples(payload, recall_samples.DEFAULT_SAMPLE_CASES)

    assert ok is False
    assert all("朋友关系: missing recall sample" not in error for error in errors)
    assert any("favorite breakfast preferences: missing recall sample" in error for error in errors)


def test_recall_metric_query_is_private_by_default(monkeypatch):
    monkeypatch.setattr(injector, "METRICS_STORE_RAW_QUERY", False)
    stored = injector.metric_query_value("private customer project details")

    assert stored.startswith("sha256:")
    assert "private customer" not in stored


def test_recall_metric_history_is_bounded(tmp_path: Path):
    db_path = tmp_path / "metrics.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE recall_metrics (id INTEGER PRIMARY KEY AUTOINCREMENT, query TEXT)")
        conn.executemany("INSERT INTO recall_metrics (query) VALUES (?)", [(str(i),) for i in range(10)])
        injector.prune_recall_metrics(conn, max_rows=4)
        rows = conn.execute("SELECT query FROM recall_metrics ORDER BY id").fetchall()
    finally:
        conn.close()

    assert rows == [("6",), ("7",), ("8",), ("9",)]


def test_recall_feedback_adjusts_candidate_order(monkeypatch):
    rows = [
        {
            "rrf_score": 0.02,
            "sources": ["knowledge"],
            "data": {"title": "Preferred", "snippet": "useful memory"},
        },
        {
            "rrf_score": 0.021,
            "sources": ["object"],
            "data": {"title": "Rejected", "snippet": "stale memory"},
        },
    ]
    preferred_key = injector.feedback_key_for_candidate(rows[0])
    rejected_key = injector.feedback_key_for_candidate(rows[1])
    monkeypatch.setattr(
        injector,
        "load_recall_feedback_scores",
        lambda: {preferred_key: 2.0, rejected_key: -2.0},
    )

    adjusted = injector.adjust_with_feedback(rows)

    assert adjusted[0]["data"]["title"] == "Preferred"
    assert adjusted[0]["feedback_adjustment"] > 0
    assert adjusted[1]["feedback_adjustment"] < 0


def test_record_recall_feedback_persists_bounded_rating(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "memory_governance.db"
    db_path.touch()
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", db_path)

    feedback_id = injector.record_recall_feedback("candidate:abc", 5, "very useful")

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT candidate_key, rating, note FROM recall_feedback WHERE id = ?",
            (feedback_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row == ("candidate:abc", 1, "very useful")


def test_memory_observability_report_summarizes_governance_and_recall(tmp_path: Path):
    db_path = tmp_path / "memory_governance.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE governance_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute(
            "CREATE TABLE knowledge_note_index (note_id TEXT PRIMARY KEY, source_path TEXT, title TEXT, summary TEXT, tags TEXT, search_text TEXT, indexed_at REAL, modified_at REAL)"
        )
        conn.execute(
            """
            CREATE TABLE recall_metric_rollups (
                intent TEXT PRIMARY KEY,
                sample_count INTEGER NOT NULL,
                avg_duration_ms REAL,
                p50_duration_ms REAL,
                p95_duration_ms REAL,
                avg_duplicate_suppressed REAL,
                avg_object_conflict_suppressed REAL,
                avg_live_hindsight_used REAL,
                avg_live_hindsight_results REAL,
                avg_cache_hits REAL,
                avg_cache_misses REAL,
                avg_weak_fallback_suppressed REAL,
                avg_knowledge_hit REAL,
                knowledge_top1_rate REAL,
                knowledge_top3_rate REAL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO governance_meta (key, value) VALUES (?, ?)",
            [
                ("knowledge_notes_total", "11"),
                ("hindsight_items_total", "11010"),
                ("last_rebuild_at", "1234567890.0"),
            ],
        )
        conn.execute(
            "INSERT INTO knowledge_note_index VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "note:concepts/agent_memory.md",
                "concepts/agent_memory.md",
                "Agent Memory Architecture",
                "Layered memory note",
                "memory, architecture",
                "Agent Memory Architecture Layered memory note",
                1.0,
                2.0,
            ),
        )
        conn.execute(
            "INSERT INTO recall_metric_rollups VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("system", 3, 12.5, 11.0, 20.0, 0.0, 0.0, 0.0, 0.0, 2.0, 1.0, 0.0, 0.66, 0.33, 0.66, 1234567890.0),
        )
        conn.commit()
    finally:
        conn.close()

    import memory_observability_report as report

    payload = report.build_report_payload(db_path, top_notes=3)
    assert payload["governance"]["knowledge_notes_total"] == 11
    assert payload["governance"]["hindsight_items_total"] == 11010
    assert payload["top_notes"][0]["title"] == "Agent Memory Architecture"
    assert payload["recall_rollups"][0]["intent"] == "system"
    assert payload["recall_rollups"][0]["avg_knowledge_hit"] == 0.66
    assert payload["recall_rollups"][0]["knowledge_top1_rate"] == 0.33
    assert payload["recall_rollups"][0]["knowledge_top3_rate"] == 0.66


def test_memory_observability_report_handles_empty_db(tmp_path: Path):
    db_path = tmp_path / "empty.db"
    db_path.touch()

    import memory_observability_report as report

    payload = report.build_report_payload(db_path, top_notes=3)
    assert payload["governance"]["knowledge_notes_total"] == 0
    assert payload["governance"]["hindsight_items_total"] == 0
    assert payload["top_notes"] == []
    assert payload["recall_rollups"] == []


def test_cli_exposes_gray_env_template():
    cli_path = REPO / "bin" / "hermes-memory"
    content = cli_path.read_text(encoding="utf-8")
    assert "gray-env" in content
    assert "MEMORY_GOVERNANCE_DB_PATH" in content


def test_cli_report_uses_installed_agent_script_path():
    cli_path = REPO / "bin" / "hermes-memory"
    content = cli_path.read_text(encoding="utf-8")
    assert "SCRIPTS_DIR / \"memory_observability_report.py\"" in content
    assert "parent.parent / \"scripts\" / \"memory_observability_report.py\"" not in content


def test_gray_env_mentions_legacy_kmm_layout():
    cli_path = REPO / "bin" / "hermes-memory"
    content = cli_path.read_text(encoding="utf-8")
    assert "knowledge/wiki/wiki" in content


def test_acceptance_check_emits_guardian_capacity_config(monkeypatch, capsys):
    monkeypatch.setenv("AGENT_HOME", str(REPO))
    knowledge_query = recall_samples.DEFAULT_SAMPLE_CASES[0].query
    system_query = next(
        case.query for case in recall_samples.DEFAULT_SAMPLE_CASES if case.expected_intent == "system"
    )
    monkeypatch.setattr(
        acceptance_check.guardian,
        "monitor",
        lambda verbose=False: (
            [],
            {
                "pending_consolidation": 0,
                "failed_consolidation": 0,
                "pending_operations": 0,
                "failed_operations": 0,
                "pending_consolidation_trend": "flat",
                "pending_consolidation_sticky": False,
                "pending_consolidation_nonzero_run": 0,
                "hindsight_sync_lag_seconds": 12,
                "node_limit": 20000,
                "level": "ok",
            },
        ),
    )
    monkeypatch.setattr(
        acceptance_check,
        "run_recall_checks",
        lambda: [
            {
                "query": knowledge_query,
                "intent": "knowledge",
                "l2_count": 1,
                "l3_count": 1,
                "live_hindsight_used": False,
                "live_hindsight_results": 0,
                "knowledge_hit": True,
                "knowledge_top_title": "Agent Memory Architecture",
                "top_titles": ["Agent Memory Architecture"],
                "top_sources": [["knowledge"]],
            },
            {
                "query": system_query,
                "intent": "system",
                "l2_count": 1,
                "l3_count": 1,
                "live_hindsight_used": False,
                "live_hindsight_results": 0,
                "knowledge_hit": False,
                "knowledge_top_title": None,
                "top_titles": ["褰撳墠妯″瀷鐢ㄩ噺"],
                "top_sources": [["object"]],
            },
            {
                "query": "github script deploy",
                "intent": "project",
                "l2_count": 1,
                "l3_count": 2,
                "live_hindsight_used": False,
                "live_hindsight_results": 0,
                "knowledge_hit": False,
                "knowledge_top_title": None,
                "top_titles": ["Deployment Playbook"],
                "top_sources": [["hub"]],
            },
            {
                "query": "recent sessions",
                "intent": "recent",
                "l2_count": 1,
                "l3_count": 1,
                "live_hindsight_used": False,
                "live_hindsight_results": 0,
                    "knowledge_hit": False,
                    "knowledge_top_title": None,
                    "top_titles": ["Recent session summary"],
                    "top_sources": [["governance"]],
                },
                {
                    "query": "朋友关系",
                    "intent": "relationship",
                    "l2_count": 0,
                    "l3_count": 1,
                    "live_hindsight_used": False,
                    "live_hindsight_results": 0,
                    "knowledge_hit": False,
                    "knowledge_top_title": None,
                    "top_titles": ["朋友关系纪要"],
                    "top_sources": [["object"]],
                },
                {
                    "query": "favorite breakfast preferences",
                    "intent": "general",
                    "l2_count": 1,
                    "l3_count": 0,
                    "live_hindsight_used": False,
                    "live_hindsight_results": 0,
                    "knowledge_hit": False,
                    "knowledge_top_title": None,
                    "top_titles": ["Breakfast preferences"],
                    "top_sources": [["hub"]],
                },
            ],
        )

    assert acceptance_check.main() == 0
    payload = capsys.readouterr().out

    assert '"node_limit": 20000' in payload


def test_acceptance_check_rejects_implicit_missing_agent_home(monkeypatch):
    monkeypatch.delenv("AGENT_HOME", raising=False)
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.delenv("MEMORY_STATE_DB_PATH", raising=False)
    monkeypatch.setattr(acceptance_check.injector, "STATE_DB", Path("missing-state-db-for-test"))

    errors = acceptance_check.validate_runtime_config()

    assert errors == [
        "AGENT_HOME, HERMES_HOME, or MEMORY_STATE_DB_PATH must be set for production acceptance checks"
    ]


def test_memory_guardian_uses_multi_agent_friendly_default_node_limit(monkeypatch):
    monkeypatch.setattr(
        guardian,
        "hs",
        lambda method, path, body=None, timeout=10: {
            "/stats": {
                "total_documents": 515,
                "total_nodes": 11084,
                "total_observations": 4368,
                "pending_consolidation": 0,
                "failed_consolidation": 0,
                "pending_operations": 0,
                "failed_operations": 0,
                "last_consolidated_at": "2026-06-19T03:39:57.216430+00:00",
            },
            "/entities": {"items": []},
        }[path],
    )
    monkeypatch.setattr(guardian, "read_governance_meta", lambda: {})
    monkeypatch.setattr(guardian, "summarize_guardian_history", lambda window=12: {})

    _, cap = guardian.monitor(verbose=False)

    assert cap["node_limit"] == 20000
    assert cap["usage_pct"] == 55.4
    assert cap["level"] == "ok"


def test_memory_guardian_clears_sticky_history_when_current_backlog_is_empty(monkeypatch):
    monkeypatch.setattr(
        guardian,
        "hs",
        lambda method, path, body=None, timeout=10: {
            "/stats": {
                "total_documents": 515,
                "total_nodes": 11084,
                "total_observations": 4368,
                "pending_consolidation": 0,
                "failed_consolidation": 0,
                "pending_operations": 0,
                "failed_operations": 0,
                "last_consolidated_at": "2026-06-19T03:39:57.216430+00:00",
            },
            "/entities": {"items": []},
        }[path],
    )
    monkeypatch.setattr(guardian, "read_governance_meta", lambda: {})
    monkeypatch.setattr(
        guardian,
        "summarize_guardian_history",
        lambda window=12: {
            "pending_consolidation_sticky": True,
            "pending_consolidation_nonzero_run": 10,
            "pending_consolidation_trend": "flat",
            "pending_consolidation_recent_max": 41,
            "pending_consolidation_recent_min": 13,
        },
    )

    _, cap = guardian.monitor(verbose=False)

    assert cap["pending_consolidation_sticky"] is False
    assert cap["pending_consolidation_nonzero_run"] == 0
    assert cap["pending_consolidation_trend"] == "clear"


def test_memory_guardian_node_limit_can_be_overridden_by_env(monkeypatch):
    monkeypatch.setenv("MEMORY_GUARDIAN_NODE_LIMIT", "10000")
    importlib.reload(guardian)
    monkeypatch.setattr(
        guardian,
        "hs",
        lambda method, path, body=None, timeout=10: {
            "/stats": {
                "total_documents": 10,
                "total_nodes": 10050,
                "total_observations": 20,
                "pending_consolidation": 0,
                "failed_consolidation": 0,
                "pending_operations": 0,
                "failed_operations": 0,
                "last_consolidated_at": "2026-06-19T03:39:57.216430+00:00",
            },
            "/entities": {"items": []},
        }[path],
    )
    monkeypatch.setattr(guardian, "read_governance_meta", lambda: {})
    monkeypatch.setattr(guardian, "summarize_guardian_history", lambda window=12: {})

    try:
        _, cap = guardian.monitor(verbose=False)
        assert cap["node_limit"] == 10000
        assert cap["level"] == "critical"
    finally:
        monkeypatch.delenv("MEMORY_GUARDIAN_NODE_LIMIT", raising=False)
        importlib.reload(guardian)
