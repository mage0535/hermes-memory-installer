#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import statistics
import sys
import time
import traceback
import urllib.request
from datetime import datetime
from pathlib import Path

import memory_governance_rebuild as governance_rebuild
from memory_governance_rebuild import (
    query_canonical_semantic,
    query_governance_hindsight,
    query_governance_hubs,
    query_governance_objects,
    query_governance_sessions,
)
from memory_family_registry import (
    focus_profile_intent,
    focus_profile_prefers_live_hindsight,
    focus_profile_recall_mode,
    focus_profile_for_query,
    get_query_family_policy,
    get_query_family_weak_layers,
    has_relationship_text,
    is_project_delivery_mode,
    is_project_exploration_mode,
    is_provider_config_query,
    is_project_query,
    is_relationship_query,
    is_system_query_text,
    is_provider_incident_query,
    is_provider_query,
    project_query_mode,
    provider_query_mode,
    query_family_prefers_live_hindsight,
    query_family_preserves_breadth,
    query_family_policy_ready,
)

AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
STATE_DB = AGENT_HOME / "state.db"
OUTPUT_CONTEXT = AGENT_HOME / "memories" / "TIERED_CONTEXT.md"
OUTPUT_RECALL = AGENT_HOME / "memories" / "PROACTIVE_RECALL.md"
HINDSIGHT_BASE_URL = os.environ.get("HINDSIGHT_BASE_URL", "http://127.0.0.1:8890")
HINDSIGHT_BANK = os.environ.get("HINDSIGHT_BANK", "hermes")
HINDSIGHT_RECALL_URL = f"{HINDSIGHT_BASE_URL}/v1/default/banks/{HINDSIGHT_BANK}/memories/recall"
HALF_LIFE_DAYS = 30
TOP_K_L1 = 5
TOP_K_L2 = 5
TOP_K_L3 = 5
RRF_K = 60
_ORIGINAL_ENSURE_GOVERNANCE_DB = governance_rebuild.ensure_governance_db
_GOVERNANCE_READY = False
_QUERY_CACHE: dict[tuple[str, str, int], list[dict]] = {}
_LAST_RECALL_DEBUG = {
    "cache_hits": 0,
    "cache_misses": 0,
    "weak_fallback_suppressed": 0,
}
SYSTEM_MARKERS = (
    "memory",
    "hermes",
    "config",
    "provider",
    "gateway",
    "cron",
    "system",
    "restart",
    "model",
    "usage",
    "archive",
    "重启",
    "模型",
    "用量",
    "模型用量",
    "归档",
)
SYSTEM_SPECIFIC_MARKERS = (
    "config",
    "provider",
    "gateway",
    "cron",
    "system",
    "重启",
    "模型",
    "用量",
    "模型用量",
    "归档",
    "server",
    "telegram",
    "endpoint",
    "api",
    "密钥",
    "key",
)
AUTO_NOISE_MARKERS = (
    "memory capacity",
    "archiving process",
    "memory_index.db",
    "goal-review/",
    "助手完成归档",
    "内存清理",
    "capacity is at",
)

RELATIONSHIP_MARKERS = (
    "kiki",
    "wang yuqi",
    "王钰淇",
    "朋友",
    "关系",
    "微信",
    "girl",
    "girlfriend",
    "message her",
)

RECENT_MARKERS = (
    "刚刚",
    "刚才",
    "today",
    "today's",
    "latest",
    "recent",
    "刚说",
    "最近一次",
)


def build_query_terms(query: str) -> list[str]:
    terms = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", query or "")
    if not terms and query and query.strip():
        return [query.strip()]
    return terms


def build_fts_query(query: str) -> str:
    terms = build_query_terms(query)
    if not terms:
        return ""
    safe_terms = []
    for term in terms:
        cleaned = term.replace('"', " ").strip()
        if cleaned:
            safe_terms.append(f"\"{cleaned}\"")
    return " OR ".join(safe_terms)


def is_system_query(query: str) -> bool:
    lowered = (query or "").lower()
    if is_system_query_text(query):
        return True
    return any(marker in lowered for marker in ("restart", "model", "usage", "archive", "重启", "模型", "用量", "模型用量", "归档"))


def is_provider_incident_cache_row(row: dict) -> bool:
    combined = f"{row.get('title', '')} {row.get('snippet', '')}".lower()
    incident_hits = any(
        marker in combined
        for marker in (
            "restart",
            "restarted",
            "interrupted",
            "shutting down",
            "shutdown",
            "error switching model",
            "重启",
            "重新启动",
            "新配置生效",
        )
    )
    config_hits = any(
        marker in combined
        for marker in ("provider", "config.yaml", "api key", "base url", "base_url", "endpoint", "/zen/")
    )
    return incident_hits and not config_hits


def hindsight_time_score(mentioned_at) -> float:
    return time_decay(mentioned_at, half_life=45)


def should_skip_hindsight_result(query: str, item: dict) -> bool:
    if is_system_query(query):
        return False
    text = (item.get("text") or "").lower()
    return any(marker in text for marker in AUTO_NOISE_MARKERS)


def classify_query_intent(query: str) -> str:
    dossier_intent = focus_profile_intent(query)
    if dossier_intent:
        return dossier_intent
    if is_system_query(query):
        return "system"
    if is_relationship_query(query):
        return "relationship"
    lowered = (query or "").lower()
    if any(marker in lowered for marker in RECENT_MARKERS):
        return "recent"
    if is_project_query(query):
        return "project"
    return "general"


