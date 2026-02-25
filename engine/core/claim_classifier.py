#!/usr/bin/env python3
"""
FILE: engine/core/claim_classifier.py
VERSION: 0.1
PURPOSE:
Deterministic, zero-cost classification of claim text.

No LLM calls. No external I/O. Pure regex heuristics.

PUBLIC API:
    classify_claim_kind(text)              -> ClaimKind
    compute_checkability(text, claim_kind) -> Checkability
    extract_source_doc_hint(text)          -> Optional[str]

DESIGN NOTES:
- classify_claim_kind: returns "document_content" only when the text
  uses explicit document-attribution language ("the law says", "according
  to the", "in verse 3", etc.). Default is "world_fact".
- compute_checkability:
    world_fact    — checkable if date / quantity / named-entity /
                    event-verb is present; else unknown.
    document_content — checkable ONLY if BOTH a specific named source
                    (KJV, U.S. Code, etc.) AND a structural locator
                    (chapter 3, verse 16, John 3:16) are present.
                    Neither alone is sufficient (e.g. "John 3:16"
                    without a version is ambiguous across translations).
- extract_source_doc_hint: returns the canonical source label when a
  known document name is found; None otherwise (no guessing).
- _HINT_PATTERNS is declared before compute_checkability because
  compute_checkability closes over it.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from engine.verify.base import Checkability, ClaimKind


# ---------------------------------------------------------------------------
# claim_kind — document_content detection
# ---------------------------------------------------------------------------

_DOC_SAYS_VERBS = (
    r"(?:says|said|states|reads|contains|records|commands|instructs|"
    r"stipulates|declares|mandates)"
)

_DOC_CONTENT_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\bthe\s+text\s+" + _DOC_SAYS_VERBS, re.IGNORECASE),
    re.compile(
        r"\bthe\s+(?:document|law|statute|code|bible|scripture|treaty|contract|"
        r"agreement|report|manual|handbook|constitution|amendment|act|bill|"
        r"regulation|guideline|policy|charter|decree|ordinance|edict|"
        r"case\s+record|court\s+record)\s+" + _DOC_SAYS_VERBS,
        re.IGNORECASE,
    ),
    re.compile(
        r"\bthe\s+(?:\w+\s+){0,3}(?:bible|code|law|act|treaty|constitution|"
        r"statute|regulation|scripture|book)\s+" + _DOC_SAYS_VERBS,
        re.IGNORECASE,
    ),
    re.compile(r"\baccording\s+to\s+the\b", re.IGNORECASE),
    re.compile(r"\bin\s+(?:chapter|section|verse|page|article|paragraph)\s+", re.IGNORECASE),
]


def classify_claim_kind(text: str) -> ClaimKind:
    for pat in _DOC_CONTENT_PATTERNS:
        if pat.search(text):
            return "document_content"
    return "world_fact"


# ---------------------------------------------------------------------------
# checkability — world_fact signals
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(
    r"\b(?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\b"
    r"|\b(?:19|20)\d{2}\b"
    r"|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    re.IGNORECASE,
)

_QUANTITY_RE = re.compile(
    r"\$\d[\d,\.]*"
    r"|\b\d[\d,\.]*\s*(?:%|percent|million|billion|trillion|"
    r"thousand|hundred|dollars?|pounds?|euros?|kg|km|mph|ft|lbs?)\b",
    re.IGNORECASE,
)

_NAMED_ENTITY_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")

_EVENT_VERB_RE = re.compile(
    r"\b(?:signed|approved|passed|enacted|introduced|announced|said|stated|declared|"
    r"launched|established|founded|created|died|born|elected|appointed|fired|"
    r"arrested|convicted|acquired|merged|filed|rejected|blocked|vetoed)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# checkability — document_content locator signals
# ---------------------------------------------------------------------------

# Requires a digit after the structural word: "in chapter 3", "verse 16".
# "in chapter" alone does NOT match (too broad).
_LOCATOR_CUE_RE = re.compile(
    r"\b(?:in\s+)?(?:chapter|section|verse|page|article|paragraph)\s+\d+\b",
    re.IGNORECASE,
)

# Covers "John 3:16", "Genesis 1:1", "1 Kings 18:21", "2 Corinthians 5:17"
_VERSE_REF_RE = re.compile(
    r"\b(?:[1-3]\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+\d+:\d+\b"
)


# ---------------------------------------------------------------------------
# Source-document hint patterns
# _HINT_PATTERNS must be declared BEFORE compute_checkability (referenced within).
# ---------------------------------------------------------------------------

_HINT_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bKJV\b|\bKing\s+James\s+(?:Version|Bible)\b", re.IGNORECASE), "KJV"),
    (re.compile(r"\bNIV\b|\bNew\s+International\s+Version\b", re.IGNORECASE), "NIV"),
    (re.compile(r"\bESV\b|\bEnglish\s+Standard\s+Version\b", re.IGNORECASE), "ESV"),
    (re.compile(r"\bNASB\b|\bNew\s+American\s+Standard\b", re.IGNORECASE), "NASB"),
    (re.compile(r"\bU\.?S\.?\s+Code\b|\bUnited\s+States\s+Code\b", re.IGNORECASE), "U.S. Code"),
    (re.compile(r"\bthe\s+Constitution\b", re.IGNORECASE), "U.S. Constitution"),
    (re.compile(r"\bthe\s+Bible\b", re.IGNORECASE), "Bible"),
]


# ---------------------------------------------------------------------------
# compute_checkability
# ---------------------------------------------------------------------------

def compute_checkability(text: str, claim_kind: ClaimKind) -> Checkability:
    if claim_kind == "document_content":
        has_source = any(pat.search(text) for pat, _ in _HINT_PATTERNS)
        has_locator = bool(_LOCATOR_CUE_RE.search(text) or _VERSE_REF_RE.search(text))
        return "checkable" if (has_source and has_locator) else "unknown"

    # world_fact
    if _DATE_RE.search(text):
        return "checkable"
    if _QUANTITY_RE.search(text):
        return "checkable"
    if _NAMED_ENTITY_RE.search(text):
        return "checkable"
    if _EVENT_VERB_RE.search(text):
        return "checkable"
    return "unknown"


# ---------------------------------------------------------------------------
# extract_source_doc_hint
# ---------------------------------------------------------------------------

def extract_source_doc_hint(text: str) -> Optional[str]:
    """Return the canonical source label for the first matching hint, or None."""
    for pat, hint in _HINT_PATTERNS:
        if pat.search(text):
            return hint
    return None
