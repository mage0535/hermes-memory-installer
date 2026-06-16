#!/usr/bin/env python3
from __future__ import annotations

PROVIDER_QUERY_MARKERS = (
    "provider",
    "gateway",
    "config",
)

PROVIDER_INCIDENT_QUERY_MARKERS = (
    "restart",
    "switch",
    "error",
    "fallback",
    "revert",
    "quota",
    "interrupted",
    "shutdown",
)

PROVIDER_TOOLING_QUERY_MARKERS = (
    "wrapper",
    "tool",
    "script",
    "env",
    "environment",
    "dynamic",
    "follow",
    "ao",
)

PROJECT_QUERY_MARKERS = (
    "project",
    "repo",
    "github",
    "deploy",
    "script",
    "strategy",
    "a股",
    "stock",
    "因子",
)

PROJECT_DELIVERY_QUERY_MARKERS = (
    "deploy",
    "script",
    "commit",
    "push",
    "release",
    "publish",
    "docs",
    "documentation",
    "readme",
    "about",
)

PROJECT_EXPLORATION_QUERY_MARKERS = (
    "search",
    "evaluate",
    "compare",
    "alternative",
    "plan",
    "idea",
    "research",
    "open source",
)

RELATIONSHIP_QUERY_MARKERS = (
    "朋友",
    "关系",
    "微信",
)

RELATIONSHIP_TEXT_MARKERS = (
    "朋友",
    "关系",
    "微信",
)

FOCUS_PROFILES = {
    "sample-profile": {
        "kind": "general",
        "intent": "dossier",
        "title": "Sample Focus Dossier",
        "hub_title": "Sample Memory Hub",
        "slug": "hub-sample",
        "aliases": (
            "sample",
            "example",
        ),
        "keywords": (
            "sample",
            "example",
            "reference",
        ),
        "tags": (
            "sample",
            "reference",
        ),
        "entity_type": "general",
        "priority": 50,
        "retention_mode": "normal",
        "recall_mode": "dossier_first",
        "prefer_live_hindsight": False,
        "summary_policy": "general",
        "timeline_enabled": False,
        "active": False,
    },
}

SYSTEM_QUERY_MARKERS = (
    "记忆",
    "memory",
    "hermes",
    "配置",
    "config",
    "provider",
    "gateway",
    "cron",
    "system",
    "server",
    "telegram",
    "endpoint",
    "api",
    "key",
    "重启",
    "restart",
    "模型",
    "model",
    "用量",
    "模型用量",
    "usage",
    "归档",
    "archive",
)

WEAK_FALLBACK_LAYERS = (
    "fts5",
    "like",
    "semantics",
    "archive",
    "governance_like",
    "governance",
)

QUERY_FAMILY_POLICIES = {
    "provider:config": {
        "strong_layers": ("object", "hindsight_cache"),
        "weak_layers": WEAK_FALLBACK_LAYERS,
        "min_direct_hits": 2,
        "min_candidate_floor": 3,
    },
    "project:delivery": {
        "strong_layers": ("object", "hindsight_cache"),
        "weak_layers": WEAK_FALLBACK_LAYERS,
        "min_direct_hits": 2,
        "min_candidate_floor": 2,
    },
    "project:exploration": {
        "preserve_breadth": True,
    },
    "relationship:core": {
        "prefer_live_hindsight": True,
    },
}


def _matches_any(query: str, markers: tuple[str, ...]) -> bool:
    lowered = (query or "").lower()
    return any(marker in lowered for marker in markers)


def is_provider_query(query: str) -> bool:
    return _matches_any(query, PROVIDER_QUERY_MARKERS)


def is_provider_incident_query(query: str) -> bool:
    return _matches_any(query, PROVIDER_INCIDENT_QUERY_MARKERS)


def is_provider_tooling_query(query: str) -> bool:
    return _matches_any(query, PROVIDER_TOOLING_QUERY_MARKERS)


def provider_query_mode(query: str) -> str:
    if not is_provider_query(query):
        return ""
    if is_provider_incident_query(query):
        return "runtime"
    if is_provider_tooling_query(query):
        return "tooling"
    return "config"


def is_provider_config_query(query: str) -> bool:
    return provider_query_mode(query) == "config"


def is_project_query(query: str) -> bool:
    return _matches_any(query, PROJECT_QUERY_MARKERS)


def is_project_delivery_query(query: str) -> bool:
    return _matches_any(query, PROJECT_DELIVERY_QUERY_MARKERS)


def is_project_exploration_query(query: str) -> bool:
    return _matches_any(query, PROJECT_EXPLORATION_QUERY_MARKERS)


def project_query_mode(query: str) -> str:
    if not is_project_query(query):
        return ""
    if is_project_exploration_query(query):
        return "exploration"
    if is_project_delivery_query(query):
        return "delivery"
    return "project"