def l3_layer_plan(query: str, top: int) -> list[tuple[str, int]]:
    intent = classify_query_intent(query)
    project_mode = project_query_mode(query)
    dossier_mode = focus_profile_recall_mode(query)
    if intent == "relationship":
        return [("hub", 1), ("object", min(2, top)), ("hindsight_cache", 1), ("hindsight", 1), ("governance", 1)]
    if intent == "dossier":
        if dossier_mode == "dossier_first" and focus_profile_prefers_live_hindsight(query):
            return [("hub", 1), ("object", min(2, top)), ("hindsight_cache", 1), ("hindsight", 1), ("governance", 1)]
        return [("hub", 1), ("object", min(2, top)), ("hindsight_cache", 1), ("governance", 1)]
    if intent == "system":
        return [("hub", 1), ("object", min(3, top)), ("hindsight_cache", 1), ("governance", 1)]
    if intent == "recent":
        return [("governance", min(2, top)), ("object", 1), ("hindsight_cache", 1), ("hub", 1)]
    if intent == "project":
        if is_project_exploration_mode(query):
            return [("hub", 1), ("governance", min(2, top)), ("object", 1), ("hindsight_cache", 1)]
        if is_project_delivery_mode(query):
            return [("hub", 1), ("object", min(2, top)), ("hindsight_cache", 1), ("governance", 1)]
        return [("hub", 1), ("object", min(2, top)), ("governance", 1), ("hindsight_cache", 1)]
    return [("hub", 1), ("object", min(2, top)), ("hindsight_cache", 1), ("governance", 1)]


def trim_l3_candidates(query: str, candidates: list[dict], top: int) -> list[dict]:
    planned = []
    seen = set()
    grouped: dict[str, list[dict]] = {}
    for row in candidates:
        grouped.setdefault(row.get("layer", "?"), []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda item: item.get("score", 0.0), reverse=True)

    for layer, quota in l3_layer_plan(query, top):
        picked = 0
        for row in grouped.get(layer, []):
            sid = row["session_id"]
            if sid in seen:
                continue
            seen.add(sid)
            planned.append(row)
            picked += 1
            if picked >= quota or len(planned) >= top:
                break
        if len(planned) >= top:
            return planned[:top]

    remaining = sorted(candidates, key=lambda item: item.get("score", 0.0), reverse=True)
    for row in remaining:
        sid = row["session_id"]
        if sid in seen:
            continue
        seen.add(sid)
        planned.append(row)
        if len(planned) >= top:
            break
    return planned[:top]


def count_direct_hits(query: str, rows: list[dict], layers: set[str] | None = None) -> int:
    hits = 0
    for row in rows:
        layer = row.get("layer", "")
        if layers and layer not in layers:
            continue
        if query_hits_text(query, row.get("title", ""), row.get("snippet", "")):
            hits += 1
    return hits


def should_use_live_hindsight(query: str, candidates: list[dict], top: int) -> bool:
    if query_family_prefers_live_hindsight(query):
        return True
    intent = classify_query_intent(query)
    if intent in {"relationship", "recent"}:
        return True
    strong_layers = {"hub", "object", "hindsight_cache", "governance"}
    direct_hits = count_direct_hits(query, candidates, strong_layers)
    if intent == "system":
        return direct_hits < 1
    if intent == "project":
        return direct_hits < max(2, min(top, 2))
    return direct_hits < max(2, min(top, 3))


def should_use_expensive_fallbacks(query: str, candidates: list[dict], top: int) -> bool:
    intent = classify_query_intent(query)
    if intent == "recent":
        return True
    if query_family_preserves_breadth(query):
        return True
    strong_layers = {"hub", "object", "hindsight_cache", "governance", "hindsight"}
    direct_hits = count_direct_hits(query, candidates, strong_layers)
    if get_query_family_policy(query):
        policy_layers = set(get_query_family_policy(query).get("strong_layers", ()))
        policy_direct_hits = count_direct_hits(query, candidates, policy_layers)
        if query_family_policy_ready(query, len(candidates), policy_direct_hits, top):
            return False
    strong_enough = len(candidates) >= top and direct_hits >= max(2, min(top, 3))
    if intent in {"relationship", "system", "project"} and strong_enough:
        return False
    return len(candidates) < (top * 2) or direct_hits < max(2, min(top, 3))


def live_hindsight_item_allowed(query: str, item: dict) -> bool:
    text = item.get("text") or ""
    entities = item.get("entities") or []
    entity_text = ", ".join(entities[:5]) if isinstance(entities, list) else str(entities or "")
    intent = classify_query_intent(query)
    if intent == "system":
        return query_hits_text(query, text, entity_text) or is_system_query(f"{text} {entity_text}")
    return query_hits_text(query, text, entity_text)


def ensure_governance_ready() -> None:
    global _GOVERNANCE_READY
    if _GOVERNANCE_READY:
        return
    _ORIGINAL_ENSURE_GOVERNANCE_DB(force=False, max_age_seconds=governance_rebuild.DEFAULT_MAX_AGE_SECONDS)
    governance_rebuild.ensure_governance_db = lambda force=False, max_age_seconds=governance_rebuild.DEFAULT_MAX_AGE_SECONDS: {
        "cached": True,
        "force": force,
        "max_age_seconds": max_age_seconds,
    }
    _GOVERNANCE_READY = True


def cached_governance_query(layer: str, query: str, top: int, fetcher) -> list[dict]:
    ensure_governance_ready()
    key = (layer, query, int(top))
    cached = _QUERY_CACHE.get(key)
    if cached is not None:
        _LAST_RECALL_DEBUG["cache_hits"] += 1
        return [row.copy() for row in cached]
    _LAST_RECALL_DEBUG["cache_misses"] += 1
    rows = fetcher(query, top=top)
    _QUERY_CACHE[key] = [row.copy() for row in rows]
    return [row.copy() for row in rows]


def normalize_topic_text(text: str) -> str:
    lowered = (text or "").lower()
    lowered = re.sub(r"\[[^\]]+\]", " ", lowered)
    lowered = re.sub(r"\b\d{8}_\d{6}_[a-z0-9]+\b", " ", lowered)
    lowered = re.sub(r"\brecovered placeholder session inserted on \d{4}-\d{2}-\d{2}\b", " ", lowered)
    lowered = re.sub(r"\bto preserve \d+ orphan messages without deleting history\b", " ", lowered)
    lowered = re.sub(r"\bcron_[a-z0-9_]+\b", " ", lowered)
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def canonical_candidate_key(title: str, snippet: str) -> str:
    normalized_title = normalize_topic_text(title)
    normalized_snippet = normalize_topic_text(snippet)
    if normalized_title and normalized_snippet.startswith(normalized_title):
        combined = normalized_title
    elif normalized_title:
        combined = f"{normalized_title} {normalized_snippet}".strip()
    else:
        combined = normalized_snippet
    return combined[:120]


