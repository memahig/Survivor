"""
FILE: engine/core/mode_constants.py
VERSION: 0.1.0
PURPOSE:
Constants and doctrine mappings for epistemic modes.

DOCTRINE: BiasLens Doctrine v1.1 — 9 core modes (expandable).
BLUEPRINT: ARCHITECTURE_BLUEPRINT_v0.2 — Layer L2.
"""

from __future__ import annotations

# --- 9 core epistemic modes + uncertain fallback ---

MODE_IDS: dict[str, int] = {
    "witness": 1,       # Attribution-bound
    "proof": 2,         # Evidence-bound (empirical)
    "rule": 3,          # Procedure-bound
    "explanation": 4,   # Explanation-bound
    "argument": 5,      # Advocacy-bound
    "experience": 6,    # Narrative-bound
    "record": 7,        # Reference-bound
    "voice": 8,         # Institutional-bound
    "formal": 9,        # Deduction-bound (logic, mathematics)
    "uncertain": 0,     # Fail-closed default
}

VALID_MODES: set[str] = set(MODE_IDS.keys())

MODE_NAMES_BY_ID: dict[int, str] = {v: k for k, v in MODE_IDS.items()}

# --- PEG scope per mode (doctrine-aligned) ---

PEG_SCOPE: dict[str, str] = {
    "witness": "limited",
    "proof": "standard",
    "rule": "limited",
    "explanation": "full",
    "argument": "full",
    "experience": "minimal",
    "record": "limited",
    "voice": "full",
    "formal": "standard",
    "uncertain": "limited",
}

VALID_PEG_SCOPES: set[str] = {"full", "standard", "limited", "minimal"}

# --- Formal submodes ---

FORMAL_SUBMODES: set[str] = {"logic", "mathematics", "none"}

# --- Mode alias map (for normalizer / drift firewall) ---

MODE_ALIASES: dict[str, str] = {
    "news": "witness",
    "reporting": "witness",
    "journalism": "witness",
    "research": "proof",
    "scientific": "proof",
    "empirical": "proof",
    "legal": "rule",
    "regulatory": "rule",
    "procedural": "rule",
    "analysis": "explanation",
    "explainer": "explanation",
    "opinion": "argument",
    "editorial": "argument",
    "advocacy": "argument",
    "persuasion": "argument",
    "memoir": "experience",
    "personal": "experience",
    "testimony": "experience",
    "reference": "record",
    "encyclopedia": "record",
    "catalog": "record",
    "institutional": "voice",
    "press_release": "voice",
    "official": "voice",
    "math": "formal",
    "mathematics": "formal",
    "logic": "formal",
    "deductive": "formal",
}
