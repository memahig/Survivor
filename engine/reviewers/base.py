#!/usr/bin/env python3
"""
FILE: survivor/reviewers/base.py
VERSION: 0.1
PURPOSE:
Defines the strict reviewer interface for Survivor.

CONTRACT:
- Reviewers must return JSON-serializable dicts that conform to survivor.core.schemas.
- Reviewers must NOT invent evidence ids; they may only reference provided EIDs.
- Reviewers must operate in two phases:
  (1) Phase 1: independent extraction + tickets
  (2) Phase 2: structured-only cross-review updates
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


@dataclass(frozen=True)
class ReviewerInputs:
    article_id: str
    source_url: Optional[str]
    title: Optional[str]
    normalized_text: str
    evidence_bank: Dict[str, Any]   # serialized EvidenceBank
    config: Dict[str, Any]          # loaded config.json


class Reviewer(Protocol):
    name: str  # "openai" | "gemini" | "claude"

    def run_phase1(self, inp: ReviewerInputs) -> Dict[str, Any]:
        """Independent extraction + tickets + judgments."""
        ...

    def run_phase2(self, inp: ReviewerInputs, cross_review_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Structured-only updates to phase1 outputs based on disagreement summaries."""
        ...