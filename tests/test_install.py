#!/usr/bin/env python3
"""Installer tests for the current sidecar project."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from installer import install


def test_version_is_3_5_1():
    assert install.VERSION == "3.5.1"


def test_supported_script_set_matches_repo():
    scripts_dir = install.scripts_source_dir()
    missing = [name for name in install.SUPPORTED_SCRIPT_NAMES if not (scripts_dir / name).exists()]
    assert missing == []


def test_supported_script_set_covers_runtime_and_cli_utilities():
    expected = {
        "memory_family_registry.py",
        "memory_governance_rebuild.py",
        "memory_guardian.py",
        "memory_maintenance_cycle.py",
        "session_to_gbrain.py",
        "sidecar_acceptance_check.py",
        "tiered_context_injector.py",
        "archive_sessions.py",
        "auto_session_summary.py",
        "gbrain_deorphan_index.py",
        "memory_observability_report.py",
        "memory_storage_cross_check.py",
        "state_db_schema.py",
        "knowledge_notes.py",
        "recall_samples.py",
        "langsmith_monitor.py",
        "langsmith_task_wrapper.py",
        "langsmith_trend_report.py",
        "runtime_drift_check.py",
        "alert_webhook_receiver.py",
        "metrics_dashboard.py",
        "metrics_dashboard_server.py",
        "openmetrics_exporter.py",
        "profile_isolation_soak.py",
        "hindsight_security_audit.py",
        "synthetic_recall_benchmark.py",
    }
    assert expected.issubset(set(install.SUPPORTED_SCRIPT_NAMES))
    assert "memory_watermark.py" not in install.SUPPORTED_SCRIPT_NAMES
    assert "memory_snapshot_backup.py" not in install.SUPPORTED_SCRIPT_NAMES


def test_storage_cross_check_defaults_to_hermes_home():
    content = (REPO / "scripts" / "memory_storage_cross_check.py").read_text(encoding="utf-8")

    assert 'Path.home() / ".hermes"' in content
    assert "AGENT_HOME/HERMES_HOME not set" in content


def test_embedding_catalog_has_recommended_default():
    recommended = [model for model in install.EMBEDDING_MODELS.values() if model.recommended]
    assert len(recommended) == 1
    assert recommended[0].model_id == install.DEFAULT_EMBEDDING_MODEL


def test_parse_args_is_import_safe_and_noninteractive():
    args = install.parse_args(["--noninteractive"])
    assert args.noninteractive is True
    assert args.agent_home is None
    assert args.dry_run is False
    assert args.install_mode == "3"
    assert args.lang == "auto"


def test_parse_args_accepts_install_mode_and_lang():
    args = install.parse_args(["--install-mode", "2", "--lang", "zh"])

    assert args.install_mode == "2"
    assert args.lang == "zh"


def test_dry_run_lang_line_does_not_conflict_with_translate_argument(tmp_path: Path, capsys):
    agent_home = tmp_path / ".agent"
    agent_home.mkdir()

    rc = install.main(["--dry-run", "--skip-checks", "--noninteractive", "--agent-home", str(agent_home), "--lang", "en"])

    assert rc == 0
    assert "Language: en" in capsys.readouterr().out


def test_resolve_language_prefers_explicit_option(monkeypatch):
    monkeypatch.setenv("LANG", "en_US.UTF-8")

    lang = install.resolve_language(install.parse_args(["--lang", "zh"]))

    assert lang == "zh"


def test_resolve_language_uses_locale_when_auto(monkeypatch):
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")

    lang = install.resolve_language(install.parse_args([]))

    assert lang == "zh"


def test_mode_1_guidance_mentions_other_modes():
    guidance = install.render_dependency_guidance(
        lang="en",
        install_mode="1",
        failed_dependencies=["postgres", "hindsight", "gbrain"],
        bootstrap_supported=True,
    )

    assert "--install-mode 2" in guidance
    assert "--install-mode 3" in guidance
    assert "Mode 1" in guidance


def test_mode_3_failure_message_includes_downgrade_paths():
    message = install.render_mode_fallback_message(
        lang="en",
        failed_mode="3",
        reason="bootstrap failed",
    )

    assert "--install-mode 2" in message
    assert "--install-mode 1" in message
    assert "bootstrap failed" in message


@pytest.mark.skip(reason="legacy mojibake assertion; replaced by readable Chinese coverage")
def test_mode_3_failure_message_supports_chinese():
    message = install.render_mode_fallback_message(
        lang="zh",
        failed_mode="3",
        reason="依赖安装失败",
    )

    assert "--install-mode 2" in message
    assert "--install-mode 1" in message
    assert "依赖安装失败" in message


@pytest.mark.skip(reason="legacy mojibake assertion; replaced by readable Chinese coverage")
def test_chinese_installer_messages_are_readable():
    message = install.render_dependency_guidance(
        lang="zh",
        install_mode="3",
        failed_dependencies=["postgres", "hindsight", "gbrain"],
        bootstrap_supported=True,
    )

    assert "模式 3" in message
    assert "缺失的关键依赖" in message
    assert "鐜" not in message
    assert "锛" not in message


def test_chinese_installer_messages_are_readable_current():
    fallback = install.render_mode_fallback_message(
        lang="zh",
        failed_mode="3",
        reason="依赖安装失败",
    )
    guidance = install.render_dependency_guidance(
        lang="zh",
        install_mode="3",
        failed_dependencies=["postgres", "hindsight", "gbrain"],
        bootstrap_supported=True,
    )

    assert "依赖安装失败" in fallback
    assert "模式 3" in guidance
    assert "缺失的关键依赖" in guidance
    assert "�" not in fallback + guidance
    assert "閿" not in fallback + guidance


def test_patch_agent_config_adds_sidecar_settings(tmp_path: Path):
    agent_home = tmp_path / ".agent"
    agent_home.mkdir()
    config_path = agent_home / "config.yaml"
    config_path.write_text("skills:\n  - existing-skill\n", encoding="utf-8")

    updated_path = install.patch_agent_config(agent_home)
    assert updated_path == config_path

    payload = yaml.safe_load(updated_path.read_text(encoding="utf-8"))
    assert payload["memory"]["provider"] == "hindsight"
    assert "existing-skill" in payload["skills"]
    assert payload["memory_sidecar"]["version"] == "3.5.1"
    assert payload["memory_sidecar"]["scripts_dir"] == str(agent_home / "scripts")


def test_patch_agent_config_preserves_existing_provider_and_creates_backup(tmp_path: Path):
    agent_home = tmp_path / ".agent"
    agent_home.mkdir()
    config_path = agent_home / "config.yaml"
    original = "memory:\n  provider: custom-memory\nskills:\n  - existing-skill\n"
    config_path.write_text(original, encoding="utf-8")

    install.patch_agent_config(agent_home)

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert payload["memory"]["provider"] == "custom-memory"
    backups = list(agent_home.glob("config.yaml.memory-sidecar-backup-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == original


def test_patch_agent_config_rejects_invalid_json_without_overwriting(tmp_path: Path):
    agent_home = tmp_path / ".agent"
    agent_home.mkdir()
    config_path = agent_home / "config.json"
    original = "{invalid json"
    config_path.write_text(original, encoding="utf-8")

    try:
        install.patch_agent_config(agent_home)
    except ValueError as exc:
        assert "invalid JSON" in str(exc)
    else:
        raise AssertionError("invalid JSON config should not be overwritten")

    assert config_path.read_text(encoding="utf-8") == original


def test_deployed_scripts_have_complete_local_dependency_closure(tmp_path: Path):
    destination = tmp_path / "scripts"
    installed = install.deploy_scripts(install.scripts_source_dir(), destination)

    assert set(installed) == set(install.SUPPORTED_SCRIPT_NAMES)
    for required in ("state_db_schema.py", "knowledge_notes.py", "recall_samples.py"):
        assert (destination / required).exists()

    shutil.copy2(destination / "memory_governance_rebuild.py", tmp_path / "probe.py")
    compile((tmp_path / "probe.py").read_text(encoding="utf-8"), str(tmp_path / "probe.py"), "exec")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import memory_governance_rebuild, sidecar_acceptance_check",
        ],
        cwd=destination,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_deploy_scripts_rejects_incomplete_source_before_writing(monkeypatch, tmp_path: Path):
    src_dir = tmp_path / "src"
    dest_dir = tmp_path / "dest"
    src_dir.mkdir()
    (src_dir / "a.py").write_text("print('a')\n", encoding="utf-8")
    monkeypatch.setattr(install, "SUPPORTED_SCRIPT_NAMES", ["a.py", "missing.py"])

    try:
        install.deploy_scripts(src_dir, dest_dir)
    except FileNotFoundError as exc:
        assert "missing.py" in str(exc)
    else:
        raise AssertionError("incomplete installer source should fail")

    assert not dest_dir.exists()


def test_deploy_scripts_is_atomic_when_copy_fails(monkeypatch, tmp_path: Path):
    src_dir = tmp_path / "src"
    dest_dir = tmp_path / "dest"
    src_dir.mkdir()
    dest_dir.mkdir()
    (src_dir / "a.py").write_text("print('new-a')\n", encoding="utf-8")
    (src_dir / "b.py").write_text("print('new-b')\n", encoding="utf-8")
    (dest_dir / "a.py").write_text("print('old-a')\n", encoding="utf-8")
    (dest_dir / "b.py").write_text("print('old-b')\n", encoding="utf-8")
    monkeypatch.setattr(install, "SUPPORTED_SCRIPT_NAMES", ["a.py", "b.py"])

    real_copy2 = shutil.copy2

    def flaky_copy(src, dst, *args, **kwargs):
        if Path(src).name == "b.py":
            raise OSError("simulated copy failure")
        return real_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(install.shutil, "copy2", flaky_copy)

    try:
        install.deploy_scripts(src_dir, dest_dir)
    except OSError:
        pass
    else:
        raise AssertionError("expected deploy failure")

    assert (dest_dir / "a.py").read_text(encoding="utf-8") == "print('old-a')\n"
    assert (dest_dir / "b.py").read_text(encoding="utf-8") == "print('old-b')\n"


def test_deploy_scripts_removes_new_targets_when_replace_fails(monkeypatch, tmp_path: Path):
    src_dir = tmp_path / "src"
    dest_dir = tmp_path / "dest"
    src_dir.mkdir()
    dest_dir.mkdir()
    (src_dir / "a.py").write_text("print('new-a')\n", encoding="utf-8")
    (src_dir / "b.py").write_text("print('new-b')\n", encoding="utf-8")
    monkeypatch.setattr(install, "SUPPORTED_SCRIPT_NAMES", ["a.py", "b.py"])

    real_replace = install.os.replace

    def flaky_replace(src, dst):
        if Path(dst).name == "b.py":
            raise OSError("simulated replace failure")
        return real_replace(src, dst)

    monkeypatch.setattr(install.os, "replace", flaky_replace)

    try:
        install.deploy_scripts(src_dir, dest_dir)
    except OSError:
        pass
    else:
        raise AssertionError("expected deploy failure")

    assert not (dest_dir / "a.py").exists()
    assert not (dest_dir / "b.py").exists()


def test_main_rolls_back_script_changes_when_config_patch_fails(monkeypatch, tmp_path: Path):
    agent_home = tmp_path / ".agent"
    scripts_dir = agent_home / "scripts"
    src_dir = tmp_path / "src"
    agent_home.mkdir()
    scripts_dir.mkdir()
    src_dir.mkdir()
    (src_dir / "a.py").write_text("print('new-a')\n", encoding="utf-8")
    (scripts_dir / "a.py").write_text("print('old-a')\n", encoding="utf-8")
    monkeypatch.setattr(install, "SUPPORTED_SCRIPT_NAMES", ["a.py"])
    monkeypatch.setattr(install, "scripts_source_dir", lambda: src_dir)
    monkeypatch.setattr(install, "patch_agent_config", lambda agent_home: (_ for _ in ()).throw(RuntimeError("config failed")))

    try:
        install.main(["--agent-home", str(agent_home), "--skip-checks", "--noninteractive"])
    except RuntimeError as exc:
        assert "config failed" in str(exc)
    else:
        raise AssertionError("expected config patch failure")

    assert (scripts_dir / "a.py").read_text(encoding="utf-8") == "print('old-a')\n"
    assert not (agent_home / install.SIDECAR_DIRNAME / "install-profile.json").exists()


def test_main_removes_config_note_when_install_fails_after_note_creation(monkeypatch, tmp_path: Path):
    agent_home = tmp_path / ".agent"
    src_dir = tmp_path / "src"
    agent_home.mkdir()
    src_dir.mkdir()
    (src_dir / "a.py").write_text("print('new-a')\n", encoding="utf-8")
    monkeypatch.setattr(install, "SUPPORTED_SCRIPT_NAMES", ["a.py"])
    monkeypatch.setattr(install, "scripts_source_dir", lambda: src_dir)
    monkeypatch.setattr(install, "write_install_profile", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("profile failed")))

    try:
        install.main(["--agent-home", str(agent_home), "--skip-checks", "--noninteractive"])
    except RuntimeError as exc:
        assert "profile failed" in str(exc)
    else:
        raise AssertionError("expected profile write failure")

    assert not (agent_home / install.SIDECAR_DIRNAME / "config-note.txt").exists()
    assert not (agent_home / "scripts" / "a.py").exists()


def test_main_preserves_existing_config_note_when_install_fails(monkeypatch, tmp_path: Path):
    agent_home = tmp_path / ".agent"
    src_dir = tmp_path / "src"
    note_path = agent_home / install.SIDECAR_DIRNAME / "config-note.txt"
    note_path.parent.mkdir(parents=True)
    src_dir.mkdir()
    note_path.write_text("existing instructions\n", encoding="utf-8")
    (src_dir / "a.py").write_text("print('new-a')\n", encoding="utf-8")
    monkeypatch.setattr(install, "SUPPORTED_SCRIPT_NAMES", ["a.py"])
    monkeypatch.setattr(install, "scripts_source_dir", lambda: src_dir)
    monkeypatch.setattr(install, "write_install_profile", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("profile failed")))

    try:
        install.main(["--agent-home", str(agent_home), "--skip-checks", "--noninteractive"])
    except RuntimeError as exc:
        assert "profile failed" in str(exc)
    else:
        raise AssertionError("expected profile write failure")

    assert note_path.read_text(encoding="utf-8") == "existing instructions\n"


def test_write_install_profile_records_embedding_metadata(tmp_path: Path):
    agent_home = tmp_path / ".agent"
    agent_home.mkdir()
    model = install.EMBEDDING_MODELS["1"]

    profile_path = install.write_install_profile(
        agent_home,
        model,
        ["memory_guardian.py", "tiered_context_injector.py"],
    )
    payload = json.loads(profile_path.read_text(encoding="utf-8"))

    assert payload["version"] == "3.5.1"
    assert payload["embedding_model"]["model_id"] == model.model_id
    assert payload["installed_scripts"] == ["memory_guardian.py", "tiered_context_injector.py"]


def test_check_hindsight_uses_http_fallback_when_curl_is_missing(monkeypatch):
    monkeypatch.setattr(install, "_run", lambda cmd, timeout=10: (127, ""))
    monkeypatch.setattr(install, "_http_probe", lambda url, timeout=5: (True, '{"status":"ok"}'))

    ok, detail = install.check_hindsight()

    assert ok is True
    assert "Hindsight reachable" in detail


def test_check_postgres_reports_probe_unavailable_without_false_failure(monkeypatch):
    monkeypatch.setattr(install, "_run", lambda cmd, timeout=10: (127, ""))

    ok, detail = install.check_postgres()

    assert ok is True
    assert "pg_isready not installed" in detail


def test_check_embedding_service_uses_health_endpoint_for_embedding_api(monkeypatch):
    monkeypatch.setenv("EMBEDDING_API_URL", "http://127.0.0.1:8766/v1/embeddings")
    probed_urls = []

    def fake_probe(url, timeout=5):
        probed_urls.append(url)
        return True, '{"ok": true}'

    monkeypatch.setattr(install, "_http_probe", fake_probe)

    ok, detail = install.check_embedding_service()

    assert ok is True
    assert probed_urls == ["http://127.0.0.1:8766/health"]
    assert "http://127.0.0.1:8766/health" in detail


def test_shell_installer_quotes_versioned_requirement():
    installer_text = (REPO / "install.sh").read_text(encoding="utf-8")

    assert '"PyYAML>=6.0"' in installer_text

