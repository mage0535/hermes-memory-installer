#!/usr/bin/env python3
"""
Legacy domain memory helper.

Provides a lightweight, generic domain routing layer for local memory workflows.
This script is not part of the default sidecar install set, but it should stay
portable and free of project-specific labels.
"""

from __future__ import annotations

import json
import re
import sys

DOMAIN_CONFIG = {
    "project": {"limit": 350, "desc": "Project planning and execution"},
    "stock": {"limit": 350, "desc": "Market, portfolio, and trading notes"},
    "system": {"limit": 300, "desc": "System configuration and operations"},
    "marketing": {"limit": 250, "desc": "Campaigns, channels, and promotion"},
    "relationship": {"limit": 250, "desc": "People, teams, and collaboration"},
    "general": {"limit": 400, "desc": "General-purpose notes"},
}
TOTAL_LIMIT = 1900

DOMAIN_PREFIXES = {
    "Project:": "project",
    "Milestone:": "project",
    "Stock:": "stock",
    "Portfolio:": "stock",
    "System:": "system",
    "Config:": "system",
    "Marketing:": "marketing",
    "Campaign:": "marketing",
    "Relationship:": "relationship",
    "Contact:": "relationship",
}


def detect_domain(content: str) -> str:
    for prefix, domain in DOMAIN_PREFIXES.items():
        if content.startswith(prefix):
            return domain
    match = re.match(r"^@(\w+):", content)
    if match and match.group(1) in DOMAIN_CONFIG:
        return match.group(1)
    return "general"


def validate_domain(domain: str) -> bool:
    return domain in DOMAIN_CONFIG


def entries_by_domain(entries: list[str]) -> dict[str, list[str]]:
    domains = {domain: [] for domain in DOMAIN_CONFIG}
    for entry in entries:
        domains[detect_domain(entry)].append(entry)
    return domains


def domain_status(entries: list[str]) -> dict[str, dict]:
    grouped = entries_by_domain(entries)
    status = {}
    for domain, config in DOMAIN_CONFIG.items():
        domain_entries = grouped.get(domain, [])
        used = sum(len(entry) + 3 for entry in domain_entries)
        status[domain] = {
            "desc": config["desc"],
            "limit": config["limit"],
            "used": used,
            "entries": len(domain_entries),
            "pct": round(used / config["limit"] * 100, 1) if config["limit"] > 0 else 0,
        }
    return status


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: domain_memory.py list|status|check <domain> <content>")
        sys.exit(0)

    action = sys.argv[1]

    if action == "list":
        print("domain\t\tlimit\tdescription")
        print("-" * 60)
        for domain, config in DOMAIN_CONFIG.items():
            print(f"{domain:<15} {config['limit']:<6} {config['desc']}")
        print()
        print("prefix mapping:")
        for prefix, domain in sorted(DOMAIN_PREFIXES.items(), key=lambda item: item[1]):
            print(f"  {prefix} -> @{domain}")

    elif action == "status":
        result = {
            "domains": {domain: {"limit": config["limit"], "desc": config["desc"]} for domain, config in DOMAIN_CONFIG.items()},
            "total_limit": TOTAL_LIMIT,
            "total_used": "N/A (run inside a memory-aware workflow)",
            "usage_pct": "N/A",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif action == "check" and len(sys.argv) >= 4:
        domain = sys.argv[2]
        content = sys.argv[3]

        if not validate_domain(domain):
            print(json.dumps({"allowed": False, "error": f"Unknown domain: {domain}"}))
            sys.exit(0)

        auto_domain = detect_domain(content)
        if auto_domain != domain:
            print(
                json.dumps(
                    {
                        "allowed": True,
                        "warning": f"content looks like @{auto_domain} rather than @{domain}",
                        "auto_domain": auto_domain,
                    },
                    ensure_ascii=False,
                )
            )
        else:
            print(json.dumps({"allowed": True}, ensure_ascii=False))

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
