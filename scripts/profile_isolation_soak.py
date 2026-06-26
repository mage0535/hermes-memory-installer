#!/usr/bin/env python3
"""Run a two-profile isolation soak without touching production state."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run_command(cmd: list[str], env: dict[str, str], timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    return {
        "command": cmd,
        "returncode": result.returncode,
        "elapsed_s": round(time.monotonic() - started, 3),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def write_minimal_metrics(metrics_dir: Path) -> None:
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "runtime-drift-latest.json").write_text(json.dumps({"status": "healthy", "reasons": []}), encoding="utf-8")
    (metrics_dir / "langsmith-trend-latest.json").write_text(
        json.dumps({"monitor": {"lag": {"status": "healthy"}, "recent_acceptance_ok_rate": 1.0, "acceptance_ok_rate": 1.0}}),
        encoding="utf-8",
    )
    (metrics_dir / "gbrain-stale-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
    (metrics_dir / "hindsight-security-latest.json").write_text(json.dumps({"status": "healthy"}), encoding="utf-8")


def soak(repo_root: Path, iterations: int, interval_s: float, timeout: int) -> dict[str, Any]:
    rows = []
    with tempfile.TemporaryDirectory(prefix="memory-profile-soak-") as tmp:
        root = Path(tmp)
        profiles = [root / "agent-a", root / "agent-b"]
        for profile in profiles:
            (profile / "scripts").mkdir(parents=True)
            write_minimal_metrics(profile / "metrics")

        for index in range(iterations):
            for profile in profiles:
                env = {**os.environ, "AGENT_HOME": str(profile)}
                manifest = run_command(
                    [sys.executable, str(repo_root / "bin" / "hermes-memory"), "manifest", "--format", "json", "--repo-root", str(repo_root)],
                    env,
                    timeout,
                )
                alert = run_command(
                    [
                        sys.executable,
                        str(repo_root / "scripts" / "alert_queue.py"),
                        "--metrics-dir",
                        str(profile / "metrics"),
                        "--alerts",
                        str(profile / "metrics" / "alerts.jsonl"),
                        "--status-output",
                        str(profile / "metrics" / "health-summary-latest.json"),
                    ],
                    env,
                    timeout,
                )
                rows.append({"iteration": index + 1, "profile": str(profile), "manifest": manifest, "alert": alert})
            if interval_s:
                time.sleep(interval_s)

    failures = [
        row
        for row in rows
        if row["manifest"]["returncode"] != 0
        or row["alert"]["returncode"] != 0
        or json.loads(row["manifest"]["stdout"]).get("agent_home") != row["profile"]
    ]
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "ok": not failures,
        "iterations": iterations,
        "profile_count": 2,
        "failures": failures,
        "runs": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--interval-s", type=float, default=0.1)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    report = soak(Path(args.repo_root).expanduser(), args.iterations, args.interval_s, args.timeout)
    if args.output:
        path = Path(args.output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
