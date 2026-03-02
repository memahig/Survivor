#!/usr/bin/env python3
"""
FILE: engine/core/translator.py
VERSION: 1.0
PURPOSE:
Universal translator + one-shot repair gate for Survivor reviewer packs.

Treats reviewer output as untrusted surface language. Translates enum fields
to canonical Survivor values using lossless-only alias maps. If translation
or validation fails, fires a one-shot repair prompt. Fails run after 2 attempts.

CONTRACT:
- Universal: same pipeline for ALL reviewers (no provider-specific paths).
- LOSSLESS-ONLY: alias maps contain only formatting variants, never semantic coercions.
- Repair is focusing: may only fix schema/enum/type issues, not substantive judgments.
- Fail-run after max_attempts with ReviewerPackCompileError carrying full debug.
- No I/O except through call_reviewer_fn (passed in by caller).
"""

from __future__ import annotations

import copy
import json
from typing import Any, Callable, Dict, List, Optional, Tuple

from engine.core.errors import ReviewerPackCompileError
from engine.core.translation_rules import (
    CANONICAL_ENUMS,
    build_enum_contract_text,
    build_error_enum_text,
    translate_field,
)
from engine.core.validators import validate_reviewer_pack


# ---------------------------------------------------------------------------
# Annotate: copy raw enum values to raw_* fields
# ---------------------------------------------------------------------------

_ANNOTATION_PATHS = [
    # (parent_key, field_name, raw_field_name)
    ("whole_article_judgment", "classification", "raw_classification_label"),
    ("whole_article_judgment", "confidence", "raw_confidence_label"),
]

_CLAIM_ANNOTATION_PATHS = [
    ("type", "raw_type_label"),
]

_VOTE_ANNOTATION_PATHS = [
    ("vote", "raw_vote_label"),
    ("confidence", "raw_confidence_label"),
]

_GSAE_ANNOTATION_PATHS = [
    ("classification_bucket", "raw_classification_bucket_label"),
    ("severity_toward_subject", "raw_severity_toward_subject_label"),
    ("severity_toward_counterparty", "raw_severity_toward_counterparty_label"),
    ("confidence_band", "raw_confidence_band_label"),
]


def _annotate_raw_fields(pack: Dict[str, Any]) -> None:
    """Copy pre-translation enum values into raw_* fields for audit."""
    waj = pack.get("whole_article_judgment")
    if isinstance(waj, dict):
        for _parent, field, raw_field in _ANNOTATION_PATHS:
            val = waj.get(field)
            if isinstance(val, str):
                waj[raw_field] = val

    claims = pack.get("claims")
    if isinstance(claims, list):
        for c in claims:
            if not isinstance(c, dict):
                continue
            for field, raw_field in _CLAIM_ANNOTATION_PATHS:
                val = c.get(field)
                if isinstance(val, str):
                    c[raw_field] = val

    votes = pack.get("cross_claim_votes")
    if isinstance(votes, list):
        for v in votes:
            if not isinstance(v, dict):
                continue
            for field, raw_field in _VOTE_ANNOTATION_PATHS:
                val = v.get(field)
                if isinstance(val, str):
                    v[raw_field] = val

    obs = pack.get("gsae_observation")
    if isinstance(obs, dict):
        for field, raw_field in _GSAE_ANNOTATION_PATHS:
            val = obs.get(field)
            if isinstance(val, str):
                obs[raw_field] = val


# ---------------------------------------------------------------------------
# Translate: apply format normalization + lossless alias maps
# ---------------------------------------------------------------------------

