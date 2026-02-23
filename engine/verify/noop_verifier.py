#!/usr/bin/env python3
"""
FILE: engine/verify/noop_verifier.py
VERSION: 0.1
PURPOSE:
Noop verifier — returns not_checked_yet for any claim.
Used as the default until real world-authority checking is implemented.

CONTRACT:
- Never makes external calls.
- Always returns a valid VerificationResult with status=not_checked_yet.
- authority_sources is [] (permitted only for not_checked_yet).
"""

from __future__ import annotations

from datetime import datetime, timezone

from engine.verify.base import ClaimKind, CLAIM_KINDS, VerificationResult


def noop_verify(
    claim_id: str,
    claim_text: str,
    claim_kind: ClaimKind,
) -> VerificationResult:
    if claim_kind not in CLAIM_KINDS:
        raise ValueError(f"Invalid claim_kind for verification: {claim_kind!r}")

    return {
        "claim_id": claim_id,
        "claim_text": claim_text,
        "claim_kind": claim_kind,
        "verification_status": "not_checked_yet",
        # "low" reflects that no verification occurred — not a judgment of the claim itself
        "confidence": "low",
        "authority_sources": [],
        "method_note": "noop_verifier: no external check performed (v1.3 scaffolding)",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
