#!/usr/bin/env python3
"""
FILE: engine/core/adjudicator.py
VERSION: 0.3
PURPOSE:
Orchestrates adjudication across two parallel tracks.

v0.3 CHANGE:
- Adds Claim Arena adjudication:
  - Build arena from claims_by_model
  - Group near-duplicates using reviewer-provided links (Phase2 cross_claim_votes.near_duplicate_of)
  - Tally votes per claim-group with margin rule (supported vs unsupported)
  - Produce adjudicated claims list (auditable)

NOTE:
- Reviewers are mocks right now; near_duplicate_of will be empty.
- This code still works (groups will be singletons).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from engine.core.triage_utils import list_triage_claims
from engine.core.validators import validate_reviewer_pack
from engine.core.voting import build_equivalence_groups, group_members, tally_reviewer_votes, decide_status
from engine.core.claim_classifier import (
    classify_claim_kind,
    compute_checkability,
    extract_source_doc_hint,
)
from engine.core.forensics_merge import merge_structural_forensics


def _conf_weight(conf: str, config: Dict[str, Any]) -> float:
    weights = config["confidence_weights"]
    if conf not in weights:
        raise RuntimeError(f"Unknown confidence: {conf}")
    return float(weights[conf])


def _model_weight(model: str, config: Dict[str, Any]) -> float:
    mw = config["model_weights"]
    if model not in mw:
        raise RuntimeError(f"Unknown model in model_weights: {model}")
    return float(mw[model])


def _adjudicate_article_classification(
    waj_by_model: Dict[str, Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    margin = float(config["decision_margin"])

    tally: Dict[str, float] = {}
    by_class_models: Dict[str, List[str]] = {}

    for model, waj in waj_by_model.items():
        cls = waj["classification"]
        conf = waj["confidence"]
        w = _conf_weight(conf, config) * _model_weight(model, config)
        tally[cls] = tally.get(cls, 0.0) + w
        by_class_models.setdefault(cls, []).append(model)

    ranked: List[Tuple[str, float]] = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))
    winner_cls, winner_score = ranked[0]
    runner_score = ranked[1][1] if len(ranked) > 1 else 0.0

    if winner_score < runner_score + margin:
        adjudicated_cls = "uncertain"
        adjudicated_conf = "low"
    else:
        adjudicated_cls = winner_cls
        gap = winner_score - runner_score
        adjudicated_conf = "high" if gap >= margin * 2 else "medium"

    if adjudicated_cls == "uncertain":
        evidence_eids: List[str] = []
    else:
        eids_set = set()
        for m in by_class_models.get(adjudicated_cls, []):
            for eid in waj_by_model[m].get("evidence_eids", []):
                eids_set.add(eid)
        evidence_eids = sorted(eids_set)

    disagreements = []
    for cls, models in sorted(by_class_models.items(), key=lambda kv: kv[0]):
        disagreements.append(
            {"classification": cls, "models": sorted(models), "score": tally.get(cls, 0.0)}
        )

    return {
        "classification": adjudicated_cls,
        "confidence": adjudicated_conf,
        "evidence_eids": evidence_eids,
        "tally": ranked,
        "disagreements": disagreements,
    }


def _index_claims_by_id(claims_by_model: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for model, claims in claims_by_model.items():
        for c in claims:
            cid = c.get("claim_id")
            if not cid:
                raise RuntimeError("Claim missing claim_id")
            if cid in idx:
                raise RuntimeError(f"Duplicate claim_id across models (must be unique): {cid}")
            idx[cid] = c
    return idx


def _collect_near_duplicate_edges(
    cross_votes_by_model: Dict[str, List[Dict[str, Any]]]
) -> List[Tuple[str, str]]:
    """
    Build UNDIRECTED, DEDUPLICATED (a,b) edges from near_duplicate_of lists.

    Reviewers may emit symmetric links (A lists B and B lists A) and multiple
    reviewers may emit the same link. We canonicalize each edge as (min, max)
    and deduplicate.
    """
    edges_set = set()

    for _model, votes in cross_votes_by_model.items():
        for v in votes:
            cid = v.get("claim_id")
            nd = v.get("near_duplicate_of")
            if not cid or not nd:
                continue
            for other in nd:
                if not other or other == cid:
                    continue
                a, b = (cid, other) if cid < other else (other, cid)
                edges_set.add((a, b))

    return sorted(edges_set)


def _build_reviewer_votes_for_claim_group(
    group_claim_ids: List[str],
    phase2_outputs: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, str]]:
    """
    For a claim-group, each reviewer gives ONE vote.
    Rule:
    - If reviewer has cross_claim_votes entries for any claim_id in group, use the first match.
    - Else: undetermined/low.
    """
    out: Dict[str, Dict[str, str]] = {}

    for reviewer, pack in phase2_outputs.items():
        votes = pack.get("cross_claim_votes", [])
        chosen = None
        for v in votes:
            if v.get("claim_id") in group_claim_ids:
                chosen = v
                break

        if chosen is None:
            out[reviewer] = {"vote": "undetermined", "confidence": "low"}
        else:
            out[reviewer] = {
                "vote": chosen.get("vote", "undetermined"),
                "confidence": chosen.get("confidence", "low"),
            }
    return out


def _adjudicate_claim_groups(
    claims_by_model: Dict[str, List[Dict[str, Any]]],
    cross_votes_by_model: Dict[str, List[Dict[str, Any]]],
    phase2_outputs: Dict[str, Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    claim_index = _index_claims_by_id(claims_by_model)

    edges = _collect_near_duplicate_edges(cross_votes_by_model)
    if edges:
        parent = build_equivalence_groups(edges)
        # Ensure every claim_id has a parent entry — unlinked claims become singletons
        for cid in claim_index:
            if cid not in parent:
                parent[cid] = cid
        groups = group_members(parent)
    else:
        groups = {cid: [cid] for cid in sorted(claim_index.keys())}

    adjudicated_claims: List[Dict[str, Any]] = []

    for rep, members in sorted(groups.items(), key=lambda kv: kv[0]):
        reviewer_votes = _build_reviewer_votes_for_claim_group(members, phase2_outputs)
        tally = tally_reviewer_votes(reviewer_votes, config)
        status = decide_status(tally, config)

        # Representative claim text: take the rep claim if present, else first member
        rep_id = rep if rep in claim_index else members[0]
        rep_claim = claim_index[rep_id]

        # Evidence: union of member evidence_eids (internal text citations)
        eids_set = set()
        for cid in members:
            for eid in claim_index[cid].get("evidence_eids", []):
                eids_set.add(eid)

        _claim_text = rep_claim.get("text") or ""
        _kind = classify_claim_kind(_claim_text)
        _checkability = compute_checkability(_claim_text, _kind)

        group: Dict[str, Any] = {
            "group_id": f"G{len(adjudicated_claims)+1:03d}",   # canonical representative
            "member_claim_ids": members,     # all merged ids
            "representative_claim_id": rep_id,
            "text": rep_claim.get("text"),
            "type": rep_claim.get("type"),
            "centrality": rep_claim.get("centrality"),
            "claim_kind": _kind,
            "checkability": _checkability,
            "evidence_eids": sorted(eids_set),
            "reviewer_votes": reviewer_votes,
            "tally": {
                "supported_score": tally.supported_score,
                "unsupported_score": tally.unsupported_score,
                "supported_votes": tally.supported_votes,
                "unsupported_votes": tally.unsupported_votes,
                "undetermined_votes": tally.undetermined_votes,
            },
            "adjudication": status,          # kept|rejected|downgraded
        }

        _hint = extract_source_doc_hint(_claim_text) if _kind == "document_content" else None
        if _hint is not None:
            group["source_doc_hint"] = _hint

        adjudicated_claims.append(group)

    return {
        "edges": edges,
        "groups_count": len(adjudicated_claims),
        "adjudicated_claims": adjudicated_claims,
    }


def adjudicate(phase2_outputs: Dict[str, Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    for _model, pack in phase2_outputs.items():
        try:
            validate_reviewer_pack(pack, config)
        except Exception as e:
            keys = list(pack.keys()) if isinstance(pack, dict) else f"(not a dict: {type(pack)})"
            raise RuntimeError(f"Reviewer '{_model}' produced invalid pack. keys={keys}. error={e}") from e

        # Article track
        waj_by_model = {m: phase2_outputs[m]["whole_article_judgment"] for m in phase2_outputs.keys()}
        adjudicated_waj = _adjudicate_article_classification(waj_by_model, config)

    article_track = {
        "whole_article_judgments": waj_by_model,
        "adjudicated_whole_article_judgment": adjudicated_waj,
        "article_tickets_by_model": {m: phase2_outputs[m]["article_tickets"] for m in phase2_outputs.keys()},
        "article_patterns_by_model": {m: phase2_outputs[m]["article_patterns"] for m in phase2_outputs.keys()},
        "counterfactual_requirements_by_model": {m: phase2_outputs[m]["counterfactual_requirements"] for m in phase2_outputs.keys()},
    }

    # Claim track (NOW: adjudicated)
    claims_by_model = {m: list_triage_claims(phase2_outputs[m]) for m in phase2_outputs.keys()}
    cross_votes_by_model = {m: phase2_outputs[m]["cross_claim_votes"] for m in phase2_outputs.keys()}

    claim_track = {
        "claims_by_model": claims_by_model,
        "cross_claim_votes_by_model": cross_votes_by_model,
        "claim_tickets_by_model": {m: phase2_outputs[m]["claim_tickets"] for m in phase2_outputs.keys()},
        "arena": _adjudicate_claim_groups(claims_by_model, cross_votes_by_model, phase2_outputs, config),
    }

    consistency_checks = {"notes": ["v0.3 placeholder: consistency checks not yet implemented"]}

    # Final tickets (v0.4):
    # - One ticket per adjudicated claim-group
    # - Plus all article_tickets as-is (for now)
    final_tickets: List[Dict[str, Any]] = []

    arena = claim_track.get("arena", {})
    adjudicated_claims = arena.get("adjudicated_claims", [])

    for g in adjudicated_claims:
        final_tickets.append(
            {
                "ticket_id": f"T-CLAIM-{g.get('group_id')}",
                "ticket_type": "claim_group",
                "adjudication": g.get("adjudication"),  # kept|rejected|downgraded
                "group_id": g.get("group_id"),
                "member_claim_ids": g.get("member_claim_ids"),
                "representative_claim_id": g.get("representative_claim_id"),
                "claim_text": g.get("text"),
                "claim_type": g.get("type"),
                "centrality": g.get("centrality"),
                "evidence_eids": g.get("evidence_eids"),
                "reviewer_votes": g.get("reviewer_votes"),
                "tally": g.get("tally"),
            }
        )

    # Carry forward article tickets from each reviewer pack (dedupe later)
    for m in phase2_outputs.keys():
        final_tickets.extend(phase2_outputs[m].get("article_tickets", []))

    # Structural forensics merge (v0.5 — optional fields)
    structural_forensics = merge_structural_forensics(phase2_outputs)

    return {
        "article_track": article_track,
        "claim_track": claim_track,
        "structural_forensics": structural_forensics,
        "consistency_checks": consistency_checks,
        "final_tickets": final_tickets,
    }