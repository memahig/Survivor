"""
FILE: engine/analysis/persuasion_screen.py
VERSION: 0.1.0
PURPOSE:
Universal persuasion screen (L3) for the Epistemic Evaluation Engine.

Cheap, deterministic detection of persuasive structural signals in raw text.
L3 is a smoke detector, not an investigator.

CONSTRAINTS:
- Deterministic only. No AI.
- No motive inference.
- No propaganda labels.
- No functional mode guess.
- No deep PEG.
- No article-quality verdict.

BLUEPRINT: ARCHITECTURE_BLUEPRINT_v0.2 — Layer L3.
LOGIC BLUEPRINT: STAGE2_LOGIC_BLUEPRINT.md
BUILD MANIFEST: Stage 2 — Universal Persuasion Screen.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from engine.core.mode_types import ModeResult


# ── provisional thresholds (centralized for tuning) ──────────────────

_T1 = 2.0                  # low/moderate boundary
_T2 = 5.0                  # moderate/high boundary
_HIGH_SIGNAL_THRESHOLD = 3.0  # single signal contradiction threshold
_CONTRADICTION_DETECTOR_COUNT = 3  # multi-family contradiction threshold
_MIN_PATTERN_COUNT = 2      # minimum hits for a detector to fire
_BASE_WEIGHT = 1.5          # default signal weight
_STRONG_WEIGHT = 2.0        # weight for strong signal density


# ── data types ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class PersuasionSignal:
    """A single persuasion signal from the L3 scanner."""
    name: str
    weight: float
    evidence: str
    family: str


@dataclass(frozen=True)
class PersuasionResult:
    """Output of the universal persuasion screen (L3)."""
    heat_level: str             # low | moderate | high
    heat_score: float           # aggregate weighted scanner score
    signals: list[PersuasionSignal] = field(default_factory=list)
    is_clean_candidate: bool = True
    detector_count: int = 0


# ── public API ───────────────────────────────────────────────────────

def scan_persuasion(
    text: str,
    title: str = "",
    mode_result: Optional[ModeResult] = None,
) -> PersuasionResult:
    """Run the universal persuasion screen on a text object.

    Args:
        text:        The body text of the article/object.
        title:       Optional title (used for signal detection).
        mode_result: Optional Stage 1 ModeResult (reserved for future
                     mode-aware weighting; not used in Stage 2).

    Returns:
        PersuasionResult with heat_level, heat_score, signals, etc.
    """
    normalized = _normalize(title=title, text=text)

    score_map: Dict[str, float] = defaultdict(float)
    signals: List[PersuasionSignal] = []
    families_fired: set[str] = set()

    for detector in _DETECTORS:
        detector(normalized, score_map, signals, families_fired)

    heat_score = sum(score_map.values())
    heat_level = _heat_level(heat_score)
    detector_count = len(families_fired)

    is_clean_candidate = _assess_clean_candidate(
        heat_level=heat_level,
        signals=signals,
        detector_count=detector_count,
        families_fired=families_fired,
    )

    return PersuasionResult(
        heat_level=heat_level,
        heat_score=round(heat_score, 3),
        signals=signals,
        is_clean_candidate=is_clean_candidate,
        detector_count=detector_count,
    )


# ── text normalization ───────────────────────────────────────────────

def _normalize(title: str, text: str) -> str:
    combined = f"{title.strip()}\n{text.strip()}".strip().lower()
    return re.sub(r"\s+", " ", combined)


# ── pattern helpers ──────────────────────────────────────────────────

def _count_pattern(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def _add_signal(
    family: str,
    name: str,
    weight: float,
    evidence: str,
    score_map: Dict[str, float],
    signals: List[PersuasionSignal],
    families_fired: set[str],
) -> None:
    score_map[family] += weight
    families_fired.add(family)
    signals.append(PersuasionSignal(
        name=name, weight=weight, evidence=evidence, family=family,
    ))


# ── detector families ────────────────────────────────────────────────

def _detect_certainty_escalation(
    text: str,
    score_map: Dict,
    signals: List,
    families_fired: set,
) -> None:
    """4.1 — Language that inflates confidence beyond evidence."""
    count = _count_pattern(
        text,
        r"\b(without question|undeniably|the fact is|it is certain|"
        r"beyond doubt|unquestionably|irrefutable|indisputable|"
        r"there is no doubt|beyond any doubt|incontrovertible|"
        r"no reasonable person|it is clear that|plainly obvious)\b",
    )
    if count >= _MIN_PATTERN_COUNT:
        weight = _STRONG_WEIGHT if count >= 3 else _BASE_WEIGHT
        _add_signal(
            "certainty_escalation", "certainty_inflation", weight,
            f"{count} certainty-escalation markers detected.",
            score_map, signals, families_fired,
        )


def _detect_moral_loading(
    text: str,
    score_map: Dict,
    signals: List,
    families_fired: set,
) -> None:
    """4.2 — Ethical/moral framing injected into non-ethical context."""
    count = _count_pattern(
        text,
        r"\b(shameful|heroic|unconscionable|disgraceful|righteous|"
        r"moral obligation|morally bankrupt|virtuous|despicable|"
        r"sacred duty|betrayal of|moral imperative|reprehensible|"
        r"duty to protect|moral failing)\b",
    )
    if count >= _MIN_PATTERN_COUNT:
        weight = _STRONG_WEIGHT if count >= 3 else _BASE_WEIGHT
        _add_signal(
            "moral_loading", "moral_vocabulary", weight,
            f"{count} moral-loading markers detected.",
            score_map, signals, families_fired,
        )


def _detect_existential_framing(
    text: str,
    score_map: Dict,
    signals: List,
    families_fired: set,
) -> None:
    """4.3 — Stakes escalated to survival/catastrophe level."""
    count = _count_pattern(
        text,
        r"\b(existential threat|point of no return|survival of|"
        r"collapse of|future generations|civilization|extinction|"
        r"end of an era|catastrophic failure|irreversible damage|"
        r"no turning back|annihilation|before it is too late|"
        r"tipping point|brink of)\b",
    )
    if count >= _MIN_PATTERN_COUNT:
        weight = _STRONG_WEIGHT if count >= 3 else _BASE_WEIGHT
        _add_signal(
            "existential_framing", "existential_stakes", weight,
            f"{count} existential-framing markers detected.",
            score_map, signals, families_fired,
        )


def _detect_authority_substitution(
    text: str,
    score_map: Dict,
    signals: List,
    families_fired: set,
) -> None:
    """4.4 — Appeals to authority used in place of evidence."""
    count = _count_pattern(
        text,
        r"\b(experts agree|scientists say|studies show|research proves|"
        r"according to experts|leading authorities|top scientists|"
        r"scholars confirm|all researchers|the science is clear|"
        r"the evidence is clear|experts have concluded|"
        r"renowned experts|it has been proven)\b",
    )
    if count >= _MIN_PATTERN_COUNT:
        weight = _STRONG_WEIGHT if count >= 3 else _BASE_WEIGHT
        _add_signal(
            "authority_substitution", "authority_appeal", weight,
            f"{count} authority-substitution markers detected.",
            score_map, signals, families_fired,
        )


def _detect_directional_persuasion(
    text: str,
    score_map: Dict,
    signals: List,
    families_fired: set,
) -> None:
    """4.5 — Normative pressure toward a specific conclusion."""
    count = _count_pattern(
        text,
        r"\b(we must|it is essential|the only way|should immediately|"
        r"we need to act|ought to demand|cannot afford to|"
        r"it is imperative|we are obligated|there is no alternative|"
        r"must be stopped|demand action|reject this|"
        r"time to act|we cannot stand by)\b",
    )
    if count >= _MIN_PATTERN_COUNT:
        weight = _STRONG_WEIGHT if count >= 3 else _BASE_WEIGHT
        _add_signal(
            "directional_persuasion", "normative_pressure", weight,
            f"{count} directional-persuasion markers detected.",
            score_map, signals, families_fired,
        )


def _detect_universalization(
    text: str,
    score_map: Dict,
    signals: List,
    families_fired: set,
) -> None:
    """4.6 — Selected examples treated as universal truths."""
    count = _count_pattern(
        text,
        r"\b(everyone knows|all experts|no one disputes|"
        r"without exception|in every case|universally accepted|"
        r"no serious person|any reasonable person|it is universally|"
        r"the entire world|all people agree|nobody disagrees)\b",
    )
    if count >= _MIN_PATTERN_COUNT:
        weight = _STRONG_WEIGHT if count >= 3 else _BASE_WEIGHT
        _add_signal(
            "universalization", "scope_inflation", weight,
            f"{count} universalization markers detected.",
            score_map, signals, families_fired,
        )


def _detect_tonal_drift(
    text: str,
    score_map: Dict,
    signals: List,
    families_fired: set,
) -> None:
    """4.7 — Shifts in register from neutral to charged.

    Minimal implementation for Stage 2: compares charged-word density
    between the first and second halves of the text. If the second half
    is substantially more charged, flags tonal drift.
    """
    if len(text) < 200:
        return

    midpoint = len(text) // 2
    first_half = text[:midpoint]
    second_half = text[midpoint:]

    charged_pattern = (
        r"\b(outrageous|shocking|alarming|devastating|catastrophic|"
        r"disgraceful|unacceptable|terrifying|horrifying|appalling|"
        r"unconscionable|shameful|reprehensible|despicable|"
        r"monstrous|obscene|intolerable)\b"
    )

    first_count = _count_pattern(first_half, charged_pattern)
    second_count = _count_pattern(second_half, charged_pattern)

    # Drift = second half has meaningfully more charged language
    if second_count >= 3 and second_count > first_count + 2:
        _add_signal(
            "tonal_drift", "register_shift", _BASE_WEIGHT,
            f"Charged vocabulary: {first_count} (first half) vs "
            f"{second_count} (second half).",
            score_map, signals, families_fired,
        )


# ── detector registry ────────────────────────────────────────────────

_DETECTORS = [
    _detect_certainty_escalation,
    _detect_moral_loading,
    _detect_existential_framing,
    _detect_authority_substitution,
    _detect_directional_persuasion,
    _detect_universalization,
    _detect_tonal_drift,
]


# ── scoring ──────────────────────────────────────────────────────────

def _heat_level(score: float) -> str:
    if score >= _T2:
        return "high"
    if score >= _T1:
        return "moderate"
    return "low"


def _assess_clean_candidate(
    heat_level: str,
    signals: List[PersuasionSignal],
    detector_count: int,
    families_fired: set[str],
) -> bool:
    """Determine if L3 found any scanner-level reason to block early termination."""
    # Must be low heat
    if heat_level != "low":
        return False

    # Any single high-weight signal is a contradiction
    for signal in signals:
        if signal.weight >= _HIGH_SIGNAL_THRESHOLD:
            return False

    # Tonal drift detected is always a contradiction
    if "tonal_drift" in families_fired:
        return False

    # Multiple weak families firing together
    if detector_count >= _CONTRADICTION_DETECTOR_COUNT:
        return False

    return True
