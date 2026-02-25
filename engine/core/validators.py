#!/usr/bin/env python3
"""
FILE: engine/core/validators.py
VERSION: 0.2.1
PURPOSE:
Fail-closed validators for Survivor run_state and reviewer packs.

CONTRACT:
- Raise RuntimeError on any violation.
- No warnings-only mode.
- Key sets are imported from engine.core.schema_constants — do not hardcode them here.

CHANGES IN v0.2:
- (A) Key sets sourced from schema_constants; no inline hardcoding.
- (B) "uncertain" classification requires uncertainty_basis + check_scope (no bypass).
- (C) Deep enum validation: ArticleClassification, ClaimType, Vote, Confidence,
      Integrity Scale (if present).
- (D) EvidenceBank canonical schema enforced: quote, locator, source_id;
      text==quote, char_len==len(quote), locator length consistency;
      full reconstructibility if normalized_text present in run_state.
- (E) near_duplicate_of references validated against claim registry (no dangling refs).
- (fix) Symmetric authority rule: not_verifiable now also exempted alongside
        not_checked_yet (AUTHORITY_SOURCES_EXEMPT_STATUSES).

CHANGES IN v0.2.1:
- reviewer non-empty check (reviewer.strip()).
- Phantom EID guard: whitespace-only EIDs are ignored (strip before lookup);
  error list normalized to stripped EIDs.
- EvidenceBank bounds check: cs and ce <= len(normalized_text) before slicing.
- cross_claim_votes: claim_id must be non-empty str.
- _collect_eids: replaced recursive impl with iterative + 200k node cap.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from engine.core.schema_constants import (
    ARTICLE_CLASSIFICATIONS,
    AUTHORITY_SOURCES_EXEMPT_STATUSES,
    CLAIM_TYPES,
    CONFIDENCE_VALUES,
    INTEGRITY_SCALE,
    REVIEWER_PACK_REQUIRED_KEYS,
    UNCERTAIN_CLASSIFICATIONS,
    VOTE_VALUES,
)
from engine.core.schemas import ReviewerPack


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _is_list_of_str(x: Any) -> bool:
    return isinstance(x, list) and all(isinstance(i, str) for i in x)


# ---------------------------------------------------------------------------
# whole_article_judgment validation
# ---------------------------------------------------------------------------


def _validate_whole_article_judgment(pack: Dict[str, Any]) -> None:
    waj = pack.get("whole_article_judgment")
    _require(isinstance(waj, dict), "ReviewerPack missing whole_article_judgment dict")

    classification = waj.get("classification")
    confidence = waj.get("confidence")
    eids = waj.get("evidence_eids")

    _require(isinstance(classification, str), "whole_article_judgment.classification must be str")
    _require(
        classification in ARTICLE_CLASSIFICATIONS,
        f"whole_article_judgment.classification invalid: {classification!r}",
    )
    _require(
        confidence in CONFIDENCE_VALUES,
        f"whole_article_judgment.confidence invalid: {confidence!r}",
    )
    _require(_is_list_of_str(eids), "whole_article_judgment.evidence_eids must be list[str]")

    # (B) Uncertain classification: no bypass — require uncertainty_basis + check_scope.
    if classification in UNCERTAIN_CLASSIFICATIONS:
        uncertainty_basis = waj.get("uncertainty_basis")
        _require(
            isinstance(uncertainty_basis, str) and uncertainty_basis.strip(),
            "whole_article_judgment.uncertainty_basis must be non-empty str when classification is uncertain",
        )
        check_scope = waj.get("check_scope") or waj.get("search_scope")
        _require(
            isinstance(check_scope, str) and check_scope.strip(),
            "whole_article_judgment.check_scope (or search_scope) must be non-empty str when classification is uncertain",
        )
        return

    _require(
        len(eids) > 0,
        "whole_article_judgment.evidence_eids must be non-empty unless classification is uncertain",
    )

    # (C) Integrity Scale — validate if the field is present in waj.
    integrity_rating = waj.get("integrity_rating")
    if integrity_rating is not None:
        _require(
            integrity_rating in INTEGRITY_SCALE,
            f"whole_article_judgment.integrity_rating invalid: {integrity_rating!r}",
        )


# ---------------------------------------------------------------------------
# Claims validation
# ---------------------------------------------------------------------------


def _validate_claims(pack: Dict[str, Any]) -> None:
    claims = pack.get("claims", [])
    for i, claim in enumerate(claims):
        _require(isinstance(claim, dict), f"claims[{i}] must be dict")
        _require(
            isinstance(claim.get("claim_id"), str) and claim["claim_id"].strip(),
            f"claims[{i}].claim_id must be non-empty str",
        )
        _require(
            isinstance(claim.get("text"), str) and claim["text"].strip(),
            f"claims[{i}].text must be non-empty str",
        )
        _require(
            claim.get("type") in CLAIM_TYPES,
            f"claims[{i}].type invalid: {claim.get('type')!r}",
        )
        _require(
            _is_list_of_str(claim.get("evidence_eids")),
            f"claims[{i}].evidence_eids must be list[str]",
        )
        centrality = claim.get("centrality")
        _require(
            isinstance(centrality, int) and centrality in (1, 2, 3),
            f"claims[{i}].centrality must be 1, 2, or 3",
        )


# ---------------------------------------------------------------------------
# Cross-claim votes validation
# ---------------------------------------------------------------------------


def _validate_cross_claim_votes(pack: Dict[str, Any], config: Dict[str, Any]) -> None:
    cap = int(config["max_near_duplicate_links"])
    votes = pack.get("cross_claim_votes", [])
    _require(isinstance(votes, list), "ReviewerPack.cross_claim_votes must be list")

    for i, v in enumerate(votes):
        _require(isinstance(v, dict), f"cross_claim_votes[{i}] must be dict")

        # (v0.2.1) claim_id must be non-empty str
        cid = v.get("claim_id")
        _require(
            isinstance(cid, str) and cid.strip(),
            f"cross_claim_votes[{i}].claim_id must be non-empty str",
        )

        vote_val = v.get("vote")
        if vote_val is not None:
            _require(
                vote_val in VOTE_VALUES,
                f"cross_claim_votes[{i}].vote invalid: {vote_val!r}",
            )

        conf_val = v.get("confidence")
        if conf_val is not None:
            _require(
                conf_val in CONFIDENCE_VALUES,
                f"cross_claim_votes[{i}].confidence invalid: {conf_val!r}",
            )

        nd = v.get("near_duplicate_of")
        if nd is None:
            continue
        _require(_is_list_of_str(nd), f"cross_claim_votes[{i}].near_duplicate_of must be list[str]")
        _require(len(nd) <= cap, f"cross_claim_votes[{i}].near_duplicate_of exceeds cap {cap}")


# ---------------------------------------------------------------------------
# validate_reviewer_pack
# ---------------------------------------------------------------------------


def validate_reviewer_pack(pack: Dict[str, Any], config: Dict[str, Any]) -> None:
    _require(isinstance(pack, dict), "ReviewerPack must be dict")
    # (v0.2.1) reviewer must be a non-empty str
    reviewer = pack.get("reviewer")
    _require(isinstance(reviewer, str) and reviewer.strip(), "ReviewerPack.reviewer missing/invalid")

    # (A) Key sets from schema_constants — no hardcoding here.
    for k in REVIEWER_PACK_REQUIRED_KEYS:
        _require(k in pack, f"ReviewerPack missing required key: {k}")

    _validate_whole_article_judgment(pack)
    _validate_claims(pack)

    claims = pack.get("claims")
    _require(isinstance(claims, list), "ReviewerPack.claims must be list")
    _require(
        len(claims) <= int(config["max_claims_per_reviewer"]),
        "claims exceed max_claims_per_reviewer",
    )

    _validate_cross_claim_votes(pack, config)


# ---------------------------------------------------------------------------
# EID collection (iterative, cap-guarded — v0.2.1)
# ---------------------------------------------------------------------------


def _collect_eids(obj: Any, out: List[str], *, max_nodes: int = 200_000) -> None:
    stack = [obj]
    seen = 0
    while stack:
        seen += 1
        if seen > max_nodes:
            raise RuntimeError(
                f"EID collection exceeded max_nodes={max_nodes} (possible nested/hostile structure)"
            )
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k == "evidence_eids" and isinstance(v, list):
                    for eid in v:
                        if isinstance(eid, str):
                            out.append(eid)
                else:
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)


# ---------------------------------------------------------------------------
# (D) EvidenceBank canonical schema validation
# ---------------------------------------------------------------------------


def _validate_evidence_bank_items(
    items: List[Any],
    normalized_text: str | None,
) -> None:
    seen_eids: Set[str] = set()
    seen_quotes: Set[str] = set()

    for i, item in enumerate(items):
        _require(isinstance(item, dict), f"evidence_bank.items[{i}] must be dict")

        eid = item.get("eid")
        _require(
            isinstance(eid, str) and eid.strip(),
            f"evidence_bank.items[{i}].eid must be non-empty str",
        )
        _require(eid not in seen_eids, f"evidence_bank: duplicate eid: {eid!r}")
        seen_eids.add(eid)

        quote = item.get("quote")
        _require(
            isinstance(quote, str) and quote.strip(),
            f"evidence_bank.items[{i}] ({eid}): quote must be non-empty str",
        )
        _require(quote not in seen_quotes, f"evidence_bank: duplicate quote at {eid!r}")
        seen_quotes.add(quote)

        locator = item.get("locator")
        _require(
            isinstance(locator, dict),
            f"evidence_bank.items[{i}] ({eid}): locator must be dict",
        )
        cs = locator.get("char_start")
        ce = locator.get("char_end")
        _require(isinstance(cs, int), f"evidence_bank.items[{i}] ({eid}): locator.char_start must be int")
        _require(isinstance(ce, int), f"evidence_bank.items[{i}] ({eid}): locator.char_end must be int")
        _require(cs >= 0, f"evidence_bank.items[{i}] ({eid}): locator.char_start must be >= 0")
        _require(cs < ce, f"evidence_bank.items[{i}] ({eid}): locator.char_start must be < char_end")

        source_id = item.get("source_id")
        _require(
            isinstance(source_id, str) and source_id.strip(),
            f"evidence_bank.items[{i}] ({eid}): source_id must be non-empty str",
        )

        # Transitional alias enforcement
        text_alias = item.get("text")
        if text_alias is not None:
            _require(
                text_alias == quote,
                f"evidence_bank.items[{i}] ({eid}): text alias must equal quote",
            )

        char_len = item.get("char_len")
        if char_len is not None:
            _require(
                isinstance(char_len, int) and char_len == len(quote),
                f"evidence_bank.items[{i}] ({eid}): char_len must equal len(quote)",
            )

        # Locator length consistency (reconstructibility without source text)
        _require(
            ce - cs == len(quote),
            f"evidence_bank.items[{i}] ({eid}): locator span [{cs}:{ce}] length {ce - cs} "
            f"!= len(quote) {len(quote)}",
        )

        # Full reconstructibility when normalized_text is available
        if normalized_text is not None:
            # (v0.2.1) bounds checks before slicing
            _require(
                cs <= len(normalized_text),
                f"evidence_bank.items[{i}] ({eid}): locator.char_start out of bounds: "
                f"{cs} > len(normalized_text) {len(normalized_text)}",
            )
            _require(
                ce <= len(normalized_text),
                f"evidence_bank.items[{i}] ({eid}): locator.char_end out of bounds: "
                f"{ce} > len(normalized_text) {len(normalized_text)}",
            )
            sliced = normalized_text[cs:ce]
            _require(
                sliced == quote,
                f"evidence_bank.items[{i}] ({eid}): locator mismatch — "
                f"normalized_text[{cs}:{ce}]={sliced!r} != quote={quote!r}",
            )


# ---------------------------------------------------------------------------
# (E) Near-duplicate link-rot validation
# ---------------------------------------------------------------------------


def _validate_near_duplicate_refs(
    phase2: Dict[str, Any],
    claim_registry: Set[str],
) -> None:
    """
    For every near_duplicate_of reference across all reviewer packs,
    ensure the referenced claim_id exists in the claim_registry.
    Raises RuntimeError on any dangling reference.
    """
    for reviewer, pack in phase2.items():
        if not isinstance(pack, dict):
            continue
        votes = pack.get("cross_claim_votes", [])
        if not isinstance(votes, list):
            continue
        for i, v in enumerate(votes):
            if not isinstance(v, dict):
                continue
            nd = v.get("near_duplicate_of")
            if not nd:
                continue
            for ref in nd:
                _require(
                    ref in claim_registry,
                    f"near_duplicate_of dangling reference in {reviewer}.cross_claim_votes[{i}]: "
                    f"{ref!r} not found in claim registry",
                )


# ---------------------------------------------------------------------------
# validate_run
# ---------------------------------------------------------------------------


def validate_run(run_state: Dict[str, Any], config: Dict[str, Any]) -> None:
    _require("phase2" in run_state, "run_state missing phase2")
    phase2 = run_state["phase2"]
    _require(isinstance(phase2, dict), "run_state.phase2 must be dict")

    # ------------------------------------------------------------------
    # EID integrity: no phantom EIDs
    # ------------------------------------------------------------------
    ev = run_state.get("evidence_bank", {})
    items = ev.get("items", [])
    _require(isinstance(items, list), "run_state.evidence_bank.items must be list")

    valid_eids = {it.get("eid") for it in items if isinstance(it, dict) and it.get("eid")}
    _require(len(valid_eids) > 0, "EvidenceBank has no valid eids")

    referenced: List[str] = []
    _collect_eids(run_state.get("phase2", {}), referenced)
    _collect_eids(run_state.get("adjudicated", {}), referenced)

    # (v0.2.1) normalize to stripped EIDs; skip whitespace-only entries
    bad = sorted({
        eid.strip() for eid in referenced
        if isinstance(eid, str) and eid.strip() and eid.strip() not in valid_eids
    })
    if bad:
        raise RuntimeError(f"EID integrity failure: referenced but not in EvidenceBank: {bad}")

    # ------------------------------------------------------------------
    # (D) EvidenceBank canonical schema validation
    # ------------------------------------------------------------------
    normalized_text: str | None = run_state.get("normalized_text")
    _validate_evidence_bank_items(items, normalized_text)

    # ------------------------------------------------------------------
    # Reviewer presence + pack validation
    # ------------------------------------------------------------------
    enabled = config.get("reviewers_enabled", [])
    _require(
        isinstance(enabled, list) and len(enabled) > 0,
        "config.reviewers_enabled must be a non-empty list",
    )

    expected = []
    for x in enabled:
        _require(isinstance(x, str) and x.strip(), "config.reviewers_enabled entries must be non-empty strings")
        expected.append(x.strip())

    for name in expected:
        _require(name in phase2, f"phase2 missing reviewer output: {name}")
        validate_reviewer_pack(phase2[name], config)

    # ------------------------------------------------------------------
    # (E) Near-duplicate link-rot: build claim registry then validate refs
    # ------------------------------------------------------------------
    claim_registry: Set[str] = set()
    for name in expected:
        pack = phase2[name]
        for claim in pack.get("claims", []):
            cid = claim.get("claim_id")
            if isinstance(cid, str) and cid.strip():
                claim_registry.add(cid)

    _validate_near_duplicate_refs(phase2, claim_registry)

    # ------------------------------------------------------------------
    # Verification layer
    # ------------------------------------------------------------------
    _validate_verification(run_state, config)


# ---------------------------------------------------------------------------
# Verification layer validation
# ---------------------------------------------------------------------------


def _validate_verification(run_state: Dict[str, Any], config: Dict[str, Any]) -> None:
    from engine.verify.base import (  # local import: verify layer is optional
        CLAIM_KINDS,
        CONFIDENCE_VALUES as VERIFY_CONFIDENCE_VALUES,
        SOURCE_TYPES,
        VERIFICATION_STATUSES,
    )

    verification_enabled = bool(config.get("verification_enabled", False))
    pack = run_state.get("verification")

    if not verification_enabled:
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
            confidence in VERIFY_CONFIDENCE_VALUES,
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

        # (fix) Symmetric authority rule: exempt not_checked_yet AND not_verifiable.
        authority_sources = r.get("authority_sources")
        _require(
            isinstance(authority_sources, list),
            f"verification result[{i}].authority_sources must be list",
        )

        if status not in AUTHORITY_SOURCES_EXEMPT_STATUSES:
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
