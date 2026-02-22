#!/usr/bin/env python3
"""
FILE: engine/core/normalize.py
VERSION: 0.1
PURPOSE:
Normalize raw article text into a stable form for evidence chunking and review.

CONTRACT:
- normalize_text(text) -> str
- Deterministic
- No external dependencies
"""

from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        raise RuntimeError("normalize_text expects a string")

    # Normalize newlines
    t = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse 3+ newlines to 2
    t = re.sub(r"\n{3,}", "\n\n", t)

    # Strip trailing whitespace on each line
    t = "\n".join(line.rstrip() for line in t.split("\n"))

    # Final trim
    t = t.strip()

    return t