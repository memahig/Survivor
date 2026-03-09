"""
FILE: engine/analysis/escalation_policy.py
VERSION: 0.1.0
PURPOSE:
Escalation policy (L5A) for the Epistemic Evaluation Engine.

Deterministic governor that translates L2 (Mode) and L3 (Scanner) outputs
into an escalation level. L5A is a governor, not an executor.

CONSTRAINTS:
- Deterministic only. No AI.
- No module lists. No execution routing.
- No quality verdict. No motive inference.
- Highest-escalation-wins precedence.

BLUEPRINT: ARCHITECTURE_BLUEPRINT_v0.2 — Layer L5A.
LOGIC BLUEPRINT: STAGE3_LOGIC_BLUEPRINT.md
BUILD MANIFEST: Stage 3 — Escalation Policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.analysis.persuasion_screen import PersuasionResult
from engine.core.mode_types import ModeResult


# ── escalation ordering ──────────────────────────────────────────────

_LEVEL_ORDER = {"none": 0, "reviewer": 1, "full": 2}


# ── data types ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class EscalationDecision:
    """Output of the escalation policy (L5A)."""
    level: str                          # none | reviewer | full
    trigger_reasons: list[str] = field(default_factory=list)
    offramp_permitted_by_policy: bool = True


# ── public API ───────────────────────────────────────────────────────

def evaluate_escalation(
    mode_result: ModeResult,
    persuasion_result: PersuasionResult,
    audit_result: Optional[object] = None,
) -> EscalationDecision:
    """Determine escalation level from L2 and L3 outputs.

    Args:
        mode_result:       Stage 1 ModeResult (full object, Rule 9B).
        persuasion_result: Stage 2 PersuasionResult.
        audit_result:      Future L4 AuditResult (not used in Stage 3).

    Returns:
        EscalationDecision with level, trigger_reasons, and offramp status.
    """
    level = "none"
    reasons: list[str] = []

    # ── Rule 1: Uncertain mode override ──────────────────────────
    if mode_result.presented_mode == "uncertain":
        level = _raise_level(level, "reviewer")
        reasons.append("uncertain_mode")

    # ── Rule 2: High heat override ───────────────────────────────
    if persuasion_result.heat_level == "high":
        level = _raise_level(level, "reviewer")
        reasons.append("high_heat")

    # ── Rule 3: Clean path eligibility ───────────────────────────
    # No escalation is raised here. This rule is reflected in
    # offramp_permitted_by_policy.

    # ── Rule 4: Low confidence + moderate heat ───────────────────
    if (mode_result.confidence_label == "low"
            and persuasion_result.heat_level == "moderate"):
        level = _raise_level(level, "reviewer")
        reasons.append("low_confidence_moderate_heat")

    # ── Rule 5: Scanner contradiction override ───────────────────
    if (persuasion_result.heat_level == "low"
            and not persuasion_result.is_clean_candidate):
        level = _raise_level(level, "reviewer")
        reasons.append("scanner_contradiction")

    # ── Rule 6: Reviewer confirmation required ───────────────────
    if mode_result.requires_reviewer_confirm:
        level = _raise_level(level, "reviewer")
        reasons.append("reviewer_confirm_required")

    # ── Rule 7: Low confidence + high heat ───────────────────────
    if (mode_result.confidence_label == "low"
            and persuasion_result.heat_level == "high"):
        level = _raise_level(level, "full")
        reasons.append("low_confidence_high_heat")

    # ── Deduplicate trigger reasons (preserve order) ─────────────
    reasons = list(dict.fromkeys(reasons))

    # ── Off-ramp determination (Rule 3 reflected here) ───────────
    offramp = (
        level == "none"
        and mode_result.confidence_label == "high"
        and persuasion_result.heat_level == "low"
        and persuasion_result.is_clean_candidate
    )

    return EscalationDecision(
        level=level,
        trigger_reasons=reasons,
        offramp_permitted_by_policy=offramp,
    )


# ── internal helpers ─────────────────────────────────────────────────

def _raise_level(current: str, candidate: str) -> str:
    """Highest-escalation-wins."""
    if _LEVEL_ORDER.get(candidate, 0) > _LEVEL_ORDER.get(current, 0):
        return candidate
    return current
