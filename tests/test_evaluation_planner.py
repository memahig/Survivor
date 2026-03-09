"""
FILE: tests/test_evaluation_planner.py
VERSION: 0.1.0
PURPOSE:
Tests for the evaluation planner (L5B).

BUILD MANIFEST: Stage 4 — Evaluation Planner.
"""

import pytest

from engine.analysis.evaluation_planner import (
    EvaluationPlan,
    build_evaluation_plan,
)
from engine.analysis.escalation_policy import EscalationDecision
from engine.core.mode_types import ModeResult, ModeSignal


# ── test helpers ─────────────────────────────────────────────────────

def _mode(
    presented_mode: str = "witness",
    confidence: float = 0.9,
    confidence_label: str = "high",
    requires_reviewer_confirm: bool = False,
    signals: list | None = None,
) -> ModeResult:
    return ModeResult(
        presented_mode=presented_mode,
        confidence=confidence,
        confidence_label=confidence_label,
        formal_submode="none",
        signals=signals or [],
        requires_reviewer_confirm=requires_reviewer_confirm,
        notes=None,
    )


def _escalation(
    level: str = "none",
    trigger_reasons: list | None = None,
    offramp_permitted_by_policy: bool = True,
) -> EscalationDecision:
    return EscalationDecision(
        level=level,
        trigger_reasons=trigger_reasons or [],
        offramp_permitted_by_policy=offramp_permitted_by_policy,
    )


# ── Authorization matrix: none ───────────────────────────────────────

class TestAuthorizationNone:
    def test_none_baseline_audit_for_witness(self):
        plan = build_evaluation_plan(
            mode_result=_mode(presented_mode="witness"),
            escalation_decision=_escalation(level="none", offramp_permitted_by_policy=True),
        )
        assert plan.authorized_baseline_audits == ["witness_baseline"]

    def test_none_no_deep_modules(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="none"),
        )
        assert plan.authorized_deep_modules == []

    def test_none_no_functional_review(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="none"),
        )
        assert plan.requires_functional_review is False

    def test_none_no_full_arbitration(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="none"),
        )
        assert plan.requires_full_arbitration is False

    def test_none_stop_early_when_policy_permits(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(
                level="none",
                offramp_permitted_by_policy=True,
            ),
        )
        assert plan.stop_early_allowed is True

    def test_none_stop_early_blocked_when_policy_denies(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(
                level="none",
                offramp_permitted_by_policy=False,
            ),
        )
        assert plan.stop_early_allowed is False


# ── Authorization matrix: reviewer ───────────────────────────────────

class TestAuthorizationReviewer:
    def test_reviewer_baseline_audit_for_mode(self):
        plan = build_evaluation_plan(
            mode_result=_mode(presented_mode="argument"),
            escalation_decision=_escalation(level="reviewer"),
        )
        assert plan.authorized_baseline_audits == ["argument_baseline"]

    def test_reviewer_deep_modules(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="reviewer"),
        )
        assert plan.authorized_deep_modules == ["functional_mode_review"]

    def test_reviewer_requires_functional_review(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="reviewer"),
        )
        assert plan.requires_functional_review is True

    def test_reviewer_no_full_arbitration(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="reviewer"),
        )
        assert plan.requires_full_arbitration is False

    def test_reviewer_stop_early_always_false(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(
                level="reviewer",
                offramp_permitted_by_policy=True,
            ),
        )
        assert plan.stop_early_allowed is False


# ── Authorization matrix: full ───────────────────────────────────────

class TestAuthorizationFull:
    def test_full_baseline_audit_for_mode(self):
        plan = build_evaluation_plan(
            mode_result=_mode(presented_mode="explanation"),
            escalation_decision=_escalation(level="full"),
        )
        assert plan.authorized_baseline_audits == ["explanation_baseline"]

    def test_full_deep_modules_ordered(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="full"),
        )
        assert plan.authorized_deep_modules == [
            "functional_mode_review",
            "survivor_arbitration",
        ]

    def test_full_requires_functional_review(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="full"),
        )
        assert plan.requires_functional_review is True

    def test_full_requires_full_arbitration(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="full"),
        )
        assert plan.requires_full_arbitration is True

    def test_full_stop_early_always_false(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(
                level="full",
                offramp_permitted_by_policy=True,
            ),
        )
        assert plan.stop_early_allowed is False


# ── Rule C: Escalation level passthrough ─────────────────────────────

class TestPassthrough:
    def test_level_passes_through_none(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="none"),
        )
        assert plan.escalation_level == "none"

    def test_level_passes_through_reviewer(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="reviewer"),
        )
        assert plan.escalation_level == "reviewer"

    def test_level_passes_through_full(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="full"),
        )
        assert plan.escalation_level == "full"


