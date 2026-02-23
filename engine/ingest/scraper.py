#!/usr/bin/env python3
"""
FILE: engine/ingest/scraper.py
VERSION: 0.1
LAST UPDATED: 2026-02-22
PURPOSE:
Hard-timeout, non-hanging URL scraper for Survivor using trafilatura.

Public API:
- scrape_url(url: str, timeout_s: int = 25) -> ScrapeResult
"""

from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional

import trafilatura


@dataclass(frozen=True)
class ScrapeResult:
    text: str
    success: bool
    error_code: Optional[str] = None  # "SCRAPE_TIMEOUT", "DOWNLOAD_FAILED", "EXTRACT_FAILED", "EXCEPTION"


def _scrape_worker(url: str) -> ScrapeResult:
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ScrapeResult(
                text="Could not download URL (possibly blocked or requires JS/login).",
                success=False,
                error_code="DOWNLOAD_FAILED",
            )

        # Conservative extraction (you can tune later)
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        if text and text.strip():
            return ScrapeResult(text=text.strip(), success=True, error_code=None)

        return ScrapeResult(
            text="Downloaded page but could not extract readable article text.",
            success=False,
            error_code="EXTRACT_FAILED",
        )
    except Exception as e:
        return ScrapeResult(text=f"Scrape exception: {e}", success=False, error_code="EXCEPTION")


def scrape_url(url: str, timeout_s: int = 25) -> ScrapeResult:
    """
    Hard-timeout protected scrape. MUST NOT hang.
    """
    try:
        with ProcessPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_scrape_worker, url)
            return fut.result(timeout=timeout_s)
    except FuturesTimeoutError:
        return ScrapeResult(
            text=f"SCRAPE_TIMEOUT: scraper exceeded {timeout_s}s (likely blocked / bot-challenge / slow network).",
            success=False,
            error_code="SCRAPE_TIMEOUT",
        )
    except Exception as e:
        return ScrapeResult(text=f"Scrape exception: {e}", success=False, error_code="EXCEPTION")