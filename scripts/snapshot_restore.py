#!/usr/bin/env python3
"""Restore a compressed runtime snapshot archive into a target directory."""

from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path


def restore_archive(archive_path: Path, target_dir: Path, *, dry_run: bool = False) -> dict:
    payload = {
        "archive_path": str(archive_path),
        "target_dir": str(target_dir),
        "archive_exists": archive_path.exists(),
        "restored": False,
        "dry_run": dry_run,
    }
    if not archive_path.exists():
        return payload
    if dry_run:
        return payload
    target_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as handle:
        handle.extractall(target_dir)
    payload["restored"] = True
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = restore_archive(Path(args.archive).expanduser(), Path(args.target_dir).expanduser(), dry_run=args.dry_run)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["archive_exists"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
