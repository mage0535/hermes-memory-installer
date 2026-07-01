from dataclasses import dataclass


@dataclass(frozen=True)
class EdgeCandidate:
    source: str
    target: str
    edge_type: str
    score: float
    provenance: str
