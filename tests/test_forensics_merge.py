#!/usr/bin/env python3
"""
FILE: tests/test_forensics_merge.py
PURPOSE:
Tests for engine/core/forensics_merge.py — cross-reviewer structural
forensics merging with provenance preservation.
"""

import pytest

from engine.core.forensics_merge import merge_structural_forensics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pack(**extras):
    """Minimal valid pack stub (only forensics fields matter here)."""
    base = {"reviewer": "test"}
    base.update(extras)
    return base


# ---------------------------------------------------------------------------
# Claim omissions
# ---------------------------------------------------------------------------


class TestClaimOmissionsMerge:
    def test_same_target_same_frame_merges(self):
        packs = {
            "openai": _pack(claim_omissions=[{
                "target_claim_id": "PC1",
                "missing_frame": "contested negotiation history",
                "reason_expected": "requires rival",
                "confidence": "high",
            }]),
            "claude": _pack(claim_omissions=[{
                "target_claim_id": "PC1",
                "missing_frame": "Contested negotiation history",
                "reason_expected": "universal claim requires rival interpretation",
                "confidence": "medium",
            }]),
        }
        result = merge_structural_forensics(packs)
        co = result["claim_omissions"]
        assert len(co) == 1
        assert co[0]["kind"] == "claim_omission"
        assert co[0]["target_claim_id"] == "PC1"
        assert set(co[0]["supporting_reviewers"]) == {"openai", "claude"}
        assert co[0]["confidence_by_reviewer"]["openai"] == "high"
        assert co[0]["confidence_by_reviewer"]["claude"] == "medium"
        assert co[0]["concern_level"] == "elevated"

    def test_same_target_different_frame_stays_separate(self):
        packs = {
            "openai": _pack(claim_omissions=[{
                "target_claim_id": "PC1",
                "missing_frame": "contested negotiation history",
                "reason_expected": "r1",
                "confidence": "high",
            }]),
            "claude": _pack(claim_omissions=[{
                "target_claim_id": "PC1",
                "missing_frame": "occupation as context",
                "reason_expected": "r2",
                "confidence": "medium",
            }]),
        }
        result = merge_structural_forensics(packs)
        co = result["claim_omissions"]
        assert len(co) == 2
        # Each has 1 reviewer → low concern
        for item in co:
            assert item["concern_level"] == "low"

    def test_three_reviewers_gives_high(self):
        packs = {
            "openai": _pack(claim_omissions=[{
                "target_claim_id": "PC2",
                "missing_frame": "rival explanation",
                "reason_expected": "r",
                "confidence": "high",
            }]),
            "claude": _pack(claim_omissions=[{
                "target_claim_id": "PC2",
                "missing_frame": "rival explanation",
                "reason_expected": "r",
                "confidence": "medium",
            }]),
            "gemini": _pack(claim_omissions=[{
                "target_claim_id": "PC2",
                "missing_frame": "Rival explanation",
                "reason_expected": "r",
                "confidence": "low",
            }]),
        }
        result = merge_structural_forensics(packs)
        co = result["claim_omissions"]
        assert len(co) == 1
        assert co[0]["concern_level"] == "high"
        assert len(co[0]["supporting_reviewers"]) == 3

    def test_empty_omissions_returns_empty(self):
        packs = {
            "openai": _pack(claim_omissions=[]),
            "claude": _pack(),
        }
        result = merge_structural_forensics(packs)
        assert result["claim_omissions"] == []


# ---------------------------------------------------------------------------
# Article omissions
# ---------------------------------------------------------------------------


class TestArticleOmissionsMerge:
    def test_same_frame_merges_with_union_claim_ids(self):
        packs = {
            "openai": _pack(article_omissions=[{
                "missing_frame": "occupation as rival causal explanation",
                "affected_claim_ids": ["PC1", "PC2"],
                "reason_expected": "article omits alternative",
                "confidence": "high",
            }]),
            "gemini": _pack(article_omissions=[{
                "missing_frame": "Occupation as rival causal explanation",
                "affected_claim_ids": ["PC2", "PC3"],
                "reason_expected": "omits major alternative framework",
                "confidence": "medium",
            }]),
        }
        result = merge_structural_forensics(packs)
        ao = result["article_omissions"]
        assert len(ao) == 1
        assert ao[0]["kind"] == "article_omission"
        assert set(ao[0]["affected_claim_ids"]) == {"PC1", "PC2", "PC3"}
        assert ao[0]["concern_level"] == "elevated"
        # Longer reason wins as merged_text
        assert "framework" in ao[0]["reason_expected"]

    def test_different_frames_stay_separate(self):
        packs = {
            "openai": _pack(article_omissions=[{
                "missing_frame": "occupation as cause",
                "affected_claim_ids": ["PC1"],
                "reason_expected": "r",
                "confidence": "high",
            }]),
            "claude": _pack(article_omissions=[{
                "missing_frame": "international law framework",
                "affected_claim_ids": ["PC2"],
                "reason_expected": "r",
                "confidence": "medium",
            }]),
        }
        result = merge_structural_forensics(packs)
        assert len(result["article_omissions"]) == 2


