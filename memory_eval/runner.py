"""Evaluation orchestration and command-line interface."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .adapters import LiveAdapter, SyntheticAdapter
from .metrics import calculate_metrics
from .models import EvalReport
from .registry_loader import load_registries
from .trends import compare_report_payloads


def run_eval(category="all", model=None, mode="smoke", registry="all", backend="synthetic", adapter=None, k=5):
    del model
    if adapter is None:
        adapter = LiveAdapter() if backend == "live" else SyntheticAdapter()
    reports = []
    for loaded in load_registries(registry):
        if loaded.error:
            reports.append(EvalReport(loaded.name, 0, calculate_metrics([], {}).to_dict(), {}, (loaded.error,)))
            continue
        cases = [case for case in loaded.cases if category == "all" or case.category == category]
        if mode == "smoke":
            selected, counts = [], Counter()
            for case in cases:
                if counts[case.category] < 3:
                    selected.append(case)
                    counts[case.category] += 1
            cases = selected
        results = [adapter.recall(case, k) for case in cases]
        expected = {case.id: tuple(case.expected_fields) for case in cases}
        metrics = calculate_metrics(results, expected).to_dict()
        reports.append(EvalReport(loaded.name, len(results), metrics, dict(Counter(c.category for c in cases))))
    return reports


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--registry", choices=("default", "production", "all"), default="all")
    parser.add_argument("--backend", choices=("synthetic", "live"), default="synthetic")
    parser.add_argument("--category", default="all")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output")
    parser.add_argument("--previous")
    args = parser.parse_args(argv)
    reports = run_eval(args.category, mode=args.mode, registry=args.registry, backend=args.backend, k=args.k)
    payload = {"reports": [asdict(report) for report in reports], "comparison": None}
    if args.previous:
        previous_path = Path(args.previous)
        if previous_path.exists():
            payload["comparison"] = compare_report_payloads(payload, json.loads(previous_path.read_text(encoding="utf-8")))
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temporary, target)
    for report in reports:
        print(f"=== MEMORY EVAL REPORT ({report.registry}) ===")
        print(f"evaluated: {report.evaluated_count} | recall@k: {report.metrics['recall_at_k']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
