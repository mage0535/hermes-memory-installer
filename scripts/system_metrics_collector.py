#!/usr/bin/env python3
import json, os, shutil, time
from pathlib import Path
from datetime import datetime, timezone

AGENT_HOME = Path(os.environ.get("AGENT_HOME", str(Path.home() / ".hermes")))
OUTPUT = AGENT_HOME / "metrics" / "system-metrics-latest.json"

def get_metrics():
    mem = {}
    with open("/proc/meminfo") as f:
        for line in f:
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                val = int(parts[1].strip().split()[0])
                mem[key] = val
    swap_total = mem.get("SwapTotal", 0) // 1024
    swap_free = mem.get("SwapFree", 0) // 1024
    swap_used = swap_total - swap_free

    disk = shutil.disk_usage("/")
    disk_total_gb = disk.total // (1024**3)
    disk_used_gb = disk.used // (1024**3)
    disk_pct = round(disk.used / disk.total * 100, 1)

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
            "total_gb": disk_total_gb,
            "used_gb": disk_used_gb,
            "free_gb": disk.free // (1024**3),
            "pct": disk_pct,
        },
        "load": os.getloadavg(),
        "state_db_size_mb": round((AGENT_HOME / "state.db").stat().st_size / (1024**2), 1) if (AGENT_HOME / "state.db").exists() else 0,
    }

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
metrics = get_metrics()
OUTPUT.write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
print(json.dumps({"ok": True, "swap_pct": metrics["memory"]["swap_pct"], "disk_pct": metrics["disk"]["pct"]}))
