from governance.temporal import temporal_retrieve
from mtm.consolidator import consolidate


def test_disabled_extensions_are_noops(monkeypatch):
    monkeypatch.delenv("TEMPORAL_TRUTH_ENABLED", raising=False)
    monkeypatch.delenv("MTM_ENABLED", raising=False)
    assert temporal_retrieve("query") == "query"
    assert consolidate()["status"] == "disabled"


def test_enabled_mtm_consolidates_empty_store_without_error(tmp_path, monkeypatch):
    monkeypatch.setenv("MTM_ENABLED", "true")
    result = consolidate(store_path=tmp_path / "missing.jsonl", governance_db=tmp_path / "gov.db", apply=False)
    assert result["status"] == "consolidated"
    assert result["processed"] == 0
