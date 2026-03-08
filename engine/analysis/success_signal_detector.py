#!/usr/bin/env python3
"""
FILE: engine/analysis/success_signal_detector.py
VERSION: 0.1
PURPOSE:
Detect positive epistemic integrity signals from the enriched substrate.
Phase 1 — conservative first wave: 3 signals only.

SIGNALS DETECTED (Phase 1):
    1. comparative_grounding   — claims anchored to explicit baselines (low risk)
    2. scope_discipline        — conclusions explicitly bounded (low risk)
    3. uncertainty_visibility   — explicit uncertainty surfaced in text + backend (moderate risk)

DEFERRED (Phase 2):
    - proportional_hedging     — keyword != proportional calibration
    - steel_manning, adverse_fact_inclusion, causal_transparency,
      assumption_externalization

HARD RULES:
    - Positive evidence only — never infer success from absence
    - Fail closed
    - Emit only known mechanisms
    - Deduplicate: each mechanism emitted at most once
    - Stable output order: comparative → scope → uncertainty
    - No scoring, no PEG interaction
    - Binary signals only (Phase 1)

CONSUMES:
    enriched["adjudicated_claims"]
    enriched["verification"]
    enriched["argument_integrity"]
    enriched["adjudicated_whole_article_judgment"]
    enriched["reader_interpretation"]  (fail-closed gate only)

RULES: pure, deterministic, no I/O, fail-closed.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sd(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _sl(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _s(x: Any) -> str:
    return str(x or "").strip()


def _collect_claim_texts(enriched: Dict[str, Any]) -> str:
    """Concatenate all adjudicated claim texts into a single searchable string."""
    claims = _sl(enriched.get("adjudicated_claims"))
    parts: List[str] = []
    for c in claims:
        if isinstance(c, dict):
            text = c.get("text", "")
            if isinstance(text, str) and text.strip():
                parts.append(text)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Compiled pattern sets
# ---------------------------------------------------------------------------

_COMPARATIVE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bcompared with\b",
        r"\brelative to\b",
        r"\bversus\b",
        r"\bvs\.?\b",
        r"\bhigher than\b",
        r"\blower than\b",
        r"\bmore than\b",
        r"\bless than\b",
        r"\bbaseline\b",
        r"\bhistorically\b",
        r"\baverage\b",
        r"\b\d+%?\s*above\b",
        r"\b\d+%?\s*below\b",
    ]
]

_SCOPE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bin this case\b",
        r"\bin this instance\b",
        r"\bin this article\b",
        r"\bwithin this dataset\b",
        r"\bfor this period\b",
        r"\bunder these conditions\b",
        r"\bcannot generalize\b",
        r"\blimited to\b",
        r"\bdoes not establish\b",
        r"\bonly shows\b",
    ]
]

_UNCERTAINTY_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bunclear\b",
        r"\buncertain\b",
        r"\bundetermined\b",
        r"\binsufficient evidence\b",
        r"\bcannot conclude\b",
        r"\bnot established\b",
        r"\bmixed evidence\b",
    ]
]

# Verification statuses that indicate unresolved epistemic state
_UNRESOLVED_STATUSES = frozenset({
    "not_verifiable",
    "conflicted_sources",
    "not_checked_yet",
})


# ---------------------------------------------------------------------------
# Block templates
# ---------------------------------------------------------------------------

_COMPARATIVE_BLOCK: Dict[str, Any] = {
    "mechanism": "comparative_grounding",
    "title": "Comparative grounding",
    "body": (
        "The argument anchors its claims against an explicit "
        "baseline or comparison point."
    ),
    "source_signals": ["adjudicated_claims"],
}

_SCOPE_BLOCK: Dict[str, Any] = {
    "mechanism": "scope_discipline",
    "title": "Disciplined scope",
    "body": (
        "The argument keeps its conclusions within explicit "
        "evidentiary boundaries."
    ),
    "source_signals": ["adjudicated_claims", "argument_integrity"],
}

_UNCERTAINTY_BLOCK: Dict[str, Any] = {
    "mechanism": "uncertainty_visibility",
    "title": "Visible uncertainty",
    "body": (
        "The argument explicitly surfaces areas where the evidence "
        "is inconclusive or unresolved."
    ),
    "source_signals": ["verification", "adjudicated_claims"],
}


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _has_pattern_match(text: str, patterns: List[re.Pattern]) -> bool:
    """Return True if any pattern matches in text."""
    for pat in patterns:
        if pat.search(text):
            return True
    return False


def _has_unresolved_verification(enriched: Dict[str, Any]) -> bool:
    """Check if verification results contain unresolved statuses."""
    verification = _sd(enriched.get("verification"))
    results = _sl(verification.get("results"))
    for r in results:
        if isinstance(r, dict):
            status = _s(r.get("verification_status"))
            if status in _UNRESOLVED_STATUSES:
                return True
    return False


# ---------------------------------------------------------------------------
# Individual detectors (stable order: comparative → scope → uncertainty)
# ---------------------------------------------------------------------------

def _detect_comparative_grounding(
    claim_text: str, enriched: Dict[str, Any],
) -> Dict[str, Any] | None:
    """Emit only when explicit baseline comparison exists in claim text."""
    if _has_pattern_match(claim_text, _COMPARATIVE_PATTERNS):
        return dict(_COMPARATIVE_BLOCK)
    return None


def _detect_scope_discipline(
    claim_text: str, enriched: Dict[str, Any],
) -> Dict[str, Any] | None:
    """Emit only when the argument explicitly bounds its claim scope."""
    if _has_pattern_match(claim_text, _SCOPE_PATTERNS):
        return dict(_SCOPE_BLOCK)
    return None


def _detect_uncertainty_visibility(
    claim_text: str, enriched: Dict[str, Any],
) -> Dict[str, Any] | None:
    """Emit only when uncertainty is explicitly surfaced in text
    or article-level judgment AND verification contains unresolved states.

    Both a surface condition (text or classification) and a backend
    condition (unresolved verification) must be met."""
    waj = _sd(enriched.get("adjudicated_whole_article_judgment"))
    waj_uncertain = _s(waj.get("classification")) == "uncertain"

    has_text = _has_pattern_match(claim_text, _UNCERTAINTY_PATTERNS)
    has_verification = _has_unresolved_verification(enriched)

    if (has_text or waj_uncertain) and has_verification:
        return dict(_UNCERTAINTY_BLOCK)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Ordered detector list — stable output order
_DETECTORS = [
    _detect_comparative_grounding,
    _detect_scope_discipline,
    _detect_uncertainty_visibility,
]


def detect_success_signals(enriched: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Detect positive epistemic integrity signals from the enriched substrate.

    Returns a list of success block dicts, each with:
        mechanism: str
        title: str
        body: str
        source_signals: [str, ...]

    Emits each mechanism at most once. Stable order.
    Returns empty list on structural error (fail-closed).
    """
    if not isinstance(enriched, dict):
        return []

    # Fail-closed gate: if reader_interpretation failed, substrate is partial
    interp = _sd(enriched.get("reader_interpretation"))
    if "error" in interp:
        return []

    claim_text = _collect_claim_texts(enriched)
    if not claim_text:
        return []

    blocks: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for detector in _DETECTORS:
        try:
            result = detector(claim_text, enriched)
            if result is not None:
                mech = result.get("mechanism", "")
                if mech and mech not in seen:
                    seen.add(mech)
                    blocks.append(result)
        except Exception:
            continue  # fail-closed per detector

    return blocks
