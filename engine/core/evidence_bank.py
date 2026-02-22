#!/usr/bin/env python3
"""
FILE: engine/core/evidence_bank.py
VERSION: 0.1
PURPOSE:
Build a deterministic EvidenceBank from normalized article text.

v0 RULE (deliberately simple + auditable):
- Split on non-empty lines (not sentences) to avoid NLP ambiguity.
- Each line becomes one EvidenceItem with eid E1..En.
- Enforce max_chars cap (stop adding items when cap would be exceeded).
"""

from __future__ import annotations

from typing import Any, Dict, List


def build_evidence_bank(normalized_text: str, config: Dict[str, Any]) -> Dict[str, Any]:
    max_chars = int(config.get("max_chars", 2400))

    # Split into deterministic chunks: non-empty lines
    raw_lines = normalized_text.splitlines()
    chunks: List[str] = []
    for ln in raw_lines:
        s = ln.strip()
        if s:
            chunks.append(s)

    items: List[Dict[str, Any]] = []
    used = 0

    for i, text in enumerate(chunks, start=1):
        # Count with newline separation (auditable, stable)
        add_len = len(text) + (1 if items else 0)
        if used + add_len > max_chars:
            break

        used += add_len
        items.append(
            {
                "eid": f"E{i}",
                "text": text,
                "char_len": len(text),
            }
        )

    return {
        "items": items,
        "used_chars": used,
        "max_chars": max_chars,
    }