from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def resolve_agent_home(env: dict[str, str] | None = None) -> Path:
    values = env if env is not None else os.environ
    return Path(values.get("AGENT_HOME") or values.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()


@dataclass(frozen=True)
class RuntimePaths:
    agent_home: Path
    sidecar_home: Path
    logs_dir: Path
    production_registry: Path
    governance_db: Path

    @classmethod
    def from_agent_home(cls, agent_home: str | Path | None = None) -> "RuntimePaths":
        home = Path(agent_home).expanduser() if agent_home is not None else resolve_agent_home()
        return cls(
            agent_home=home,
            sidecar_home=home / "memory-sidecar",
            logs_dir=home / "logs",
            production_registry=home / ".memory_eval" / "registry_production.py",
            governance_db=home / "memory_governance.db",
        )
