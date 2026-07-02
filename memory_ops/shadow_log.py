from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from governance.policy import apply_policy_to_candidates
from runtime_paths import RuntimePaths


def _memory_id(item: dict[str, Any]) -> str:
    return str(item.get("session_id") or item.get("object_id") or item.get("slug") or "")


def _top_ids(candidates: list[dict[str, Any]], top_k: int) -> list[str]:
    ordered = sorted(candidates, key=lambda item: float(item.get("score", item.get("rrf_score", 0.0)) or 0.0), reverse=True)
    return [_memory_id(item) for item in ordered[:top_k] if _memory_id(item)]


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def _rank_deltas(before: list[str], after: list[str]) -> tuple[list[str], list[str]]:
    before_rank = {memory_id: idx for idx, memory_id in enumerate(before)}
    after_rank = {memory_id: idx for idx, memory_id in enumerate(after)}
    promoted = [
        memory_id
        for memory_id, idx in after_rank.items()
        if memory_id not in before_rank or idx < before_rank[memory_id]
    ]
    demoted = [
        memory_id
        for memory_id, idx in before_rank.items()
        if memory_id not in after_rank or after_rank[memory_id] > idx
    ]
    return promoted, demoted


def record_shadow_event(
    query: str,
    candidates: list[dict[str, Any]],
    db_path: str | Path,
    log_path: str | Path,
    top_k: int = 5,
) -> dict[str, Any]:
    started = time.perf_counter()
    before = _top_ids(candidates, top_k)
    ranked = apply_policy_to_candidates(db_path, [dict(item) for item in candidates])
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    after = _top_ids(ranked, top_k)
    promoted, demoted = _rank_deltas(before, after)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query_hash": _hash(query or ""),
        "query_length": len(query or ""),
        "candidate_count": len(candidates),
        "top_k": top_k,
        "before_top_ids": before,
        "after_top_ids": after,
        "promoted_ids": promoted,
        "demoted_ids": demoted,
        "changed": before != after,
        "elapsed_ms": elapsed_ms,
        "candidate_set_hash": _hash("|".join(sorted({_memory_id(item) for item in candidates if _memory_id(item)}))),
    }
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def _load_events(log_path: str | Path, days: int) -> list[dict[str, Any]]:
    path = Path(log_path)
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        timestamp = event.get("timestamp")
        if timestamp:
            try:
                if datetime.fromisoformat(timestamp) < cutoff:
                    continue
            except ValueError:
                pass
        events.append(event)
    return events


def analyze_shadow_log(log_path: str | Path, days: int = 7, min_events: int = 20) -> dict[str, Any]:
    events = _load_events(log_path, days)
    changed = [event for event in events if event.get("changed")]
    promoted = Counter(memory_id for event in events for memory_id in event.get("promoted_ids", []))
    demoted = Counter(memory_id for event in events for memory_id in event.get("demoted_ids", []))
    elapsed = [float(event.get("elapsed_ms", 0.0) or 0.0) for event in events]
    event_count = len(events)
    change_rate = round(len(changed) / event_count, 4) if event_count else 0.0
    avg_elapsed = round(sum(elapsed) / event_count, 3) if event_count else 0.0
    if event_count < min_events:
        recommendation = "continue_shadow_until_enough_data"
    elif avg_elapsed > 100:
        recommendation = "keep_disabled_latency_too_high"
    elif change_rate >= 0.05 and promoted:
        recommendation = "enable_policy_ranking_gray"
    elif change_rate < 0.01:
        recommendation = "keep_disabled_low_impact"
    else:
        recommendation = "continue_shadow_review_samples"
    return {
        "window_days": days,
        "events": event_count,
        "changed_events": len(changed),
        "change_rate": change_rate,
        "avg_elapsed_ms": avg_elapsed,
        "top_promoted_ids": [{"memory_id": key, "count": count} for key, count in promoted.most_common(10)],
        "top_demoted_ids": [{"memory_id": key, "count": count} for key, count in demoted.most_common(10)],
        "recommendation": recommendation,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze policy-ranking shadow logs without exposing memory text.")
    parser.add_argument("--agent-home")
    parser.add_argument("--log")
    parser.add_argument("--output")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--min-events", type=int, default=20)
    args = parser.parse_args(argv)
    paths = RuntimePaths.from_agent_home(args.agent_home)
    log_path = Path(args.log) if args.log else paths.logs_dir / "memory-policy-shadow.jsonl"
    report = analyze_shadow_log(log_path, days=args.days, min_events=args.min_events)
    text = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
