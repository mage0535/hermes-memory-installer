"""
Memory Sidecar Installer v3.1.0 — agent-agnostic, environment-aware.

Installs the production memory sidecar next to any AI agent (Hermes, Claude Code,
Cursor, Codex, etc.) without modifying the agent core.

The sidecar provides:
  - session archival to gbrain
  - Hindsight-backed fact recall
  - tiered context injection
  - Focused Dossier management for important people / projects / topics
  - optional semantic vector retrieval via embedding models
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

VERSION = "3.1.0"
DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
SIDECAR_DIRNAME = "memory-sidecar"

SUPPORTED_SCRIPT_NAMES = [
    "memory_family_registry.py",
    "memory_governance_rebuild.py",
    "memory_guardian.py",
    "memory_maintenance_cycle.py",
    "session_to_gbrain.py",
    "sidecar_acceptance_check.py",
    "tiered_context_injector.py",
]


@dataclass(frozen=True)
class EmbeddingModel:
    key: str
    model_id: str
    languages: str
    dimension: str
    approx_size: str
    best_for: str
    recommended: bool = False


EMBEDDING_MODELS: dict[str, EmbeddingModel] = {
    "1": EmbeddingModel(
        key="1",
        model_id="intfloat/multilingual-e5-small",
        languages="100+ languages",
        dimension="384d",
        approx_size="~470MB",
        best_for="Default. Balanced multilingual recall for mixed-language deployments.",
        recommended=True,
    ),
    "2": EmbeddingModel(
        key="2",
        model_id="BAAI/bge-small-zh-v1.5",
        languages="Chinese focused",
        dimension="512d",
        approx_size="~96MB",
        best_for="Lightweight Chinese-first deployment with tight memory budget.",
    ),
    "3": EmbeddingModel(
        key="3",
        model_id="paraphrase-multilingual-MiniLM-L12-v2",
        languages="50+ languages",
        dimension="384d",
        approx_size="~471MB",
        best_for="Mature sentence-transformers ecosystem, broad language coverage.",
    ),
    "4": EmbeddingModel(
        key="4",
        model_id="Alibaba-NLP/gte-multilingual-base",
        languages="75+ languages",
        dimension="768d",
        approx_size="~610MB",
        best_for="Higher recall quality when you have comfortable RAM headroom.",
    ),
    "5": EmbeddingModel(
        key="5",
        model_id="sentence-transformers/LaBSE",
        languages="109 languages",
        dimension="768d",
        approx_size="~471MB",
        best_for="Cross-lingual alignment: Chinese queries matching English content.",
    ),
    "6": EmbeddingModel(
        key="6",
        model_id="BAAI/bge-m3",
        languages="100+ languages",
        dimension="1024d",
        approx_size="~2GB",
        best_for="Maximum recall precision. Needs abundant disk and RAM.",
    ),
}

# ── environment checks ────────────────────────────────────────────────

def _run(cmd: list[str], timeout: int = 10) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def check_python() -> tuple[bool, str]:
    ok = sys.version_info >= (3, 9)
    detail = f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return ok, detail


def check_hindsight() -> tuple[bool, str]:
    """Check if Hindsight is reachable at localhost:8890/health."""
    code, out = _run(["curl", "-sf", "http://localhost:8890/health"])
    if code == 0:
        return True, f"Hindsight reachable — {out[:120]}"
    return False, "Hindsight not reachable at http://localhost:8890. Is it running?"


def check_gbrain() -> tuple[bool, str]:
    """Check gbrain MCP endpoint."""
    code, _ = _run(["curl", "-sf", "http://localhost:8787/health"])
    if code == 0:
        return True, "gbrain MCP reachable at http://localhost:8787"
    # Fallback: check CLI
    gbrain = shutil.which("gbrain")
    if gbrain:
        return True, f"gbrain CLI found at {gbrain} (health endpoint not responding)"
    return False, "gbrain not found. Install from https://github.com/hi-ogawa/gbrain"


def check_postgres() -> tuple[bool, str]:
    """Check PostgreSQL connectivity."""
    pg_host = os.environ.get("PGHOST", "localhost")
    pg_port = os.environ.get("PGPORT", "5432")
    code, out = _run(
        ["pg_isready", "-h", pg_host, "-p", pg_port],
        timeout=5,
    )
    if code == 0:
        return True, f"PostgreSQL ready at {pg_host}:{pg_port}"
    return False, f"PostgreSQL not responding at {pg_host}:{pg_port}"


def check_embedding_service() -> tuple[bool, str]:
    """Check if an embedding service is already running."""
    embed_url = os.environ.get(
        "EMBEDDING_API_URL",
        "http://localhost:8766/health",
    )
    code, out = _run(["curl", "-sf", embed_url])
    if code == 0:
        return True, f"Embedding service reachable at {embed_url}"
    return False, "No embedding service detected — will be configured separately."


def run_environment_checks() -> dict[str, tuple[bool, str]]:
    """Run all checks, return results. Install continues on warnings — only
    Python version is a hard fail."""
    checks = {}
    for name, fn in [
        ("python", check_python),
        ("postgres", check_postgres),
        ("hindsight", check_hindsight),
        ("gbrain", check_gbrain),
        ("embedding", check_embedding_service),
    ]:
        try:
            checks[name] = fn()
        except Exception as exc:
            checks[name] = (False, f"check failed: {exc}")
    return checks


def print_environment_report(checks: dict) -> int:
    """Print check results. Returns number of failures."""
    print("\n── Environment Check ──")
    failures = 0
    for name, (ok, detail) in checks.items():
        mark = "✓" if ok else "✗"
        print(f"  {mark} {name}: {detail}")
        if not ok:
            failures += 1
    return failures


# ── cli ───────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Memory Sidecar Installer v{VERSION} — works with any AI agent",
    )
    parser.add_argument(
        "--agent-home",
        default=None,
        help="Target agent home directory (e.g., ~/.hermes, ~/.claude). "
             "Overrides AGENT_HOME / HERMES_HOME env vars.",
    )
    parser.add_argument(
        "--embedding",
        default=None,
        help="Embedding model ID. Omit for interactive selection.",
    )
    parser.add_argument(
        "--noninteractive",
        action="store_true",
        help="Skip prompts, use default recommended embedding model.",
    )
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip environment checks (not recommended).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run checks and show what would be installed, without touching files.",
    )
    return parser.parse_args(argv)


def choose_embedding_model(args: argparse.Namespace) -> EmbeddingModel:
    if args.embedding:
        return EmbeddingModel(
            key="custom", model_id=args.embedding,
            languages="custom", dimension="unknown",
            approx_size="unknown", best_for="User-supplied model",
        )
    if args.noninteractive:
        return EMBEDDING_MODELS["1"]

    print("\n── Embedding Model Selection ──")
    print("Choose a model for semantic vector retrieval.\n")
    for key, m in EMBEDDING_MODELS.items():
        star = " ★" if m.recommended else "  "
        print(f"  [{key}]{star} {m.model_id}")
        print(f"         {m.languages} | {m.dimension} | {m.approx_size}")
        print(f"         {m.best_for}\n")
    choice = input("Pick [1-6] (default: 1): ").strip() or "1"
    return EMBEDDING_MODELS.get(choice, EMBEDDING_MODELS["1"])


# ── helpers ───────────────────────────────────────────────────────────

def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def scripts_source_dir() -> Path:
    return repo_root() / "scripts"


def resolve_agent_home(args: argparse.Namespace) -> Path:
    if args.agent_home:
        return Path(args.agent_home).expanduser()
    env_val = os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME")
    if env_val:
        return Path(env_val).expanduser()
    # Sensible fallback
    return Path.home() / ".agent"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def save_yaml(path: Path, payload: dict) -> None:
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def patch_agent_config(agent_home: Path) -> Path | None:
    """Optionally patch the agent config to enable memory sidecar.

    Looks for common config names: config.yaml, config.json, claude_config.json.
    If none found, creates a sidecar-only config note.
    """
    candidates = [
        agent_home / "config.yaml",
        agent_home / "config.json",
        agent_home / "claude_config.json",
    ]
    config_path = None
    for c in candidates:
        if c.exists():
            config_path = c
            break

    if config_path is None:
        # No recognizable config — create a sidecar setup note
        note = agent_home / SIDECAR_DIRNAME / "config-note.txt"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(
            f"Memory Sidecar v{VERSION} installed.\n"
            "No agent config detected. Add the sidecar scripts path to your agent's\n"
            "startup hook or run them via cron.\n\n"
            f"Scripts: {agent_home / 'scripts'}\n"
        )
        return None

    if config_path.suffix == ".yaml":
        config = load_yaml(config_path)
    else:
        config = {}
        try:
            raw = config_path.read_text()
            config = json.loads(raw)
        except Exception:
            pass

    config.setdefault("memory", {})
    config["memory"]["provider"] = "hindsight"
    config.setdefault("memory_sidecar", {})
    config["memory_sidecar"]["version"] = VERSION
    config["memory_sidecar"]["scripts_dir"] = str(agent_home / "scripts")

    if config_path.suffix == ".yaml":
        save_yaml(config_path, config)
    elif config_path.suffix == ".json":
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

    return config_path


def deploy_scripts(src_dir: Path, dest_dir: Path) -> list[str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    installed = []
    for name in SUPPORTED_SCRIPT_NAMES:
        src = src_dir / name
        if not src.exists():
            print(f"[installer] skipping {name} — not in source repo", file=sys.stderr)
            continue
        dst = dest_dir / name
        try:
            shutil.copy2(src, dst)
            if src.suffix == ".py":
                dst.chmod(0o755)
            installed.append(name)
        except OSError as exc:
            print(f"[installer] failed to deploy {name}: {exc}", file=sys.stderr)
            raise
    return installed


def write_install_profile(
    agent_home: Path, embedding: EmbeddingModel, installed_scripts: list[str],
) -> Path:
    sidecar_dir = agent_home / SIDECAR_DIRNAME
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": VERSION,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": asdict(embedding),
        "installed_scripts": installed_scripts,
    }
    path = sidecar_dir / "install-profile.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ── main ──────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    agent_home = resolve_agent_home(args)
    src_dir = scripts_source_dir()

    # 1. Environment checks (unless skipped)
    if not args.skip_checks:
        checks = run_environment_checks()
        failures = print_environment_report(checks)
        if not checks["python"][0]:
            print("\nPython 3.9+ is required. Aborting.")
            return 1
        if failures > 0:
            print(
                "\nSome checks failed. The sidecar can still install, but those\n"
                "services (Hindsight, gbrain, PostgreSQL) must be running for memory\n"
                "recall to work. You can fix them later and re-run the script."
            )
    else:
        checks = {}

    if args.dry_run:
        print(f"\n── Dry Run ── v{VERSION}")
        print(f"  Agent home: {agent_home}")
        print(f"  Scripts source: {src_dir}")
        print(f"  Scripts to deploy: {SUPPORTED_SCRIPT_NAMES}")
        return 0

    # 2. Check agent home exists or create it
    if not agent_home.exists():
        print(f"Agent home {agent_home} does not exist. Create it first, or set")
        print("AGENT_HOME environment variable to an existing agent directory.")
        return 1

    # 3. Embedding model selection
    embedding = choose_embedding_model(args)

    # 4. Deploy scripts
    installed_scripts = deploy_scripts(src_dir, agent_home / "scripts")

    # 5. Patch config (optional — agent may not have config.yaml)
    config_path = patch_agent_config(agent_home)

    # 6. Write install profile
    profile_path = write_install_profile(agent_home, embedding, installed_scripts)

    # 7. Report
    print(f"\n── Memory Sidecar v{VERSION} Installed ──")
    print(f"  Agent home:      {agent_home}")
    print(f"  Embedding model: {embedding.model_id}")
    print(f"  Scripts:         {len(installed_scripts)} deployed")
    if config_path:
        print(f"  Config:          {config_path} patched")
    print(f"  Profile:         {profile_path}")
    print()
    print("Next steps:")
    print(f"  1. Ensure Hindsight, PostgreSQL, and gbrain are running")
    print(f"  2. Deploy your chosen embedding model service ({embedding.model_id})")
    print(f"  3. Run: python3 {agent_home}/scripts/session_to_gbrain.py --resume")
    print(f"  4. Schedule maintenance via cron or systemd timer")
    print("")
    print("See ARCHITECTURE.md for the full memory stack layout.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
