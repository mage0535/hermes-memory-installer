#!/usr/bin/env python3
"""Prune old runtime snapshots and oversized historical logs conservatively."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
DEFAULT_SNAPSHOT_DIR = AGENT_HOME / "state-snapshots"
DEFAULT_LOG_DIR = Path("/var/log")


def snapshot_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted([path for path in root.iterdir() if path.is_dir()], key=lambda item: item.stat().st_mtime, reverse=True)


def prune_snapshots(root: Path, keep: int, min_age_days: int, dry_run: bool) -> list[dict]:
    removed = []
    now = time.time()
    min_age_seconds = max(0, min_age_days) * 86400
    for index, path in enumerate(snapshot_dirs(root)):
        if index < keep:
            continue
        age_seconds = now - path.stat().st_mtime
        if age_seconds < min_age_seconds:
            continue
        size_bytes = sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
        removed.append({"path": str(path), "size_bytes": size_bytes})
        if not dry_run:
            for item in sorted(path.rglob("*"), reverse=True):
                if item.is_file() or item.is_symlink():
                    item.unlink(missing_ok=True)
                elif item.is_dir():
                    item.rmdir()
            path.rmdir()
    return removed


def truncate_logs(log_dir: Path, patterns: list[str], threshold_mb: int, dry_run: bool) -> list[dict]:
    touched = []
    if not log_dir.exists():
        return touched
    threshold_bytes = threshold_mb * 1024 * 1024
    for pattern in patterns:
        for path in log_dir.glob(pattern):
            if not path.is_file():
                continue
            size_bytes = path.stat().st_size
            if size_bytes <= threshold_bytes:
                continue
            touched.append({"path": str(path), "size_bytes": size_bytes})
            if not dry_run:
                path.write_bytes(b"")
    return touched


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", default=str(DEFAULT_SNAPSHOT_DIR))
    parser.add_argument("--keep", type=int, default=int(os.environ.get("MEMORY_SNAPSHOT_KEEP", "1")))
    parser.add_argument("--min-age-days", type=int, default=int(os.environ.get("MEMORY_SNAPSHOT_MIN_AGE_DAYS", "2")))
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--log-threshold-mb", type=int, default=int(os.environ.get("MEMORY_LOG_TRUNCATE_MB", "32")))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = {
        "ok": True,
        "snapshot_dir": str(Path(args.snapshot_dir).expanduser()),
        "removed_snapshots": prune_snapshots(Path(args.snapshot_dir).expanduser(), args.keep, args.min_age_days, args.dry_run),
        "truncated_logs": truncate_logs(Path(args.log_dir).expanduser(), ["gbrain-embed*.log"], args.log_threshold_mb, args.dry_run),
        "dry_run": args.dry_run,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
