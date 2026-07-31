#!/usr/bin/env python3
"""Hindsight service wrapper with Hermes model-config sync and safe defaults."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import sys
import time

import yaml


DEFAULT_ENV = {
    # Keep service logs quieter and reduce idle polling churn.
    "HINDSIGHT_API_LOG_LEVEL": "warning",
    "HINDSIGHT_API_WORKER_POLL_INTERVAL_MS": "1000",
    # Limit background work so Hindsight cannot monopolize a shared host.
    "HINDSIGHT_API_WORKER_MAX_SLOTS": "6",
    "HINDSIGHT_API_WORKER_CONSOLIDATION_MAX_SLOTS": "1",
    # Bound long-running model calls so stuck work releases slots promptly.
    "HINDSIGHT_API_LLM_TIMEOUT": "90",
    "HINDSIGHT_API_LLM_MAX_CONCURRENT": "2",
    "HINDSIGHT_API_RETAIN_LLM_TIMEOUT": "75",
    "HINDSIGHT_API_RETAIN_LLM_MAX_CONCURRENT": "2",
    "HINDSIGHT_API_CONSOLIDATION_LLM_TIMEOUT": "90",
    "HINDSIGHT_API_CONSOLIDATION_LLM_MAX_CONCURRENT": "1",
    "HINDSIGHT_API_REFLECT_LLM_TIMEOUT": "60",
    "HINDSIGHT_API_REFLECT_LLM_MAX_CONCURRENT": "1",
    "HINDSIGHT_API_RECALL_MAX_CONCURRENT": "20",
}


def agent_home() -> Path:
    return Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()


def hermes_active_model(home: Path | None = None) -> dict[str, str] | None:
    """Resolve the active Hermes model provider without copying raw config."""
    config_path = (home or agent_home()) / "config.yaml"
    if not config_path.is_file():
        return None
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    model_config = config.get("model") if isinstance(config.get("model"), dict) else {}
    provider_name = model_config.get("provider")
    if not provider_name:
        return None

    providers = config.get("providers") if isinstance(config.get("providers"), dict) else {}
    custom_providers = config.get("custom_providers") if isinstance(config.get("custom_providers"), list) else []
    provider_config = providers.get(provider_name) if isinstance(providers.get(provider_name), dict) else None
    if provider_config is None:
        provider_config = next(
            (item for item in custom_providers if isinstance(item, dict) and item.get("name") == provider_name),
            None,
        )
    if not isinstance(provider_config, dict):
        return None

    api_key = provider_config.get("api_key") or os.environ.get(provider_config.get("api_key_env", ""), "")
    return {
        "api_key": str(api_key or ""),
        "base_url": str(provider_config.get("base_url") or ""),
        "model": str(model_config.get("model") or model_config.get("default") or provider_config.get("model") or ""),
        "provider": str(provider_name),
    }


def openai_compatible_provider(active: dict[str, str]) -> str:
    base_url = active.get("base_url", "").lower()
    provider = active.get("provider", "")
    if any(token in base_url for token in ("openai", "opencode", "deepseek")):
        return "openai"
    return provider


def configure_environment() -> dict[str, str] | None:
    for key, value in DEFAULT_ENV.items():
        os.environ.setdefault(key, value)

    active = hermes_active_model()
    if active:
        os.environ.setdefault("HINDSIGHT_API_KEY", active["api_key"])
        os.environ.setdefault("HINDSIGHT_LLM_BASE_URL", active["base_url"])
        os.environ.setdefault("HINDSIGHT_LLM_MODEL", active["model"])
        os.environ.setdefault("HINDSIGHT_LLM_PROVIDER", openai_compatible_provider(active))

    data_dir = os.environ.get("HINDSIGHT_DATA_DIR", str(Path.home() / ".hindsight-embedded"))
    os.environ["PG0_DATA_DIR"] = data_dir
    Path(data_dir).expanduser().mkdir(parents=True, exist_ok=True)
    return active


def main() -> int:
    active = configure_environment()
    if active:
        print(f"[hindsight] Synced with Hermes: {active['provider']}/{active['model']} @ {active['base_url']}")
    else:
        print("[hindsight] WARNING: Could not read Hermes model config. Using environment/default settings.")

    from hindsight import HindsightServer

    server = HindsightServer(
        db_url=os.environ.get("HINDSIGHT_DB_URL", "postgresql://postgres@/hindsight"),
        llm_provider=os.environ.get("HINDSIGHT_LLM_PROVIDER", "openai"),
        llm_model=os.environ.get("HINDSIGHT_LLM_MODEL", "deepseek-v4-flash-free"),
        llm_api_key=os.environ.get("HINDSIGHT_API_KEY", ""),
        llm_base_url=os.environ.get("HINDSIGHT_LLM_BASE_URL", ""),
        host=os.environ.get("HINDSIGHT_HOST", "127.0.0.1"),
        port=int(os.environ.get("HINDSIGHT_PORT", "8890")),
    )

    def cleanup(signum, frame):
        print("Shutting down Hindsight...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    server.start(timeout=180)
    print(f"HINDSIGHT_READY:{server.url}")
    sys.stdout.flush()

    while True:
        time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