# ---------------------------------------------------------------------------
# Framing omissions
# ---------------------------------------------------------------------------


class TestFramingOmissionsMerge:
    def test_same_frame_merges_with_union_alternatives(self):
        packs = {
            "openai": _pack(framing_omissions=[{
                "frame_used_by_article": "antisemitism lens",
                "missing_frame": "nationalist framing",
                "alternative_frames": ["territorial dispute"],
                "reason_expected": "excludes rival",
                "confidence": "high",
            }]),
            "claude": _pack(framing_omissions=[{
                "frame_used_by_article": "antisemitism lens",
                "missing_frame": "Nationalist framing",
                "alternative_frames": ["human rights framework"],
                "reason_expected": "excludes rival definitions of the conflict",
                "confidence": "medium",
            }]),
        }
        result = merge_structural_forensics(packs)
        fo = result["framing_omissions"]
        assert len(fo) == 1
        assert set(fo[0]["alternative_frames"]) == {"territorial dispute", "human rights framework"}
        assert fo[0]["concern_level"] == "elevated"

    def test_empty_returns_empty(self):
        packs = {"openai": _pack(), "claude": _pack()}
        result = merge_structural_forensics(packs)
        assert result["framing_omissions"] == []


# ---------------------------------------------------------------------------
# Argument summary
# ---------------------------------------------------------------------------


class TestArgumentSummaryMerge:
    def test_merges_rival_explanations(self):
        packs = {
            "openai": _pack(argument_summary={
                "main_conclusion": "Article argues X",
                "supporting_reasons": ["reason A"],
                "key_rival_explanations_missing": ["territorial dispute", "international law"],
            }),
            "claude": _pack(argument_summary={
                "main_conclusion": "Article claims X",
                "supporting_reasons": ["reason B"],
                "key_rival_explanations_missing": ["Territorial dispute", "human rights framework"],
            }),
        }
        result = merge_structural_forensics(packs)
        a = result["argument_summary"]
        assert set(a["supporting_reviewers"]) == {"openai", "claude"}
        # "territorial dispute" dedupes (case-insensitive)
        rivals = a["merged_rival_explanations_missing"]
        norms = [r.lower() for r in rivals]
        assert norms.count("territorial dispute") == 1
        assert any("human rights" in r.lower() for r in rivals)
        assert any("international law" in r.lower() for r in rivals)
        # Preserves per-reviewer summaries
        assert "openai" in a["by_reviewer"]
        assert "claude" in a["by_reviewer"]

    def test_no_summaries_returns_none(self):
        packs = {"openai": _pack(), "claude": _pack()}
        result = merge_structural_forensics(packs)
        assert "argument_summary" not in result


# ---------------------------------------------------------------------------
# Object discipline check
# ---------------------------------------------------------------------------


class TestObjectDisciplineMerge:
    def test_all_pass(self):
        packs = {
            "openai": _pack(object_discipline_check={"status": "pass", "reason": "ok"}),
            "claude": _pack(object_discipline_check={"status": "pass", "reason": "grounded"}),
        }
        result = merge_structural_forensics(packs)
        odc = result["object_discipline_check"]
        assert odc["overall_status"] == "pass"
        assert len(odc["supporting_reviewers"]) == 2

    def test_one_fail_means_overall_fail(self):
        packs = {
            "openai": _pack(object_discipline_check={"status": "pass", "reason": "ok"}),
            "claude": _pack(object_discipline_check={"status": "fail", "reason": "drift detected"}),
        }
        result = merge_structural_forensics(packs)
        assert result["object_discipline_check"]["overall_status"] == "fail"

    def test_no_checks_returns_none(self):
        packs = {"openai": _pack(), "claude": _pack()}
        result = merge_structural_forensics(packs)
        assert "object_discipline_check" not in result


# ---------------------------------------------------------------------------
# Concern level edge cases
# ---------------------------------------------------------------------------


