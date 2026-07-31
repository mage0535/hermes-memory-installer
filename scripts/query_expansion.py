#!/usr/bin/env python3
from __future__ import annotations

import re


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}")

EXPANSION_RULES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        (
            "\u6700\u8fd1",
            "\u4e0a\u6b21",
            "\u521a\u624d",
            "\u521a\u521a",
            "\u8ba8\u8bba",
            "\u4f1a\u8bdd",
            "recent",
            "latest",
        ),
        (
            "\u6700\u8fd1",
            "\u8ba8\u8bba",
            "\u4f1a\u8bdd",
            "\u4e0a\u6b21",
            "recent",
            "latest",
            "session",
            "summary",
        ),
    ),
    (
        (
            "\u670b\u53cb",
            "\u5173\u7cfb",
            "\u5fae\u4fe1",
            "\u5b89\u6170",
            "\u504f\u597d",
            "\u559c\u6b22",
            "friend",
            "relationship",
            "preference",
        ),
        (
            "\u670b\u53cb",
            "\u5173\u7cfb",
            "\u5fae\u4fe1",
            "\u5b89\u6170",
            "\u504f\u597d",
            "\u559c\u6b22",
            "friend",
            "relationship",
            "preference",
            "profile",
        ),
    ),
    (
        (
            "\u8bb0\u5fc6",
            "\u8bb0\u5fc6\u4f53",
            "\u53ec\u56de",
            "\u5916\u6302",
            "hindsight",
            "gbrain",
            "l3",
            "recall",
            "memory",
        ),
        (
            "\u8bb0\u5fc6",
            "\u8bb0\u5fc6\u4f53",
            "\u53ec\u56de",
            "\u5916\u6302",
            "\u95ee\u9898",
            "\u7f3a\u9677",
            "\u4e09\u7aef",
            "hindsight",
            "gbrain",
            "l3",
            "recall",
            "memory",
            "sidecar",
        ),
    ),
    (
        (
            "\u544a\u8b66",
            "\u62a5\u9519",
            "\u5f02\u5e38",
            "\u95ee\u9898",
            "\u5904\u7406",
            "alert",
            "error",
            "issue",
            "incident",
        ),
        (
            "\u544a\u8b66",
            "\u62a5\u9519",
            "\u5f02\u5e38",
            "\u95ee\u9898",
            "\u5904\u7406",
            "alert",
            "error",
            "issue",
            "incident",
            "action",
        ),
    ),
    (
        (
            "\u9879\u76ee",
            "\u4e09\u7aef",
            "\u540c\u6b65",
            "\u4e00\u81f4",
            "project",
            "deploy",
            "github",
        ),
        (
            "\u9879\u76ee",
            "\u4e09\u7aef",
            "\u540c\u6b65",
            "\u4e00\u81f4",
            "\u670d\u52a1\u5668",
            "project",
            "deploy",
            "github",
            "server",
        ),
    ),
)


def raw_query_terms(query: str) -> list[str]:
    terms = TOKEN_RE.findall(query or "")
    if not terms and query and query.strip():
        return [query.strip()]
    return terms


def expanded_query_terms(query: str) -> list[str]:
    raw_terms = raw_query_terms(query)
    lowered_query = (query or "").lower()
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        value = str(term or "").strip()
        key = value.lower()
        if len(value) < 2 or key in seen:
            return
        seen.add(key)
        terms.append(value)

    for term in raw_terms:
        add(term)

    for triggers, aliases in EXPANSION_RULES:
        if any(trigger.lower() in lowered_query for trigger in triggers):
            for alias in aliases:
                add(alias)

    return terms

