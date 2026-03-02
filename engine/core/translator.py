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
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from engine.core.errors import ReviewerPackCompileError, ReviewerPackValidationError
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
# Diff guard: allowlist-based enforcement for repair attempts
# ---------------------------------------------------------------------------
#
# Design: the allowed change set is derived from the exact error paths.
# For each failing error path p:
#   - allow p
#   - allow raw_* sibling fields under that object (audit fields)
#   - allow "expression" at top level (always permitted)
# Everything else must be identical between attempt 1 and attempt 2.
# Comparison is on post-translate packs (both after translation rules applied).


# Explicit map from canonical enum field path → raw_* audit field name.
# Derived from _ANNOTATION_PATHS / _CLAIM_ANNOTATION_PATHS / etc.
# Do NOT synthesize raw_* names; use this map.
_RAW_SIBLING_MAP: Dict[str, str] = {
    "whole_article_judgment.classification": "whole_article_judgment.raw_classification_label",
    "whole_article_judgment.confidence": "whole_article_judgment.raw_confidence_label",
    "claims.type": "claims.raw_type_label",
    "cross_claim_votes.vote": "cross_claim_votes.raw_vote_label",
    "cross_claim_votes.confidence": "cross_claim_votes.raw_confidence_label",
    "gsae_observation.classification_bucket": "gsae_observation.raw_classification_bucket_label",
    "gsae_observation.severity_toward_subject": "gsae_observation.raw_severity_toward_subject_label",
    "gsae_observation.severity_toward_counterparty": "gsae_observation.raw_severity_toward_counterparty_label",
    "gsae_observation.confidence_band": "gsae_observation.raw_confidence_band_label",
}


def _build_allowed_paths(
    error_paths: List[str],
) -> set:
    """
    Build the set of allowed-change paths from validation error paths.

    Error paths like "whole_article_judgment.classification" or "claims[2].type"
    produce allowed paths for that field plus its raw_* sibling (from explicit map).
    """
    allowed = {"expression"}  # always allowed to add/modify

    for path in error_paths:
        allowed.add(path)

        # Allow raw_* sibling using explicit map (not synthesis).
        # Indexed paths like "claims[2].type" → strip index to find map key "claims.type",
        # then re-add the index to get "claims[2].raw_type_label".
        stripped = re.sub(r'\[\d+\]', '', path)  # "claims[2].type" → "claims.type"
        raw_sibling = _RAW_SIBLING_MAP.get(stripped)
        if raw_sibling:
            # Re-inject the index from the original path into the raw sibling.
            # e.g. path="claims[2].type", raw_sibling="claims.raw_type_label"
            #   → "claims[2].raw_type_label"
            idx_match = re.search(r'\[\d+\]', path)
            if idx_match:
                # Insert index after the first segment
                parent = raw_sibling.split('.')[0]
                rest = raw_sibling[len(parent):]
                allowed.add(f"{parent}{idx_match.group()}{rest}")
            else:
                allowed.add(raw_sibling)

    return allowed


def _nullify_indexed_list(
    items: List[Any],
    list_key: str,
    allowed_paths: set,
    sentinel: str,
) -> None:
    """
    Sentinel fields on specific list items based on indexed allowed paths.

    Parses paths like "claims[2].type" to sentinel only index 2's "type" field.
    Does NOT broadcast to all indices — each index must be explicitly allowed.
    """
    # Build per-index allowed fields: {2: {"type", "raw_type_label"}, ...}
    per_index: Dict[int, set] = {}
    for p in allowed_paths:
        if not p.startswith(list_key):
            continue
        m = re.match(rf'^{re.escape(list_key)}\[(\d+)\]\.(.+)$', p)
        if m:
            idx = int(m.group(1))
            field = m.group(2)
            per_index.setdefault(idx, set()).add(field)

    for idx, fields in per_index.items():
        if idx < len(items) and isinstance(items[idx], dict):
            for f in fields:
                if f in items[idx]:
                    items[idx][f] = sentinel


def _nullify_allowed_fields(
    pack: Dict[str, Any],
    allowed_paths: set,
) -> Dict[str, Any]:
    """
    Deep copy a pack and set all allowed-change fields to a sentinel.
    The remaining fields can then be compared with == for drift detection.
    """
    SENTINEL = "__ALLOWED_CHANGE__"
    out = copy.deepcopy(pack)

    # Top-level allowed keys — also insert sentinel for absent keys
    # so that a new key added during repair (e.g. "expression") doesn't
    # trigger a false positive when the original pack lacked it.
    for key in list(out.keys()):
        if key in allowed_paths:
            out[key] = SENTINEL
    for path in allowed_paths:
        if "." not in path and "[" not in path and path not in out:
            out[path] = SENTINEL

    # Nested: whole_article_judgment.*
    waj = out.get("whole_article_judgment")
    if isinstance(waj, dict):
        for key in list(waj.keys()):
            full_path = f"whole_article_judgment.{key}"
            if full_path in allowed_paths:
                waj[key] = SENTINEL

    # Nested: claims[N].field — only sentinel the specific index allowed
    claims = out.get("claims")
    if isinstance(claims, list):
        _nullify_indexed_list(claims, "claims", allowed_paths, SENTINEL)

    # Nested: cross_claim_votes[N].field
    votes = out.get("cross_claim_votes")
    if isinstance(votes, list):
        _nullify_indexed_list(votes, "cross_claim_votes", allowed_paths, SENTINEL)

    # Nested: gsae_observation.*
    obs = out.get("gsae_observation")
    if isinstance(obs, dict):
        for key in list(obs.keys()):
            full_path = f"gsae_observation.{key}"
            if full_path in allowed_paths:
                obs[key] = SENTINEL

    return out


