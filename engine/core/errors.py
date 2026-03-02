#!/usr/bin/env python3
"""
FILE: engine/core/errors.py
VERSION: 1.0
PURPOSE:
Structured error types for the Survivor pipeline compiler/translator.

CONTRACT:
- ReviewerPackCompileError carries full debug payload for fail-run reports.
- No I/O, no side effects on import.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


class ReviewerPackValidationError(RuntimeError):
    """
    Raised by validate_reviewer_pack when enum/type validation fails.

    Carries structured error dicts [{path, expected, got, message}] so the
    translator can derive a precise diff-guard allowlist for repair attempts.

    Falls back to plain RuntimeError behaviour (str message) for callers that
    don't inspect .errors.
    """

    def __init__(self, errors: List[Dict[str, str]]) -> None:
        self.errors = errors
        super().__init__(errors[0]["message"] if errors else "validation error")


class ReviewerPackCompileError(Exception):
    """
    Raised when a reviewer pack cannot be compiled into valid Survivor schema
    after max_attempts (initial + repair).

    Carries full debug payload for compile_error.json output.
    """

    def __init__(
        self,
        reviewer_id: str,
        attempt: int,
        validation_errors: List[Dict[str, Any]],
        raw_response_text: Optional[str],
        parsed_json: Optional[Dict[str, Any]],
        translation_trace: List[Dict[str, Any]],
    ) -> None:
        self.reviewer_id = reviewer_id
        self.attempt = attempt
        self.validation_errors = validation_errors
        self.raw_response_text = raw_response_text
        self.parsed_json = parsed_json
        self.translation_trace = translation_trace

        # Build human-readable summary
        error_lines = [
            f"  - {e.get('path', '?')}: got {e.get('got', '?')!r}, "
            f"expected one of {e.get('expected', '?')}"
            for e in validation_errors
        ]
        summary = (
            f"ReviewerPackCompileError: reviewer={reviewer_id!r}, "
            f"attempt={attempt}, errors={len(validation_errors)}\n"
            + "\n".join(error_lines)
        )
        super().__init__(summary)

    def to_debug_dict(self) -> Dict[str, Any]:
        """Serialize to dict for compile_error.json output."""
        return {
            "reviewer_id": self.reviewer_id,
            "attempt": self.attempt,
            "validation_errors": self.validation_errors,
            "raw_response_text": self.raw_response_text,
            "parsed_json": self.parsed_json,
            "translation_trace": self.translation_trace,
        }
