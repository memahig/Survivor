#!/usr/bin/env python3
"""
FILE: tests/test_verification_smoke.py
PURPOSE:
Smoke tests for the verification layer (engine/verify/base.py).
Prevents hidden ImportErrors from the local import in _validate_verification().

Tests:
  - engine/verify/base.py imports cleanly and exports required names.
  - validate_authority_source() enforces source_type and locator/url.
  - validate_run() with verification_enabled=True passes structural validation
    using enums from engine/verify/base.py.

Run with: python -m pytest tests/ -v
"""

import pytest

from engine.verify.base import (
    CLAIM_KINDS,
    CONFIDENCE_VALUES,
    SOURCE_TYPES,
    VERIFICATION_STATUSES,
    validate_authority_source,
)
from engine.core.validators import validate_run


# ---------------------------------------------------------------------------
# Import / enum smoke tests
# ---------------------------------------------------------------------------


def test_claim_kinds_nonempty():
    assert len(CLAIM_KINDS) > 0


def test_verification_statuses_nonempty():
    assert len(VERIFICATION_STATUSES) > 0


def test_source_types_nonempty():
    assert len(SOURCE_TYPES) > 0


def test_confidence_values_nonempty():
    assert len(CONFIDENCE_VALUES) > 0


def test_confidence_values_are_uppercase():
    for v in CONFIDENCE_VALUES:
        assert v == v.upper(), f"CONFIDENCE_VALUES must be uppercase; got {v!r}"


def test_not_checked_yet_in_verification_statuses():
    assert "not_checked_yet" in VERIFICATION_STATUSES


def test_not_verifiable_in_verification_statuses():
    assert "not_verifiable" in VERIFICATION_STATUSES


# ---------------------------------------------------------------------------
# validate_authority_source
# ---------------------------------------------------------------------------


def test_authority_source_valid_with_url():
    validate_authority_source({"source_type": "web", "url": "https://example.com"})


def test_authority_source_valid_with_locator():
    validate_authority_source({"source_type": "gov", "locator": "Section 4, para 2"})


def test_authority_source_invalid_source_type_raises():
    with pytest.raises(RuntimeError, match="source_type invalid"):
        validate_authority_source({"source_type": "alien", "url": "https://example.com"})


def test_authority_source_missing_locator_and_url_raises():
    with pytest.raises(RuntimeError, match="locator or url"):
        validate_authority_source({"source_type": "web"})


def test_authority_source_empty_url_raises():
    with pytest.raises(RuntimeError, match="locator or url"):
        validate_authority_source({"source_type": "web", "url": "   "})


def test_authority_source_not_dict_raises():
    with pytest.raises(RuntimeError):
        validate_authority_source("not-a-dict")


# ---------------------------------------------------------------------------
# validate_run with verification_enabled=True
# ---------------------------------------------------------------------------

_EVIDENCE_ITEM = {
    "eid": "E1",
    "quote": "Verbatim sentence from the article.",
    "locator": {"char_start": 0, "char_end": 35},
    "source_id": "A1",
    "text": "Verbatim sentence from the article.",
    "char_len": 35,
}

assert len("Verbatim sentence from the article.") == 35


_REVIEWER_PACK = {
    "reviewer": "openai",
    "whole_article_judgment": {
        "classification": "analysis",
        "confidence": "high",
        "evidence_eids": ["E1"],
    },
    "main_conclusion": {"text": "The article presents factual analysis."},
    "pillar_claims": [],
    "questionable_claims": [
        {
            "claim_id": "openai-CL-01",
            "text": "A factual claim.",
            "type": "factual",
            "evidence_eids": ["E1"],
            "centrality": 1,
        }
    ],
    "background_claims_summary": {"total_claims_estimate": 1, "not_triaged_count": 0},
    "scope_markers": [],
    "causal_links": [],
    "article_patterns": [],
    "omission_candidates": [],
    "counterfactual_requirements": [],
    "evidence_density": {
        "claims_count": 1,
        "claims_with_internal_support": 1,
        "external_sources_count": 0,
    },
    "claim_tickets": [],
    "article_tickets": [],
    "cross_claim_votes": [],
}

_CFG = {
    "max_claims_per_reviewer": 20,
    "max_near_duplicate_links": 3,
    "reviewers_enabled": ["openai"],
    "confidence_weights": {"low": 0.5, "medium": 1.0, "high": 1.5},
    "model_weights": {"openai": 1.0},
    "decision_margin": 0.2,
    "verification_enabled": True,
}


def _make_verification_result(status: str, authority_sources=None):
    # Keep claim_id aligned with the claim_id used in phase2 for coherence.
    return {
        "claim_id": "openai-CL-01",
        "claim_text": "A factual claim.",
        "claim_kind": "world_fact",   # from CLAIM_KINDS
        "verification_status": status,
        "confidence": "LOW",          # from CONFIDENCE_VALUES (uppercase)
        "authority_sources": authority_sources if authority_sources is not None else [],
        "method_note": "Automated smoke check.",
        "checked_at": "2026-02-24T00:00:00Z",
    }


def _make_run_state(verification_result):
    return {
        "evidence_bank": {"items": [_EVIDENCE_ITEM.copy()]},
        "phase2": {"openai": _REVIEWER_PACK},
        "verification": {
            "enabled": True,
            "results": [verification_result],
        },
    }


def test_validate_run_verification_enabled_not_checked_yet_passes():
    run = _make_run_state(_make_verification_result("not_checked_yet"))
    validate_run(run, _CFG)  # must not raise


def test_validate_run_verification_enabled_not_verifiable_passes():
    run = _make_run_state(_make_verification_result("not_verifiable"))
    validate_run(run, _CFG)  # must not raise


def test_validate_run_verification_enabled_verified_true_with_source_passes():
    result = _make_verification_result(
        "verified_true",
        authority_sources=[{"source_type": "web", "url": "https://example.com"}],
    )
    run = _make_run_state(result)
    validate_run(run, _CFG)  # must not raise


def test_validate_run_verification_enabled_verified_true_no_source_raises():
    result = _make_verification_result("verified_true", authority_sources=[])
    run = _make_run_state(result)
    with pytest.raises(RuntimeError, match="authority_sources must be non-empty"):
        validate_run(run, _CFG)


def test_validate_run_verification_enabled_invalid_claim_kind_raises():
    result = _make_verification_result("not_checked_yet")
    result["claim_kind"] = "ghost_kind"
    run = _make_run_state(result)
    with pytest.raises(RuntimeError, match="claim_kind invalid"):
        validate_run(run, _CFG)


def test_validate_run_verification_enabled_invalid_status_raises():
    result = _make_verification_result("not_checked_yet")
    result["verification_status"] = "totally_made_up"
    run = _make_run_state(result)
    with pytest.raises(RuntimeError, match="verification_status invalid"):
        validate_run(run, _CFG)
