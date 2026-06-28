#!/usr/bin/env python3
"""Rotate dashboard token and update dependent configs."""
import json, os, secrets, shutil, string
from pathlib import Path
from datetime import datetime, timezone

AGENT_HOME = Path(os.environ.get("AGENT_HOME", str(Path.home() / ".hermes")))
TOKEN_FILE = AGENT_HOME / "private" / "dashboard-token"
TOKEN_HISTORY = AGENT_HOME / "private" / "dashboard-token-history.jsonl"
PROMETHEUS_YML = Path(os.environ.get("MEMORY_REPO_ROOT", str(Path.home() / "hermes-memory-installer"))) / "deploy" / "observability" / "prometheus.yml"
DRY_RUN = os.environ.get("TOKEN_ROTATE_DRY_RUN", "") == "1"

def generate_token(length=43):
    alphabet = string.ascii_letters + string.digits + "-_"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def main():
    old_token = TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else None
    new_token = generate_token()

    if DRY_RUN:
        print(json.dumps({"ok": True, "dry_run": True, "old_token_age": "static"}))
        return 0

    # Backup old token
    if old_token:
        TOKEN_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_HISTORY, "a") as f:
            f.write(json.dumps({
                "rotated_at": datetime.now(timezone.utc).isoformat(),
                "old_prefix": old_token[:8] + "...",
                "new_prefix": new_token[:8] + "...",
            }) + "\n")

    # Write new token
    TOKEN_FILE.write_text(new_token)

    # Update prometheus config
    if PROMETHEUS_YML.exists() and old_token:
        content = PROMETHEUS_YML.read_text()
        if old_token in content:
            PROMETHEUS_YML.write_text(content.replace(old_token, new_token))

    print(json.dumps({"ok": True, "new_prefix": new_token[:8] + "...", "next": "restart metrics-dashboard and prometheus services"}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
