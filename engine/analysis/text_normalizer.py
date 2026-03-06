#!/usr/bin/env python3
"""
FILE: engine/analysis/text_normalizer.py
PURPOSE: Text normalization and tokenization for analysis modules.
         Provides Jaccard similarity for claim deduplication.
RULES: stdlib only, pure, deterministic, no I/O.
"""

from __future__ import annotations

import re
import unicodedata
from typing import FrozenSet


# ---- Smart quote / dash mappings ----

_SMART_CHARS = {
    "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"',
    "\u2032": "'", "\u2033": '"',
    "\u2013": "-", "\u2014": "-", "\u2015": "-",
}

# ---- Lightweight stopword set (English, common function words) ----

_STOPWORDS: FrozenSet[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "it", "its",
    "this", "that", "these", "those", "he", "she", "they", "we", "i",
    "you", "his", "her", "their", "our", "my", "your", "not", "no",
    "as", "if", "so", "than", "also", "very", "just", "about", "into",
    "more", "some", "such", "only", "other", "any", "each", "all",
})

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace runs to single space, strip."""
    if not text:
        return ""
    return _WS_RE.sub(" ", text).strip()


def normalize_unicode(text: str) -> str:
    """NFC normalize, convert smart quotes/dashes to ASCII equivalents."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    for src, dst in _SMART_CHARS.items():
        text = text.replace(src, dst)
    return text


def tokenize_for_similarity(text: str) -> FrozenSet[str]:
    """
    Tokenize text for Jaccard similarity comparison.
    Steps: unicode normalize → whitespace normalize → lowercase →
           strip punctuation → split → remove stopwords.
    Returns frozenset of tokens.
    """
    if not text:
        return frozenset()
    text = normalize_unicode(text)
    text = normalize_whitespace(text)
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    tokens = text.split()
    return frozenset(t for t in tokens if t and t not in _STOPWORDS)


def jaccard_similarity(a: FrozenSet[str], b: FrozenSet[str]) -> float:
    """
    Jaccard similarity: |A ∩ B| / |A ∪ B|.
    Returns 0.0 if both sets are empty.
    """
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return intersection / union
