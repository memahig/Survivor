#!/usr/bin/env python3
"""
FILE: engine/analysis/peg.py
VERSION: 1.0
PURPOSE: Build a Persuasion-Evidence Gap (PEG) profile from reader_interpretation
         mechanism blocks and load_bearing fragility. This is a post-interpretation
         consumer — it does NOT re-derive signals.

         PEG identifies the structural condition where persuasive force exceeds
         evidentiary support. See human/peg_doctrine.md for the locked doctrine.

AUTHORITATIVE SOURCES (consume only):
    reader_interpretation["mechanism_blocks"]  — what mechanisms fired
    load_bearing["argument_fragility"]         — structural fragility

DO NOT re-derive: omissions, causal signals, scope inflation, fragility,
                  or mechanism presence. Those are reader_interpretation's job.

RULES: pure, deterministic, no I/O, fail-closed.
"""

from __future__ import annotations

from typing import Any, Dict, List


# ---- PEG Label Ladder (locked) ----
#
# minimal  — no significant persuasion-evidence mismatch detected
# notable  — some propaganda-style patterns are present, but the full structure is not established
# severe   — multiple mechanisms active; persuasive force materially exceeds evidence
# critical — propaganda-patterned structure; argument depends on mechanisms, not evidence
#
# Level is driven by CORE mechanism count + structural conditions.
# Classification labels do NOT escalate PEG level.
# The label ladder does NOT use numerical scores.

# Core mechanisms — structural persuasion patterns with high diagnostic weight
_CORE_MECHANISMS = frozenset({
    "scope_inflation",
    "omission_dependence",
    "unsupported_causal",
    "framing_escalation",
    "load_bearing_weakness",
})

# Secondary mechanisms — weaker signals, do not drive critical/severe alone
_SECONDARY_MECHANISMS = frozenset({
    "official_reliance",
    "baseline_absence",
})

# Priority order for peg_line rendering (top mechanisms first, max 3 shown)
_MECHANISM_PRIORITY = [
    "omission_dependence",
    "unsupported_causal",
    "load_bearing_weakness",
    "framing_escalation",
    "scope_inflation",
    "official_reliance",
    "baseline_absence",
]

_MECHANISM_LABELS = {
    "scope_inflation": "scope inflation",
    "omission_dependence": "omitted rival explanations",
    "unsupported_causal": "unsupported causal claims",
    "framing_escalation": "escalating framing",
    "load_bearing_weakness": "load-bearing weakness",
    "official_reliance": "overreliance on official assertions",
    "baseline_absence": "baseline-absent statistics",
}


