"""
FILE: engine/analysis/mode_normalizer.py
VERSION: 0.1.0
PURPOSE:
Canonicalize mode labels from deterministic classifiers or reviewer/model outputs.

CONTRACT:
- Fail closed to "uncertain"
- Map aliases to doctrinal mode names
- Normalize formal submode
- Resolve PEG scope from canonical mode

BLUEPRINT: ARCHITECTURE_BLUEPRINT_v0.2 — Layer L2 support.
BUILD MANIFEST: Stage 1 — Mode Spine.
"""

from __future__ import annotations

from engine.core.mode_constants import (
    FORMAL_SUBMODES,
    MODE_ALIASES,
    PEG_SCOPE,
    VALID_MODES,
)
from engine.core.mode_types import NormalizedMode


def normalize_mode(
    raw_mode: str | None,
    raw_formal_submode: str | None = None,
) -> NormalizedMode:
    """Canonicalize a raw mode string into a validated NormalizedMode.

    Args:
        raw_mode:           Raw mode string from classifier or reviewer.
        raw_formal_submode: Raw formal submode string (only relevant for formal mode).

    Returns:
        NormalizedMode with canonical mode, submode, PEG scope, and uncertainty flag.
    """
    mode = _canonicalize_mode(raw_mode)
    formal_submode = _canonicalize_formal_submode(raw_formal_submode, mode)

    return NormalizedMode(
        mode=mode,
        formal_submode=formal_submode,
        peg_scope=PEG_SCOPE.get(mode, "limited"),
        is_uncertain=(mode == "uncertain"),
    )


def _canonicalize_mode(raw_mode: str | None) -> str:
    if not raw_mode:
        return "uncertain"

    token = _clean(raw_mode)

    # Direct match first
    if token in VALID_MODES:
        return token

    # Alias lookup
    token = MODE_ALIASES.get(token, token)
    if token in VALID_MODES:
        return token

    # Fail closed
    return "uncertain"


def _canonicalize_formal_submode(
    raw_formal_submode: str | None,
    mode: str,
) -> str:
    if mode != "formal":
        return "none"

    if not raw_formal_submode:
        return "none"

    token = _clean(raw_formal_submode)

    if token in FORMAL_SUBMODES:
        return token

    # Common aliases
    if token in {"math", "mathematical"}:
        return "mathematics"

    return "none"


def _clean(value: str) -> str:
    """Lowercase, strip, replace hyphens/spaces with underscores."""
    return value.strip().lower().replace("-", "_").replace(" ", "_")
