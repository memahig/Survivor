#!/usr/bin/env python3
"""
FILE: engine/analysis/omission_ranker.py
PURPOSE: Classify omissions as minor/important/load_bearing based on
         impact on central and load-bearing claims (not keywords).
RULES: pure, deterministic, no I/O, fail-closed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set


def rank_omissions(
    structural_forensics: Dict[str, Any],
    load_bearing_group_ids: List[str],
    adjudicated_claims: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Rank all merged omissions into severity tiers.

    Severity is impact-based:
    - load_bearing: concern in ("elevated","high") AND targets critical claim
    - important: targets critical claim, OR concern in ("elevated","high"),
                 OR fragility-boosted (high fragility + substantive text)
    - minor: everything else

    The fragility boost ensures that for structurally fragile articles
    (advocacy/propaganda patterns), single-reviewer omissions with
    substantive text are surfaced rather than silently dropped.

    Args:
        structural_forensics: run_state.adjudicated.structural_forensics
        load_bearing_group_ids: from load_bearing_claims module
        adjudicated_claims: for centrality lookup

    Returns all omissions with added severity and severity_reason fields.
    Sorted: load_bearing first, then important, then minor.
    Within tier, by reviewer count descending.
    """
    if not isinstance(structural_forensics, dict):
        return []

    # Extract argument fragility for boost logic
    ai = structural_forensics.get("argument_integrity")
    merged_fragility = ""
    if isinstance(ai, dict):
        merged_fragility = ai.get("merged_argument_fragility", "")
    high_fragility = merged_fragility in ("high", "elevated")

    # Build centrality lookup: claim_id -> centrality
    high_centrality_ids: Set[str] = set()
    if isinstance(adjudicated_claims, list):
        for claim in adjudicated_claims:
            if not isinstance(claim, dict):
                continue
            centrality = claim.get("centrality", 1)
            if isinstance(centrality, int) and centrality >= 3:
                gid = claim.get("group_id", "")
                if gid:
                    high_centrality_ids.add(gid)
                for cid in claim.get("member_claim_ids", []):
                    if isinstance(cid, str) and cid:
                        high_centrality_ids.add(cid)

    lb_set = set(load_bearing_group_ids) if isinstance(load_bearing_group_ids, list) else set()

    # Collect all omission types
    all_omissions: List[Dict[str, Any]] = []

    for kind_key, kind_label in [
        ("article_omissions", "article_omission"),
        ("framing_omissions", "framing_omission"),
        ("claim_omissions", "claim_omission"),
    ]:
        items = structural_forensics.get(kind_key, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            om = dict(item)  # shallow copy — don't mutate original
            om["kind"] = om.get("kind", kind_label)
            all_omissions.append(om)

    # Classify severity
    _SEVERITY_ORDER = {"load_bearing": 0, "important": 1, "minor": 2}

    for om in all_omissions:
        concern = om.get("concern_level", "low")
        target_claim_id = om.get("target_claim_id", "")
        affected_claim_ids = om.get("affected_claim_ids", [])
        if not isinstance(affected_claim_ids, list):
            affected_claim_ids = []

        # Check if this omission affects load-bearing or high-centrality claims
        affects_critical = False
        reason_parts: List[str] = []

        # Check target_claim_id (claim_omissions have this)
        if isinstance(target_claim_id, str) and target_claim_id:
            if target_claim_id in lb_set:
                affects_critical = True
                reason_parts.append(f"targets load-bearing claim {target_claim_id}")
            elif target_claim_id in high_centrality_ids:
                affects_critical = True
                reason_parts.append(f"targets high-centrality claim {target_claim_id}")

        # Check affected_claim_ids (article_omissions may have this)
        for acid in affected_claim_ids:
            if isinstance(acid, str):
                if acid in lb_set:
                    affects_critical = True
                    reason_parts.append(f"affects load-bearing claim {acid}")
                elif acid in high_centrality_ids:
                    affects_critical = True
                    reason_parts.append(f"affects high-centrality claim {acid}")

        # Fragility boost: when the article is structurally fragile,
        # single-reviewer omissions with substantive text (> 30 chars)
        # are boosted to "important". This prevents the common failure
        # where reviewers describe the same omission differently,
        # conservative text merging keeps them separate, and ALL
        # omissions end up as "minor".
        merged_text = om.get("merged_text", "")
        has_substantive_text = isinstance(merged_text, str) and len(merged_text.strip()) > 30
        fragility_boosted = high_fragility and has_substantive_text

        # Severity model: impact-aware with fragility boost.
        if affects_critical and concern in ("elevated", "high"):
            severity = "load_bearing"
            severity_reason = "; ".join(reason_parts) + f" (concern: {concern})"
        elif affects_critical:
            severity = "important"
            severity_reason = "; ".join(reason_parts) if reason_parts else "affects critical claims"
        elif concern in ("elevated", "high"):
            severity = "important"
            severity_reason = f"concern level: {concern}"
        elif fragility_boosted:
            severity = "important"
            severity_reason = f"fragility boost: argument fragility is {merged_fragility}"
        else:
            severity = "minor"
            severity_reason = f"concern level: {concern}"

        om["severity"] = severity
        om["severity_reason"] = severity_reason

    # Sort: severity tier, then reviewer count descending
    all_omissions.sort(key=lambda om: (
        _SEVERITY_ORDER.get(om.get("severity", "minor"), 9),
        -len(om.get("supporting_reviewers", []) if isinstance(om.get("supporting_reviewers"), list) else []),
    ))

    return all_omissions
