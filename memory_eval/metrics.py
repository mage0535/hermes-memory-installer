"""Memory evaluation metrics."""

from collections import defaultdict

from .models import CaseResult, MetricSet


def _normalized_fact(hit) -> str:
    return " ".join(hit.content.casefold().split())


def calculate_metrics(results: list[CaseResult], expected: dict[str, tuple[str, ...]]) -> MetricSet:
    evaluated = [item for item in results if item.status == "evaluated"]
    if not evaluated:
        return MetricSet(0.0, 0.0, 0.0, 0.0, None)
    matched_cases = 0
    relevant_hits = 0
    total_hits = 0
    stale_hits = 0
    comparable_cases = 0
    agreeing_cases = 0
    contradicting_cases = 0
    for result in evaluated:
        fields = tuple(value.casefold() for value in expected.get(result.case_id, ()))
        matches = [hit for hit in result.hits if any(field in hit.content.casefold() for field in fields)]
        matched_cases += bool(matches)
        relevant_hits += len(matches)
        total_hits += len(result.hits)
        stale_hits += sum(1 for hit in result.hits if hit.stale)

        by_key = defaultdict(list)
        for hit in result.hits:
            key = hit.conflict_group or hit.fact_key
            if key:
                by_key[key].append(hit)
        has_comparable = False
        has_agreement = False
        has_contradiction = False
        for hits in by_key.values():
            active_hits = [hit for hit in hits if not hit.stale]
            if len({hit.layer for hit in hits}) > 1:
                has_comparable = True
                has_agreement = len({_normalized_fact(hit) for hit in hits}) == 1
            if len(active_hits) > 1 and len({_normalized_fact(hit) for hit in active_hits}) > 1:
                has_contradiction = True
        comparable_cases += has_comparable
        agreeing_cases += has_comparable and has_agreement
        contradicting_cases += has_contradiction
    return MetricSet(
        matched_cases / len(evaluated),
        relevant_hits / total_hits if total_hits else 0.0,
        contradicting_cases / len(evaluated),
        stale_hits / total_hits if total_hits else 0.0,
        agreeing_cases / comparable_cases if comparable_cases else None,
    )
