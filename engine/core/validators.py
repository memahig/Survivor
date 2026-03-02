#!/usr/bin/env python3
"""
FILE: engine/core/validators.py
VERSION: 0.2.1
PURPOSE:
Fail-closed validators for Survivor run_state and reviewer packs.

CONTRACT:
- Raise RuntimeError on any violation.
- No warnings-only mode.
- Key sets are imported from engine.core.schema_constants — do not hardcode them here.

CHANGES IN v0.2:
- (A) Key sets sourced from schema_constants; no inline hardcoding.
- (B) "uncertain" classification requires uncertainty_basis + check_scope (no bypass).
- (C) Deep enum validation: ArticleClassification, ClaimType, Vote, Confidence,
      Integrity Scale (if present).
- (D) EvidenceBank canonical schema enforced: quote, locator, source_id;
      text==quote, char_len==len(quote), locator length consistency;
      full reconstructibility if normalized_text present in run_state.
- (E) near_duplicate_of references validated against claim registry (no dangling refs).
- (fix) Symmetric authority rule: not_verifiable now also exempted alongside
        not_checked_yet (AUTHORITY_SOURCES_EXEMPT_STATUSES).

CHANGES IN v0.2.1:
- reviewer non-empty check (reviewer.strip()).
- Phantom EID guard: whitespace-only EIDs are ignored (strip before lookup);
  error list normalized to stripped EIDs.
- EvidenceBank bounds check: cs and ce <= len(normalized_text) before slicing.
- cross_claim_votes: claim_id must be non-empty str.
- _collect_eids: replaced recursive impl with iterative + 200k node cap.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from engine.core.schema_constants import (
    ARTICLE_CLASSIFICATIONS,
    AUTHORITY_SOURCES_EXEMPT_STATUSES,
    CLAIM_TYPES,
    CLASSIFICATION_BUCKET_VALUES,
    CONFIDENCE_VALUES,
    GSAE_ARTIFACT_REQUIRED_KEYS,
    GSAE_SETTINGS_REQUIRED_KEYS,
    GSAE_SUBJECT_REQUIRED_KEYS,
    GSAE_SYMMETRY_PACKET_REQUIRED_KEYS,
    GSAE_SYMMETRY_PACKET_V03_REQUIRED_KEYS,
    INTEGRITY_SCALE,
    REVIEWER_PACK_OPTIONAL_KEYS,
    REVIEWER_PACK_REQUIRED_KEYS,
    SEVERITY_TIER_VALUES_ORDERED,
    SYMMETRY_BAND_VALUES_ORDERED,
    SYMMETRY_FIELDS_ALL,
    SYMMETRY_FIELDS_BASE,
    SYMMETRY_FIELDS_V03,
    SYMMETRY_STATUS_VALUES,
    EMPTY_EIDS_ALLOWED_CLASSIFICATIONS,
    UNCERTAIN_CLASSIFICATIONS,
    VOTE_VALUES,
)
from engine.core.schemas import ReviewerPack


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _is_list_of_str(x: Any) -> bool:
    return isinstance(x, list) and all(isinstance(i, str) for i in x)


# ---------------------------------------------------------------------------
# whole_article_judgment validation
# ---------------------------------------------------------------------------


def _validate_whole_article_judgment(pack: Dict[str, Any]) -> None:
    waj = pack.get("whole_article_judgment")
    _require(isinstance(waj, dict), "ReviewerPack missing whole_article_judgment dict")

    classification = waj.get("classification")
    confidence = waj.get("confidence")
    eids = waj.get("evidence_eids")

    _require(isinstance(classification, str), "whole_article_judgment.classification must be str")
    _require(
        classification in ARTICLE_CLASSIFICATIONS,
        f"whole_article_judgment.classification invalid: {classification!r}",
    )
    _require(
        confidence in CONFIDENCE_VALUES,
        f"whole_article_judgment.confidence invalid: {confidence!r}",
    )
    _require(_is_list_of_str(eids), "whole_article_judgment.evidence_eids must be list[str]")

    # (B) Uncertain classification: require uncertainty_basis + check_scope.
    if classification in UNCERTAIN_CLASSIFICATIONS:
        uncertainty_basis = waj.get("uncertainty_basis")
        _require(
            isinstance(uncertainty_basis, str) and uncertainty_basis.strip(),
            "whole_article_judgment.uncertainty_basis must be non-empty str when classification is uncertain",
        )
        check_scope = waj.get("check_scope") or waj.get("search_scope")
        _require(
            isinstance(check_scope, str) and check_scope.strip(),
            "whole_article_judgment.check_scope (or search_scope) must be non-empty str when classification is uncertain",
        )
        return

    # (B2) Some classifications allow empty evidence_eids at whole-article level.
    if classification not in EMPTY_EIDS_ALLOWED_CLASSIFICATIONS:
        _require(
            len(eids) > 0,
            "whole_article_judgment.evidence_eids must be non-empty unless classification is uncertain or reporting",
        )

    # (C) Integrity Scale — validate if the field is present in waj.
    integrity_rating = waj.get("integrity_rating")
    if integrity_rating is not None:
        _require(
            integrity_rating in INTEGRITY_SCALE,
            f"whole_article_judgment.integrity_rating invalid: {integrity_rating!r}",
        )


# ---------------------------------------------------------------------------
# Claims validation
# ---------------------------------------------------------------------------


def _validate_claims(pack: Dict[str, Any]) -> None:
    claims = pack.get("claims", [])
    for i, claim in enumerate(claims):
        _require(isinstance(claim, dict), f"claims[{i}] must be dict")
        _require(
            isinstance(claim.get("claim_id"), str) and claim["claim_id"].strip(),
            f"claims[{i}].claim_id must be non-empty str",
        )
        _require(
            isinstance(claim.get("text"), str) and claim["text"].strip(),
            f"claims[{i}].text must be non-empty str",
        )
        _require(
            claim.get("type") in CLAIM_TYPES,
            f"claims[{i}].type invalid: {claim.get('type')!r}",
        )
        _require(
            _is_list_of_str(claim.get("evidence_eids")),
            f"claims[{i}].evidence_eids must be list[str]",
        )
        centrality = claim.get("centrality")
        _require(
            isinstance(centrality, int) and centrality in (1, 2, 3),
            f"claims[{i}].centrality must be 1, 2, or 3",
        )


# ---------------------------------------------------------------------------
# Cross-claim votes validation
# ---------------------------------------------------------------------------


def _validate_cross_claim_votes(pack: Dict[str, Any], config: Dict[str, Any]) -> None:
    cap = int(config["max_near_duplicate_links"])
    votes = pack.get("cross_claim_votes", [])
    _require(isinstance(votes, list), "ReviewerPack.cross_claim_votes must be list")

    for i, v in enumerate(votes):
        _require(isinstance(v, dict), f"cross_claim_votes[{i}] must be dict")

        # (v0.2.1) claim_id must be non-empty str
        cid = v.get("claim_id")
        _require(
            isinstance(cid, str) and cid.strip(),
            f"cross_claim_votes[{i}].claim_id must be non-empty str",
        )

        vote_val = v.get("vote")
        if vote_val is not None:
            _require(
                vote_val in VOTE_VALUES,
                f"cross_claim_votes[{i}].vote invalid: {vote_val!r}",
            )

        conf_val = v.get("confidence")
        if conf_val is not None:
            _require(
                conf_val in CONFIDENCE_VALUES,
                f"cross_claim_votes[{i}].confidence invalid: {conf_val!r}",
            )

        nd = v.get("near_duplicate_of")
        if nd is None:
            continue
        _require(_is_list_of_str(nd), f"cross_claim_votes[{i}].near_duplicate_of must be list[str]")
        _require(len(nd) <= cap, f"cross_claim_votes[{i}].near_duplicate_of exceeds cap {cap}")


# ---------------------------------------------------------------------------
# validate_reviewer_pack
# ---------------------------------------------------------------------------


def _normalize_reviewer_pack(pack: Dict[str, Any]) -> None:
    """Normalize common LLM drift in reviewer output before strict validation."""
    # --- Classification synonyms ---
    waj = pack.get("whole_article_judgment")
    if isinstance(waj, dict):
        raw = waj.get("classification")
        if isinstance(raw, str):
            key = raw.strip().lower()
            _CLASSIFICATION_MAP = {
                "news": "reporting",
                "straight_news": "reporting",
                "news_reporting": "reporting",
                "factual_reporting": "reporting",
                "commentary": "analysis",
                "opinion": "analysis",
                "editorial": "analysis",
                "propaganda": "propaganda-patterned advocacy",
                "propaganda_patterned": "propaganda-patterned advocacy",
            }
            if key in _CLASSIFICATION_MAP:
                waj["classification"] = _CLASSIFICATION_MAP[key]

    # --- Centrality clamping (must be 1, 2, or 3) ---
    claims = pack.get("claims")
    if isinstance(claims, list):
        for c in claims:
            if not isinstance(c, dict):
                continue
            raw_c = c.get("centrality")
            try:
                v = int(raw_c)
            except (TypeError, ValueError):
                v = 2  # default to mid-range
            c["centrality"] = max(1, min(3, v))


def validate_reviewer_pack(pack: Dict[str, Any], config: Dict[str, Any]) -> None:
    _require(isinstance(pack, dict), "ReviewerPack must be dict")
    _normalize_reviewer_pack(pack)
    # (v0.2.1) reviewer must be a non-empty str
    reviewer = pack.get("reviewer")
    _require(isinstance(reviewer, str) and reviewer.strip(), "ReviewerPack.reviewer missing/invalid")

    # (A) Key sets from schema_constants — no hardcoding here.
    # "reviewer" validated separately above; include in allowed set.
    actual_keys = set(pack.keys())
    allowed_keys = REVIEWER_PACK_REQUIRED_KEYS | REVIEWER_PACK_OPTIONAL_KEYS | {"reviewer"}

    missing = sorted(REVIEWER_PACK_REQUIRED_KEYS - actual_keys)
    _require(not missing, f"ReviewerPack missing required key(s): {missing}")

    extra = sorted(actual_keys - allowed_keys)
    _require(not extra, f"ReviewerPack has unknown extra key(s): {extra}")

    # Optional Tier C blocks (validated strictly if present).
    if "gsae_observation" in pack:
        _validate_gsae_symmetry_packet(pack["gsae_observation"])
    if "gsae_subject" in pack:
        _validate_gsae_subject(pack["gsae_subject"])

    _validate_whole_article_judgment(pack)
    _validate_claims(pack)

    claims = pack.get("claims")
    _require(isinstance(claims, list), "ReviewerPack.claims must be list")
    _require(
        len(claims) <= int(config["max_claims_per_reviewer"]),
        "claims exceed max_claims_per_reviewer",
    )

    _validate_cross_claim_votes(pack, config)


# ---------------------------------------------------------------------------
# EID collection (iterative, cap-guarded — v0.2.1)
# ---------------------------------------------------------------------------


def _collect_eids(obj: Any, out: List[str], *, max_nodes: int = 200_000) -> None:
    stack = [obj]
    seen = 0
    while stack:
        seen += 1
        if seen > max_nodes:
            raise RuntimeError(
                f"EID collection exceeded max_nodes={max_nodes} (possible nested/hostile structure)"
            )
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k == "evidence_eids" and isinstance(v, list):
                    for eid in v:
                        if isinstance(eid, str):
                            out.append(eid)
                else:
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)


# ---------------------------------------------------------------------------
# (D) EvidenceBank canonical schema validation
# ---------------------------------------------------------------------------


def _validate_evidence_bank_items(
    items: List[Any],
    normalized_text: str | None,
) -> None:
    seen_eids: Set[str] = set()
    seen_quotes: Set[str] = set()

    for i, item in enumerate(items):
        _require(isinstance(item, dict), f"evidence_bank.items[{i}] must be dict")

        eid = item.get("eid")
        _require(
            isinstance(eid, str) and eid.strip(),
            f"evidence_bank.items[{i}].eid must be non-empty str",
        )
        _require(eid not in seen_eids, f"evidence_bank: duplicate eid: {eid!r}")
        seen_eids.add(eid)

        quote = item.get("quote")
        _require(
            isinstance(quote, str) and quote.strip(),
            f"evidence_bank.items[{i}] ({eid}): quote must be non-empty str",
        )
        _require(quote not in seen_quotes, f"evidence_bank: duplicate quote at {eid!r}")
        seen_quotes.add(quote)

        locator = item.get("locator")
        _require(
            isinstance(locator, dict),
            f"evidence_bank.items[{i}] ({eid}): locator must be dict",
        )
        cs = locator.get("char_start")
        ce = locator.get("char_end")
        _require(isinstance(cs, int), f"evidence_bank.items[{i}] ({eid}): locator.char_start must be int")
        _require(isinstance(ce, int), f"evidence_bank.items[{i}] ({eid}): locator.char_end must be int")
        _require(cs >= 0, f"evidence_bank.items[{i}] ({eid}): locator.char_start must be >= 0")
        _require(cs < ce, f"evidence_bank.items[{i}] ({eid}): locator.char_start must be < char_end")

        source_id = item.get("source_id")
        _require(
            isinstance(source_id, str) and source_id.strip(),
            f"evidence_bank.items[{i}] ({eid}): source_id must be non-empty str",
        )

        # Transitional alias enforcement
        text_alias = item.get("text")
        if text_alias is not None:
            _require(
                text_alias == quote,
                f"evidence_bank.items[{i}] ({eid}): text alias must equal quote",
            )

        char_len = item.get("char_len")
        if char_len is not None:
            _require(
                isinstance(char_len, int) and char_len == len(quote),
                f"evidence_bank.items[{i}] ({eid}): char_len must equal len(quote)",
            )

        # Locator length consistency (reconstructibility without source text)
        _require(
            ce - cs == len(quote),
            f"evidence_bank.items[{i}] ({eid}): locator span [{cs}:{ce}] length {ce - cs} "
            f"!= len(quote) {len(quote)}",
        )

        # Full reconstructibility when normalized_text is available
        if normalized_text is not None:
            # (v0.2.1) bounds checks before slicing
            _require(
                cs <= len(normalized_text),
                f"evidence_bank.items[{i}] ({eid}): locator.char_start out of bounds: "
                f"{cs} > len(normalized_text) {len(normalized_text)}",
            )
            _require(
                ce <= len(normalized_text),
                f"evidence_bank.items[{i}] ({eid}): locator.char_end out of bounds: "
                f"{ce} > len(normalized_text) {len(normalized_text)}",
            )
            sliced = normalized_text[cs:ce]
            _require(
                sliced == quote,
                f"evidence_bank.items[{i}] ({eid}): locator mismatch — "
                f"normalized_text[{cs}:{ce}]={sliced!r} != quote={quote!r}",
            )


# ---------------------------------------------------------------------------
# (E) Near-duplicate link-rot validation
# ---------------------------------------------------------------------------


def _validate_near_duplicate_refs(
    phase2: Dict[str, Any],
    claim_registry: Set[str],
) -> None:
    """
    For every near_duplicate_of reference across all reviewer packs,
    ensure the referenced claim_id exists in the claim_registry.
    Raises RuntimeError on any dangling reference.
    """
    for reviewer, pack in phase2.items():
        if not isinstance(pack, dict):
            continue
        votes = pack.get("cross_claim_votes", [])
        if not isinstance(votes, list):
            continue
        for i, v in enumerate(votes):
            if not isinstance(v, dict):
                continue
            nd = v.get("near_duplicate_of")
            if not nd:
                continue
            for ref in nd:
                _require(
                    ref in claim_registry,
                    f"near_duplicate_of dangling reference in {reviewer}.cross_claim_votes[{i}]: "
                    f"{ref!r} not found in claim registry",
                )


# ---------------------------------------------------------------------------
# GSAE — Tier C validation (fail-closed, Tier A integrity)
# ---------------------------------------------------------------------------


def _is_numeric_not_bool(x: Any) -> bool:
    """True if x is int or float but not bool."""
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _validate_gsae_symmetry_packet(packet: Dict[str, Any]) -> None:
    """Validate a GSAESymmetryPacket dict — strict keyset, vocab, types.

    Accepts exactly one of two keysets:
      v0.2 (legacy): GSAE_SYMMETRY_PACKET_REQUIRED_KEYS (uses severity_tier)
      v0.3 (directional): GSAE_SYMMETRY_PACKET_V03_REQUIRED_KEYS
            (uses severity_toward_subject + severity_toward_counterparty)
    """
    pfx = "_validate_gsae_symmetry_packet"
    _require(isinstance(packet, dict), f"{pfx}: packet must be dict")

    keys = set(packet.keys())
    is_v02 = keys == GSAE_SYMMETRY_PACKET_REQUIRED_KEYS
    is_v03 = keys == GSAE_SYMMETRY_PACKET_V03_REQUIRED_KEYS
    _require(
        is_v02 or is_v03,
        f"{pfx}: key mismatch — keys do not match v0.2 or v0.3 keyset. "
        f"got={sorted(keys)}",
    )

    # --- Common fields (both versions) ---
    cb = packet["classification_bucket"]
    _require(
        cb in CLASSIFICATION_BUCKET_VALUES,
        f"{pfx}: classification_bucket invalid: {cb!r}",
    )

    il = packet["intent_level"]
    _require(
        isinstance(il, str) and il.strip(),
        f"{pfx}: intent_level must be non-empty str",
    )

    band = packet["confidence_band"]
    _require(
        band in SYMMETRY_BAND_VALUES_ORDERED,
        f"{pfx}: confidence_band invalid: {band!r}",
    )

    rc = packet["requires_corrob"]
    _require(
        isinstance(rc, bool),
        f"{pfx}: requires_corrob must be bool, got {type(rc).__name__}",
    )

    olb = packet["omission_load_bearing"]
    _require(
        isinstance(olb, bool),
        f"{pfx}: omission_load_bearing must be bool, got {type(olb).__name__}",
    )

    # --- Version-specific severity fields ---
    if is_v02:
        st = packet["severity_tier"]
        _require(
            st in SEVERITY_TIER_VALUES_ORDERED,
            f"{pfx}: severity_tier invalid: {st!r}",
        )
    else:
        sts = packet["severity_toward_subject"]
        _require(
            sts in SEVERITY_TIER_VALUES_ORDERED,
            f"{pfx}: severity_toward_subject invalid: {sts!r}",
        )
        stc = packet["severity_toward_counterparty"]
        _require(
            stc in SEVERITY_TIER_VALUES_ORDERED,
            f"{pfx}: severity_toward_counterparty invalid: {stc!r}",
        )


def _validate_gsae_subject(subject: Dict[str, Any]) -> None:
    """Validate a GSAESubject dict — strict keyset, all non-empty str."""
    pfx = "_validate_gsae_subject"
    _require(isinstance(subject, dict), f"{pfx}: subject must be dict")

    keys = set(subject.keys())
    _require(
        keys == GSAE_SUBJECT_REQUIRED_KEYS,
        f"{pfx}: key mismatch — "
        f"missing={sorted(GSAE_SUBJECT_REQUIRED_KEYS - keys)}, "
        f"extra={sorted(keys - GSAE_SUBJECT_REQUIRED_KEYS)}",
    )

    for k in sorted(GSAE_SUBJECT_REQUIRED_KEYS):
        val = subject[k]
        _require(
            isinstance(val, str) and val.strip(),
            f"{pfx}: {k} must be non-empty str, got {type(val).__name__}",
        )


def _validate_gsae_settings(settings: Dict[str, Any]) -> None:
    """Validate a GSAESettings dict — strict keyset, type/range checks."""
    pfx = "_validate_gsae_settings"
    _require(isinstance(settings, dict), f"{pfx}: settings must be dict")

    keys = set(settings.keys())
    _require(
        keys == GSAE_SETTINGS_REQUIRED_KEYS,
        f"{pfx}: key mismatch — "
        f"missing={sorted(GSAE_SETTINGS_REQUIRED_KEYS - keys)}, "
        f"extra={sorted(keys - GSAE_SETTINGS_REQUIRED_KEYS)}",
    )

    _require(
        isinstance(settings["enabled"], bool),
        f"{pfx}: enabled must be bool",
    )

    eps = settings["epsilon"]
    _require(
        _is_numeric_not_bool(eps),
        f"{pfx}: epsilon must be numeric (int/float), got {type(eps).__name__}",
    )

    tau = settings["tau"]
    _require(
        _is_numeric_not_bool(tau),
        f"{pfx}: tau must be numeric (int/float), got {type(tau).__name__}",
    )

    _require(eps >= 0, f"{pfx}: epsilon must be >= 0, got {eps}")
    _require(tau >= eps, f"{pfx}: tau must be >= epsilon ({eps}), got {tau}")

    # Version must be validated before weights (weights keyset depends on version).
    ver = settings["version"]
    _require(
        isinstance(ver, str) and ver.strip(),
        f"{pfx}: version must be non-empty str",
    )

    weights = settings["weights"]
    _require(isinstance(weights, dict), f"{pfx}: weights must be dict")

    # Weights keys must match the packet keyset for the declared version.
    if ver == "0.3":
        expected_w_keys = GSAE_SYMMETRY_PACKET_V03_REQUIRED_KEYS
    else:
        expected_w_keys = GSAE_SYMMETRY_PACKET_REQUIRED_KEYS

    w_keys = set(weights.keys())
    _require(
        w_keys == expected_w_keys,
        f"{pfx}: weights key mismatch for version {ver!r} — "
        f"missing={sorted(expected_w_keys - w_keys)}, "
        f"extra={sorted(w_keys - expected_w_keys)}",
    )
    for wk, wv in weights.items():
        _require(
            _is_numeric_not_bool(wv),
            f"{pfx}: weights[{wk!r}] must be numeric (int/float), got {type(wv).__name__}",
        )
        _require(
            wv >= 0,
            f"{pfx}: weights[{wk!r}] must be >= 0, got {wv}",
        )


def _validate_gsae_symmetry_artifact(artifact: Dict[str, Any]) -> None:
    """Validate a GSAESymmetryArtifact dict — strict keyset, status/flag consistency."""
    pfx = "_validate_gsae_symmetry_artifact"
    _require(isinstance(artifact, dict), f"{pfx}: artifact must be dict")

    keys = set(artifact.keys())
    _require(
        keys == GSAE_ARTIFACT_REQUIRED_KEYS,
        f"{pfx}: key mismatch — "
        f"missing={sorted(GSAE_ARTIFACT_REQUIRED_KEYS - keys)}, "
        f"extra={sorted(keys - GSAE_ARTIFACT_REQUIRED_KEYS)}",
    )

    status = artifact["symmetry_status"]
    _require(
        status in SYMMETRY_STATUS_VALUES,
        f"{pfx}: symmetry_status invalid: {status!r}",
    )

    delta = artifact["delta"]
    if status == "UNKNOWN":
        _require(
            delta is None,
            f"{pfx}: delta must be None when symmetry_status is UNKNOWN",
        )
    else:
        _require(
            _is_numeric_not_bool(delta),
            f"{pfx}: delta must be numeric when symmetry_status is {status!r}, "
            f"got {type(delta).__name__}",
        )

    eps = artifact["epsilon"]
    _require(
        _is_numeric_not_bool(eps),
        f"{pfx}: epsilon must be numeric (int/float), got {type(eps).__name__}",
    )

    tau = artifact["tau"]
    _require(
        _is_numeric_not_bool(tau),
        f"{pfx}: tau must be numeric (int/float), got {type(tau).__name__}",
    )

    # soft_symmetry_flag consistency: False for UNKNOWN/PASS, True for SOFT_FLAG/QUARANTINE
    flag = artifact["soft_symmetry_flag"]
    _require(isinstance(flag, bool), f"{pfx}: soft_symmetry_flag must be bool")

    if status in ("UNKNOWN", "PASS"):
        _require(
            flag is False,
            f"{pfx}: soft_symmetry_flag must be False when symmetry_status is {status!r}",
        )
    else:
        _require(
            flag is True,
            f"{pfx}: soft_symmetry_flag must be True when symmetry_status is {status!r}",
        )

    # quarantine_fields: list[str], entries must be known symmetry fields (any version)
    qf = artifact["quarantine_fields"]
    _require(isinstance(qf, list), f"{pfx}: quarantine_fields must be list")
    for i, f_name in enumerate(qf):
        _require(
            isinstance(f_name, str),
            f"{pfx}: quarantine_fields[{i}] must be str",
        )
        _require(
            f_name in SYMMETRY_FIELDS_ALL,
            f"{pfx}: quarantine_fields[{i}] invalid field: {f_name!r}",
        )

    # quarantine_fields must be empty unless status == QUARANTINE
    if status != "QUARANTINE":
        _require(
            len(qf) == 0,
            f"{pfx}: quarantine_fields must be empty when symmetry_status is {status!r}",
        )

    # field_deltas: dict, keys must be known symmetry fields (any version)
    fd = artifact["field_deltas"]
    _require(isinstance(fd, dict), f"{pfx}: field_deltas must be dict")
    for fk, fv in fd.items():
        _require(
            fk in SYMMETRY_FIELDS_ALL,
            f"{pfx}: field_deltas key {fk!r} not in SYMMETRY_FIELDS_ALL",
        )
        if fv is not None:
            _require(
                _is_numeric_not_bool(fv),
                f"{pfx}: field_deltas[{fk!r}] must be numeric or None, "
                f"got {type(fv).__name__}",
            )

    # notes: list of non-empty strings
    notes = artifact["notes"]
    _require(isinstance(notes, list), f"{pfx}: notes must be list")
    for i, n in enumerate(notes):
        _require(
            isinstance(n, str) and n.strip(),
            f"{pfx}: notes[{i}] must be non-empty str",
        )


# ---------------------------------------------------------------------------
# validate_run
# ---------------------------------------------------------------------------


def validate_run(run_state: Dict[str, Any], config: Dict[str, Any]) -> None:
    _require("phase2" in run_state, "run_state missing phase2")
    phase2 = run_state["phase2"]
    _require(isinstance(phase2, dict), "run_state.phase2 must be dict")

    # ------------------------------------------------------------------
    # EID integrity: no phantom EIDs
    # ------------------------------------------------------------------
    ev = run_state.get("evidence_bank", {})
    items = ev.get("items", [])
    _require(isinstance(items, list), "run_state.evidence_bank.items must be list")

    valid_eids = {it.get("eid") for it in items if isinstance(it, dict) and it.get("eid")}
    _require(len(valid_eids) > 0, "EvidenceBank has no valid eids")

    referenced: List[str] = []
    _collect_eids(run_state.get("phase2", {}), referenced)
    _collect_eids(run_state.get("adjudicated", {}), referenced)

    # (v0.2.1) normalize to stripped EIDs; skip whitespace-only entries
    bad = sorted({
        eid.strip() for eid in referenced
        if isinstance(eid, str) and eid.strip() and eid.strip() not in valid_eids
    })
    if bad:
        raise RuntimeError(f"EID integrity failure: referenced but not in EvidenceBank: {bad}")

    # ------------------------------------------------------------------
    # (D) EvidenceBank canonical schema validation
    # ------------------------------------------------------------------
    normalized_text: str | None = run_state.get("normalized_text")
    _validate_evidence_bank_items(items, normalized_text)

    # ------------------------------------------------------------------
    # Reviewer presence + pack validation
    # ------------------------------------------------------------------
    enabled = config.get("reviewers_enabled", [])
    _require(
        isinstance(enabled, list) and len(enabled) > 0,
        "config.reviewers_enabled must be a non-empty list",
    )

    expected = []
    for x in enabled:
        _require(isinstance(x, str) and x.strip(), "config.reviewers_enabled entries must be non-empty strings")
        expected.append(x.strip())

    for name in expected:
        _require(name in phase2, f"phase2 missing reviewer output: {name}")
        validate_reviewer_pack(phase2[name], config)

    # ------------------------------------------------------------------
    # (E) Near-duplicate link-rot: build claim registry then validate refs
    # ------------------------------------------------------------------
    claim_registry: Set[str] = set()
    for name in expected:
        pack = phase2[name]
        for claim in pack.get("claims", []):
            cid = claim.get("claim_id")
            if isinstance(cid, str) and cid.strip():
                claim_registry.add(cid)

    _validate_near_duplicate_refs(phase2, claim_registry)

    # ------------------------------------------------------------------
    # Verification layer
    # ------------------------------------------------------------------
    _validate_verification(run_state, config)

    # ------------------------------------------------------------------
    # GSAE — Tier C validation (only if GSAE data present in run_state)
    # Tier A validations above run first and fail first.
    # ------------------------------------------------------------------
    _validate_gsae_run_state(run_state)


# ---------------------------------------------------------------------------
# GSAE run_state orchestration
# ---------------------------------------------------------------------------


def _validate_gsae_run_state(run_state: Dict[str, Any]) -> None:
    """Validate all GSAE objects in run_state, if present.

    Gated: does nothing if no GSAE keys exist.
    If any GSAE key is present, validates all GSAE objects strictly.
    """
    pfx = "_validate_gsae_run_state"
    gsae = run_state.get("gsae")
    if gsae is None:
        return

    _require(isinstance(gsae, dict), f"{pfx}: run_state.gsae must be dict")

    # Settings must be present if gsae block exists
    settings = gsae.get("settings")
    _require(settings is not None, f"{pfx}: run_state.gsae.settings missing")
    _validate_gsae_settings(settings)

    # Packet pairs: list of {packet_a, packet_b} dicts
    pairs = gsae.get("packet_pairs")
    if pairs is not None:
        _require(isinstance(pairs, list), f"{pfx}: run_state.gsae.packet_pairs must be list")
        for i, pair in enumerate(pairs):
            _require(isinstance(pair, dict), f"{pfx}: packet_pairs[{i}] must be dict")
            _require("packet_a" in pair, f"{pfx}: packet_pairs[{i}] missing packet_a")
            _require("packet_b" in pair, f"{pfx}: packet_pairs[{i}] missing packet_b")
            _validate_gsae_symmetry_packet(pair["packet_a"])
            _validate_gsae_symmetry_packet(pair["packet_b"])

    # Artifacts: list of SymmetryArtifact dicts
    artifacts = gsae.get("artifacts")
    if artifacts is not None:
        _require(isinstance(artifacts, list), f"{pfx}: run_state.gsae.artifacts must be list")
        for i, art in enumerate(artifacts):
            _validate_gsae_symmetry_artifact(art)


# ---------------------------------------------------------------------------
# Verification layer validation
# ---------------------------------------------------------------------------


def _validate_verification(run_state: Dict[str, Any], config: Dict[str, Any]) -> None:
    from engine.verify.base import (  # local import: verify layer is optional
        CLAIM_KINDS,
        CONFIDENCE_VALUES as VERIFY_CONFIDENCE_VALUES,
        SOURCE_TYPES,
        VERIFICATION_STATUSES,
    )

    verification_enabled = bool(config.get("verification_enabled", False))
    pack = run_state.get("verification")

    if not verification_enabled:
        if pack is None:
            return
        _require(isinstance(pack, dict), "run_state.verification must be dict when present")
        enabled_flag = pack.get("enabled")
        if enabled_flag is not None:
            _require(
                enabled_flag is False,
                "run_state.verification.enabled must be False when verification_enabled=false",
            )
        return

    # verification_enabled=True: pack must be present and well-formed
    _require(pack is not None, "run_state.verification missing but verification_enabled=true")
    _require(isinstance(pack, dict), "run_state.verification must be dict")
    _require(
        pack.get("enabled") is True,
        "run_state.verification.enabled must be True when verification_enabled=true",
    )

    results = pack.get("results")
    _require(isinstance(results, list), "run_state.verification.results must be list")

    # Validate verification_kinds_enabled config
    kinds_enabled_raw = config.get("verification_kinds_enabled", list(CLAIM_KINDS))
    _require(isinstance(kinds_enabled_raw, list), "config.verification_kinds_enabled must be a list")
    kinds_enabled: set[str] = set()
    for k in kinds_enabled_raw:
        _require(
            k in CLAIM_KINDS,
            f"config.verification_kinds_enabled contains unknown kind: {k!r}",
        )
        kinds_enabled.add(k)

    seen_ids: set[str] = set()

    for i, r in enumerate(results):
        _require(isinstance(r, dict), f"verification result[{i}] must be dict")

        claim_id = r.get("claim_id")
        _require(
            isinstance(claim_id, str) and claim_id.strip(),
            f"verification result[{i}].claim_id must be a non-empty string",
        )
        _require(
            claim_id not in seen_ids,
            f"duplicate claim_id in verification results: {claim_id!r}",
        )
        seen_ids.add(claim_id)

        claim_text = r.get("claim_text")
        _require(
            isinstance(claim_text, str) and claim_text.strip(),
            f"verification result[{i}].claim_text must be non-empty",
        )

        claim_kind = r.get("claim_kind")
        _require(
            claim_kind in CLAIM_KINDS,
            f"verification result[{i}].claim_kind invalid: {claim_kind!r}",
        )

        status = r.get("verification_status")
        _require(
            status in VERIFICATION_STATUSES,
            f"verification result[{i}].verification_status invalid: {status!r}",
        )

        confidence = r.get("confidence")
        _require(
            confidence in VERIFY_CONFIDENCE_VALUES,
            f"verification result[{i}].confidence invalid: {confidence!r}",
        )

        method_note = r.get("method_note")
        _require(
            isinstance(method_note, str) and method_note.strip(),
            f"verification result[{i}].method_note must be non-empty",
        )

        checked_at = r.get("checked_at")
        _require(
            isinstance(checked_at, str) and checked_at.strip(),
            f"verification result[{i}].checked_at must be non-empty",
        )

        # (fix) Symmetric authority rule: exempt not_checked_yet AND not_verifiable.
        authority_sources = r.get("authority_sources")
        _require(
            isinstance(authority_sources, list),
            f"verification result[{i}].authority_sources must be list",
        )

        if status not in AUTHORITY_SOURCES_EXEMPT_STATUSES:
            _require(
                len(authority_sources) > 0,
                f"verification result[{i}].authority_sources must be non-empty when status={status!r}",
            )

        for j, src in enumerate(authority_sources):
            _require(
                isinstance(src, dict),
                f"verification result[{i}].authority_sources[{j}] must be dict",
            )
            src_type = src.get("source_type")
            _require(
                src_type in SOURCE_TYPES,
                f"verification result[{i}].authority_sources[{j}].source_type invalid: {src_type!r}",
            )
            has_locator = isinstance(src.get("locator"), str) and bool(src["locator"].strip())
            has_url = isinstance(src.get("url"), str) and bool(src["url"].strip())
            _require(
                has_locator or has_url,
                f"verification result[{i}].authority_sources[{j}] must have locator or url",
            )