def _translate_pack(pack: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Translate enum fields in-place. Returns list of translation failures.
    Each failure: {"path": str, "got": str, "expected": str, "message": str}
    """
    failures: List[Dict[str, Any]] = []

    waj = pack.get("whole_article_judgment")
    if isinstance(waj, dict):
        for field_path_suffix in ("classification", "confidence"):
            field_path = f"whole_article_judgment.{field_path_suffix}"
            raw = waj.get(field_path_suffix)
            if isinstance(raw, str):
                canonical, _raw_preserved, ok = translate_field(field_path, raw)
                if ok:
                    waj[field_path_suffix] = canonical
                else:
                    failures.append({
                        "path": field_path,
                        "got": raw,
                        "expected": build_error_enum_text(field_path),
                        "message": f"{field_path}: got {raw!r}, not a valid enum value",
                    })

    claims = pack.get("claims")
    if isinstance(claims, list):
        for i, c in enumerate(claims):
            if not isinstance(c, dict):
                continue
            raw = c.get("type")
            if isinstance(raw, str):
                field_path = "claims.type"
                canonical, _raw_preserved, ok = translate_field(field_path, raw)
                if ok:
                    c["type"] = canonical
                else:
                    failures.append({
                        "path": f"claims[{i}].type",
                        "got": raw,
                        "expected": build_error_enum_text(field_path),
                        "message": f"claims[{i}].type: got {raw!r}, not a valid enum value",
                    })

    votes = pack.get("cross_claim_votes")
    if isinstance(votes, list):
        for i, v in enumerate(votes):
            if not isinstance(v, dict):
                continue
            for field_name, field_path in [("vote", "cross_claim_votes.vote"),
                                            ("confidence", "cross_claim_votes.confidence")]:
                raw = v.get(field_name)
                if isinstance(raw, str):
                    canonical, _raw_preserved, ok = translate_field(field_path, raw)
                    if ok:
                        v[field_name] = canonical
                    else:
                        failures.append({
                            "path": f"cross_claim_votes[{i}].{field_name}",
                            "got": raw,
                            "expected": build_error_enum_text(field_path),
                            "message": f"cross_claim_votes[{i}].{field_name}: got {raw!r}",
                        })

    obs = pack.get("gsae_observation")
    if isinstance(obs, dict):
        for field_name in ("classification_bucket", "severity_toward_subject",
                           "severity_toward_counterparty", "confidence_band"):
            field_path = f"gsae_observation.{field_name}"
            raw = obs.get(field_name)
            if isinstance(raw, str):
                canonical, _raw_preserved, ok = translate_field(field_path, raw)
                if ok:
                    obs[field_name] = canonical
                else:
                    failures.append({
                        "path": field_path,
                        "got": raw,
                        "expected": build_error_enum_text(field_path),
                        "message": f"{field_path}: got {raw!r}, not a valid enum value",
                    })

    return failures


# ---------------------------------------------------------------------------
# Repair prompt builder
# ---------------------------------------------------------------------------

_REPAIR_SYSTEM_PROMPT = (
    "You are a schema repair assistant. You will receive a JSON response that "
    "had enum/schema errors. Fix ONLY the fields listed in the ERRORS section. "
    "Do not change substantive judgments, claim text, evidence, or any other fields. "
    "Return the corrected full JSON only."
)


def _build_repair_user_prompt(
    raw_pack: Dict[str, Any],
    failures: List[Dict[str, Any]],
) -> str:
    """Build the repair prompt with errors + enum contract."""
    lines = [
        "Your previous response had schema errors. Fix ONLY the fields listed below.",
        "Do not change substantive judgments or any other fields.",
        "",
        "Your original labels are preserved in raw_* fields for audit. You must now",
        "select the closest match from the allowed enum list for each canonical field.",
        "",
        "ERRORS:",
    ]
    for f in failures:
        lines.append(f"- {f['path']}: got {f['got']!r}")
        lines.append(f"  Allowed values: {f['expected']}")

    lines.append("")
    lines.append("If you need to express nuance beyond the enum, add an \"expression\"")
    lines.append("key at the top level with free-text commentary. This field is permissive.")
    lines.append("")
    lines.append(build_enum_contract_text())
    lines.append("")
    lines.append("ORIGINAL JSON (fix and return):")
    lines.append(json.dumps(raw_pack, indent=2, ensure_ascii=False))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compile_reviewer_pack(
    reviewer_id: str,
    raw_pack: Dict[str, Any],
    call_reviewer_fn: Callable[[str, str], Dict[str, Any]],
    config: Dict[str, Any],
    *,
    max_attempts: int = 2,
) -> Dict[str, Any]:
    """
    Compile a raw reviewer pack into a validated Survivor pack.

    1. Annotate raw_* fields
    2. Translate enum fields (lossless-only)
    3. Validate via validate_reviewer_pack
    4. If invalid: one-shot repair via call_reviewer_fn
    5. If still invalid: raise ReviewerPackCompileError

    Args:
        reviewer_id: Name of the reviewer (for error reporting)
        raw_pack: The raw JSON dict returned by the reviewer
        call_reviewer_fn: The reviewer's _call_json(system_prompt, user_prompt) method
        config: Pipeline config dict
        max_attempts: 1 (initial only) or 2 (initial + 1 repair). Default: 2.

    Returns:
        Validated reviewer pack dict.

    Raises:
        ReviewerPackCompileError: If pack cannot be compiled after max_attempts.
    """
    trace: List[Dict[str, Any]] = []

    for attempt in range(1, max_attempts + 1):
        pack = copy.deepcopy(raw_pack) if attempt == 1 else raw_pack

        # Step 1: Annotate raw_* fields
        _annotate_raw_fields(pack)

        # Step 2: Translate enum fields
        translation_failures = _translate_pack(pack)

        trace.append({
            "attempt": attempt,
            "translation_failures": translation_failures,
            "stage": "translate",
        })

        if translation_failures:
            # Translation failed — if we have attempts left, try repair
            if attempt < max_attempts:
                repair_prompt = _build_repair_user_prompt(pack, translation_failures)
                try:
                    raw_pack = call_reviewer_fn(_REPAIR_SYSTEM_PROMPT, repair_prompt)
                except Exception as e:
                    trace.append({
                        "attempt": attempt,
                        "stage": "repair_call_failed",
                        "error": str(e),
                    })
                    raise ReviewerPackCompileError(
                        reviewer_id=reviewer_id,
                        attempt=attempt,
                        validation_errors=translation_failures,
                        raw_response_text=None,
                        parsed_json=pack,
                        translation_trace=trace,
                    ) from e
                continue  # retry with repaired output

            # No attempts left — fail
            raise ReviewerPackCompileError(
                reviewer_id=reviewer_id,
                attempt=attempt,
                validation_errors=translation_failures,
                raw_response_text=None,
                parsed_json=pack,
                translation_trace=trace,
            )

        # Step 3: Validate (validator still has legacy normalizer as safety net)
        try:
            validate_reviewer_pack(pack, config)
        except RuntimeError as e:
            validation_error = {
                "path": "(validator)",
                "got": str(e),
                "expected": "(see validator contract)",
                "message": str(e),
            }
            trace.append({
                "attempt": attempt,
                "stage": "validate",
                "error": str(e),
            })

            if attempt < max_attempts:
                # Validation failed — try repair
                repair_prompt = _build_repair_user_prompt(pack, [validation_error])
                try:
                    raw_pack = call_reviewer_fn(_REPAIR_SYSTEM_PROMPT, repair_prompt)
                except Exception as repair_err:
                    trace.append({
                        "attempt": attempt,
                        "stage": "repair_call_failed",
                        "error": str(repair_err),
                    })
                    raise ReviewerPackCompileError(
                        reviewer_id=reviewer_id,
                        attempt=attempt,
                        validation_errors=[validation_error],
                        raw_response_text=None,
                        parsed_json=pack,
                        translation_trace=trace,
                    ) from repair_err
                continue

            raise ReviewerPackCompileError(
                reviewer_id=reviewer_id,
                attempt=attempt,
                validation_errors=[validation_error],
                raw_response_text=None,
                parsed_json=pack,
                translation_trace=trace,
            ) from e

        # Success
        trace.append({
            "attempt": attempt,
            "stage": "success",
        })
        return pack

    # Should not reach here, but fail-closed
    raise ReviewerPackCompileError(
        reviewer_id=reviewer_id,
        attempt=max_attempts,
        validation_errors=[{"path": "(unreachable)", "got": "bug", "expected": "success", "message": "unreachable"}],
        raw_response_text=None,
        parsed_json=None,
        translation_trace=trace,
    )
