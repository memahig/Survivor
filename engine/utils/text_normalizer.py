#!/usr/bin/env python3
"""
FILE: engine/utils/text_normalizer.py
PURPOSE: Report output text cleanup. Whitespace, unicode, control chars.
         Separate from analysis tokenization logic in engine/analysis/text_normalizer.py.
RULES: stdlib only, pure, deterministic, no I/O.
"""

from __future__ import annotations

import re
import unicodedata


_SMART_QUOTES = {
    "\u2018": "'",   # left single
    "\u2019": "'",   # right single
    "\u201c": '"',   # left double
    "\u201d": '"',   # right double
    "\u2032": "'",   # prime
    "\u2033": '"',   # double prime
}

_SMART_DASHES = {
    "\u2013": "-",   # en dash
    "\u2014": "-",   # em dash
    "\u2015": "-",   # horizontal bar
}

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace runs to single space, strip leading/trailing."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def normalize_unicode(text: str) -> str:
    """NFC normalize, convert smart quotes and dashes to ASCII equivalents."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    for src, dst in _SMART_QUOTES.items():
        text = text.replace(src, dst)
    for src, dst in _SMART_DASHES.items():
        text = text.replace(src, dst)
    return text


def clean_for_report(text: str) -> str:
    """Full cleanup: unicode normalize + whitespace collapse + strip control chars."""
    if not text:
        return ""
    text = normalize_unicode(text)
    text = _CONTROL_RE.sub("", text)
    text = normalize_whitespace(text)
    return text
