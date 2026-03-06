#!/usr/bin/env python3
"""
FILE: engine/analysis/load_bearing_claims.py
PURPOSE: Identify claims where failure collapses the article's argument.
         Merges two signals: argument_integrity (reviewer-derived) and centrality==3.
RULES: pure, deterministic, no I/O, fail-closed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set


def identify_load_bearing(
    adjudicated_claims: List[Dict[str, Any]],
    argument_integrity: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """
    Identify load-bearing claims using two converging signals:
    1. argument_integrity.load_bearing_claim_ids (reviewer-derived)
    2. centrality == 3 on adjudicated groups

    Important: claim_ids in argument_integrity are raw reviewer claim IDs.
    These must be matched against group.member_claim_ids to find group_ids.

    Args:
        adjudicated_claims: from run_state.adjudicated.claim_track.arena.adjudicated_claims
        argument_integrity: from run_state.adjudicated.structural_forensics.argument_integrity
                            (may be None)

    Returns dict with load_bearing_group_ids, weak_link_group_ids, etc.
    """
    if not isinstance(adjudicated_claims, list):
        return _empty_result("centrality_only")

    # Extract claim_id sets from argument_integrity
    ai_load_bearing_ids: Set[str] = set()
    ai_weak_link_ids: Set[str] = set()
    fragility = "unknown"
    source = "centrality_only"

    if isinstance(argument_integrity, dict):
        for cid in argument_integrity.get("load_bearing_claim_ids", []):
            if isinstance(cid, str) and cid.strip():
                ai_load_bearing_ids.add(cid)
        for cid in argument_integrity.get("weak_link_claim_ids", []):
            if isinstance(cid, str) and cid.strip():
                ai_weak_link_ids.add(cid)
        fragility = argument_integrity.get("merged_argument_fragility", "unknown")
        if not isinstance(fragility, str):
            fragility = "unknown"
        if ai_load_bearing_ids or ai_weak_link_ids:
            source = "argument_integrity+centrality"

    # Build group_id -> (text, centrality, member_claim_ids) index
    load_bearing_group_ids: List[str] = []
    load_bearing_texts: List[str] = []
    weak_link_group_ids: List[str] = []
    weak_link_texts: List[str] = []

    for claim in adjudicated_claims:
        if not isinstance(claim, dict):
            continue

        gid = claim.get("group_id", "")
        if not isinstance(gid, str) or not gid:
            continue

        text = claim.get("text", "")
        if not isinstance(text, str):
            text = ""

        centrality = claim.get("centrality", 1)
        if not isinstance(centrality, int):
            centrality = 1

        member_claim_ids = claim.get("member_claim_ids", [])
        if not isinstance(member_claim_ids, list):
            member_claim_ids = []

        # Check if any member claim_id is in the load-bearing set
        member_set = set(
            cid for cid in member_claim_ids
            if isinstance(cid, str) and cid.strip()
        )

        is_load_bearing = (
            centrality >= 3
            or bool(member_set & ai_load_bearing_ids)
        )

        is_weak_link = bool(member_set & ai_weak_link_ids)

        if is_load_bearing and gid not in load_bearing_group_ids:
            load_bearing_group_ids.append(gid)
            load_bearing_texts.append(text)

        if is_weak_link and gid not in weak_link_group_ids:
            weak_link_group_ids.append(gid)
            weak_link_texts.append(text)

    return {
        "load_bearing_group_ids": sorted(load_bearing_group_ids),
        "load_bearing_texts": load_bearing_texts,
        "weak_link_group_ids": sorted(weak_link_group_ids),
        "weak_link_texts": weak_link_texts,
        "argument_fragility": fragility,
        "source": source,
    }


def _empty_result(source: str) -> Dict[str, Any]:
    """Return empty result structure."""
    return {
        "load_bearing_group_ids": [],
        "load_bearing_texts": [],
        "weak_link_group_ids": [],
        "weak_link_texts": [],
        "argument_fragility": "unknown",
        "source": source,
    }
