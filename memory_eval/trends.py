from __future__ import annotations


def _reports_by_registry(payload: dict) -> dict[str, dict]:
    return {item.get("registry", ""): item for item in payload.get("reports", []) if item.get("registry")}


def compare_report_payloads(current: dict, previous: dict | None) -> dict | None:
    if not previous:
        return None
    previous_by_registry = _reports_by_registry(previous)
    comparison: dict[str, dict] = {}
    for registry, report in _reports_by_registry(current).items():
        old = previous_by_registry.get(registry)
        if not old:
            continue
        metrics = {}
        for name, value in report.get("metrics", {}).items():
            old_value = old.get("metrics", {}).get(name)
            if isinstance(value, (int, float)) and isinstance(old_value, (int, float)):
                metrics[name] = {
                    "current": value,
                    "previous": old_value,
                    "delta": round(value - old_value, 6),
                }
        if metrics:
            comparison[registry] = metrics
    return comparison or None
