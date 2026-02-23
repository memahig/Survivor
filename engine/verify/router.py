#!/usr/bin/env python3
"""
FILE: engine/verify/router.py
VERSION: 0.3
PURPOSE:
Runs verification over adjudicated claims using the verifier registry.

Routing rules:
  - world_fact:        requires checkability == "checkable" before calling verifier.
  - document_content:  checkability is not required; proceeds if verifier registered.

For v1.3 scaffolding: adjudicator does not yet emit claim_kind or checkability.
Router returns empty results transparently — no field invention, no silent failure.

Enabling prerequisite (separate ticket):
  adjudicator must emit claim_kind + checkability on adjudicated_claims objects.

PUBLIC API:
    run_verification(run_state, config) -> VerificationPack
"""

from __future__ import annotations

from typing import Any, Dict, List

from engine.verify.base import (
    CHECKABILITY_VALUES,
    CLAIM_KINDS,
    ClaimKind,
    VerificationPack,
    VerificationResult,
)
from engine.verify.registry import build_registry


def _get_adjudicated_claims(run_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    return (
        run_state
        .get("adjudicated", {})
        .get("claim_track", {})
        .get("arena", {})
        .get("adjudicated_claims", [])
    )


def _is_routable(
    claim_kind: ClaimKind,
    raw_checkability: Any,
    group_id: Any,
) -> bool:
    """
    Returns True if this claim should be routed to a verifier.

    world_fact:        checkability must be present, valid, and == "checkable".
    document_content:  checkability is ignored — doc authority is always the document itself.
    """
    if claim_kind == "world_fact":
        if raw_checkability is None:
            return False  # upstream not yet emitting checkability
        if raw_checkability not in CHECKABILITY_VALUES:
            raise RuntimeError(
                f"Invalid checkability emitted by adjudicator: {raw_checkability!r} "
                f"for group_id={group_id}"
            )
        return raw_checkability == "checkable"

    if claim_kind == "document_content":
        # checkability does not gate document-authority verification
        return True

    return False  # unreachable after CLAIM_KINDS check; assert_never candidate later


def run_verification(run_state: Dict[str, Any], config: Dict[str, Any]) -> VerificationPack:
    enabled = bool(config.get("verification_enabled", False))

    if not enabled:
        return {"enabled": False, "results": []}

    registry = build_registry(config)
    adjudicated_claims = _get_adjudicated_claims(run_state)
    results: List[VerificationResult] = []

    saw_missing_kind = False
    saw_missing_checkability = False
    saw_routable_claim = False

    for g in adjudicated_claims:
        raw_kind = g.get("claim_kind")
        raw_checkability = g.get("checkability")
        group_id = g.get("group_id")

        # claim_kind absent: adjudicator not yet emitting it (v1.3 scaffolding)
        if raw_kind is None:
            saw_missing_kind = True
            continue

        # claim_kind present but invalid: fail closed
        if raw_kind not in CLAIM_KINDS:
            raise RuntimeError(
                f"Invalid claim_kind emitted by adjudicator: {raw_kind!r} "
                f"for group_id={group_id}"
            )

        # Track missing checkability only for kinds that require it
        if raw_kind == "world_fact" and raw_checkability is None:
            saw_missing_checkability = True

        # Type-narrow after validation
        claim_kind: ClaimKind = raw_kind  # type: ignore[assignment]

        if not _is_routable(claim_kind, raw_checkability, group_id):
            continue

        saw_routable_claim = True

        verifier = registry.get(claim_kind)
        if verifier is None:
            continue  # no verifier registered for this claim_kind yet

        claim_text = g.get("text") or ""

        if not group_id:
            raise RuntimeError(f"adjudicated_claim missing group_id: {g}")
        if not claim_text:
            raise RuntimeError(
                f"adjudicated_claim missing text for group_id={group_id}"
            )

        results.append(verifier(group_id, claim_text, claim_kind))

    out: VerificationPack = {"enabled": True, "results": results}

    if not results:
        if saw_missing_kind or saw_missing_checkability:
            missing = []
            if saw_missing_kind:
                missing.append("claim_kind")
            if saw_missing_checkability:
                missing.append("checkability")
            out["note"] = (
                f"verification_enabled=true but adjudicator does not yet emit "
                f"{', '.join(missing)} — no claims verified (v1.3 scaffolding)"
            )
        elif saw_routable_claim:
            out["note"] = (
                "routable claims found but no verifier registered "
                "for their claim_kind (v1.3 scaffolding)"
            )
        else:
            out["note"] = "no routable claims found in adjudicated output"

    return out
