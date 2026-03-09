"""
FILE: engine/core/mode_types.py
VERSION: 0.1.0
PURPOSE:
Shared types for epistemic mode classification, normalization, and routing.

DOCTRINE: BiasLens Doctrine v1.1 — 9 core modes (expandable).
BLUEPRINT: ARCHITECTURE_BLUEPRINT_v0.2 — canonical data objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ModeName = Literal[
    "witness",
    "proof",
    "rule",
    "explanation",
    "argument",
    "experience",
    "record",
    "voice",
    "formal",
    "uncertain",
]

FormalSubmode = Literal[
    "logic",
    "mathematics",
    "none",
]

ConfidenceLabel = Literal[
    "low",
    "medium",
    "high",
]

PegScope = Literal[
    "full",
    "standard",
    "limited",
    "minimal",
]


@dataclass(frozen=True)
class ModeSignal:
    """A single structural signal contributing to mode classification."""
    name: str
    weight: float
    evidence: str


@dataclass(frozen=True)
class ModeResult:
    """Output of the deterministic presented-mode classifier (L2)."""
    presented_mode: ModeName
    confidence: float
    confidence_label: ConfidenceLabel
    formal_submode: FormalSubmode
    signals: list[ModeSignal] = field(default_factory=list)
    requires_reviewer_confirm: bool = True
    notes: str | None = None


@dataclass(frozen=True)
class NormalizedMode:
    """Canonicalized mode after alias resolution and validation."""
    mode: ModeName
    formal_submode: FormalSubmode = "none"
    peg_scope: PegScope = "limited"
    is_uncertain: bool = False
