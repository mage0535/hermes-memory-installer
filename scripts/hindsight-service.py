#!/usr/bin/env python3
"""Hindsight Service — standalone daemon, using existing PG on port 5432"""
import os, time, sys, signal

os.environ['PG0_DATA_DIR'] = '/root/.hindsight-embedded'
os.makedirs('/root/.hindsight-embedded', exist_ok=True)

from hindsight import HindsightServer

server = HindsightServer(
    db_url='postgresql://postgres@/hindsight',
    llm_provider='openai',
    llm_model='deepseek-v4-flash-free',
    llm_api_key='sk-a7X84RUATo1Ww0wcNd8z1lWs8mnnltyFqTJRJmRCWZ0b25R4CyEcc6HVHIjF9lnQ',
    llm_base_url='https://opencode.ai/zen/v1',
    host='127.0.0.1',
    port=8890
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
