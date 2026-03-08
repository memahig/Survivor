#!/usr/bin/env python3
"""
FILE: engine/analysis/epistemic_success.py
VERSION: 1.1
PURPOSE:
Build an Epistemic Success Profile (ESM) to identify structural integrity
and rigor. Operates in parallel with PEG.

DOCTRINE:
    1. Symmetry: Success signals must be as granular as persuasion signals.
    2. Non-Compensability: Integrity work does NOT erase structural PEG findings.
    3. Domain-Routing: Success is defined partly by the object's genre
       (Legal, Scientific, Journalism, Advocacy), but routing is informational
       and does not yet re-weight the score.
    4. Fail-Closed: Unknown success mechanisms are ignored.
    5. Mechanism-Based Reporting: Report concrete integrity signals, not vibes.

CONSUMES:
    enriched["success_blocks"]                              (primary; produced by SSD)
    enriched["reader_interpretation"]["success_blocks"]     (fallback only)
    enriched["adjudicated_whole_article_judgment"]["classification"]

RULES: pure, deterministic, no I/O, fail-closed.
"""

from __future__ import annotations

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Success tiers (locked)
# ---------------------------------------------------------------------------

# Deep rigor — hard-to-fake, high-labor integrity signals
_DEEP_RIGOR = frozenset({
    "adverse_fact_inclusion",     # Including facts that complicate the thesis
    "steel_manning",              # Strongest rival case presented recognizably
    "uncertainty_visibility",     # Explicitly naming "known unknowns"
    "assumption_externalization", # Naming the ideological/theoretical lens
})

# Structural rigor — disciplined reasoning and calibration
_STRUCTURAL_RIGOR = frozenset({
    "proportional_hedging",       # Certainty mirrors evidence strength
    "causal_transparency",        # Explicit step-by-step derivation
    "scope_discipline",           # Refusing to over-extrapolate
    "comparative_grounding",      # Testing uniqueness against baselines
})

# All known success mechanisms — fail-closed boundary
_ALL_SUCCESS_SIGNALS = _DEEP_RIGOR | _STRUCTURAL_RIGOR


# ---------------------------------------------------------------------------
# Domain routing (informational, not score-altering yet)
# ---------------------------------------------------------------------------

_DOMAIN_PRIORITY = {
    "scientific": ["uncertainty_visibility", "causal_transparency"],
    "legal": ["comparative_grounding", "scope_discipline"],
    "advocacy": ["steel_manning", "comparative_grounding"],
    "journalism": ["adverse_fact_inclusion", "uncertainty_visibility"],
    "general": [],
}


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

_SUCCESS_PRIORITY = [
    "adverse_fact_inclusion",
    "steel_manning",
    "uncertainty_visibility",
    "assumption_externalization",
    "proportional_hedging",
    "causal_transparency",
    "scope_discipline",
    "comparative_grounding",
]

