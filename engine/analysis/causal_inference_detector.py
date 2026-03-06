#!/usr/bin/env python3
"""
FILE: engine/analysis/causal_inference_detector.py
PURPOSE: Detect claims containing causal language patterns.
         Flag unsupported causal claims (causal language + no evidence).
RULES: pure, deterministic, no I/O, fail-closed.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


# ---- Compiled causal patterns ----

_CAUSAL_PATTERNS: List[tuple[re.Pattern, str]] = [
    (re.compile(r"\bcaused?\b", re.IGNORECASE), "caused"),
    (re.compile(r"\bled\s+to\b", re.IGNORECASE), "led to"),
    (re.compile(r"\bresulted?\s+in\b", re.IGNORECASE), "resulted in"),
    (re.compile(r"\bdue\s+to\b", re.IGNORECASE), "due to"),
    (re.compile(r"\btriggered?\b", re.IGNORECASE), "triggered"),
    (re.compile(r"\bbrought\s+about\b", re.IGNORECASE), "brought about"),
    (re.compile(r"\bcontributed?\s+to\b", re.IGNORECASE), "contributed to"),
    (re.compile(r"\bdrove\b", re.IGNORECASE), "drove"),
    (re.compile(r"\bbecause\s+of\b", re.IGNORECASE), "because of"),
    (re.compile(r"\bresponsible\s+for\b", re.IGNORECASE), "responsible for"),
]

_WEAKENED_ADJUDICATIONS = frozenset({"rejected", "downgraded"})


def detect_causal_claims(
    adjudicated_claims: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Detect claims containing causal language patterns.

    Input: adjudicated_claims from
           run_state.adjudicated.claim_track.arena.adjudicated_claims

    Returns only claims where at least one causal pattern matches.
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

        group_id = claim.get("group_id", "")
        evidence_eids = claim.get("evidence_eids", [])
        if not isinstance(evidence_eids, list):
            evidence_eids = []
        adjudication = claim.get("adjudication", "")

        # Check all causal patterns
        matched: List[str] = []
        for pattern, label in _CAUSAL_PATTERNS:
            if pattern.search(text):
                matched.append(label)

        if not matched:
            continue

        has_evidence = len(evidence_eids) > 0
        unsupported_causal = len(matched) > 0 and not has_evidence
        causal_claim_weakened = adjudication in _WEAKENED_ADJUDICATIONS

        results.append({
            "group_id": group_id,
            "claim_text": text,
            "matched_patterns": sorted(matched),
            "evidence_eids": evidence_eids,
            "adjudication": adjudication,
            "unsupported_causal": unsupported_causal,
            "causal_claim_weakened": causal_claim_weakened,
        })

    return results
