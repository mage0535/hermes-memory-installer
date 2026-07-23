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
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

import memory_family_registry as family_registry
import memory_guardian as guardian
import recall_samples
import query_expansion
import sidecar_acceptance_check as acceptance_check
import tiered_context_injector as injector
import alert_queue
import alert_webhook_receiver
import cron_freshness
import metrics_dashboard
import metrics_dashboard_server
import memory_storage_cross_check
import openmetrics_exporter
import slo_rollup
import gbrain_stale_maintenance
import profile_isolation_soak
import synthetic_recall_benchmark
import system_metrics_collector
import hermes_load_shedder
import live_hindsight_refresh_worker
import telegram_language_sync
import prometheus_alert_bridge
import sync_embeddings
import snapshot_compress
import snapshot_restore


def load_script_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def load_source_file_module(name: str, relative_path: str):
    loader = importlib.machinery.SourceFileLoader(name, str(REPO / relative_path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def test_hindsight_service_can_follow_hermes_active_model_config(tmp_path: Path, monkeypatch):
    (tmp_path / "config.yaml").write_text(
        """
model:
  provider: custom-openai
  model: generic-model
custom_providers:
  - name: custom-openai
    base_url: https://llm.example.test/v1
    api_key_env: HERMES_TEST_API_KEY
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_TEST_API_KEY", "test-secret")
    service = load_script_module("hindsight_service_test", "scripts/hindsight-service.py")

    active = service.hermes_active_model(tmp_path)

    assert active == {
        "api_key": "test-secret",
        "base_url": "https://llm.example.test/v1",
        "model": "generic-model",
        "provider": "custom-openai",
    }


def test_hindsight_service_import_is_side_effect_free():
    service = load_script_module("hindsight_service_import_test", "scripts/hindsight-service.py")

    assert hasattr(service, "main")
    assert hasattr(service, "HindsightServer") is False


def test_runtime_drift_repo_dirty_is_info_when_deploy_content_matches():
    cli = load_source_file_module("hermes_memory_cli_test", "bin/hermes-memory")

    reason = cli.repo_dirty_reason(
        {"dirty": True, "lines": [" M DEVELOPMENT_CONTINUATION.md"]},
        {"missing_scripts": [], "mismatched_scripts": []},
    )

    assert reason["code"] == "repo_dirty"
    assert reason["severity"] == "info"


def test_cron_freshness_gbrain_stale_threshold_matches_six_hour_schedule():
    check = next(row for row in cron_freshness.CHECKS if row["name"] == "gbrain_stale_refresh")

    assert check["max_age_s"] >= 8 * 3600


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


def test_chinese_broad_queries_expand_to_operational_terms():
    terms = query_expansion.expanded_query_terms("最近服务器告警")

    assert "最近" in terms
    assert "alert" in terms
    assert "recent" in terms


def test_relationship_and_preference_queries_share_profile_family():
    assert injector.classify_query_intent("朋友关系") == "relationship"
    assert injector.classify_query_intent("我的偏好是什么") == "relationship"
    assert "preference" in injector.build_query_terms("我的偏好是什么")


def test_chinese_alert_queries_are_system_intent():
    assert injector.classify_query_intent("最近服务器告警") == "system"


def test_weak_recall_enqueues_async_hindsight_refresh(monkeypatch, tmp_path: Path):
    gov_db = tmp_path / "memory_governance.db"
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(injector, "ASYNC_LIVE_HINDSIGHT_REFRESH_ENABLED", True, raising=False)
    monkeypatch.setattr(injector, "LIVE_HINDSIGHT_ENABLED", False, raising=False)
    monkeypatch.setattr(injector, "STATE_DB", tmp_path / "missing-state.db")
    monkeypatch.setattr(injector, "cached_governance_query", lambda *args, **kwargs: [])
    monkeypatch.setattr(injector, "should_use_expensive_fallbacks", lambda query, candidates, top: False)

    rows, live_used, live_count = injector.get_l3("朋友关系", top=5)

    assert rows == []
    assert live_used is False
    assert live_count == 0
    conn = sqlite3.connect(str(gov_db))
    try:
        queued = conn.execute("SELECT query, reason FROM recall_refresh_queue").fetchone()
    finally:
        conn.close()
    assert queued == ("朋友关系", "foreground_live_disabled")


def test_sufficient_cached_relationship_recall_does_not_enqueue_refresh(monkeypatch, tmp_path: Path):
    gov_db = tmp_path / "memory_governance.db"
    sqlite3.connect(str(gov_db)).close()
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(injector, "ASYNC_LIVE_HINDSIGHT_REFRESH_ENABLED", True, raising=False)
    monkeypatch.setattr(injector, "LIVE_HINDSIGHT_ENABLED", False, raising=False)
    monkeypatch.setattr(injector, "STATE_DB", tmp_path / "missing-state.db")

    def fake_cached(layer, query, top, fetcher):
        if layer != "hindsight_cache":
            return []
        return [
                {
                    "session_id": f"h{idx}",
                    "title": f"朋友关系偏好 {idx}",
                    "snippet": f"朋友关系偏好需要温和安慰 {idx}",
                    "source": "hindsight_cache",
                "layer": "hindsight_cache",
                "score": 0.9 - idx * 0.01,
            }
            for idx in range(3)
        ]

    monkeypatch.setattr(injector, "cached_governance_query", fake_cached)
    monkeypatch.setattr(injector, "should_use_expensive_fallbacks", lambda query, candidates, top: False)

    rows, live_used, live_count = injector.get_l3("朋友关系", top=5)

    assert len(rows) >= 1
    assert live_used is False
    assert live_count == 0
    conn = sqlite3.connect(str(gov_db))
    try:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'recall_refresh_queue'"
        ).fetchone()
    finally:
        conn.close()
    assert exists is None


def test_provider_config_objects_are_demoted_for_memory_recall_queries():
    fused = injector.rrf_fuse(
        [
            [
                {
                    "session_id": "provider-state",
                    "slug": "provider-state",
                    "title": "Provider Model State",
                    "snippet": "provider model config endpoint",
                    "layer": "object",
                    "score": 0.99,
                },
                {
                    "session_id": "memory-recall",
                    "slug": "memory-recall",
                    "title": "Hindsight recall defect analysis",
                    "snippet": "memory recall L3 hindsight gbrain sidecar issue",
                    "layer": "hindsight_cache",
                    "score": 0.72,
                },
            ]
        ],
        query="外挂记忆体召回缺陷",
    )

    assert fused[0]["data"]["slug"] == "memory-recall"


def test_live_hindsight_refresh_worker_caches_results(monkeypatch, tmp_path: Path):
    gov_db = tmp_path / "memory_governance.db"
    monkeypatch.setattr(live_hindsight_refresh_worker.governance_rebuild, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", gov_db)
    assert injector.enqueue_live_hindsight_refresh("朋友关系", "test", 0) is True
    monkeypatch.setattr(
        live_hindsight_refresh_worker,
        "fetch_live_hindsight",
        lambda query, timeout_s: [
            {
                "id": "m1",
                "type": "observation",
                "text": "朋友关系偏好需要温和安慰",
                "entities": ["朋友"],
                "tags": ["relationship"],
            }
        ],
    )

    payload = live_hindsight_refresh_worker.run_once(limit=1, timeout_s=0.5)

    conn = sqlite3.connect(str(gov_db))
    try:
        cached = conn.execute("SELECT text FROM hindsight_index WHERE memory_id = 'm1'").fetchone()
        queued = conn.execute("SELECT status, candidate_count FROM recall_refresh_queue").fetchone()
    finally:
        conn.close()
    assert {key: payload[key] for key in ("ok", "status", "processed", "cached", "failed")} == {
        "ok": True,
        "status": "healthy",
        "processed": 1,
        "cached": 1,
        "failed": 0,
    }
    assert cached == ("朋友关系偏好需要温和安慰",)
    assert queued == ("done", 1)


def test_live_hindsight_refresh_worker_skips_cleanly_when_governance_db_is_locked(monkeypatch, tmp_path: Path):
    gov_db = tmp_path / "memory_governance.db"
    sqlite3.connect(str(gov_db)).close()
    monkeypatch.setattr(live_hindsight_refresh_worker.governance_rebuild, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(live_hindsight_refresh_worker, "ensure_schema_when_unlocked", lambda conn: False)

    payload = live_hindsight_refresh_worker.run_once(limit=1, timeout_s=0.1)

    assert {key: payload[key] for key in ("ok", "status", "processed", "cached", "failed", "skipped")} == {
        "ok": True,
        "status": "healthy",
        "processed": 0,
        "cached": 0,
        "failed": 0,
        "skipped": "database_locked",
    }


def test_live_hindsight_refresh_worker_expires_exhausted_failures(monkeypatch, tmp_path: Path):
    gov_db = tmp_path / "memory_governance.db"
    monkeypatch.setattr(live_hindsight_refresh_worker.governance_rebuild, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", gov_db)
    assert injector.enqueue_live_hindsight_refresh("stale weak query", "test", 0) is True
    conn = sqlite3.connect(str(gov_db))
    try:
        conn.execute("UPDATE recall_refresh_queue SET status = 'failed', attempts = 3, last_error = 'timed out'")
        conn.commit()
    finally:
        conn.close()

    payload = live_hindsight_refresh_worker.run_once(limit=5, timeout_s=0.1, max_attempts=3)

    conn = sqlite3.connect(str(gov_db))
    try:
        row = conn.execute("SELECT status, attempts, last_error FROM recall_refresh_queue").fetchone()
    finally:
        conn.close()
    assert payload["ok"] is True
    assert payload["status"] == "healthy"
    assert payload["processed"] == 0
    assert payload["expired"] == 1
    assert row == ("expired", 3, "max_attempts_exhausted")


def test_live_hindsight_refresh_worker_classifies_timeout_failures(monkeypatch, tmp_path: Path):
    gov_db = tmp_path / "memory_governance.db"
    monkeypatch.setattr(live_hindsight_refresh_worker.governance_rebuild, "GOVERNANCE_DB", gov_db)
    monkeypatch.setattr(injector.governance_rebuild, "GOVERNANCE_DB", gov_db)
    assert injector.enqueue_live_hindsight_refresh("slow weak query", "test", 0) is True

    def raise_timeout(query, timeout_s):
        raise TimeoutError("timed out")

    monkeypatch.setattr(live_hindsight_refresh_worker, "fetch_live_hindsight", raise_timeout)

    payload = live_hindsight_refresh_worker.run_once(limit=1, timeout_s=0.1, max_attempts=3)

    assert payload["ok"] is False
    assert payload["status"] == "degraded"
    assert payload["failure_buckets"] == {"timeout": 1}
    assert payload["queue"]["retryable_failed"] == 1


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


def test_acceptance_check_treats_authoritative_architecture_object_as_knowledge_hit():
    sample_by_intent = {
        case.expected_intent: case.query
        for case in recall_samples.DEFAULT_SAMPLE_CASES
        if case.required_for_acceptance
    }
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
                "knowledge_hit": True,
                "knowledge_top_title": "Hermes Agent memory architecture",
                "top_titles": [
                    "Hermes Agent's persistent memory system is a four-layer memory architecture"
                ],
                "top_sources": [["object"]],
            },
            {
                "query": sample_by_intent["system"],
                "intent": "system",
                "l2_count": 1,
                "l3_count": 1,
                "top_titles": ["Provider Config"],
                "top_sources": [["object"]],
            },
            {
                "query": sample_by_intent["project"],
                "intent": "project",
                "l2_count": 1,
                "l3_count": 1,
                "top_titles": ["Deployment Playbook"],
                "top_sources": [["hub"]],
            },
            {
                "query": sample_by_intent["recent"],
                "intent": "recent",
                "l2_count": 1,
                "l3_count": 1,
                "top_titles": ["Recent session summary"],
                "top_sources": [["governance"]],
            },
            {
                "query": sample_by_intent["general"],
                "intent": "general",
                "l2_count": 1,
                "l3_count": 0,
                "top_titles": ["Breakfast preferences"],
                "top_sources": [["hub"]],
            },
        ],
    }

    ok, errors = acceptance_check.evaluate_payload(payload)

    assert ok is True
    assert errors == []


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


def test_alert_queue_does_not_escalate_recent_window_when_latest_acceptance_is_ok(tmp_path: Path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "runtime-drift-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
    (metrics / "langsmith-trend-latest.json").write_text(
        json.dumps(
            {
                "monitor": {
                    "latest_acceptance_ok": True,
                    "acceptance_ok_rate": 0.6,
                    "recent_acceptance_ok_rate": 0.6,
                    "failure_reasons": {"acceptance_not_ok": 2},
                    "recent_failures": [{"reasons": ["acceptance_not_ok"]}],
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
    assert [row["code"] for row in alerts] == ["historical_acceptance_failures"]


def test_alert_queue_repairs_gbrain_stale_before_alerting(monkeypatch, tmp_path: Path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "runtime-drift-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
    (metrics / "langsmith-trend-latest.json").write_text(
        json.dumps({"monitor": {"latest_acceptance_ok": True, "acceptance_ok_rate": 1.0, "lag": {"status": "healthy"}}}),
        encoding="utf-8",
    )
    (metrics / "gbrain-stale-latest.json").write_text(
        json.dumps({"status": "action-needed", "auto_fix_attempted": True, "auto_fix_succeeded": False}),
        encoding="utf-8",
    )
    (metrics / "hindsight-security-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
    calls = []

    def fake_repair(metrics_dir: Path, stale_payload: dict) -> dict:
        calls.append((metrics_dir, stale_payload["status"]))
        return {"status": "healthy", "auto_fix_attempted": True, "auto_fix_succeeded": True}

    monkeypatch.setattr(alert_queue, "repair_gbrain_stale_if_needed", fake_repair)

    status, alerts = alert_queue.build_alerts(metrics)

    assert calls == [(metrics, "action-needed")]
    assert status == "healthy"
    assert alerts == []


def test_alert_queue_reports_cron_freshness_action_needed(tmp_path: Path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "runtime-drift-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
    (metrics / "langsmith-trend-latest.json").write_text(
        json.dumps({"monitor": {"latest_acceptance_ok": True, "acceptance_ok_rate": 1.0, "lag": {"status": "healthy"}}}),
        encoding="utf-8",
    )
    (metrics / "gbrain-stale-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
    (metrics / "hindsight-security-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
    (metrics / "cron-freshness-latest.json").write_text(
        json.dumps(
            {
                "status": "action-needed",
                "jobs": [
                    {"name": "cron_freshness", "status": "action-needed", "age_s": 99999},
                    {"name": "slo_rollup", "status": "healthy", "age_s": 10},
                ],
            }
        ),
        encoding="utf-8",
    )

    status, alerts = alert_queue.build_alerts(metrics)

    assert status == "action-needed"
    assert [(row["source"], row["code"], row["severity"]) for row in alerts] == [
        ("cron-freshness", "cron_jobs_stale", "action-needed")
    ]
    assert alerts[0]["detail"]["jobs"] == [{"name": "cron_freshness", "status": "action-needed", "age_s": 99999}]


def test_alert_queue_reports_live_hindsight_refresh_degraded(tmp_path: Path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "runtime-drift-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
    (metrics / "langsmith-trend-latest.json").write_text(
        json.dumps({"monitor": {"latest_acceptance_ok": True, "acceptance_ok_rate": 1.0, "lag": {"status": "healthy"}}}),
        encoding="utf-8",
    )
    (metrics / "gbrain-stale-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
    (metrics / "hindsight-security-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
    (metrics / "live-hindsight-refresh-latest.json").write_text(
        json.dumps(
            {
                "status": "degraded",
                "failed": 2,
                "failure_buckets": {"timeout": 2},
                "queue": {"pending": 0, "retryable_failed": 2, "expired": 1},
            }
        ),
        encoding="utf-8",
    )

    status, alerts = alert_queue.build_alerts(metrics)

    assert status == "degraded"
    assert [(row["source"], row["code"], row["severity"]) for row in alerts] == [
        ("live-hindsight-refresh", "live_hindsight_refresh_degraded", "degraded")
    ]
    assert alerts[0]["detail"]["failure_buckets"] == {"timeout": 2}


def test_alert_queue_resolves_language_from_locale(monkeypatch):
    monkeypatch.setenv("LANG", "en_US.UTF-8")

    assert alert_queue.resolve_lang() == "en"

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
    assert "Hermes 记忆系统告警" in body["text"]

def test_alert_webhook_receiver_payload_language_overrides_locale(monkeypatch):
    monkeypatch.setenv("MEMORY_ALERT_TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")

    body = alert_webhook_receiver.build_forward_body(
        "telegram",
        {
            "lang": "en",
            "status": "action-needed",
            "alert_count": 1,
            "alerts": [{"severity": "action-needed", "source": "runtime", "code": "x"}],
        },
    )

    assert "Hermes Memory alert" in body["text"]


def test_alert_webhook_receiver_prefers_cached_telegram_chat_language(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MEMORY_ALERT_TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    lang_map = tmp_path / "telegram-chat-languages.json"
    lang_map.write_text(json.dumps({"12345": {"lang": "zh"}}), encoding="utf-8")
    monkeypatch.setattr(alert_webhook_receiver, "DEFAULT_TELEGRAM_LANG_MAP", lang_map)

    body = alert_webhook_receiver.build_forward_body(
        "telegram",
        {"status": "action-needed", "alert_count": 1, "alerts": [{"severity": "action-needed", "source": "runtime", "code": "x"}]},
    )

    assert "Hermes 记忆系统告警" in body["text"]


def test_alert_webhook_receiver_supports_recipient_preferences(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("MEMORY_ALERT_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    recipients = tmp_path / "alert-recipients.json"
    recipients.write_text(
        json.dumps(
            {
                "telegram": [
                    {"chat_id": "1001", "lang": "zh", "min_severity": "warning"},
                    {"chat_id": "1002", "lang": "en", "min_severity": "action-needed"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(alert_webhook_receiver, "DEFAULT_RECIPIENTS", recipients)

    targets = alert_webhook_receiver.forward_targets(
        "telegram",
        {
            "status": "action-needed",
            "alerts": [{"severity": "action-needed", "source": "runtime", "code": "x"}],
        },
    )

    assert [target["chat_id"] for target in targets] == ["1001", "1002"]
    assert "Hermes 记忆系统告警" in targets[0]["body"]["text"]
    assert "Hermes Memory alert" in targets[1]["body"]["text"]

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
    (metrics / "slo-rollup-latest.json").write_text(
        json.dumps({"status": "healthy", "acceptance_ok_rate": 1.0, "alert_queue_growth": 0, "recall_latency": {"p95_s": 0.42}}),
        encoding="utf-8",
    )
    (metrics / "prometheus-alert-bridge-latest.json").write_text(
        json.dumps({"status": "healthy", "alert_count": 0}),
        encoding="utf-8",
    )
    (metrics / "cron-freshness-latest.json").write_text(
        json.dumps({"status": "healthy", "jobs": []}),
        encoding="utf-8",
    )
    (metrics / "live-hindsight-refresh-latest.json").write_text(
        json.dumps({"status": "healthy", "queue": {"pending": 0, "retryable_failed": 0, "expired": 0}}),
        encoding="utf-8",
    )
    (metrics / "system-metrics-latest.json").write_text(
        json.dumps({"memory": {"available_mb": 2048, "swap_pct": 10.0}, "disk": {"pct": 50.0}, "state_db_size_mb": 100.0}),
        encoding="utf-8",
    )

    html = metrics_dashboard.render_dashboard(metrics, lang="zh", query_params={"view": "alerts"})
    html_en = metrics_dashboard.render_dashboard(metrics, lang="en", query_params={"view": "components"})

    assert 'lang="zh-CN"' in html
    assert "#section-alerts" in html
    assert "#section-components" in html
    assert "historical_acceptance_failures" in html
    assert "47" in html
    assert "HTTP 200" in html
    assert "Hermes 记忆体监控中心" in html
    assert "Prometheus / Grafana" in html
    assert "view=alerts" in html
    assert "Hermes Memory Control Center" in html_en
    assert "Runtime Drift" in html_en
    assert "Language" in html_en
    assert "Success, HTTP 200, 1 attempt(s)" in html_en
    assert "view=components" in html_en
    payload = metrics_dashboard.build_dashboard_payload(metrics)
    assert payload["artifacts"][0]["name"] == "Runtime Drift"
    assert any(item["name"] == "Live Hindsight Refresh" for item in payload["artifacts"])
    assert payload["overall_status"] == "healthy"
    assert payload["status_counts"]["healthy"] >= 1


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
            assert "Hermes Memory Control Center" in body
            assert "Language" in body
            assert "Prometheus / Grafana" in body
        with urllib.request.urlopen(f"{base}/api/status?token=secret", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
            assert "artifacts" in payload
            assert "summary_text" not in payload
            assert payload["overall_status"] in {"healthy", "degraded", "action-needed"}
        with urllib.request.urlopen(f"{base}/api/status?token=secret&lang=en", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
            assert payload["summary_text"].startswith("Overall status:")
        with urllib.request.urlopen(f"{base}/api/status?token=secret&lang=zh", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
            assert payload["summary_text"].startswith("整体状态：")
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


def test_slo_rollup_summarizes_acceptance_queue_replay_and_recall(tmp_path: Path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "langsmith-trend-latest.json").write_text(
        json.dumps(
            {
                "monitor": {"recent_acceptance_ok_rate": 0.8},
                "performance": {"recall_latency": {"p50_s": 0.12, "p95_s": 0.45, "max_s": 0.9}},
            }
        ),
        encoding="utf-8",
    )
    (metrics / "dead-letter-replay-latest.json").write_text(
        json.dumps({"replayed": 5, "failed": 1}),
        encoding="utf-8",
    )
    (metrics / "inbound-alert-webhook.jsonl").write_text("{}\n{}\n{}\n", encoding="utf-8")
    history = metrics / "slo-rollup-history.jsonl"
    history.write_text(json.dumps({"alert_queue_lines": 1}) + "\n", encoding="utf-8")

    payload = slo_rollup.build_slo_rollup(metrics)

    assert payload["status"] == "degraded"
    assert payload["acceptance_ok_rate"] == 0.8
    assert payload["alert_queue_lines"] == 3
    assert payload["alert_queue_growth"] == 2
    assert payload["dead_letter_replay_success_rate"] == 0.8
    assert payload["recall_latency"]["p95_s"] == 0.45


def test_slo_rollup_treats_empty_dead_letter_replay_as_success(tmp_path: Path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "dead-letter-replay-latest.json").write_text(
        json.dumps({"ok": True, "total": 0, "replayed": 0, "failed": 0, "remaining": 0}),
        encoding="utf-8",
    )

    payload = slo_rollup.build_slo_rollup(metrics)

    assert payload["dead_letter_replay_success_rate"] == 1.0
    assert payload["status"] == "healthy"


def test_slo_rollup_prefers_current_acceptance_window(tmp_path: Path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "langsmith-trend-latest.json").write_text(
        json.dumps(
            {
                "monitor": {
                    "acceptance_ok_rate": 0.55,
                    "recent_acceptance_ok_rate": 0.8,
                    "current_acceptance_ok_rate": 1.0,
                    "current_window": 4,
                }
            }
        ),
        encoding="utf-8",
    )

    payload = slo_rollup.build_slo_rollup(metrics)

    assert payload["status"] == "healthy"
    assert payload["acceptance_ok_rate"] == 1.0
    assert payload["acceptance_window"] == "current"


def test_openmetrics_exporter_includes_slo_rollup(tmp_path: Path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "slo-rollup-latest.json").write_text(
        json.dumps(
            {
                "status": "healthy",
                "acceptance_ok_rate": 0.95,
                "alert_queue_growth": 2,
                "dead_letter_replay_success_rate": 1.0,
                "recall_latency": {"p50_s": 0.1, "p95_s": 0.3},
            }
        ),
        encoding="utf-8",
    )

    text = openmetrics_exporter.render_openmetrics(metrics)

    assert "hermes_memory_slo_acceptance_ok_rate 0.95" in text
    assert "hermes_memory_slo_alert_queue_growth 2" in text
    assert "hermes_memory_slo_dead_letter_replay_success_rate 1.0" in text
    assert 'hermes_memory_slo_recall_latency_seconds{quantile="0.95"} 0.3' in text


def test_openmetrics_exporter_includes_live_hindsight_refresh_queue(tmp_path: Path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "live-hindsight-refresh-latest.json").write_text(
        json.dumps({"status": "degraded", "queue": {"pending": 2, "retryable_failed": 1, "expired": 3}}),
        encoding="utf-8",
    )

    text = openmetrics_exporter.render_openmetrics(metrics)

    assert 'hermes_memory_component_status{component="live_hindsight_refresh"} 1' in text
    assert 'hermes_memory_live_hindsight_refresh_queue{state="pending"} 2' in text
    assert 'hermes_memory_live_hindsight_refresh_queue{state="retryable_failed"} 1' in text
    assert 'hermes_memory_live_hindsight_refresh_queue{state="expired"} 3' in text


def test_openmetrics_exporter_includes_cron_and_system_metrics(tmp_path: Path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "cron-freshness-latest.json").write_text(
        json.dumps(
            {
                "status": "degraded",
                "jobs": [
                    {"name": "cron_a", "status": "healthy", "age_s": 30.0, "max_age_s": 600},
                    {"name": "cron_b", "status": "degraded", "age_s": 900.0, "max_age_s": 600},
                ],
            }
        ),
        encoding="utf-8",
    )
    (metrics / "system-metrics-latest.json").write_text(
        json.dumps(
            {
                "memory": {"available_mb": 2048, "swap_pct": 61.5},
                "disk": {"pct": 77.2},
                "state_db_size_mb": 3979.1,
            }
        ),
        encoding="utf-8",
    )

    text = openmetrics_exporter.render_openmetrics(metrics)

    assert 'hermes_memory_cron_job_status{job="cron_b"} 1' in text
    assert 'hermes_memory_cron_job_age_seconds{job="cron_a"} 30.0' in text
    assert "hermes_memory_system_swap_used_pct 61.5" in text
    assert "hermes_memory_system_disk_used_pct 77.2" in text


def test_grafana_dashboard_template_consumes_openmetrics():
    dashboard = json.loads((REPO / "docs" / "grafana" / "hermes-memory-openmetrics-dashboard.json").read_text(encoding="utf-8"))
    serialized = json.dumps(dashboard)
    panel_titles = {panel["title"] for panel in dashboard["panels"]}

    assert dashboard["title"] == "Hermes Memory OpenMetrics / Hermes 记忆体指标看板"
    assert "hermes_memory_component_status" in serialized
    assert "hermes_memory_slo_acceptance_ok_rate" in serialized
    assert "hermes_memory_slo_recall_latency_seconds" in serialized
    assert "hermes_memory_cron_job_age_seconds" in serialized
    assert "hermes_memory_system_swap_used_pct" in serialized
    assert "Overall Component Status / 整体组件状态" in panel_titles


def test_grafana_home_dashboard_exists():
    dashboard = json.loads((REPO / "docs" / "grafana" / "hermes-memory-home.json").read_text(encoding="utf-8"))
    serialized = json.dumps(dashboard)

    assert dashboard["uid"] == "hermes-memory-home"
    assert "Hermes Memory Home" in dashboard["title"]
    assert "hermes-memory-openmetrics" in serialized
    assert "Operator Notes" in serialized


def test_prometheus_and_grafana_provisioning_templates_exist():
    prometheus = (REPO / "deploy" / "observability" / "prometheus.yml").read_text(encoding="utf-8")
    rules = (REPO / "deploy" / "observability" / "prometheus-rules.yml").read_text(encoding="utf-8")
    compose = (REPO / "deploy" / "observability" / "docker-compose.yml").read_text(encoding="utf-8")
    provision = (REPO / "deploy" / "observability" / "provision_dashboards.py").read_text(encoding="utf-8")
    datasource = (REPO / "deploy" / "observability" / "grafana" / "provisioning" / "datasources" / "prometheus.yml").read_text(encoding="utf-8")
    dashboards = (REPO / "deploy" / "observability" / "grafana" / "provisioning" / "dashboards" / "dashboards.yml").read_text(encoding="utf-8")

    assert "127.0.0.1:9500/metrics" in prometheus
    assert "prometheus-rules.yml" in prometheus
    assert "HermesMemoryAcceptanceRateLow" in rules
    assert "HermesMemoryRecallLatencyHigh" in rules
    assert "grafana/grafana" in compose
    assert "prom/prometheus" in compose
    assert "GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH" in compose
    assert "prometheus-rules.yml" in compose
    assert "/api/dashboards/db" in provision
    assert "homeDashboardUID" in provision
    assert "type: prometheus" in datasource
    assert "hermes-memory-openmetrics-dashboard.json" in dashboards


def test_telegram_language_sync_updates_chat_language(monkeypatch, tmp_path: Path):
    map_path = tmp_path / "telegram-chat-languages.json"
    offset_path = tmp_path / "telegram-updates-offset"
    monkeypatch.setattr(
        telegram_language_sync,
        "telegram_api",
        lambda method, params, token: {
            "ok": True,
            "result": [
                {
                    "update_id": 10,
                    "message": {
                        "chat": {"id": 12345},
                        "from": {"id": 99, "username": "tester", "language_code": "zh-hans"},
                    },
                }
            ],
        },
    )

    payload = telegram_language_sync.sync_telegram_languages(map_path, offset_path, "token", limit=10)
    stored = json.loads(map_path.read_text(encoding="utf-8"))

    assert payload["ok"] is True
    assert payload["updated"] == 1
    assert stored["12345"]["lang"] == "zh"
    assert offset_path.read_text(encoding="utf-8") == "11"


def test_prometheus_alert_bridge_builds_local_webhook_payload():
    payload = prometheus_alert_bridge.build_bridge_payload(
        [
            {
                "labels": {"alertname": "HermesMemoryRecallLatencyHigh", "severity": "warning", "service": "hermes-memory"},
                "annotations": {"summary": "Recall latency high", "description": "P95 above threshold"},
                "state": "firing",
                "activeAt": "2026-06-28T00:00:00Z",
                "value": "21.4",
            }
        ],
        lang="zh",
    )

    assert payload["status"] == "action-needed"
    assert payload["lang"] == "zh"
    assert payload["alert_count"] == 1
    assert payload["alerts"][0]["code"] == "HermesMemoryRecallLatencyHigh"
    assert payload["alerts"][0]["detail"]["summary"] == "Recall latency high"


def test_prometheus_alert_bridge_filters_non_memory_alerts_by_default():
    payload = prometheus_alert_bridge.build_bridge_payload(
        [
            {
                "labels": {
                    "alertname": "HermesContentDeliveryFailures",
                    "severity": "warning",
                    "service": "hermes-content-platform",
                },
                "annotations": {"summary": "Content delivery failures remain"},
                "state": "firing",
                "activeAt": "2026-07-15T01:40:00Z",
                "value": "2",
            },
            {
                "labels": {"alertname": "HermesMemoryRecallLatencyHigh", "severity": "warning", "service": "hermes-memory"},
                "annotations": {"summary": "Recall latency high"},
                "state": "firing",
                "activeAt": "2026-07-15T01:41:00Z",
                "value": "21.4",
            },
        ],
        lang="zh",
    )

    assert payload["status"] == "action-needed"
    assert payload["alert_count"] == 1
    assert payload["filtered_count"] == 1
    assert payload["alerts"][0]["code"] == "HermesMemoryRecallLatencyHigh"


def test_prometheus_alert_bridge_can_include_all_alerts_for_debugging():
    payload = prometheus_alert_bridge.build_bridge_payload(
        [
            {
                "labels": {
                    "alertname": "HermesContentDeliveryFailures",
                    "severity": "warning",
                    "service": "hermes-content-platform",
                },
                "annotations": {"summary": "Content delivery failures remain"},
                "state": "firing",
                "activeAt": "2026-07-15T01:40:00Z",
                "value": "2",
            }
        ],
        lang="zh",
        include_all=True,
    )

    assert payload["alert_count"] == 1
    assert payload["filtered_count"] == 0
    assert payload["alerts"][0]["code"] == "HermesContentDeliveryFailures"


def test_load_shedder_targets_only_stale_temp_browser_trees():
    processes = {
        100: (1, 1200, "/usr/bin/node /tmp/patchright/driver/package/cli.js run-driver"),
        101: (100, 1190, "/browser/chrome --user-data-dir=/tmp/playwright_profile"),
        200: (1, 1200, "/usr/bin/node /usr/local/lib/playwright/driver/package/cli.js run-driver"),
        201: (200, 1190, "/browser/chrome --user-data-dir=/root/social-auto-upload/cookies/profile/persistent_profile"),
        300: (1, 60, "/usr/bin/node /tmp/playwright/driver/package/cli.js run-driver"),
    }
    children = {1: [100, 200, 300], 100: [101], 200: [201]}

    killed = hermes_load_shedder.terminate_stale_temp_trees(processes, children, min_age_s=900, dry_run=True)
    reniced = hermes_load_shedder.renice_persistent(processes, dry_run=True)

    assert killed == [100, 101]
    assert reniced == [201]


def test_load_shedder_terminates_stale_persistent_browsers_only_under_critical_pressure():
    processes = {
        100: (1, 1200, "/usr/bin/node /tmp/playwright/driver/package/cli.js run-driver"),
        101: (100, 1190, "/browser/chrome --user-data-dir=/root/social-auto-upload/cookies/profile/persistent_profile"),
        200: (1, 1200, "/root/.hermes/hermes-agent/.venv/bin/python -m hermes_cli.main gateway run"),
        300: (1, 1200, "/root/.hermes/hermes-agent/.venv/bin/python3 /root/.hermes/scripts/hindsight-service.py"),
        400: (1, 60, "/usr/bin/node /tmp/playwright/driver/package/cli.js run-driver"),
        401: (400, 55, "/browser/chrome --user-data-dir=/root/social-auto-upload/cookies/profile/persistent_profile"),
    }
    children = {1: [100, 200, 300, 400], 100: [101], 400: [401]}

    normal = hermes_load_shedder.terminate_stale_persistent_trees(
        processes,
        children,
        min_age_s=900,
        critical=False,
        dry_run=True,
    )
    critical = hermes_load_shedder.terminate_stale_persistent_trees(
        processes,
        children,
        min_age_s=900,
        critical=True,
        dry_run=True,
    )

    assert normal == []
    assert critical == [100, 101]


def test_load_shedder_terminates_publish_runners_under_critical_pressure():
    processes = {
        100: (
            1,
            5,
            "python3 /agent/scripts/baijiahao_article_scheduled_runner.py /tmp/manifest.json /tmp/evidence",
        ),
        200: (1, 5, "/root/.hermes/hermes-agent/.venv/bin/python -m hermes_cli.main gateway run"),
        300: (1, 5, "/root/.hermes/hermes-agent/.venv/bin/python3 /root/.hermes/scripts/hindsight-service.py"),
    }

    normal = hermes_load_shedder.terminate_publish_runners(processes, min_age_s=0, critical=False, dry_run=True)
    critical = hermes_load_shedder.terminate_publish_runners(processes, min_age_s=0, critical=True, dry_run=True)

    assert normal == []
    assert critical == [100]


def test_load_shedder_does_not_restart_core_services():
    source = (REPO / "scripts" / "hermes_load_shedder.py").read_text(encoding="utf-8")

    assert "systemctl restart" not in source
    assert "hindsight.service" not in source
    assert "hermes-gateway.service" not in source


def test_metrics_dashboard_includes_explanations_and_actions(tmp_path: Path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "runtime-drift-latest.json").write_text(
        json.dumps({"status": "action-needed", "reasons": [{"code": "mismatched_scripts", "severity": "action-needed"}]}),
        encoding="utf-8",
    )
    (metrics / "health-summary-latest.json").write_text(
        json.dumps({"status": "action-needed", "alert_count": 1, "alerts": [{"code": "x", "severity": "action-needed"}]}),
        encoding="utf-8",
    )
    (metrics / "langsmith-trend-latest.json").write_text(
        json.dumps({"monitor": {"lag": {"status": "action-needed"}, "recent_acceptance_ok_rate": 0.8}}),
        encoding="utf-8",
    )
    (metrics / "gbrain-stale-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
    (metrics / "hindsight-security-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
    (metrics / "webhook-receiver-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
    (metrics / "slo-rollup-latest.json").write_text(json.dumps({"status": "degraded"}), encoding="utf-8")

    payload = metrics_dashboard.build_dashboard_payload(metrics)
    html = metrics_dashboard.render_dashboard(metrics, lang="zh")

    assert payload["overall_status"] == "action-needed"
    assert payload["explanations"]
    assert payload["actions"]
    assert "原因解读" in html
    assert "建议动作" in html


def test_status_command_prints_one_line_summary(tmp_path: Path):
    home = tmp_path / "home"
    metrics = home / "metrics"
    metrics.mkdir(parents=True)
    (metrics / "health-summary-latest.json").write_text(json.dumps({"status": "healthy", "alert_count": 0}), encoding="utf-8")
    (metrics / "langsmith-trend-latest.json").write_text(
        json.dumps({"monitor": {"recent_acceptance_ok_rate": 1.0}}),
        encoding="utf-8",
    )
    (metrics / "slo-rollup-latest.json").write_text(
        json.dumps({"acceptance_ok_rate": 1.0, "alert_queue_growth": 0}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(REPO / "bin" / "hermes-memory"), "status"],
        env={**os.environ, "AGENT_HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )

    line = result.stdout.strip()
    assert "\n" not in line
    assert line.startswith("healthy")
    assert "alerts=0" in line
    assert "acceptance=100.0%" in line


def test_status_command_does_not_count_info_alerts_as_actionable(tmp_path: Path):
    home = tmp_path / "home"
    metrics = home / "metrics"
    metrics.mkdir(parents=True)
    (metrics / "health-summary-latest.json").write_text(
        json.dumps(
            {
                "status": "healthy",
                "alert_count": 1,
                "alerts": [{"code": "historical_acceptance_failures", "severity": "info"}],
            }
        ),
        encoding="utf-8",
    )
    (metrics / "langsmith-trend-latest.json").write_text(
        json.dumps({"monitor": {"current_acceptance_ok_rate": 1.0}}),
        encoding="utf-8",
    )
    (metrics / "slo-rollup-latest.json").write_text(
        json.dumps({"acceptance_ok_rate": 1.0, "alert_queue_growth": 0}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(REPO / "bin" / "hermes-memory"), "status"],
        env={**os.environ, "AGENT_HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )

    assert "alerts=0" in result.stdout.strip()


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


def test_gbrain_stale_maintenance_loads_env_file(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".gbrain.env"
    env_file.write_text("OPENAI_BASE_URL=http://127.0.0.1:8766/v1\nOPENAI_API_KEY=sk-local-dummy\n", encoding="utf-8")
    monkeypatch.setattr(gbrain_stale_maintenance, "DEFAULT_GBRAIN_ENV_FILE", env_file)

    env = gbrain_stale_maintenance.gbrain_env()

    assert env["OPENAI_BASE_URL"] == "http://127.0.0.1:8766/v1"
    assert env["OPENAI_API_KEY"] == "sk-local-dummy"


def test_gbrain_stale_report_does_not_mark_success_when_actionable_debt_remains(monkeypatch):
    calls = []

    def fake_run(command, timeout=300):
        calls.append(command)
        if command[-1] == "health":
            return {
                "returncode": 0,
                "stdout": "Health score: 6/10\nMissing embeddings: 149\nStale pages: 918\nOrphan pages: 0\n",
                "stderr": "",
            }
        return {"returncode": 0, "stdout": "No chunks found", "stderr": ""}

    monkeypatch.setattr(gbrain_stale_maintenance, "run", fake_run)
    monkeypatch.setattr(gbrain_stale_maintenance, "actual_orphan_count", lambda: 0)

    report = gbrain_stale_maintenance.build_report(refresh_embeddings=True, reindex_code=False, output="")

    assert ["gbrain-embed", "embed", "--all"] not in calls
    assert ["gbrain-embed", "embed", "--stale", "--limit", "100"] in calls
    assert report["status"] == "action-needed"
    assert report["auto_fix_attempted"] is True
    assert report["auto_fix_succeeded"] is False
    assert report["auto_fix_failed"] is True


def test_server_cron_enables_gbrain_embedding_refresh():
    content = (REPO / "docs" / "ops" / "server-root.cron").read_text(encoding="utf-8")
    line = next(row for row in content.splitlines() if "gbrain-stale-refresh" in row)

    assert "--refresh-embeddings" in line
    assert "--stale-budget" in line
    assert "--missing-budget 0" in line


def test_server_cron_enables_async_live_hindsight_refresh():
    content = (REPO / "docs" / "ops" / "server-root.cron").read_text(encoding="utf-8")
    line = next(row for row in content.splitlines() if "live-hindsight-refresh" in row)

    assert "live_hindsight_refresh_worker.py" in line
    assert "flock -n" in line
    assert "--max-attempts 3" in line
    assert "--output /root/.hermes/metrics/live-hindsight-refresh-latest.json" in line


def test_cron_freshness_checks_live_hindsight_refresh_artifact():
    checks = {row["name"]: row["path"].name for row in cron_freshness.CHECKS}

    assert checks["live_hindsight_refresh"] == "live-hindsight-refresh-latest.json"


def test_storage_cross_check_filters_generated_gbrain_orphan_indexes(monkeypatch):
    def fake_run(command, capture_output=True, text=True, timeout=30):
        if command == ["gbrain", "health"]:
            return subprocess.CompletedProcess(
                command,
                0,
                "Health score: 8/10\nMissing embeddings: 0\nStale pages: 918\nOrphan pages: 1\n",
                "",
            )
        if command == ["gbrain", "orphans", "--json"]:
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps({"orphans": [{"slug": "hub-orphans-sessions"}]}),
                "",
            )
        raise AssertionError(command)

    monkeypatch.setattr(subprocess, "run", fake_run)

    payload = memory_storage_cross_check.gbrain_health()
    warnings = memory_storage_cross_check.evaluate(
        {
            "state_db": {"exists": True},
            "governance_db": {"exists": True},
            "hindsight": {"ok": True, "failed_consolidation": 0},
            "gbrain": payload,
        }
    )

    assert payload["orphan_pages_actual"] == 0
    assert "gbrain_orphans" not in warnings


def test_storage_cross_check_writes_output(monkeypatch, tmp_path: Path, capsys):
    output = tmp_path / "storage.json"
    monkeypatch.setattr(memory_storage_cross_check, "STATE_DB", tmp_path / "missing-state.db")
    monkeypatch.setattr(memory_storage_cross_check, "GOVERNANCE_DB", tmp_path / "missing-governance.db")
    monkeypatch.setattr(memory_storage_cross_check, "hindsight_stats", lambda: {"ok": True, "failed_consolidation": 0})
    monkeypatch.setattr(
        memory_storage_cross_check,
        "gbrain_health",
        lambda: {"ok": True, "missing_embeddings": 0, "orphan_pages_actual": 0},
    )
    monkeypatch.setattr(sys, "argv", ["memory_storage_cross_check.py", "--output", str(output)])

    rc = memory_storage_cross_check.main()

    assert rc == 1
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8"))["warnings"] == ["state_db_missing", "governance_db_missing"]
    assert "state_db_missing" in capsys.readouterr().out


def test_cron_freshness_reports_stale_jobs(tmp_path: Path, monkeypatch):
    fresh = tmp_path / "fresh.log"
    stale = tmp_path / "stale.log"
    fresh.write_text("ok\n", encoding="utf-8")
    stale.write_text("old\n", encoding="utf-8")
    now = 1_700_000_000
    os.utime(fresh, (now, now))
    os.utime(stale, (now - 10000, now - 10000))
    monkeypatch.setattr(
        cron_freshness,
        "CHECKS",
        [
            {"name": "fresh_job", "path": fresh, "max_age_s": 600},
            {"name": "stale_job", "path": stale, "max_age_s": 600},
        ],
    )
    monkeypatch.setattr(cron_freshness.time, "time", lambda: now)

    payload = cron_freshness.build_report()

    assert payload["status"] == "action-needed"
    assert {job["name"]: job["status"] for job in payload["jobs"]} == {
        "fresh_job": "healthy",
        "stale_job": "action-needed",
    }


def test_cron_freshness_uses_artifacts_for_silent_jobs():
    checks = {row["name"]: row["path"].name for row in cron_freshness.CHECKS}

    assert checks["runtime_drift_check"] == "runtime-drift-latest.json"
    assert checks["alert_queue"] == "health-summary-latest.json"
    assert checks["storage_cross_check"] == "storage-cross-check-latest.json"
    assert checks["gbrain_stale_refresh"] == "gbrain-stale-latest.json"


def test_sync_embeddings_stats_handles_missing_legacy_state_table(tmp_path: Path, monkeypatch, capsys):
    state_db = tmp_path / "state.db"
    semantics_db = tmp_path / "semantics.db"

    conn = sqlite3.connect(str(state_db))
    try:
        conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, content TEXT)")
        conn.execute("INSERT INTO messages (content) VALUES (?)", ("x" * 32,))
        conn.commit()
    finally:
        conn.close()

    conn = sqlite3.connect(str(semantics_db))
    try:
        conn.execute(
            """
            CREATE TABLE embeddings (
                message_id INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                embedding BLOB NOT NULL,
                content_len INTEGER NOT NULL,
                indexed_at REAL NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(sync_embeddings, "STATE_DB", state_db)
    monkeypatch.setattr(sync_embeddings, "SEMANTICS_DB", semantics_db)

    sync_embeddings.get_stats()
    out = capsys.readouterr().out

    assert "state.db message_embeddings: n/a (table missing)" in out
    assert "state.db gap:                n/a (table missing)" in out


def test_system_metrics_collector_appends_history(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    metrics_dir = home / "metrics"
    metrics_dir.mkdir(parents=True)
    monkeypatch.setattr(system_metrics_collector, "AGENT_HOME", home)
    monkeypatch.setattr(system_metrics_collector, "OUTPUT", metrics_dir / "system-metrics-latest.json")
    monkeypatch.setattr(system_metrics_collector, "HISTORY", metrics_dir / "system-metrics-history.jsonl")

    assert system_metrics_collector.main() == 0
    lines = (metrics_dir / "system-metrics-history.jsonl").read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1
    assert json.loads(lines[0])["disk"]["pct"] >= 0


def test_snapshot_compress_and_restore_roundtrip(tmp_path: Path):
    snapshot_dir = tmp_path / "snap-1"
    snapshot_dir.mkdir()
    (snapshot_dir / "file.txt").write_text("hello\n", encoding="utf-8")

    compressed = snapshot_compress.compress_snapshot(snapshot_dir, dry_run=False, remove_source=False)
    restored_dir = tmp_path / "restore"
    restored = snapshot_restore.restore_archive(Path(compressed["archive_path"]), restored_dir, dry_run=False)

    assert compressed["compressed"] is True
    assert Path(compressed["archive_path"]).exists()
    assert restored["restored"] is True
    assert (restored_dir / "snap-1" / "file.txt").read_text(encoding="utf-8") == "hello\n"


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


def test_memory_guardian_uses_production_default_node_limit(monkeypatch):
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

    assert cap["node_limit"] == 30000
    assert cap["usage_pct"] == 36.9
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
        assert cap["level"] == "action"
    finally:
        monkeypatch.delenv("MEMORY_GUARDIAN_NODE_LIMIT", raising=False)
        importlib.reload(guardian)
