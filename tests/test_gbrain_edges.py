import subprocess

import pytest

from gbrain_edges.models import EdgeCandidate
from gbrain_edges.planner import apply_edges, plan_edges


def test_planner_deduplicates_orders_and_budgets():
    candidates = [EdgeCandidate("a", "b", "semantic", .8, "x"), EdgeCandidate("a", "b", "semantic", .9, "y"), EdgeCandidate("a", "c", "semantic", .7, "z")]
    assert plan_edges(candidates, set(), top_k=1) == [candidates[1]]


def test_dry_run_never_invokes_subprocess(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("write called"))
    assert apply_edges([EdgeCandidate("a", "b", "semantic", .9, "x")], apply=False) == 0
