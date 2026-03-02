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

# Optional keys permitted (but not required) in a ReviewerPack dict.
# Fail closed: any key not in REQUIRED | OPTIONAL is rejected.
REVIEWER_PACK_OPTIONAL_KEYS: frozenset[str] = frozenset({
    "gsae_observation",
    "gsae_subject",
})

# ---------------------------------------------------------------------------
# Reviewer pack enum values
# ---------------------------------------------------------------------------

ARTICLE_CLASSIFICATIONS: frozenset[str] = frozenset({
    "reporting",
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
# GSAE — Tier C Symmetry Constants
# ---------------------------------------------------------------------------

# Structural rhetorical mode — MUST remain disjoint from ARTICLE_CLASSIFICATIONS.
CLASSIFICATION_BUCKET_VALUES: frozenset[str] = frozenset({
    "reporting",
    "interpretive",
    "normative",
    "mobilizing",
    "ambiguous",
})

# Ordinal scale for severity (index position determines distance).
# Immutable tuple: order is load-bearing.
SEVERITY_TIER_VALUES_ORDERED: tuple[str, ...] = (
    "minimal",
    "moderate",
    "elevated",
    "high",
    "critical",
)

# Ordinal scale for symmetry confidence band.
# Prefixed sb_* to avoid collision with CONFIDENCE_VALUES.
# Immutable tuple: order is load-bearing.
SYMMETRY_BAND_VALUES_ORDERED: tuple[str, ...] = (
    "sb_low",
    "sb_mid",
    "sb_high",
    "sb_max",
)

# Tier C v0.2 base symmetry field set (legacy undirected).
# Membership set — order is not load-bearing.
SYMMETRY_FIELDS_BASE: frozenset[str] = frozenset({
    "classification_bucket",
    "intent_level",
    "requires_corrob",
    "omission_load_bearing",
    "severity_tier",
    "confidence_band",
})

# Tier C v0.3 directional symmetry field set.
# Replaces severity_tier with directional pair.
SYMMETRY_FIELDS_V03: frozenset[str] = frozenset({
    "classification_bucket",
    "intent_level",
    "requires_corrob",
    "omission_load_bearing",
    "severity_toward_subject",
    "severity_toward_counterparty",
    "confidence_band",
})

# Union of all known symmetry fields across versions.
SYMMETRY_FIELDS_ALL: frozenset[str] = SYMMETRY_FIELDS_BASE | SYMMETRY_FIELDS_V03

# Symmetry status zones (output-only).
SYMMETRY_STATUS_VALUES: frozenset[str] = frozenset({
    "UNKNOWN",
    "PASS",
    "SOFT_FLAG",
    "QUARANTINE",
})

# ---------------------------------------------------------------------------
# GSAE — Required key sets (distinct from field sets by design)
# ---------------------------------------------------------------------------

# Keys required in a GSAESymmetryPacket dict.
# Equal to SYMMETRY_FIELDS_BASE today; may diverge if packet gains metadata fields.
GSAE_SYMMETRY_PACKET_REQUIRED_KEYS: frozenset[str] = frozenset({
    "classification_bucket",
    "intent_level",
    "requires_corrob",
    "omission_load_bearing",
    "severity_tier",
    "confidence_band",
})

# Keys required in a v0.3 directional GSAESymmetryPacket dict.
# Replaces severity_tier with directional severity pair.
GSAE_SYMMETRY_PACKET_V03_REQUIRED_KEYS: frozenset[str] = frozenset({
    "classification_bucket",
    "intent_level",
    "requires_corrob",
    "omission_load_bearing",
    "severity_toward_subject",
    "severity_toward_counterparty",
    "confidence_band",
})

# Keys required in a GSAESettings dict.
GSAE_SETTINGS_REQUIRED_KEYS: frozenset[str] = frozenset({
    "enabled",
    "epsilon",
    "tau",
    "weights",
    "version",
})

# Keys required in a GSAESymmetryArtifact dict.
GSAE_ARTIFACT_REQUIRED_KEYS: frozenset[str] = frozenset({
    "symmetry_status",
    "delta",
    "epsilon",
    "tau",
    "soft_symmetry_flag",
    "quarantine_fields",
    "field_deltas",
    "notes",
})

# Keys required in a GSAESubject dict (identity metadata for swap transform).
# All fields are non-empty str. counterparty_label uses "unspecified" when none.
GSAE_SUBJECT_REQUIRED_KEYS: frozenset[str] = frozenset({
    "subject_label",
    "subject_role",
    "counterparty_label",
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