def layer_priority(layer: str) -> int:
    priorities = {
        "hub": 60,
        "hindsight": 50,
        "object": 40,
        "hindsight_cache": 30,
        "governance": 20,
        "governance_like": 15,
        "like": 10,
        "fts5": 10,
        "semantics": 5,
        "archive": 1,
    }
    return priorities.get(layer or "", 0)


def query_hits_text(query: str, *texts: str) -> bool:
    terms = [term.lower() for term in build_query_terms(query) if len(term.strip()) >= 2]
    haystack = " ".join(texts).lower()
    return bool(terms) and any(term in haystack for term in terms)


def count_query_term_hits(query: str, *texts: str) -> int:
    terms = []
    seen = set()
    for term in build_query_terms(query):
        lowered = term.lower().strip()
        if len(lowered) < 2 or lowered in seen:
            continue
        seen.add(lowered)
        terms.append(lowered)
    haystack = " ".join(texts).lower()
    return sum(1 for term in terms if term in haystack)


def has_any_marker(markers: tuple[str, ...], *texts: str) -> bool:
    haystack = " ".join(texts).lower()
    return any(marker in haystack for marker in markers)


def minimum_term_coverage(query: str) -> int:
    terms = {term.lower().strip() for term in build_query_terms(query) if len(term.lower().strip()) >= 2}
    if not terms:
        return 0
    if len(terms) == 1:
        return 1
    return min(2, len(terms))


def l2_candidate_allowed(query: str, title: str, snippet: str) -> bool:
    intent = classify_query_intent(query)
    combined = f"{title or ''} {snippet or ''}"
    covered_terms = count_query_term_hits(query, title or "", snippet or "")
    required_terms = minimum_term_coverage(query)
    if intent == "relationship":
        lowered = combined.lower()
        if any(marker in lowered for marker in AUTO_NOISE_MARKERS):
            return False
        return query_hits_text(query, title or "", snippet or "")
    if intent == "system":
        if has_relationship_text(combined) and not has_any_marker(SYSTEM_SPECIFIC_MARKERS, combined):
            return False
        if required_terms >= 2 and covered_terms < required_terms:
            return False
        return query_hits_text(query, title or "", snippet or "") or is_system_query(combined)
    if intent == "project":
        if required_terms >= 2 and covered_terms < required_terms:
            return False
        return query_hits_text(query, title or "", snippet or "")
    return True


def l3_candidate_allowed(query: str, layer: str, title: str, snippet: str) -> bool:
    intent = classify_query_intent(query)
    combined = f"{title or ''} {snippet or ''}"
    covered_terms = count_query_term_hits(query, title or "", snippet or "")
    required_terms = minimum_term_coverage(query)
    if intent == "system":
        if has_relationship_text(combined) and not has_any_marker(SYSTEM_SPECIFIC_MARKERS, combined):
            return False
        if layer != "hub" and required_terms >= 2 and covered_terms < required_terms:
            return False
        if layer in {"hub", "object", "hindsight", "hindsight_cache", "governance"}:
            return query_hits_text(query, title or "", snippet or "") or is_system_query(combined)
        return query_hits_text(query, title or "", snippet or "") or is_system_query(combined)
    if intent == "project":
        if layer != "hub" and required_terms >= 2 and covered_terms < required_terms:
            return False
        return query_hits_text(query, title or "", snippet or "")
    if intent == "relationship":
        return query_hits_text(query, title or "", snippet or "")
    return True


def is_session_like_title(title: str) -> bool:
    value = (title or "").strip().lower()
    if not value:
        return True
    if value.startswith("cron_") or value.startswith("[system: you are running as a scheduled cron job."):
        return True
    return bool(re.fullmatch(r"\d{8}_\d{6}_[a-z0-9]+", value))


def time_decay(ended_at, half_life: int = HALF_LIFE_DAYS) -> float:
    if not ended_at:
        return 1.0
    try:
        if isinstance(ended_at, (int, float)):
            ended = datetime.fromtimestamp(ended_at)
        else:
            ended = datetime.fromisoformat(str(ended_at).replace("Z", "+00:00"))
        age_days = (datetime.now() - ended).total_seconds() / 86400
        return round(math.exp(-max(age_days, 0) / half_life), 4)
    except Exception:
        return 1.0


