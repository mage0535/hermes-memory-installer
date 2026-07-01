import pytest

from governance.temporal import temporal_retrieve
from mtm.consolidator import consolidate


def test_disabled_extensions_are_noops(monkeypatch):
    monkeypatch.delenv("TEMPORAL_TRUTH_ENABLED", raising=False)
    monkeypatch.delenv("MTM_ENABLED", raising=False)
    assert temporal_retrieve("query") == "query"
    assert consolidate()["status"] == "disabled"


def test_enabled_extensions_require_approved_design(monkeypatch):
    monkeypatch.setenv("MTM_ENABLED", "true")
    with pytest.raises(NotImplementedError):
        consolidate()
