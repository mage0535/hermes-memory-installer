#!/usr/bin/env python3
"""Create and verify SHA-256 checksums for public release entrypoints."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILES = [
    "install.sh",
    "install_cli.sh",
    "installer/install.py",
    "installer/check_env.py",
    "installer/config_patch.py",
    "bin/hermes-memory",
    "scripts/slo_rollup.py",
    "docs/grafana/hermes-memory-openmetrics-dashboard.json",
    "README.md",
    "README_CN.md",
    "ARCHITECTURE.md",
    "ARCHITECTURE_CN.md",
    "MANUAL_INSTALL.md",
    "MANUAL_INSTALL_CN.md",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_checksums(repo_root: Path, files: list[str]) -> list[tuple[str, str]]:
    rows = []
    for name in files:
        path = repo_root / name
        if not path.is_file():
            raise FileNotFoundError(name)
        rows.append((sha256_file(path), name.replace("\\", "/")))
    return rows


def format_checksums(rows: list[tuple[str, str]]) -> str:
    return "".join(f"{digest}  {name}\n" for digest, name in rows)


def parse_checksums(path: Path) -> list[tuple[str, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        digest, name = stripped.split(None, 1)
        rows.append((digest, name.strip()))
    return rows


def verify_checksums(repo_root: Path, checksum_file: Path) -> tuple[bool, list[dict[str, str]]]:
    mismatches = []
    for expected, name in parse_checksums(checksum_file):
        actual = sha256_file(repo_root / name)
        if actual != expected:
            mismatches.append({"path": name, "expected": expected, "actual": actual})
    return len(mismatches) == 0, mismatches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--output", help="Write checksum file")
    parser.add_argument("--verify", help="Verify an existing checksum file")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("files", nargs="*", help="Release files to checksum")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    files = args.files or DEFAULT_FILES

    if args.verify:
        ok, mismatches = verify_checksums(repo_root, Path(args.verify).expanduser())
        payload = {"ok": ok, "mismatches": mismatches}
        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"ok={str(ok).lower()} mismatches={len(mismatches)}")
        return 0 if ok else 1

    rows = build_checksums(repo_root, files)
    text = format_checksums(rows)
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    if args.format == "json":
        print(json.dumps({"ok": True, "count": len(rows), "output": args.output, "checksums": rows}, ensure_ascii=False, indent=2))
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
