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
    "max_pillar_claims_per_reviewer": 15,
    "max_questionable_claims_per_reviewer": 30,
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


def _make_pack(
    reviewer="openai",
    waj=None,
    claims=None,
    votes=None,
    *,
    pillar_claims=None,
    questionable_claims=None,
    background_claims_summary=None,
):
    default_claims = [_make_claim()]
    pack = {
        "reviewer": reviewer,
        "whole_article_judgment": waj or _make_waj(),
        "main_conclusion": {"text": "The article argues X."},
        "pillar_claims": pillar_claims if pillar_claims is not None else default_claims,
        "questionable_claims": questionable_claims if questionable_claims is not None else [],
        "background_claims_summary": background_claims_summary or {
            "total_claims_estimate": 1,
            "not_triaged_count": 0,
        },
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
    # Legacy compat: if caller passes claims=, use legacy bridge path
    if claims is not None:
        pack.pop("pillar_claims")
        pack.pop("questionable_claims")
        pack.pop("background_claims_summary")
        pack["claims"] = claims
    # Also keep "claims" for adjudicator compat (PR1 TEMP)
    elif "claims" not in pack:
        all_claims = list(pack["pillar_claims"]) + list(pack["questionable_claims"])
        pack["claims"] = all_claims
    return pack


def _make_run_state(packs=None, evidence_items=None, normalized_text=None):
    items = evidence_items if evidence_items is not None else [_EVIDENCE_ITEM.copy()]
    state: dict = {
        "evidence_bank": {"items": items},
        "phase2": packs or {
            "openai": _make_pack("openai"),
            "gemini": _make_pack(
                "gemini",
                pillar_claims=[_make_claim("gemini-CL-01")],
                questionable_claims=[],
            ),
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


def test_unknown_extra_key_rejected():
    """Any key not in REQUIRED | OPTIONAL must be rejected (fail closed)."""
    pack = _make_pack()
    pack["metadata"] = {"debug": True}
    with pytest.raises(RuntimeError, match="unknown extra key"):
        validate_reviewer_pack(pack, _CFG)


def test_valid_gsae_observation_passes():
    """A pack with a valid gsae_observation optional key must pass."""
    pack = _make_pack()
    pack["gsae_observation"] = {
        "classification_bucket": "reporting",
        "intent_level": "none",
        "requires_corrob": False,
        "omission_load_bearing": False,
        "severity_tier": "minimal",
        "confidence_band": "sb_low",
    }
    validate_reviewer_pack(pack, _CFG)  # must not raise


def test_invalid_gsae_observation_rejected():
    """A pack with an invalid gsae_observation must fail closed."""
    pack = _make_pack()
    pack["gsae_observation"] = {
        "classification_bucket": "reporting",
        "intent_level": "none",
        "requires_corrob": False,
        "omission_load_bearing": False,
        "severity_tier": "minimal",
        # missing confidence_band
    }
    with pytest.raises(RuntimeError, match="key mismatch"):
        validate_reviewer_pack(pack, _CFG)


def test_valid_gsae_subject_passes():
    """A pack with a valid gsae_subject optional key must pass."""
    pack = _make_pack()
    pack["gsae_subject"] = {
        "subject_label": "Israel",
        "subject_role": "actor_primary",
        "counterparty_label": "Iran",
    }
    validate_reviewer_pack(pack, _CFG)  # must not raise


def test_gsae_subject_missing_key_rejected():
    """A gsae_subject missing a required key must fail closed."""
    pack = _make_pack()
    pack["gsae_subject"] = {
        "subject_label": "Israel",
        "subject_role": "actor_primary",
        # missing counterparty_label
    }
    with pytest.raises(RuntimeError, match="key mismatch"):
        validate_reviewer_pack(pack, _CFG)


def test_gsae_subject_extra_key_rejected():
    """A gsae_subject with an unknown key must fail closed."""
    pack = _make_pack()
    pack["gsae_subject"] = {
        "subject_label": "Israel",
        "subject_role": "actor_primary",
        "counterparty_label": "Iran",
        "polarity": "negative",
    }
    with pytest.raises(RuntimeError, match="key mismatch"):
        validate_reviewer_pack(pack, _CFG)


def test_valid_gsae_observation_v03_passes():
    """v0.3 directional packet passes strict keyset validation."""
    pack = _make_pack()
    pack["gsae_observation"] = {
        "classification_bucket": "reporting",
        "intent_level": "none",
        "requires_corrob": False,
        "omission_load_bearing": False,
        "severity_toward_subject": "minimal",
        "severity_toward_counterparty": "minimal",
        "confidence_band": "sb_low",
    }
    validate_reviewer_pack(pack, _CFG)  # must not raise


def test_gsae_observation_v03_missing_pair_rejected():
    """Missing one directional severity field fails closed."""
    pack = _make_pack()
    pack["gsae_observation"] = {
        "classification_bucket": "reporting",
        "intent_level": "none",
        "requires_corrob": False,
        "omission_load_bearing": False,
        "severity_toward_subject": "high",
        # missing severity_toward_counterparty
        "confidence_band": "sb_low",
    }
    with pytest.raises(RuntimeError, match="key mismatch"):
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


def test_unknown_claim_type_normalized_to_factual():
    claim = _make_claim(ctype="speculative")
    pack = _make_pack(pillar_claims=[claim], questionable_claims=[])
    validate_reviewer_pack(pack, _CFG)  # must not raise — normalizer maps to factual
    assert pack["pillar_claims"][0]["type"] == "factual"


def test_all_valid_claim_types_accepted():
    for ctype in CLAIM_TYPES:
        claim = _make_claim(ctype=ctype)
        pack = _make_pack(pillar_claims=[claim], questionable_claims=[])
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
            "gemini": _make_pack(
                "gemini",
                pillar_claims=[_make_claim("gemini-CL-01")],
                questionable_claims=[],
            ),
        }
    )
    validate_run(run, _CFG)  # must not raise


def test_near_duplicate_ref_dangling_raises():
    """Dangling near_duplicate_of refs that survive per-pack vote cleanup are caught by validate_run.

    Per-pack vote cleanup only filters against kept_ids within the same pack.
    A ref to a claim_id from another reviewer that exists locally (passes vote cleanup)
    but doesn't exist globally would be caught — but in practice this is rare.

    Instead, test the _validate_near_duplicate_refs function directly via a
    hand-crafted run_state where the votes bypass per-pack cleanup.
    """
    from engine.core.validators import _validate_near_duplicate_refs
    phase2 = {
        "openai": {
            "cross_claim_votes": [
                {"claim_id": "openai-CL-01", "near_duplicate_of": ["GHOST-CL-99"]},
            ],
        },
    }
    claim_registry = {"openai-CL-01", "gemini-CL-01"}
    with pytest.raises(RuntimeError, match="dangling reference"):
        _validate_near_duplicate_refs(phase2, claim_registry)


# ---------------------------------------------------------------------------
# (fix) Symmetric authority rule: not_verifiable exempt
# ---------------------------------------------------------------------------


def _make_verification_result(status, authority_sources=None):
    base = {
        "claim_id": "G001",
        "claim_text": "Some claim text.",
        "claim_kind": "world_fact",      # CLAIM_KINDS from engine.verify.base
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
    run = _make_run_state(
        packs={
            "openai": _make_pack(
                "openai",
                pillar_claims=[_make_claim(eids=["E99"])],
                questionable_claims=[],
            ),
            "gemini": _make_pack(
                "gemini",
                pillar_claims=[_make_claim("gemini-CL-01", eids=["E1"])],
                questionable_claims=[],
            ),
        }
    )
    with pytest.raises(RuntimeError, match="EID integrity failure"):
        validate_run(run, _CFG)


def test_valid_run_passes():
    run = _make_run_state()
    validate_run(run, _CFG)  # must not raise


# ---------------------------------------------------------------------------
# Triage model: pillar/questionable clamp + vote cleanup
# ---------------------------------------------------------------------------


def test_pillar_claims_truncated_when_exceeds_cap():
    """20 pillar claims with cap=15 → truncated, warning emitted."""
    claims = [_make_claim(claim_id=f"CL-{i:02d}") for i in range(20)]
    pack = _make_pack(pillar_claims=claims, questionable_claims=[])
    validate_reviewer_pack(pack, _CFG)
    assert len(pack["pillar_claims"]) == 15
    warnings = pack.get("_policy_warnings", [])
    codes = [w["code"] for w in warnings]
    assert "pillar_claims_truncated" in codes


def test_questionable_claims_truncated_when_exceeds_cap():
    """35 questionable claims with cap=30 → truncated, warning emitted."""
    claims = [_make_claim(claim_id=f"CL-{i:02d}") for i in range(35)]
    pack = _make_pack(pillar_claims=[], questionable_claims=claims)
    validate_reviewer_pack(pack, _CFG)
    assert len(pack["questionable_claims"]) == 30
    warnings = pack.get("_policy_warnings", [])
    codes = [w["code"] for w in warnings]
    assert "questionable_claims_truncated" in codes


def test_vote_cleanup_after_truncation():
    """Votes referencing truncated claim_ids are dropped; near_duplicate_of cleaned."""
    # Claims: CL-00..CL-19 (pillar), CL-15 will be truncated
    pillar = [_make_claim(claim_id=f"CL-{i:02d}") for i in range(20)]
    votes = [
        {"claim_id": "CL-00", "vote": "supported", "confidence": "high",
         "near_duplicate_of": ["CL-16"]},  # CL-16 will be truncated
        {"claim_id": "CL-16", "vote": "supported", "confidence": "high"},  # will be dropped
    ]
    pack = _make_pack(pillar_claims=pillar, questionable_claims=[], votes=votes)
    validate_reviewer_pack(pack, _CFG)
    remaining_votes = pack["cross_claim_votes"]
    assert len(remaining_votes) == 1
    assert remaining_votes[0]["claim_id"] == "CL-00"
    assert remaining_votes[0]["near_duplicate_of"] == []


# ---------------------------------------------------------------------------
# Legacy bridge: claims → questionable_claims
# ---------------------------------------------------------------------------


def test_legacy_bridge_converts_claims_to_questionable():
    """Pack with only 'claims' key → bridged to questionable_claims + warning."""
    legacy_pack = _make_pack(claims=[_make_claim()])
    validate_reviewer_pack(legacy_pack, _CFG)
    assert legacy_pack["questionable_claims"] == [_make_claim()]
    assert legacy_pack["pillar_claims"] == []
    warnings = legacy_pack.get("_policy_warnings", [])
    codes = [w["code"] for w in warnings]
    assert "legacy_claims_field_used" in codes


def test_legacy_bridge_preserves_claims_key():
    """Legacy bridge must COPY, not move — claims key remains for adjudicator compat."""
    legacy_pack = _make_pack(claims=[_make_claim()])
    validate_reviewer_pack(legacy_pack, _CFG)
    assert "claims" in legacy_pack


def test_legacy_bridge_synthesizes_background_summary():
    """Legacy bridge must create background_claims_summary with correct counts."""
    claims = [_make_claim(claim_id=f"CL-{i}") for i in range(5)]
    legacy_pack = _make_pack(claims=claims)
    validate_reviewer_pack(legacy_pack, _CFG)
    bcs = legacy_pack["background_claims_summary"]
    assert bcs["total_claims_estimate"] == 5
    assert bcs["not_triaged_count"] == 0


# ---------------------------------------------------------------------------
# E5: Category collision trap
# ---------------------------------------------------------------------------


def test_e5_collision_dedupes_to_pillar():
    """Same claim_id in both lists → kept in pillar, removed from questionable."""
    shared_claim = _make_claim(claim_id="SHARED-01")
    unique_q = _make_claim(claim_id="Q-ONLY-01")
    pack = _make_pack(
        pillar_claims=[shared_claim],
        questionable_claims=[dict(shared_claim), unique_q],
    )
    validate_reviewer_pack(pack, _CFG)
    q_ids = [c["claim_id"] for c in pack["questionable_claims"]]
    assert "SHARED-01" not in q_ids
    assert "Q-ONLY-01" in q_ids
    warnings = pack.get("_policy_warnings", [])
    codes = [w["code"] for w in warnings]
    assert "claim_category_collision_deduped" in codes


# ---------------------------------------------------------------------------
# background_claims_summary validation
# ---------------------------------------------------------------------------


def test_background_summary_missing_not_triaged_count_raises():
    pack = _make_pack(
        background_claims_summary={"total_claims_estimate": 10},
    )
    with pytest.raises(RuntimeError, match="not_triaged_count"):
        validate_reviewer_pack(pack, _CFG)


def test_background_summary_valid_passes():
    pack = _make_pack(
        background_claims_summary={"total_claims_estimate": 10, "not_triaged_count": 5},
    )
    validate_reviewer_pack(pack, _CFG)  # must not raise


def test_background_summary_with_samples_passes():
    pack = _make_pack(
        background_claims_summary={
            "total_claims_estimate": 10,
            "not_triaged_count": 5,
            "samples": ["Claim A", "Claim B"],
        },
    )
    validate_reviewer_pack(pack, _CFG)  # must not raise


def test_background_summary_invalid_samples_raises():
    pack = _make_pack(
        background_claims_summary={
            "total_claims_estimate": 10,
            "not_triaged_count": 5,
            "samples": [123],  # not list[str]
        },
    )
    with pytest.raises(RuntimeError, match="samples must be list"):
        validate_reviewer_pack(pack, _CFG)
