"""Hermes Memory Sidecar Installer v3.0."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

VERSION = "3.0"
DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_PROFILE = "hybrid"
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
        best_for="Best default for mixed Chinese/English Hermes deployments",
        recommended=True,
    ),
    "2": EmbeddingModel(
        key="2",
        model_id="BAAI/bge-small-zh-v1.5",
        languages="Chinese focused",
        dimension="512d",
        approx_size="~96MB",
        best_for="Lowest-resource Chinese-first deployment",
    ),
    "3": EmbeddingModel(
        key="3",
        model_id="paraphrase-multilingual-MiniLM-L12-v2",
        languages="50+ languages",
        dimension="384d",
        approx_size="~471MB",
        best_for="Mature multilingual sentence-transformers ecosystem",
    ),
    "4": EmbeddingModel(
        key="4",
        model_id="Alibaba-NLP/gte-multilingual-base",
        languages="75+ languages",
        dimension="768d",
        approx_size="~610MB",
        best_for="Higher multilingual recall quality when RAM budget is comfortable",
    ),
    "5": EmbeddingModel(
        key="5",
        model_id="sentence-transformers/LaBSE",
        languages="109 languages",
        dimension="768d",
        approx_size="~471MB",
        best_for="Cross-lingual alignment heavy workloads",
    ),
    "6": EmbeddingModel(
        key="6",
        model_id="BAAI/bge-m3",
        languages="100+ languages",
        dimension="1024d",
        approx_size="~2GB",
        best_for="Maximum recall quality when disk and RAM are abundant",
    ),
}

RETRIEVAL_PROFILES = {
    "hybrid": {
        "name": "Hybrid Sidecar",
        "description": "Hindsight + governance objects + gbrain archive pages. This is the supported production profile.",
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Memory Sidecar Installer v3.0 — multi-agent compatible")
    parser.add_argument(
        "--profile",
        choices=sorted(RETRIEVAL_PROFILES.keys()),
        default=DEFAULT_PROFILE,
        help="Retrieval profile to install.",
    )
    parser.add_argument(
        "--embedding",
        default=None,
        help="Embedding model ID to record for deployment metadata. Omit for interactive selection.",
    )
    parser.add_argument(
        "--noninteractive",
        action="store_true",
        help=f"Skip prompts and use the default recommended model ({DEFAULT_EMBEDDING_MODEL}).",
    )
    parser.add_argument(
        "--agent-home",
        default=None,
        help="Target agent home directory (overrides --hermes-home and AGENT_HOME env).",
    )
    parser.add_argument(
        "--hermes-home",
        default=None,
        help="(deprecated) Target Hermes home directory. Use --agent-home instead.",
    )
    return parser.parse_args(argv)


def choose_embedding_model(args: argparse.Namespace) -> EmbeddingModel:
    if args.embedding:
        return EmbeddingModel(
            key="custom",
            model_id=args.embedding,
            languages="custom",
            dimension="unknown",
            approx_size="unknown",
            best_for="Custom user-supplied model",
        )

    if args.noninteractive:
        return EMBEDDING_MODELS["1"]

    print("\nSelect an embedding model for the sidecar metadata:")
    for key, model in EMBEDDING_MODELS.items():
        prefix = "*" if model.recommended else " "
        print(
            f"  {key}){prefix} {model.model_id} | {model.languages} | {model.dimension} | "
            f"{model.approx_size} | {model.best_for}"
        )
    choice = input("Choose [1-6] (default: 1): ").strip() or "1"
    return EMBEDDING_MODELS.get(choice, EMBEDDING_MODELS["1"])


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def scripts_source_dir() -> Path:
    return repo_root() / "scripts"


def resolve_agent_home(args: argparse.Namespace) -> Path:
    if args.agent_home:
        return Path(args.agent_home).expanduser()
    if args.hermes_home:
        return Path(args.hermes_home).expanduser()
    env_val = os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME")
    if env_val:
        return Path(env_val).expanduser()
    return Path.home() / ".hermes"


def check_agent_home(agent_home: Path) -> bool:
    return agent_home.exists()


def check_python() -> bool:
    return sys.version_info >= (3, 9)


def check_required_scripts(src_dir: Path) -> list[str]:
    missing = []
    for name in SUPPORTED_SCRIPT_NAMES:
        if not (src_dir / name).exists():
            missing.append(name)
    return missing


def load_yaml(path: Path) -> dict:
    if not path.exists():
        print(f"[installer] warning: config not found at {path}, creating new")
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def save_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def patch_config(hermes_home: Path, profile: str) -> Path:
    config_path = hermes_home / "config.yaml"
    config = load_yaml(config_path)
    config.setdefault("memory", {})
    config["memory"]["provider"] = "hindsight"

    skills = list(config.get("skills") or [])
    for skill in ("memory-starter-kit", "memory-archivist", "memory-proactive"):
        if skill not in skills:
            skills.append(skill)
    config["skills"] = skills

    config.setdefault("memory_sidecar", {})
    config["memory_sidecar"]["version"] = VERSION
    config["memory_sidecar"]["profile"] = profile
    config["memory_sidecar"]["scripts_dir"] = str(hermes_home / "scripts")

    save_yaml(config_path, config)
    return config_path


def deploy_scripts(src_dir: Path, dest_dir: Path) -> list[str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    installed = []
    for name in SUPPORTED_SCRIPT_NAMES:
        src = src_dir / name
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


def write_install_profile(hermes_home: Path, profile: str, embedding: EmbeddingModel, installed_scripts: list[str]) -> Path:
    sidecar_dir = hermes_home / SIDECAR_DIRNAME
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": VERSION,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "embedding_model": asdict(embedding),
        "installed_scripts": installed_scripts,
    }
    path = sidecar_dir / "install-profile.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    agent_home = resolve_agent_home(args)
    src_dir = scripts_source_dir()

    if not check_python():
        print("Python 3.9+ is required.")
        return 1

    if not check_agent_home(agent_home):
        print(f"Agent home not found: {agent_home}")
        print("Set AGENT_HOME env or use --agent-home to specify the target directory.")
        return 1

    missing = check_required_scripts(src_dir)
    if missing:
        print("Missing required sidecar scripts:")
        for name in missing:
            print(f"  - {name}")
        return 1

    embedding = choose_embedding_model(args)
    installed_scripts = deploy_scripts(src_dir, agent_home / "scripts")
    config_path = patch_config(agent_home, args.profile)
    profile_path = write_install_profile(agent_home, args.profile, embedding, installed_scripts)

    print("Memory Sidecar v3.0 installed")
    print(f"  Agent home: {agent_home}")
    print(f"  Retrieval profile: {args.profile} ({RETRIEVAL_PROFILES[args.profile]['name']})")
    print(f"  Embedding model: {embedding.model_id}")
    print(f"  Config patched: {config_path}")
    print(f"  Install profile: {profile_path}")
    print(f"  Scripts installed: {len(installed_scripts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
