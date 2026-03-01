"""
engine/eo/gsae_process.py  v0.2 — GSAE Tier C Runner

Orchestrates the full Tier C pipeline: observation extraction →
version-aware swap → compute_symmetry → artifact collection.

Returns a validator-compliant gsae block for run_state, or None
if GSAE is disabled or no observations exist.

Swap semantics (Task 13):
  v0.3 packets: flip severity_toward_subject ↔ severity_toward_counterparty
  v0.2 packets: null swap (packet_b = packet_a), delta=0.0 → PASS

Does NOT mutate phase2_outputs.
No I/O. Deterministic.

Trilateral session: 2026-03-01
Authorized by: ChatGPT (Coordinator), Gemini (Structural Critic), Claude (Code Author)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine.core.schema_constants import (
    GSAE_SYMMETRY_PACKET_V03_REQUIRED_KEYS,
)
from engine.eo.genre_alignment import compute_symmetry
from engine.eo.gsae_packets import extract_gsae_observations


def _is_v03_packet(packet: Dict[str, Any]) -> bool:
    """True if packet has v0.3 directional keyset."""
    return set(packet.keys()) == GSAE_SYMMETRY_PACKET_V03_REQUIRED_KEYS


def _build_swapped_packet(packet_a: Dict[str, Any]) -> Dict[str, Any]:
    """Create packet_b by flipping directional severity fields.

    For v0.3 packets: swap severity_toward_subject ↔ severity_toward_counterparty.
    For v0.2 packets: null swap (identity — packet_b = packet_a).
    """
    if not _is_v03_packet(packet_a):
        return packet_a  # null swap for legacy packets

    packet_b = dict(packet_a)
    packet_b["severity_toward_subject"] = packet_a["severity_toward_counterparty"]
    packet_b["severity_toward_counterparty"] = packet_a["severity_toward_subject"]
    return packet_b


def run_gsae_tier_c(
    phase2_outputs: Dict[str, Dict[str, Any]],
    config: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Run Tier C symmetry pipeline and return a gsae block, or None.

    Returns None (no run_state["gsae"]) when:
      - gsae_settings.enabled is not True
      - no gsae_observation blocks found in phase2 packs

    When observations exist, produces a validator-compliant dict:
      {"settings": GSAESettings, "packet_pairs": [...], "artifacts": [...]}

    Swap transform:
      v0.3: flip severity_toward_subject ↔ severity_toward_counterparty
      v0.2: null swap (packet_b = packet_a), delta=0.0 → PASS
    """
    gsae_settings = config.get("gsae_settings")
    if not isinstance(gsae_settings, dict) or gsae_settings.get("enabled") is not True:
        return None

    observations = extract_gsae_observations(phase2_outputs)
    if not observations:
        return None

    packet_pairs: List[Dict[str, Any]] = []
    artifacts: List[Dict[str, Any]] = []

    for obs in observations:
        packet_a = obs["observation"]
        packet_b = _build_swapped_packet(packet_a)

        artifact = compute_symmetry(packet_a, packet_b, gsae_settings)

        packet_pairs.append({"packet_a": packet_a, "packet_b": packet_b})
        artifacts.append(artifact)

    return {
        "settings": gsae_settings,
        "packet_pairs": packet_pairs,
        "artifacts": artifacts,
    }
