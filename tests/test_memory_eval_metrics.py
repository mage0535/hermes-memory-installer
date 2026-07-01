from memory_eval.metrics import calculate_metrics
from memory_eval.models import CaseResult, RecallHit


def test_metrics_use_only_evaluated_cases():
    results = [
        CaseResult("a", "evaluated", (RecallHit("hot", 1, "field=value"),)),
        CaseResult("b", "evaluated", (RecallHit("hot", 0, "irrelevant"),)),
        CaseResult("c", "skipped"),
    ]
    metrics = calculate_metrics(results, {"a": ("field",), "b": ("missing",)})
    assert metrics.recall_at_k == 0.5
    assert metrics.precision_at_k == 0.5


def test_stale_contradiction_and_agreement_metrics():
    result = CaseResult(
        "case_conflict",
        "evaluated",
        (
            RecallHit("hindsight", 0.9, "preference=blue", conflict_group="preference", fact_key="preference", stale=False),
            RecallHit("governance", 0.8, "preference=green", conflict_group="preference", fact_key="preference", stale=False),
            RecallHit("gbrain", 0.5, "preference=red", conflict_group="preference", fact_key="preference", stale=True),
        ),
    )

    metrics = calculate_metrics([result], {"case_conflict": ("preference",)})

    assert metrics.contradiction_rate == 1.0
    assert metrics.stale_hit_rate == 1 / 3
    assert metrics.cross_layer_agreement == 0.0


def test_cross_layer_agreement_is_one_when_layers_match():
    result = CaseResult(
        "case_agree",
        "evaluated",
        (
            RecallHit("hindsight", 0.9, "server=<SERVER_HOST>", fact_key="server"),
            RecallHit("gbrain", 0.8, "server=<SERVER_HOST>", fact_key="server"),
        ),
    )

    metrics = calculate_metrics([result], {"case_agree": ("server",)})

    assert metrics.cross_layer_agreement == 1.0


def test_all_five_metrics_are_exposed():
    metrics = calculate_metrics([], {})
    assert set(metrics.to_dict()) == {"recall_at_k", "precision_at_k", "contradiction_rate", "stale_hit_rate", "cross_layer_agreement"}