# ── Rule A: Wrong-mode protection ────────────────────────────────────

class TestWrongModeProtection:
    def test_argument_mode_gets_argument_baseline(self):
        plan = build_evaluation_plan(
            mode_result=_mode(presented_mode="argument"),
            escalation_decision=_escalation(level="none"),
        )
        assert plan.authorized_baseline_audits == ["argument_baseline"]
        assert "witness_baseline" not in plan.authorized_baseline_audits

    def test_proof_mode_gets_proof_baseline(self):
        plan = build_evaluation_plan(
            mode_result=_mode(presented_mode="proof"),
            escalation_decision=_escalation(level="reviewer"),
        )
        assert plan.authorized_baseline_audits == ["proof_baseline"]
        assert "witness_baseline" not in plan.authorized_baseline_audits

    def test_each_mode_gets_own_baseline(self):
        for mode in ["witness", "proof", "rule", "explanation", "argument",
                      "experience", "record", "voice", "formal", "uncertain"]:
            plan = build_evaluation_plan(
                mode_result=_mode(presented_mode=mode),
                escalation_decision=_escalation(level="none"),
            )
            assert plan.authorized_baseline_audits == [f"{mode}_baseline"]


# ── Rule D: Source signals ───────────────────────────────────────────

class TestSourceSignals:
    def test_l2_signals_included(self):
        signals = [
            ModeSignal(name="attribution_count", weight=0.8, evidence="3 attributions"),
            ModeSignal(name="quote_density", weight=0.6, evidence="high"),
        ]
        plan = build_evaluation_plan(
            mode_result=_mode(signals=signals),
            escalation_decision=_escalation(level="none"),
        )
        l2_entries = [s for s in plan.source_signals if s["layer"] == "L2"]
        assert len(l2_entries) == 2
        assert l2_entries[0]["signal_name"] == "attribution_count"
        assert l2_entries[0]["weight"] == 0.8
        assert l2_entries[1]["signal_name"] == "quote_density"
        assert l2_entries[1]["weight"] == 0.6

    def test_l5a_trigger_reasons_included(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(
                level="reviewer",
                trigger_reasons=["high_heat", "scanner_contradiction"],
            ),
        )
        l5a_entries = [s for s in plan.source_signals if s["layer"] == "L5A"]
        assert len(l5a_entries) == 2
        assert l5a_entries[0]["signal_name"] == "high_heat"
        assert l5a_entries[0]["weight"] == 0.0
        assert l5a_entries[1]["signal_name"] == "scanner_contradiction"
        assert l5a_entries[1]["weight"] == 0.0

    def test_source_signals_flat_list(self):
        signals = [ModeSignal(name="sig1", weight=0.5, evidence="e1")]
        plan = build_evaluation_plan(
            mode_result=_mode(signals=signals),
            escalation_decision=_escalation(
                level="reviewer",
                trigger_reasons=["uncertain_mode"],
            ),
        )
        assert isinstance(plan.source_signals, list)
        for entry in plan.source_signals:
            assert isinstance(entry, dict)
            assert "layer" in entry
            assert "signal_name" in entry
            assert "weight" in entry

    def test_empty_signals_when_no_upstream(self):
        plan = build_evaluation_plan(
            mode_result=_mode(signals=[]),
            escalation_decision=_escalation(level="none", trigger_reasons=[]),
        )
        assert plan.source_signals == []


# ── Rule E: Reasoning summary ────────────────────────────────────────

class TestReasoningSummary:
    def test_reasoning_non_empty(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="none"),
        )
        assert plan.reasoning_summary != ""
        assert len(plan.reasoning_summary) > 0

    def test_clean_path_reasoning(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(
                level="none",
                offramp_permitted_by_policy=True,
            ),
        )
        assert "witness" in plan.reasoning_summary.lower()

    def test_reviewer_reasoning(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="reviewer"),
        )
        assert "reviewer" in plan.reasoning_summary.lower()

    def test_full_reasoning(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(level="full"),
        )
        assert "full" in plan.reasoning_summary.lower()


# ── Output contract ──────────────────────────────────────────────────

class TestOutputContract:
    def test_result_type(self):
        plan = build_evaluation_plan(
            mode_result=_mode(),
            escalation_decision=_escalation(),
        )
        assert isinstance(plan, EvaluationPlan)

    def test_escalation_level_valid_values(self):
        for level in ["none", "reviewer", "full"]:
            plan = build_evaluation_plan(
                mode_result=_mode(),
                escalation_decision=_escalation(level=level),
            )
            assert plan.escalation_level in {"none", "reviewer", "full"}
