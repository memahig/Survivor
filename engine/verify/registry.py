#!/usr/bin/env python3
"""
FILE: engine/verify/registry.py
VERSION: 0.2
PURPOSE:
Maps claim_kind to the appropriate verifier function.
Honors config.verification_kinds_enabled to gate which kinds are active.

This is the exit ramp for future verifier providers (web, law, document, etc.).
For v1.3 scaffolding: all routable kinds map to noop_verify.

PUBLIC API:
    build_registry(config) -> Dict[ClaimKind, VerifierFn]
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from engine.verify.base import CLAIM_KINDS, ClaimKind, VerificationResult
from engine.verify.noop_verifier import noop_verify

VerifierFn = Callable[[str, str, ClaimKind], VerificationResult]

# Exit ramp: swap noop_verify for real verifiers here in future versions
_VERIFIERS: Dict[ClaimKind, VerifierFn] = {
    "world_fact": noop_verify,
    # "document_content": doc_authority_verifier,  # future
}


def build_registry(config: Dict[str, Any]) -> Dict[ClaimKind, VerifierFn]:
    """
    Returns a mapping of claim_kind -> verifier callable.
    Only includes kinds listed in config.verification_kinds_enabled.
    v1.3: all registered kinds route to noop_verify.
    v1.4+: swap in real verifiers per kind based on config.
    """
    enabled_kinds_raw = config.get("verification_kinds_enabled", list(CLAIM_KINDS))
    if not isinstance(enabled_kinds_raw, list):
        raise RuntimeError("config.verification_kinds_enabled must be a list")

    for k in enabled_kinds_raw:
        if k not in CLAIM_KINDS:
            raise RuntimeError(
                f"Unknown kind in config.verification_kinds_enabled: {k!r}"
            )

    enabled_kinds = set(enabled_kinds_raw)
    return {k: v for k, v in _VERIFIERS.items() if k in enabled_kinds}
