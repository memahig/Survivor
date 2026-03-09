"""
FILE: engine/analysis/evaluation_planner.py
VERSION: 0.1.0
PURPOSE:
Evaluation Planner (L5B) for the Epistemic Evaluation Engine.

Deterministic planner that translates L2 (Mode) and L5A (Escalation)
outputs into a structured EvaluationPlan — the "mission brief" for
downstream layers.

CONSTRAINTS:
- Deterministic only. No AI.
- No execution routing. No module imports.
- No policy recalculation.
- Capability strings only.

BLUEPRINT: ARCHITECTURE_BLUEPRINT_v0.2 — Layer L5B.
LOGIC BLUEPRINT: STAGE4_LOGIC_BLUEPRINT.md
BUILD MANIFEST: Stage 4 — Evaluation Planner.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.analysis.escalation_policy import EscalationDecision
from engine.core.mode_types import ModeResult


# ── data types ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class EvaluationPlan:
    """Output of the evaluation planner (L5B)."""
    presented_mode: str
    escalation_level: str                          # none | reviewer | full
    offramp_permitted_by_policy: bool
    stop_early_allowed: bool
    authorized_baseline_audits: list[str] = field(default_factory=list)
    authorized_deep_modules: list[str] = field(default_factory=list)
    requires_functional_review: bool = False
    requires_full_arbitration: bool = False
    source_signals: list[dict] = field(default_factory=list)
    reasoning_summary: str = ""


# ── public API ───────────────────────────────────────────────────────

def build_evaluation_plan(
    mode_result: ModeResult,
    escalation_decision: EscalationDecision,
) -> EvaluationPlan:
    """Build an EvaluationPlan from L2 and L5A outputs.

    Args:
        mode_result:         Stage 1 ModeResult (full object, Rule 9B).
        escalation_decision: Stage 3 EscalationDecision from L5A.

    Returns:
        EvaluationPlan with authorized capabilities and traceability.
    """
    level = escalation_decision.level
    mode = mode_result.presented_mode

    # ── Rule A: Mode-specific baseline audit ────────────────────
    baseline = f"{mode}_baseline"

    # ── Authorization matrix ────────────────────────────────────
    deep_modules: list[str] = []
    functional_review = False
    full_arbitration = False

    if level == "reviewer":
        deep_modules = ["functional_mode_review"]
        functional_review = True

    elif level == "full":
        deep_modules = ["functional_mode_review", "survivor_arbitration"]
        functional_review = True
        full_arbitration = True

    # ── Rule B: Stop-early gate (two gates) ─────────────────────
    stop_early = (
        escalation_decision.offramp_permitted_by_policy
        and level == "none"
    )

    # ── Rule D: Source signals preservation ─────────────────────
    signals: list[dict] = []

    for s in mode_result.signals:
        signals.append({
            "layer": "L2",
            "signal_name": s.name,
            "weight": s.weight,
        })

    for reason in escalation_decision.trigger_reasons:
        signals.append({
            "layer": "L5A",
            "signal_name": reason,
            "weight": 0.0,
        })

    # ── Rule E: Reasoning summary ───────────────────────────────
    summary = _build_reasoning(mode, level, stop_early)

    return EvaluationPlan(
        presented_mode=mode,
        escalation_level=level,
        offramp_permitted_by_policy=escalation_decision.offramp_permitted_by_policy,
        stop_early_allowed=stop_early,
        authorized_baseline_audits=[baseline],
        authorized_deep_modules=deep_modules,
        requires_functional_review=functional_review,
        requires_full_arbitration=full_arbitration,
        source_signals=signals,
        reasoning_summary=summary,
    )


# ── internal helpers ─────────────────────────────────────────────────

def _build_reasoning(mode: str, level: str, stop_early: bool) -> str:
    """Deterministic, concise reasoning string."""
    if stop_early:
        return f"Clean path: {mode} mode, no escalation, early stop permitted."
    if level == "none":
        return f"Baseline only: {mode} mode, no escalation, early stop blocked by policy."
    if level == "reviewer":
        return f"Reviewer: {mode} mode, single-model interpretive pass authorized."
    if level == "full":
        return f"Full: {mode} mode, multi-model arbitration authorized."
    return f"Plan: {mode} mode, escalation level {level}."
