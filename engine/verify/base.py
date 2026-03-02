#!/usr/bin/env python3
"""
FILE: engine/verify/base.py
VERSION: 0.3
PURPOSE:
Canonical verification interface layer for the Survivor pipeline.

Provides the enums, constants, and a minimal authority-source validator
used by engine/core/validators.py when verification_enabled=True.

CONTRACT:
- No provider adapters, web calls, or I/O of any kind.
- No optional imports, no side effects on import.
- Import-safe from any context; always available at runtime.
- Enums are frozensets; membership checks are O(1).
- validate_authority_source() raises RuntimeError (fail-closed).
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Literal, TypedDict


# ---------------------------------------------------------------------------
# Type aliases (used by claim_classifier and verification layer)
# ---------------------------------------------------------------------------

ClaimKind = Literal["world_fact", "document_content"]
Checkability = Literal["checkable", "unknown"]

CHECKABILITY_VALUES: FrozenSet[str] = frozenset({"checkable", "unknown"})


# ---------------------------------------------------------------------------
# Typed dicts for verification output
# ---------------------------------------------------------------------------

class VerificationResult(TypedDict, total=False):
    claim_id: str
    claim_text: str
    claim_kind: str
    verification_status: str
    confidence: str
    authority_sources: List[Dict[str, Any]]
    method_note: str
    checked_at: str


class VerificationPack(TypedDict, total=False):
    enabled: bool
    results: List[VerificationResult]
    note: str


# ---------------------------------------------------------------------------
# Claim kinds
# ---------------------------------------------------------------------------

CLAIM_KINDS: FrozenSet[str] = frozenset({
    "factual",
    "numerical",
    "causal",
    "attribution",
    "timeline",
})


# ---------------------------------------------------------------------------
# Verification statuses
# ---------------------------------------------------------------------------

VERIFICATION_STATUSES: FrozenSet[str] = frozenset({
    "verified_true",
    "verified_false",
    "mixed_or_partial",
    "conflicted_sources",
    "insufficient_evidence",
    "not_checked_yet",
    "not_verifiable",
})


# ---------------------------------------------------------------------------
# Source types
# ---------------------------------------------------------------------------

SOURCE_TYPES: FrozenSet[str] = frozenset({
    "web",
    "gov",
    "academic",
    "news",
    "organization",
    "database",
    "other",
})


# ---------------------------------------------------------------------------
# Confidence values (verification layer — uppercase; distinct from reviewer
# pack confidence which uses lowercase via schema_constants.CONFIDENCE_VALUES)
# ---------------------------------------------------------------------------

CONFIDENCE_VALUES: FrozenSet[str] = frozenset({
    "HIGH",
    "MEDIUM",
    "LOW",
})


# ---------------------------------------------------------------------------
# Authority source validator
# ---------------------------------------------------------------------------

def validate_authority_source(src: Dict[str, Any]) -> None:
    """
    Fail-closed validator for a single authority source dict.
    Raises RuntimeError on any violation.
    """
    if not isinstance(src, dict):
        raise RuntimeError("authority_source must be a dict")

    src_type = src.get("source_type")
    if src_type not in SOURCE_TYPES:
        raise RuntimeError(f"authority_source.source_type invalid: {src_type!r}")

    has_locator = isinstance(src.get("locator"), str) and bool(src["locator"].strip())
    has_url = isinstance(src.get("url"), str) and bool(src["url"].strip())
    if not (has_locator or has_url):
        raise RuntimeError(
            "authority_source must have a non-empty locator or url"
        )
