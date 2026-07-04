from pathlib import Path

from runtime_paths import RuntimePaths, resolve_agent_home


def test_agent_home_precedence_and_default(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    monkeypatch.setenv("AGENT_HOME", str(tmp_path / "agent"))

    assert resolve_agent_home() == tmp_path / "agent"

    monkeypatch.delenv("AGENT_HOME")
    assert resolve_agent_home() == tmp_path / "hermes"

    monkeypatch.delenv("HERMES_HOME")
    assert resolve_agent_home() == Path.home() / ".hermes"


def test_runtime_paths_are_derived_from_agent_home(tmp_path):
    paths = RuntimePaths.from_agent_home(tmp_path)

    assert paths.agent_home == tmp_path
    assert paths.sidecar_home == tmp_path / "memory-sidecar"
    assert paths.logs_dir == tmp_path / "logs"
    assert paths.production_registry == tmp_path / ".memory_eval" / "registry_production.py"
    assert paths.governance_db == tmp_path / "memory_governance.db"
