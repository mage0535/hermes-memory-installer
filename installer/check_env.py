"""Environment checks for Memory Sidecar v3.5."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def check_python() -> bool:
    return sys.version_info >= (3, 9)


def check_disk_space(min_free_gb: float = 1.0) -> bool:
    _, _, free = shutil.disk_usage(str(Path.home()))
    free_gb = free / (1024**3)
    return free_gb >= min_free_gb


def check_gbrain() -> bool:
    return shutil.which("gbrain") is not None


def run() -> bool:
    checks = {
        "python": check_python(),
        "disk_space": check_disk_space(),
        "gbrain_cli": check_gbrain(),
    }
    for name, ok in checks.items():
        print(f"{name}: {'ok' if ok else 'missing'}")
    return all(checks.values())


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
