#!/usr/bin/env python3
"""
FILE: engine/core/ingest.py
VERSION: 0.2
PURPOSE:
Ingest input article text from a URL (via trafilatura) or local textfile.

CONTRACT:
- ingest_input(url, textfile) returns dict:
    {
      "id": str,
      "source_url": Optional[str],
      "title": Optional[str],
      "text": str
    }
- Fail closed if neither or both are provided.
- URL ingestion uses engine.ingest.scraper (hard-timeout, non-hanging).
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

    # url path — scrape via trafilatura
    from engine.ingest.scraper import scrape_url

    result = scrape_url(url, timeout_s=30)
    if not result.success:
        raise RuntimeError(f"URL scrape failed ({result.error_code}): {result.text}")

    text = result.text.strip()
    if not text:
        raise RuntimeError("Scraped page but got empty text")

    return {
        "id": _stable_id(text),
        "source_url": url,
        "title": None,
        "text": text,
    }