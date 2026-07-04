from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .registry_loader import load_registries

SECRET_PATTERNS = (
    re.compile(r"\b(?:sk|ghp|github_pat)-?[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    re.compile(r"(?:https?|postgresql)://[^/@\s]+@"),
)


def lint_registry(cases: list[dict]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, case in enumerate(cases):
        case_id = str(case.get("id", f"case_{index}"))
        if case_id in seen:
            issues.append({"case_id": case_id, "rule": "duplicate_id"})
        seen.add(case_id)
        serialized = json.dumps(case, ensure_ascii=False)
        for pattern in SECRET_PATTERNS:
            if pattern.search(serialized):
                issues.append({"case_id": case_id, "rule": "secret_like"})
                break
        missing = {"id", "category", "query", "expected_fields", "expected_layer"} - set(case)
        for field in sorted(missing):
            issues.append({"case_id": case_id, "rule": "missing_field", "field": field})
    return issues


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", choices=("default", "production", "all"), default="all")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    payload = {"ok": True, "registries": []}
    for loaded in load_registries(args.registry):
        cases = [case.__dict__ for case in loaded.cases]
        issues = lint_registry(cases)
        payload["registries"].append({"registry": loaded.name, "issues": issues, "error": loaded.error})
        if issues or loaded.error:
            payload["ok"] = False
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
