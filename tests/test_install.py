#!/usr/bin/env python3
"""Installer tests for the v3.0 sidecar project."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from installer import install


def test_version_is_3_0():
    assert install.VERSION == "3.0"


def test_supported_script_set_matches_repo():
    scripts_dir = install.scripts_source_dir()
    missing = install.check_required_scripts(scripts_dir)
    assert missing == []


def test_embedding_catalog_has_recommended_default():
    recommended = [model for model in install.EMBEDDING_MODELS.values() if model.recommended]
    assert len(recommended) == 1
    assert recommended[0].model_id == install.DEFAULT_EMBEDDING_MODEL


def test_parse_args_is_import_safe_and_defaults_are_hybrid():
    args = install.parse_args(["--noninteractive"])
    assert args.profile == "hybrid"
    assert args.noninteractive is True


def test_patch_config_adds_sidecar_settings(tmp_path: Path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    config_path = hermes_home / "config.yaml"
    config_path.write_text("skills:\n  - existing-skill\n", encoding="utf-8")

    updated_path = install.patch_config(hermes_home, "hybrid")
    payload = yaml.safe_load(updated_path.read_text(encoding="utf-8"))

    assert payload["memory"]["provider"] == "hindsight"
    assert "existing-skill" in payload["skills"]
    assert "memory-starter-kit" in payload["skills"]
    assert "memory-archivist" in payload["skills"]
    assert "memory-proactive" in payload["skills"]
    assert payload["memory_sidecar"]["version"] == "3.0"
    assert payload["memory_sidecar"]["profile"] == "hybrid"


def test_write_install_profile_records_embedding_metadata(tmp_path: Path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    model = install.EMBEDDING_MODELS["1"]

    profile_path = install.write_install_profile(
        hermes_home,
        "hybrid",
        model,
        ["memory_guardian.py", "tiered_context_injector.py"],
    )
    payload = json.loads(profile_path.read_text(encoding="utf-8"))

    assert payload["version"] == "3.0"
    assert payload["profile"] == "hybrid"
    assert payload["embedding_model"]["model_id"] == model.model_id
    assert payload["installed_scripts"] == ["memory_guardian.py", "tiered_context_injector.py"]