def rerank_fused(query: str, fused_rows: list[dict]) -> list[dict]:
    intent = classify_query_intent(query)
    provider_mode = provider_query_mode(query)
    project_mode = project_query_mode(query)
    policy_weak_layers = get_query_family_weak_layers(query)
    strong_provider_object = any(
        "object" in set(row.get("sources", []))
        and (
            "provider" in f"{row.get('data', {}).get('title', '')} {row.get('data', {}).get('snippet', '')}".lower()
            or "endpoint" in f"{row.get('data', {}).get('title', '')} {row.get('data', {}).get('snippet', '')}".lower()
        )
        for row in fused_rows
    )
    strong_provider_cache = any(
        "hindsight_cache" in set(row.get("sources", []))
        and any(
            marker in f"{row.get('data', {}).get('title', '')} {row.get('data', {}).get('snippet', '')}".lower()
            for marker in ("provider", "config.yaml", "api key", "base url", "base_url", "endpoint", "/zen/")
        )
        for row in fused_rows
    )
    strong_project_object = any(
        "object" in set(row.get("sources", []))
        and any(
            marker in f"{row.get('data', {}).get('title', '')} {row.get('data', {}).get('snippet', '')}".lower()
            for marker in ("deploy", "commit", "push", "publish", "docs", "documentation", "readme", "about")
        )
        for row in fused_rows
    )
    strong_project_cache = any(
        "hindsight_cache" in set(row.get("sources", []))
        and any(
            marker in f"{row.get('data', {}).get('title', '')} {row.get('data', {}).get('snippet', '')}".lower()
            for marker in ("deploy", "commit", "push", "publish", "docs", "documentation", "readme", "about")
        )
        for row in fused_rows
    )
    reranked = []
    for row in fused_rows:
        score = row["rrf_score"]
        layer_set = set(row.get("sources", []))
        data = row.get("data", {}) or {}
        session_like_result = is_session_like_title(str(data.get("title", ""))) or is_session_like_title(str(data.get("slug", "")))
        if (
            provider_mode == "config"
            and strong_provider_object
            and strong_provider_cache
            and layer_set & policy_weak_layers
            and not (layer_set & {"hub", "object", "hindsight", "hindsight_cache"})
        ):
            continue
        if (
            project_mode == "delivery"
            and strong_project_object
            and strong_project_cache
            and layer_set & policy_weak_layers
            and not (layer_set & {"hub", "object", "hindsight", "hindsight_cache"})
        ):
            continue
        if intent == "relationship":
            if "hub" in layer_set:
                score += 0.006
            if "hindsight_cache" in layer_set or "hindsight" in layer_set:
                score += 0.004
            if "fts5" in layer_set or "like" in layer_set:
                score -= 0.004
        elif intent == "system":
            if "hub" in layer_set:
                score += 0.005
            if "object" in layer_set:
                score += 0.003
            if "fts5" in layer_set or "like" in layer_set:
                score -= 0.003
            if session_like_result and not (layer_set & {"hub", "object", "hindsight", "hindsight_cache"}):
                score -= 0.02
        elif intent == "project":
            if "hub" in layer_set:
                score += 0.004
            if "object" in layer_set:
                score += 0.003
            if session_like_result and not (layer_set & {"hub", "object", "hindsight", "hindsight_cache"}):
                score -= 0.018
        reranked.append({**row, "rrf_score": round(score, 12)})
    return sorted(reranked, key=lambda item: item["rrf_score"], reverse=True)


def ensure_recall_metrics_table() -> None:
    conn = sqlite3.connect(str(governance_rebuild.GOVERNANCE_DB))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recall_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                query TEXT NOT NULL,
                intent TEXT NOT NULL,
                l2_count INTEGER NOT NULL,
                l3_count INTEGER NOT NULL,
                fused_count INTEGER NOT NULL,
                unique_count INTEGER NOT NULL,
                duplicate_suppressed INTEGER NOT NULL,
                object_conflict_suppressed INTEGER NOT NULL,
                live_hindsight_used INTEGER NOT NULL DEFAULT 0,
                live_hindsight_results INTEGER NOT NULL DEFAULT 0,
                cache_hits INTEGER NOT NULL DEFAULT 0,
                cache_misses INTEGER NOT NULL DEFAULT 0,
                weak_fallback_suppressed INTEGER NOT NULL DEFAULT 0,
                top_layers TEXT,
                top_titles TEXT,
                duration_ms REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recall_metric_rollups (
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
                updated_at REAL NOT NULL
            )
            """
        )
        existing = {row[1] for row in conn.execute("PRAGMA table_info(recall_metrics)").fetchall()}
        if "live_hindsight_used" not in existing:
            conn.execute("ALTER TABLE recall_metrics ADD COLUMN live_hindsight_used INTEGER NOT NULL DEFAULT 0")
        if "live_hindsight_results" not in existing:
            conn.execute("ALTER TABLE recall_metrics ADD COLUMN live_hindsight_results INTEGER NOT NULL DEFAULT 0")
        if "cache_hits" not in existing:
            conn.execute("ALTER TABLE recall_metrics ADD COLUMN cache_hits INTEGER NOT NULL DEFAULT 0")
        if "cache_misses" not in existing:
            conn.execute("ALTER TABLE recall_metrics ADD COLUMN cache_misses INTEGER NOT NULL DEFAULT 0")
        if "weak_fallback_suppressed" not in existing:
            conn.execute("ALTER TABLE recall_metrics ADD COLUMN weak_fallback_suppressed INTEGER NOT NULL DEFAULT 0")
        rollup_existing = {row[1] for row in conn.execute("PRAGMA table_info(recall_metric_rollups)").fetchall()}
        if "avg_live_hindsight_used" not in rollup_existing:
            conn.execute("ALTER TABLE recall_metric_rollups ADD COLUMN avg_live_hindsight_used REAL")
        if "avg_live_hindsight_results" not in rollup_existing:
            conn.execute("ALTER TABLE recall_metric_rollups ADD COLUMN avg_live_hindsight_results REAL")
        if "avg_cache_hits" not in rollup_existing:
            conn.execute("ALTER TABLE recall_metric_rollups ADD COLUMN avg_cache_hits REAL")
        if "avg_cache_misses" not in rollup_existing:
            conn.execute("ALTER TABLE recall_metric_rollups ADD COLUMN avg_cache_misses REAL")
        if "avg_weak_fallback_suppressed" not in rollup_existing:
            conn.execute("ALTER TABLE recall_metric_rollups ADD COLUMN avg_weak_fallback_suppressed REAL")
        conn.commit()
    finally:
        conn.close()


def update_recall_metric_rollups(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT intent, duration_ms, duplicate_suppressed, object_conflict_suppressed,
               live_hindsight_used, live_hindsight_results, cache_hits, cache_misses,
               weak_fallback_suppressed
        FROM recall_metrics
        ORDER BY id DESC
        LIMIT 500
        """
    ).fetchall()
    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(str(row[0]), []).append(row)

    for intent, items in grouped.items():
        durations = sorted(float(item[1] or 0.0) for item in items if item[1] is not None)
        duplicates = [float(item[2] or 0.0) for item in items]
        conflicts = [float(item[3] or 0.0) for item in items]
        live_hindsight_used = [float(item[4] or 0.0) for item in items]
        live_hindsight_results = [float(item[5] or 0.0) for item in items]
        cache_hits = [float(item[6] or 0.0) for item in items]
        cache_misses = [float(item[7] or 0.0) for item in items]
        weak_fallback_suppressed = [float(item[8] or 0.0) for item in items]
        if durations:
            p50 = statistics.median(durations)
            idx95 = max(0, min(len(durations) - 1, math.ceil(len(durations) * 0.95) - 1))
            p95 = durations[idx95]
            avg_duration = sum(durations) / len(durations)
        else:
            p50 = p95 = avg_duration = 0.0
        conn.execute(
            """
            INSERT INTO recall_metric_rollups (
                intent, sample_count, avg_duration_ms, p50_duration_ms, p95_duration_ms,
                avg_duplicate_suppressed, avg_object_conflict_suppressed,
                avg_live_hindsight_used, avg_live_hindsight_results, avg_cache_hits,
                avg_cache_misses, avg_weak_fallback_suppressed, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(intent) DO UPDATE SET
                sample_count=excluded.sample_count,
                avg_duration_ms=excluded.avg_duration_ms,
                p50_duration_ms=excluded.p50_duration_ms,
                p95_duration_ms=excluded.p95_duration_ms,
                avg_duplicate_suppressed=excluded.avg_duplicate_suppressed,
                avg_object_conflict_suppressed=excluded.avg_object_conflict_suppressed,
                avg_live_hindsight_used=excluded.avg_live_hindsight_used,
                avg_live_hindsight_results=excluded.avg_live_hindsight_results,
                avg_cache_hits=excluded.avg_cache_hits,
                avg_cache_misses=excluded.avg_cache_misses,
                avg_weak_fallback_suppressed=excluded.avg_weak_fallback_suppressed,
                updated_at=excluded.updated_at
            """,
            (
                intent,
                len(items),
                round(avg_duration, 3),
                round(p50, 3),
                round(p95, 3),
                round(sum(duplicates) / len(duplicates), 3) if duplicates else 0.0,
                round(sum(conflicts) / len(conflicts), 3) if conflicts else 0.0,
                round(sum(live_hindsight_used) / len(live_hindsight_used), 3) if live_hindsight_used else 0.0,
                round(sum(live_hindsight_results) / len(live_hindsight_results), 3) if live_hindsight_results else 0.0,
                round(sum(cache_hits) / len(cache_hits), 3) if cache_hits else 0.0,
                round(sum(cache_misses) / len(cache_misses), 3) if cache_misses else 0.0,
                round(sum(weak_fallback_suppressed) / len(weak_fallback_suppressed), 3)
                if weak_fallback_suppressed
                else 0.0,
                time.time(),
            ),
        )


