#!/usr/bin/env python3
"""
FILE: engine/verify/base.py
VERSION: 0.2
PURPOSE:
Types and constants for the Authority Verification layer.

Separates:
  Document Authority  — what does the document say?  (verbatim quote + locator)
  World Authority     — is it true in the world?      (external authority check)

VerificationResult is the canonical output of any verifier.
VerificationPack is the return type of run_verification().
"""

from __future__ import annotations

from typing import Dict, List, Literal, TypedDict


# ---------------------------------------------------------------------------
# Enums / Literals
# ---------------------------------------------------------------------------

Confidence = Literal["low", "medium", "high"]

CONFIDENCE_VALUES: frozenset[Confidence] = frozenset({"low", "medium", "high"})

ClaimKind = Literal["document_content", "world_fact"]

CLAIM_KINDS: frozenset[ClaimKind] = frozenset({"document_content", "world_fact"})

Checkability = Literal["checkable", "uncheckable", "unknown"]

CHECKABILITY_VALUES: frozenset[Checkability] = frozenset({"checkable", "uncheckable", "unknown"})

VerificationStatus = Literal[
    "verified_true",
    "verified_false",
    "conflicted_sources",
    "not_verifiable",
    "not_checked_yet",
]

VERIFICATION_STATUSES: frozenset[VerificationStatus] = frozenset({
    "verified_true",
    "verified_false",
    "conflicted_sources",
    "not_verifiable",
    "not_checked_yet",
})

SourceType = Literal[
    "document",
    "web_page",
    "database",
    "law_record",
    "journal_article",
    "book",
    "dataset",
    "other",
]

SOURCE_TYPES: frozenset[SourceType] = frozenset({
    "document",
    "web_page",
    "database",
    "law_record",
    "journal_article",
    "book",
    "dataset",
    "other",
})


# ---------------------------------------------------------------------------
# AuthoritySource
# ---------------------------------------------------------------------------

class AuthoritySource(TypedDict, total=False):
    source_id: str
    source_type: SourceType
    title: str
    locator: str        # paragraph ref, URL fragment, page number
    url: str            # optional


# ---------------------------------------------------------------------------
# VerificationResult
# ---------------------------------------------------------------------------

class VerificationResult(TypedDict):
    claim_id: str       # adjudicated claim group_id (G###), not member_claim_id
    claim_text: str
    claim_kind: ClaimKind
    verification_status: VerificationStatus
    confidence: Confidence
    authority_sources: List[AuthoritySource]    # may be [] ONLY if not_checked_yet
    method_note: str
    checked_at: str                             # ISO 8601 UTC timestamp


# ---------------------------------------------------------------------------
# VerificationPack — return type of run_verification()
# ---------------------------------------------------------------------------

class VerificationPack(TypedDict, total=False):
    enabled: bool
    results: List[VerificationResult]
    note: str           # present only when enabled=True and results=[]
