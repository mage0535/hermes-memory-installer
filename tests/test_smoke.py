#!/usr/bin/env python3
"""Repository smoke tests for the current sidecar project."""

from __future__ import annotations

import py_compile
import importlib.util
from pathlib import Path
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from installer import install


def test_expected_project_files_exist():
    expected = [
        REPO / "README.md",
        REPO / "README_CN.md",
        REPO / "ARCHITECTURE.md",
        REPO / "ARCHITECTURE_CN.md",
        REPO / "MANUAL_INSTALL.md",
        REPO / "LICENSE",
        REPO / "install.sh",
        REPO / "install_cli.sh",
        REPO / "installer" / "install.py",
        REPO / "bin" / "hermes-memory",
    ]
    for path in expected:
        assert path.exists(), f"Missing required file: {path}"


def test_cli_exposes_deploy_audit_command():
    content = (REPO / "bin" / "hermes-memory").read_text(encoding="utf-8")

    assert "audit-deploy" in content
    assert "audit-repo" in content
    assert "manifest" in content
    assert "drift-check" in content
    assert "langsmith_uses_gray_path" in content
    assert "gbrain_deorphan_scheduled" in content
    assert "memory-guardian.timer" in content


def test_supported_scripts_compile():
    for name in install.SUPPORTED_SCRIPT_NAMES:
        with tempfile.NamedTemporaryFile(suffix=".pyc", delete=False) as tmp:
            cfile = tmp.name
        py_compile.compile(str(REPO / "scripts" / name), cfile=cfile, doraise=True)


def test_wrapper_scripts_compile():
    for path in [
        REPO / "installer" / "install.py",
        REPO / "installer" / "check_env.py",
        REPO / "installer" / "config_patch.py",
        REPO / "bin" / "hermes-memory",
    ]:
        with tempfile.NamedTemporaryFile(suffix=".pyc", delete=False) as tmp:
            cfile = tmp.name
        py_compile.compile(str(path), cfile=cfile, doraise=True)


def test_repository_defaults_do_not_expose_personal_entities():
    session_to_gbrain = (REPO / "scripts" / "session_to_gbrain.py").read_text(encoding="utf-8")
    assert "宁宁" not in session_to_gbrain
    assert "郑大姐" not in session_to_gbrain
    assert "MagicMusic" not in session_to_gbrain


def test_repository_defaults_do_not_depend_on_root_hermes_path():
    for path in list((REPO / "scripts").glob("*.py")) + list((REPO / "installer").glob("*.py")) + [REPO / "bin" / "hermes-memory"]:
        content = path.read_text(encoding="utf-8")
        assert "/root/.hermes" not in content
        assert "/usr/local/bin/gbrain" not in content


