#!/usr/bin/env python3
"""Compress runtime state snapshots into restorable tar.gz archives."""

from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path


def snapshot_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted([path for path in root.iterdir() if path.is_dir()], key=lambda item: item.stat().st_mtime, reverse=True)


def compress_snapshot(snapshot_dir: Path, *, dry_run: bool = False, remove_source: bool = False) -> dict:
    archive_path = snapshot_dir.with_suffix(".tar.gz")
    size_bytes = sum(item.stat().st_size for item in snapshot_dir.rglob("*") if item.is_file())
    payload = {
        "snapshot_dir": str(snapshot_dir),
        "archive_path": str(archive_path),
        "source_size_bytes": size_bytes,
        "archive_exists": archive_path.exists(),
        "compressed": False,
        "removed_source": False,
        "dry_run": dry_run,
    }
    if dry_run:
        return payload
    with tarfile.open(archive_path, "w:gz") as handle:
        handle.add(snapshot_dir, arcname=snapshot_dir.name)
    payload["archive_exists"] = archive_path.exists()
    payload["compressed"] = True
    if remove_source:
        for item in sorted(snapshot_dir.rglob("*"), reverse=True):
            if item.is_file() or item.is_symlink():
                item.unlink(missing_ok=True)
            elif item.is_dir():
                item.rmdir()
        snapshot_dir.rmdir()
        payload["removed_source"] = True
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--remove-source", action="store_true")
    args = parser.parse_args()

    payload = compress_snapshot(Path(args.snapshot_dir).expanduser(), dry_run=args.dry_run, remove_source=args.remove_source)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
