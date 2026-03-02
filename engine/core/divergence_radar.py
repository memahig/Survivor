#!/usr/bin/env python3
"""
FILE: engine/core/divergence_radar.py
VERSION: 0.1
PURPOSE:
Post-adjudication divergence analysis for the Survivor pipeline.
Measures how much reviewers converge on recoverable story elements.

CONTRACT:
- Pure function: no I/O, no model calls, deterministic.
- Reads run_state (phase2, adjudicated, gsae) — never mutates inputs.
- Returns a divergence_radar dict to be attached to run_state.
- Graceful on missing keys: returns partial radar rather than crashing.

DETECTORS:
A) Whole-article conflict: how many distinct classifications across reviewers.
B) Central claim instability: unsupported/undetermined rates among core claims.
C) GSAE risk signal: quarantine count bumps conflict level.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Conflict level helpers
# ---------------------------------------------------------------------------

_LEVELS = ("low", "moderate", "high")


def _bump_level(level: str) -> str:
    """Bump a conflict level by one step, capped at high."""
    idx = _LEVELS.index(level) if level in _LEVELS else 0
    return _LEVELS[min(idx + 1, len(_LEVELS) - 1)]


# ---------------------------------------------------------------------------
# Detector A: Whole-article classification conflict
# ---------------------------------------------------------------------------

def _detect_article_conflict(phase2: Dict[str, Any]) -> tuple[str, List[str]]:
    """
    Returns (conflict_level, notes).
    Measures distinct classifications and confidence disagreement.
    """
    classifications: Dict[str, str] = {}
    confidences: Dict[str, str] = {}

    for reviewer, pack in phase2.items():
        if not isinstance(pack, dict):
            continue
        waj = pack.get("whole_article_judgment")
        if not isinstance(waj, dict):
            continue
        c = waj.get("classification")
        if isinstance(c, str):
            classifications[reviewer] = c
        conf = waj.get("confidence")
        if isinstance(conf, str):
            confidences[reviewer] = conf

    unique_classes = set(classifications.values())
    notes: List[str] = []

    if len(unique_classes) <= 1:
        level = "low"
    elif len(unique_classes) == 2:
        level = "moderate"
        notes.append(
            f"Reviewers split on classification: {sorted(unique_classes)}"
        )
    else:
        level = "high"
        notes.append(
            f"Reviewers diverge across {len(unique_classes)} classifications: "
            f"{sorted(unique_classes)}"
        )

    # If any reviewer has high confidence but classes differ, bump
    if len(unique_classes) > 1 and "high" in confidences.values():
        level = _bump_level(level)
        notes.append("High-confidence reviewer disagrees on classification")

    return level, notes


# ---------------------------------------------------------------------------
# Detector B: Central claim instability
# ---------------------------------------------------------------------------

def _detect_claim_instability(
    adjudicated: Dict[str, Any],
) -> tuple[str, float, float, List[str]]:
    """
    Returns (level, unsupported_core_rate, undetermined_core_rate, notes).
    Focuses on core claim groups (centrality >= 2).
    """
    arena = adjudicated.get("claim_track", {}).get("arena", {})
    groups = arena.get("adjudicated_claims", [])

    # Core groups: centrality >= 2
    core_groups = [
        g for g in groups
        if isinstance(g, dict) and isinstance(g.get("centrality"), int) and g["centrality"] >= 2
    ]

    if not core_groups:
        return "low", 0.0, 0.0, ["No core claim groups (centrality >= 2) found"]

    total = len(core_groups)
    unsupported = 0
    undetermined = 0

    for g in core_groups:
        adj = g.get("adjudication", "")
        tally = g.get("tally", {})

        if adj == "rejected":
            unsupported += 1
        elif adj == "downgraded":
            # Check if primarily undetermined
            und_votes = tally.get("undetermined_votes", 0)
            sup_votes = tally.get("supported_votes", 0)
            unsup_votes = tally.get("unsupported_votes", 0)
            if und_votes > sup_votes and und_votes > unsup_votes:
                undetermined += 1
            else:
                unsupported += 1

    unsupported_rate = round(unsupported / total, 3)
    undetermined_rate = round(undetermined / total, 3)

    notes: List[str] = []

    if unsupported_rate >= 0.40 or undetermined_rate >= 0.40:
        level = "high"
        notes.append(
            f"Core claims unstable: {unsupported}/{total} unsupported, "
            f"{undetermined}/{total} undetermined"
        )
    elif unsupported_rate >= 0.20 or undetermined_rate >= 0.20:
        level = "moderate"
        notes.append(
            f"Some core claim instability: {unsupported}/{total} unsupported, "
            f"{undetermined}/{total} undetermined"
        )
    else:
        level = "low"

    return level, unsupported_rate, undetermined_rate, notes


# ---------------------------------------------------------------------------
# Detector C: GSAE quarantine signal
# ---------------------------------------------------------------------------

def _detect_gsae_risk(gsae: Optional[Dict[str, Any]]) -> tuple[int, List[str]]:
    """
    Returns (quarantine_count, notes).
    """
    if gsae is None:
        return 0, []

    artifacts = gsae.get("artifacts", [])
    if not isinstance(artifacts, list):
        return 0, []

    quarantine_count = sum(
        1 for a in artifacts
        if isinstance(a, dict) and a.get("symmetry_status") == "QUARANTINE"
    )

    notes: List[str] = []
    if quarantine_count > 0:
        notes.append(
            f"GSAE quarantine: {quarantine_count} reviewer(s) removed from symmetry pool"
        )

    return quarantine_count, notes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_divergence_radar(run_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute divergence radar from run_state.
    Returns a divergence_radar dict ready to attach to run_state.

    Pure function — never mutates run_state.
    """
    phase2 = run_state.get("phase2", {})
    adjudicated = run_state.get("adjudicated", {})
    gsae = run_state.get("gsae")

    all_notes: List[str] = []

    # A) Whole-article conflict
    article_conflict, a_notes = _detect_article_conflict(phase2)
    all_notes.extend(a_notes)

    # B) Central claim instability
    claim_level, unsup_rate, undet_rate, b_notes = _detect_claim_instability(adjudicated)
    all_notes.extend(b_notes)

    # C) GSAE risk signal
    quarantine_count, c_notes = _detect_gsae_risk(gsae)
    all_notes.extend(c_notes)

    # GSAE quarantine bumps article conflict one level
    if quarantine_count > 0:
        article_conflict = _bump_level(article_conflict)
        all_notes.append(
            "Symmetry quarantine detected — article conflict level bumped"
        )

    return {
        "status": "run",
        "whole_article_conflict": article_conflict,
        "central_claim_instability": claim_level,
        "unsupported_core_rate": unsup_rate,
        "undetermined_core_rate": undet_rate,
        "gsae_quarantine_count": quarantine_count,
        "notes": all_notes,
    }
