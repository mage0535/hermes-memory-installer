from __future__ import annotations

from pathlib import Path
import importlib.util


REPO = Path(__file__).resolve().parent.parent


def load_report_module():
    path = REPO / "scripts" / "memory_eval_report.py"
    spec = importlib.util.spec_from_file_location("memory_eval_report_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Run:
    def __init__(self, acceptance_ok: bool, guardian_level: str):
        self.name = "memory-sidecar-monitor"
        self.start_time = None
        self.outputs = {
            "acceptance": {
                "payload": {
                    "ok": acceptance_ok,
                    "guardian": {
                        "level": guardian_level,
                        "hindsight_sync_lag_seconds": 900,
                    },
                    "recalls": [
                        {
                            "l2_count": 3,
                            "l3_count": 2,
                            "timings": {"total_s": 1.0},
                        }
                    ],
                }
            }
        }


def test_eval_report_uses_current_window_not_historical_failures():
    report = load_report_module()
    runs = [Run(True, "ok") for _ in range(5)] + [Run(False, "critical") for _ in range(8)]

    monitor = report.analyze_monitor_trend(runs)
    health = report.evaluate_health(monitor, {})

    assert monitor["acceptance_ok_rate"] == 0.385
    assert monitor["current_acceptance_ok_rate"] == 1.0
    assert monitor["guardian_levels"]["critical_count"] == 8
    assert health["level"] == "healthy"
    assert not any("critical" in issue for issue in health["issues"])


def test_memory_eval_report_declares_langsmith_dependency():
    requirements = (REPO / "requirements.txt").read_text(encoding="utf-8")

    assert any(line.strip().lower().startswith("langsmith") for line in requirements.splitlines())
