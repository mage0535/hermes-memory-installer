#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import struct
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
import yaml

from knowledge_notes import (
    build_knowledge_note_rows as _build_knowledge_note_rows,
    compute_knowledge_notes_signature as _compute_knowledge_notes_signature,
    parse_knowledge_note as _parse_knowledge_note,
    refresh_knowledge_note_index as _refresh_knowledge_note_index,
    resolve_knowledge_notes_dir as _resolve_knowledge_notes_dir,
)
from state_db_schema import detect_state_schema, sql_expr
from memory_family_registry import (
    active_focus_profiles,
    focus_profile_for_text,
    focus_profile_ids_for_text,
    has_relationship_text,
    is_project_delivery_mode,
    is_provider_config_query,
    is_project_delivery_query,
    is_provider_incident_query,
    is_provider_query,
    is_provider_tooling_query,
    is_system_query_text,
    project_query_mode,
)

AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".agent"))).expanduser()
STATE_DB = Path(os.environ.get("MEMORY_STATE_DB_PATH", str(AGENT_HOME / "state.db"))).expanduser()
GOVERNANCE_DB = Path(os.environ.get("MEMORY_GOVERNANCE_DB_PATH", str(AGENT_HOME / "memory_governance.db"))).expanduser()
KNOWLEDGE_NOTES_DIR = Path(os.environ.get("MEMORY_KNOWLEDGE_NOTES_DIR", str(AGENT_HOME / "knowledge" / "notes"))).expanduser()
DEFAULT_MAX_AGE_SECONDS = 900
HINDSIGHT_BASE_URL = os.environ.get("HINDSIGHT_BASE_URL", "http://127.0.0.1:8890")
HINDSIGHT_BANK = os.environ.get("HINDSIGHT_BANK", "hermes")
HINDSIGHT_LIST_URL = f"{HINDSIGHT_BASE_URL}/v1/default/banks/{HINDSIGHT_BANK}/memories/list"
HINDSIGHT_FETCH_RETRIES = 24
HINDSIGHT_FETCH_RETRY_SLEEP_SECONDS = 5
GOVERNANCE_SQLITE_TIMEOUT_SECONDS = 30
GOVERNANCE_REBUILD_LOCK_RETRIES = 6
LAST_OBJECT_QUERY_STATS = {"raw_rows": 0, "distinct_results": 0, "suppressed_conflict_rows": 0}
EMBEDDING_API_URL = os.environ.get("EMBEDDING_API_URL", "")
EMBEDDING_BATCH_SIZE = int(os.environ.get("EMBEDDING_BATCH_SIZE", "32"))

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
)
SYSTEM_SPECIFIC_MARKERS = (
    "config",
    "provider",
    "gateway",
    "cron",
    "system",
    "restart",
    "model",
    "usage",
    "archive",
    "server",
    "telegram",
    "endpoint",
    "api",
    "key",
)
PROVIDER_GATEWAY_FAMILY_MARKERS = (
    "provider",
    "gateway",
    "config",
    "endpoint",
    "api",
    "key",
    "model",
    "run.py",
    "gateway/run.py",
)
RELATIONSHIP_MARKERS = (
    "朋友",
    "关系",
    "微信",
    "girl",
    "girlfriend",
    "message her",
)
PROJECT_DEPLOY_FAMILY_MARKERS = (
    "github",
    "deploy",
    "script",
    "commit",
    "pushed",
    "push",
    "release",
    "publish",
    "published",
    "documentation",
    "docs",
    "readme",
    "about",
)
PROJECT_DEPLOY_STRONG_MARKERS = (
    "deploy",
    "deployed",
    "commit",
    "pushed",
    "push",
    "publish",
    "published",
    "documentation",
    "docs",
    "readme",
    "about",
)
PROJECT_BROAD_PENALTY_MARKERS = (
    "search for open source",
    "evaluate",
    "评估",
    "summary",
    "conversation transcript",
    "multiple github projects",
)
PROVIDER_GATEWAY_STRONG_MARKERS = (
    "provider",
    "gateway",
    "config",
    "endpoint",
    "api key",
    "base_url",
    "base url",
    "model reverted",
    "模型切换",
)
HERMES_PROVIDER_CONTEXT_MARKERS = (
    "hermes",
    "config.yaml",
    "custom_providers",
    "ao_wrapper.py",
    "opencode-go",
    "opencode",
    "deepseek",
    "qwen",
    "kimi",
    "minimax",
    "glm",
    "zhipu",
    "base_url",
    "base url",
    "127.0.0.1:18888",
    "opencode.ai/zen",
    "gateway/run.py",
    "run.py",
    "api端点",
    "自定义provider",
)
GENERIC_PROVIDER_CONTEXT_PENALTY_MARKERS = (
    "medium",
    "linkedin",
    "twitter",
    "threads",
    "wordpress",
    "discord",
    "ghost",
    "mastodon",
    "discourse",
    "buttondown",
    "hashnode",
    "bluesky",
    "playwright",
    "scrapling",
    "capsolver",
    "cloudflare turnstile",
    "oauth token",
    "registration",
    "publishing",
    "publish",
    "crier",
)
PROVIDER_FOCUS_NOISE_MARKERS = (
    "loaded three relevant skills",
    "relevant skills to investigate",
    "gateway operations and troubleshooting",
    "agent.log-based real-time model tracking",
    "custom provider configuration and",
    "skill to investigate",
)
PROVIDER_NAME_MARKERS = (
    "opencode-zen",
    "opencode-go",
    "deepseek",
    "qwen",
    "alibaba",
    "minimax",
    "kimi",
    "glm",
    "zhipu",
    "zen",
)
PROVIDER_OBJECT_REQUIRED_MARKERS = (
    "provider",
    "config",
    "model",
    "api",
    "key",
    "endpoint",
    "base_url",
    "base url",
    "api端点",
)
PROVIDER_CONFIG_MARKERS = (
    "provider",
    "config",
    "endpoint",
    "api key",
    "base_url",
    "base url",
    "api",
    "key",
    "api端点",
    "自定义provider",
)
PROVIDER_MODEL_STATE_MARKERS = (
    "model",
    "using model",
    "current model",
    "model reverted",
    "switched model",
    "模型切换",
    "当前模型",
    "default model",
)
GATEWAY_RESTART_MARKERS = (
    "gateway",
    "restart",
    "restarted",
    "shutting down",
    "sigterm",
    "interrupted",
    "systemctl restart",
    "关闭警告",
    "重启",
)
PROVIDER_GATEWAY_BROAD_PENALTY_MARKERS = (
    "## summary",
    "what was accomplished",
    "p6-1",
    "semantic search upgrade",
    "planning",
    "记忆召回机制",
    "memory recall",
    "多 agent",
    "data isolation",
    "对话总结",
    "用户核心需求",
)

BASE_MEMORY_HUB_DEFS = {
    "system": {
        "title": "Hermes System Memory",
        "keywords": ["hermes", "gateway", "provider", "config", "systemd", "docker", "api key"],
        "min_hits": 2,
    },
    "coding": {
        "title": "Coding And Tooling Memory",
        "keywords": ["python", "github", "script", "deploy", "tool", "skill", "api"],
        "min_hits": 2,
    },
    "a_stock": {
        "title": "A Stock Memory",
        "keywords": ["a股", "stock", "hs300", "zz500", "lightgbm", "hedge", "因子"],
        "min_hits": 1,
    },
    "social": {
        "title": "Social Media Memory",
        "keywords": ["douyin", "tiktok", "youtube", "微信", "telegram", "内容", "视频"],
        "min_hits": 2,
    },
}


def build_memory_hub_defs() -> dict[str, dict]:
    hub_defs = dict(BASE_MEMORY_HUB_DEFS)
    for profile_id, profile in active_focus_profiles().items():
        hub_defs[profile_id] = {
            "title": profile.get("hub_title") or profile.get("title") or profile_id,
            "keywords": list(profile.get("keywords", ()) or profile.get("aliases", ())),
            "min_hits": 1,
            "entity_type": profile.get("entity_type") or profile.get("kind") or "general",
            "dossier": True,
            "priority": int(profile.get("priority", 50)),
        }
    return hub_defs


MEMORY_HUB_DEFS = build_memory_hub_defs()

AUTO_NOISE_MARKERS = (
    "memory capacity",
    "archiving process",
    "memory_index.db",
    "goal-review/",
    "goal-review",
    "capacity is at",
    "automated cron",
    "master cron",
    "system steward",
    "consolidated_system.py",
    "助手完成归档",
    "内存清理",
)

STRONG_SYSTEM_PATTERNS = (
    "merged from 17 to 5",
    "wrote 1 reply iteration experience",
    "write memory",
    "wrote 1",
    "absorbing hermes updates",
    "automated task merge",
    "archiving process:",
)
LOW_VALUE_OBJECT_PREFIXES = (
    "<think>",
    "thinking.",
)
LOW_VALUE_OBJECT_MARKERS = (
    "analyze the request",
    "goal: create a concise summary",
    "tone: past tense, factual recap",
    "content requirements:",
)


def build_query_terms(query: str) -> list[str]:
    terms = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", query or "")
    if not terms and query and query.strip():
        return [query.strip()]
    return terms


def build_fts_query(query: str) -> str:
    terms = build_query_terms(query)
    safe_terms = []
    for term in terms:
        cleaned = term.replace('"', " ").strip()
        if cleaned:
            safe_terms.append(f'"{cleaned}"')
    return " OR ".join(safe_terms)


def resolve_knowledge_notes_dir() -> Path:
    return _resolve_knowledge_notes_dir(AGENT_HOME, KNOWLEDGE_NOTES_DIR)


def _strip_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not match:
        return {}, text
    raw_meta, body = match.groups()
    try:
        meta = yaml.safe_load(raw_meta) or {}
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
    return meta, body


def _normalize_note_title(path: Path, body: str, meta: dict) -> str:
    title = str(meta.get("title") or "").strip()
    if title:
        return title
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            candidate = stripped.lstrip("#").strip()
            if candidate:
                return candidate
    return path.stem.replace("-", " ").replace("_", " ").strip().title() or path.stem


def _summarize_note_body(body: str) -> str:
    lines = []
    in_code = False
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        lines.append(stripped)
    summary = " ".join(lines)
    summary = re.sub(r"\s+", " ", summary).strip()
    return summary[:1200]


def parse_knowledge_note(path: Path, root_dir: Path) -> dict | None:
    return _parse_knowledge_note(path, root_dir)


def build_knowledge_note_rows(indexed_at: float) -> tuple[list[tuple], list[tuple]]:
    return _build_knowledge_note_rows(resolve_knowledge_notes_dir(), indexed_at)


def compute_knowledge_notes_signature(notes_dir: Path | None = None) -> str:
    return _compute_knowledge_notes_signature(notes_dir or resolve_knowledge_notes_dir())


