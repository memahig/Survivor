#!/usr/bin/env python3
"""
FILE: survivor/reviewers/claude_reviewer.py
VERSION: 0.1
PURPOSE:
Claude (Anthropic) reviewer adapter for Survivor.

NOTE:
- Network/API code intentionally not implemented yet.
- This module will expose the same interface as other reviewers.
"""

from __future__ import annotations

from typing import Any, Dict
from survivor.reviewers.base import Reviewer, ReviewerInputs


class ClaudeReviewer:
    name = "claude"

    def run_phase1(self, inp: ReviewerInputs) -> Dict[str, Any]:
        raise NotImplementedError("Claude API adapter not implemented yet.")

    def run_phase2(self, inp: ReviewerInputs, cross_review_payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Claude API adapter not implemented yet.")