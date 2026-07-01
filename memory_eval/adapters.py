"""Recall adapter contracts and deterministic synthetic implementation."""

from __future__ import annotations

import os
import json
from urllib import request
from typing import Callable, Mapping, Protocol

from .models import CaseResult, EvalCase, RecallHit


class RecallAdapter(Protocol):
    def recall(self, case: EvalCase, k: int) -> CaseResult: ...


def validate_case(payload: Mapping[str, object]) -> EvalCase:
    required = {
        "id",
        "category",
        "query",
        "expected_fields",
        "expected_layer",
        "expected_min_score",
    }
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"missing evaluation case fields: {sorted(missing)}")
    return EvalCase(
        id=str(payload["id"]),
        category=str(payload["category"]),
        query=str(payload["query"]),
        expected_fields=tuple(str(item) for item in payload["expected_fields"]),
        expected_layer=str(payload["expected_layer"]),
        expected_min_score=float(payload["expected_min_score"]),
        conflict_expected=bool(payload.get("conflict_expected", False)),
        temporal_context=payload.get("temporal_context"),
        synthetic_hits=tuple(payload.get("synthetic_hits", ())),
    )


class SyntheticAdapter:
    """Return fixture hits without external I/O or persistent state."""

    def recall(self, case: EvalCase, k: int) -> CaseResult:
        hits = tuple(
            RecallHit(
                layer=str(item["layer"]),
                score=float(item["score"]),
                content=str(item["content"]),
                conflict_group=item.get("conflict_group"),
                fact_key=item.get("fact_key"),
                stale=bool(item.get("stale", False)),
            )
            for item in case.synthetic_hits[:k]
        )
        return CaseResult(case_id=case.id, status="evaluated", hits=hits)


class LiveAdapter:
    """Compose independently failing, read-only layer readers."""

    def __init__(self, layer_readers: Mapping[str, Callable[[str], list[dict]]] | None = None):
        self.layer_readers = dict(layer_readers or {"hindsight": self._read_hindsight})

    def _read_hindsight(self, query: str) -> list[dict]:
        base_url = os.getenv("HINDSIGHT_API_URL", "http://127.0.0.1:8890").rstrip("/")
        payload = json.dumps({"bank_id": os.getenv("HINDSIGHT_BANK_ID", "default"), "query": query, "k": 5}).encode("utf-8")
        req = request.Request(
            f"{base_url}/v1/recall",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=float(os.getenv("MEMORY_EVAL_LAYER_TIMEOUT", "5"))) as response:
            data = json.loads(response.read().decode("utf-8"))
        raw_hits = data.get("results") or data.get("hits") or data.get("memories") or []
        normalized = []
        for item in raw_hits if isinstance(raw_hits, list) else []:
            if not isinstance(item, dict):
                continue
            content = item.get("content") or item.get("text") or item.get("memory") or item.get("summary") or ""
            normalized.append({"content": str(content), "score": float(item.get("score", item.get("similarity", 0.0)))})
        return normalized

    def recall(self, case: EvalCase, k: int) -> CaseResult:
        if case.category == "test_time_learning" and os.getenv("MEMORY_EVAL_ALLOW_WRITES", "").lower() != "true":
            return CaseResult(case.id, "skipped")
        hits = []
        for layer, reader in self.layer_readers.items():
            try:
                for item in reader(case.query)[:k]:
                    hits.append(
                        RecallHit(
                            layer,
                            float(item.get("score", 0)),
                            str(item.get("content", "")),
                            conflict_group=item.get("conflict_group"),
                            fact_key=item.get("fact_key"),
                            stale=bool(item.get("stale", False)),
                        )
                    )
            except Exception:
                continue
        return CaseResult(case.id, "evaluated", tuple(hits[:k]))
