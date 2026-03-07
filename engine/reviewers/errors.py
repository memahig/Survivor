#!/usr/bin/env python3
"""
FILE: engine/reviewers/errors.py
PURPOSE:
Shared reviewer error classification and structured error object.

Used by:
- reviewer adapters (OpenAI / Gemini / Claude)
- pipeline orchestration
- audit reporting
"""

from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

class ErrorType(str, Enum):
    TRANSIENT = "transient"
    RATE_LIMIT = "rate_limited"
    QUOTA = "quota_exhausted"
    AUTH = "auth_failed"
    TIMEOUT = "timeout"
    REVIEWER_FAILED = "reviewer_failed"


# Types that are worth retrying at the adapter level
RETRYABLE_TYPES = frozenset({ErrorType.TRANSIENT, ErrorType.RATE_LIMIT, ErrorType.TIMEOUT})


def classify_error(e: BaseException) -> ErrorType:
    """Convert provider-specific errors into normalized ErrorType."""
    msg = str(e).lower()

    # Check status_code attribute (httpx, requests, google API errors)
    status_code = getattr(e, "status_code", None) or getattr(e, "code", None)
    if isinstance(status_code, int):
        if status_code in (429,):
            if any(p in msg for p in ("quota", "resource_exhausted", "billing")):
                return ErrorType.QUOTA
            return ErrorType.RATE_LIMIT
        if status_code in (500, 502, 503, 504):
            return ErrorType.TRANSIENT
        if status_code in (401, 403):
            return ErrorType.AUTH

    if "quota" in msg or "resource_exhausted" in msg or "billing" in msg:
        return ErrorType.QUOTA

    if "rate" in msg and "limit" in msg:
        return ErrorType.RATE_LIMIT

    if "timeout" in msg or "timed out" in msg:
        return ErrorType.TIMEOUT

    if "auth" in msg or "permission" in msg or "api key" in msg:
        return ErrorType.AUTH

    if "503" in msg or "temporar" in msg or "service unavailable" in msg:
        return ErrorType.TRANSIENT

    return ErrorType.REVIEWER_FAILED


# ---------------------------------------------------------------------------
# Structured reviewer error
# ---------------------------------------------------------------------------

class ReviewerError(RuntimeError):
    """Structured reviewer failure used across the pipeline."""

    def __init__(
        self,
        reviewer: str,
        error_type: ErrorType,
        message: str,
        stage: str | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.reviewer = reviewer
        self.error_type = error_type
        self.stage = stage
        self.retryable = retryable
        self.message = message

    def to_dict(self) -> dict:
        return {
            "reviewer": self.reviewer,
            "error_type": self.error_type.value,
            "stage": self.stage,
            "retryable": self.retryable,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# Retry policy constants
# ---------------------------------------------------------------------------

MAX_TRANSIENT_RETRIES = 3
RETRY_BACKOFF_SECONDS = [3, 8, 20]
