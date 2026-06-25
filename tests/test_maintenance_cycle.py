#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
import importlib
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import memory_maintenance_cycle as cycle


def test_governance_rebuild_command_omits_force_by_default(monkeypatch):
    monkeypatch.delenv("MEMORY_MAINTENANCE_FORCE_REBUILD", raising=False)
    reloaded = importlib.reload(cycle)

    cmd = reloaded.governance_rebuild_command()

    assert "--quiet" in cmd
    assert "--force" not in cmd


def test_governance_rebuild_command_includes_force_when_env_enabled(monkeypatch):
    monkeypatch.setenv("MEMORY_MAINTENANCE_FORCE_REBUILD", "true")
    reloaded = importlib.reload(cycle)

    cmd = reloaded.governance_rebuild_command()

    assert "--force" in cmd

    monkeypatch.delenv("MEMORY_MAINTENANCE_FORCE_REBUILD", raising=False)
    importlib.reload(cycle)


def test_should_run_daily_snapshot_recovers_when_narrow_window_is_missed(tmp_path: Path):
    stamp = tmp_path / ".snapshot-last-run"
    now = datetime(2026, 6, 19, 11, 30, 0)

    assert cycle.should_run_daily_snapshot(now, stamp) is True

    stamp.write_text("2026-06-19", encoding="utf-8")
    assert cycle.should_run_daily_snapshot(now, stamp) is False

    stamp.write_text("2026-06-18", encoding="utf-8")
    assert cycle.should_run_daily_snapshot(now, stamp) is True
