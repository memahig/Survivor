#!/usr/bin/env python3
"""
FILE: engine/arena/judge.py
VERSION: 0.2
PURPOSE:
Arena adjudication — Milestone 2.

Weighted W_score consensus with union-find near-duplicate grouping.

CONTRACT:
- Reads phase2 reviewer packs from run_state.
- Groups claims via near_duplicate_of edges (union-find from engine.core.voting).
- Computes W_score = sum(Vote_i * Weight_i) / sum(Weight_i)
  where Vote_i = +1 (supported) / -1 (unsupported) / 0 (undetermined)
  and   Weight_i = conf_weight(confidence_i) * model_weight(reviewer_i).
- Emits status: kept / rejected / downgraded / insufficient.
- Fail-closed on 4 error traps (E1-E3 raise RuntimeError; E4 appends flag).
- No external I/O, no side effects. Deterministic given inputs.

THRESHOLDS:
  kept:         W_score >= 0.6
  rejected:     W_score <= -0.6
  downgraded:   0.2 <= |W_score| < 0.6
  insufficient: |W_score| < 0.2

ERROR TRAPS:
  E1: claim_id collision with divergent text       -> RuntimeError
  E2: self-link in near_duplicate_of               -> RuntimeError
  E3: near_duplicate_of references unknown claim   -> RuntimeError
  E4: >=2 reviewers support but share zero eids    -> flags: ["high_structural_risk"]

OUTPUT SCHEMA (per adjudicated group):
  {
    "group_id":              str,          # canonical claim_id (lex-smallest rep)
    "member_claim_ids":      [str, ...],   # sorted
    "canonical_text":        str | None,
    "status":                str,          # kept|rejected|downgraded|insufficient
    "wscore":                float,        # rounded to 6 dp
    "evidence_union":        [str, ...],   # sorted union of all member eids
    "contributing_reviewers":[str, ...],   # sorted
    "flags":                 [str, ...]    # optional; present only if non-empty
  }
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from engine.core.triage_utils import list_triage_claims
from engine.core.voting import build_equivalence_groups, group_members


# ---------------------------------------------------------------------------
# Threshold constants
# ---------------------------------------------------------------------------

_KEPT_THRESHOLD = 0.6
_REJECTED_THRESHOLD = -0.6
_DOWNGRADE_THRESHOLD = 0.2


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _vote_scalar(vote: str) -> float:
    if vote == "supported":
        return 1.0
    if vote == "unsupported":
        return -1.0
    return 0.0  # "undetermined" or unknown


def _compute_wscore(
    group_claim_ids: Set[str],
    phase2: Dict[str, Any],
    config: Dict[str, Any],
) -> float:
    """
    Compute normalized weighted score for a group.
    Returns 0.0 if no weighted votes exist (-> insufficient status).
    """
    conf_weights: Dict[str, float] = config.get("confidence_weights", {})
    model_weights: Dict[str, float] = config.get("model_weights", {})

    total_weight = 0.0
    weighted_sum = 0.0

    for reviewer, pack in phase2.items():
        if not isinstance(pack, dict):
            continue
        raw_mw = model_weights.get(reviewer, 1.0)
        try:
            m_weight = float(raw_mw)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"config.model_weights[{reviewer!r}] is not numeric: {raw_mw!r}"
            ) from exc
        for v in pack.get("cross_claim_votes", []):
            if not isinstance(v, dict):
                continue
            if v.get("claim_id") not in group_claim_ids:
                continue
            vote = v.get("vote", "undetermined")
            conf = v.get("confidence", "medium")
            raw_cw = conf_weights.get(conf, 1.0)
            try:
                c_weight = float(raw_cw)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"config.confidence_weights[{conf!r}] is not numeric: {raw_cw!r}"
                ) from exc
            w = c_weight * m_weight
            weighted_sum += _vote_scalar(vote) * w
            total_weight += w

    if total_weight == 0.0:
        return 0.0
    return weighted_sum / total_weight


def _decide_status_m2(wscore: float) -> str:
    if wscore >= _KEPT_THRESHOLD:
        return "kept"
    if wscore <= _REJECTED_THRESHOLD:
        return "rejected"
    if abs(wscore) >= _DOWNGRADE_THRESHOLD:
        return "downgraded"
    return "insufficient"


def _check_consensus_paradox(
    group_claim_ids: Set[str],
    phase2: Dict[str, Any],
) -> bool:
    """
    E4: Returns True if >=2 reviewers cast 'supported' votes for claims in
    this group but share zero overlapping evidence_eids across those claims.
    """
    # reviewer -> eids from claims they support within this group
    reviewer_support_eids: Dict[str, Set[str]] = {}

    for reviewer, pack in phase2.items():
        if not isinstance(pack, dict):
            continue

        # Identify which group claims this reviewer supports via cross_claim_votes
        supported_in_group: Set[str] = set()
        for v in pack.get("cross_claim_votes", []):
            if not isinstance(v, dict):
                continue
            cid = v.get("claim_id")
            if cid in group_claim_ids and v.get("vote") == "supported":
                supported_in_group.add(cid)

        if not supported_in_group:
            continue

        # Collect eids from the supported claims in this reviewer's own pack
        eids: Set[str] = set()
        for claim in list_triage_claims(pack):
            if not isinstance(claim, dict):
                continue
            if claim.get("claim_id") in supported_in_group:
                for eid in claim.get("evidence_eids", []):
                    if isinstance(eid, str) and eid:
                        eids.add(eid)

        reviewer_support_eids[reviewer] = eids

    if len(reviewer_support_eids) < 2:
        return False

    reviewers = sorted(reviewer_support_eids.keys())
    for i in range(len(reviewers)):
        for j in range(i + 1, len(reviewers)):
            r1, r2 = reviewers[i], reviewers[j]
            if not (reviewer_support_eids[r1] & reviewer_support_eids[r2]):
                return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def adjudicate(run_state: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adjudicate phase2 reviewer packs into a canonical group-level verdict.

    Returns:
        {"adjudicated_claims": [<group_dict>, ...]}   (groups sorted by group_id)

    Raises:
        RuntimeError: on E1 (collision), E2 (self-link), or E3 (dangling ref).
    """
    phase2 = run_state.get("phase2", {})

    # -------------------------------------------------------------------
    # Pass 1: Build claim registry; detect E1 (collision with divergent text)
    # -------------------------------------------------------------------
    # claim_id -> {"_claim_text": str|None, "source_reviewers": set, "evidence_eids": set}
    registry: Dict[str, Dict[str, Any]] = {}

    for reviewer, pack in phase2.items():
        if not isinstance(pack, dict):
            continue
        for claim in list_triage_claims(pack):
            if not isinstance(claim, dict):
                continue
            claim_id = claim.get("claim_id")
            if not claim_id:
                continue
            claim_text = claim.get("text")

            if claim_id in registry:
                # E1: collision guard
                existing_text = registry[claim_id].get("_claim_text")
                if (
                    existing_text is not None
                    and claim_text is not None
                    and existing_text != claim_text
                ):
                    raise RuntimeError(
                        f"Claim ID collision with divergent text for {claim_id!r}"
                    )
            else:
                registry[claim_id] = {
                    "_claim_text": claim_text,
                    "source_reviewers": set(),
                    "evidence_eids": set(),
                }

            registry[claim_id]["source_reviewers"].add(reviewer)
            for eid in claim.get("evidence_eids", []):
                if isinstance(eid, str) and eid:
                    registry[claim_id]["evidence_eids"].add(eid)

    all_claim_ids: Set[str] = set(registry.keys())

    # -------------------------------------------------------------------
    # Pass 2: Collect near_duplicate_of edges; detect E2 (self-link) and
    #         E3 (dangling reference)
    # -------------------------------------------------------------------
    nd_edges: List[Tuple[str, str]] = []

    for reviewer, pack in phase2.items():
        if not isinstance(pack, dict):
            continue
        for v in pack.get("cross_claim_votes", []):
            if not isinstance(v, dict):
                continue
            source_cid = v.get("claim_id")
            if not isinstance(source_cid, str) or not source_cid:
                continue
            if source_cid not in all_claim_ids:
                continue  # vote references unknown source; skip (validator concern)
            nd = v.get("near_duplicate_of")
            if not nd:
                continue
            for target in nd:
                if not isinstance(target, str) or not target:
                    continue
                # E2: self-link
                if target == source_cid:
                    raise RuntimeError(
                        f"Self-link in near_duplicate_of: {source_cid!r} references itself "
                        f"(reviewer: {reviewer!r})"
                    )
                # E3: dangling reference
                if target not in all_claim_ids:
                    raise RuntimeError(
                        f"near_duplicate_of dangling reference: {target!r} not found in "
                        f"claim registry (reviewer: {reviewer!r}, source: {source_cid!r})"
                    )
                nd_edges.append((source_cid, target))

    # -------------------------------------------------------------------
    # Pass 3: Group via union-find
    # Seed all claim_ids as self-edges so singletons appear in parent map.
    # -------------------------------------------------------------------
    seed_edges: List[Tuple[str, str]] = [(cid, cid) for cid in sorted(all_claim_ids)]
    parent = build_equivalence_groups(nd_edges + seed_edges)
    groups = group_members(parent)  # rep -> sorted [member, ...]

    # -------------------------------------------------------------------
    # Pass 4: Score and emit one result per group
    # -------------------------------------------------------------------
    adjudicated_claims: List[Dict[str, Any]] = []

    for group_id in sorted(groups.keys()):
        member_ids: List[str] = groups[group_id]  # sorted by group_members()
        group_set: Set[str] = set(member_ids)

        # Aggregate evidence and contributor sets
        evidence_union: Set[str] = set()
        contributing: Set[str] = set()
        canonical_text: Optional[str] = None

        for cid in member_ids:
            entry = registry.get(cid, {})
            evidence_union.update(entry.get("evidence_eids", set()))
            contributing.update(entry.get("source_reviewers", set()))
            if cid == group_id:
                t = entry.get("_claim_text")
                if t:
                    canonical_text = t

        wscore = _compute_wscore(group_set, phase2, config)
        status = _decide_status_m2(wscore)

        result: Dict[str, Any] = {
            "group_id": group_id,
            "member_claim_ids": member_ids,
            "canonical_text": canonical_text,
            "status": status,
            "wscore": round(wscore, 6),
            "evidence_union": sorted(evidence_union),
            "contributing_reviewers": sorted(contributing),
        }

        # E4: consensus paradox — append flag (does not raise)
        if _check_consensus_paradox(group_set, phase2):
            result["flags"] = ["high_structural_risk"]

        adjudicated_claims.append(result)

    return {"adjudicated_claims": adjudicated_claims}
