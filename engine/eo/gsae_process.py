"""
engine/eo/gsae_process.py  v0.1 — GSAE Tier C Runner

Orchestrates the full Tier C pipeline: observation extraction →
null swap (Task 11) → compute_symmetry → artifact collection.

Returns a validator-compliant gsae block for run_state, or None
if GSAE is disabled or no observations exist.

Does NOT define real swap semantics (deferred to Task 12).
Does NOT mutate phase2_outputs.
No I/O. Deterministic.

Trilateral session: 2026-03-01
Authorized by: ChatGPT (Coordinator), Gemini (Structural Critic), Claude (Code Author)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine.eo.genre_alignment import compute_symmetry
from engine.eo.gsae_packets import extract_gsae_observations


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

    Swap transform: NULL (packet_b = packet_a). Real swap deferred to Task 12.
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
        packet_b = packet_a  # NULL swap — delta will be 0.0 → PASS

        artifact = compute_symmetry(packet_a, packet_b, gsae_settings)

        packet_pairs.append({"packet_a": packet_a, "packet_b": packet_b})
        artifacts.append(artifact)

    return {
        "settings": gsae_settings,
        "packet_pairs": packet_pairs,
        "artifacts": artifacts,
    }
