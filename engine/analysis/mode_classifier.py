"""
FILE: engine/analysis/mode_classifier.py
VERSION: 0.1.0
PURPOSE:
Deterministic presented-mode classifier for BiasLens / Survivor.

NOTES:
- This module classifies PRESENTED mode only.
- Functional mode and camouflage detection are performed later through
  reviewer analysis + adjudication (L6/L7).
- Fail-closed to "uncertain" when signal strength is weak or conflicting.
- Uses weighted signal system, not if/else chains.
- No external dependencies. No AI. Deterministic.

BLUEPRINT: ARCHITECTURE_BLUEPRINT_v0.2 — Layer L2.
BUILD MANIFEST: Stage 1 — Mode Spine.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List

from engine.core.mode_constants import VALID_MODES
from engine.core.mode_types import (
    ConfidenceLabel,
    FormalSubmode,
    ModeName,
    ModeResult,
    ModeSignal,
)


# ── minimum score to avoid uncertain ──────────────────────────────────

_MIN_SCORE_THRESHOLD = 1.5


# ── public API ────────────────────────────────────────────────────────

def classify_mode(text: str, title: str = "") -> ModeResult:
    """Classify the presented epistemic mode of a text object.

    Args:
        text:  The body text of the article/object.
        title: Optional title (used for signal detection, not required).

    Returns:
        ModeResult with presented_mode, confidence, signals, etc.
    """
    normalized = _normalize_text(title=title, text=text)

    score_map: Dict[str, float] = defaultdict(float)
    signals: List[ModeSignal] = []

    for detector in _DETECTORS:
        detector(normalized, score_map, signals)

    presented_mode, top_score, second_score = _pick_mode(score_map)
    confidence = _compute_confidence(top_score, second_score)
    confidence_label = _confidence_label(confidence)
    formal_submode = _classify_formal_submode(normalized, presented_mode)

    # Fail closed: insufficient signal strength → uncertain
    if top_score < _MIN_SCORE_THRESHOLD:
        presented_mode = "uncertain"
        confidence = 0.2
        confidence_label = "low"

    requires_reviewer_confirm = (
        presented_mode == "uncertain"
        or confidence < 0.75
    )

    notes = None
    if presented_mode == "uncertain":
        notes = (
            "Insufficient or conflicting surface signals for "
            "deterministic classification."
        )

    # Only report signals with meaningful weight
    filtered_signals = [s for s in signals if s.weight >= 0.5]

    return ModeResult(
        presented_mode=presented_mode,
        confidence=round(confidence, 3),
        confidence_label=confidence_label,
        formal_submode=formal_submode,
        signals=filtered_signals,
        requires_reviewer_confirm=requires_reviewer_confirm,
        notes=notes,
    )


# ── text normalization ────────────────────────────────────────────────

def _normalize_text(title: str, text: str) -> str:
    combined = f"{title.strip()}\n{text.strip()}".strip().lower()
    return re.sub(r"\s+", " ", combined)


# ── signal helpers ────────────────────────────────────────────────────

def _count_pattern(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def _add_signal(
    mode: str,
    name: str,
    weight: float,
    evidence: str,
    score_map: Dict[str, float],
    signals: List[ModeSignal],
) -> None:
    if mode not in VALID_MODES:
        return
    score_map[mode] += weight
    signals.append(ModeSignal(name=name, weight=weight, evidence=evidence))


# ── mode-specific signal detectors ────────────────────────────────────

def _detect_witness(text: str, score_map: Dict, signals: List) -> None:
    count = _count_pattern(
        text,
        r"\b(said|told|according to|reported|reports|confirmed|"
        r"officials said|police said|sources say|a spokesperson)\b",
    )
    if count >= 3:
        _add_signal(
            "witness", "attribution_density", 2.0,
            f"{count} attribution markers detected.",
            score_map, signals,
        )
    elif count >= 2:
        _add_signal(
            "witness", "attribution_density", 1.5,
            f"{count} attribution markers detected.",
            score_map, signals,
        )


def _detect_proof(text: str, score_map: Dict, signals: List) -> None:
    count = _count_pattern(
        text,
        r"\b(study|data|results|method|methods|sample|dataset|"
        r"analysis|figure|table|findings|experiment|hypothesis|"
        r"participants|statistically significant)\b",
    )
    if count >= 3:
        _add_signal(
            "proof", "empirical_structure", 2.0,
            f"{count} empirical/research vocabulary terms detected.",
            score_map, signals,
        )
    elif count >= 2:
        _add_signal(
            "proof", "empirical_structure", 1.5,
            f"{count} empirical/research vocabulary terms detected.",
            score_map, signals,
        )


def _detect_rule(text: str, score_map: Dict, signals: List) -> None:
    count = _count_pattern(
        text,
        r"\b(statute|rule|policy|regulation|court|burden|standard|"
        r"compliance|procedure|pursuant|jurisdiction|ruling|"
        r"verdict|ordinance|amendment)\b",
    )
    if count >= 3:
        _add_signal(
            "rule", "procedural_language", 2.0,
            f"{count} legal/procedural vocabulary terms detected.",
            score_map, signals,
        )
    elif count >= 2:
        _add_signal(
            "rule", "procedural_language", 1.5,
            f"{count} legal/procedural vocabulary terms detected.",
            score_map, signals,
        )


def _detect_explanation(text: str, score_map: Dict, signals: List) -> None:
    count = _count_pattern(
        text,
        r"\b(because|why|how|explains|reason|caused by|driven by|"
        r"as a result|contributing factor|leads to|due to)\b",
    )
    if count >= 3:
        _add_signal(
            "explanation", "causal_framing", 1.75,
            f"{count} causal/explanatory markers detected.",
            score_map, signals,
        )
    elif count >= 2:
        _add_signal(
            "explanation", "causal_framing", 1.25,
            f"{count} causal/explanatory markers detected.",
            score_map, signals,
        )


def _detect_argument(text: str, score_map: Dict, signals: List) -> None:
    count = _count_pattern(
        text,
        r"\b(should|must|therefore|clearly|obviously|ought|"
        r"proves that|we need to|it is essential|without question|"
        r"undeniably|the only way)\b",
    )
    if count >= 3:
        _add_signal(
            "argument", "directional_persuasion", 2.0,
            f"{count} normative/directional language markers detected.",
            score_map, signals,
        )
    elif count >= 2:
        _add_signal(
            "argument", "directional_persuasion", 1.5,
            f"{count} normative/directional language markers detected.",
            score_map, signals,
        )


def _detect_experience(text: str, score_map: Dict, signals: List) -> None:
    count = _count_pattern(
        text,
        r"\b(i was|i am|my life|i remember|i saw|i felt|"
        r"i thought|i knew|i realized|we lived|my family)\b",
    )
    if count >= 3:
        _add_signal(
            "experience", "first_person_narrative", 2.0,
            f"{count} first-person lived-experience markers detected.",
            score_map, signals,
        )
    elif count >= 2:
        _add_signal(
            "experience", "first_person_narrative", 1.5,
            f"{count} first-person lived-experience markers detected.",
            score_map, signals,
        )


def _detect_record(text: str, score_map: Dict, signals: List) -> None:
    count = _count_pattern(
        text,
        r"\b(entry|reference|catalog|archived|date of|born|"
        r"located|definition|see also|index|glossary|appendix)\b",
    )
    if count >= 3:
        _add_signal(
            "record", "reference_structure", 1.75,
            f"{count} reference/catalog language markers detected.",
            score_map, signals,
        )
    elif count >= 2:
        _add_signal(
            "record", "reference_structure", 1.25,
            f"{count} reference/catalog language markers detected.",
            score_map, signals,
        )


def _detect_voice(text: str, score_map: Dict, signals: List) -> None:
    count = _count_pattern(
        text,
        r"\b(official statement|press release|we believe|"
        r"our organization|on behalf of|we are committed|"
        r"our mission|we remain|our position|the company)\b",
    )
    if count >= 1:
        _add_signal(
            "voice", "institutional_framing", 2.0,
            f"{count} institutional voice marker(s) detected.",
            score_map, signals,
        )


def _detect_formal(text: str, score_map: Dict, signals: List) -> None:
    keyword_count = _count_pattern(
        text,
        r"\b(theorem|lemma|proof|corollary|axiom|proposition|"
        r"definition|conjecture|qed|premise|conclusion|syllogism|"
        r"modus ponens|modus tollens|deduction|inference)\b",
    )
    symbol_count = _count_pattern(
        text,
        r"(=>|->|∴|∀|∃|∈|∑|√|≤|≥|⊂|⊃|∧|∨|¬)",
    )
    total = keyword_count + symbol_count
    if total >= 3:
        _add_signal(
            "formal", "formal_structure", 2.5,
            f"{keyword_count} formal keywords + {symbol_count} symbols detected.",
            score_map, signals,
        )
    elif total >= 2:
        _add_signal(
            "formal", "formal_structure", 2.0,
            f"{keyword_count} formal keywords + {symbol_count} symbols detected.",
            score_map, signals,
        )


# ── detector registry ─────────────────────────────────────────────────

_DETECTORS = [
    _detect_witness,
    _detect_proof,
    _detect_rule,
    _detect_explanation,
    _detect_argument,
    _detect_experience,
    _detect_record,
    _detect_voice,
    _detect_formal,
]


# ── scoring ───────────────────────────────────────────────────────────

def _pick_mode(
    score_map: Dict[str, float],
) -> tuple[ModeName, float, float]:
    if not score_map:
        return "uncertain", 0.0, 0.0
    ranked = sorted(score_map.items(), key=lambda kv: kv[1], reverse=True)
    top_mode, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    return top_mode, top_score, second_score


def _compute_confidence(top_score: float, second_score: float) -> float:
    if top_score <= 0:
        return 0.0
    margin = top_score - second_score
    return min(1.0, 0.45 + 0.15 * top_score + 0.12 * margin)


def _confidence_label(confidence: float) -> ConfidenceLabel:
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.60:
        return "medium"
    return "low"


def _classify_formal_submode(
    text: str, presented_mode: str,
) -> FormalSubmode:
    if presented_mode != "formal":
        return "none"

    logic_hits = _count_pattern(
        text,
        r"\b(premise|conclusion|valid|invalid|syllogism|"
        r"modus ponens|modus tollens|deduction|inference)\b",
    )
    math_hits = _count_pattern(
        text,
        r"\b(integer|prime|function|theorem|lemma|corollary|"
        r"sequence|matrix|proof|polynomial|derivative|integral)\b",
    )

    if math_hits > logic_hits:
        return "mathematics"
    if logic_hits > math_hits:
        return "logic"
    return "none"