def _governance_meta_value(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM governance_meta WHERE key = ?", (key,)).fetchone()
    return str(row[0]) if row and row[0] is not None else None


def refresh_knowledge_note_index(conn: sqlite3.Connection, indexed_at: float, force: bool = False) -> dict:
    return _refresh_knowledge_note_index(
        conn,
        notes_dir=resolve_knowledge_notes_dir(),
        indexed_at=indexed_at,
        force=force,
    )


def is_system_query(query: str) -> bool:
    lowered = (query or "").lower()
    if is_system_query_text(query):
        return True
    return any(marker in lowered for marker in ("restart", "model", "usage", "archive", "重启", "模型", "用量", "模型用量", "归档"))


def is_noisy_hindsight_text(query: str, text: str) -> bool:
    if is_system_query(query):
        return False
    lowered = (text or "").lower()
    return any(marker in lowered for marker in AUTO_NOISE_MARKERS) or any(
        marker in lowered for marker in STRONG_SYSTEM_PATTERNS
    )


def direct_query_hit(query: str, *texts: str) -> bool:
    terms = [term.lower() for term in build_query_terms(query) if len(term.strip()) >= 2]
    haystack = " ".join(text or "" for text in texts).lower()
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


def count_marker_hits(markers: tuple[str, ...], *texts: str) -> int:
    haystack = " ".join(texts).lower()
    return sum(1 for marker in markers if marker in haystack)


def is_low_value_object_text(title: str, summary: str) -> bool:
    title_lower = (title or "").strip().lower()
    summary_lower = (summary or "").strip().lower()
    if any(title_lower.startswith(prefix) for prefix in LOW_VALUE_OBJECT_PREFIXES):
        return True
    combined = f"{title_lower} {summary_lower}"
    return any(marker in combined for marker in LOW_VALUE_OBJECT_MARKERS)


def minimum_term_coverage(query: str) -> int:
    terms = {term.lower().strip() for term in build_query_terms(query) if len(term.lower().strip()) >= 2}
    if not terms:
        return 0
    if len(terms) == 1:
        return 1
    return min(2, len(terms))


def hindsight_relevance_score(query: str, row: sqlite3.Row, base_score: float) -> float | None:
    text = row["text"] or row["context"] or ""
    entities = row["entities"] or ""
    lowered = text.lower()
    if is_noisy_hindsight_text(query, text):
        return None
    if not is_system_query(query) and any(marker in lowered for marker in STRONG_SYSTEM_PATTERNS):
        return None
    has_direct_hit = direct_query_hit(query, text, entities)
    if not is_system_query(query) and not has_direct_hit:
        return None
    score = base_score
    if row["fact_type"] == "observation":
        score += 0.05
    elif row["fact_type"] == "world":
        score += 0.03
    if has_direct_hit:
        score += 0.04
    if entities and has_direct_hit:
        score += 0.03
    return round(min(score, 0.94), 4)


def infer_memory_hubs(text: str) -> list[str]:
    lowered = (text or "").lower()
    hits = list(focus_profile_ids_for_text(text or ""))
    for hub_id, hub in MEMORY_HUB_DEFS.items():
        if hub_id in hits:
            continue
        match_count = sum(1 for keyword in hub["keywords"] if keyword.lower() in lowered)
        if match_count >= int(hub.get("min_hits", 1)):
            hits.append(hub_id)
    return hits


def normalize_memory_text(text: str) -> str:
    lowered = (text or "").lower()
    lowered = re.sub(r"\|\s*when:.*$", "", lowered)
    lowered = re.sub(r"\|\s*involving:.*$", "", lowered)
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def build_memory_object_id(normalized_text: str) -> str:
    digest = hashlib.sha1(normalized_text.encode("utf-8")).hexdigest()[:16]
    return f"mem:{digest}"


def extract_named_entities(text: str) -> list[str]:
    entities = []
    lowered = (text or "").lower()
    for hub in MEMORY_HUB_DEFS.values():
        for keyword in hub["keywords"]:
            if keyword.lower() in lowered:
                entities.append(keyword)
    profile_id, profile = focus_profile_for_text(text or "")
    if profile_id and profile:
        entities.extend(profile.get("aliases", ()))
    seen = set()
    ordered = []
    for entity in entities:
        key = entity.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(entity)
    return ordered[:8]


def timestamp_freshness(value) -> float:
    if not value:
        return 0.55
    try:
        ts = float(value)
        age_days = max((time.time() - ts) / 86400.0, 0.0)
        return round(max(0.35, min(0.9, 0.9 - age_days / 120.0)), 4)
    except Exception:
        return 0.55


def infer_entity_type(text: str, hubs: list[str]) -> str:
    lowered = (text or "").lower()
    profile_id, profile = focus_profile_for_text(text or "", " ".join(hubs))
    if profile_id and profile:
        return profile.get("entity_type") or profile.get("kind") or "general"
    if "system" in hubs or any(term in lowered for term in ("provider", "gateway", "config", "systemd", "docker")):
        return "system"
    if "user-profile" in hubs or any(term in lowered for term in ("user", "profile", "preferences")):
        return "person_social"
    if "a_stock" in hubs or any(term in lowered for term in ("a股", "stock", "hs300", "zz500", "因子")):
        return "finance_strategy"
    if "coding" in hubs or any(term in lowered for term in ("github", "deploy", "script", "python", "repo")):
        return "project_technical"
    if "social" in hubs or any(term in lowered for term in ("douyin", "tiktok", "youtube", "telegram", "微信")):
        return "social_content"
    return "general"


def split_memory_segments(text: str) -> list[str]:
    raw_parts = re.split(r"[\n\r]+|(?<=[。！？!?])\s+|(?<=[.;:])\s+", text or "")
    parts = []
    for part in raw_parts:
        cleaned = " ".join(str(part).split()).strip(" -|")
        if cleaned:
            parts.append(cleaned)
    return parts


def build_family_focus_text(text: str, markers: tuple[str, ...], max_parts: int = 3) -> str:
    selected = []
    seen = set()
    for part in split_memory_segments(text):
        lowered = part.lower()
        if not any(marker in lowered for marker in markers):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        selected.append(part)
        if len(selected) >= max_parts:
            break
    return " | ".join(selected)[:900]


def prune_provider_focus_text(text: str) -> str:
    cleaned = []
    for part in split_memory_segments(text):
        lowered = part.lower()
        if any(marker in lowered for marker in PROVIDER_FOCUS_NOISE_MARKERS):
            continue
        cleaned.append(part)
    return " | ".join(cleaned)[:900]


def infer_provider_object_title(text: str) -> str:
    merged = text or ""
    lowered = merged.lower()
    if "base_url" in lowered or "base url" in lowered or "endpoint" in lowered or "api端点" in merged:
        return "Gateway Endpoint Configuration"
    for marker in PROVIDER_NAME_MARKERS:
        if marker in lowered:
            pretty = marker.replace("-", " ")
            return f"Provider Config: {pretty}"[:100]
    patterns = (
        r"([A-Za-z0-9._-]+)\s+provider",
        r"provider[:=]\s*([A-Za-z0-9._-]+)",
        r"model[:=]\s*([A-Za-z0-9._-]+)",
        r"([A-Za-z0-9._-]+)\s+model",
    )
    for pattern in patterns:
        match = re.search(pattern, merged, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip("`'\" ")
            if value:
                return f"Provider Config: {value}"[:100]
    return "Provider And Gateway Configuration"


def infer_provider_object_kind(text: str) -> str | None:
    config_hits = count_marker_hits(PROVIDER_CONFIG_MARKERS, text)
    model_hits = count_marker_hits(PROVIDER_MODEL_STATE_MARKERS, text)
    restart_hits = count_marker_hits(GATEWAY_RESTART_MARKERS, text)
    provider_name_hits = count_marker_hits(PROVIDER_NAME_MARKERS, text)
    hermes_context_hits = count_marker_hits(HERMES_PROVIDER_CONTEXT_MARKERS, text)
    generic_penalty_hits = count_marker_hits(GENERIC_PROVIDER_CONTEXT_PENALTY_MARKERS, text)
    if generic_penalty_hits > 0 and provider_name_hits == 0 and hermes_context_hits < 2:
        return None
    if model_hits >= 2 and (provider_name_hits > 0 or hermes_context_hits >= 1) and config_hits <= 1:
        return "provider_model_state"
    if config_hits >= 2 and (provider_name_hits > 0 or hermes_context_hits >= 2):
        return "provider_config"
    if provider_name_hits > 0 and config_hits >= 1:
        return "provider_config"
    if model_hits >= 1 and (provider_name_hits > 0 or hermes_context_hits >= 2 or config_hits >= 1 or model_hits >= 2):
        return "provider_model_state"
    if restart_hits >= 2 and (config_hits >= 1 or model_hits >= 1 or provider_name_hits > 0 or hermes_context_hits >= 2):
        return "gateway_restart"
    return None


def infer_provider_subtype_title(kind: str, text: str) -> str:
    base = infer_provider_object_title(text)
    if kind == "provider_model_state":
        return base.replace("Provider Config", "Provider Model State")
    if kind == "gateway_restart":
        if base.startswith("Provider Config:"):
            return base.replace("Provider Config", "Gateway Restart")
        return "Gateway Restart Context"
    return base


def add_specialized_provider_object(
    objects: dict[str, dict],
    merged: str,
    source_ref: str,
    freshness: float,
    last_seen_at: str,
    base_confidence: float,
) -> None:
    if not merged:
        return
    if not has_any_marker(PROVIDER_GATEWAY_FAMILY_MARKERS, merged):
        return
    if has_relationship_text(merged):
        return
    focus_text = build_family_focus_text(merged, PROVIDER_GATEWAY_FAMILY_MARKERS, max_parts=3)
    focus_text = prune_provider_focus_text(focus_text)
    if len(focus_text) < 32:
        return
    strong_hits = count_marker_hits(PROVIDER_GATEWAY_STRONG_MARKERS, focus_text)
    required_hits = count_marker_hits(PROVIDER_OBJECT_REQUIRED_MARKERS, focus_text)
    provider_name_hits = count_marker_hits(PROVIDER_NAME_MARKERS, focus_text)
    hermes_context_hits = count_marker_hits(HERMES_PROVIDER_CONTEXT_MARKERS, focus_text)
    generic_penalty_hits = count_marker_hits(GENERIC_PROVIDER_CONTEXT_PENALTY_MARKERS, focus_text)
    if strong_hits == 0:
        return
    if generic_penalty_hits > 0 and provider_name_hits == 0 and hermes_context_hits < 2:
        return
    if required_hits < 2 and provider_name_hits == 0 and hermes_context_hits < 2:
        return
    kind = infer_provider_object_kind(focus_text)
    if not kind:
        return
    title = infer_provider_subtype_title(kind, focus_text or merged)
    if title == "Provider And Gateway Configuration" and provider_name_hits == 0 and (required_hits < 3 or hermes_context_hits < 2):
        return
    if title == "Gateway Endpoint Configuration" and hermes_context_hits < 2:
        return
    normalized = normalize_memory_text(f"{kind} {title} {focus_text}")
    if not normalized:
        return
    object_id = build_memory_object_id(normalized)
    hubs = ["system"]
    entities = set(extract_named_entities(focus_text or merged))
    bucket = objects.setdefault(
        object_id,
        {
            "object_type": kind,
            "entity_type": "system",
            "title": title,
            "summary_parts": [],
            "entities": set(),
            "hub_ids": set(),
            "source_refs": set(),
            "status": "active",
            "confidence": base_confidence,
            "freshness": freshness,
            "last_seen_at": last_seen_at or "",
        },
    )
    bucket["summary_parts"].append(focus_text[:320])
    bucket["entities"].update(entity for entity in entities if entity)
    bucket["hub_ids"].update(hubs)
    bucket["source_refs"].add(source_ref)
    bucket["confidence"] = max(bucket["confidence"], base_confidence)
    bucket["freshness"] = max(bucket["freshness"], freshness)
    if last_seen_at:
        bucket["last_seen_at"] = max(bucket["last_seen_at"], str(last_seen_at))


def infer_source_kind(source_refs: set[str]) -> str:
    has_session = any(ref.startswith("session:") for ref in source_refs)
    has_hindsight = any(ref and not ref.startswith("session:") for ref in source_refs)
    if has_session and has_hindsight:
        return "mixed"
    if has_session:
        return "session"
    if has_hindsight:
        return "hindsight"
    return "unknown"


def build_version_tag(last_seen_at: str, freshness: float) -> str:
    if freshness >= 0.82:
        return "current"
    if last_seen_at:
        try:
            if re.fullmatch(r"\d+(\.\d+)?", str(last_seen_at)):
                return time.strftime("%Y-%m", time.localtime(float(last_seen_at)))
            return str(last_seen_at)[:7]
        except (ValueError, OSError):
            pass
    return "undated"


def build_conflict_group(title: str, entity_type: str) -> str:
    normalized = normalize_memory_text(title)
    normalized = re.sub(r"\[[^\]]+\]", "", normalized)
    normalized = re.sub(r"\b\d{8}_\d{6}_[a-z0-9]+\b", "", normalized)
    normalized = re.sub(r"\b[a-f0-9]{6,}\b", "", normalized)
    normalized = re.sub(r"\b20\d{2}\b", "", normalized)
    normalized = re.sub(r"\b\d{1,2}\b", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    base = normalized[:40] or entity_type
    return f"{entity_type}:{base}"


def object_row_priority(row) -> tuple:
    version_tag = str(row["version_tag"] or "")
    freshness = float(row["freshness"] or 0.0)
    confidence = float(row["confidence"] or 0.0)
    source_kind = str(row["source_kind"] or "")
    current_boost = 1 if version_tag == "current" else 0
    mixed_boost = 1 if source_kind == "mixed" else 0
    return (current_boost, freshness, confidence, mixed_boost, str(row["last_seen_at"] or ""))


def object_query_sort_key(query: str, row) -> tuple:
    combined = " ".join(
        [
            str(row["title"] or ""),
            str(row["summary"] or ""),
            str(row["entities"] or ""),
            str(row["hub_ids"] or ""),
        ]
    )
    title_hits = count_query_term_hits(query, str(row["title"] or ""))
    combined_hits = count_query_term_hits(query, combined)
    exact_title = 1 if direct_query_hit(query, str(row["title"] or "")) else 0
    exact_combined = 1 if direct_query_hit(query, combined) else 0
    provider_family_query = is_provider_query(query)
    deploy_family_query = is_project_delivery_mode(query)
    provider_family_hits = count_marker_hits(PROVIDER_GATEWAY_FAMILY_MARKERS, combined) if provider_family_query else 0
    provider_strong_hits = count_marker_hits(PROVIDER_GATEWAY_STRONG_MARKERS, combined) if provider_family_query else 0
    provider_broad_penalty = count_marker_hits(PROVIDER_GATEWAY_BROAD_PENALTY_MARKERS, combined) if provider_family_query else 0
    deploy_family_hits = count_marker_hits(PROJECT_DEPLOY_FAMILY_MARKERS, combined) if deploy_family_query else 0
    deploy_strong_hits = count_marker_hits(PROJECT_DEPLOY_STRONG_MARKERS, combined) if deploy_family_query else 0
    deploy_broad_penalty = count_marker_hits(PROJECT_BROAD_PENALTY_MARKERS, combined) if deploy_family_query else 0
    relationship_penalty = -1 if provider_family_query and has_relationship_text(combined) else 0
    provider_object_type = str(row["object_type"] or "")
    provider_object_boost = 0
    if provider_family_query:
        provider_object_boost = {
            "provider_config": 3,
            "provider_model_state": 2,
            "system_provider": 1,
            "gateway_restart": 0,
        }.get(provider_object_type, 0)
    return (
        provider_object_boost,
        provider_strong_hits,
        provider_family_hits,
        -provider_broad_penalty,
        deploy_strong_hits,
        deploy_family_hits,
        -deploy_broad_penalty,
        combined_hits,
        title_hits,
        exact_title,
        exact_combined,
        relationship_penalty,
        *object_row_priority(row),
    )


def provider_family_row_strength(row) -> tuple[int, int, int, int]:
    combined = " ".join(
        [
            str(row["title"] or ""),
            str(row["summary"] or ""),
            str(row["entities"] or ""),
            str(row["hub_ids"] or ""),
        ]
    )
    return (
        count_marker_hits(PROVIDER_GATEWAY_STRONG_MARKERS, combined),
        count_marker_hits(PROVIDER_GATEWAY_FAMILY_MARKERS, combined),
        count_marker_hits(PROVIDER_GATEWAY_BROAD_PENALTY_MARKERS, combined),
        1 if has_relationship_text(combined) else 0,
    )


def is_broad_provider_family_row(row) -> bool:
    title = str(row["title"] or "")
    combined = " ".join(
        [
            title,
            str(row["summary"] or ""),
            str(row["entities"] or ""),
            str(row["hub_ids"] or ""),
        ]
    ).lower()
    return (
        title == "Provider And Gateway Configuration"
        or "provider and gateway configuration" in combined
    )


def has_narrow_provider_family_evidence(row) -> bool:
    title = str(row["title"] or "")
    combined = " ".join(
        [
            title,
            str(row["summary"] or ""),
            str(row["entities"] or ""),
            str(row["hub_ids"] or ""),
        ]
    ).lower()
    return (
        title == "Gateway Endpoint Configuration"
        or title.startswith("Provider Config:")
        or title.startswith("Provider Model State:")
        or count_marker_hits(PROVIDER_NAME_MARKERS, combined) > 0
        or "endpoint" in combined
        or "base_url" in combined
        or "base url" in combined
    )


def is_provider_cache_row_allowed(query: str, text: str, context: str) -> bool:
    combined = f"{text or ''} {context or ''}".lower()
    provider_family_query = is_provider_query(query)
    if not provider_family_query or is_provider_incident_query(query):
        return True
    provider_config_hits = any(
        marker in combined
        for marker in (
            "provider",
            "config.yaml",
            "api key",
            "base url",
            "base_url",
            "endpoint",
            "/zen/",
            "model ",
        )
    )
    provider_identity_hits = any(
        marker in combined
        for marker in (
            "hermes",
            "gateway",
            "opencode",
            "opencode-go",
            "opencode zen",
            "zen",
            "kimi",
            "qwen",
            "deepseek",
            "openai",
            "claude",
            "provider config",
            "default model provider",
            "current ai model",
        )
    )
    payment_gateway_hits = any(
        marker in combined
        for marker in (
            "payment gateway",
            "bank account",
            "tax id",
            "monetization",
            "merchant",
            "billing",
            "checkout",
            "payment provider",
            "payout",
        )
    )
    provider_tooling_hits = any(
        marker in combined
        for marker in (
            "ao_wrapper.py",
            "injects them as environment variables",
            "dynamic model following",
            "replaces ao compose/run",
            "before calling ao",
            "reads the current model",
            "environment variables before calling ao",
        )
    )
    restart_only_hits = any(
        marker in combined
        for marker in (
            "gateway restart",
            "gateway has restarted",
            "interrupted due to gateway restart",
            "shutting down",
            "shutdown",
            "restart completed",
            "gateway restarted",
        )
    )
    if payment_gateway_hits and not (provider_config_hits or provider_identity_hits):
        return False
    if provider_tooling_hits and not is_provider_tooling_query(query):
        return False
    if restart_only_hits and not provider_config_hits:
        return False
    if provider_identity_hits and not payment_gateway_hits:
        return True
    if not provider_config_hits and not provider_identity_hits:
        return False
    return not payment_gateway_hits


def is_provider_model_query(query: str) -> bool:
    lowered = query.lower()
    return "model" in lowered or "模型" in lowered


def is_provider_incident_row(row) -> bool:
    combined = " ".join(
        [
            str(row["title"] or ""),
            str(row["summary"] or ""),
            str(row["entities"] or ""),
            str(row["hub_ids"] or ""),
        ]
    ).lower()
    return any(
        marker in combined
        for marker in (
            "fallback chain",
            "gateway restart request",
            "error switching model",
            "persistence fix",
            "quota exhausted",
            "quota is exhausted",
            "model reverted",
            "reverted from",
        )
    )


def is_historical_provider_config_row(row) -> bool:
    title = str(row["title"] or "")
    if not title.startswith("Provider Config:"):
        return False
    combined = " ".join(
        [
            title,
            str(row["summary"] or ""),
            str(row["entities"] or ""),
            str(row["hub_ids"] or ""),
        ]
    ).lower()
    return any(
        marker in combined
        for marker in (
            "fallback chain",
            "quota exhausted",
            "openssl certificate",
            "gateway restart request",
            "remove three model providers",
            "residual",
            "residue",
            "aliases",
            "openrouter",
            "github-copilot",
            "copilot",
        )
    )


def is_broad_deploy_family_row(row) -> bool:
    title = str(row["title"] or "")
    combined = " ".join(
        [
            title,
            str(row["summary"] or ""),
            str(row["entities"] or ""),
            str(row["hub_ids"] or ""),
        ]
    ).lower()
    return (
        count_marker_hits(PROJECT_BROAD_PENALTY_MARKERS, combined) > 0
        or title.startswith("We need to create a concise summary")
        or "conversation transcript" in combined
        or "evaluate two github projects" in combined
        or "search for open source automation tools" in combined
        or "alternative methods" in combined
        or "try to access these platforms" in combined
        or "tls fingerprint" in combined
        or "fingerprint bypass" in combined
        or "curl_cffi" in combined
        or "registration endpoint" in combined
    )


def has_narrow_deploy_family_evidence(row) -> bool:
    title = str(row["title"] or "")
    combined = " ".join(
        [
            title,
            str(row["summary"] or ""),
            str(row["entities"] or ""),
            str(row["hub_ids"] or ""),
        ]
    ).lower()
    return (
        count_marker_hits(PROJECT_DEPLOY_STRONG_MARKERS, combined) >= 2
        or title.startswith("Hermes Agent updated project documentation")
        or "changes pushed with commit" in combined
        or "updated github about" in combined
        or "readme" in combined
        or "documentation" in combined
    )


def choose_distinct_object_rows(rows) -> list:
    best_by_group = {}
    ordered_groups = []
    for row in rows:
        key = str(row["conflict_group"] or row["object_id"])
        existing = best_by_group.get(key)
        if existing is None:
            best_by_group[key] = row
            ordered_groups.append(key)
            continue
        if object_row_priority(row) > object_row_priority(existing):
            best_by_group[key] = row
    distinct = [best_by_group[key] for key in ordered_groups]
    distinct.sort(key=object_row_priority, reverse=True)
    return distinct


def object_candidate_allowed(query: str, row) -> bool:
    combined = " ".join(
        [
            str(row["title"] or ""),
            str(row["summary"] or ""),
            str(row["entities"] or ""),
            str(row["hub_ids"] or ""),
        ]
    )
    entity_type = str(row["entity_type"] or "")
    required_terms = minimum_term_coverage(query)
    covered_terms = count_query_term_hits(query, combined)
    deploy_family_query = is_project_delivery_mode(query)
    if is_system_query(query):
        provider_family_query = has_any_marker(("provider", "gateway", "config"), query)
        if has_relationship_text(combined) and not has_any_marker(SYSTEM_SPECIFIC_MARKERS, combined):
            return False
        if provider_family_query and has_relationship_text(combined):
            provider_like_hits = count_marker_hits(PROVIDER_GATEWAY_FAMILY_MARKERS, combined)
            provider_strong_hits = count_marker_hits(PROVIDER_GATEWAY_STRONG_MARKERS, combined)
            if provider_like_hits < 2 or provider_strong_hits == 0:
                return False
        if required_terms >= 2 and covered_terms < required_terms:
            return False
    elif deploy_family_query:
        if entity_type == "person_relationship":
            return False
        if has_relationship_text(combined):
            return False
        if required_terms >= 2 and covered_terms < required_terms:
            return False
    elif required_terms >= 2 and covered_terms < required_terms:
        return False
    return True


def fetch_hindsight_memories(batch_size: int = 200) -> list[dict]:
    items = []
    offset = 0
    while True:
        payload = None
        last_error = None
        for attempt in range(HINDSIGHT_FETCH_RETRIES):
            try:
                with urllib.request.urlopen(
                    f"{HINDSIGHT_LIST_URL}?limit={batch_size}&offset={offset}",
                    timeout=20,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.URLError as exc:
                last_error = exc
                if attempt >= HINDSIGHT_FETCH_RETRIES - 1:
                    raise
                time.sleep(HINDSIGHT_FETCH_RETRY_SLEEP_SECONDS)
        if payload is None:
            raise last_error or RuntimeError("failed to fetch hindsight memories")
        chunk = payload.get("items", [])
        if not chunk:
            break
        items.extend(chunk)
        offset += len(chunk)
        if len(chunk) < batch_size:
            break
    return items


def ensure_table_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def recreate_memory_objects_fts_if_needed(conn: sqlite3.Connection) -> None:
    expected = {"object_id", "object_type", "entity_type", "title", "summary", "entities", "hub_ids", "search_text"}
    existing = {row[1] for row in conn.execute("PRAGMA table_info(memory_objects_fts)").fetchall()}
    if existing and expected.issubset(existing):
        return
    conn.execute("DROP TABLE IF EXISTS memory_objects_fts")
    conn.execute(
        """
        CREATE VIRTUAL TABLE memory_objects_fts USING fts5(
            object_id UNINDEXED,
            object_type UNINDEXED,
            entity_type UNINDEXED,
            title,
            summary,
            entities,
            hub_ids,
            search_text,
            tokenize='unicode61'
        )
        """
    )


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS governance_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS repair_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at REAL NOT NULL,
            finished_at REAL,
            mode TEXT NOT NULL,
            notes TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orphan_messages (
            message_id INTEGER PRIMARY KEY,
            original_session_id TEXT,
            timestamp REAL,
            role TEXT,
            content_hash TEXT,
            content_preview TEXT,
            detected_at REAL NOT NULL,
            repair_status TEXT NOT NULL DEFAULT 'pending',
            repair_run_id INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_repair_map (
            message_id INTEGER PRIMARY KEY,
            repaired_session_id TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.5,
            strategy TEXT NOT NULL,
            evidence_json TEXT,
            repair_run_id INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_lineage_repair (
            child_session_id TEXT PRIMARY KEY,
            original_parent_session_id TEXT,
            repaired_parent_session_id TEXT,
            confidence REAL NOT NULL DEFAULT 0.5,
            strategy TEXT NOT NULL,
            evidence_json TEXT,
            repair_run_id INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recovered_fragments (
            fragment_id TEXT PRIMARY KEY,
            source_message_ids TEXT NOT NULL,
            inferred_topic TEXT,
            inferred_time_range TEXT,
            summary TEXT,
            archive_slug TEXT,
            created_at REAL NOT NULL,
            repair_run_id INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_aliases (
            alias TEXT PRIMARY KEY,
            memory_id TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_memory_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            to_memory_id TEXT NOT NULL,
            weight REAL NOT NULL DEFAULT 1.0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_index (
            session_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT,
            summary TEXT,
            first_user TEXT,
            last_assistant TEXT,
            started_at REAL,
            ended_at REAL,
            message_count INTEGER NOT NULL DEFAULT 0,
            end_reason TEXT,
            is_recovered INTEGER NOT NULL DEFAULT 0,
            search_text TEXT NOT NULL,
            indexed_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recovered_sessions (
            session_id TEXT PRIMARY KEY,
            message_count INTEGER NOT NULL,
            started_at REAL,
            ended_at REAL,
            title TEXT,
            summary TEXT,
            indexed_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hindsight_index (
            memory_id TEXT PRIMARY KEY,
            fact_type TEXT NOT NULL,
            text TEXT NOT NULL,
            context TEXT,
            entities TEXT,
            tags TEXT,
            source_session_id TEXT,
            mentioned_at TEXT,
            occurred_start TEXT,
            occurred_end TEXT,
            search_text TEXT NOT NULL,
            indexed_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_hubs (
            hub_id TEXT PRIMARY KEY,
            hub_type TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            entities TEXT,
            source_count INTEGER NOT NULL DEFAULT 0,
            last_seen_at TEXT,
            search_text TEXT NOT NULL,
            indexed_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_objects (
            object_id TEXT PRIMARY KEY,
            object_type TEXT NOT NULL,
            entity_type TEXT,
            source_kind TEXT,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            entities TEXT,
            hub_ids TEXT,
            source_refs TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.5,
            freshness REAL NOT NULL DEFAULT 0.5,
            valid_from TEXT,
            valid_to TEXT,
            version_tag TEXT,
            conflict_group TEXT,
            last_seen_at TEXT,
            search_text TEXT NOT NULL,
            indexed_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_note_index (
            note_id TEXT PRIMARY KEY,
            source_path TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            tags TEXT,
            search_text TEXT NOT NULL,
            indexed_at REAL NOT NULL,
            modified_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS session_index_fts USING fts5(
            session_id UNINDEXED,
            source UNINDEXED,
            title,
            summary,
            first_user,
            last_assistant,
            search_text,
            end_reason UNINDEXED,
            message_count UNINDEXED,
            started_at UNINDEXED,
            ended_at UNINDEXED,
            is_recovered UNINDEXED,
            tokenize='unicode61'
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS hindsight_index_fts USING fts5(
            memory_id UNINDEXED,
            fact_type UNINDEXED,
            text,
            context,
            entities,
            tags,
            source_session_id UNINDEXED,
            mentioned_at UNINDEXED,
            search_text,
            tokenize='unicode61'
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_hubs_fts USING fts5(
            hub_id UNINDEXED,
            hub_type UNINDEXED,
            title,
            summary,
            entities,
            search_text,
            tokenize='unicode61'
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_note_index_fts USING fts5(
            note_id UNINDEXED,
            source_path UNINDEXED,
            title,
            summary,
            tags,
            search_text,
            tokenize='unicode61'
        )
        """
    )
    recreate_memory_objects_fts_if_needed(conn)
    ensure_table_column(conn, "memory_objects", "entity_type", "TEXT")
    ensure_table_column(conn, "memory_objects", "source_kind", "TEXT")
    ensure_table_column(conn, "memory_objects", "version_tag", "TEXT")
    ensure_table_column(conn, "memory_objects", "conflict_group", "TEXT")
    ensure_table_column(conn, "memory_objects", "valid_from", "TEXT")
    ensure_table_column(conn, "memory_objects", "valid_to", "TEXT")

    conn.execute("DROP VIEW IF EXISTS sessions_effective")
    conn.execute(
        """
        CREATE VIEW sessions_effective AS
        SELECT
            si.*,
            COALESCE(slr.repaired_parent_session_id, '') AS effective_parent_session_id
        FROM session_index si
        LEFT JOIN session_lineage_repair slr ON slr.child_session_id = si.session_id
        """
    )
    conn.execute("DROP VIEW IF EXISTS repaired_message_summary")
    conn.execute(
        """
        CREATE VIEW repaired_message_summary AS
        SELECT
            COALESCE(srm.repaired_session_id, 'orphan') AS effective_session_id,
            COUNT(*) AS repaired_count,
            ROUND(AVG(srm.confidence), 4) AS avg_confidence
        FROM session_repair_map srm
        GROUP BY effective_session_id
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS canonical_semantic_index (
            memory_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL DEFAULT 0,
            chunk_text TEXT NOT NULL,
            embedding BLOB NOT NULL,
            indexed_at REAL NOT NULL,
            PRIMARY KEY (memory_id, chunk_index)
        )
    """
    )


def _needs_rebuild(max_age_seconds: int) -> bool:
    if not STATE_DB.exists() or not GOVERNANCE_DB.exists():
        return True
    if GOVERNANCE_DB.stat().st_mtime < STATE_DB.stat().st_mtime:
        return True
    if time.time() - GOVERNANCE_DB.stat().st_mtime > max_age_seconds:
        return True
    return False


def build_hub_rows(session_rows: list[dict], hindsight_items: list[dict], indexed_at: float) -> tuple[list[tuple], list[tuple]]:
    buckets: dict[str, dict] = defaultdict(
        lambda: {"snippets": [], "entities": set(), "sources": set(), "last_seen_at": ""}
    )
    for row in session_rows:
        snippet = " ".join(part for part in [row["title"], row["summary"], row["first_user"]] if part).strip()
        hubs = infer_memory_hubs(snippet)
        if not hubs:
            continue
        entities = extract_named_entities(snippet)
        for hub_id in hubs:
            bucket = buckets[hub_id]
            if snippet:
                bucket["snippets"].append(snippet[:280])
            bucket["entities"].update(entities)
            bucket["sources"].add(row["session_id"])
            bucket["last_seen_at"] = str(row["ended_at"] or row["started_at"] or "")
    for item in hindsight_items:
        text = item.get("text") or ""
        context = item.get("context") or ""
        merged = " ".join(part for part in [text, context] if part).strip()
        hubs = infer_memory_hubs(merged)
        if not hubs:
            continue
        entity_values = item.get("entities") or []
        if not isinstance(entity_values, list):
            entity_values = [str(entity_values)]
        entities = set(entity_values) | set(extract_named_entities(merged))
        for hub_id in hubs:
            bucket = buckets[hub_id]
            if merged:
                bucket["snippets"].append(merged[:280])
            bucket["entities"].update(entities)
            bucket["sources"].add(item.get("id", ""))
            bucket["last_seen_at"] = item.get("mentioned_at") or bucket["last_seen_at"]
    hub_rows = []
    hub_fts_rows = []
    for hub_id, bucket in buckets.items():
        snippets = []
        seen_snippets = set()
        for snippet in bucket["snippets"]:
            key = snippet.lower()
            if key in seen_snippets:
                continue
            seen_snippets.add(key)
            snippets.append(snippet)
            if len(snippets) >= 6:
                break
        entity_text = ", ".join(sorted(entity for entity in bucket["entities"] if entity))
        title = MEMORY_HUB_DEFS.get(hub_id, {}).get("title", hub_id.replace("_", " ").title())
        summary = " | ".join(snippets)[:1600]
        search_text = " ".join(
            part for part in [hub_id, title, summary, entity_text, " ".join(MEMORY_HUB_DEFS.get(hub_id, {}).get("keywords", []))] if part
        )
        hub_rows.append(
            (
                hub_id,
                "topic",
                title,
                summary,
                entity_text,
                len(bucket["sources"]),
                bucket["last_seen_at"],
                search_text,
                indexed_at,
            )
        )
        hub_fts_rows.append((hub_id, "topic", title, summary, entity_text, search_text))
    return hub_rows, hub_fts_rows


def build_memory_object_rows(session_rows: list[dict], hindsight_items: list[dict], indexed_at: float) -> tuple[list[tuple], list[tuple]]:
    objects: dict[str, dict] = {}
    for item in hindsight_items:
        text = item.get("text") or ""
        context = item.get("context") or ""
        entity_values = item.get("entities") or []
        if not isinstance(entity_values, list):
            entity_values = [str(entity_values)]
        merged = " ".join(part for part in [text, context] if part).strip()
        normalized = normalize_memory_text(merged or text)
        if not normalized:
            continue
        object_id = build_memory_object_id(normalized)
        hubs = infer_memory_hubs(" ".join([merged, " ".join(entity_values)]))
        object_type = hubs[0] if hubs else (item.get("fact_type") or "memory")
        entities = set(entity_values) | set(extract_named_entities(merged))
        source_refs = [item.get("id", "")]
        if item.get("tags"):
            source_refs.extend(tag for tag in item.get("tags", []) if isinstance(tag, str) and tag.startswith("session:"))
        bucket = objects.setdefault(
            object_id,
            {
                "object_type": object_type,
                "entity_type": infer_entity_type(merged or text, hubs),
                "title": (text or context or normalized)[:100],
                "summary_parts": [],
                "entities": set(),
                "hub_ids": set(),
                "source_refs": set(),
                "status": "active",
                "confidence": 0.72,
                "freshness": 0.60,
                "valid_from": item.get("mentioned_at") or "",
                "valid_to": "",
                "last_seen_at": item.get("mentioned_at") or "",
            },
        )
        if merged:
            bucket["summary_parts"].append(merged[:240])
        bucket["entities"].update(entity for entity in entities if entity)
        bucket["hub_ids"].update(hubs)
        bucket["source_refs"].update(ref for ref in source_refs if ref)
        if item.get("fact_type") == "observation":
            bucket["confidence"] = max(bucket["confidence"], 0.82)
        elif item.get("fact_type") == "world":
            bucket["confidence"] = max(bucket["confidence"], 0.78)
        bucket["freshness"] = max(bucket["freshness"], 0.72 if item.get("mentioned_at") else 0.60)
        if item.get("mentioned_at"):
            bucket["last_seen_at"] = max(bucket["last_seen_at"], item.get("mentioned_at") or "")
            if bucket.get("valid_from"):
                bucket["valid_from"] = min(bucket["valid_from"], item.get("mentioned_at") or "")
            else:
                bucket["valid_from"] = item.get("mentioned_at") or ""
        add_specialized_provider_object(
            objects,
            merged,
            item.get("id", ""),
            bucket["freshness"],
            str(item.get("mentioned_at") or ""),
            0.84 if item.get("fact_type") == "observation" else 0.80,
        )

    for row in session_rows:
        source = (row.get("source") or "").lower()
        session_id = row.get("session_id") or ""
        if source == "cron" or session_id.startswith("cron_"):
            continue
        merged = " ".join(
            part
            for part in [
                row.get("title", ""),
                row.get("summary", ""),
                row.get("first_user", ""),
            ]
            if part
        ).strip()
        if len(merged) < 36:
            continue
        hubs = infer_memory_hubs(merged)
        if not hubs and len(row.get("summary", "") or "") < 48:
            continue
        normalized = normalize_memory_text(merged)
        if not normalized:
            continue
        object_id = build_memory_object_id(normalized)
        entities = set(extract_named_entities(merged))
        bucket = objects.setdefault(
            object_id,
            {
                "object_type": hubs[0] if hubs else "session_memory",
                "entity_type": infer_entity_type(merged, hubs),
                "title": (row.get("title") or row.get("summary") or normalized)[:100],
                "summary_parts": [],
                "entities": set(),
                "hub_ids": set(),
                "source_refs": set(),
                "status": "active",
                "confidence": 0.64,
                "freshness": timestamp_freshness(row.get("ended_at") or row.get("started_at")),
                "valid_from": str(row.get("started_at") or ""),
                "valid_to": "",
                "last_seen_at": str(row.get("ended_at") or row.get("started_at") or ""),
            },
        )
        bucket["summary_parts"].append(merged[:240])
        bucket["entities"].update(entity for entity in entities if entity)
        bucket["hub_ids"].update(hubs)
        bucket["source_refs"].add(f"session:{session_id}")
        bucket["confidence"] = max(bucket["confidence"], 0.66 if hubs else 0.62)
        bucket["freshness"] = max(bucket["freshness"], timestamp_freshness(row.get("ended_at") or row.get("started_at")))
        if row.get("ended_at") or row.get("started_at"):
            bucket["last_seen_at"] = max(bucket["last_seen_at"], str(row.get("ended_at") or row.get("started_at") or ""))
            session_valid_from = str(row.get("started_at") or row.get("ended_at") or "")
            if bucket.get("valid_from") and session_valid_from:
                bucket["valid_from"] = min(bucket["valid_from"], session_valid_from)
            elif session_valid_from:
                bucket["valid_from"] = session_valid_from
        add_specialized_provider_object(
            objects,
            merged,
            f"session:{session_id}",
            timestamp_freshness(row.get("ended_at") or row.get("started_at")),
            str(row.get("ended_at") or row.get("started_at") or ""),
            0.80,
        )

    object_rows = []
    object_fts_rows = []
    for object_id, bucket in objects.items():
        summary_parts = []
        seen = set()
        for part in bucket["summary_parts"]:
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            summary_parts.append(part)
            if len(summary_parts) >= 4:
                break
        summary = " | ".join(summary_parts)[:1600]
        entities_text = ", ".join(sorted(bucket["entities"]))
        hub_ids_text = ", ".join(sorted(bucket["hub_ids"]))
        source_kind = infer_source_kind(bucket["source_refs"])
        version_tag = build_version_tag(str(bucket["last_seen_at"] or ""), float(bucket["freshness"] or 0.5))
        conflict_group = build_conflict_group(bucket["title"], bucket["entity_type"])
        search_text = " ".join(
            part
            for part in [
                object_id,
                bucket["title"],
                summary,
                entities_text,
                hub_ids_text,
                bucket["object_type"],
                bucket["entity_type"],
                source_kind,
                version_tag,
                conflict_group,
            ]
            if part
        )
        source_refs_json = json.dumps(sorted(bucket["source_refs"]), ensure_ascii=False)
        row = (
            object_id,
            bucket["object_type"],
            bucket["entity_type"],
            source_kind,
            bucket["title"],
            summary,
            entities_text,
            hub_ids_text,
            source_refs_json,
            bucket["status"],
            round(bucket["confidence"], 4),
            round(bucket["freshness"], 4),
            bucket.get("valid_from", ""),
            bucket.get("valid_to", ""),
            version_tag,
            conflict_group,
            bucket["last_seen_at"],
            search_text,
            indexed_at,
        )
        object_rows.append(row)
        object_fts_rows.append(
            (
                object_id,
                bucket["object_type"],
                bucket["entity_type"],
                bucket["title"],
                summary,
                entities_text,
                hub_ids_text,
                search_text,
            )
        )
    # --- multi-version status: mark best per conflict_group active, rest superseded ---
    conflict_groups: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(object_rows):
        conflict_groups[row[15] or row[0]].append(i)
    mutable = [list(row) for row in object_rows]
    for _cg, indices in conflict_groups.items():
        if len(indices) < 2:
            continue
        sorted_indices = sorted(
            indices,
            key=lambda i: (
                1 if mutable[i][14] == "current" else 0,
                mutable[i][11],
                mutable[i][10],
                1 if mutable[i][3] == "mixed" else 0,
                mutable[i][16] or "",
            ),
            reverse=True,
        )
        best_idx = sorted_indices[0]
        best_valid_from = mutable[best_idx][12]
        for idx in sorted_indices[1:]:
            mutable[idx][9] = "superseded"
            if best_valid_from:
                mutable[idx][13] = best_valid_from
    object_rows = [tuple(row) for row in mutable]
    return object_rows, object_fts_rows


def rebuild_index(force: bool = False, max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS) -> dict:
    if not STATE_DB.exists():
        raise FileNotFoundError(f"state.db not found: {STATE_DB}")
    if not force and not _needs_rebuild(max_age_seconds):
        return {"rebuilt": False, "reason": "fresh", "path": str(GOVERNANCE_DB)}

    started = time.time()
    state = sqlite3.connect(str(STATE_DB), timeout=GOVERNANCE_SQLITE_TIMEOUT_SECONDS)
    state.row_factory = sqlite3.Row
    gov = sqlite3.connect(str(GOVERNANCE_DB), timeout=GOVERNANCE_SQLITE_TIMEOUT_SECONDS)
    gov.row_factory = sqlite3.Row
    gov.execute(f"PRAGMA busy_timeout={int(GOVERNANCE_SQLITE_TIMEOUT_SECONDS * 1000)}")
    ensure_schema(gov)
    gov.execute(
        "INSERT INTO repair_runs (started_at, mode, notes) VALUES (?, ?, ?)",
        (started, "rebuild", "session/hindsight/hub governance rebuild"),
    )
    run_id = gov.execute("SELECT last_insert_rowid()").fetchone()[0]
    schema = detect_state_schema(state)

    rows = state.execute(
        f"""
        SELECT
            s.id,
            COALESCE({sql_expr(schema.session_source, "'unknown'", table_alias="s.")}, 'unknown') AS source,
            COALESCE({sql_expr(schema.session_title, "''", table_alias="s.")}, '') AS title,
            COALESCE({sql_expr(schema.session_summary, "''", table_alias="s.")}, '') AS summary,
            {sql_expr(schema.session_started_at, "0", "started_at", "s.")},
            {sql_expr(schema.session_ended_at, "0", "ended_at", "s.")},
            COALESCE({sql_expr(schema.session_message_count, "0", table_alias="s.")}, 0) AS message_count,
            COALESCE({sql_expr(schema.session_end_reason, "''", table_alias="s.")}, '') AS end_reason,
            COALESCE(
                (
                    SELECT {sql_expr(schema.message_content, "''")}
                    FROM messages
                    WHERE session_id = s.id
                      AND {sql_expr(schema.message_role, "'user'")} = 'user'
                      AND {sql_expr(schema.message_content, "NULL")} IS NOT NULL
                      AND trim({sql_expr(schema.message_content, "''")}) <> ''
                    ORDER BY {sql_expr(schema.message_timestamp, "0")}, id
                    LIMIT 1
                ),
                ''
            ) AS first_user,
            COALESCE(
                (
                    SELECT {sql_expr(schema.message_content, "''")}
                    FROM messages
                    WHERE session_id = s.id
                      AND {sql_expr(schema.message_role, "'assistant'")} = 'assistant'
                      AND {sql_expr(schema.message_content, "NULL")} IS NOT NULL
                      AND trim({sql_expr(schema.message_content, "''")}) <> ''
                    ORDER BY {sql_expr(schema.message_timestamp, "0")} DESC, id DESC
                    LIMIT 1
                ),
                ''
            ) AS last_assistant
        FROM sessions s
        ORDER BY {sql_expr(schema.session_started_at, "0", table_alias="s.")} DESC
        """
    ).fetchall()

    now = time.time()
    gov.execute("DELETE FROM session_index")
    gov.execute("DELETE FROM recovered_sessions")
    gov.execute("DELETE FROM session_index_fts")
    gov.execute("DELETE FROM hindsight_index")
    gov.execute("DELETE FROM hindsight_index_fts")
    gov.execute("DELETE FROM memory_hubs")
    gov.execute("DELETE FROM memory_hubs_fts")
    gov.execute("DELETE FROM memory_objects")
    gov.execute("DELETE FROM memory_objects_fts")
    session_rows = []
    session_fts_rows = []
    recovered_rows = []
    session_dict_rows = []
    for row in rows:
        session_id = row["id"]
        title = row["title"]
        summary = row["summary"]
        first_user = row["first_user"]
        last_assistant = row["last_assistant"]
        end_reason = row["end_reason"]
        is_recovered = 1 if end_reason == "recovered-orphan-session" else 0
        search_text = " ".join(
            part.strip()
            for part in [session_id, title, summary, first_user, last_assistant]
            if part and part.strip()
        )
        session_rows.append(
            (
                session_id,
                row["source"] or "unknown",
                title,
                summary,
                first_user,
                last_assistant,
                row["started_at"],
                row["ended_at"],
                row["message_count"],
                end_reason,
                is_recovered,
                search_text,
                now,
            )
        )
        session_fts_rows.append(
            (
                session_id,
                row["source"] or "unknown",
                title,
                summary,
                first_user,
                last_assistant,
                search_text,
                end_reason,
                str(row["message_count"] or 0),
                str(row["started_at"] or ""),
                str(row["ended_at"] or ""),
                str(is_recovered),
            )
        )
        session_dict_rows.append(
            {
                "session_id": session_id,
                "source": row["source"] or "unknown",
                "title": title,
                "summary": summary,
                "first_user": first_user,
                "last_assistant": last_assistant,
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
            }
        )
        if is_recovered:
            recovered_rows.append(
                (
                    session_id,
                    row["message_count"],
                    row["started_at"],
                    row["ended_at"],
                    title,
                    summary,
                    now,
                )
            )

    gov.executemany(
        """
        INSERT INTO session_index (
            session_id, source, title, summary, first_user, last_assistant,
            started_at, ended_at, message_count, end_reason, is_recovered,
            search_text, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        session_rows,
    )
    gov.executemany(
        """
        INSERT INTO session_index_fts (
            session_id, source, title, summary, first_user, last_assistant,
            search_text, end_reason, message_count, started_at, ended_at, is_recovered
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        session_fts_rows,
    )
    gov.executemany(
        """
        INSERT INTO recovered_sessions (
            session_id, message_count, started_at, ended_at, title, summary, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        recovered_rows,
    )

    hindsight_items = fetch_hindsight_memories()
    hindsight_items_total = len(hindsight_items)
    hindsight_rows_by_id = {}
    hindsight_fts_rows_by_id = {}
    for item in hindsight_items:
        memory_id = item.get("id")
        if not memory_id:
            continue
        tags = item.get("tags") or []
        tag_text = " ".join(tags) if isinstance(tags, list) else str(tags or "")
        entities = item.get("entities") or []
        entity_text = " ".join(entities) if isinstance(entities, list) else str(entities or "")
        source_session_id = ""
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag.startswith("session:"):
                    source_session_id = tag.split("session:", 1)[1]
                    break
        text = item.get("text") or ""
        context = item.get("context") or ""
        search_text = " ".join(
            part.strip()
            for part in [text, context, entity_text, tag_text, item.get("fact_type") or "", source_session_id]
            if part and part.strip()
        )
        hindsight_rows_by_id[memory_id] = (
            memory_id,
            item.get("fact_type") or "unknown",
            text,
            context,
            entity_text,
            tag_text,
            source_session_id,
            item.get("mentioned_at") or "",
            item.get("occurred_start") or "",
            item.get("occurred_end") or "",
            search_text,
            now,
        )
        hindsight_fts_rows_by_id[memory_id] = (
            memory_id,
            item.get("fact_type") or "unknown",
            text,
            context,
            entity_text,
            tag_text,
            source_session_id,
            item.get("mentioned_at") or "",
            search_text,
        )
    hindsight_rows = list(hindsight_rows_by_id.values())
    hindsight_fts_rows = list(hindsight_fts_rows_by_id.values())
    hindsight_duplicate_count = max(hindsight_items_total - len(hindsight_rows), 0)

    gov.executemany(
        """
        INSERT INTO hindsight_index (
            memory_id, fact_type, text, context, entities, tags,
            source_session_id, mentioned_at, occurred_start, occurred_end,
            search_text, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        hindsight_rows,
    )
    gov.executemany(
        """
        INSERT INTO hindsight_index_fts (
            memory_id, fact_type, text, context, entities, tags,
            source_session_id, mentioned_at, search_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        hindsight_fts_rows,
    )

    hub_rows, hub_fts_rows = build_hub_rows(session_dict_rows, hindsight_items, now)
    object_rows, object_fts_rows = build_memory_object_rows(session_dict_rows, hindsight_items, now)
    knowledge_index_stats = refresh_knowledge_note_index(gov, indexed_at=now, force=force)
    gov.executemany(
        """
        INSERT INTO memory_hubs (
            hub_id, hub_type, title, summary, entities, source_count,
            last_seen_at, search_text, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        hub_rows,
    )
    gov.executemany(
        """
        INSERT INTO memory_hubs_fts (
            hub_id, hub_type, title, summary, entities, search_text
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        hub_fts_rows,
    )
    gov.executemany(
        """
        INSERT INTO memory_objects (
            object_id, object_type, entity_type, source_kind, title, summary, entities, hub_ids,
            source_refs, status, confidence, freshness, valid_from, valid_to, version_tag, conflict_group, last_seen_at,
            search_text, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        object_rows,
    )
    gov.executemany(
        """
        INSERT INTO memory_objects_fts (
            object_id, object_type, entity_type, title, summary, entities, hub_ids, search_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        object_fts_rows,
    )
    embed_canonical_objects(gov, object_rows)
    gov.execute(
        """
        INSERT INTO governance_meta (key, value) VALUES ('last_rebuild_at', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(now),),
    )
    gov.execute(
        """
        INSERT INTO governance_meta (key, value) VALUES ('state_db_mtime', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(STATE_DB.stat().st_mtime),),
    )
    gov.execute(
        """
        INSERT INTO governance_meta (key, value) VALUES ('hindsight_synced_at', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(now),),
    )
    gov.execute(
        """
        INSERT INTO governance_meta (key, value) VALUES ('hindsight_items_total', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(hindsight_items_total),),
    )
    gov.execute(
        """
        INSERT INTO governance_meta (key, value) VALUES ('hindsight_duplicate_count', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(hindsight_duplicate_count),),
    )
    gov.execute(
        """
        INSERT INTO governance_meta (key, value) VALUES ('knowledge_notes_total', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(knowledge_index_stats["count"]),),
    )
    gov.execute("UPDATE repair_runs SET finished_at = ? WHERE id = ?", (time.time(), run_id))
    gov.commit()
    state.close()
    gov.close()
    return {
        "rebuilt": True,
        "path": str(GOVERNANCE_DB),
        "sessions_indexed": len(session_rows),
        "recovered_sessions": len(recovered_rows),
        "hindsight_items_total": hindsight_items_total,
        "hindsight_memories": len(hindsight_rows),
        "hindsight_duplicate_count": hindsight_duplicate_count,
        "memory_hubs": len(hub_rows),
        "memory_objects": len(object_rows),
        "knowledge_notes": int(knowledge_index_stats["count"]),
        "knowledge_notes_reused": bool(knowledge_index_stats["reused"]),
    }


def ensure_governance_db(force: bool = False, max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS) -> dict:
    last_lock_exc = None
    for attempt in range(GOVERNANCE_REBUILD_LOCK_RETRIES):
        try:
            return rebuild_index(force=force, max_age_seconds=max_age_seconds)
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            last_lock_exc = exc
            time.sleep(0.5 * (attempt + 1))
    if not force and GOVERNANCE_DB.exists():
        return {"rebuilt": False, "reason": "locked", "path": str(GOVERNANCE_DB)}
    raise last_lock_exc or RuntimeError("governance rebuild failed")


def query_governance_sessions(query: str, top: int = 5) -> list[dict]:
    ensure_governance_db(force=False, max_age_seconds=DEFAULT_MAX_AGE_SECONDS)
    if not GOVERNANCE_DB.exists():
        return []
    conn = sqlite3.connect(str(GOVERNANCE_DB))
    conn.row_factory = sqlite3.Row
    seen = set()
    results = []
    terms = build_query_terms(query)
    allow_cron = any(term.lower() == "cron" for term in terms)
    try:
        fts_query = build_fts_query(query)
        if fts_query:
            rows = conn.execute(
                """
                SELECT
                    session_id, source, title, summary, first_user, last_assistant,
                    end_reason, message_count, started_at, ended_at, is_recovered,
                    bm25(session_index_fts) AS rank
                FROM session_index_fts
                WHERE session_index_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, top * 3),
            ).fetchall()
            for row in rows:
                sid = row["session_id"]
                if not allow_cron and (row["source"] or "") == "cron":
                    continue
                if sid in seen:
                    continue
                seen.add(sid)
                snippet = row["summary"] or row["first_user"] or row["last_assistant"] or row["title"] or sid
                score = 0.72 + (0.10 if int(row["is_recovered"] or 0) else 0.0)
                if query and query.lower() in (row["title"] or "").lower():
                    score += 0.08
                results.append(
                    {
                        "session_id": sid,
                        "title": row["title"] or sid,
                        "snippet": snippet[:180],
                        "source": row["source"],
                        "layer": "governance",
                        "score": round(min(score, 0.92), 4),
                    }
                )
                if len(results) >= top:
                    break
        if len(results) < top:
            like_pat = f"%{query.strip()}%"
            rows = conn.execute(
                """
                SELECT session_id, source, title, summary, first_user, last_assistant
                FROM session_index
                WHERE title LIKE ? OR summary LIKE ? OR first_user LIKE ? OR search_text LIKE ?
                ORDER BY ended_at DESC
                LIMIT ?
                """,
                (like_pat, like_pat, like_pat, like_pat, top * 3),
            ).fetchall()
            for row in rows:
                sid = row["session_id"]
                if not allow_cron and (row["source"] or "") == "cron":
                    continue
                if sid in seen:
                    continue
                seen.add(sid)
                snippet = row["summary"] or row["first_user"] or row["last_assistant"] or row["title"] or sid
                results.append(
                    {
                        "session_id": sid,
                        "title": row["title"] or sid,
                        "snippet": snippet[:180],
                        "source": row["source"],
                        "layer": "governance_like",
                        "score": 0.62,
                    }
                )
                if len(results) >= top:
                    break
    finally:
        conn.close()
    return results[:top]


def query_governance_hindsight(query: str, top: int = 5) -> list[dict]:
    ensure_governance_db(force=False, max_age_seconds=DEFAULT_MAX_AGE_SECONDS)
    if not GOVERNANCE_DB.exists():
        return []
    conn = sqlite3.connect(str(GOVERNANCE_DB))
    conn.row_factory = sqlite3.Row
    results = []
    seen = set()
    try:
        fts_query = build_fts_query(query)
        if fts_query:
            rows = conn.execute(
                """
                SELECT
                    memory_id, fact_type, text, context, entities, tags,
                    source_session_id, mentioned_at, bm25(hindsight_index_fts) AS rank
                FROM hindsight_index_fts
                WHERE hindsight_index_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, top * 3),
            ).fetchall()
            for row in rows:
                memory_id = row["memory_id"]
                if memory_id in seen:
                    continue
                if not is_provider_cache_row_allowed(query, row["text"], row["context"]):
                    continue
                score = hindsight_relevance_score(query, row, 0.80)
                if score is None:
                    continue
                seen.add(memory_id)
                results.append(
                    {
                        "memory_id": memory_id,
                        "session_id": f"hindsight:{memory_id}",
                        "title": (row["text"] or memory_id)[:80],
                        "snippet": (row["text"] or row["context"] or "")[:180],
                        "source": "hindsight_cache",
                        "layer": "hindsight_cache",
                        "score": score,
                    }
                )
                if len(results) >= top:
                    break
        if len(results) < top:
            like_pat = f"%{query.strip()}%"
            rows = conn.execute(
                """
                SELECT memory_id, fact_type, text, context, entities, tags, source_session_id, mentioned_at
                FROM hindsight_index
                WHERE text LIKE ? OR context LIKE ? OR entities LIKE ? OR search_text LIKE ?
                ORDER BY mentioned_at DESC
                LIMIT ?
                """,
                (like_pat, like_pat, like_pat, like_pat, top * 3),
            ).fetchall()
            for row in rows:
                memory_id = row["memory_id"]
                if memory_id in seen:
                    continue
                if not is_provider_cache_row_allowed(query, row["text"], row["context"]):
                    continue
                score = hindsight_relevance_score(query, row, 0.72)
                if score is None:
                    continue
                seen.add(memory_id)
                results.append(
                    {
                        "memory_id": memory_id,
                        "session_id": f"hindsight:{memory_id}",
                        "title": (row["text"] or memory_id)[:80],
                        "snippet": (row["text"] or row["context"] or "")[:180],
                        "source": "hindsight_cache",
                        "layer": "hindsight_cache",
                        "score": score,
                    }
                )
                if len(results) >= top:
                    break
    finally:
        conn.close()
    return results[:top]


def query_governance_hubs(query: str, top: int = 5) -> list[dict]:
    ensure_governance_db(force=False, max_age_seconds=DEFAULT_MAX_AGE_SECONDS)
    if not GOVERNANCE_DB.exists():
        return []
    conn = sqlite3.connect(str(GOVERNANCE_DB))
    conn.row_factory = sqlite3.Row
    results = []
    seen = set()
    try:
        fts_query = build_fts_query(query)
        if fts_query:
            rows = conn.execute(
                """
                SELECT
                    f.hub_id,
                    h.hub_type,
                    h.title,
                    h.summary,
                    h.entities,
                    h.source_count,
                    h.last_seen_at,
                    bm25(memory_hubs_fts) AS rank
                FROM memory_hubs_fts f
                JOIN memory_hubs h ON h.hub_id = f.hub_id
                WHERE memory_hubs_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, top * 3),
            ).fetchall()
            for row in rows:
                hub_id = row["hub_id"]
                if hub_id in seen:
                    continue
                if not direct_query_hit(query, row["title"]) and not direct_query_hit(
                    query, " ".join(MEMORY_HUB_DEFS.get(hub_id, {}).get("keywords", []))
                ):
                    continue
                seen.add(hub_id)
                score = 0.86
                if direct_query_hit(query, row["summary"], row["entities"] or ""):
                    score += 0.04
                results.append(
                    {
                        "hub_id": hub_id,
                        "session_id": f"hub:{hub_id}",
                        "title": row["title"],
                        "snippet": row["summary"][:220],
                        "source": "governance_hub",
                        "layer": "hub",
                        "score": round(min(score, 0.95), 4),
                    }
                )
                if len(results) >= top:
                    break
        if len(results) < top:
            like_pat = f"%{query.strip()}%"
            rows = conn.execute(
                """
                SELECT hub_id, hub_type, title, summary, entities, source_count, last_seen_at
                FROM memory_hubs
                WHERE title LIKE ? OR summary LIKE ? OR entities LIKE ? OR search_text LIKE ?
                ORDER BY source_count DESC, last_seen_at DESC
                LIMIT ?
                """,
                (like_pat, like_pat, like_pat, like_pat, top * 3),
            ).fetchall()
            for row in rows:
                hub_id = row["hub_id"]
                if hub_id in seen:
                    continue
                if not direct_query_hit(query, row["title"]) and not direct_query_hit(
                    query, " ".join(MEMORY_HUB_DEFS.get(hub_id, {}).get("keywords", []))
                ):
                    continue
                seen.add(hub_id)
                results.append(
                    {
                        "hub_id": hub_id,
                        "session_id": f"hub:{hub_id}",
                        "title": row["title"],
                        "snippet": row["summary"][:220],
                        "source": "governance_hub",
                        "layer": "hub",
                        "score": 0.78,
                    }
                )
                if len(results) >= top:
                    break
    finally:
        conn.close()
    return results[:top]


def query_governance_knowledge(query: str, top: int = 5) -> list[dict]:
    ensure_governance_db(force=False, max_age_seconds=DEFAULT_MAX_AGE_SECONDS)
    if not GOVERNANCE_DB.exists():
        return []
    conn = sqlite3.connect(str(GOVERNANCE_DB))
    conn.row_factory = sqlite3.Row
    results = []
    seen = set()
    try:
        fts_query = build_fts_query(query)
        if fts_query:
            rows = conn.execute(
                """
                SELECT
                    f.note_id,
                    n.source_path,
                    n.title,
                    n.summary,
                    n.tags,
                    n.modified_at,
                    bm25(knowledge_note_index_fts) AS rank
                FROM knowledge_note_index_fts f
                JOIN knowledge_note_index n ON n.note_id = f.note_id
                WHERE knowledge_note_index_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, top * 3),
            ).fetchall()
            for row in rows:
                note_id = row["note_id"]
                if note_id in seen:
                    continue
                if not direct_query_hit(query, row["title"], row["summary"], row["tags"] or "", row["source_path"]):
                    continue
                seen.add(note_id)
                score = 0.77
                if direct_query_hit(query, row["summary"], row["tags"] or ""):
                    score += 0.05
                results.append(
                    {
                        "note_id": note_id,
                        "session_id": note_id,
                        "title": row["title"],
                        "snippet": row["summary"][:220],
                        "source": f"knowledge:{row['source_path']}",
                        "layer": "knowledge",
                        "score": round(min(score, 0.92), 4),
                    }
                )
                if len(results) >= top:
                    break
        if len(results) < top:
            like_pat = f"%{query.strip()}%"
            rows = conn.execute(
                """
                SELECT note_id, source_path, title, summary, tags, modified_at
                FROM knowledge_note_index
                WHERE title LIKE ? OR summary LIKE ? OR tags LIKE ? OR source_path LIKE ? OR search_text LIKE ?
                ORDER BY modified_at DESC
                LIMIT ?
                """,
                (like_pat, like_pat, like_pat, like_pat, like_pat, top * 3),
            ).fetchall()
            for row in rows:
                note_id = row["note_id"]
                if note_id in seen:
                    continue
                if not direct_query_hit(query, row["title"], row["summary"], row["tags"] or "", row["source_path"]):
                    continue
                seen.add(note_id)
                results.append(
                    {
                        "note_id": note_id,
                        "session_id": note_id,
                        "title": row["title"],
                        "snippet": row["summary"][:220],
                        "source": f"knowledge:{row['source_path']}",
                        "layer": "knowledge",
                        "score": 0.71,
                    }
                )
                if len(results) >= top:
                    break
    finally:
        conn.close()
    return results[:top]


def query_governance_objects(query: str, top: int = 5) -> list[dict]:
    global LAST_OBJECT_QUERY_STATS
    ensure_governance_db(force=False, max_age_seconds=DEFAULT_MAX_AGE_SECONDS)
    if not GOVERNANCE_DB.exists():
        LAST_OBJECT_QUERY_STATS = {"raw_rows": 0, "distinct_results": 0, "suppressed_conflict_rows": 0}
        return []
    conn = sqlite3.connect(str(GOVERNANCE_DB))
    conn.row_factory = sqlite3.Row
    rows_pool = []
    provider_family_query = is_provider_query(query)
    deploy_family_query = is_project_delivery_mode(query)
    system_family_query = is_system_query_text(query)
    try:
        fts_query = build_fts_query(query)
        if fts_query:
            rows = conn.execute(
                """
                SELECT
                    f.object_id,
                    o.object_type,
                    o.entity_type,
                    o.source_kind,
                    o.title,
                    o.summary,
                    o.entities,
                    o.hub_ids,
                    o.status,
                    o.confidence,
                    o.freshness,
                    o.version_tag,
                    o.conflict_group,
                    o.last_seen_at,
                    bm25(memory_objects_fts) AS rank
                FROM memory_objects_fts f
                JOIN memory_objects o ON o.object_id = f.object_id
                WHERE memory_objects_fts MATCH ?
                  AND o.status = 'active'
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, top * 3),
            ).fetchall()
            for row in rows:
                if is_low_value_object_text(str(row["title"] or ""), str(row["summary"] or "")):
                    continue
                if is_noisy_hindsight_text(query, f"{row['title']} {row['summary']}"):
                    continue
                if not object_candidate_allowed(query, row):
                    continue
                rows_pool.append(row)
        if len(rows_pool) < top:
            like_pat = f"%{query.strip()}%"
            rows = conn.execute(
                """
                SELECT object_id, object_type, entity_type, source_kind, title, summary, entities, hub_ids, status, confidence, freshness, version_tag, conflict_group, last_seen_at
                FROM memory_objects
                WHERE status = 'active' AND (
                    title LIKE ? OR summary LIKE ? OR entities LIKE ? OR hub_ids LIKE ? OR search_text LIKE ?
                )
                ORDER BY confidence DESC, freshness DESC, last_seen_at DESC
                LIMIT ?
                """,
                (like_pat, like_pat, like_pat, like_pat, like_pat, top * 3),
            ).fetchall()
            for row in rows:
                if is_low_value_object_text(str(row["title"] or ""), str(row["summary"] or "")):
                    continue
                if is_noisy_hindsight_text(query, f"{row['title']} {row['summary']}"):
                    continue
                if not object_candidate_allowed(query, row):
                    continue
                rows_pool.append(row)
        if provider_family_query:
            like_pat = f"%{query.strip()}%"
            rows = conn.execute(
                """
                SELECT object_id, object_type, entity_type, source_kind, title, summary, entities, hub_ids, status, confidence, freshness, version_tag, conflict_group, last_seen_at
                FROM memory_objects
                WHERE status = 'active'
                  AND object_type IN ('provider_config', 'provider_model_state', 'gateway_restart', 'system_provider')
                  AND (title LIKE ? OR summary LIKE ? OR search_text LIKE ?)
                ORDER BY confidence DESC, freshness DESC, last_seen_at DESC
                LIMIT ?
                """,
                (like_pat, like_pat, like_pat, top * 4),
            ).fetchall()
            for row in rows:
                if is_low_value_object_text(str(row["title"] or ""), str(row["summary"] or "")):
                    continue
                if is_noisy_hindsight_text(query, f"{row['title']} {row['summary']}"):
                    continue
                if not object_candidate_allowed(query, row):
                    continue
                rows_pool.append(row)
        if system_family_query:
            system_terms = [query.strip()]
            system_expansions = [
                "model", "usage", "provider", "gateway", "quota", "endpoint", "api key", "base url",
                "模型", "用量", "配置", "网关",
            ]
            for term in system_expansions:
                if term not in system_terms:
                    system_terms.append(term)
            for term in system_terms:
                like_pat = f"%{term}%"
                rows = conn.execute(
                    """
                    SELECT object_id, object_type, entity_type, source_kind, title, summary, entities, hub_ids, status, confidence, freshness, version_tag, conflict_group, last_seen_at
                    FROM memory_objects
                    WHERE status = 'active'
                      AND object_type IN ('provider_config', 'provider_model_state', 'gateway_restart', 'system_provider')
                      AND (title LIKE ? OR summary LIKE ? OR search_text LIKE ?)
                    ORDER BY confidence DESC, freshness DESC, last_seen_at DESC
                    LIMIT ?
                    """,
                    (like_pat, like_pat, like_pat, top * 4),
                ).fetchall()
                for row in rows:
                    if is_low_value_object_text(str(row["title"] or ""), str(row["summary"] or "")):
                        continue
                    if is_noisy_hindsight_text(query, f"{row['title']} {row['summary']}"):
                        continue
                    if not object_candidate_allowed(query, row):
                        continue
                    rows_pool.append(row)
    finally:
        conn.close()
    distinct_rows = choose_distinct_object_rows(rows_pool)
    distinct_rows.sort(key=lambda row: object_query_sort_key(query, row), reverse=True)
    if provider_family_query:
        narrow_rows = []
        fallback_rows = []
        for row in distinct_rows:
            strong_hits, family_hits, broad_penalty_hits, relationship_hits = provider_family_row_strength(row)
            if (
                str(row["object_type"] or "") in {"provider_config", "provider_model_state"}
                and strong_hits >= 2
                and family_hits >= 3
                and broad_penalty_hits == 0
                and relationship_hits == 0
            ):
                narrow_rows.append(row)
            else:
                fallback_rows.append(row)
        if narrow_rows:
            distinct_rows = narrow_rows + fallback_rows
        if any(has_narrow_provider_family_evidence(row) for row in distinct_rows):
            distinct_rows = [
                row
                for row in distinct_rows
                if not (
                    is_broad_provider_family_row(row)
                    and not has_narrow_provider_family_evidence(row)
                )
            ]
        has_current_endpoint_or_config = any(
            str(row["title"] or "") == "Gateway Endpoint Configuration"
            or str(row["title"] or "").startswith("Provider Config:")
            for row in distinct_rows
        )
        if has_current_endpoint_or_config and not is_provider_incident_query(query):
            if not is_provider_model_query(query):
                distinct_rows = [
                    row
                    for row in distinct_rows
                    if str(row["object_type"] or "") in {"provider_config", "system_provider"}
                ]
                distinct_rows = [
                    row
                    for row in distinct_rows
                    if str(row["object_type"] or "") != "provider_model_state"
                ]
                distinct_rows = [
                    row
                    for row in distinct_rows
                    if not is_historical_provider_config_row(row)
                ]
            distinct_rows = [
                row
                for row in distinct_rows
                if not (
                    str(row["object_type"] or "") == "provider_model_state"
                    and is_provider_incident_row(row)
                )
            ]
    if deploy_family_query and any(has_narrow_deploy_family_evidence(row) for row in distinct_rows):
        distinct_rows = [
            row
            for row in distinct_rows
            if not (
                is_broad_deploy_family_row(row)
                and not has_narrow_deploy_family_evidence(row)
            )
        ]
    LAST_OBJECT_QUERY_STATS = {
        "raw_rows": len(rows_pool),
        "distinct_results": len(distinct_rows),
        "suppressed_conflict_rows": max(len(rows_pool) - len(distinct_rows), 0),
    }
    results = []
    used_fts = bool(build_fts_query(query))
    for row in distinct_rows[:top]:
        base = 0.74 if used_fts else 0.68
        confidence_weight = 0.15 if used_fts else 0.12
        freshness_weight = 0.08 if used_fts else 0.04
        score = min(base + float(row["confidence"] or 0.5) * confidence_weight + float(row["freshness"] or 0.5) * freshness_weight, 0.94)
        if str(row["version_tag"] or "") == "current":
            score += 0.01
        if str(row["source_kind"] or "") == "mixed":
            score += 0.01
        results.append(
            {
                "object_id": row["object_id"],
                "session_id": f"object:{row['object_id']}",
                "object_type": row["object_type"],
                "entity_type": row["entity_type"],
                "source_kind": row["source_kind"],
                "version_tag": row["version_tag"],
                "conflict_group": row["conflict_group"],
                "title": row["title"],
                "snippet": (row["summary"] or "")[:220],
                "source": "governance_object",
                "layer": "object",
                "score": round(min(score, 0.95), 4),
            }
        )
    return results[:top]


def _pack_embedding(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack_embedding(blob: bytes) -> bytes | list[float]:
    step = struct.calcsize("f")
    if len(blob) % step != 0:
        return blob
    return list(struct.unpack(f"{len(blob) // step}f", blob))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _semantic_text_coverage(query: str, *parts: str) -> int:
    terms = build_query_terms(query)
    if not terms:
        return 0
    haystack = " ".join(str(part or "") for part in parts).lower()
    return sum(1 for term in terms if term.lower() in haystack)


def _prefilter_semantic_rows(conn: sqlite3.Connection, query: str, top: int) -> list[sqlite3.Row]:
    terms = build_query_terms(query)
    limit = max(top * 8, 24)
    base_sql = """
        SELECT csi.memory_id, csi.chunk_text, csi.embedding,
               o.object_type, o.entity_type, o.title, o.summary,
               o.confidence, o.freshness, o.version_tag, o.last_seen_at
        FROM canonical_semantic_index csi
        JOIN memory_objects o ON o.object_id = csi.memory_id
        WHERE o.status = 'active'
    """
    fts_query = build_fts_query(query)
    if fts_query:
        rows = conn.execute(
            """
            SELECT csi.memory_id, csi.chunk_text, csi.embedding,
                   o.object_type, o.entity_type, o.title, o.summary,
                   o.confidence, o.freshness, o.version_tag, o.last_seen_at
            FROM memory_objects_fts f
            JOIN memory_objects o ON o.object_id = f.object_id
            JOIN canonical_semantic_index csi ON csi.memory_id = o.object_id
            WHERE memory_objects_fts MATCH ?
              AND o.status = 'active'
            ORDER BY bm25(memory_objects_fts)
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()
        if rows:
            return rows
    if not terms:
        return conn.execute(base_sql + " LIMIT ?", (limit,)).fetchall()

    like_clauses = []
    params: list[str | int] = []
    for term in terms:
        pattern = f"%{term}%"
        like_clauses.append("(o.title LIKE ? OR o.summary LIKE ? OR csi.chunk_text LIKE ?)")
        params.extend([pattern, pattern, pattern])
    sql = base_sql + " AND (" + " OR ".join(like_clauses) + ") LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    if rows:
        return rows
    return conn.execute(base_sql + " LIMIT ?", (limit,)).fetchall()


def _get_embedding(text: str) -> list[float] | None:
    vectors = _get_embeddings([text])
    if not vectors:
        return None
    return vectors[0]


def _get_embeddings(texts: list[str]) -> list[list[float]] | None:
    if not EMBEDDING_API_URL:
        return None
    normalized = [str(text or "") for text in texts]
    if not normalized:
        return []
    payload = json.dumps({"input": normalized}).encode("utf-8")
    req = urllib.request.Request(
        EMBEDDING_API_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        embeddings = body.get("embeddings") or body.get("data") or []
        if embeddings and isinstance(embeddings[0], list):
            return [[float(v) for v in row] for row in embeddings]
        if embeddings and isinstance(embeddings[0], dict):
            return [[float(v) for v in row.get("embedding", [])] for row in embeddings]
        return None
    except Exception as exc:
        print(f"[governance_rebuild] embedding API call failed: {exc}", file=sys.stderr)
        return None


def replace_canonical_semantic_index(conn: sqlite3.Connection, object_rows: list[tuple]) -> bool:
    if not EMBEDDING_API_URL or not object_rows:
        return False
    active_rows = [
        (row[0], f"{row[4] or ''} {row[5] or ''}"[:1200])
        for row in object_rows
        if row[9] == "active"
    ]
    if not active_rows:
        return False
    now = time.time()
    values: list[tuple[str, int, str, bytes, float]] = []
    expected_dimension = None
    for start in range(0, len(active_rows), max(1, EMBEDDING_BATCH_SIZE)):
        batch = active_rows[start:start + max(1, EMBEDDING_BATCH_SIZE)]
        chunk_texts = [chunk_text.strip() or mem_id for mem_id, chunk_text in batch]
        vectors = _get_embeddings(chunk_texts)
        if not vectors or len(vectors) != len(batch):
            return False
        for vec in vectors:
            if not vec:
                return False
            if expected_dimension is None:
                expected_dimension = len(vec)
            elif len(vec) != expected_dimension:
                return False
        for (mem_id, _chunk_text), chunk_text, vec in zip(batch, chunk_texts, vectors):
            values.append((mem_id, 0, chunk_text, _pack_embedding(vec), now))
    conn.execute("DELETE FROM canonical_semantic_index")
    conn.executemany(
        "INSERT INTO canonical_semantic_index (memory_id, chunk_index, chunk_text, embedding, indexed_at) VALUES (?, ?, ?, ?, ?)",
        values,
    )
    return True


def embed_canonical_objects(conn: sqlite3.Connection, object_rows: list[tuple]) -> bool:
    return replace_canonical_semantic_index(conn, object_rows)


def query_canonical_semantic(query: str, top: int = 5) -> list[dict]:
    if not EMBEDDING_API_URL:
        return []
    gov_path = GOVERNANCE_DB
    if not gov_path.exists():
        return []
    query_vec = _get_embedding(query)
    if query_vec is None:
        return []
    conn = sqlite3.connect(str(gov_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = _prefilter_semantic_rows(conn, query, top)
    finally:
        conn.close()
    max_coverage = max(
        (_semantic_text_coverage(query, row["title"], row["summary"], row["chunk_text"]) for row in rows),
        default=0,
    )
    if max_coverage > 0:
        rows = [
            row for row in rows
            if _semantic_text_coverage(query, row["title"], row["summary"], row["chunk_text"]) == max_coverage
        ]
    scored = []
    for row in rows:
        emb = _unpack_embedding(row["embedding"])
        if not isinstance(emb, list) or len(emb) != len(query_vec):
            continue
        sim = _cosine_similarity(query_vec, emb)
        scored.append(
            {
                "memory_id": row["memory_id"],
                "session_id": f"semantic:{row['memory_id']}",
                "title": row["title"] or row["memory_id"],
                "snippet": row["chunk_text"][:220],
                "object_type": row["object_type"],
                "entity_type": row["entity_type"],
                "source": "governance_semantic",
                "layer": "semantic",
                "score": round(min(0.45 + 0.40 * sim, 0.92), 4),
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top]


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild and query Hermes memory governance index")
    parser.add_argument("--force", action="store_true", help="Force a full rebuild")
    parser.add_argument("--query", help="Run a governance query after rebuild")
    parser.add_argument("--top", type=int, default=5, help="Result count for --query")
    parser.add_argument("--quiet", action="store_true", help="Suppress rebuild stats")
    parser.add_argument("--mode", choices=["sessions", "hindsight", "hubs", "objects", "all"], default="sessions")
    args = parser.parse_args()

    stats = ensure_governance_db(force=args.force)
    if not args.quiet:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    if args.query:
        if args.mode == "sessions":
            payload = query_governance_sessions(args.query, top=args.top)
        elif args.mode == "hindsight":
            payload = query_governance_hindsight(args.query, top=args.top)
        elif args.mode == "hubs":
            payload = query_governance_hubs(args.query, top=args.top)
        elif args.mode == "objects":
            payload = query_governance_objects(args.query, top=args.top)
        else:
            payload = {
                "sessions": query_governance_sessions(args.query, top=args.top),
                "hindsight": query_governance_hindsight(args.query, top=args.top),
                "hubs": query_governance_hubs(args.query, top=args.top),
                "objects": query_governance_objects(args.query, top=args.top),
            }
        print(json.dumps({"query": args.query, "mode": args.mode, "results": payload}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