def _sd(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _sl(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _s(x: Any) -> str:
    return str(x or "").strip()


def _join_mechanisms(items: List[str]) -> str:
    """Join mechanism names with proper grammar."""
    if len(items) == 0:
        return "structural mechanisms"
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _top_mechanism_names(active_mechanisms: List[str], max_show: int = 3) -> List[str]:
    """Return the top N mechanism labels in priority order."""
    priority_map = {m: i for i, m in enumerate(_MECHANISM_PRIORITY)}
    sorted_mechs = sorted(
        active_mechanisms,
        key=lambda m: priority_map.get(m, len(_MECHANISM_PRIORITY)),
    )
    return [_MECHANISM_LABELS.get(m, m) for m in sorted_mechs[:max_show]]


# All known PEG mechanisms — fail-closed: unknown strings are ignored and never
# enter active_mechanisms, counts, or rendered output.
_KNOWN_MECHANISMS = _CORE_MECHANISMS | _SECONDARY_MECHANISMS


def _extract_unique_mechanisms(blocks: List[Any]) -> List[str]:
    """Extract known mechanism names only, preserving order and deduplicating."""
    seen: set[str] = set()
    result: List[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        mech = _s(block.get("mechanism"))
        if mech in _KNOWN_MECHANISMS and mech not in seen:
            seen.add(mech)
            result.append(mech)
    return result


def build_peg_profile(enriched: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a PEG profile from enriched substrate.

    Consumes only:
        enriched["reader_interpretation"]["mechanism_blocks"]
        enriched["load_bearing"]["argument_fragility"]

    Returns:
        {
            "peg_level": str,               # minimal | notable | severe | critical
            "mechanism_count": int,
            "core_count": int,
            "secondary_count": int,
            "active_mechanisms": [str, ...],
            "fragility": str,
            "tilt_active": bool,            # load-bearing gap at argument core
            "fragility_sensitivity": bool,  # fragility + omission dependence
            "peg_line": str,                # structural summary sentence
        }
    """
    if not isinstance(enriched, dict):
        return _unavailable_profile()

    # ---- Check reader_interpretation health ----
    interp = enriched.get("reader_interpretation")
    if not isinstance(interp, dict) or "error" in interp:
        return _unavailable_profile()

    blocks = _sl(interp.get("mechanism_blocks"))

    # ---- Load-bearing fragility (from load_bearing module) ----
    lb = _sd(enriched.get("load_bearing"))
    fragility = _s(lb.get("argument_fragility")) or "unknown"

    # ---- Active mechanisms (ordered-unique from blocks) ----
    active_mechanisms = _extract_unique_mechanisms(blocks)
    mechanism_count = len(active_mechanisms)
    core_count = sum(1 for m in active_mechanisms if m in _CORE_MECHANISMS)
    secondary_count = sum(1 for m in active_mechanisms if m in _SECONDARY_MECHANISMS)

    # ---- The Tilt: load-bearing priority ----
    tilt_active = "load_bearing_weakness" in active_mechanisms

    # ---- Fragility Sensitivity Principle ----
    high_fragility = fragility == "high"
    has_omission_dependence = "omission_dependence" in active_mechanisms
    fragility_sensitivity = high_fragility and has_omission_dependence

    # ---- PEG level determination (core mechanisms drive thresholds) ----
    peg_level = _determine_level(
        core_count=core_count,
        secondary_count=secondary_count,
        tilt_active=tilt_active,
        fragility_sensitivity=fragility_sensitivity,
        high_fragility=high_fragility,
    )

    # ---- PEG line (structural summary, top 3 mechanisms) ----
    peg_line = _build_peg_line(
        peg_level=peg_level,
        active_mechanisms=active_mechanisms,
    )

    return {
        "peg_level": peg_level,
        "mechanism_count": mechanism_count,
        "core_count": core_count,
        "secondary_count": secondary_count,
        "active_mechanisms": active_mechanisms,
        "fragility": fragility,
        "tilt_active": tilt_active,
        "fragility_sensitivity": fragility_sensitivity,
        "peg_line": peg_line,
    }


def _determine_level(
    *,
    core_count: int,
    secondary_count: int,
    tilt_active: bool,
    fragility_sensitivity: bool,
    high_fragility: bool,
) -> str:
    """
    Map structural signals to PEG level.

    Only CORE mechanisms drive critical/severe. Classification labels
    do NOT escalate PEG level — only structural conditions matter.

    Rules (evaluated top-down, first match wins):
    1. critical: core_count >= 3 AND (tilt OR fragility_sensitivity)
    2. severe:   core_count >= 2 AND (tilt OR high_fragility)
    3. severe:   core_count >= 3
    4. notable:  core_count >= 1
    5. notable:  secondary_count >= 2 AND high_fragility
    6. minimal:  otherwise
    """
    # critical
    if core_count >= 3 and (tilt_active or fragility_sensitivity):
        return "critical"

    # severe
    if core_count >= 2 and (tilt_active or high_fragility):
        return "severe"
    if core_count >= 3:
        return "severe"

    # notable
    if core_count >= 1:
        return "notable"
    if secondary_count >= 2 and high_fragility:
        return "notable"

    # minimal
    return "minimal"


def _build_peg_line(
    *,
    peg_level: str,
    active_mechanisms: List[str],
) -> str:
    """Build a single-sentence structural summary for the PEG profile.

    Uses only the top 3 mechanisms in priority order.
    """
    if peg_level == "minimal":
        return "No significant persuasion-evidence gap detected."

    top = _top_mechanism_names(active_mechanisms, max_show=3)
    mech_str = _join_mechanisms(top)

    if peg_level == "critical":
        return (
            f"This argument heavily relies on elements commonly used in "
            f"propaganda-style persuasion, especially {mech_str}. "
            f"At key points, the argument depends more on persuasive structure "
            f"than on fully demonstrated evidence."
        )

    if peg_level == "severe":
        return (
            f"This argument relies on several elements often used in "
            f"propaganda-style persuasion, especially {mech_str}. "
            f"These elements increase persuasive force beyond what the evidence "
            f"fully supports."
        )

    return (
        f"This argument includes some elements sometimes used in "
        f"propaganda-style persuasion, especially {mech_str}. "
        f"In those parts, persuasive force may run ahead of the evidence."
    )


def _unavailable_profile() -> Dict[str, Any]:
    """Return when reader_interpretation failed or input is invalid."""
    return {
        "peg_level": "unknown",
        "mechanism_count": 0,
        "core_count": 0,
        "secondary_count": 0,
        "active_mechanisms": [],
        "fragility": "unknown",
        "tilt_active": False,
        "fragility_sensitivity": False,
        "peg_line": "PEG profile unavailable because interpretation failed.",
    }