def record_recall_metrics(
    query: str,
    l2: list[dict],
    l3: list[dict],
    fused: list[dict],
    duration_ms: float | None = None,
    live_hindsight_used: bool = False,
    live_hindsight_results: int = 0,
) -> None:
    if not governance_rebuild.GOVERNANCE_DB.exists():
        return
    ensure_recall_metrics_table()
    top_layers = json.dumps([",".join(row.get("sources", [])) for row in fused[:5]], ensure_ascii=False)
    top_titles = json.dumps([row.get("data", {}).get("title", "")[:80] for row in fused[:5]], ensure_ascii=False)
    raw_count = len(l2) + len(l3)
    unique_count = len(fused)
    duplicate_suppressed = max(raw_count - unique_count, 0)
    object_stats = dict(governance_rebuild.LAST_OBJECT_QUERY_STATS or {})
    debug_stats = dict(_LAST_RECALL_DEBUG or {})
    payload = (
        time.time(),
        query,
        classify_query_intent(query),
        len(l2),
        len(l3),
        len(fused[:5]),
        unique_count,
        duplicate_suppressed,
        int(object_stats.get("suppressed_conflict_rows", 0)),
        int(bool(live_hindsight_used)),
        int(live_hindsight_results),
        int(debug_stats.get("cache_hits", 0)),
        int(debug_stats.get("cache_misses", 0)),
        int(debug_stats.get("weak_fallback_suppressed", 0)),
        top_layers,
        top_titles,
        duration_ms,
    )
    for attempt in range(6):
        conn = sqlite3.connect(str(governance_rebuild.GOVERNANCE_DB), timeout=5)
        try:
            conn.execute(
                """
                INSERT INTO recall_metrics (
                    created_at, query, intent, l2_count, l3_count, fused_count, unique_count,
                    duplicate_suppressed, object_conflict_suppressed, live_hindsight_used,
                    live_hindsight_results, cache_hits, cache_misses, weak_fallback_suppressed,
                    top_layers, top_titles, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
            update_recall_metric_rollups(conn)
            conn.commit()
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt >= 5:
                if attempt >= 5:
                    print(f"[tiered_context] metrics write failed after {attempt + 1} retries: {exc}", file=sys.stderr)
                return
            time.sleep(0.2 * (attempt + 1))
        finally:
            conn.close()


def rrf_fuse(results_list, query: str | None = None, k: int = RRF_K):
    scores = {}
    for results in results_list:
        for i, row in enumerate(results):
            item_id = row.get("session_id") or row.get("slug")
            if not item_id:
                continue
            rank = i + 1
            slot = scores.setdefault(
                item_id,
                {"rrf_score": 0.0, "sources": [], "data": row.copy()},
            )
            slot["rrf_score"] += (1.0 / (k + rank)) + (0.05 * row.get("score", 0.0))
            slot["sources"].append(row.get("layer", "?"))
    fused = sorted(scores.values(), key=lambda item: item["rrf_score"], reverse=True)
    if query:
        return rerank_fused(query, fused)
    return fused


def get_l1(limit: int = TOP_K_L1):
    if not STATE_DB.exists():
        return []
    conn = sqlite3.connect(str(STATE_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, title, started_at, source, message_count
            FROM sessions
            WHERE parent_session_id IS NULL
              AND COALESCE(end_reason, '') <> 'recovered-orphan-session'
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit + 10,),
        ).fetchall()
        results = []
        for row in rows:
            preview_row = conn.execute(
                """
                SELECT content
                FROM messages
                WHERE session_id = ? AND role = 'user'
                ORDER BY timestamp ASC
                LIMIT 1
                """,
                (row["id"],),
            ).fetchone()
            preview = (preview_row[0] if preview_row and preview_row[0] else "")[:80]
            results.append(
                {
                    "session_id": row["id"],
                    "time": datetime.fromtimestamp(row["started_at"]).strftime("%m-%d %H:%M")
                    if row["started_at"]
                    else "?",
                    "source": row["source"] or "?",
                    "title": (row["title"] or "(untitled)")[:48],
                    "preview": preview,
                    "msgs": row["message_count"] or 0,
                }
            )
            if len(results) >= limit:
                break
        return results
    finally:
        conn.close()


def get_l2(query: str, top: int = TOP_K_L2):
    results = []
    if not STATE_DB.exists():
        return results
    intent = classify_query_intent(query)
    effective_top = min(top, 2) if intent == "relationship" else top
    fts_limit = effective_top * (2 if intent == "relationship" else 4)
    like_limit = effective_top * (2 if intent == "relationship" else 3)
    conn = sqlite3.connect(str(STATE_DB))
    conn.row_factory = sqlite3.Row
    seen = set()
    try:
        fts_query = build_fts_query(query)
        if fts_query:
            rows = conn.execute(
                """
                SELECT m.session_id, m.content, s.title, s.source, s.ended_at
                FROM messages_fts f
                JOIN messages m ON f.rowid = m.id
                JOIN sessions s ON m.session_id = s.id
                WHERE messages_fts MATCH ?
                  AND s.ended_at IS NOT NULL
                  AND s.id NOT LIKE 'cron_%'
                  AND COALESCE(s.end_reason, '') <> 'recovered-orphan-session'
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, fts_limit),
            ).fetchall()
            for row in rows:
                sid = row["session_id"]
                if sid in seen:
                    continue
                snippet = (row["content"] or "")[:180]
                title = row["title"] or sid
                if not l2_candidate_allowed(query, title, snippet):
                    continue
                seen.add(sid)
                results.append(
                    {
                        "session_id": sid,
                        "slug": sid,
                        "title": title,
                        "snippet": snippet,
                        "source": row["source"],
                        "layer": "fts5",
                        "score": round(0.90 * time_decay(row["ended_at"]), 4),
                    }
                )
                if len(results) >= effective_top:
                    break
        if len(results) < effective_top:
            like_pat = f"%{query.strip()}%"
            rows = conn.execute(
                """
                SELECT
                    s.id,
                    s.title,
                    s.source,
                    s.ended_at,
                    (
                        SELECT content
                        FROM messages
                        WHERE session_id = s.id AND role = 'user'
                        ORDER BY timestamp ASC
                        LIMIT 1
                    ) AS preview
                FROM sessions s
                WHERE s.ended_at IS NOT NULL
                  AND s.id NOT LIKE 'cron_%'
                  AND COALESCE(s.end_reason, '') <> 'recovered-orphan-session'
                  AND (s.title LIKE ? OR s.summary LIKE ? OR s.id LIKE ?)
                ORDER BY s.ended_at DESC
                LIMIT ?
                """,
                (like_pat, like_pat, like_pat, like_limit),
            ).fetchall()
            for row in rows:
                sid = row["id"]
                if sid in seen:
                    continue
                title = row["title"] or sid
                snippet = (row["preview"] or "")[:180]
                if not l2_candidate_allowed(query, title, snippet):
                    continue
                seen.add(sid)
                results.append(
                    {
                        "session_id": sid,
                        "slug": sid,
                        "title": title,
                        "snippet": snippet,
                        "source": row["source"],
                        "layer": "like",
                        "score": round(0.65 * time_decay(row["ended_at"]), 4),
                    }
                )
                if len(results) >= effective_top:
                    break
    finally:
        conn.close()
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:effective_top]


