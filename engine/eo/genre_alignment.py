"""
engine/eo/genre_alignment.py  v0.2 — GSAE Implementation

Genre Symmetry & Alignment Engine (Tier C).

Pipeline position: post-extraction, pre-judge.
Receives two structured GSAESymmetryPackets (original + swapped),
returns a GSAESymmetryArtifact describing field-level symmetry status.

Does NOT mutate packets.
Does NOT perform swaps (swap generation belongs to extraction layer).
Does NOT load config (settings passed in by caller).

Tier C invariants:
  - Symmetry overrides consensus at field level.
  - Consensus never rescues contaminated fields.
  - soft_symmetry_flag is audit-only, zero mechanical effect.

Trilateral session: 2026-03-01
Authorized by: ChatGPT (Coordinator), Gemini (Structural Critic), Claude (Code Author)
"""

from __future__ import annotations

from engine.core.schema_constants import (
    GSAE_SYMMETRY_PACKET_V03_REQUIRED_KEYS,
    SEVERITY_TIER_VALUES_ORDERED,
    SYMMETRY_BAND_VALUES_ORDERED,
    SYMMETRY_FIELDS_BASE,
    SYMMETRY_FIELDS_V03,
)
from engine.core.schemas import (
    GSAESettings,
    GSAESymmetryArtifact,
    GSAESymmetryPacket,
)


# ---------------------------------------------------------------------------
# Field classification (v0.1 locked)
# ---------------------------------------------------------------------------

# Ordinal fields with their ordered scales (index determines distance).
_ORDINAL_SCALES: dict[str, tuple[str, ...]] = {
    "severity_tier": SEVERITY_TIER_VALUES_ORDERED,
    "severity_toward_subject": SEVERITY_TIER_VALUES_ORDERED,
    "severity_toward_counterparty": SEVERITY_TIER_VALUES_ORDERED,
    "confidence_band": SYMMETRY_BAND_VALUES_ORDERED,
}

# Boolean fields (binary distance: 0.0 if equal, 1.0 if not).
_BOOLEAN_FIELDS: frozenset[str] = frozenset({
    "requires_corrob",
    "omission_load_bearing",
})

# All remaining SYMMETRY_FIELDS_BASE fields are categorical
# (string equality: 0.0 if equal, 1.0 if not).


# ---------------------------------------------------------------------------
# Distance functions (pure, no side effects)
# ---------------------------------------------------------------------------

def _ordinal_distance(
    val_a: str, val_b: str, scale: tuple[str, ...]
) -> float | None:
    """Normalized ordinal distance in [0,1], or None if value not in scale."""
    try:
        idx_a = scale.index(val_a)
        idx_b = scale.index(val_b)
    except ValueError:
        return None
    n = len(scale)
    if n <= 1:
        return 0.0
    return abs(idx_a - idx_b) / (n - 1)


def _field_distance(field: str, val_a: object, val_b: object) -> float | None:
    """Compute per-field distance. Returns float in [0,1] or None if indeterminate."""
    if field in _ORDINAL_SCALES:
        return _ordinal_distance(val_a, val_b, _ORDINAL_SCALES[field])
    if field in _BOOLEAN_FIELDS:
        if not isinstance(val_a, bool) or not isinstance(val_b, bool):
            return None
        return 0.0 if val_a == val_b else 1.0
    # Categorical: exact string match
    if not isinstance(val_a, str) or not isinstance(val_b, str):
        return None
    return 0.0 if val_a == val_b else 1.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_symmetry(
    packet_a: GSAESymmetryPacket,
    packet_b: GSAESymmetryPacket,
    settings: GSAESettings,
) -> GSAESymmetryArtifact:
    """Compute symmetry artifact by comparing two structured packets.

    packet_a: original extraction packet (structured fields only).
    packet_b: swapped extraction packet (produced by extraction layer).
    settings: calibration values from config.json gsae_settings block.

    Returns a GSAESymmetryArtifact with field-level deltas and zone classification.

    No side effects. No I/O. Deterministic.
    """
    eps = settings["epsilon"]
    tau = settings["tau"]
    weights = settings["weights"]

    # --- Detect packet version from keys ---
    pkt_keys = set(packet_a.keys())
    if pkt_keys == GSAE_SYMMETRY_PACKET_V03_REQUIRED_KEYS:
        active_fields = SYMMETRY_FIELDS_V03
    else:
        active_fields = SYMMETRY_FIELDS_BASE

    # --- Per-field deltas (all fields in active set) ---
    field_deltas: dict[str, float | None] = {}
    notes: list[str] = []

    for field in sorted(active_fields):
        val_a = packet_a.get(field)
        val_b = packet_b.get(field)

        if val_a is None or val_b is None:
            field_deltas[field] = None
            notes.append(
                f"Indeterminate field delta for '{field}' (excluded from delta)."
            )
            continue

        d_f = _field_distance(field, val_a, val_b)

        if d_f is None:
            field_deltas[field] = None
            notes.append(
                f"Indeterminate field delta for '{field}' (excluded from delta)."
            )
        else:
            field_deltas[field] = round(d_f, 6)

    # --- Weighted aggregate delta ---
    determinate = [
        f for f in sorted(active_fields)
        if field_deltas.get(f) is not None and weights.get(f, 0) > 0
    ]

    if not determinate:
        delta = None
        status = "UNKNOWN"
        notes.append(
            "No determinate symmetry fields available for delta computation."
        )
    else:
        w_sum = sum(weights[f] for f in determinate)
        raw_delta = sum(
            weights[f] * field_deltas[f] for f in determinate
        ) / w_sum
        delta = round(raw_delta, 6)

        if delta <= eps:
            status = "PASS"
        elif delta < tau:
            status = "SOFT_FLAG"
            notes.append("Soft flag: epsilon < delta < tau (audit-only).")
        else:
            status = "QUARANTINE"
            notes.append(
                "Quarantine triggered: delta >= tau; divergent fields listed."
            )

    # --- Derived outputs ---
    soft_flag = status in ("SOFT_FLAG", "QUARANTINE")

    if status == "QUARANTINE":
        quarantine_fields = sorted(
            f for f in active_fields
            if field_deltas.get(f) is not None and field_deltas[f] > 0.0
        )
    else:
        quarantine_fields = []

    return {
        "symmetry_status": status,
        "delta": delta,
        "epsilon": eps,
        "tau": tau,
        "soft_symmetry_flag": soft_flag,
        "quarantine_fields": quarantine_fields,
        "field_deltas": field_deltas,
        "notes": notes,
    }
