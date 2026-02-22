#!/usr/bin/env python3
"""
FILE: engine/core/validators.py
VERSION: 0.1
PURPOSE:
Fail-closed validators for Survivor run_state.

CONTRACT:
- Raise RuntimeError on any violation.
- No warnings-only mode.
"""

from __future__ import annotations

from typing import Any, Dict, List

from engine.core.schemas import ReviewerPack


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _is_list_of_str(x: Any) -> bool:
    return isinstance(x, list) and all(isinstance(i, str) for i in x)


def _validate_whole_article_judgment(pack: Dict[str, Any]) -> None:
    waj = pack.get("whole_article_judgment")
    _require(isinstance(waj, dict), "ReviewerPack missing whole_article_judgment dict")

    classification = waj.get("classification")
    confidence = waj.get("confidence")
    eids = waj.get("evidence_eids")

    _require(isinstance(classification, str), "whole_article_judgment.classification must be str")
    _require(confidence in ("low", "medium", "high"), "whole_article_judgment.confidence invalid")
    _require(_is_list_of_str(eids), "whole_article_judgment.evidence_eids must be list[str]")

    if classification == "uncertain":
        # allow empty evidence_eids
        return

    _require(len(eids) > 0, "whole_article_judgment.evidence_eids must be non-empty unless classification == 'uncertain'")


def _validate_claim_caps(pack: Dict[str, Any], config: Dict[str, Any]) -> None:
    claims = pack.get("claims")
    _require(isinstance(claims, list), "ReviewerPack.claims must be list")
    _require(len(claims) <= int(config["max_claims_per_reviewer"]), "claims exceed max_claims_per_reviewer")


def _validate_near_duplicate_cap(pack: Dict[str, Any], config: Dict[str, Any]) -> None:
    cap = int(config["max_near_duplicate_links"])
    votes = pack.get("cross_claim_votes", [])
    _require(isinstance(votes, list), "ReviewerPack.cross_claim_votes must be list")

    for v in votes:
        if not isinstance(v, dict):
            raise RuntimeError("cross_claim_votes entries must be dicts")
        nd = v.get("near_duplicate_of")
        if nd is None:
            continue
        _require(_is_list_of_str(nd), "near_duplicate_of must be list[str]")
        _require(len(nd) <= cap, f"near_duplicate_of exceeds cap {cap}")


def validate_reviewer_pack(pack: Dict[str, Any], config: Dict[str, Any]) -> None:
    _require(isinstance(pack, dict), "ReviewerPack must be dict")
    _require(isinstance(pack.get("reviewer"), str), "ReviewerPack.reviewer missing/invalid")

    _validate_whole_article_judgment(pack)
    _validate_claim_caps(pack, config)
    _validate_near_duplicate_cap(pack, config)

    # minimal required structure fields exist
    for k in [
        "main_conclusion",
        "claims",
        "scope_markers",
        "causal_links",
        "article_patterns",
        "omission_candidates",
        "counterfactual_requirements",
        "evidence_density",
        "claim_tickets",
        "article_tickets",
        "cross_claim_votes",
    ]:
        _require(k in pack, f"ReviewerPack missing required key: {k}")
        

def _collect_eids(obj: Any, out: List[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "evidence_eids" and isinstance(v, list):
                for eid in v:
                    if isinstance(eid, str):
                        out.append(eid)
            else:
                _collect_eids(v, out)
    elif isinstance(obj, list):
        for x in obj:
            _collect_eids(x, out)

def validate_run(run_state: Dict[str, Any], config: Dict[str, Any]) -> None:
    _require("phase2" in run_state, "run_state missing phase2")
    phase2 = run_state["phase2"]
    _require(isinstance(phase2, dict), "run_state.phase2 must be dict")

    # ------------------------------
    # EID integrity: no phantom EIDs
    # ------------------------------
    ev = run_state.get("evidence_bank", {})
    items = ev.get("items", [])
    _require(isinstance(items, list), "run_state.evidence_bank.items must be list")

    valid_eids = {it.get("eid") for it in items if isinstance(it, dict) and it.get("eid")}
    _require(len(valid_eids) > 0, "EvidenceBank has no valid eids")

    referenced: List[str] = []

    _collect_eids(run_state.get("phase2", {}), referenced)
    _collect_eids(run_state.get("adjudicated", {}), referenced)

    bad = sorted({eid for eid in referenced if eid and eid not in valid_eids})
    if bad:
        raise RuntimeError(f"EID integrity failure: referenced but not in EvidenceBank: {bad}")

    # Require all three reviewers in v0
    for name in ("openai", "gemini", "claude"):
        _require(name in phase2, f"phase2 missing reviewer output: {name}")
        validate_reviewer_pack(phase2[name], config)

