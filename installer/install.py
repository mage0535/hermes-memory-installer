"""
Memory Sidecar Installer v3.5 - agent-agnostic, environment-aware.

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
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import urlopen

import yaml

VERSION = "3.5"
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
    "archive_sessions.py",
    "auto_session_summary.py",
    "memory_observability_report.py",
    "state_db_schema.py",
    "knowledge_notes.py",
    "recall_samples.py",
    "langsmith_monitor.py",
    "langsmith_task_wrapper.py",
]

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "environment_check_title": "== Environment Check ==",
        "status_ok": "OK",
        "status_fail": "FAIL",
        "python_required": "Python 3.9+ is required. Aborting.",
        "checks_failed_notice": (
            "Some checks failed. Memory recall needs PostgreSQL, Hindsight, and gbrain.\n"
            "The installer can still continue, or you can switch install modes for dependency help."
        ),
        "dry_run_title": "== Dry Run v{version} ==",
        "dry_run_agent_home": "  Agent home: {agent_home}",
        "dry_run_scripts_source": "  Scripts source: {src_dir}",
        "dry_run_scripts": "  Scripts to deploy: {scripts}",
        "dry_run_mode": "  Install mode: {install_mode}",
        "dry_run_lang": "  Language: {lang}",
        "agent_home_missing_1": "Agent home {agent_home} does not exist. Create it first, or set",
        "agent_home_missing_2": "AGENT_HOME environment variable to an existing agent directory.",
        "embedding_title": "== Embedding Model Selection ==",
        "embedding_intro": "Choose a model for semantic vector retrieval.",
        "embedding_custom_prompt": "Pick [1-6], or type c for custom (default: 1): ",
        "embedding_custom_id": "Enter a custom embedding model id: ",
        "installed_title": "== Memory Sidecar v{version} Installed ==",
        "installed_agent_home": "  Agent home:      {agent_home}",
        "installed_embedding": "  Embedding model: {embedding}",
        "installed_scripts": "  Scripts:         {count} deployed",
        "installed_config": "  Config:          {config_path} patched",
        "installed_profile": "  Profile:         {profile_path}",
        "next_steps": "Next steps:",
        "next_step_1": "  1. Ensure Hindsight, PostgreSQL, and gbrain are running",
        "next_step_2": "  2. Deploy your chosen embedding model service ({embedding})",
        "next_step_3": "  3. Run: python3 {agent_home}/scripts/session_to_gbrain.py --resume",
        "next_step_4": "  4. Schedule maintenance via cron or systemd timer",
        "architecture_note": "See ARCHITECTURE.md for the full memory stack layout.",
        "mode_1_title": "Mode 1: detect and guide only",
        "mode_2_title": "Mode 2: semi-automatic dependency assistance",
        "mode_3_title": "Mode 3: automatic dependency bootstrap",
        "dependency_missing_title": "Missing required dependencies: {deps}",
        "dependency_supported": "Bootstrap support detected for this host.",
        "dependency_not_supported": "Automatic bootstrap is not supported on this host. Use install mode 1 or 2.",
        "dependency_mode_1_body": (
            "Mode 1 will not change your system. Review the missing dependencies above,\n"
            "install them manually, then re-run ./install.sh.\n"
            "If you want guided help, switch to --install-mode 2 or --install-mode 3."
        ),
        "dependency_mode_2_body": (
            "Mode 2 provides guided dependency assistance without forcing a full automatic bootstrap.\n"
            "Recommended next step: re-run with --install-mode 2 after reviewing the commands below.\n"
            "If you want the installer to try the automatic path first, use --install-mode 3."
        ),
        "dependency_mode_3_body": (
            "Mode 3 tries the automatic bootstrap path first. If it fails, switch to --install-mode 2,\n"
            "and if that still fails, switch to --install-mode 1 to finish dependency setup manually."
        ),
        "bootstrap_detected": "Bootstrap plan: platform={platform}, package_manager={package_manager}",
        "bootstrap_commands_title": "Suggested dependency commands:",
        "bootstrap_hints_title": "Additional setup hints:",
        "bootstrap_attempt_title": "== Automatic Dependency Bootstrap ==",
        "bootstrap_unsupported": "Automatic bootstrap is unavailable on this platform.",
        "bootstrap_dry_run": "Dry run: bootstrap commands were not executed.",
        "bootstrap_failed": "Automatic bootstrap failed",
        "bootstrap_mode_2_note": "Mode 2 does not execute commands automatically. Review and run them step by step.",
        "fallback_message": (
            "Install mode {failed_mode} failed: {reason}\n"
            "Next options:\n"
            "  - Retry with --install-mode 2 for guided dependency assistance\n"
            "  - Retry with --install-mode 1 for detection-only instructions"
        ),
    },
    "zh": {
        "environment_check_title": "== 环境检查 ==",
        "status_ok": "通过",
        "status_fail": "失败",
        "python_required": "需要 Python 3.9+，安装终止。",
        "checks_failed_notice": (
            "部分检查未通过。记忆召回依赖 PostgreSQL、Hindsight 和 gbrain。\n"
            "安装器仍可继续，或切换安装模式获取依赖安装协助。"
        ),
        "dry_run_title": "== Dry Run v{version} ==",
        "dry_run_agent_home": "  Agent home: {agent_home}",
        "dry_run_scripts_source": "  脚本来源: {src_dir}",
        "dry_run_scripts": "  将部署脚本: {scripts}",
        "dry_run_mode": "  安装模式: {install_mode}",
        "dry_run_lang": "  输出语言: {lang}",
        "agent_home_missing_1": "目标 agent home {agent_home} 不存在，请先创建，或设置",
        "agent_home_missing_2": "AGENT_HOME 环境变量指向一个已存在的智能体目录。",
        "embedding_title": "== Embedding 模型选择 ==",
        "embedding_intro": "请选择用于语义召回的 embedding 模型。",
        "embedding_custom_prompt": "请输入 [1-6]，或输入 c 使用自定义模型（默认: 1）：",
        "embedding_custom_id": "请输入自定义 embedding 模型 ID：",
        "installed_title": "== Memory Sidecar v{version} 安装完成 ==",
        "installed_agent_home": "  Agent home:      {agent_home}",
        "installed_embedding": "  Embedding 模型:  {embedding}",
        "installed_scripts": "  已部署脚本:      {count} 个",
        "installed_config": "  已修补配置:      {config_path}",
        "installed_profile": "  安装档案:        {profile_path}",
        "next_steps": "下一步：",
        "next_step_1": "  1. 确保 Hindsight、PostgreSQL 和 gbrain 已运行",
        "next_step_2": "  2. 部署你选择的 embedding 服务（{embedding}）",
        "next_step_3": "  3. 运行: python3 {agent_home}/scripts/session_to_gbrain.py --resume",
        "next_step_4": "  4. 用 cron 或 systemd timer 调度维护周期",
        "architecture_note": "完整架构说明见 ARCHITECTURE.md。",
        "mode_1_title": "模式 1：仅检测与指引",
        "mode_2_title": "模式 2：半自动依赖协助",
        "mode_3_title": "模式 3：自动依赖引导安装",
        "dependency_missing_title": "缺失的关键依赖：{deps}",
        "dependency_supported": "当前主机支持依赖引导协助。",
        "dependency_not_supported": "当前主机不支持自动引导安装，请使用模式 1 或模式 2。",
        "dependency_mode_1_body": (
            "模式 1 不会改动系统。请先根据上面的缺失依赖手动安装，\n"
            "然后重新运行 ./install.sh。\n"
            "如果需要安装器协助，请切换到 --install-mode 2 或 --install-mode 3。"
        ),
        "dependency_mode_2_body": (
            "模式 2 提供半自动依赖协助，但不会强制执行完整自动安装。\n"
            "建议先查看下面的命令，再使用 --install-mode 2 继续安装。\n"
            "如果希望安装器先自动尝试，请使用 --install-mode 3。"
        ),
        "dependency_mode_3_body": (
            "模式 3 会先尝试自动引导安装依赖。如果失败，请切换到 --install-mode 2，\n"
            "如果模式 2 仍然失败，再切换到 --install-mode 1 手动完成依赖安装。"
        ),
        "bootstrap_detected": "依赖引导方案：platform={platform}, package_manager={package_manager}",
        "bootstrap_commands_title": "建议执行的依赖命令：",
        "bootstrap_hints_title": "补充说明：",
        "bootstrap_attempt_title": "== 自动依赖引导安装 ==",
        "bootstrap_unsupported": "当前平台不支持自动依赖引导安装。",
        "bootstrap_dry_run": "当前是 dry-run，未真正执行依赖安装命令。",
        "bootstrap_failed": "自动依赖安装失败",
        "bootstrap_mode_2_note": "模式 2 不会自动执行命令，请按顺序查看并手动执行。",
        "fallback_message": (
            "安装模式 {failed_mode} 失败：{reason}\n"
            "后续可选路径：\n"
            "  - 使用 --install-mode 2 进行半自动依赖协助\n"
            "  - 使用 --install-mode 1 仅获取检测与人工安装指引"
        ),
    },
}

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


def _run(cmd: list[str], timeout: int = 10) -> tuple[int, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, (result.stdout + result.stderr).strip()
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def _http_probe(url: str, timeout: int = 5) -> tuple[bool, str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
        return True, body[:120]
    except URLError as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)


def translate(lang: str, key: str, **kwargs: object) -> str:
    template = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)
    return template.format(**kwargs)


def resolve_language(args: argparse.Namespace) -> str:
    if getattr(args, "lang", "auto") in {"zh", "en"}:
        return args.lang
    locale = (os.environ.get("LC_ALL") or os.environ.get("LANG") or "").lower()
    if locale.startswith("zh"):
        return "zh"
    return "en"


def check_python() -> tuple[bool, str]:
    ok = sys.version_info >= (3, 9)
    detail = f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return ok, detail


def check_hindsight() -> tuple[bool, str]:
    ok, out = _http_probe("http://localhost:8890/health")
    if ok:
        return True, f"Hindsight reachable - {out[:120]}"
    code, out = _run(["curl", "-sf", "http://localhost:8890/health"])
    if code == 0:
        return True, f"Hindsight reachable - {out[:120]}"
    return False, "Hindsight not reachable at http://localhost:8890. Is it running?"


def check_gbrain() -> tuple[bool, str]:
    ok, _ = _http_probe("http://localhost:8787/health")
    if ok:
        return True, "gbrain MCP reachable at http://localhost:8787"
    code, _ = _run(["curl", "-sf", "http://localhost:8787/health"])
    if code == 0:
        return True, "gbrain MCP reachable at http://localhost:8787"
    gbrain = shutil.which("gbrain")
    if gbrain:
        return True, f"gbrain CLI found at {gbrain} (health endpoint not responding)"
    return False, "gbrain not found. Install from https://github.com/hi-ogawa/gbrain"


def check_postgres() -> tuple[bool, str]:
    pg_host = os.environ.get("PGHOST", "localhost")
    pg_port = os.environ.get("PGPORT", "5432")
    code, _ = _run(["pg_isready", "-h", pg_host, "-p", pg_port], timeout=5)
    if code == 0:
        return True, f"PostgreSQL ready at {pg_host}:{pg_port}"
    if code == 127:
        return True, f"pg_isready not installed - skipping PostgreSQL readiness probe for {pg_host}:{pg_port}"
    return False, f"PostgreSQL not responding at {pg_host}:{pg_port}"


def check_embedding_service() -> tuple[bool, str]:
    configured_url = os.environ.get("EMBEDDING_API_URL", "http://localhost:8766/health")
    parts = urlsplit(configured_url)
    probe_path = "/health" if parts.path.rstrip("/").endswith("/embeddings") else parts.path
    probe_url = urlunsplit((parts.scheme, parts.netloc, probe_path, "", ""))
    ok, _ = _http_probe(probe_url)
    if ok:
        return True, f"Embedding service reachable at {probe_url}"
    code, _ = _run(["curl", "-sf", probe_url])
    if code == 0:
        return True, f"Embedding service reachable at {probe_url}"
    return False, "No embedding service detected - will be configured separately."


def run_environment_checks() -> dict[str, tuple[bool, str]]:
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


def print_environment_report(checks: dict, lang: str) -> int:
    print(f"\n{translate(lang, 'environment_check_title')}")
    failures = 0
    for name, (ok, detail) in checks.items():
        mark = translate(lang, "status_ok") if ok else translate(lang, "status_fail")
        print(f"  {mark} {name}: {detail}")
        if not ok:
            failures += 1
    return failures


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Memory Sidecar Installer v{VERSION} - works with any AI agent",
    )
    parser.add_argument(
        "--agent-home",
        default=None,
        help="Target agent home directory (e.g., ~/.hermes, ~/.claude). Overrides AGENT_HOME / HERMES_HOME env vars.",
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
    parser.add_argument(
        "--install-mode",
        choices=["1", "2", "3"],
        default="3",
        help="Dependency assistance mode: 1=detect only, 2=guided assistance, 3=automatic bootstrap first.",
    )
    parser.add_argument(
        "--lang",
        choices=["auto", "en", "zh"],
        default="auto",
        help="Installer output language. Defaults to locale detection.",
    )
    return parser.parse_args(argv)


def choose_embedding_model(args: argparse.Namespace, lang: str) -> EmbeddingModel:
    if args.embedding:
        return EmbeddingModel(
            key="custom",
            model_id=args.embedding,
            languages="custom",
            dimension="unknown",
            approx_size="unknown",
            best_for="User-supplied model",
        )
    if args.noninteractive:
        return EMBEDDING_MODELS["1"]

    print(f"\n{translate(lang, 'embedding_title')}")
    print(f"{translate(lang, 'embedding_intro')}\n")
    for key, model in EMBEDDING_MODELS.items():
        star = " *" if model.recommended else "  "
        print(f"  [{key}]{star} {model.model_id}")
        print(f"         {model.languages} | {model.dimension} | {model.approx_size}")
        print(f"         {model.best_for}\n")
    choice = input(translate(lang, "embedding_custom_prompt")).strip() or "1"
    if choice.lower() in {"c", "custom"}:
        custom_model = input(translate(lang, "embedding_custom_id")).strip()
        if custom_model:
            return EmbeddingModel(
                key="custom",
                model_id=custom_model,
                languages="custom",
                dimension="unknown",
                approx_size="unknown",
                best_for="User-supplied model",
            )
    return EMBEDDING_MODELS.get(choice, EMBEDDING_MODELS["1"])


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
    candidates = [
        agent_home / "config.yaml",
        agent_home / "config.json",
        agent_home / "claude_config.json",
    ]
    config_path = None
    for candidate in candidates:
        if candidate.exists():
            config_path = candidate
            break

    if config_path is None:
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
        try:
            raw = config_path.read_text(encoding="utf-8")
            config = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid JSON agent config: {config_path}") from exc

    config.setdefault("memory", {})
    if not config["memory"].get("provider"):
        config["memory"]["provider"] = "hindsight"
    config.setdefault("memory_sidecar", {})
    config["memory_sidecar"]["version"] = VERSION
    config["memory_sidecar"]["scripts_dir"] = str(agent_home / "scripts")

    backup_path = config_path.with_name(
        f"{config_path.name}.memory-sidecar-backup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    shutil.copy2(config_path, backup_path)
    if config_path.suffix == ".yaml":
        save_yaml(config_path, config)
    elif config_path.suffix == ".json":
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

    return config_path


def deploy_scripts(src_dir: Path, dest_dir: Path) -> list[str]:
    missing = [name for name in SUPPORTED_SCRIPT_NAMES if not (src_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"installer source is missing required scripts: {', '.join(missing)}")

    dest_dir.mkdir(parents=True, exist_ok=True)
    installed = []
    staging_root = Path(tempfile.mkdtemp(prefix="memory-sidecar-stage-", dir=str(dest_dir.parent)))
    rollback_root = Path(tempfile.mkdtemp(prefix="memory-sidecar-rollback-", dir=str(dest_dir.parent)))
    replaced_targets: list[Path] = []
    backed_up_targets: set[str] = set()
    try:
        for name in SUPPORTED_SCRIPT_NAMES:
            src = src_dir / name
            staged = staging_root / name
            try:
                shutil.copy2(src, staged)
                if src.suffix == ".py":
                    staged.chmod(0o755)
                installed.append(name)
            except OSError as exc:
                print(f"[installer] failed to stage {name}: {exc}", file=sys.stderr)
                raise

        for name in installed:
            dst = dest_dir / name
            staged = staging_root / name
            backup = rollback_root / name
            try:
                if dst.exists():
                    shutil.copy2(dst, backup)
                    backed_up_targets.add(name)
                os.replace(staged, dst)
                replaced_targets.append(dst)
            except OSError as exc:
                for target in replaced_targets:
                    restore = rollback_root / target.name
                    if target.name in backed_up_targets and restore.exists():
                        os.replace(restore, target)
                    elif target.exists():
                        target.unlink()
                print(f"[installer] failed to deploy {name}: {exc}", file=sys.stderr)
                raise
        return installed
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
        shutil.rmtree(rollback_root, ignore_errors=True)


def _copy_if_exists(path: Path, backup_root: Path, relative_name: str) -> Path | None:
    if not path.exists():
        return None
    backup_path = backup_root / relative_name
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return backup_path


def rollback_install_transaction(
    agent_home: Path,
    backup_root: Path,
    installed_scripts: list[str],
    config_path: Path | None,
    had_profile: bool,
    had_config_note: bool,
) -> None:
    sidecar_dir = agent_home / SIDECAR_DIRNAME
    scripts_dir = agent_home / "scripts"
    for name in installed_scripts:
        dst = scripts_dir / name
        backup = backup_root / "scripts" / name
        if backup.exists():
            os.replace(backup, dst)
        elif dst.exists():
            dst.unlink()

    if config_path is not None:
        backup = backup_root / "config" / config_path.name
        if backup.exists():
            os.replace(backup, config_path)

    profile_path = agent_home / SIDECAR_DIRNAME / "install-profile.json"
    backup_profile = backup_root / "profile" / "install-profile.json"
    if had_profile and backup_profile.exists():
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(backup_profile, profile_path)
    elif profile_path.exists():
        profile_path.unlink()

    config_note = sidecar_dir / "config-note.txt"
    backup_note = backup_root / "note" / "config-note.txt"
    if had_config_note and backup_note.exists():
        config_note.parent.mkdir(parents=True, exist_ok=True)
        os.replace(backup_note, config_note)
    elif config_note.exists():
        config_note.unlink()


def install_sidecar(agent_home: Path, embedding: EmbeddingModel, src_dir: Path) -> tuple[list[str], Path | None, Path]:
    backup_root = Path(tempfile.mkdtemp(prefix="memory-sidecar-install-", dir=str(agent_home.parent)))
    installed_scripts: list[str] = []
    config_path: Path | None = None
    had_profile = False
    had_config_note = False
    try:
        scripts_dir = agent_home / "scripts"
        for name in SUPPORTED_SCRIPT_NAMES:
            _copy_if_exists(scripts_dir / name, backup_root / "scripts", name)

        for candidate in (agent_home / "config.yaml", agent_home / "config.json", agent_home / "claude_config.json"):
            if candidate.exists():
                config_path = candidate
                _copy_if_exists(candidate, backup_root / "config", candidate.name)
                break

        profile_path = agent_home / SIDECAR_DIRNAME / "install-profile.json"
        had_profile = profile_path.exists()
        _copy_if_exists(profile_path, backup_root / "profile", "install-profile.json")

        config_note = agent_home / SIDECAR_DIRNAME / "config-note.txt"
        had_config_note = config_note.exists()
        _copy_if_exists(config_note, backup_root / "note", "config-note.txt")

        installed_scripts = deploy_scripts(src_dir, scripts_dir)
        patched_config_path = patch_agent_config(agent_home)
        written_profile_path = write_install_profile(agent_home, embedding, installed_scripts)
        shutil.rmtree(backup_root, ignore_errors=True)
        return installed_scripts, patched_config_path, written_profile_path
    except Exception:
        rollback_install_transaction(
            agent_home,
            backup_root,
            installed_scripts or SUPPORTED_SCRIPT_NAMES,
            config_path,
            had_profile,
            had_config_note,
        )
        shutil.rmtree(backup_root, ignore_errors=True)
        raise


def write_install_profile(
    agent_home: Path, embedding: EmbeddingModel, installed_scripts: list[str]
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


def required_dependency_failures(checks: dict[str, tuple[bool, str]]) -> list[str]:
    return [name for name in ("postgres", "hindsight", "gbrain") if not checks.get(name, (True, ""))[0]]


def detect_package_manager() -> str | None:
    for candidate in ("apt-get", "dnf", "yum", "brew"):
        if shutil.which(candidate):
            return candidate
    return None


def bootstrap_supported() -> bool:
    return platform.system().lower() == "linux" and detect_package_manager() in {"apt-get", "dnf", "yum"}


def build_bootstrap_commands(package_manager: str | None) -> list[str]:
    if package_manager == "apt-get":
        return [
            "sudo apt-get update",
            "sudo apt-get install -y curl git python3-pip python3-venv postgresql postgresql-contrib",
        ]
    if package_manager in {"dnf", "yum"}:
        tool = package_manager
        return [
            f"sudo {tool} install -y curl git python3-pip postgresql postgresql-server",
        ]
    if package_manager == "brew":
        return [
            "brew install postgresql@16 curl git",
        ]
    return []


def build_bootstrap_hints() -> list[str]:
    return [
        "Hindsight project: https://github.com/HindsightTechnologySolutions/hindsight",
        "gbrain project: https://github.com/hi-ogawa/gbrain",
        "Re-run ./install.sh after PostgreSQL, Hindsight, and gbrain are reachable.",
    ]


def render_dependency_guidance(
    lang: str,
    install_mode: str,
    failed_dependencies: list[str],
    bootstrap_supported: bool,
) -> str:
    body_key = {
        "1": "dependency_mode_1_body",
        "2": "dependency_mode_2_body",
        "3": "dependency_mode_3_body",
    }[install_mode]
    lines = [
        translate(lang, f"mode_{install_mode}_title"),
        translate(lang, "dependency_missing_title", deps=", ".join(failed_dependencies)),
        translate(lang, "dependency_supported" if bootstrap_supported else "dependency_not_supported"),
        translate(lang, body_key),
    ]
    return "\n".join(lines)


def render_mode_fallback_message(lang: str, failed_mode: str, reason: str) -> str:
    return translate(lang, "fallback_message", failed_mode=failed_mode, reason=reason)


def assist_dependencies(
    args: argparse.Namespace,
    lang: str,
    failed_dependencies: list[str],
) -> bool:
    supported = bootstrap_supported()
    package_manager = detect_package_manager()
    print(render_dependency_guidance(lang, args.install_mode, failed_dependencies, supported))
    print(translate(lang, "bootstrap_detected", platform=platform.system().lower(), package_manager=package_manager or "none"))
    print(translate(lang, "bootstrap_commands_title"))
    for command in build_bootstrap_commands(package_manager):
        print(f"  {command}")
    print(translate(lang, "bootstrap_hints_title"))
    for hint in build_bootstrap_hints():
        print(f"  - {hint}")

    if args.install_mode == "1":
        return False
    if args.install_mode == "2":
        print(translate(lang, "bootstrap_mode_2_note"))
        return False
    if not supported:
        print(translate(lang, "bootstrap_unsupported"))
        print(render_mode_fallback_message(lang, "3", translate(lang, "bootstrap_unsupported")))
        return False
    print(f"\n{translate(lang, 'bootstrap_attempt_title')}")
    if args.dry_run:
        print(translate(lang, "bootstrap_dry_run"))
        return True

    for command in build_bootstrap_commands(package_manager):
        result = subprocess.run(command, shell=True, text=True)
        if result.returncode != 0:
            print(render_mode_fallback_message(lang, "3", translate(lang, "bootstrap_failed")))
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    lang = resolve_language(args)
    agent_home = resolve_agent_home(args)
    src_dir = scripts_source_dir()

    if not args.skip_checks:
        checks = run_environment_checks()
        failures = print_environment_report(checks, lang)
        if not checks["python"][0]:
            print(f"\n{translate(lang, 'python_required')}")
            return 1
        if failures > 0:
            print(f"\n{translate(lang, 'checks_failed_notice')}")
            failed_dependencies = required_dependency_failures(checks)
            if failed_dependencies:
                assisted = assist_dependencies(args, lang, failed_dependencies)
                if args.install_mode in {"1", "2"}:
                    return 1
                if args.install_mode == "3" and not assisted:
                    return 1
    else:
        checks = {}

    if args.dry_run:
        print(f"\n{translate(lang, 'dry_run_title', version=VERSION)}")
        print(translate(lang, "dry_run_agent_home", agent_home=agent_home))
        print(translate(lang, "dry_run_scripts_source", src_dir=src_dir))
        print(translate(lang, "dry_run_scripts", scripts=SUPPORTED_SCRIPT_NAMES))
        print(translate(lang, "dry_run_mode", install_mode=args.install_mode))
        print(translate(lang, "dry_run_lang", lang=lang))
        return 0

    if not agent_home.exists():
        print(translate(lang, "agent_home_missing_1", agent_home=agent_home))
        print(translate(lang, "agent_home_missing_2"))
        return 1

    embedding = choose_embedding_model(args, lang)
    installed_scripts, config_path, profile_path = install_sidecar(agent_home, embedding, src_dir)

    print(f"\n{translate(lang, 'installed_title', version=VERSION)}")
    print(translate(lang, "installed_agent_home", agent_home=agent_home))
    print(translate(lang, "installed_embedding", embedding=embedding.model_id))
    print(translate(lang, "installed_scripts", count=len(installed_scripts)))
    if config_path:
        print(translate(lang, "installed_config", config_path=config_path))
    print(translate(lang, "installed_profile", profile_path=profile_path))
    print()
    print(translate(lang, "next_steps"))
    print(translate(lang, "next_step_1"))
    print(translate(lang, "next_step_2", embedding=embedding.model_id))
    print(translate(lang, "next_step_3", agent_home=agent_home))
    print(translate(lang, "next_step_4"))
    print("")
    print(translate(lang, "architecture_note"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