_SUCCESS_LABELS = {
    "adverse_fact_inclusion": "inclusion of adverse facts",
    "steel_manning": "substantive counter-narrative engagement",
    "uncertainty_visibility": "explicit uncertainty visibility",
    "assumption_externalization": "externalized assumptions",
    "proportional_hedging": "proportional hedging",
    "causal_transparency": "causal transparency",
    "scope_discipline": "disciplined scope",
    "comparative_grounding": "comparative grounding",
}


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def _sd(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _sl(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _s(x: Any) -> str:
    return str(x or "").strip()


def _join_labels(items: List[str]) -> str:
    if len(items) == 0:
        return "integrity-strengthening mechanisms"
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _extract_valid_successes(blocks: Any) -> List[str]:
    """Extract known success mechanisms only, preserving order and deduplicating."""
    seen: set[str] = set()
    result: List[str] = []

    for block in _sl(blocks):
        if not isinstance(block, dict):
            continue
        mech = _s(block.get("mechanism"))
        if mech in _ALL_SUCCESS_SIGNALS and mech not in seen:
            seen.add(mech)
            result.append(mech)

    return result


def _top_success_labels(active_successes: List[str], max_show: int = 3) -> List[str]:
    priority_map = {m: i for i, m in enumerate(_SUCCESS_PRIORITY)}
    sorted_mechs = sorted(
        active_successes,
        key=lambda m: priority_map.get(m, len(_SUCCESS_PRIORITY)),
    )
    return [_SUCCESS_LABELS.get(m, m) for m in sorted_mechs[:max_show]]


def _domain_priority_hits(active_successes: List[str], object_type: str) -> List[str]:
    expected = _DOMAIN_PRIORITY.get(object_type, [])
    return [m for m in active_successes if m in expected]


# ---------------------------------------------------------------------------
# Level determination
# ---------------------------------------------------------------------------

def _determine_success_level(deep_count: int, structural_count: int) -> str:
    """
    Evaluate the volume of integrity work.

    Rules:
    1. exceptional: deep >= 2 and structural >= 2
    2. high:        deep >= 1 or structural >= 3
    3. notable:     structural >= 1
    4. minimal:     otherwise
    """
    if deep_count >= 2 and structural_count >= 2:
        return "exceptional"
    if deep_count >= 1 or structural_count >= 3:
        return "high"
    if structural_count >= 1:
        return "notable"
    return "minimal"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _build_integrity_line(success_level: str, active_successes: List[str]) -> str:
    """Render the success findings clinically and non-euphemistically."""
    if success_level == "minimal":
        return "No distinct structural integrity-strengthening signals detected."

    top = _top_success_labels(active_successes, max_show=3)
    mech_str = _join_labels(top)

    if success_level == "exceptional":
        return (
            f"The argument exhibits exceptional epistemic rigor through {mech_str}. "
            f"These signals strengthen information recoverability."
        )

    if success_level == "high":
        return (
            f"The argument shows significant integrity-strengthening work via {mech_str}. "
            f"These signals materially improve interpretive discipline."
        )

    return (
        f"The argument includes notable integrity signals, specifically {mech_str}."
    )


# ---------------------------------------------------------------------------
# Unavailable
# ---------------------------------------------------------------------------

def _unavailable_profile() -> Dict[str, Any]:
    return {
        "success_level": "unknown",
        "active_successes": [],
        "deep_rigor_count": 0,
        "structural_rigor_count": 0,
        "integrity_line": "Integrity profile unavailable.",
        "domain_alignment": "unknown",
        "domain_priority_hits": [],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_success_profile(enriched: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the ESM profile.

    Consumes:
        enriched["success_blocks"]                              # primary
        enriched["reader_interpretation"]["success_blocks"]     # fallback
        enriched["adjudicated_whole_article_judgment"]["classification"]

    Returns:
        {
            "success_level": str,           # minimal | notable | high | exceptional | unknown
            "active_successes": [str, ...],
            "deep_rigor_count": int,
            "structural_rigor_count": int,
            "integrity_line": str,
            "domain_alignment": str,
            "domain_priority_hits": [str, ...],
        }
    """
    if not isinstance(enriched, dict):
        return _unavailable_profile()

    interp = _sd(enriched.get("reader_interpretation"))
    if "error" in interp:
        return _unavailable_profile()

    metadata = _sd(enriched.get("metadata"))
    waj = _sd(enriched.get("adjudicated_whole_article_judgment"))

    # Top-level success_blocks (from SSD), fallback to reader_interpretation
    blocks = enriched.get("success_blocks")
    if not isinstance(blocks, list):
        blocks = interp.get("success_blocks", [])

    object_type = (
        _s(metadata.get("object_type"))
        or _s(waj.get("classification"))
        or "general"
    )

    active_successes = _extract_valid_successes(blocks)

    deep_count = sum(1 for s in active_successes if s in _DEEP_RIGOR)
    structural_count = sum(1 for s in active_successes if s in _STRUCTURAL_RIGOR)

    success_level = _determine_success_level(deep_count, structural_count)
    integrity_line = _build_integrity_line(success_level, active_successes)
    domain_hits = _domain_priority_hits(active_successes, object_type)

    return {
        "success_level": success_level,
        "active_successes": active_successes,
        "deep_rigor_count": deep_count,
        "structural_rigor_count": structural_count,
        "integrity_line": integrity_line,
        "domain_alignment": object_type,
        "domain_priority_hits": domain_hits,
    }
