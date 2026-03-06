#!/usr/bin/env python3
"""Tests for engine.core.spine_builder."""

from engine.core.spine_builder import build_argument_spine


def test_empty_input():
    result = build_argument_spine({})
    assert result == {
        "main_conclusion": {},
        "pillar_claims": [],
        "questionable_claims": [],
    }


def test_single_reviewer():
    triage = {
        "reviewer_a": {
            "main_conclusion": {"text": "Short conclusion.", "confidence": "medium"},
            "pillar_claims": [{"claim_id": "a-PC1", "text": "Pillar one"}],
            "questionable_claims": [{"claim_id": "a-QC1", "text": "Questionable one"}],
        }
    }
    result = build_argument_spine(triage)
    assert result["main_conclusion"]["text"] == "Short conclusion."
    assert len(result["pillar_claims"]) == 1
    assert len(result["questionable_claims"]) == 1


def test_multiple_reviewers_union():
    triage = {
        "reviewer_a": {
            "main_conclusion": {"text": "Short.", "confidence": "low"},
            "pillar_claims": [{"claim_id": "a-PC1", "text": "A pillar"}],
            "questionable_claims": [],
        },
        "reviewer_b": {
            "main_conclusion": {"text": "This is a longer conclusion text.", "confidence": "high"},
            "pillar_claims": [{"claim_id": "b-PC1", "text": "B pillar"}],
            "questionable_claims": [{"claim_id": "b-QC1", "text": "B questionable"}],
        },
    }
    result = build_argument_spine(triage)
    # Longest conclusion wins
    assert result["main_conclusion"]["text"] == "This is a longer conclusion text."
    # Union of all claims
    assert len(result["pillar_claims"]) == 2
    assert len(result["questionable_claims"]) == 1


def test_non_dict_pack_skipped():
    triage = {
        "reviewer_a": "not a dict",
        "reviewer_b": {
            "main_conclusion": {"text": "Valid.", "confidence": "medium"},
            "pillar_claims": [],
            "questionable_claims": [],
        },
    }
    result = build_argument_spine(triage)
    assert result["main_conclusion"]["text"] == "Valid."


def test_non_dict_claims_skipped():
    triage = {
        "reviewer_a": {
            "main_conclusion": {"text": "Ok.", "confidence": "low"},
            "pillar_claims": ["not a dict", {"claim_id": "a-PC1", "text": "Valid"}],
            "questionable_claims": [42],
        },
    }
    result = build_argument_spine(triage)
    assert len(result["pillar_claims"]) == 1
    assert len(result["questionable_claims"]) == 0
