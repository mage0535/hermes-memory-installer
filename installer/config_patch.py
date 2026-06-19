"""Config patch helpers for Memory Sidecar v3.5."""

from __future__ import annotations

import os
from pathlib import Path

import yaml


DEFAULT_SKILLS = [
    "memory-starter-kit",
    "memory-archivist",
    "memory-proactive",
]


def patch(config_path: Path | None = None, profile: str = "hybrid") -> bool:
    if config_path is None:
        agent_home = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".agent"))).expanduser()
        config_path = agent_home / "config.yaml"
    if not config_path.exists():
        return False

    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    changed = False

    config.setdefault("memory", {})
    if config["memory"].get("provider") != "hindsight":
        config["memory"]["provider"] = "hindsight"
        changed = True

    skills = list(config.get("skills") or [])
    for skill in DEFAULT_SKILLS:
        if skill not in skills:
            skills.append(skill)
            changed = True
    config["skills"] = skills

    config.setdefault("memory_sidecar", {})
    if config["memory_sidecar"].get("version") != "3.5":
        config["memory_sidecar"]["version"] = "3.5"
        changed = True
    if config["memory_sidecar"].get("profile") != profile:
        config["memory_sidecar"]["profile"] = profile
        changed = True

    if changed:
        config_path.write_text(
            yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    return changed


if __name__ == "__main__":
    raise SystemExit(0 if patch() else 1)
