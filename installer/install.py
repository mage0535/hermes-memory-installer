"""Memory Sidecar Installer v3.5 - agent-agnostic, environment-aware.

Installs the production memory sidecar next to any AI agent (Hermes, Claude Code,
Cursor, Codex, etc.) without modifying the agent core.

The sidecar provides:
  - session archival to gbrain
  - Hindsight-backed fact recall
  - tiered context injection
  - Focused Dossier management for important people / projects / topics
  - optional semantic vector retrieval via embedding models
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import urlopen

import yaml

VERSION = "3.5"
DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
SIDECAR_DIRNAME = "memory-sidecar"

SUPPORTED_SCRIPT_NAMES = [
    "memory_family_registry.py",
    "memory_governance_rebuild.py",
    "memory_guardian.py",
    "memory_maintenance_cycle.py",
    "session_to_gbrain.py",
    "sidecar_acceptance_check.py",
    "tiered_context_injector.py",
    "archive_sessions.py",
    "auto_session_summary.py",
    "memory_observability_report.py",
    "state_db_schema.py",
    "knowledge_notes.py",
    "recall_samples.py",
]

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "environment_check_title": "== Environment Check ==",
        "status_ok": "OK",
        "status_fail": "FAIL",
        "python_required": "Python 3.9+ is required. Aborting.",
        "checks_failed_notice": (
            "Some checks failed. Memory recall needs PostgreSQL, Hindsight, and gbrain.\n"
            "The installer can still continue, or you can switch install modes for dependency help."
        ),
        "dry_run_title": "== Dry Run v{version} ==",
        "dry_run_agent_home": "  Agent home: {agent_home}",
        "dry_run_scripts_source": "  Scripts source: {src_dir}",
        "dry_run_scripts": "  Scripts to deploy: {scripts}",
        "dry_run_mode": "  Install mode: {install_mode}",
        "dry_run_lang": "  Language: {lang}",
        "agent_home_missing_1": "Agent home {agent_home} does not exist. Create it first, or set",
        "agent_home_missing_2": "AGENT_HOME environment variable to an existing agent directory.",
        "embedding_title": "== Embedding Model Selection ==",
        "embedding_intro": "Choose a model for semantic vector retrieval.",
        "embedding_custom_prompt": "Pick [1-6], or type c for custom (default: 1): ",
        "embedding_custom_id": "Enter a custom embedding model id: ",
        "installed_title": "== Memory Sidecar v{version} Installed ==",
        "installed_agent_home": "  Agent home:      {agent_home}",
        "installed_embedding": "  Embedding model: {embedding}",
        "installed_scripts": "  Scripts:         {count} deployed",
        "installed_config": "  Config:          {config_path} patched",
        "installed_profile": "  Profile:         {profile_path}",
        "next_steps": "Next steps:",
        "next_step_1": "  1. Ensure Hindsight, PostgreSQL, and gbrain are running",
        "next_step_2": "  2. Deploy your chosen embedding model service ({embedding})",
        "next_step_3": "  3. Run: python3 {agent_home}/scripts/session_to_gbrain.py --resume",
        "next_step_4": "  4. Schedule maintenance via cron or systemd timer",
        "architecture_note": "See ARCHITECTURE.md for the full memory stack layout.",
        "mode_1_title": "Mode 1: detect and guide only",
        "mode_2_title": "Mode 2: semi-automatic dependency assistance",
        "mode_3_title": "Mode 3: automatic dependency bootstrap",
        "dependency_missing_title": "Missing required dependencies: {deps}",
        "dependency_supported": "Bootstrap support detected for this host.",
        "dependency_not_supported": "Automatic bootstrap s navailable on this platform. Use install mode 1 or 2.",
        "dependency_mode_1_body": (
            "Mode 1 will not change your system. Review the missing dependencies above,\n"
            "install them manually, then re-run ./install.sh.\n"
            "If you want guided help, switch to --install-mode 2 or --install-mode 3."
        ),
        "dependency_mode_2_body": (
            "Mode 2 provides guided dependency assistance without forcing a full automatic bootstrap.\n"
            "Recommended next step: re-run with --install-mode 2 after reviewing the commands below.\n"
            "If you want the installer to try the automatic path first, use --install-mode 3."
        ),
        "dependency_mode_3_body": (
            "Mode 3 tries the automatic bootstrap path first. If it fails, switch to --install-mode 2, \n"
            "and if that still fails, switch to --install-mode 1 to finish dependency setup manually."
        ),
        "bootstrap_detected": "Bootstrap plan: platform={platform}, package_manager={package_manager}",
        "bootstrap_commands_title": "Suggested dependency commands:",
        "bootstrap_hints_title": "Additional setup hints:",
        "bootstrap_attempt_title": "== Automatic Dependency Bootstrap ==",
        "bootstrap_unsupported": "Automatic bootstrap is unavailable on this platform.",
        "bootstrap_dry_run": "Dry run: bootstrap commands were not executed.",
        "bootstrap_failed": "Automatic bootstrap failed",
        "bootstrap_mode_2_note": "Mode 2 does not execute commands automatically. Review and run them step by step.",
        "fallback_message": (
            "Install mode {failed_mode} failed: {reason}\n"
            "Next options:\n"
            "  - Retry with --install-mode 2 for guided dependency assistance\n"
            "  - Retry with --install-mode 1 for detection-only instructions"
        ),
    },
}


def _http_probe(url: str, timeout: int = 5) -> tuple[bool, str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
        return True, body[:120]
    except URLError as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)


def translate(lang: str, key: str, **kwargs: object) -> str:
    template = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)
    return template.format(**kwargs)


def resolve_language(args: argparse.Namespace) -> str:
    if getattr(args, "lang", "auto") in {"zh", "en"}:
        return args.lang
    locale = (os.environ.get("LC_ALL") or os.environ.get(