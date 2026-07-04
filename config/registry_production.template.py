"""Private production registry template.

Copy this file to:
  $AGENT_HOME/.memory_eval/registry_production.py

Keep real secrets, host IPs, user names, and credential-bearing URLs out of
queries and expected fields. Use stable categories and sanitized fact labels.
"""

REGISTRY = [
    {
        "id": "prod_001",
        "category": "accurate_retrieval",
        "query": "current memory quality release objective",
        "expected_fields": ["memory", "quality"],
        "expected_layer": "hindsight",
        "expected_min_score": 0.1,
        "conflict_expected": False,
    },
    {
        "id": "prod_002",
        "category": "temporal_understanding",
        "query": "current backup schedule status",
        "expected_fields": ["backup", "schedule"],
        "expected_layer": "hindsight",
        "expected_min_score": 0.1,
        "conflict_expected": False,
        "temporal_context": {"mode": "current"},
    },
]
