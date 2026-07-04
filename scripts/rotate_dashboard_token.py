#!/usr/bin/env python3
"""Rotate dashboard token and restart dependents so auth stays consistent."""

from __future__ import annotations

import json
import os
import secrets
import string
import subprocess
from datetime import datetime, timezone
from pathlib import Path

AGENT_HOME = Path(os.environ.get("AGENT_HOME", str(Path.home() / ".hermes")))
TOKEN_FILE = AGENT_HOME / "private" / "dashboard-token"
TOKEN_HISTORY = AGENT_HOME / "private" / "dashboard-token-history.jsonl"
REPO_ROOT = Path(os.environ.get("MEMORY_REPO_ROOT", str(Path.home() / "hermes-memory-installer")))
PROMETHEUS_CONFIGS = [
    REPO_ROOT / "deploy" / "observability" / "prometheus.yml",
    AGENT_HOME / "observability" / "prometheus.yml",
]
DRY_RUN = os.environ.get("TOKEN_ROTATE_DRY_RUN", "") == "1"


def generate_token(length: int = 43) -> str:
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def replace_token_in_file(path: Path, old_token: str, new_token: str) -> bool:
    if not old_token or not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    if old_token not in content:
        return False
    path.write_text(content.replace(old_token, new_token), encoding="utf-8")
    return True


def run_step(cmd: list[str]) -> dict:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as exc:
        return {"command": cmd, "ok": False, "error": str(exc)}
    return {
        "command": cmd,
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout[-400:],
        "stderr": result.stderr[-400:],
    }


def main() -> int:
    old_token = TOKEN_FILE.read_text(encoding="utf-8").strip() if TOKEN_FILE.exists() else None
    new_token = generate_token()

    if DRY_RUN:
        print(json.dumps({"ok": True, "dry_run": True, "token_file": str(TOKEN_FILE)}))
        return 0

    TOKEN_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    if old_token:
        with TOKEN_HISTORY.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "rotated_at": datetime.now(timezone.utc).isoformat(),
                        "old_prefix": old_token[:8] + "...",
                        "new_prefix": new_token[:8] + "...",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    TOKEN_FILE.write_text(new_token, encoding="utf-8")

    updated_configs = []
    for config_path in PROMETHEUS_CONFIGS:
        if replace_token_in_file(config_path, old_token or "", new_token):
            updated_configs.append(str(config_path))

    restarts = [
        run_step(["systemctl", "restart", "hermes-metrics-dashboard.service"]),
    ]
    if (AGENT_HOME / "observability" / "docker-compose.yml").exists():
        restarts.append(
            run_step(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(AGENT_HOME / "observability" / "docker-compose.yml"),
                    "restart",
                    "prometheus",
                ]
            )
        )

    ok = all(step.get("ok") for step in restarts)
    payload = {
        "ok": ok,
        "new_prefix": new_token[:8] + "...",
        "token_file": str(TOKEN_FILE),
        "updated_prometheus_configs": updated_configs,
        "restart_steps": restarts,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
