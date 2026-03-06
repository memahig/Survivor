#!/usr/bin/env python3
"""
FILE: engine/core/triage_utils.py
VERSION: 0.1.0
PURPOSE:
Small helpers for triage-claim iteration to avoid duplicate logic and
reduce circular-import risk between translator/adjudicator/renderers.

CONTRACT:
- iter_triage_claims yields pillar_claims first, then questionable_claims.
- Defensive: ignores non-dict items and missing keys.
- No I/O, no global state, deterministic.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List


def iter_triage_claims(pack: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """
    Yields all triage-eligible claims in deterministic order:
      pillar_claims first, then questionable_claims.

    Defensive: skips non-dict items, entries missing claim_id,
    and entries with blank/non-string claim_id.
    """
    for list_key in ("pillar_claims", "questionable_claims"):
        items = pack.get(list_key)
        if not isinstance(items, list):
            continue
        for c in items:
            if not isinstance(c, dict):
                continue
            cid = c.get("claim_id")
            if not isinstance(cid, str) or not cid.strip():
                continue
            yield c


def list_triage_claims(pack: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convenience wrapper (sometimes easier for existing call sites)."""
    return list(iter_triage_claims(pack))
