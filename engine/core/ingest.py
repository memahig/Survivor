#!/usr/bin/env python3
"""
FILE: engine/core/ingest.py
VERSION: 0.1
PURPOSE:
Ingest input article text from either a URL (future) or local textfile (v0).

CONTRACT:
- ingest_input(url, textfile) returns dict:
    {
      "id": str,
      "source_url": Optional[str],
      "title": Optional[str],
      "text": str
    }
- Fail closed if neither or both are provided.
- v0 supports textfile only. URL ingestion will be added later.
"""

from __future__ import annotations

import hashlib
from typing import Optional, Dict, Any


def _stable_id(text: str) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"A-{h}"


def ingest_input(url: Optional[str], textfile: Optional[str]) -> Dict[str, Any]:
    if bool(url) == bool(textfile):
        raise RuntimeError("Provide exactly one of --url or --textfile")

    if textfile:
        with open(textfile, "r", encoding="utf-8") as f:
            text = f.read().strip()
        if not text:
            raise RuntimeError("textfile is empty")
        return {
            "id": _stable_id(text),
            "source_url": None,
            "title": None,
            "text": text,
        }

    # url path (not implemented yet)
    raise NotImplementedError("URL ingestion not implemented yet (v0 supports --textfile only).")