def is_project_delivery_mode(query: str) -> bool:
    return project_query_mode(query) == "delivery"


def is_project_exploration_mode(query: str) -> bool:
    return project_query_mode(query) == "exploration"


def is_relationship_query(query: str) -> bool:
    return _matches_any(query, RELATIONSHIP_QUERY_MARKERS)


def has_relationship_text(*texts: str) -> bool:
    haystack = " ".join(texts).lower()
    return any(marker in haystack for marker in RELATIONSHIP_TEXT_MARKERS)


def is_system_query_text(query: str) -> bool:
    return _matches_any(query, SYSTEM_QUERY_MARKERS)


def active_focus_profiles() -> dict[str, dict]:
    return {profile_id: profile for profile_id, profile in FOCUS_PROFILES.items() if profile.get("active", True)}


def focus_profile_matches_text(profile: dict, *texts: str) -> bool:
    haystack = " ".join(texts).lower()
    return any(alias.lower() in haystack for alias in profile.get("aliases", ())) or any(
        keyword.lower() in haystack for keyword in profile.get("keywords", ())
    )


def focus_profile_for_text(*texts: str) -> tuple[str, dict] | tuple[None, None]:
    for profile_id, profile in active_focus_profiles().items():
        if focus_profile_matches_text(profile, *texts):
            return profile_id, profile
    return None, None


def focus_profile_for_query(query: str) -> tuple[str, dict] | tuple[None, None]:
    return focus_profile_for_text(query or "")


def focus_profile_ids_for_text(*texts: str) -> list[str]:
    matched = []
    for profile_id, profile in active_focus_profiles().items():
        if focus_profile_matches_text(profile, *texts):
            matched.append(profile_id)
    return matched


def focus_profile_kind(query: str) -> str:
    _, profile = focus_profile_for_query(query)
    return profile.get("kind", "") if profile else ""


def is_focus_profile_query(query: str) -> bool:
    profile_id, profile = focus_profile_for_query(query)
    return bool(profile_id and profile)


def focus_profile_recall_mode(query: str) -> str:
    _, profile = focus_profile_for_query(query)
    return profile.get("recall_mode", "") if profile else ""


def focus_profile_summary_policy(query: str) -> str:
    _, profile = focus_profile_for_query(query)
    return profile.get("summary_policy", "") if profile else ""


def focus_profile_intent(query: str) -> str:
    _, profile = focus_profile_for_query(query)
    if not profile:
        return ""
    return profile.get("intent", "") or "dossier"


def focus_profile_prefers_live_hindsight(query: str) -> bool:
    _, profile = focus_profile_for_query(query)
    return bool(profile and profile.get("prefer_live_hindsight"))


def focus_profile_timeline_enabled(*texts: str) -> bool:
    for profile_id in focus_profile_ids_for_text(*texts):
        profile = active_focus_profiles().get(profile_id, {})
        if profile.get("timeline_enabled"):
            return True
    return False


def focus_profile_archive_tags(*texts: str) -> list[str]:
    tags: list[str] = []
    seen = set()
    for profile_id in focus_profile_ids_for_text(*texts):
        profile = active_focus_profiles().get(profile_id, {})
        for tag in profile.get("tags", ()):
            tag_text = str(tag).strip()
            if not tag_text or tag_text in seen:
                continue
            seen.add(tag_text)
            tags.append(tag_text)
        if profile.get("timeline_enabled") and "timeline" not in seen:
            seen.add("timeline")
            tags.append("timeline")
    return tags


def query_family_policy_key(query: str) -> str:
    if is_relationship_query(query):
        return "relationship:core"
    if is_provider_config_query(query):
        return "provider:config"
    if is_project_exploration_mode(query):
        return "project:exploration"
    if is_project_delivery_mode(query):
        return "project:delivery"
    return ""


def get_query_family_policy(query: str) -> dict:
    key = query_family_policy_key(query)
    return QUERY_FAMILY_POLICIES.get(key, {})


def get_query_family_weak_layers(query: str) -> set[str]:
    return set(get_query_family_policy(query).get("weak_layers", ()))


def query_family_policy_ready(query: str, candidate_count: int, direct_hits: int, top: int) -> bool:
    policy = get_query_family_policy(query)
    if not policy:
        return False
    candidate_floor = int(policy.get("min_candidate_floor", top))
    min_hits = int(policy.get("min_direct_hits", 2))
    return candidate_count >= max(candidate_floor, top - 1) and direct_hits >= min_hits


def query_family_preserves_breadth(query: str) -> bool:
    return bool(get_query_family_policy(query).get("preserve_breadth"))


def query_family_prefers_live_hindsight(query: str) -> bool:
    policy = get_query_family_policy(query)
    if policy.get("prefer_live_hindsight"):
        return True
    _, profile = focus_profile_for_query(query)
    return bool(profile and profile.get("prefer_live_hindsight"))
