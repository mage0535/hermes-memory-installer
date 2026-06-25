#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecallSampleCase:
    query: str
    expected_intent: str
    min_l2: int = 0
    min_l3: int = 0
    required_source: str | None = None
    require_top_titles: bool = True
    require_knowledge_hit: bool = False
    required_for_acceptance: bool = True


DEFAULT_SAMPLE_CASES = (
    RecallSampleCase(
        query="agent memory architecture",
        expected_intent="knowledge",
        min_l2=1,
        min_l3=1,
        required_source="knowledge",
        require_knowledge_hit=True,
    ),
    RecallSampleCase(
        query="模型用量",
        expected_intent="system",
        min_l3=1,
    ),
    RecallSampleCase(
        query="github script deploy",
        expected_intent="project",
        min_l2=1,
        min_l3=1,
    ),
    RecallSampleCase(
        query="朋友关系",
        expected_intent="relationship",
        min_l3=1,
        required_for_acceptance=False,
    ),
    RecallSampleCase(
        query="recent sessions",
        expected_intent="recent",
        min_l2=1,
        min_l3=1,
    ),
    RecallSampleCase(
        query="favorite breakfast preferences",
        expected_intent="general",
        min_l2=1,
    ),
)


def _flatten_top_sources(row: dict) -> list[str]:
    flattened = []
    for item in row.get("top_sources", []):
        if isinstance(item, list):
            flattened.extend(str(source) for source in item)
        elif item:
            flattened.append(str(item))
    return flattened


def evaluate_recall_samples(payload: dict, samples=DEFAULT_SAMPLE_CASES) -> tuple[bool, list[str]]:
    recalls = payload.get("recalls") or []
    rows_by_query = {str(row.get("query") or ""): row for row in recalls}
    errors = []

    for sample in samples:
        if not sample.required_for_acceptance:
            continue
        row = rows_by_query.get(sample.query)
        if row is None:
            errors.append(f"{sample.query}: missing recall sample")
            continue
        if row.get("intent") != sample.expected_intent:
            errors.append(f"{sample.query}: expected intent {sample.expected_intent!r}, got {row.get('intent')!r}")
        if int(row.get("l2_count") or 0) < sample.min_l2:
            errors.append(f"{sample.query}: expected l2_count >= {sample.min_l2}")
        if int(row.get("l3_count") or 0) < sample.min_l3:
            errors.append(f"{sample.query}: expected l3_count >= {sample.min_l3}")
        if sample.require_top_titles and not row.get("top_titles"):
            errors.append(f"{sample.query}: expected non-empty top titles")
        if sample.required_source and sample.required_source not in _flatten_top_sources(row):
            errors.append(f"{sample.query}: expected source {sample.required_source!r} in top sources")
        if sample.require_knowledge_hit and not row.get("knowledge_hit"):
            errors.append(f"{sample.query}: expected knowledge_hit to be true")

    return len(errors) == 0, errors
