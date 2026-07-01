from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from memory_eval.adapters import SyntheticAdapter, validate_case
from memory_eval.registry_default import REGISTRY


def test_synthetic_adapter_returns_fixture_hits():
    case = validate_case(REGISTRY[0])
    result = SyntheticAdapter().recall(case, k=5)

    assert result.status == "evaluated"
    assert result.hits
    assert result.hits[0].layer == case.expected_layer
