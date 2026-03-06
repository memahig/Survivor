#!/usr/bin/env python3
"""
FILE: engine/analysis/official_assertion_detector.py
PURPOSE: Detect claims supported only by official/government statements
         with no independent corroboration.
RULES: pure, deterministic, no I/O, fail-closed.
NOTE: Does NOT depend on raw evidence_bank structure.
      Receives eid -> quote text via evidence_lookup param.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


# ---- Official source patterns ----

_OFFICIAL_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bofficial\b", re.IGNORECASE),
    re.compile(r"\bspokesperson\b", re.IGNORECASE),
    re.compile(r"\bspokeswoman\b", re.IGNORECASE),
    re.compile(r"\bspokesman\b", re.IGNORECASE),
    re.compile(r"\bministry\b", re.IGNORECASE),
    re.compile(r"\bdepartment\b", re.IGNORECASE),
    re.compile(r"\bgovernment\b", re.IGNORECASE),
    re.compile(r"\bpentagon\b", re.IGNORECASE),
    re.compile(r"\bwhite\s+house\b", re.IGNORECASE),
    re.compile(r"\bmilitary\b", re.IGNORECASE),
    re.compile(r"\bbriefing\b", re.IGNORECASE),
    re.compile(r"\bpress\s+release\b", re.IGNORECASE),
]

# ---- Independent corroboration patterns ----

_INDEPENDENT_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bindependent\b", re.IGNORECASE),
    re.compile(r"\bresearchers?\b", re.IGNORECASE),
    re.compile(r"\bstudy\b", re.IGNORECASE),
    re.compile(r"\bsurvey\b", re.IGNORECASE),
    re.compile(r"\binvestigat", re.IGNORECASE),
    re.compile(r"\bleaked?\b", re.IGNORECASE),
]


def _has_official_source(text: str) -> bool:
    """Check if text contains official source language."""
    for pattern in _OFFICIAL_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _has_independent_source(text: str) -> bool:
    """Check if text contains independent corroboration language."""
    for pattern in _INDEPENDENT_PATTERNS:
        if pattern.search(text):
            return True
    return False


def detect_official_assertions(
    adjudicated_claims: List[Dict[str, Any]],
    evidence_lookup: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Detect claims whose evidence contains only official-source language
    and no independent corroboration markers.

    Args:
        adjudicated_claims: from run_state.adjudicated.claim_track.arena.adjudicated_claims
        evidence_lookup: eid -> quote text (built externally)

    Returns only claims where official_only=True.
    Returns empty list on any structural error (fail-closed).
    """
    if not isinstance(adjudicated_claims, list):
        return []
    if not isinstance(evidence_lookup, dict):
        return []

    results: List[Dict[str, Any]] = []

    for claim in adjudicated_claims:
        if not isinstance(claim, dict):
            continue

        text = claim.get("text", "")
        if not isinstance(text, str) or not text.strip():
            continue

        evidence_eids = claim.get("evidence_eids", [])
        if not isinstance(evidence_eids, list):
            evidence_eids = []

        # Resolve evidence texts
        evidence_texts: List[str] = []
        for eid in evidence_eids:
            if not isinstance(eid, str):
                continue
            quote = evidence_lookup.get(eid, "")
            if isinstance(quote, str) and quote.strip():
                evidence_texts.append(quote)

        # Skip claims with no resolvable evidence
        if not evidence_texts:
            continue

        # Check combined evidence text
        combined = " ".join(evidence_texts)
        has_official = _has_official_source(combined)
        has_independent = _has_independent_source(combined)

        if not has_official:
            continue  # no official source pattern — not relevant

        official_only = has_official and not has_independent

        if not official_only:
            continue  # has independent corroboration — skip

        results.append({
            "group_id": claim.get("group_id", ""),
            "claim_text": text,
            "evidence_eids": evidence_eids,
            "official_only": True,
        })

    return results
