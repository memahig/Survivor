"""
FILE: tests/test_escalation_policy.py
VERSION: 0.1.0
PURPOSE:
Tests for the escalation policy (L5A).

BUILD MANIFEST: Stage 3 — Escalation Policy.
"""

import pytest

from engine.analysis.escalation_policy import (
    EscalationDecision,
    evaluate_escalation,
)
from engine.analysis.persuasion_screen import PersuasionResult
from engine.core.mode_types import ModeResult


# ── test helpers ─────────────────────────────────────────────────────

def _mode(
    presented_mode: str = "witness",
    confidence: float = 0.9,
    confidence_label: str = "high",
    requires_reviewer_confirm: bool = False,
) -> ModeResult:
    return ModeResult(
        presented_mode=presented_mode,
        confidence=confidence,
        confidence_label=confidence_label,
        formal_submode="none",
        signals=[],
        requires_reviewer_confirm=requires_reviewer_confirm,
        notes=None,
    )


def _persuasion(
    heat_level: str = "low",
    heat_score: float = 0.0,
    is_clean_candidate: bool = True,
    detector_count: int = 0,
) -> PersuasionResult:
    return PersuasionResult(
        heat_level=heat_level,
        heat_score=heat_score,
        signals=[],
        is_clean_candidate=is_clean_candidate,
        detector_count=detector_count,
    )


# ── Rule 1: Uncertain mode override ─────────────────────────────────

class TestRule1UncertainMode:
    def test_uncertain_mode_escalates_to_reviewer(self):
        result = evaluate_escalation(
            mode_result=_mode(presented_mode="uncertain", confidence_label="low"),
            persuasion_result=_persuasion(heat_level="low"),
        )
        assert result.level in {"reviewer", "full"}
        assert "uncertain_mode" in result.trigger_reasons

    def test_uncertain_mode_blocks_offramp(self):
        result = evaluate_escalation(
            mode_result=_mode(presented_mode="uncertain", confidence_label="low"),
            persuasion_result=_persuasion(heat_level="low"),
        )
        assert result.offramp_permitted_by_policy is False


# ── Rule 2: High heat override ──────────────────────────────────────

class TestRule2HighHeat:
    def test_high_heat_escalates_to_reviewer(self):
        result = evaluate_escalation(
            mode_result=_mode(confidence_label="high"),
            persuasion_result=_persuasion(heat_level="high", is_clean_candidate=False),
        )
        assert result.level in {"reviewer", "full"}
        assert "high_heat" in result.trigger_reasons

    def test_high_heat_blocks_offramp(self):
        result = evaluate_escalation(
            mode_result=_mode(confidence_label="high"),
            persuasion_result=_persuasion(heat_level="high", is_clean_candidate=False),
        )
        assert result.offramp_permitted_by_policy is False


# ── Rule 3: Clean path eligibility ──────────────────────────────────

class TestRule3CleanPath:
    def test_clean_path_offramp_permitted(self):
        result = evaluate_escalation(
            mode_result=_mode(
                confidence_label="high",
                requires_reviewer_confirm=False,
            ),
            persuasion_result=_persuasion(
                heat_level="low",
                is_clean_candidate=True,
            ),
        )
        assert result.level == "none"
        assert result.offramp_permitted_by_policy is True
        assert result.trigger_reasons == []

    def test_clean_path_requires_high_confidence(self):
        result = evaluate_escalation(
            mode_result=_mode(
                confidence_label="medium",
                requires_reviewer_confirm=True,
            ),
            persuasion_result=_persuasion(
                heat_level="low",
                is_clean_candidate=True,
            ),
        )
        assert result.offramp_permitted_by_policy is False

    def test_clean_path_requires_clean_candidate(self):
        result = evaluate_escalation(
            mode_result=_mode(
                confidence_label="high",
                requires_reviewer_confirm=False,
            ),
            persuasion_result=_persuasion(
                heat_level="low",
                is_clean_candidate=False,
            ),
        )
        assert result.offramp_permitted_by_policy is False


# ── Rule 4: Low confidence + moderate heat ───────────────────────────

class TestRule4LowConfModerateHeat:
    def test_low_confidence_moderate_heat_is_reviewer(self):
        result = evaluate_escalation(
            mode_result=_mode(confidence_label="low"),
            persuasion_result=_persuasion(
                heat_level="moderate",
                is_clean_candidate=False,
            ),
        )
        assert result.level == "reviewer"
        assert "low_confidence_moderate_heat" in result.trigger_reasons

    def test_low_confidence_moderate_heat_is_NOT_full(self):
        """Explicit test: this gray zone must not trigger full."""
        result = evaluate_escalation(
            mode_result=_mode(confidence_label="low"),
            persuasion_result=_persuasion(
                heat_level="moderate",
                is_clean_candidate=False,
            ),
        )
        assert result.level != "full"


