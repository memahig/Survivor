#!/usr/bin/env python3
"""
FILE: engine/analysis/claim_deduplicator.py
PURPOSE: Second-level story clustering of adjudicated claim groups.
         Groups semantically similar claims by Jaccard token overlap.
         Uses existing union-find from engine.core.voting.
RULES: pure, deterministic, no I/O, fail-closed.
"""

from __future__ import annotations

import re
from typing import Any, Dict, FrozenSet, List, Tuple

from engine.analysis.text_normalizer import jaccard_similarity, tokenize_for_similarity
from engine.core.voting import build_equivalence_groups, group_members


# ---- Material-difference guard ----

_NUMBER_RE = re.compile(r'\b\d[\d,.]*\b')
_YEAR_RE = re.compile(r'\b(?:19|20)\d{2}\b')
_CAUSAL_WORDS = frozenset({
    "caused", "led", "resulted", "due", "triggered",
    "brought", "contributed", "drove", "because", "responsible",
})


def _extract_actors(text: str) -> FrozenSet[str]:
    """Extract capitalized words as actor proxies."""
    words = text.split()
    actors = set()
    for w in words:
        if w and w[0].isupper() and w.isalpha() and len(w) > 1:
            actors.add(w.lower())
    return frozenset(actors)


def _claims_differ_materially(text_a: str, text_b: str) -> bool:
    """
    Return True if two claims differ in quantity, year, actor, or
    causal vocabulary — even if Jaccard similarity is high.

    This prevents clustering claims like:
    - "GDP grew 3%" vs "GDP grew 12%"
    - "Russia invaded in 2014" vs "Russia invaded in 2022"
    - "NATO caused the conflict" vs "Russia caused the conflict"
    - one claim with a stat and one without
    """
    # Different quantities (including one has numbers, other doesn't)
    nums_a = set(_NUMBER_RE.findall(text_a))
    nums_b = set(_NUMBER_RE.findall(text_b))
    if nums_a != nums_b:
        return True

    # Different years (including one has year, other doesn't)
    years_a = set(_YEAR_RE.findall(text_a))
    years_b = set(_YEAR_RE.findall(text_b))
    if years_a != years_b:
        return True

    # Different causal vocabulary (detects vocabulary divergence)
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    causal_a = words_a & _CAUSAL_WORDS
    causal_b = words_b & _CAUSAL_WORDS
    if causal_a and causal_b and causal_a != causal_b:
        return True

    # Different actors (< 50% overlap)
    actors_a = _extract_actors(text_a)
    actors_b = _extract_actors(text_b)
    if actors_a and actors_b:
        overlap = len(actors_a & actors_b)
        total = len(actors_a | actors_b)
        if total > 0 and overlap / total < 0.5:
            return True

    return False


# ---- Main clustering function ----

def cluster_story_claims(
    adjudicated_claims: List[Dict[str, Any]],
    threshold: float = 0.25,
) -> List[Dict[str, Any]]:
    """
    Group adjudicated claim groups into higher-level story clusters
    by normalized token overlap (Jaccard).

    The pipeline already handles near-duplicate merging via SequenceMatcher.
    This is a second-level grouping by topic similarity.

    Guards against false clustering: claims that pass the Jaccard threshold
    but differ materially (quantity, year, actor, causal framing) are kept
    separate via _claims_differ_materially().

    Args:
        adjudicated_claims: from run_state.adjudicated.claim_track.arena.adjudicated_claims
        threshold: Jaccard similarity threshold for clustering (default 0.25)

    Returns list of cluster dicts, sorted by cluster_id.
    Returns empty list on structural error (fail-closed).
    """
    if not isinstance(adjudicated_claims, list):
        return []

    # Build group_id -> (text, centrality, adjudication) index
    groups: Dict[str, Dict[str, Any]] = {}
    token_cache: Dict[str, frozenset] = {}

    for claim in adjudicated_claims:
        if not isinstance(claim, dict):
            continue
        gid = claim.get("group_id", "")
        if not isinstance(gid, str) or not gid:
            continue
        text = claim.get("text", "")
        if not isinstance(text, str):
            text = ""

        groups[gid] = {
            "text": text,
            "centrality": claim.get("centrality", 1),
            "adjudication": claim.get("adjudication", ""),
        }
        token_cache[gid] = tokenize_for_similarity(text)

    if not groups:
        return []

    # Build similarity edges (with material-difference guard)
    gids = sorted(groups.keys())
    edges: List[Tuple[str, str]] = []

    for i in range(len(gids)):
        for j in range(i + 1, len(gids)):
            a, b = gids[i], gids[j]
            sim = jaccard_similarity(token_cache[a], token_cache[b])
            if sim >= threshold and not _claims_differ_materially(
                groups[a]["text"], groups[b]["text"]
            ):
                edges.append((a, b))

    # Union-find clustering
    # Verified signature: build_equivalence_groups(edges: List[Tuple[str, str]]) -> Dict[str, str]
    if edges:
        parent = build_equivalence_groups(edges)
        clusters_map = group_members(parent)
    else:
        clusters_map = {}

    # Collect all group_ids that appeared in edges
    clustered_gids = set()
    for members in clusters_map.values():
        for m in members:
            clustered_gids.add(m)

    # Add singletons (groups not in any edge)
    for gid in gids:
        if gid not in clustered_gids:
            clusters_map[gid] = [gid]

    # Build output
    results: List[Dict[str, Any]] = []
    cluster_num = 0

    for rep in sorted(clusters_map.keys()):
        members = sorted(clusters_map[rep])
        cluster_num += 1
        cluster_id = f"SC{cluster_num:03d}"

        # Pick longest text as canonical
        texts = [(groups[m]["text"], m) for m in members if m in groups]
        canonical_text = max(texts, key=lambda t: len(t[0]))[0] if texts else ""

        # Max centrality
        centralities = [
            groups[m].get("centrality", 1)
            for m in members if m in groups
        ]
        max_centrality = max(centralities) if centralities else 1
        if not isinstance(max_centrality, int):
            max_centrality = 1

        # Adjudication summary
        adj_counts = {"kept": 0, "rejected": 0, "downgraded": 0}
        for m in members:
            if m in groups:
                adj = groups[m].get("adjudication", "")
                if adj in adj_counts:
                    adj_counts[adj] += 1

        results.append({
            "cluster_id": cluster_id,
            "member_group_ids": members,
            "canonical_text": canonical_text,
            "max_centrality": max_centrality,
            "adjudication_summary": adj_counts,
        })

    return results
