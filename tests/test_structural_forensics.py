#!/usr/bin/env python3
"""
FILE: tests/test_structural_forensics.py
PURPOSE:
Tests for structural forensics validator functions (v0.5):
  - claim_omissions
  - article_omissions
  - framing_omissions
  - argument_summary
  - object_discipline_check

These fields are OPTIONAL in the ReviewerPack schema.
When present, they are validated strictly.
"""

import pytest

from engine.core.validators import validate_reviewer_pack


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_CFG = {
    "max_claims_per_reviewer": 20,
    "max_pillar_claims_per_reviewer": 15,
    "max_questionable_claims_per_reviewer": 30,
    "max_near_duplicate_links": 3,
    "reviewers_enabled": ["openai"],
    "confidence_weights": {"low": 0.5, "medium": 1.0, "high": 1.5},
    "model_weights": {"openai": 1.0},
    "decision_margin": 0.2,
}


def _make_pack(**extras):
    pack = {
        "reviewer": "openai",
        "whole_article_judgment": {
            "classification": "advocacy",
            "confidence": "high",
            "evidence_eids": ["E1"],
        },
        "main_conclusion": {"text": "The article argues X."},
        "pillar_claims": [
            {
                "claim_id": "PC1",
                "text": "A factual claim.",
                "type": "factual",
                "evidence_eids": ["E1"],
                "centrality": 1,
            }
        ],
        "questionable_claims": [],
        "background_claims_summary": {
            "total_claims_estimate": 1,
            "not_triaged_count": 0,
        },
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
    pack.update(extras)
    return pack


# ---------------------------------------------------------------------------
# claim_omissions
# ---------------------------------------------------------------------------


class TestClaimOmissions:
    def test_valid_claim_omission_passes(self):
        pack = _make_pack(claim_omissions=[
            {
                "target_claim_id": "PC1",
                "missing_frame": "contested negotiation history",
                "reason_expected": "universal claim requires rival interpretation",
                "confidence": "high",
            }
        ])
        validate_reviewer_pack(pack, _CFG)  # should not raise

    def test_missing_target_claim_id_raises(self):
        pack = _make_pack(claim_omissions=[
            {
                "missing_frame": "contested negotiation history",
                "reason_expected": "requires rival interpretation",
                "confidence": "high",
            }
        ])
        with pytest.raises(RuntimeError, match="target_claim_id"):
            validate_reviewer_pack(pack, _CFG)

    def test_invalid_confidence_raises(self):
        pack = _make_pack(claim_omissions=[
            {
                "target_claim_id": "PC1",
                "missing_frame": "contested history",
                "reason_expected": "requires rival",
                "confidence": "very_high",
            }
        ])
        with pytest.raises(RuntimeError, match="confidence"):
            validate_reviewer_pack(pack, _CFG)

    def test_empty_list_passes(self):
        pack = _make_pack(claim_omissions=[])
        validate_reviewer_pack(pack, _CFG)


# ---------------------------------------------------------------------------
# article_omissions
# ---------------------------------------------------------------------------


class TestArticleOmissions:
    def test_valid_article_omission_passes(self):
        pack = _make_pack(article_omissions=[
            {
                "missing_frame": "occupation as rival causal explanation",
                "affected_claim_ids": ["PC1"],
                "reason_expected": "article explains violence causally but omits major alternative",
                "confidence": "high",
            }
        ])
        validate_reviewer_pack(pack, _CFG)

    def test_missing_affected_claim_ids_raises(self):
        pack = _make_pack(article_omissions=[
            {
                "missing_frame": "occupation as rival explanation",
                "reason_expected": "omits alternative",
                "confidence": "high",
            }
        ])
        with pytest.raises(RuntimeError, match="affected_claim_ids"):
            validate_reviewer_pack(pack, _CFG)

    def test_empty_list_passes(self):
        pack = _make_pack(article_omissions=[])
        validate_reviewer_pack(pack, _CFG)


# ---------------------------------------------------------------------------
# framing_omissions
# ---------------------------------------------------------------------------


class TestFramingOmissions:
    def test_valid_framing_omission_passes(self):
        pack = _make_pack(framing_omissions=[
            {
                "frame_used_by_article": "antisemitism lens",
                "missing_frame": "territorial / nationalist framing",
                "alternative_frames": [
                    "territorial sovereignty dispute",
                    "human rights framework",
                ],
                "reason_expected": "article uses one lens excluding rival definitions",
                "confidence": "high",
            }
        ])
        validate_reviewer_pack(pack, _CFG)

    def test_missing_alternative_frames_raises(self):
        pack = _make_pack(framing_omissions=[
            {
                "frame_used_by_article": "antisemitism lens",
                "missing_frame": "nationalist framing",
                "reason_expected": "excludes rival definitions",
                "confidence": "high",
            }
        ])
        with pytest.raises(RuntimeError, match="alternative_frames"):
            validate_reviewer_pack(pack, _CFG)

    def test_non_string_alternative_frames_raises(self):
        pack = _make_pack(framing_omissions=[
            {
                "frame_used_by_article": "antisemitism lens",
                "missing_frame": "nationalist framing",
                "alternative_frames": [123],
                "reason_expected": "excludes rival",
                "confidence": "high",
            }
        ])
        with pytest.raises(RuntimeError, match="alternative_frames"):
            validate_reviewer_pack(pack, _CFG)

    def test_empty_list_passes(self):
        pack = _make_pack(framing_omissions=[])
        validate_reviewer_pack(pack, _CFG)


# ---------------------------------------------------------------------------
# argument_summary
# ---------------------------------------------------------------------------


class TestArgumentSummary:
    def test_valid_argument_summary_passes(self):
        pack = _make_pack(argument_summary={
            "main_conclusion": "Anti-Zionism is the greatest threat to Jews",
            "supporting_reasons": [
                "existential threat to Israeli Jews",
                "assault on post-Holocaust identity",
            ],
            "key_rival_explanations_missing": [
                "territorial dispute framing",
                "international law framework",
            ],
        })
        validate_reviewer_pack(pack, _CFG)

    def test_missing_main_conclusion_raises(self):
        pack = _make_pack(argument_summary={
            "supporting_reasons": ["reason"],
            "key_rival_explanations_missing": ["rival"],
        })
        with pytest.raises(RuntimeError, match="main_conclusion"):
            validate_reviewer_pack(pack, _CFG)

    def test_missing_supporting_reasons_raises(self):
        pack = _make_pack(argument_summary={
            "main_conclusion": "conclusion",
            "key_rival_explanations_missing": ["rival"],
        })
        with pytest.raises(RuntimeError, match="supporting_reasons"):
            validate_reviewer_pack(pack, _CFG)

    def test_missing_key_rival_raises(self):
        pack = _make_pack(argument_summary={
            "main_conclusion": "conclusion",
            "supporting_reasons": ["reason"],
        })
        with pytest.raises(RuntimeError, match="key_rival_explanations_missing"):
            validate_reviewer_pack(pack, _CFG)


# ---------------------------------------------------------------------------
# object_discipline_check
# ---------------------------------------------------------------------------


class TestObjectDisciplineCheck:
    def test_pass_status_passes(self):
        pack = _make_pack(object_discipline_check={
            "status": "pass",
            "reason": "all findings tethered to article claims",
        })
        validate_reviewer_pack(pack, _CFG)

    def test_fail_status_passes(self):
        pack = _make_pack(object_discipline_check={
            "status": "fail",
            "reason": "topic drift detected in omission candidates",
        })
        validate_reviewer_pack(pack, _CFG)

    def test_invalid_status_normalized(self):
        """Layer 8 normalizer repairs invalid status to 'pass'."""
        pack = _make_pack(object_discipline_check={
            "status": "warning",
            "reason": "some drift",
        })
        validate_reviewer_pack(pack, _CFG)
        assert pack["object_discipline_check"]["status"] == "pass"

    def test_missing_reason_normalized(self):
        """Layer 8 normalizer repairs missing/empty reason."""
        pack = _make_pack(object_discipline_check={
            "status": "pass",
        })
        validate_reviewer_pack(pack, _CFG)
        assert pack["object_discipline_check"]["reason"] == "No reason provided by reviewer."


# ---------------------------------------------------------------------------
# Pack without structural forensics fields still passes (optional)
# ---------------------------------------------------------------------------


class TestOptionalFields:
    def test_pack_without_forensics_fields_passes(self):
        pack = _make_pack()
        validate_reviewer_pack(pack, _CFG)

    def test_pack_with_all_forensics_fields_passes(self):
        pack = _make_pack(
            claim_omissions=[{
                "target_claim_id": "PC1",
                "missing_frame": "contested history",
                "reason_expected": "requires rival",
                "confidence": "medium",
            }],
            article_omissions=[{
                "missing_frame": "occupation as rival explanation",
                "affected_claim_ids": ["PC1"],
                "reason_expected": "omits alternative framework",
                "confidence": "high",
            }],
            framing_omissions=[{
                "frame_used_by_article": "antisemitism lens",
                "missing_frame": "nationalist framing",
                "alternative_frames": ["territorial dispute"],
                "reason_expected": "excludes rival definitions",
                "confidence": "medium",
            }],
            argument_summary={
                "main_conclusion": "Article argues X",
                "supporting_reasons": ["reason A", "reason B"],
                "key_rival_explanations_missing": ["rival X"],
            },
            object_discipline_check={
                "status": "pass",
                "reason": "all findings grounded in article",
            },
        )
        validate_reviewer_pack(pack, _CFG)
