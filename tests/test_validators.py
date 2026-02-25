#!/usr/bin/env python3
"""
FILE: tests/test_validators.py
PURPOSE:
Fail-closed contract tests for engine/core/validators.py (v0.2).

Tests cover:
  (A) Key sets from schema_constants (no inline hardcoding regressions)
  (B) Uncertain classification: requires uncertainty_basis + check_scope
  (C) Deep enum validation: ArticleClassification, ClaimType, Vote, Confidence,
      Integrity Scale
  (D) EvidenceBank canonical schema: quote, locator, source_id, transitional
      aliases, locator span consistency, full reconstructibility
  (E) near_duplicate_of link-rot: dangling references raise RuntimeError
  (fix) Symmetric authority rule: not_verifiable now also exempt

Run with: python -m pytest tests/ -v
"""

import pytest

from engine.core.validators import (
    _validate_evidence_bank_items,
    validate_reviewer_pack,
    validate_run,
)
from engine.core.schema_constants import (
    REVIEWER_PACK_REQUIRED_KEYS,
    ARTICLE_CLASSIFICATIONS,
    CLAIM_TYPES,
    VOTE_VALUES,
    INTEGRITY_SCALE,
    AUTHORITY_SOURCES_EXEMPT_STATUSES,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_CFG = {
    "max_claims_per_reviewer": 20,
    "max_near_duplicate_links": 3,
    "reviewers_enabled": ["openai", "gemini"],
    "confidence_weights": {"low": 0.5, "medium": 1.0, "high": 1.5},
    "model_weights": {"openai": 1.0, "gemini": 1.0},
    "decision_margin": 0.2,
}

_EVIDENCE_ITEM = {
    "eid": "E1",
    "quote": "Verbatim sentence from the article.",
    "locator": {"char_start": 0, "char_end": 35},
    "source_id": "A1",
    "text": "Verbatim sentence from the article.",
    "char_len": 35,
}

assert len("Verbatim sentence from the article.") == 35  # sanity


def _make_waj(classification="analysis", confidence="high", eids=None):
    return {
        "classification": classification,
        "confidence": confidence,
        "evidence_eids": eids if eids is not None else ["E1"],
    }


def _make_claim(claim_id="openai-CL-01", text="A factual claim.", ctype="factual", eids=None, centrality=1):
    return {
        "claim_id": claim_id,
        "text": text,
        "type": ctype,
        "evidence_eids": eids if eids is not None else ["E1"],
        "centrality": centrality,
    }


def _make_pack(reviewer="openai", waj=None, claims=None, votes=None):
    return {
        "reviewer": reviewer,
        "whole_article_judgment": waj or _make_waj(),
        "main_conclusion": {"text": "The article argues X."},
        "claims": claims if claims is not None else [_make_claim()],
        "scope_markers": [],
        "causal_links": [],
        "article_patterns": [],
        "omission_candidates": [],
        "counterfactual_requirements": [],
        "evidence_density": {"claims_count": 1, "claims_with_internal_support": 1, "external_sources_count": 0},
        "claim_tickets": [],
        "article_tickets": [],
        "cross_claim_votes": votes if votes is not None else [],
    }


def _make_run_state(packs=None, evidence_items=None, normalized_text=None):
    items = evidence_items if evidence_items is not None else [_EVIDENCE_ITEM.copy()]
    state: dict = {
        "evidence_bank": {"items": items},
        "phase2": packs or {
            "openai": _make_pack("openai"),
            "gemini": _make_pack("gemini", claims=[_make_claim("gemini-CL-01")]),
        },
    }
    if normalized_text is not None:
        state["normalized_text"] = normalized_text
    return state


# ---------------------------------------------------------------------------
# (A) Schema constants — regression guard
# ---------------------------------------------------------------------------


def test_reviewer_pack_required_keys_is_frozenset():
    assert isinstance(REVIEWER_PACK_REQUIRED_KEYS, frozenset)


def test_all_required_keys_validated():
    """Removing any required key from a pack must raise RuntimeError."""
    for key in REVIEWER_PACK_REQUIRED_KEYS:
        pack = _make_pack()
        del pack[key]
        with pytest.raises(RuntimeError, match=key):
            validate_reviewer_pack(pack, _CFG)


def test_article_classifications_covers_uncertain():
    assert "uncertain" in ARTICLE_CLASSIFICATIONS


def test_authority_sources_exempt_includes_not_verifiable():
    assert "not_verifiable" in AUTHORITY_SOURCES_EXEMPT_STATUSES


def test_authority_sources_exempt_includes_not_checked_yet():
    assert "not_checked_yet" in AUTHORITY_SOURCES_EXEMPT_STATUSES


# ---------------------------------------------------------------------------
# (B) Uncertain classification loophole closed
# ---------------------------------------------------------------------------


def test_uncertain_classification_requires_uncertainty_basis():
    waj = _make_waj(classification="uncertain", eids=[])
    pack = _make_pack(waj=waj)
    with pytest.raises(RuntimeError, match="uncertainty_basis"):
        validate_reviewer_pack(pack, _CFG)


def test_uncertain_classification_requires_check_scope():
    waj = _make_waj(classification="uncertain", eids=[])
    waj["uncertainty_basis"] = "Insufficient signal in the article."
    pack = _make_pack(waj=waj)
    with pytest.raises(RuntimeError, match="check_scope"):
        validate_reviewer_pack(pack, _CFG)


def test_uncertain_classification_passes_with_both_fields():
    waj = _make_waj(classification="uncertain", eids=[])
    waj["uncertainty_basis"] = "Insufficient signal."
    waj["check_scope"] = "Reviewed paragraphs 1-3."
    pack = _make_pack(waj=waj)
    validate_reviewer_pack(pack, _CFG)  # must not raise


def test_uncertain_classification_passes_with_search_scope_alias():
    waj = _make_waj(classification="uncertain", eids=[])
    waj["uncertainty_basis"] = "Insufficient signal."
    waj["search_scope"] = "Reviewed paragraphs 1-3."
    pack = _make_pack(waj=waj)
    validate_reviewer_pack(pack, _CFG)  # must not raise


def test_non_uncertain_classification_still_requires_eids():
    waj = _make_waj(classification="analysis", eids=[])
    pack = _make_pack(waj=waj)
    with pytest.raises(RuntimeError, match="evidence_eids"):
        validate_reviewer_pack(pack, _CFG)


# ---------------------------------------------------------------------------
# (C) Deep enum validation
# ---------------------------------------------------------------------------


def test_invalid_article_classification_raises():
    waj = _make_waj(classification="bogus_classification")
    pack = _make_pack(waj=waj)
    with pytest.raises(RuntimeError, match="classification invalid"):
        validate_reviewer_pack(pack, _CFG)


def test_invalid_waj_confidence_raises():
    waj = _make_waj(confidence="ultra")
    pack = _make_pack(waj=waj)
    with pytest.raises(RuntimeError, match="confidence invalid"):
        validate_reviewer_pack(pack, _CFG)


def test_invalid_claim_type_raises():
    claim = _make_claim(ctype="speculative")
    pack = _make_pack(claims=[claim])
    with pytest.raises(RuntimeError, match="type invalid"):
        validate_reviewer_pack(pack, _CFG)


def test_all_valid_claim_types_accepted():
    for ctype in CLAIM_TYPES:
        claim = _make_claim(ctype=ctype)
        pack = _make_pack(claims=[claim])
        validate_reviewer_pack(pack, _CFG)  # must not raise


def test_invalid_vote_in_cross_claim_votes_raises():
    votes = [{"claim_id": "openai-CL-01", "vote": "maybe", "confidence": "high"}]
    pack = _make_pack(votes=votes)
    with pytest.raises(RuntimeError, match="vote invalid"):
        validate_reviewer_pack(pack, _CFG)


def test_invalid_confidence_in_cross_claim_votes_raises():
    votes = [{"claim_id": "openai-CL-01", "vote": "supported", "confidence": "extreme"}]
    pack = _make_pack(votes=votes)
    with pytest.raises(RuntimeError, match="confidence invalid"):
        validate_reviewer_pack(pack, _CFG)


def test_all_valid_votes_accepted():
    for vote in VOTE_VALUES:
        votes = [{"claim_id": "openai-CL-01", "vote": vote, "confidence": "high"}]
        pack = _make_pack(votes=votes)
        validate_reviewer_pack(pack, _CFG)  # must not raise


def test_integrity_rating_validated_when_present():
    waj = _make_waj()
    waj["integrity_rating"] = "EXTREME"
    pack = _make_pack(waj=waj)
    with pytest.raises(RuntimeError, match="integrity_rating invalid"):
        validate_reviewer_pack(pack, _CFG)


def test_valid_integrity_rating_accepted():
    for rating in INTEGRITY_SCALE:
        waj = _make_waj()
        waj["integrity_rating"] = rating
        pack = _make_pack(waj=waj)
        validate_reviewer_pack(pack, _CFG)  # must not raise


def test_missing_integrity_rating_accepted():
    pack = _make_pack()
    assert "integrity_rating" not in pack["whole_article_judgment"]
    validate_reviewer_pack(pack, _CFG)  # must not raise


# ---------------------------------------------------------------------------
# (D) EvidenceBank schema validation
# ---------------------------------------------------------------------------


def _good_item(**overrides):
    item = _EVIDENCE_ITEM.copy()
    item["locator"] = dict(item["locator"])
    item.update(overrides)
    return item


def test_valid_evidence_item_passes():
    _validate_evidence_bank_items([_good_item()], normalized_text=None)


def test_evidence_item_missing_quote_raises():
    item = _good_item()
    del item["quote"]
    with pytest.raises(RuntimeError, match="quote"):
        _validate_evidence_bank_items([item], normalized_text=None)


def test_evidence_item_empty_quote_raises():
    item = _good_item(quote="   ")
    with pytest.raises(RuntimeError, match="quote"):
        _validate_evidence_bank_items([item], normalized_text=None)


def test_evidence_item_missing_locator_raises():
    item = _good_item()
    del item["locator"]
    with pytest.raises(RuntimeError, match="locator"):
        _validate_evidence_bank_items([item], normalized_text=None)


def test_evidence_item_locator_missing_char_start_raises():
    item = _good_item()
    del item["locator"]["char_start"]
    with pytest.raises(RuntimeError, match="char_start"):
        _validate_evidence_bank_items([item], normalized_text=None)


def test_evidence_item_locator_missing_char_end_raises():
    item = _good_item()
    del item["locator"]["char_end"]
    with pytest.raises(RuntimeError, match="char_end"):
        _validate_evidence_bank_items([item], normalized_text=None)


def test_evidence_item_missing_source_id_raises():
    item = _good_item()
    del item["source_id"]
    with pytest.raises(RuntimeError, match="source_id"):
        _validate_evidence_bank_items([item], normalized_text=None)


def test_evidence_item_text_alias_mismatch_raises():
    item = _good_item(text="WRONG TEXT")
    with pytest.raises(RuntimeError, match="text alias"):
        _validate_evidence_bank_items([item], normalized_text=None)


def test_evidence_item_char_len_mismatch_raises():
    item = _good_item(char_len=999)
    with pytest.raises(RuntimeError, match="char_len"):
        _validate_evidence_bank_items([item], normalized_text=None)


def test_evidence_item_locator_span_mismatch_raises():
    """char_end - char_start != len(quote) must raise."""
    item = _good_item()
    item["locator"]["char_end"] = item["locator"]["char_start"] + 5  # wrong span
    item["char_len"] = 5
    item["text"] = item["quote"][:5]
    item["quote"] = item["quote"][:5]
    # Recompute to get an item where the locator span doesn't match the real quote
    bad = _good_item()
    bad["locator"]["char_end"] = bad["locator"]["char_start"] + 5  # only 5, but quote is 35 chars
    with pytest.raises(RuntimeError, match="locator span"):
        _validate_evidence_bank_items([bad], normalized_text=None)


def test_evidence_item_duplicate_eid_raises():
    item1 = _good_item(eid="E1")
    item2 = _good_item(eid="E1")
    with pytest.raises(RuntimeError, match="duplicate eid"):
        _validate_evidence_bank_items([item1, item2], normalized_text=None)


def test_evidence_item_duplicate_quote_raises():
    text = "Verbatim sentence from the article."
    item1 = _good_item(eid="E1")
    item2 = _good_item(eid="E2")  # different eid, same quote
    with pytest.raises(RuntimeError, match="duplicate quote"):
        _validate_evidence_bank_items([item1, item2], normalized_text=None)


def test_evidence_item_full_reconstructibility_pass():
    source = "Verbatim sentence from the article."
    item = _good_item()
    _validate_evidence_bank_items([item], normalized_text=source)  # must not raise


def test_evidence_item_full_reconstructibility_fail():
    source = "COMPLETELY DIFFERENT TEXT HERE AND EVERYWHERE."
    item = _good_item()
    with pytest.raises(RuntimeError, match="locator mismatch"):
        _validate_evidence_bank_items([item], normalized_text=source)


# ---------------------------------------------------------------------------
# (E) Near-duplicate link-rot
# ---------------------------------------------------------------------------


def test_near_duplicate_ref_valid_passes():
    votes = [{"claim_id": "openai-CL-01", "near_duplicate_of": ["gemini-CL-01"]}]
    run = _make_run_state(
        packs={
            "openai": _make_pack("openai", votes=votes),
            "gemini": _make_pack("gemini", claims=[_make_claim("gemini-CL-01")]),
        }
    )
    validate_run(run, _CFG)  # must not raise


def test_near_duplicate_ref_dangling_raises():
    votes = [{"claim_id": "openai-CL-01", "near_duplicate_of": ["GHOST-CL-99"]}]
    run = _make_run_state(
        packs={
            "openai": _make_pack("openai", votes=votes),
            "gemini": _make_pack("gemini", claims=[_make_claim("gemini-CL-01")]),
        }
    )
    with pytest.raises(RuntimeError, match="dangling reference"):
        validate_run(run, _CFG)


# ---------------------------------------------------------------------------
# (fix) Symmetric authority rule: not_verifiable exempt
# ---------------------------------------------------------------------------


def _make_verification_result(status, authority_sources=None):
    base = {
        "claim_id": "G001",
        "claim_text": "Some claim text.",
        "claim_kind": "factual",         # CLAIM_KINDS from engine.verify.base
        "verification_status": status,
        "confidence": "LOW",             # CONFIDENCE_VALUES from engine.verify.base (uppercase)
        "authority_sources": authority_sources if authority_sources is not None else [],
        "method_note": "Manual check.",
        "checked_at": "2026-01-01T00:00:00Z",
    }
    return base


def _make_verify_run(status, authority_sources=None):
    run = _make_run_state()
    run["verification"] = {
        "enabled": True,
        "results": [_make_verification_result(status, authority_sources)],
    }
    cfg = dict(_CFG)
    cfg["verification_enabled"] = True
    return run, cfg


def test_not_checked_yet_allows_empty_authority_sources():
    run, cfg = _make_verify_run("not_checked_yet", authority_sources=[])
    validate_run(run, cfg)  # must not raise


def test_not_verifiable_allows_empty_authority_sources():
    run, cfg = _make_verify_run("not_verifiable", authority_sources=[])
    validate_run(run, cfg)  # must not raise


def test_verified_true_requires_nonempty_authority_sources():
    run, cfg = _make_verify_run("verified_true", authority_sources=[])
    with pytest.raises(RuntimeError, match="authority_sources must be non-empty"):
        validate_run(run, cfg)


def test_verified_false_requires_nonempty_authority_sources():
    run, cfg = _make_verify_run("verified_false", authority_sources=[])
    with pytest.raises(RuntimeError, match="authority_sources must be non-empty"):
        validate_run(run, cfg)


def test_conflicted_sources_requires_nonempty_authority_sources():
    run, cfg = _make_verify_run("conflicted_sources", authority_sources=[])
    with pytest.raises(RuntimeError, match="authority_sources must be non-empty"):
        validate_run(run, cfg)


# ---------------------------------------------------------------------------
# validate_run: phantom EID guard preserved
# ---------------------------------------------------------------------------


def test_phantom_eid_raises():
    """EID referenced in phase2 but absent from EvidenceBank must raise."""
    claims = [_make_claim(eids=["E99"])]  # E99 does not exist
    run = _make_run_state(
        packs={
            "openai": _make_pack("openai", claims=claims),
            "gemini": _make_pack("gemini", claims=[_make_claim("gemini-CL-01", eids=["E1"])]),
        }
    )
    with pytest.raises(RuntimeError, match="EID integrity failure"):
        validate_run(run, _CFG)


def test_valid_run_passes():
    run = _make_run_state()
    validate_run(run, _CFG)  # must not raise
