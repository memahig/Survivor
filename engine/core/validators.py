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

    # Require reviewers based on config (fail-closed)
    enabled = config.get("reviewers_enabled", [])
    _require(isinstance(enabled, list) and len(enabled) > 0, "config.reviewers_enabled must be a non-empty list")

    expected = []
    for x in enabled:
        _require(isinstance(x, str) and x.strip(), "config.reviewers_enabled entries must be non-empty strings")
        expected.append(x.strip())

    for name in expected:
        _require(name in phase2, f"phase2 missing reviewer output: {name}")
        validate_reviewer_pack(phase2[name], config)

    _validate_verification(run_state, config)


def _validate_verification(run_state: Dict[str, Any], config: Dict[str, Any]) -> None:
    from engine.verify.base import (  # local import: verify layer is optional
        CLAIM_KINDS,
        CONFIDENCE_VALUES,
        SOURCE_TYPES,
        VERIFICATION_STATUSES,
    )

    verification_enabled = bool(config.get("verification_enabled", False))
    pack = run_state.get("verification")

    if not verification_enabled:
        # Disabled: pack may be absent or a disabled stub — either is fine
        if pack is None:
            return
        _require(isinstance(pack, dict), "run_state.verification must be dict when present")
        enabled_flag = pack.get("enabled")
        if enabled_flag is not None:
            _require(
                enabled_flag is False,
                "run_state.verification.enabled must be False when verification_enabled=false",
            )
        return

    # verification_enabled=True: pack must be present and well-formed
    _require(pack is not None, "run_state.verification missing but verification_enabled=true")
    _require(isinstance(pack, dict), "run_state.verification must be dict")
    _require(
        pack.get("enabled") is True,
        "run_state.verification.enabled must be True when verification_enabled=true",
    )

    results = pack.get("results")
    _require(isinstance(results, list), "run_state.verification.results must be list")

    # Validate verification_kinds_enabled config
    kinds_enabled_raw = config.get("verification_kinds_enabled", list(CLAIM_KINDS))
    _require(isinstance(kinds_enabled_raw, list), "config.verification_kinds_enabled must be a list")
    kinds_enabled: set[str] = set()
    for k in kinds_enabled_raw:
        _require(
            k in CLAIM_KINDS,
            f"config.verification_kinds_enabled contains unknown kind: {k!r}",
        )
        kinds_enabled.add(k)

    seen_ids: set[str] = set()

    for i, r in enumerate(results):
        _require(isinstance(r, dict), f"verification result[{i}] must be dict")

        claim_id = r.get("claim_id")
        _require(
            isinstance(claim_id, str) and claim_id.strip(),
            f"verification result[{i}].claim_id must be a non-empty string",
        )
        _require(
            claim_id not in seen_ids,
            f"duplicate claim_id in verification results: {claim_id!r}",
        )
        seen_ids.add(claim_id)

        claim_text = r.get("claim_text")
        _require(
            isinstance(claim_text, str) and claim_text.strip(),
            f"verification result[{i}].claim_text must be non-empty",
        )

        claim_kind = r.get("claim_kind")
        _require(
            claim_kind in CLAIM_KINDS,
            f"verification result[{i}].claim_kind invalid: {claim_kind!r}",
        )

        status = r.get("verification_status")
        _require(
            status in VERIFICATION_STATUSES,
            f"verification result[{i}].verification_status invalid: {status!r}",
        )

        confidence = r.get("confidence")
        _require(
            confidence in CONFIDENCE_VALUES,
            f"verification result[{i}].confidence invalid: {confidence!r}",
        )

        method_note = r.get("method_note")
        _require(
            isinstance(method_note, str) and method_note.strip(),
            f"verification result[{i}].method_note must be non-empty",
        )

        checked_at = r.get("checked_at")
        _require(
            isinstance(checked_at, str) and checked_at.strip(),
            f"verification result[{i}].checked_at must be non-empty",
        )

        # Symmetric authority_sources rule:
        # [] is ONLY permitted when status == "not_checked_yet"
        authority_sources = r.get("authority_sources")
        _require(
            isinstance(authority_sources, list),
            f"verification result[{i}].authority_sources must be list",
        )

        if status != "not_checked_yet":
            _require(
                len(authority_sources) > 0,
                f"verification result[{i}].authority_sources must be non-empty when status={status!r}",
            )

        for j, src in enumerate(authority_sources):
            _require(
                isinstance(src, dict),
                f"verification result[{i}].authority_sources[{j}] must be dict",
            )
            src_type = src.get("source_type")
            _require(
                src_type in SOURCE_TYPES,
                f"verification result[{i}].authority_sources[{j}].source_type invalid: {src_type!r}",
            )
            has_locator = isinstance(src.get("locator"), str) and bool(src["locator"].strip())
            has_url = isinstance(src.get("url"), str) and bool(src["url"].strip())
            _require(
                has_locator or has_url,
                f"verification result[{i}].authority_sources[{j}] must have locator or url",
            )
