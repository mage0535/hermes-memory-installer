from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    id: str
    category: str
    query: str
    expected_fields: list[str]
    expected_layer: str
    expected_min_score: float = 0.0
    conflict_expected: bool = False
    temporal_context: Any = None
    synthetic_hits: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class LoadedRegistry:
    name: str
    cases: list[EvalCase] = field(default_factory=list)
    error: str | None = None
    source_path: Path | None = None


@dataclass(frozen=True)
class RecallHit:
    layer: str
    score: float
    content: str
    conflict_group: str | None = None
    fact_key: str | None = None
    stale: bool = False


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    status: str
    hits: tuple[RecallHit, ...] = ()


@dataclass(frozen=True)
class MetricSet:
    recall_at_k: float
    precision_at_k: float
    contradiction_rate: float
    stale_hit_rate: float
    cross_layer_agreement: float | None

    def to_dict(self) -> dict[str, float | None]:
        return {
            "recall_at_k": self.recall_at_k,
            "precision_at_k": self.precision_at_k,
            "contradiction_rate": self.contradiction_rate,
            "stale_hit_rate": self.stale_hit_rate,
            "cross_layer_agreement": self.cross_layer_agreement,
        }


@dataclass(frozen=True)
class EvalReport:
    registry: str
    evaluated_count: int
    metrics: dict[str, float | None]
    per_category: dict[str, int]
    failures: tuple[str, ...] = ()
    comparison: dict | None = None


Case = EvalCase