def test_repo_audit_command_passes_for_current_repository():
    import json
    import subprocess

    result = subprocess.run(
        [sys.executable, str(REPO / "bin" / "hermes-memory"), "audit-repo", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    audit = json.loads(result.stdout)

    assert audit["ok"] is True
    assert audit["missing_required_files"] == []
    assert audit["private_path_refs"] == []
    assert audit["secret_like_refs"] == []
    assert audit["compile_failures"] == []


def test_manifest_command_emits_expected_json(tmp_path: Path, monkeypatch):
    import json
    import subprocess

    agent_home = tmp_path / "agent-home"
    monkeypatch.setenv("AGENT_HOME", str(agent_home))

    result = subprocess.run(
        [sys.executable, str(REPO / "bin" / "hermes-memory"), "manifest", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)

    assert payload["agent_home"] == str(agent_home)
    assert payload["wrapper"]["mode"] in {"missing", "custom", "hardcoded_env", "env_default_safe"}
    assert "deploy_audit" in payload
    assert "generated_at" in payload


def test_public_repository_does_not_contain_private_server_paths():
    excluded_parts = {".pytest_cache", "__pycache__"}
    text_suffixes = {".py", ".md", ".sh", ".yaml", ".yml", ".json", ".j2"}
    for path in REPO.rglob("*"):
        if not path.is_file() or any(part in excluded_parts for part in path.parts):
            continue
        if "tests" in path.relative_to(REPO).parts:
            continue
        if path.suffix.lower() not in text_suffixes:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        assert "/root/.hermes" not in content, f"{path} contains a private server path"
        assert "/root/hermes-memory-installer" not in content, f"{path} contains a private server path"


def test_acceptance_check_covers_knowledge_layer():
    acceptance = (REPO / "scripts" / "sidecar_acceptance_check.py").read_text(encoding="utf-8")
    assert "agent memory architecture" in acceptance


def test_archive_sessions_uses_agent_home_instead_of_fixed_hermes_path():
    content = (REPO / "scripts" / "archive_sessions.py").read_text(encoding="utf-8")
    assert 'AGENT_HOME' in content
    assert '~/.hermes/state.db' not in content


def test_auto_session_summary_does_not_require_hermes_private_runtime():
    content = (REPO / "scripts" / "auto_session_summary.py").read_text(encoding="utf-8")
    assert 'hermes_state' not in content
    assert 'hermes-agent' not in content


def test_compatibility_matrix_documents_agent_agnostic_and_hermes_only_surfaces():
    matrix = (REPO / "docs" / "compatibility-matrix.md").read_text(encoding="utf-8")
    assert "Agent-Agnostic" in matrix
    assert "Hermes-Only" in matrix
    assert "memory_reflect.py" in matrix
    assert "auto_session_summary.py" in matrix


def test_hermes_onboarding_is_marked_hermes_specific():
    content = (REPO / "HERMES_ONBOARDING.md").read_text(encoding="utf-8")
    assert "Hermes-specific" in content


def test_memory_starter_skill_is_marked_historical_or_hermes_only():
    content = (REPO / "skills" / "memory-starter-kit" / "SKILL.md").read_text(encoding="utf-8")
    assert "Hermes-only" in content or "historical" in content


def test_memory_starter_skill_no_longer_instructs_agentmemory_runtime():
    content = (REPO / "skills" / "memory-starter-kit" / "SKILL.md").read_text(encoding="utf-8")
    assert "docker restart agentmemory" not in content
    assert "agentmemory Docker" not in content


def test_memory_proactive_skill_uses_generic_domains():
    content = (REPO / "skills" / "memory-proactive" / "SKILL.md").read_text(encoding="utf-8")
    assert "project-alpha" not in content
    assert "--domains project,stock" in content


def test_domain_memory_defaults_are_generic():
    content = (REPO / "scripts" / "domain_memory.py").read_text(encoding="utf-8")
    assert "project-alpha" not in content
    assert "Project Alpha" not in content
    assert '"project"' in content or "'project'" in content


def test_supporting_docs_and_headers_do_not_advertise_v3_1_1():
    for path in [
        REPO / "HERMES_ONBOARDING.md",
        REPO / "ARCHITECTURE_CN.md",
        REPO / "installer" / "check_env.py",
        REPO / "installer" / "config_patch.py",
        REPO / "installer" / "install.py",
    ]:
        content = path.read_text(encoding="utf-8")
        assert "v3.1.1" not in content


def test_remaining_runtime_scripts_use_agent_home_fallback():
    for path in [
        REPO / "scripts" / "memory_snapshot_backup.py",
        REPO / "scripts" / "memory_watermark.py",
        REPO / "scripts" / "memory_reflect.py",
        REPO / "scripts" / "memory_lifecycle.py",
    ]:
        content = path.read_text(encoding="utf-8")
        assert ".agent" in content


def test_legacy_runtime_helpers_respect_agent_home_env(tmp_path: Path, monkeypatch):
    agent_home = tmp_path / "agent-home"
    monkeypatch.setenv("AGENT_HOME", str(agent_home))

    def load_module(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        return module

    memory_guard = load_module("memory_guard_test", REPO / "scripts" / "memory_guard.py")
    memory_prewrite_guard = load_module("memory_prewrite_guard_test", REPO / "scripts" / "memory_prewrite_guard.py")
    sync_embeddings = load_module("sync_embeddings_test", REPO / "scripts" / "sync_embeddings.py")
    memory_watermark = load_module("memory_watermark_test", REPO / "scripts" / "memory_watermark.py")
    memory_lifecycle = load_module("memory_lifecycle_test", REPO / "scripts" / "memory_lifecycle.py")

    assert memory_guard.MEMORY_FILE == agent_home / "memory.json"
    assert memory_prewrite_guard.MEMORY_FILE == agent_home / "memory.json"
    assert sync_embeddings.STATE_DB == agent_home / "state.db"
    assert sync_embeddings.SEMANTICS_DB == agent_home / "semantics.db"
    assert memory_watermark.MEMORY_DIR == agent_home / "memories"
    assert memory_lifecycle.STATE_DB == agent_home / "state.db"
    assert memory_lifecycle.GBRAIN_DB == agent_home / "gbrain" / "brain.db"


def test_runtime_surfaces_do_not_contain_common_mojibake_markers():
    suspicious_tokens = [
        "鈥",
        "鍙",
        "妯",
        "鐢",
        "褰",
        "鑷",
        "寰俊",
        "鏈嬪弸",
        "鍏崇郴",
    ]
    for path in [
        REPO / "scripts" / "memory_family_registry.py",
        REPO / "scripts" / "memory_governance_rebuild.py",
        REPO / "scripts" / "tiered_context_injector.py",
        REPO / "scripts" / "memory_maintenance_cycle.py",
        REPO / "scripts" / "sidecar_acceptance_check.py",
        REPO / "installer" / "install.py",
        REPO / "README.md",
    ]:
        content = path.read_text(encoding="utf-8")
        for token in suspicious_tokens:
            assert token not in content, f"{path} contains suspicious mojibake token: {token}"


def test_release_docs_are_aligned_for_v3_5_1_and_kmm_positioning():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    readme_cn = (REPO / "README_CN.md").read_text(encoding="utf-8")
    manual = (REPO / "MANUAL_INSTALL.md").read_text(encoding="utf-8")
    release = (REPO / "docs" / "release-v3.5.1.md").read_text(encoding="utf-8")

    for content in (readme, readme_cn, manual):
        assert "3.5.1" in content
        assert "Knowledge-and-Memory-Management" in content

    assert "not installed by default" in readme
    assert "README_CN.md" in readme
    assert "How It Works" in readme
    assert "Repository Structure" in readme
    assert "Embedding Model Selection" in readme
    assert "Knowledge-and-Memory-Management" in readme
    assert "operational hardening release" in release
    assert "--install-mode 3" in release


def test_release_check_workflow_and_proxy_docs_exist():
    workflow = (REPO / ".github" / "workflows" / "release-check.yml").read_text(encoding="utf-8")
    proxy_doc = (REPO / "docs" / "dashboard-reverse-proxy.md").read_text(encoding="utf-8")
    checklist = (REPO / "docs" / "release-checklist.md").read_text(encoding="utf-8")

    assert "python -m pytest -q" in workflow
    assert "audit-repo" in workflow
    assert "release_checksums.py" in workflow
    assert "synthetic_recall_benchmark.py" in workflow
    assert "Profile isolation soak" in workflow
    assert "Authorization: Bearer" in proxy_doc
    assert "profile_isolation_soak.py" in checklist
    assert "release_checksums.py" in checklist
