#!/usr/bin/env python3
"""Hindsight service wrapper with conservative worker/LLM defaults."""

import os
import signal
import sys
import time


DEFAULT_ENV = {
    # Keep service logs quieter and reduce idle polling churn.
    "HINDSIGHT_API_LOG_LEVEL": "warning",
    "HINDSIGHT_API_WORKER_POLL_INTERVAL_MS": "1000",
    # Limit total concurrent background jobs so one backlog does not
    # monopolize CPU and memory on the shared Hermes host.
    "HINDSIGHT_API_WORKER_MAX_SLOTS": "6",
    "HINDSIGHT_API_WORKER_CONSOLIDATION_MAX_SLOTS": "1",
    # Bound long-running model calls so stuck consolidation/reflect tasks
    # release their worker slots sooner.
    "HINDSIGHT_API_LLM_TIMEOUT": "90",
    "HINDSIGHT_API_LLM_MAX_CONCURRENT": "2",
    "HINDSIGHT_API_RETAIN_LLM_TIMEOUT": "75",
    "HINDSIGHT_API_RETAIN_LLM_MAX_CONCURRENT": "2",
    "HINDSIGHT_API_CONSOLIDATION_LLM_TIMEOUT": "90",
    "HINDSIGHT_API_CONSOLIDATION_LLM_MAX_CONCURRENT": "1",
    "HINDSIGHT_API_REFLECT_LLM_TIMEOUT": "60",
    "HINDSIGHT_API_REFLECT_LLM_MAX_CONCURRENT": "1",
    # Avoid recall-side fan-out from exploding under large sessions.
    "HINDSIGHT_API_RECALL_MAX_CONCURRENT": "20",
}

for key, value in DEFAULT_ENV.items():
    os.environ.setdefault(key, value)

data_dir = os.environ.get("HINDSIGHT_DATA_DIR", str(os.path.expanduser("~/.hindsight-embedded")))
os.environ["PG0_DATA_DIR"] = data_dir
os.makedirs(data_dir, exist_ok=True)

from hindsight import HindsightServer


server = HindsightServer(
    db_url=os.environ.get("HINDSIGHT_DB_URL", "postgresql://postgres@/hindsight"),
    llm_provider=os.environ.get("HINDSIGHT_LLM_PROVIDER", "openai"),
    llm_model=os.environ.get("HINDSIGHT_LLM_MODEL", "deepseek-v4-flash-free"),
    llm_api_key=os.environ.get("HINDSIGHT_API_KEY", ""),
    llm_base_url=os.environ.get("HINDSIGHT_LLM_BASE_URL", "https://opencode.ai/zen/v1"),
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
url = server.url
print(f"HINDSIGHT_READY:{url}")
sys.stdout.flush()

while True:
    time.sleep(5)
