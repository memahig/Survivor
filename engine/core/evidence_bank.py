#!/usr/bin/env python3
"""
FILE: engine/core/evidence_bank.py
VERSION: 0.2
PURPOSE:
Build a deterministic EvidenceBank from normalized article text.

CANONICAL SCHEMA (v0.2):
Each EvidenceItem emits:
  {
    "eid":      "E12",
    "quote":    verbatim slice of normalized_text[char_start:char_end],
    "locator":  {"char_start": int, "char_end": int},
    "source_id": str,       # article-scoped identifier, e.g. "A-<hash>"
    "text":     alias of quote (transitional — prefer quote),
    "char_len": alias of len(quote) (transitional)
  }

LOCATOR DISCIPLINE:
- char_start/char_end are byte offsets into normalized_text (not raw source).
- quote MUST equal normalized_text[char_start:char_end] exactly.
- Mismatch → RuntimeError (fail-closed).

CHUNKING RULE (deterministic, auditable):
- Split on non-empty lines using splitlines(keepends=True) so positions
  in normalized_text can be tracked precisely without post-hoc recomputation.
- Each non-empty stripped line becomes one EvidenceItem with eid E1..En.
- Enforce max_chars cap (stop adding items when cap would be exceeded).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def build_evidence_bank(
    normalized_text: str,
    config: Dict[str, Any],
    source_id: str = "A1",
) -> Dict[str, Any]:
    max_chars = int(config.get("max_chars", 2400))

    # Walk normalized_text with keepends=True so we can track char positions.
    # This is the only correct way to derive locators without post-hoc recomputation.
    chunks: List[Tuple[int, int, str]] = []  # (char_start, char_end, stripped_text)

    pos = 0
    for ln in normalized_text.splitlines(keepends=True):
        stripped = ln.strip()
        if stripped:
            # Find where the stripped content begins inside this line's span.
            leading_ws = len(ln) - len(ln.lstrip())
            char_start = pos + leading_ws
            char_end = char_start + len(stripped)
            chunks.append((char_start, char_end, stripped))
        pos += len(ln)

    items: List[Dict[str, Any]] = []
    used = 0

    for i, (char_start, char_end, text) in enumerate(chunks, start=1):
        # Count with newline separation (auditable, stable)
        add_len = len(text) + (1 if items else 0)
        if used + add_len > max_chars:
            break

        # FAIL-CLOSED: verify locator reconstructs exact text before emitting.
        quote = normalized_text[char_start:char_end]
        if quote != text:
            raise RuntimeError(
                f"EvidenceBank locator mismatch at E{i}: "
                f"normalized_text[{char_start}:{char_end}]={quote!r} != {text!r}"
            )

        used += add_len
        items.append(
            {
                "eid": f"E{i}",
                "quote": quote,
                "locator": {
                    "char_start": char_start,
                    "char_end": char_end,
                },
                "source_id": source_id,
                # Transitional aliases — downstream consumers should prefer "quote"
                "text": quote,
                "char_len": len(quote),
            }
        )

    return {
        "items": items,
        "used_chars": used,
        "max_chars": max_chars,
    }
