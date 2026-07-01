from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from memory_eval.registry_loader import load_registries


def test_default_registry_is_always_loadable(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_HOME", str(tmp_path))

    loaded = load_registries("all")

    assert [item.name for item in loaded] == ["default"]


def test_all_adds_private_registry_without_copying_it(monkeypatch, tmp_path):
    private = tmp_path / ".memory_eval" / "registry_production.py"
    private.parent.mkdir()
    private.write_text(
        "REGISTRY = [{'id': 'prod_001', 'category': 'accurate_retrieval', "
        "'query': 'current project', 'expected_fields': ['project'], "
        "'expected_layer': 'hindsight', 'expected_min_score': 0.7}]",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_HOME", str(tmp_path))

    loaded = load_registries("all")

    assert [item.name for item in loaded] == ["default", "production"]
    assert loaded[1].cases[0].id == "prod_001"


def test_invalid_private_registry_becomes_scoped_error(monkeypatch, tmp_path):
    private = tmp_path / ".memory_eval" / "registry_production.py"
    private.parent.mkdir()
    private.write_text("REGISTRY = 'invalid'", encoding="utf-8")
    monkeypatch.setenv("AGENT_HOME", str(tmp_path))

    loaded = load_registries("all")

    assert loaded[0].name == "default"
    assert loaded[1].name == "production"
    assert loaded[1].error


def test_explicit_production_registry_requires_private_file(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_HOME", str(tmp_path))

    with pytest.raises(FileNotFoundError):
        load_registries("production")
