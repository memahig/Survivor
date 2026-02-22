#!/usr/bin/env python3
"""
FILE: engine/core/voting.py
VERSION: 0.1
PURPOSE:
Pure voting/adjudication helpers for Survivor.

CONTRACT:
- No I/O
- No global state
- Deterministic given inputs + config
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple


Vote = str          # "supported" | "unsupported" | "undetermined"
Confidence = str    # "low" | "medium" | "high"


@dataclass(frozen=True)
class VoteTally:
    supported_score: float
    unsupported_score: float
    supported_votes: int
    unsupported_votes: int
    undetermined_votes: int


def _conf_weight(conf: Confidence, config: Dict[str, Any]) -> float:
    weights = config["confidence_weights"]
    if conf not in weights:
        raise RuntimeError(f"Unknown confidence: {conf}")
    return float(weights[conf])


def _model_weight(model: str, config: Dict[str, Any]) -> float:
    mw = config["model_weights"]
    if model not in mw:
        raise RuntimeError(f"Unknown model in model_weights: {model}")
    return float(mw[model])


def tally_reviewer_votes(
    reviewer_votes: Dict[str, Dict[str, str]],
    config: Dict[str, Any],
) -> VoteTally:
    """
    reviewer_votes format:
      {
        "openai": {"vote":"supported","confidence":"high"},
        "gemini": {"vote":"unsupported","confidence":"medium"},
        "claude": {"vote":"undetermined","confidence":"high"}
      }
    """
    sup = 0.0
    unsup = 0.0
    sup_n = 0
    unsup_n = 0
    und_n = 0

    for model, vc in reviewer_votes.items():
        vote = vc.get("vote")
        conf = vc.get("confidence")
        if vote not in ("supported", "unsupported", "undetermined"):
            raise RuntimeError(f"Unknown vote: {vote}")
        if conf not in ("low", "medium", "high"):
            raise RuntimeError(f"Unknown confidence: {conf}")

        w = _conf_weight(conf, config) * _model_weight(model, config)

        if vote == "supported":
            sup += w
            sup_n += 1
        elif vote == "unsupported":
            unsup += w
            unsup_n += 1
        else:
            und_n += 1

    return VoteTally(
        supported_score=sup,
        unsupported_score=unsup,
        supported_votes=sup_n,
        unsupported_votes=unsup_n,
        undetermined_votes=und_n,
    )


def decide_status(tally: VoteTally, config: Dict[str, Any]) -> str:
    """
    Returns: "kept" | "rejected" | "downgraded"
    Deterministic margin rule.
    """
    margin = float(config["decision_margin"])
    if tally.supported_score >= tally.unsupported_score + margin:
        return "kept"
    if tally.unsupported_score >= tally.supported_score + margin:
        return "rejected"
    return "downgraded"


# ----------------------------
# Near-duplicate grouping
# ----------------------------

def build_equivalence_groups(edges: List[Tuple[str, str]]) -> Dict[str, str]:
    """
    Build union-find groups from (a,b) edges meaning a ~ b.

    Returns parent map where find(x) gives canonical representative.
    Pure + deterministic with path compression.
    """
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        if x not in parent:
            parent[x] = x
            return x
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra = find(a)
        rb = find(b)
        if ra == rb:
            return
        # deterministic union: lexicographically smaller root becomes parent
        if ra < rb:
            parent[rb] = ra
        else:
            parent[ra] = rb

    for a, b in edges:
        union(a, b)

    # ensure all nodes appear
    for a, b in edges:
        find(a)
        find(b)

    return parent


def group_members(parent: Dict[str, str]) -> Dict[str, List[str]]:
    """
    Convert parent map into rep -> members list.
    """
    reps: Dict[str, List[str]] = {}
    for node in list(parent.keys()):
        rep = node
        while parent[rep] != rep:
            rep = parent[rep]
        reps.setdefault(rep, []).append(node)
    # deterministic member ordering
    for rep in reps:
        reps[rep].sort()
    return reps