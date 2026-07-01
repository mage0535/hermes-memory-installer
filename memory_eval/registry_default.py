"""Privacy-safe synthetic evaluation registry."""

from __future__ import annotations


_CATEGORIES = (
    ("accurate_retrieval", 12),
    ("conflict_resolution", 10),
    ("temporal_understanding", 10),
    ("test_time_learning", 8),
)

_LAYERS = ("memory_tool", "hindsight", "governance", "gbrain")


def _build_registry() -> list[dict]:
    registry: list[dict] = []
    number = 1
    for category, count in _CATEGORIES:
        for offset in range(count):
            layer = _LAYERS[offset % len(_LAYERS)]
            field = f"synthetic_field_{number:03d}"
            content = f"{field}=<SYNTHETIC_VALUE_{number:03d}>"
            registry.append(
                {
                    "id": f"eval_{number:03d}",
                    "category": category,
                    "query": f"Recall fictional {category.replace('_', ' ')} fact {number}",
                    "expected_fields": [field],
                    "expected_layer": layer,
                    "expected_min_score": 0.7,
                    "conflict_expected": category == "conflict_resolution",
                    "temporal_context": (
                        {"mode": "current", "reference": "<SYNTHETIC_DATE>"}
                        if category == "temporal_understanding"
                        else None
                    ),
                    "synthetic_hits": [
                        {"layer": layer, "score": 0.95, "content": content}
                    ],
                }
            )
            number += 1
    return registry


REGISTRY = _build_registry()
