from memory_eval.runner import run_eval
import memory_eval.runner as runner_module


def test_smoke_selects_three_cases_per_category():
    report = run_eval(mode="smoke", registry="default", backend="synthetic")[0]
    assert report.evaluated_count == 12
    assert set(report.metrics) == {"recall_at_k", "precision_at_k", "contradiction_rate", "stale_hit_rate", "cross_layer_agreement"}


def test_full_selects_all_cases():
    report = run_eval(mode="full", registry="default", backend="synthetic")[0]
    assert report.evaluated_count == 40


def test_live_backend_uses_default_live_adapter(monkeypatch):
    class StubLiveAdapter:
        def recall(self, case, k):
            from memory_eval.models import CaseResult, RecallHit

            return CaseResult(case.id, "evaluated", (RecallHit(case.expected_layer, 1.0, case.expected_fields[0]),))

    monkeypatch.setattr(runner_module, "LiveAdapter", StubLiveAdapter)

    report = run_eval(mode="smoke", registry="default", backend="live")[0]

    assert report.evaluated_count == 12
    assert report.metrics["recall_at_k"] == 1.0