# ── Rule 5: Scanner contradiction override ───────────────────────────

class TestRule5ScannerContradiction:
    def test_low_heat_not_clean_escalates(self):
        result = evaluate_escalation(
            mode_result=_mode(confidence_label="high"),
            persuasion_result=_persuasion(
                heat_level="low",
                is_clean_candidate=False,
            ),
        )
        assert result.level in {"reviewer", "full"}
        assert "scanner_contradiction" in result.trigger_reasons

    def test_scanner_contradiction_blocks_offramp(self):
        result = evaluate_escalation(
            mode_result=_mode(confidence_label="high"),
            persuasion_result=_persuasion(
                heat_level="low",
                is_clean_candidate=False,
            ),
        )
        assert result.offramp_permitted_by_policy is False


# ── Rule 6: Reviewer confirmation required ───────────────────────────

class TestRule6ReviewerConfirm:
    def test_reviewer_confirm_escalates(self):
        result = evaluate_escalation(
            mode_result=_mode(
                confidence_label="medium",
                requires_reviewer_confirm=True,
            ),
            persuasion_result=_persuasion(heat_level="low"),
        )
        assert result.level in {"reviewer", "full"}
        assert "reviewer_confirm_required" in result.trigger_reasons


# ── Rule 7: Low confidence + high heat ───────────────────────────────

class TestRule7LowConfHighHeat:
    def test_low_confidence_high_heat_is_full(self):
        result = evaluate_escalation(
            mode_result=_mode(confidence_label="low"),
            persuasion_result=_persuasion(
                heat_level="high",
                is_clean_candidate=False,
            ),
        )
        assert result.level == "full"
        assert "low_confidence_high_heat" in result.trigger_reasons

    def test_low_confidence_high_heat_blocks_offramp(self):
        result = evaluate_escalation(
            mode_result=_mode(confidence_label="low"),
            persuasion_result=_persuasion(
                heat_level="high",
                is_clean_candidate=False,
            ),
        )
        assert result.offramp_permitted_by_policy is False


# ── precedence: highest-escalation-wins ──────────────────────────────

class TestPrecedence:
    def test_uncertain_plus_high_heat_at_least_reviewer(self):
        result = evaluate_escalation(
            mode_result=_mode(
                presented_mode="uncertain",
                confidence_label="low",
            ),
            persuasion_result=_persuasion(
                heat_level="high",
                is_clean_candidate=False,
            ),
        )
        assert result.level == "full"
        assert "uncertain_mode" in result.trigger_reasons
        assert "high_heat" in result.trigger_reasons
        assert "low_confidence_high_heat" in result.trigger_reasons

    def test_multiple_reviewer_rules_stay_reviewer(self):
        result = evaluate_escalation(
            mode_result=_mode(
                confidence_label="medium",
                requires_reviewer_confirm=True,
            ),
            persuasion_result=_persuasion(
                heat_level="low",
                is_clean_candidate=False,
            ),
        )
        assert result.level == "reviewer"
        assert "scanner_contradiction" in result.trigger_reasons
        assert "reviewer_confirm_required" in result.trigger_reasons


# ── traceability ─────────────────────────────────────────────────────

class TestTraceability:
    def test_trigger_reasons_preserved(self):
        result = evaluate_escalation(
            mode_result=_mode(
                presented_mode="uncertain",
                confidence_label="low",
            ),
            persuasion_result=_persuasion(
                heat_level="high",
                is_clean_candidate=False,
            ),
        )
        assert len(result.trigger_reasons) >= 2

    def test_no_duplicate_reasons(self):
        result = evaluate_escalation(
            mode_result=_mode(
                presented_mode="uncertain",
                confidence_label="low",
            ),
            persuasion_result=_persuasion(
                heat_level="high",
                is_clean_candidate=False,
            ),
        )
        assert len(result.trigger_reasons) == len(set(result.trigger_reasons))

    def test_clean_path_has_no_reasons(self):
        result = evaluate_escalation(
            mode_result=_mode(
                confidence_label="high",
                requires_reviewer_confirm=False,
            ),
            persuasion_result=_persuasion(
                heat_level="low",
                is_clean_candidate=True,
            ),
        )
        assert result.trigger_reasons == []


# ── output contract ──────────────────────────────────────────────────

class TestOutputContract:
    def test_result_type(self):
        result = evaluate_escalation(
            mode_result=_mode(),
            persuasion_result=_persuasion(),
        )
        assert isinstance(result, EscalationDecision)

    def test_level_valid_values(self):
        result = evaluate_escalation(
            mode_result=_mode(),
            persuasion_result=_persuasion(),
        )
        assert result.level in {"none", "reviewer", "full"}

    def test_accepts_audit_result_param(self):
        result = evaluate_escalation(
            mode_result=_mode(),
            persuasion_result=_persuasion(),
            audit_result=None,
        )
        assert isinstance(result, EscalationDecision)