def get_l3(query: str, top: int = TOP_K_L3):
    _LAST_RECALL_DEBUG["cache_hits"] = 0
    _LAST_RECALL_DEBUG["cache_misses"] = 0
    _LAST_RECALL_DEBUG["weak_fallback_suppressed"] = 0
    candidates = []
    seen = set()
    seen_keys = set()
    key_index: dict[str, int] = {}
    live_hindsight_used = False
    live_hindsight_results = 0
    allow_cron = any(term.lower() == "cron" for term in build_query_terms(query))

    def add_candidate(row: dict):
        sid = row["session_id"]
        if not allow_cron and str(sid).startswith("cron_"):
            _LAST_RECALL_DEBUG["weak_fallback_suppressed"] += 1
            return
        if not l3_candidate_allowed(query, row.get("layer", ""), row.get("title", ""), row.get("snippet", "")):
            _LAST_RECALL_DEBUG["weak_fallback_suppressed"] += 1
            return
        if (
            is_provider_query(query)
            and not is_provider_incident_query(query)
            and row.get("layer", "") == "hindsight_cache"
            and is_provider_incident_cache_row(row)
            and any(
                existing.get("layer", "") == "object"
                and (
                    "provider" in f"{existing.get('title', '')} {existing.get('snippet', '')}".lower()
                    or "endpoint" in f"{existing.get('title', '')} {existing.get('snippet', '')}".lower()
                )
                for existing in candidates
            )
        ):
            _LAST_RECALL_DEBUG["weak_fallback_suppressed"] += 1
            return
        if (
            is_provider_query(query)
            and not is_provider_incident_query(query)
            and row.get("layer", "") in {"fts5", "like", "semantics", "archive", "governance_like", "governance"}
            and any(
                existing.get("layer", "") == "object"
                and (
                    "provider" in f"{existing.get('title', '')} {existing.get('snippet', '')}".lower()
                    or "endpoint" in f"{existing.get('title', '')} {existing.get('snippet', '')}".lower()
                )
                for existing in candidates
            )
            and any(
                existing.get("layer", "") == "hindsight_cache"
                and (
                    "provider" in f"{existing.get('title', '')} {existing.get('snippet', '')}".lower()
                    or "config.yaml" in f"{existing.get('title', '')} {existing.get('snippet', '')}".lower()
                    or "endpoint" in f"{existing.get('title', '')} {existing.get('snippet', '')}".lower()
                )
                for existing in candidates
            )
        ):
            _LAST_RECALL_DEBUG["weak_fallback_suppressed"] += 1
            return
        if classify_query_intent(query) == "system" and row.get("layer", "") in {"semantics", "archive", "governance_like", "governance"}:
            strong_system_hit = any(
                existing.get("layer", "") in {"hub", "object"} and query_hits_text(query, existing.get("title", ""), existing.get("snippet", ""))
                for existing in candidates
            )
            strong_provider_hit = (
                is_provider_query(query)
                and not is_provider_incident_query(query)
                and any(
                    existing.get("layer", "") in {"object", "hindsight_cache"}
                    and query_hits_text(query, existing.get("title", ""), existing.get("snippet", ""))
                    for existing in candidates
                )
            )
            if strong_system_hit and is_session_like_title(row.get("title", "")):
                _LAST_RECALL_DEBUG["weak_fallback_suppressed"] += 1
                return
            if strong_provider_hit:
                _LAST_RECALL_DEBUG["weak_fallback_suppressed"] += 1
                return
            if strong_system_hit:
                combined_text = f"{row.get('title', '')} {row.get('snippet', '')}"
                if "用量" in query and "用量" not in combined_text:
                    _LAST_RECALL_DEBUG["weak_fallback_suppressed"] += 1
                    return
                total_terms = len({term.lower().strip() for term in build_query_terms(query) if len(term.lower().strip()) >= 2})
                covered_terms = count_query_term_hits(query, row.get("title", ""), row.get("snippet", ""))
                if total_terms >= 2 and covered_terms < total_terms:
                    _LAST_RECALL_DEBUG["weak_fallback_suppressed"] += 1
                    return
        if sid in seen:
            return
        key = canonical_candidate_key(row.get("title", ""), row.get("snippet", ""))
        if key and key in key_index:
            existing_idx = key_index[key]
            existing = candidates[existing_idx]
            if layer_priority(row.get("layer", "")) > layer_priority(existing.get("layer", "")):
                seen.discard(existing["session_id"])
                seen.add(sid)
                candidates[existing_idx] = row
            return
        seen.add(sid)
        if key:
            seen_keys.add(key)
            key_index[key] = len(candidates)
        candidates.append(row)

    for row in cached_governance_query("hub", query, max(1, top // 2), query_governance_hubs):
        add_candidate(
            {
                "session_id": row["session_id"],
                "slug": row["session_id"],
                "title": row["title"],
                "snippet": row["snippet"],
                "source": row["source"],
                "layer": row["layer"],
                "score": row["score"],
            }
        )

    for row in cached_governance_query("object", query, top, query_governance_objects):
        add_candidate(
            {
                "session_id": row["session_id"],
                "slug": row["session_id"],
                "title": row["title"],
                "snippet": row["snippet"],
                "source": row["source"],
                "layer": row["layer"],
                "score": row["score"],
            }
        )

    for row in cached_governance_query("governance", query, top * 3, query_governance_sessions):
        add_candidate(
            {
                "session_id": row["session_id"],
                "slug": row["session_id"],
                "title": row["title"],
                "snippet": row["snippet"],
                "source": row["source"],
                "layer": row["layer"],
                "score": row["score"],
            }
        )

    for row in cached_governance_query("hindsight_cache", query, top * 3, query_governance_hindsight):
        add_candidate(
            {
                "session_id": row["session_id"],
                "slug": row["session_id"],
                "title": row["title"],
                "snippet": row["snippet"],
                "source": row["source"],
                "layer": row["layer"],
                "score": row["score"],
            }
        )

    if should_use_live_hindsight(query, candidates, top):
        live_hindsight_used = True
        hindsight_payload = json.dumps(
            {
                "query": query,
                "types": ["world", "experience", "observation"],
                "budget": "low",
                "max_tokens": 1200,
                "trace": False,
            }
        ).encode("utf-8")
        try:
            request = urllib.request.Request(
                HINDSIGHT_RECALL_URL,
                data=hindsight_payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            for item in payload.get("results", []):
                text = item.get("text") or ""
                if not text or should_skip_hindsight_result(query, item) or not live_hindsight_item_allowed(query, item):
                    continue
                slug = f"hindsight:{item.get('id', '')}"
                type_boost = {
                    "observation": 0.05,
                    "world": 0.03,
                    "experience": 0.02,
                }.get(item.get("type"), 0.0)
                score = round(min(0.78 + type_boost + 0.12 * hindsight_time_score(item.get("mentioned_at")), 0.93), 4)
                title = text[:60]
                entities = item.get("entities") or []
                entity_text = ", ".join(entities[:3]) if isinstance(entities, list) else ""
                snippet = text[:180]
                if entity_text:
                    snippet = f"{snippet} | entities: {entity_text}"[:180]
                add_candidate(
                    {
                        "session_id": slug,
                        "slug": slug,
                        "title": title,
                        "snippet": snippet,
                        "source": "hindsight",
                        "layer": "hindsight",
                        "score": score,
                    }
                )
                live_hindsight_results += 1
                if len(candidates) >= top * 4:
                    break
        except Exception as exc:
            print(f"[tiered_context] live hindsight recall failed: {exc}", file=sys.stderr)

    use_expensive_fallbacks = should_use_expensive_fallbacks(query, candidates, top)

    sem_db = AGENT_HOME / "semantics.db"
    if use_expensive_fallbacks and sem_db.exists() and len(candidates) < top * 3:
        conn = sqlite3.connect(str(sem_db))
        try:
            rows = conn.execute(
                """
                SELECT session_id, content
                FROM embeddings
                WHERE content LIKE ?
                GROUP BY session_id
                ORDER BY MAX(indexed_at) DESC
                LIMIT ?
                """,
                (f"%{query}%", top * 2),
            ).fetchall()
            for sid, content in rows:
                if sid.startswith("cron_"):
                    continue
                add_candidate(
                    {
                        "session_id": sid,
                        "slug": sid,
                        "title": sid,
                        "snippet": (content or "")[:180],
                        "source": "semantics",
                        "layer": "semantics",
                        "score": 0.48,
                    }
                )
                if len(candidates) >= top * 3:
                    break
        finally:
            conn.close()

    if use_expensive_fallbacks and STATE_DB.exists() and len(candidates) < top * 3:
        conn = sqlite3.connect(str(STATE_DB))
        try:
            fts_query = build_fts_query(query)
            if fts_query:
                rows = conn.execute(
                    """
                    SELECT name, summary, category
                    FROM archives_fts
                    WHERE archives_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_query, top * 2),
                ).fetchall()
                for name, summary, category in rows:
                    slug = f"archive:{name}"
                    add_candidate(
                        {
                            "session_id": slug,
                            "slug": slug,
                            "title": name[:60],
                            "snippet": (summary or "")[:180],
                            "source": f"archive:{category or '?'}",
                            "layer": "archive",
                            "score": 0.40,
                        }
                    )
                    if len(candidates) >= top * 3:
                        break
        finally:
            conn.close()

    if use_expensive_fallbacks and len(candidates) < top * 3:
        for row in query_canonical_semantic(query, top=min(top, 3)):
            add_candidate(
                {
                    "session_id": row["session_id"],
                    "slug": row["session_id"],
                    "title": row["title"],
                    "snippet": row["snippet"],
                    "source": row["source"],
                    "layer": row["layer"],
                    "score": row["score"],
                }
            )
            if len(candidates) >= top * 3:
                break

    return trim_l3_candidates(query, candidates, top), live_hindsight_used, live_hindsight_results


def adjust_with_feedback(fused_results):
    return fused_results


def route_context(fused_results, query: str):
    high = [row for row in fused_results if row["rrf_score"] > 0.025]
    mid = [row for row in fused_results if 0.01 <= row["rrf_score"] <= 0.025]
    if len(high) >= 2:
        return {"decision": "inject_all", "count": len(high), "sessions": high}
    if mid:
        return {"decision": "inject_one", "count": 1, "sessions": [mid[0]]}
    return {"decision": "fallback_session_search", "count": 0, "sessions": []}


def generate(recall_queries=None):
    OUTPUT_CONTEXT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_RECALL.parent.mkdir(parents=True, exist_ok=True)
    l1 = get_l1()
    lines = [
        "<!-- Auto-generated by tiered_context_injector.py (governance-aware) -->",
        "",
        "## L1: Recent Sessions",
        "",
        "| Time | Source | Title | First User Message |",
        "|------|--------|-------|--------------------|",
    ]
    for row in l1:
        lines.append(f"| {row['time']} | {row['source']} | {row['title']} | {row['preview']} |")

    if recall_queries:
        for query in recall_queries:
            started_at = time.perf_counter()
            lines.append("")
            lines.append(f"### Recall: {query}")
            l2 = get_l2(query)
            l3, live_hindsight_used, live_hindsight_results = get_l3(query)
            if l2 or l3:
                fused = (
                    rrf_fuse([l2, l3], query=query)
                    if (l2 and l3)
                    else [
                        {
                            "rrf_score": row.get("score", 0.5),
                            "sources": [row.get("layer", "?")],
                            "data": row,
                        }
                        for row in (l2 or l3)
                    ]
                )
                fused = adjust_with_feedback(fused)
                record_recall_metrics(
                    query,
                    l2,
                    l3,
                    fused,
                    duration_ms=round((time.perf_counter() - started_at) * 1000.0, 3),
                    live_hindsight_used=live_hindsight_used,
                    live_hindsight_results=live_hindsight_results,
                )
                route = route_context(fused, query)
                lines.append(
                    f"Decision: {route['decision']} ({route['count']} candidates | L2={len(l2)} L3={len(l3)})"
                )
                for row in fused[:5]:
                    data = row["data"]
                    lines.append(
                        f"- [{','.join(row['sources'])}] {data.get('title', '?')[:60]} | "
                        f"rrf={row['rrf_score']:.4f} | {data.get('snippet', '')[:120]}"
                    )

    lines.extend(
        [
            "",
            "---",
            f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"L1={len(l1)} | RRF k={RRF_K}",
        ]
    )
    OUTPUT_CONTEXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Tiered Context Injector (governance-aware)")
    parser.add_argument("--recall", nargs="*", help="Recall query list")
    parser.add_argument("--test", help="Test a single recall query and print JSON")
    args = parser.parse_args()

    if args.test:
        started_at = time.perf_counter()
        l2 = get_l2(args.test)
        l3, live_hindsight_used, live_hindsight_results = get_l3(args.test)
        fused = (
            rrf_fuse([l2, l3], query=args.test)
            if (l2 and l3)
            else [
                {
                    "rrf_score": row.get("score", 0.5),
                    "sources": [row.get("layer", "?")],
                    "data": row,
                }
                for row in (l2 or l3)
            ]
        )
        record_recall_metrics(
            args.test,
            l2,
            l3,
            fused,
            duration_ms=round((time.perf_counter() - started_at) * 1000.0, 3),
            live_hindsight_used=live_hindsight_used,
            live_hindsight_results=live_hindsight_results,
        )
        print(
            json.dumps(
                {
                    "query": args.test,
                    "l2_count": len(l2),
                    "l3_count": len(l3),
                    "live_hindsight_used": live_hindsight_used,
                    "live_hindsight_results": live_hindsight_results,
                    "fused": [
                        {
                            "slug": row["data"].get("slug", ""),
                            "rrf": row["rrf_score"],
                            "sources": row["sources"],
                            "title": row["data"].get("title", ""),
                        }
                        for row in fused[:5]
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    count = generate(recall_queries=args.recall)
    print(f"TIERED_CONTEXT.md updated ({count} lines)")


if __name__ == "__main__":
    main()
