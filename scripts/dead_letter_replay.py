#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
from urllib import request
from datetime import datetime, timezone

AGENT_HOME = Path(os.environ.get("AGENT_HOME", str(Path.home() / ".hermes")))
DEAD_LETTER = AGENT_HOME / "metrics" / "failed-alert-webhook.jsonl"
REPLAY_LOG = AGENT_HOME / "metrics" / "dead-letter-replay.log"
FORWARD_URL = os.environ.get("MEMORY_ALERT_FORWARD_URL", "")

def main():
    if not DEAD_LETTER.exists():
        print(json.dumps({"ok": True, "replayed": 0, "message": "no file"}))
        return 0
    with open(DEAD_LETTER) as f:
        events = [json.loads(line) for line in f if line.strip()]
    if not events:
        print(json.dumps({"ok": True, "replayed": 0, "message": "empty"}))
        return 0
    if not FORWARD_URL:
        print(json.dumps({"ok": False, "error": "FORWARD_URL not set"}))
        return 1
    replayed = 0
    failed = 0
    for event in events:
        try:
            data = json.dumps(event.get("payload", event)).encode()
            req = request.Request(FORWARD_URL, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            with request.urlopen(req, timeout=10) as resp:
                if resp.status < 400:
                    replayed += 1
                else:
                    failed += 1
        except Exception:
            failed += 1
        time.sleep(0.5)
    if failed == 0:
        DEAD_LETTER.unlink(missing_ok=True)
    result = {"ok": failed == 0, "replayed": replayed, "failed": failed}
    REPLAY_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    log_entry = {"timestamp": ts}
    log_entry.update(result)
    with open(REPLAY_LOG, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
