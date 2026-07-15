#!/usr/bin/env python3
"""Conservative load shedding for non-core browser automation."""

from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import signal
import subprocess
import time


AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
DEFAULT_LOG = Path(os.environ.get("HERMES_LOAD_SHEDDER_LOG", "/var/log/hermes-load-shedder.log"))


def read_load1() -> int:
    try:
        return int(float(Path("/proc/loadavg").read_text(encoding="utf-8").split()[0]))
    except (OSError, ValueError, IndexError):
        return 0


def read_swap_pct() -> int:
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith(("SwapTotal:", "SwapFree:")):
                key, raw = line.split(":", 1)
                values[key] = int(raw.strip().split()[0])
    except (OSError, ValueError, IndexError):
        return 0
    total = values.get("SwapTotal", 0)
    free = values.get("SwapFree", 0)
    return int((total - free) * 100 / total) if total > 0 else 0


def list_processes() -> tuple[dict[int, tuple[int, int, str]], dict[int, list[int]]]:
    output = subprocess.check_output(["ps", "-eo", "pid=,ppid=,etimes=,args="], text=True, errors="replace")
    processes: dict[int, tuple[int, int, str]] = {}
    children: dict[int, list[int]] = {}
    for line in output.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) < 4:
            continue
        pid, ppid, etimes, args = int(parts[0]), int(parts[1]), int(parts[2]), parts[3]
        processes[pid] = (ppid, etimes, args)
        children.setdefault(ppid, []).append(pid)
    return processes, children


def collect_tree(pid: int, children: dict[int, list[int]], out: set[int]) -> None:
    if pid in out:
        return
    out.add(pid)
    for child in children.get(pid, []):
        collect_tree(child, children, out)


def is_driver(args: str) -> bool:
    return ("patchright/driver" in args or "playwright/driver" in args) and "run-driver" in args


def is_persistent_profile(args: str) -> bool:
    return "/root/social-auto-upload/" in args or "persistent_profile" in args


def is_publish_runner(args: str) -> bool:
    markers = (
        "baijiahao_article_scheduled_runner.py",
        "publish_all.py",
        "social-auto-upload",
        "channel-publish",
    )
    return any(marker in args for marker in markers)