def _diff_guard(
    original: Dict[str, Any],
    repaired: Dict[str, Any],
    error_paths: List[str],
) -> List[str]:
    """
    Compare post-translate attempt-1 pack with post-translate attempt-2 pack.

    Only fields in the allowed change set (derived from error_paths) may differ.
    Returns list of violation descriptions. Empty = repair is clean.
    """
    allowed = _build_allowed_paths(error_paths)

    orig_masked = _nullify_allowed_fields(original, allowed)
    repair_masked = _nullify_allowed_fields(repaired, allowed)

    if orig_masked == repair_masked:
        return []

    # Find specific differences — drill into nested structures for useful messages
    violations: List[str] = []

    all_keys = set(list(orig_masked.keys()) + list(repair_masked.keys()))
    for key in sorted(all_keys):
        orig_val = orig_masked.get(key)
        repair_val = repair_masked.get(key)
        if orig_val == repair_val:
            continue

        # Drill into dicts to find the specific changed fields
        if isinstance(orig_val, dict) and isinstance(repair_val, dict):
            sub_keys = set(list(orig_val.keys()) + list(repair_val.keys()))
            for sk in sorted(sub_keys):
                if orig_val.get(sk) != repair_val.get(sk):
                    violations.append(
                        f"{key}.{sk} changed during repair (disallowed): "
                        f"{orig_val.get(sk)!r} → {repair_val.get(sk)!r}"
                    )
        # Drill into lists (claims, votes)
        elif isinstance(orig_val, list) and isinstance(repair_val, list):
            for i, (a, b) in enumerate(zip(orig_val, repair_val)):
                if a != b:
                    if isinstance(a, dict) and isinstance(b, dict):
                        sub_keys = set(list(a.keys()) + list(b.keys()))
                        for sk in sorted(sub_keys):
                            if a.get(sk) != b.get(sk):
                                violations.append(
                                    f"{key}[{i}].{sk} changed during repair (disallowed): "
                                    f"{a.get(sk)!r} → {b.get(sk)!r}"
                                )
                    else:
                        violations.append(
                            f"{key}[{i}] changed during repair (disallowed)"
                        )
            if len(orig_val) != len(repair_val):
                violations.append(
                    f"{key} length changed during repair: "
                    f"{len(orig_val)} → {len(repair_val)}"
                )
        else:
            violations.append(f"{key} changed during repair (disallowed)")

    return violations


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
    attempt1_pack: Optional[Dict[str, Any]] = None  # saved for diff guard
    attempt1_error_paths: List[str] = []  # error paths from attempt 1 (for diff guard)

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
            if attempt < max_attempts:
                # Save attempt 1 pack + error paths for diff guard comparison
                attempt1_pack = copy.deepcopy(pack)
                attempt1_error_paths = [f["path"] for f in translation_failures]
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
                continue

            raise ReviewerPackCompileError(
                reviewer_id=reviewer_id,
                attempt=attempt,
                validation_errors=translation_failures,
                raw_response_text=None,
                parsed_json=pack,
                translation_trace=trace,
            )

        # Step 3: Diff guard — if this is a repair attempt, verify substantive
        # fields were not changed by the model during repair.
        if attempt > 1 and attempt1_pack is not None:
            violations = _diff_guard(attempt1_pack, pack, attempt1_error_paths)
            if violations:
                diff_errors = [
                    {
                        "path": "(diff_guard)",
                        "got": v,
                        "expected": "unchanged",
                        "message": f"Substantive field changed during repair: {v}",
                    }
                    for v in violations
                ]
                trace.append({
                    "attempt": attempt,
                    "stage": "diff_guard_failed",
                    "violations": violations,
                })
                raise ReviewerPackCompileError(
                    reviewer_id=reviewer_id,
                    attempt=attempt,
                    validation_errors=diff_errors,
                    raw_response_text=None,
                    parsed_json=pack,
                    translation_trace=trace,
                )

        # Step 4: Validate (validator still has legacy normalizer as safety net)
        # ReviewerPackValidationError = structured enum/type errors → repairable.
        # Plain RuntimeError = shape/keyset errors → non-repairable, fail-run.
        try:
            validate_reviewer_pack(pack, config)
        except ReviewerPackValidationError as e:
            # Structured errors with real field paths — repairable
            validation_errors = e.errors
            error_paths = [err["path"] for err in validation_errors]
            trace.append({
                "attempt": attempt,
                "stage": "validate",
                "errors": validation_errors,
            })

            if attempt < max_attempts:
                attempt1_pack = copy.deepcopy(pack)
                attempt1_error_paths = error_paths
                repair_prompt = _build_repair_user_prompt(pack, validation_errors)
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
                        validation_errors=validation_errors,
                        raw_response_text=None,
                        parsed_json=pack,
                        translation_trace=trace,
                    ) from repair_err
                continue

            raise ReviewerPackCompileError(
                reviewer_id=reviewer_id,
                attempt=attempt,
                validation_errors=validation_errors,
                raw_response_text=None,
                parsed_json=pack,
                translation_trace=trace,
            ) from e
        except RuntimeError as e:
            # Non-structured error (shape/keyset) — non-repairable, fail immediately
            trace.append({
                "attempt": attempt,
                "stage": "validate_fatal",
                "error": str(e),
            })
            raise ReviewerPackCompileError(
                reviewer_id=reviewer_id,
                attempt=attempt,
                validation_errors=[{
                    "path": "(validator)",
                    "got": str(e),
                    "expected": "(see validator contract)",
                    "message": str(e),
                }],
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
