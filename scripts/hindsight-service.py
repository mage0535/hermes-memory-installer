#!/usr/bin/env python3
"""Hindsight Service — standalone daemon, using existing PG on port 5432"""
import os, time, sys, signal

_data_dir = os.environ.get("HINDSIGHT_DATA_DIR", str(os.path.expanduser("~/.hindsight-embedded")))
os.environ['PG0_DATA_DIR'] = _data_dir
os.makedirs(_data_dir, exist_ok=True)

from hindsight import HindsightServer

server = HindsightServer(
    db_url=os.environ.get("HINDSIGHT_DB_URL", 'postgresql://postgres@/hindsight'),
    llm_provider=os.environ.get("HINDSIGHT_LLM_PROVIDER", 'openai'),
    llm_model=os.environ.get("HINDSIGHT_LLM_MODEL", 'deepseek-v4-flash-free'),
    llm_api_key=os.environ.get("HINDSIGHT_API_KEY", ''),
    llm_base_url=os.environ.get("HINDSIGHT_LLM_BASE_URL", 'https://opencode.ai/zen/v1'),
    host=os.environ.get("HINDSIGHT_HOST", '127.0.0.1'),
    port=int(os.environ.get("HINDSIGHT_PORT", '8890')),
)

def cleanup(signum, frame):
    print("Shutting down Hindsight...")
    server.stop()
    sys.exit(0)

signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

server.start(timeout=60)
url = server.url
print(f"HINDSIGHT_READY:{url}")
sys.stdout.flush()

while True:
    time.sleep(5)
