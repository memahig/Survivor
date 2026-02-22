#!/usr/bin/env python3
"""
FILE: engine/core/near_duplicates.py
VERSION: 0.1
PURPOSE:
Deterministic near-duplicate claim linking.

v0:
- Uses stdlib difflib SequenceMatcher ratio.
- This is a placeholder for future embedding-based guardrail.
- Deterministic and auditable.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple


def _norm(s: str) -> str:
    return " ".join(s.lower().strip().split())


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def build_edges_from_claim_texts(
    claims_by_id: Dict[str, Dict[str, Any]],
    threshold: float = 0.92,
    max_links_per_claim: int = 3,
) -> List[Tuple[str, str]]:
    """
    Returns undirected edges (a,b) where similarity(text_a, text_b) >= threshold.
    Deterministic and deduplicated.
    Caps links per claim_id for stability.
    """
    ids = sorted(claims_by_id.keys())
    edges_set = set()
    links_count: Dict[str, int] = {cid: 0 for cid in ids}

    for i in range(len(ids)):
        a = ids[i]
        ta = claims_by_id[a].get("text", "")
        if not isinstance(ta, str) or not ta.strip():
            continue
        for j in range(i + 1, len(ids)):
            b = ids[j]
            tb = claims_by_id[b].get("text", "")
            if not isinstance(tb, str) or not tb.strip():
                continue

            if links_count[a] >= max_links_per_claim or links_count[b] >= max_links_per_claim:
                continue

            if similarity(ta, tb) >= threshold:
                edge = (a, b)  # i<j ensures undirected canonical form
                if edge not in edges_set:
                    edges_set.add(edge)
                    links_count[a] += 1
                    links_count[b] += 1

    return sorted(edges_set)