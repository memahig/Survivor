#!/usr/bin/env python3
"""
FILE: engine/core/spine_builder.py
VERSION: 0.1
PURPOSE:
Build a cross-reviewer merged argument spine from triage outputs.

The spine is fed to enrichment (Pass 2) so each reviewer sees what
ALL reviewers found, not just its own triage.

CONTRACT:
- Pure function, no I/O, deterministic.
- Input: dict of {reviewer_name: triage_pack}
- Output: merged spine dict with pillar_claims, main_conclusion, etc.
"""

from __future__ import annotations

from typing import Any, Dict, List


def build_argument_spine(triage_outputs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge triage outputs from all reviewers into a cross-reviewer argument spine.

    The spine contains:
    - main_conclusion: the longest main_conclusion text across reviewers
    - pillar_claims: union of all pillar_claims (preserving reviewer prefixes)
    - questionable_claims: union of all questionable_claims
    """
    all_pillar: List[Dict[str, Any]] = []
    all_questionable: List[Dict[str, Any]] = []
    best_conclusion: Dict[str, Any] = {}
    best_conclusion_len = 0

    for _reviewer, pack in sorted(triage_outputs.items()):
        if not isinstance(pack, dict):
            continue

        # Pillar claims
        for c in pack.get("pillar_claims", []):
            if isinstance(c, dict):
                all_pillar.append(c)

        # Questionable claims
        for c in pack.get("questionable_claims", []):
            if isinstance(c, dict):
                all_questionable.append(c)

        # Main conclusion — keep the longest
        mc = pack.get("main_conclusion")
        if isinstance(mc, dict):
            text = mc.get("text", "")
            if isinstance(text, str) and len(text) > best_conclusion_len:
                best_conclusion = mc
                best_conclusion_len = len(text)

    return {
        "main_conclusion": best_conclusion,
        "pillar_claims": all_pillar,
        "questionable_claims": all_questionable,
    }
