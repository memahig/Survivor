#!/usr/bin/env python3
"""
FILE: engine/core/schema_constants.py
VERSION: 0.1
PURPOSE:
Centralized schema constants for Survivor pipeline validators.

CONTRACT:
- Validators must reference these constants only; do not hardcode key sets inline.
- Prompt schemas must be updated in the same PR when keys change.
- This file has no runtime dependencies on the rest of the engine.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# ReviewerPack required keys
# ---------------------------------------------------------------------------

REVIEWER_PACK_REQUIRED_KEYS: frozenset[str] = frozenset({
    "whole_article_judgment",
    "main_conclusion",
    "claims",
    "scope_markers",
    "causal_links",
    "article_patterns",
    "omission_candidates",
    "counterfactual_requirements",
    "evidence_density",
    "claim_tickets",
    "article_tickets",
    "cross_claim_votes",
})

# ---------------------------------------------------------------------------
# Reviewer pack enum values
# ---------------------------------------------------------------------------

ARTICLE_CLASSIFICATIONS: frozenset[str] = frozenset({
    "analysis",
    "advocacy",
    "propaganda-patterned advocacy",
    "mixed",
    "uncertain",
})

# Classifications that require uncertainty_basis + check_scope in the pack
UNCERTAIN_CLASSIFICATIONS: frozenset[str] = frozenset({"uncertain"})

CLAIM_TYPES: frozenset[str] = frozenset({
    "factual",
    "causal",
    "normative",
    "predictive",
})

VOTE_VALUES: frozenset[str] = frozenset({
    "supported",
    "unsupported",
    "undetermined",
})

CONFIDENCE_VALUES: frozenset[str] = frozenset({
    "low",
    "medium",
    "high",
})

# ---------------------------------------------------------------------------
# Integrity Scale (machine-mode outputs only)
# ---------------------------------------------------------------------------

INTEGRITY_SCALE: frozenset[str] = frozenset({
    "HIGH",
    "MEDIUM",
    "LOW",
})

# ---------------------------------------------------------------------------
# Verification authority rules
# ---------------------------------------------------------------------------

# Statuses whose authority_sources list is permitted to be empty.
# All other statuses (verified_true, verified_false, conflicted_sources)
# MUST have at least one authority_sources entry with a locator or url.
AUTHORITY_SOURCES_EXEMPT_STATUSES: frozenset[str] = frozenset({
    "not_checked_yet",
    "not_verifiable",
})
