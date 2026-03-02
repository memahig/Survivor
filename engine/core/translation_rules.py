#!/usr/bin/env python3
"""
FILE: engine/core/translation_rules.py
VERSION: 1.0
PURPOSE:
Single source of truth for enum translation in the Survivor pipeline.

CONTRACT:
- LOSSLESS-ONLY alias maps: only formatting variants of the same canonical token.
- NO semantic coercions. Unknown tokens trigger repair gate, not silent mapping.
- Namespace isolation: certain tokens are forbidden in certain fields.
- No I/O, no side effects on import.

RULE (LOCKED):
  ALIAS_MAPS is lossless-only forever. Any token that is not an obvious
  formatting variant of a canonical enum must trigger repair, not mapping.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Optional, Set, Tuple

from engine.core.schema_constants import (
    ARTICLE_CLASSIFICATIONS,
    CLAIM_TYPES,
    CLASSIFICATION_BUCKET_VALUES,
    CONFIDENCE_VALUES,
    SEVERITY_TIER_VALUES_ORDERED,
    SYMMETRY_BAND_VALUES_ORDERED,
    VOTE_VALUES,
)


# ---------------------------------------------------------------------------
# Canonical enum sets, keyed by field path
# ---------------------------------------------------------------------------

CANONICAL_ENUMS: Dict[str, FrozenSet[str]] = {
    "whole_article_judgment.classification": ARTICLE_CLASSIFICATIONS,
    "whole_article_judgment.confidence": CONFIDENCE_VALUES,
    "claims.type": CLAIM_TYPES,
    "cross_claim_votes.vote": VOTE_VALUES,
    "cross_claim_votes.confidence": CONFIDENCE_VALUES,
    "gsae_observation.classification_bucket": CLASSIFICATION_BUCKET_VALUES,
    "gsae_observation.severity_toward_subject": frozenset(SEVERITY_TIER_VALUES_ORDERED),
    "gsae_observation.severity_toward_counterparty": frozenset(SEVERITY_TIER_VALUES_ORDERED),
    "gsae_observation.confidence_band": frozenset(SYMMETRY_BAND_VALUES_ORDERED),
}


# ---------------------------------------------------------------------------
# LOSSLESS-ONLY alias maps: formatting variants of the SAME canonical token.
# Case, whitespace, underscore/hyphen normalization only.
# NO semantic coercions (opinion→analysis etc. is FORBIDDEN here).
# ---------------------------------------------------------------------------

ALIAS_MAPS: Dict[str, Dict[str, str]] = {
    "whole_article_judgment.classification": {
        # "propaganda-patterned advocacy" formatting variants only
        "propaganda_patterned_advocacy": "propaganda-patterned advocacy",
        "propaganda-patterned_advocacy": "propaganda-patterned advocacy",
        "propaganda_patterned advocacy": "propaganda-patterned advocacy",
    },
    "claims.type": {
        # No lossless aliases — all 4 canonical tokens are single words.
    },
    "gsae_observation.classification_bucket": {
        # No lossless aliases — canonical tokens are single words.
    },
    "gsae_observation.severity_toward_subject": {
        # No lossless aliases — canonical tokens are single words.
    },
    "gsae_observation.severity_toward_counterparty": {
        # No lossless aliases — canonical tokens are single words.
    },
    "gsae_observation.confidence_band": {
        # sb_* hyphen variants
        "sb-low": "sb_low",
        "sb-mid": "sb_mid",
        "sb-high": "sb_high",
        "sb-max": "sb_max",
    },
}


# ---------------------------------------------------------------------------
# Namespace isolation: tokens forbidden in specific fields
# ---------------------------------------------------------------------------

FORBIDDEN_TOKENS: Dict[str, FrozenSet[str]] = {
    "whole_article_judgment.classification": CLASSIFICATION_BUCKET_VALUES,
    "gsae_observation.classification_bucket": ARTICLE_CLASSIFICATIONS,
}


# ---------------------------------------------------------------------------
# Format normalizer
# ---------------------------------------------------------------------------

def normalize_format(s: str) -> str:
    """Strip + lowercase. Does NOT replace underscores/hyphens (load-bearing)."""
    return s.strip().lower()


# ---------------------------------------------------------------------------
# Field translation
# ---------------------------------------------------------------------------

def translate_field(
    field_path: str,
    raw_value: str,
) -> Tuple[Optional[str], str, bool]:
    """
    Translate a raw enum value to canonical form.

    Returns: (canonical_value, raw_value_preserved, ok)
    - ok=True: canonical_value is valid enum member
    - ok=False: canonical_value is None, raw_value preserved for error reporting
    """
    normed = normalize_format(raw_value)

    canonical_set = CANONICAL_ENUMS.get(field_path)
    if canonical_set is None:
        # Unknown field path — pass through (not an enum-controlled field)
        return raw_value, raw_value, True

    # Direct match after normalization — canonical membership takes priority
    if normed in canonical_set:
        return normed, raw_value, True

    # Namespace isolation: block tokens from other enum families
    # (only checked for non-canonical values to avoid blocking shared tokens
    # like "reporting" which is valid in both ARTICLE_CLASSIFICATIONS and
    # CLASSIFICATION_BUCKET_VALUES)
    forbidden = FORBIDDEN_TOKENS.get(field_path)
    if forbidden is not None and normed in forbidden:
        return None, raw_value, False

    # Lossless alias lookup
    aliases = ALIAS_MAPS.get(field_path, {})
    if normed in aliases:
        return aliases[normed], raw_value, True

    # No match — translation failure
    return None, raw_value, False


# ---------------------------------------------------------------------------
# Enum contract text builder (for repair prompts)
# ---------------------------------------------------------------------------

def build_enum_contract_text() -> str:
    """Build a human-readable enum contract for repair prompts."""
    lines = ["ALLOWED ENUM VALUES:"]
    for path in sorted(CANONICAL_ENUMS.keys()):
        values = sorted(CANONICAL_ENUMS[path])
        lines.append(f"  {path}: {' | '.join(values)}")
    return "\n".join(lines)


def build_error_enum_text(field_path: str) -> str:
    """Build the allowed values string for a specific field."""
    canonical_set = CANONICAL_ENUMS.get(field_path)
    if canonical_set is None:
        return "(unknown field)"
    return " | ".join(sorted(canonical_set))
