import json

from memory_eval.registry_lint import lint_registry
from memory_eval.trends import compare_report_payloads


def report_payload(recall):
    return {
        "reports": [
            {
                "registry": "production",
                "evaluated_count": 4,
                "metrics": {
                    "recall_at_k": recall,
                    "precision_at_k": 0.5,
                    "contradiction_rate": 0.0,
                    "stale_hit_rate": 0.0,
                    "cross_layer_agreement": None,
                },
                "per_category": {"accurate_retrieval": 4},
                "failures": [],
            }
        ]
    }


def test_compare_reports_returns_metric_deltas():
    comparison = compare_report_payloads(report_payload(0.75), report_payload(0.5))

    assert comparison["production"]["recall_at_k"]["current"] == 0.75
    assert comparison["production"]["recall_at_k"]["previous"] == 0.5
    assert comparison["production"]["recall_at_k"]["delta"] == 0.25


def test_registry_lint_rejects_secret_like_content():
    issues = lint_registry(
        [
            {
                "id": "prod_001",
                "category": "accurate_retrieval",
                "query": "token sk-live-abcdefghijklmnopqrstuvwxyz",
                "expected_fields": ["token"],
                "expected_layer": "hindsight",
            }
        ]
    )

    assert issues
    assert issues[0]["rule"] == "secret_like"
    assert "sk-live" not in json.dumps(issues)
