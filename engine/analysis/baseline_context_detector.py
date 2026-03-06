#!/usr/bin/env python3
"""
FILE: engine/analysis/baseline_context_detector.py
PURPOSE: Detect percentage/statistical claims that lack baseline context.
RULES: pure, deterministic, no I/O, fail-closed.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# ---- Statistical claim patterns ----

_STAT_PATTERNS: List[tuple[re.Pattern, str]] = [
    (re.compile(r"\b\d+\s*%", re.IGNORECASE), "percentage"),
    (re.compile(r"\b\d+\s+percent\b", re.IGNORECASE), "percent"),
    (re.compile(r"\bdoubled\b", re.IGNORECASE), "doubled"),
    (re.compile(r"\btripled\b", re.IGNORECASE), "tripled"),
    (re.compile(r"\b\d+\s*x\s+(?:more|higher|lower|faster|greater)\b", re.IGNORECASE), "multiplier"),
    (re.compile(r"\bincreased\s+by\b", re.IGNORECASE), "increased by"),
    (re.compile(r"\bdecreased\s+by\b", re.IGNORECASE), "decreased by"),
]

# ---- Baseline context indicators ----

_BASELINE_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bcompared\s+to\b", re.IGNORECASE),
    re.compile(r"\brelative\s+to\b", re.IGNORECASE),
    re.compile(r"\bversus\b", re.IGNORECASE),
    re.compile(r"\bvs\.?\b", re.IGNORECASE),
    re.compile(r"\bdown\s+from\b", re.IGNORECASE),
    re.compile(r"\bup\s+from\b", re.IGNORECASE),
    re.compile(r"\bin\s+(?:19|20)\d{2}\b", re.IGNORECASE),
]


def _find_stat_match(text: str) -> Optional[str]:
    """Return the first matching stat pattern label, or None."""
    for pattern, label in _STAT_PATTERNS:
        if pattern.search(text):
            return label
    return None


def _has_baseline(text: str) -> bool:
    """Check if text contains any baseline context indicator."""
    for pattern in _BASELINE_PATTERNS:
        if pattern.search(text):
            return True
    return False


def detect_baseline_absent(
    adjudicated_claims: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Detect claims with statistical language but no baseline context.

    Input: adjudicated_claims from
           run_state.adjudicated.claim_track.arena.adjudicated_claims

    Returns only claims where baseline_absent=True.
    Returns empty list on any structural error (fail-closed).
    """
    if not isinstance(adjudicated_claims, list):
        return []

    results: List[Dict[str, Any]] = []

    for claim in adjudicated_claims:
        if not isinstance(claim, dict):
            continue

        text = claim.get("text", "")
        if not isinstance(text, str) or not text.strip():
            continue

        stat_match = _find_stat_match(text)
        if stat_match is None:
            continue

        has_bl = _has_baseline(text)
        if has_bl:
            continue  # has baseline context — skip

        results.append({
            "group_id": claim.get("group_id", ""),
            "claim_text": text,
            "stat_match": stat_match,
            "baseline_absent": True,
        })

    return results
