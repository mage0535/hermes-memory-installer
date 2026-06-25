#!/usr/bin/env python3
import gzip
import json
import shutil
import sqlite3
import subprocess
from datetime import datetime
import os
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.environ.get("AGENT_HOME", str(Path.home() / ".agent"))))
BACKUP_ROOT = HERMES_HOME / "backups" / "rolling"
FILES_TO_COPY = [
    HERMES_HOME / "state.db",
    HERMES_HOME / "memory_governance.db",
    HERMES_HOME / "memory_index.db",
    HERMES_HOME / "semantics.db",
    HERMES_HOME / "config.yaml",
    HERMES_HOME / ".env",
]


def sqlite_backup(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(src))
    try:
        backup_conn = sqlite3.connect(str(dest))
        try:
            conn.backup(backup_conn)
        finally:
            backup_conn.close()
    finally:
        conn.close()


def main() -> int:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_ROOT / ts
    target.mkdir(parents=True, exist_ok=True)
    manifest = {"created_at": ts, "files": [], "postgres_dump": None}

    for path in FILES_TO_COPY:
        if not path.exists():
            continue
        dest = target / path.name
        if path.suffix == ".db":
            sqlite_backup(path, dest)
        else:
            shutil.copy2(path, dest)
        manifest["files"].append({"source": str(path), "backup": str(dest), "size": dest.stat().st_size})

    dump_path = target / "hindsight.sql.gz"
    proc = subprocess.run(
        ["su", "-", "postgres", "-c", "pg_dump hindsight"],
        capture_output=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise SystemExit(f"pg_dump failed: {proc.stderr.decode('utf-8', 'replace')[:500]}")
    with gzip.open(dump_path, "wb") as gz:
        gz.write(proc.stdout)
    manifest["postgres_dump"] = {"backup": str(dump_path), "size": dump_path.stat().st_size}

    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "backup_dir": str(target),
                "files": manifest["files"],
                "postgres_dump": manifest["postgres_dump"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
