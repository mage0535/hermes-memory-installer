#!/usr/bin/env python3
"""Quick multi-agent profile isolation check. Runs fast acceptance against two profiles."""
import json, os, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

AGENT_HOME = Path(os.environ.get("AGENT_HOME", str(Path.home() / ".hermes")))
METRICS_DIR = AGENT_HOME / "metrics"
PROFILES = [
    {"name": "hermes", "home": str(AGENT_HOME)},
    {"name": "default", "home": str(Path.home() / ".agent")},
]

def main():
    results = []
    for profile in PROFILES:
        home = Path(profile["home"])
        script = home / "scripts" / "sidecar_acceptance_check.py"
        if not script.exists():
            results.append({"profile": profile["name"], "ok": False, "error": "no acceptance script"})
            continue
        try:
            r = subprocess.run(
                ["python3", str(script), "--mode", "fast"],
                capture_output=True, text=True, timeout=30,
                env={"AGENT_HOME": str(home), "PATH": os.environ.get("PATH", "")}
            )
            if r.returncode == 0:
                payload = json.loads(r.stdout) if r.stdout.strip() else {}
                results.append({"profile": profile["name"], "ok": payload.get("ok", False), "home": str(home)})
            else:
                results.append({"profile": profile["name"], "ok": False, "error": r.stderr[:200]})
        except Exception as e:
            results.append({"profile": profile["name"], "ok": False, "error": str(e)})

    all_ok = all(r["ok"] for r in results)
    output = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "ok": all_ok,
        "profiles": results,
    }
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    (METRICS_DIR / "profile-isolation-latest.json").write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(json.dumps(output, ensure_ascii=False))
    return 0 if all_ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
