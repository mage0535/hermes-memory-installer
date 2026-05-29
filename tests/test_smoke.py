#!/usr/bin/env python3
"""Repository smoke tests for the v3.0 sidecar project."""

from __future__ import annotations

import py_compile
from pathlib import Path
import sys

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
        REPO / "install.sh",
        REPO / "install_cli.sh",
        REPO / "installer" / "install.py",
        REPO / "bin" / "hermes-memory",
    ]
    for path in expected:
        assert path.exists(), f"Missing required file: {path}"


def test_supported_scripts_compile():
    for name in install.SUPPORTED_SCRIPT_NAMES:
        py_compile.compile(str(REPO / "scripts" / name), doraise=True)


def test_wrapper_scripts_compile():
    py_compile.compile(str(REPO / "installer" / "install.py"), doraise=True)
    py_compile.compile(str(REPO / "installer" / "check_env.py"), doraise=True)
    py_compile.compile(str(REPO / "installer" / "config_patch.py"), doraise=True)
    py_compile.compile(str(REPO / "bin" / "hermes-memory"), doraise=True)
