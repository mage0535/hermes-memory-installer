from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from governance.policy import MemoryPolicy, upsert_policy
from runtime_paths import RuntimePaths


def _bool_env(name: str) -> bool:
    value = os.getenv(name, "false").lower()
    if value not in {"true", "1", "yes", "false", "0", "no"}:
        raise ValueError(f"invalid boolean for {name}")
    return value in {"true", "1", "yes"}


class MidTermMemory:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else RuntimePaths.from_agent_home().sidecar_home / "mtm.jsonl"

    def retain(self, content: str, source: str, status: str = "pending") -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        item = {"content": content, "source": source, "created_at": time.time(), "status": status}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        return item

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def save(self, rows: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def _importance(content: str) -> float:
    text = content.casefold()
    score = 2.0
    if any(token in text for token in ("api", "key", "config", "server", "password", "preference", "policy")):
        score += 2.0
    if len(content) > 80:
        score += 0.5
    return min(5.0, score)


def consolidate(
    store_path: str | Path | None = None,
    governance_db: str | Path | None = None,
    apply: bool = False,
):
    if not _bool_env("MTM_ENABLED"):
        return {"status": "disabled", "dry_run": True}
    store = MidTermMemory(store_path)
    rows = store.load()
    db = Path(governance_db) if governance_db is not None else RuntimePaths.from_agent_home().governance_db
    promoted = 0
    for index, row in enumerate(rows):
        if row.get("status") != "pending":
            continue
        score = _importance(str(row.get("content", "")))
        row["importance_score"] = score
        if score >= 4.0:
            row["status"] = "promoted"
            promoted += 1
            if apply:
                upsert_policy(
                    db,
                    MemoryPolicy(
                        memory_id=f"mtm:{index}:{int(row.get('created_at', 0))}",
                        importance_score=score,
                        tier="mtm",
                        policy_confidence=0.75,
                        source_layer=str(row.get("source", "mtm")),
                        provenance="mtm_consolidation",
                        promotion_reason="mtm_high_importance",
                        fact_key="mtm",
                    ),
                )
        elif score < 2.5:
            row["status"] = "evicted"
        else:
            row["status"] = "merged"
    if apply:
        store.save(rows)
    return {"status": "consolidated", "dry_run": not apply, "processed": len(rows), "promoted": promoted}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store-path")
    parser.add_argument("--governance-db")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(consolidate(args.store_path, args.governance_db, apply=args.apply)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
