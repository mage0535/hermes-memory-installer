from __future__ import annotations

import re
import subprocess

from .models import EdgeCandidate


def plan_edges(candidates, existing, top_k=50):
    best = {}
    for edge in candidates:
        if edge.source == edge.target or not re.fullmatch(r"[A-Za-z0-9._-]+", edge.source + edge.target):
            continue
        key = (edge.source, edge.target, edge.edge_type)
        if key not in existing and (key not in best or edge.score > best[key].score):
            best[key] = edge
    outgoing, incoming, selected = {}, {}, []
    for edge in sorted(best.values(), key=lambda item: (-item.score, item.source, item.target, item.edge_type)):
        if outgoing.get(edge.source, 0) >= top_k or incoming.get(edge.target, 0) >= top_k:
            continue
        selected.append(edge)
        outgoing[edge.source] = outgoing.get(edge.source, 0) + 1
        incoming[edge.target] = incoming.get(edge.target, 0) + 1
    return selected


def apply_edges(edges, apply=False, binary="gbrain"):
    if not apply:
        return 0
    for edge in edges:
        result = subprocess.run([binary, "link", edge.source, edge.target, "--type", edge.edge_type], shell=False)
        if result.returncode:
            return result.returncode
    return 0
