#!/usr/bin/env python3
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

AGENT_HOME = Path(os.environ.get("AGENT_HOME", str(Path.home() / ".hermes")))
OUTPUT = AGENT_HOME / "metrics" / "system-metrics-latest.json"
HISTORY = AGENT_HOME / "metrics" / "system-metrics-history.jsonl"


def get_metrics() -> dict:
    mem = {}
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        with meminfo.open(encoding="utf-8") as handle:
            for line in handle:
                parts = line.split(":")
                if len(parts) != 2:
                    continue
                key = parts[0].strip()
                val = int(parts[1].strip().split()[0])
                mem[key] = val

    swap_total = mem.get("SwapTotal", 0) // 1024
    swap_free = mem.get("SwapFree", 0) // 1024
    swap_used = swap_total - swap_free
    disk = shutil.disk_usage("/")
    state_db = AGENT_HOME / "state.db"
    try:
        load = os.getloadavg()
    except (AttributeError, OSError):
        load = [0.0, 0.0, 0.0]

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "memory": {
            "total_mb": mem.get("MemTotal", 0) // 1024,
            "available_mb": mem.get("MemAvailable", 0) // 1024,
            "swap_total_mb": swap_total,
            "swap_used_mb": swap_used,
            "swap_pct": round(swap_used / swap_total * 100, 1) if swap_total else 0,
        },
        "disk": {
            "total_gb": disk.total // (1024**3),
            "used_gb": disk.used // (1024**3),
            "free_gb": disk.free // (1024**3),
            "pct": round(disk.used / disk.total * 100, 1),
        },
        "load": load,
        "state_db_size_mb": round(state_db.stat().st_size / (1024**2), 1) if state_db.exists() else 0,
    }


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    metrics = get_metrics()
    OUTPUT.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    with HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(metrics, ensure_ascii=False) + "\n")
    print(json.dumps({"ok": True, "swap_pct": metrics["memory"]["swap_pct"], "disk_pct": metrics["disk"]["pct"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