def renice_persistent(processes: dict[int, tuple[int, int, str]], dry_run: bool) -> list[int]:
    changed: list[int] = []
    for pid, (_, _, args) in processes.items():
        if not is_persistent_profile(args):
            continue
        changed.append(pid)
        if dry_run:
            continue
        subprocess.run(["renice", "+10", "-p", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ionice", "-c2", "-n7", "-p", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return sorted(changed)


def terminate_stale_temp_trees(
    processes: dict[int, tuple[int, int, str]],
    children: dict[int, list[int]],
    min_age_s: int,
    dry_run: bool,
) -> list[int]:
    killset: set[int] = set()
    for pid, (_, etimes, args) in processes.items():
        if not (is_driver(args) and etimes >= min_age_s):
            continue
        tree: set[int] = set()
        collect_tree(pid, children, tree)
        if any(is_persistent_profile(processes.get(tree_pid, (0, 0, ""))[2]) for tree_pid in tree):
            continue
        killset.update(tree)
    if dry_run or not killset:
        return sorted(killset)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in sorted(killset, reverse=True):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        time.sleep(1)
        if not any(Path(f"/proc/{pid}").exists() for pid in killset):
            break
    return sorted(killset)


def terminate_stale_persistent_trees(
    processes: dict[int, tuple[int, int, str]],
    children: dict[int, list[int]],
    min_age_s: int,
    critical: bool,
    dry_run: bool,
) -> list[int]:
    """Stop non-core persistent browser automation only under critical pressure.

    Persistent publishing browsers can consume more memory than the memory stack.
    They are still non-core: under critical host pressure, preserving gateway and
    memory services takes priority over finishing a browser publish attempt.
    """
    if not critical:
        return []
    killset: set[int] = set()
    for pid, (_, etimes, args) in processes.items():
        if not (is_driver(args) and etimes >= min_age_s):
            continue
        tree: set[int] = set()
        collect_tree(pid, children, tree)
        if not any(is_persistent_profile(processes.get(tree_pid, (0, 0, ""))[2]) for tree_pid in tree):
            continue
        killset.update(tree)
    if dry_run or not killset:
        return sorted(killset)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in sorted(killset, reverse=True):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        time.sleep(1)
        if not any(Path(f"/proc/{pid}").exists() for pid in killset):
            break
    return sorted(killset)


def terminate_publish_runners(
    processes: dict[int, tuple[int, int, str]],
    min_age_s: int,
    critical: bool,
    dry_run: bool,
) -> list[int]:
    if not critical:
        return []
    killset = {
        pid
        for pid, (_, etimes, args) in processes.items()
        if etimes >= min_age_s and is_publish_runner(args)
    }
    if dry_run or not killset:
        return sorted(killset)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in sorted(killset, reverse=True):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        time.sleep(1)
        if not any(Path(f"/proc/{pid}").exists() for pid in killset):
            break
    return sorted(killset)


def append_log(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line.rstrip() + "\n")


def run_once(
    load_threshold: int,
    swap_threshold: int,
    min_age_s: int,
    dry_run: bool,
    critical_load_threshold: int = 32,
    critical_swap_threshold: int = 95,
    persistent_min_age_s: int = 900,
    publisher_min_age_s: int = 0,
) -> dict:
    load1 = read_load1()
    swap_pct = read_swap_pct()
    processes, children = list_processes()
    pressure = load1 >= load_threshold or swap_pct >= swap_threshold
    critical = load1 >= critical_load_threshold or swap_pct >= critical_swap_threshold
    reniced = renice_persistent(processes, dry_run=dry_run) if pressure else []
    killed = terminate_stale_temp_trees(processes, children, min_age_s=min_age_s, dry_run=dry_run) if pressure else []
    killed_persistent = (
        terminate_stale_persistent_trees(
            processes,
            children,
            min_age_s=persistent_min_age_s,
            critical=critical,
            dry_run=dry_run,
        )
        if pressure
        else []
    )
    killed_publishers = (
        terminate_publish_runners(
            processes,
            min_age_s=publisher_min_age_s,
            critical=critical,
            dry_run=dry_run,
        )
        if pressure
        else []
    )
    return {
        "timestamp": datetime.now().strftime("%F %T"),
        "load1": load1,
        "swap_pct": swap_pct,
        "pressure": pressure,
        "critical": critical,
        "reniced_persistent": reniced,
        "terminated_stale_temp": killed,
        "terminated_stale_persistent": killed_persistent,
        "terminated_publish_runners": killed_publishers,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--load-threshold", type=int, default=int(os.environ.get("HERMES_LOAD_SHEDDER_LOAD_THRESHOLD", "16")))
    parser.add_argument("--swap-threshold", type=int, default=int(os.environ.get("HERMES_LOAD_SHEDDER_SWAP_THRESHOLD", "90")))
    parser.add_argument("--critical-load-threshold", type=int, default=int(os.environ.get("HERMES_LOAD_SHEDDER_CRITICAL_LOAD_THRESHOLD", "32")))
    parser.add_argument("--critical-swap-threshold", type=int, default=int(os.environ.get("HERMES_LOAD_SHEDDER_CRITICAL_SWAP_THRESHOLD", "95")))
    parser.add_argument("--min-age-s", type=int, default=int(os.environ.get("HERMES_LOAD_SHEDDER_MIN_AGE_S", "900")))
    parser.add_argument(
        "--persistent-min-age-s",
        type=int,
        default=int(os.environ.get("HERMES_LOAD_SHEDDER_PERSISTENT_MIN_AGE_S", "900")),
    )
    parser.add_argument(
        "--publisher-min-age-s",
        type=int,
        default=int(os.environ.get("HERMES_LOAD_SHEDDER_PUBLISHER_MIN_AGE_S", "0")),
    )
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run_once(
        args.load_threshold,
        args.swap_threshold,
        args.min_age_s,
        dry_run=args.dry_run,
        critical_load_threshold=args.critical_load_threshold,
        critical_swap_threshold=args.critical_swap_threshold,
        persistent_min_age_s=args.persistent_min_age_s,
        publisher_min_age_s=args.publisher_min_age_s,
    )
    append_log(
        Path(args.log).expanduser(),
        [
            (
                f"[{result['timestamp']}] load1={result['load1']} swap={result['swap_pct']}% "
                f"pressure={result['pressure']} critical={result['critical']} dry_run={result['dry_run']}"
            ),
            f"  reniced_persistent={result['reniced_persistent']}",
            f"  terminated_stale_temp={result['terminated_stale_temp']}",
            f"  terminated_stale_persistent={result['terminated_stale_persistent']}",
            f"  terminated_publish_runners={result['terminated_publish_runners']}",
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
