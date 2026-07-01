from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from memory_eval.registry_default import REGISTRY


def test_default_registry_distribution_and_ids():
    counts = Counter(case["category"] for case in REGISTRY)

    assert len(REGISTRY) == 40
    assert counts == {
        "accurate_retrieval": 12,
        "conflict_resolution": 10,
        "temporal_understanding": 10,
        "test_time_learning": 8,
    }
    assert len({case["id"] for case in REGISTRY}) == 40


def test_default_registry_is_privacy_safe():
    serialized = json.dumps(REGISTRY, ensure_ascii=False)
    forbidden = [r"sk-[A-Za-z0-9]", r"/root/", r"postgresql://[^<]", r"\b(?:\d{1,3}\.){3}\d{1,3}\b"]

    assert not any(re.search(pattern, serialized) for pattern in forbidden)
