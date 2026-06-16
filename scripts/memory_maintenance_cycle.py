#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable
AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
MEMORY_SNAPSHOT = SCRIPT_DIR / "memory_snapshot_backup.py"
SESSION_TO_GBRAIN = SCRIPT_DIR / "session_to_gbrain.py"
GOVERNANCE_REBUILD = SCRIPT_DIR / "memory_governance_rebuild.py"
TIERED_CONTEXT = SCRIPT_DIR / "tiered_context_injector.py"
MEMORY_GUARDIAN = SCRIPT_DIR / "memory_guardian.py"
METRICS_DIR = AGENT_HOME / "metrics"
GUARDIAN_HISTORY = METRICS_DIR / "guardian_status_history.jsonl"
GUARDIAN_HISTORY_LIMIT = 500
SESSIONS_DIR = AGENT_HOME / "sessions"
SESSION_TO_GBRAIN_CHECKPOINT = AGENT_HOME / ".session_to_gbrain_checkpoint.json"
CONSOLIDATION_DRAIN_MIN_PENDING = 20
CONSOLIDATION_DRAIN_MIN_AGE_SECONDS = 1800
CONSOLIDATION_DRAIN_MAX_CYCLES = 2
CONSOLIDATION_DRAIN_POLL_SECONDS = 8

DEFAULT_RECALLS = [
    "memory",
    "stock",
    "模型用量",
    "重启hermes",
]


def run_step(name: str, cmd: list[str], timeout: int = 180) -> dict:
    started = datetime.now().isoformat(timespec="seconds")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "name": name,
            "cmd": cmd,
            "started_at": started,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "").strip()[:4000],
            "stderr": (proc.stderr or "").strip()[:4000],
            "ok": proc.returncode == 0,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "cmd": cmd,
            "started_at": started,
            "returncode": 124,
            "stdout": ((exc.stdout or "") if isinstance(exc.stdout, str) else "").strip()[:4000],
            "stderr": ((exc.stderr or "") if isinstance(exc.stderr, str) else "").strip()[:4000],
            "ok": False,
            "error": f"timeout after {timeout}s",
        }
    except Exception as exc:
        return {
            "name": name,
            "cmd": cmd,
            "started_at": started,
            "returncode": 1,
            "stdout": "",
            "stderr": "",
            "ok": False,
            "error": str(exc),
        }


def maybe_add_step(steps: list[dict], path: Path, name: str, cmd: list[str], timeout: int = 180) -> None:
    if path.exists():
        steps.append(run_step(name, cmd, timeout=timeout))


def session_to_gbrain_batch_size() -> int:
    try:
        total_sessions = sum(1 for _ in SESSIONS_DIR.glob("*.json"))
        processed_sessions = 0
        if SESSION_TO_GBRAIN_CHECKPOINT.exists():
            checkpoint = json.loads(SESSION_TO_GBRAIN_CHECKPOINT.read_text(encoding="utf-8"))
            processed_sessions = len(checkpoint.get("processed_sessions", []))
        backlog = max(total_sessions - processed_sessions, 0)
        if backlog >= 5000:
            return 200
        if backlog >= 2000:
            return 120
        if backlog >= 500:
            return 60
        return 20
    except Exception as exc:
        print(f"[maintenance_cycle] failed to read backlog, using default batch: {exc}", file=sys.stderr)
        return 20


def append_guardian_history(payload: dict, steps: list[dict]) -> None:
    guardian_step = next((step for step in steps if step.get("name") == "memory_guardian_status" and step.get("ok")), None)
    if not guardian_step:
        return
    try:
        guardian_status = json.loads(guardian_step.get("stdout") or "{}")
    except Exception:
        return
    snapshot = {
        "ran_at": payload.get("ran_at"),
        "maintenance_ok": payload.get("ok"),
        "session_to_gbrain_batch": payload.get("session_to_gbrain_batch"),
        "guardian": guardian_status,
    }
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        existing: list[str] = []
        if GUARDIAN_HISTORY.exists():
            existing = GUARDIAN_HISTORY.read_text(encoding="utf-8").splitlines()
        existing.append(json.dumps(snapshot, ensure_ascii=False))
        if len(existing) > GUARDIAN_HISTORY_LIMIT:
            existing = existing[-GUARDIAN_HISTORY_LIMIT:]
        GUARDIAN_HISTORY.write_text("\n".join(existing) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"[maintenance_cycle] failed to write guardian history: {exc}", file=sys.stderr)


def main() -> int:
    steps: list[dict] = []
    now = datetime.now()
    batch_size = session_to_gbrain_batch_size()
    if now.hour == 3 and now.minute < 10:
        maybe_add_step(
            steps,
            MEMORY_SNAPSHOT,
            "memory_snapshot_backup",
            [PYTHON, str(MEMORY_SNAPSHOT)],
            timeout=600,
        )
    maybe_add_step(
        steps,
        SESSION_TO_GBRAIN,
        "session_to_gbrain",
        [PYTHON, str(SESSION_TO_GBRAIN), f"--batch={batch_size}"],
        timeout=540 if batch_size >= 120 else 360 if batch_size >= 60 else 240,
    )
    maybe_add_step(
        steps,
        GOVERNANCE_REBUILD,
        "memory_governance_rebuild",
        [PYTHON, str(GOVERNANCE_REBUILD), "--force", "--quiet"],
        timeout=300,
    )
    maybe_add_step(
        steps,
        MEMORY_GUARDIAN,
        "memory_guardian_drain_consolidation",
        [PYTHON,
         str(MEMORY_GUARDIAN),
            "--drain-consolidation",
            f"--min-pending={CONSOLIDATION_DRAIN_MIN_PENDING}",
            f"--min-age-seconds={CONSOLIDATION_DRAIN_MIN_AGE_SECONDS}",
            f"--max-cycles={CONSOLIDATION_DRAIN_MAX_CYCLES}",
            f"--poll-seconds={CONSOLIDATION_DRAIN_POLL_SECONDS}",
        ],
        timeout=120,
    )
    maybe_add_step(
        steps,
        TIERED_CONTEXT,
        "tiered_context_generate",
        [PYTHON, str(TIERED_CONTEXT), "--recall", *DEFAULT_RECALLS],
        timeout=180,
    )
    maybe_add_step(
        steps,
        MEMORY_GUARDIAN,
        "memory_guardian_status",
        [PYTHON, str(MEMORY_GUARDIAN), "--status"],
        timeout=60,
    )

    payload = {
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "session_to_gbrain_batch": batch_size,
        "steps": steps,
        "ok": all(step.get("ok") for step in steps) if steps else False,
    }
    append_guardian_history(payload, steps)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
