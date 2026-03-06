#!/usr/bin/env python3
"""
FILE: engine/analysis/reads_like_label.py
PURPOSE: Authorize blunt language from structural signals.
         Maps combinations of boolean flags to readable labels.
         Every label is earned from substrate fields, never hard-coded opinion.
RULES: pure, deterministic, no I/O, fail-closed.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _safe_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def infer_reads_like(enriched: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build boolean flags from enriched substrate, then map to a blunt label.

    The label map is priority-ordered: first matching rule wins.
    Every label must be traceable to the flags that triggered it.

    Args:
        enriched: the full enriched_substrate dict

    Returns:
        {
            "label": str,
            "flags": dict[str, bool],
            "matched_rule": int,
        }
    """
    if not isinstance(enriched, dict):
        return {
            "label": "a mixed information object that resists clean classification",
            "flags": {},
            "matched_rule": 7,
        }

    # ---- Build boolean flags from substrate ----

    # Official assertion reliance
    official_detections = _safe_list(enriched.get("official_detections"))
    has_official_reliance = any(
        isinstance(d, dict) and d.get("official_only") is True
        for d in official_detections
    )

    # Verification gap
    causal_detections = _safe_list(enriched.get("causal_detections"))
    unsupported_causal_count = sum(
        1 for d in causal_detections
        if isinstance(d, dict) and d.get("unsupported_causal") is True
    )

    divergence_radar = _safe_dict(enriched.get("divergence_radar"))
    unsupported_core_rate = divergence_radar.get("unsupported_core_rate", 0.0)
    if not isinstance(unsupported_core_rate, (int, float)):
        unsupported_core_rate = 0.0

    has_verification_gap = (
        unsupported_core_rate > 0.3
        or unsupported_causal_count >= 2
    )

    # Reassurance / mobilizing pattern from classification
    adjudicated = _safe_dict(enriched.get("adjudicated"))
    article_track = _safe_dict(adjudicated.get("article_track"))
    waj = _safe_dict(article_track.get("adjudicated_whole_article_judgment"))
    classification = str(waj.get("classification", "")).lower()

    has_reassurance_pattern = any(
        term in classification
        for term in ("reassurance", "mobilizing", "propaganda", "advocacy")
    )

    # Omission dependence: >=2 load_bearing omissions
    ranked_omissions = _safe_list(enriched.get("ranked_omissions"))
    load_bearing_omission_count = sum(
        1 for om in ranked_omissions
        if isinstance(om, dict) and om.get("severity") == "load_bearing"
    )
    has_omission_dependence = load_bearing_omission_count >= 2

    # Framing escalation: high-concern framing omissions
    framing_high = any(
        isinstance(om, dict)
        and om.get("kind") == "framing_omission"
        and om.get("concern_level") == "high"
        for om in ranked_omissions
    )
    has_framing_escalation = framing_high

    # Reporting structure
    has_reporting_structure = any(
        term in classification
        for term in ("reporting", "analysis")
    )

    # Major blind spots: >=3 important+ omissions
    important_plus_count = sum(
        1 for om in ranked_omissions
        if isinstance(om, dict) and om.get("severity") in ("important", "load_bearing")
    )
    has_major_blind_spots = important_plus_count >= 3

    # High fragility from argument integrity
    structural_forensics = _safe_dict(adjudicated.get("structural_forensics"))
    argument_integrity = _safe_dict(structural_forensics.get("argument_integrity"))
    merged_fragility = argument_integrity.get("merged_argument_fragility", "")

    # Also check load_bearing module output
    load_bearing = _safe_dict(enriched.get("load_bearing"))
    lb_fragility = load_bearing.get("argument_fragility", "")

    has_high_fragility = (
        merged_fragility == "high"
        or lb_fragility == "high"
    )

    # Rival weakness: any rival narrative with structural_fragility == "high"
    rival_narratives = _safe_list(structural_forensics.get("rival_narratives"))
    has_rival_weakness = any(
        isinstance(rn, dict) and rn.get("structural_fragility") == "high"
        for rn in rival_narratives
    )

    # ---- Assemble flags ----

    flags = {
        "has_official_reliance": has_official_reliance,
        "has_verification_gap": has_verification_gap,
        "has_reassurance_pattern": has_reassurance_pattern,
        "has_omission_dependence": has_omission_dependence,
        "has_framing_escalation": has_framing_escalation,
        "has_reporting_structure": has_reporting_structure,
        "has_major_blind_spots": has_major_blind_spots,
        "has_high_fragility": has_high_fragility,
        "has_rival_weakness": has_rival_weakness,
    }

    # ---- Priority-ordered label map ----

    if has_omission_dependence and has_framing_escalation and has_high_fragility:
        return {
            "label": (
                "a pattern often seen in propaganda - "
                "the argument depends on excluding rival explanations "
                "and missing context"
            ),
            "flags": flags,
            "matched_rule": 1,
        }

    if has_official_reliance and has_verification_gap:
        return {
            "label": (
                "a reassurance narrative built around official assertions "
                "without independent verification"
            ),
            "flags": flags,
            "matched_rule": 2,
        }

    if has_official_reliance and has_reassurance_pattern:
        return {
            "label": "reassurance framing that relies heavily on official claims",
            "flags": flags,
            "matched_rule": 3,
        }

    if has_reporting_structure and has_major_blind_spots:
        return {
            "label": "mostly reporting with important structural blind spots",
            "flags": flags,
            "matched_rule": 4,
        }

    if has_high_fragility and has_rival_weakness:
        return {
            "label": (
                "structurally fragile - "
                "the argument collapses if rival explanations are admitted"
            ),
            "flags": flags,
            "matched_rule": 5,
        }

    if has_reporting_structure:
        return {
            "label": "reporting with minor structural concerns",
            "flags": flags,
            "matched_rule": 6,
        }

    return {
        "label": "a mixed information object that resists clean classification",
        "flags": flags,
        "matched_rule": 7,
    }