class TestConcernLevel:
    def test_single_reviewer_is_low(self):
        packs = {
            "openai": _pack(article_omissions=[{
                "missing_frame": "frame A",
                "affected_claim_ids": ["PC1"],
                "reason_expected": "r",
                "confidence": "high",
            }]),
        }
        result = merge_structural_forensics(packs)
        assert result["article_omissions"][0]["concern_level"] == "low"

    def test_merged_text_uses_longest(self):
        packs = {
            "openai": _pack(article_omissions=[{
                "missing_frame": "rival",
                "affected_claim_ids": [],
                "reason_expected": "short",
                "confidence": "high",
            }]),
            "claude": _pack(article_omissions=[{
                "missing_frame": "Rival",
                "affected_claim_ids": [],
                "reason_expected": "a much longer reason expected text",
                "confidence": "medium",
            }]),
        }
        result = merge_structural_forensics(packs)
        ao = result["article_omissions"]
        assert len(ao) == 1
        assert ao[0]["reason_expected"] == "a much longer reason expected text"


# ---------------------------------------------------------------------------
# Rival narratives
# ---------------------------------------------------------------------------


class TestRivalNarrativesMerge:
    def test_same_lens_merges(self):
        packs = {
            "openai": _pack(rival_narratives=[{
                "rival_narrative_id": "RN1",
                "lens": "territorial / occupation",
                "summary": "Violence from occupation",
                "same_core_facts_used": ["E1"],
                "claims_weakened_if_true": ["PC1"],
                "structural_fragility": "elevated",
                "confidence": "high",
            }]),
            "claude": _pack(rival_narratives=[{
                "rival_narrative_id": "RN1",
                "lens": "Territorial / Occupation",
                "summary": "Violence explained through long-term occupation and blockade",
                "same_core_facts_used": ["E1", "E3"],
                "claims_weakened_if_true": ["PC1", "PC8"],
                "structural_fragility": "high",
                "confidence": "medium",
            }]),
        }
        result = merge_structural_forensics(packs)
        rn = result["rival_narratives"]
        assert len(rn) == 1
        assert rn[0]["kind"] == "rival_narrative"
        assert sorted(rn[0]["supporting_reviewers"]) == ["claude", "openai"]
        assert rn[0]["concern_level"] == "elevated"
        # Longest summary wins
        assert "long-term occupation" in rn[0]["merged_summary"]
        # Highest fragility wins
        assert rn[0]["structural_fragility"] == "high"
        # Union of facts and weakened claims
        assert "E3" in rn[0]["same_core_facts_used"]
        assert "PC8" in rn[0]["claims_weakened_if_true"]

    def test_different_lens_stays_separate(self):
        packs = {
            "openai": _pack(rival_narratives=[{
                "rival_narrative_id": "RN1",
                "lens": "territorial",
                "summary": "Territorial explanation",
                "same_core_facts_used": ["E1"],
                "claims_weakened_if_true": ["PC1"],
                "structural_fragility": "elevated",
                "confidence": "high",
            }]),
            "claude": _pack(rival_narratives=[{
                "rival_narrative_id": "RN1",
                "lens": "economic disparity",
                "summary": "Economic explanation",
                "same_core_facts_used": ["E2"],
                "claims_weakened_if_true": ["PC2"],
                "structural_fragility": "low",
                "confidence": "medium",
            }]),
        }
        result = merge_structural_forensics(packs)
        rn = result["rival_narratives"]
        assert len(rn) == 2

    def test_empty_all_reviewers_triggers_blind_spot_fail(self):
        packs = {
            "openai": _pack(rival_narratives=[]),
            "claude": _pack(rival_narratives=[]),
            "gemini": _pack(rival_narratives=[]),
        }
        result = merge_structural_forensics(packs)
        assert result["rival_narratives"] == []
        sbs = result["shared_blind_spot_check"]
        assert sbs["status"] == "fail"
        assert "corpus-locked" in sbs["reason"].lower()

    def test_one_reviewer_has_rival_triggers_pass(self):
        packs = {
            "openai": _pack(rival_narratives=[]),
            "claude": _pack(rival_narratives=[{
                "rival_narrative_id": "RN1",
                "lens": "territorial",
                "summary": "Territory-based explanation",
                "same_core_facts_used": ["E1"],
                "claims_weakened_if_true": ["PC1"],
                "structural_fragility": "elevated",
                "confidence": "medium",
            }]),
        }
        result = merge_structural_forensics(packs)
        sbs = result["shared_blind_spot_check"]
        assert sbs["status"] == "pass"
        assert len(result["rival_narratives"]) == 1
