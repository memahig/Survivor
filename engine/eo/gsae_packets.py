"""
engine/eo/gsae_packets.py  v0.1 — GSAE Observation Extraction

Extracts optional gsae_observation blocks from validated Phase 2
reviewer packs. Pure function, no I/O, no side effects.

Pipeline position: post-Phase2, pre-adjudication.
Does NOT perform swaps (swap transform belongs to a future task).
Does NOT call compute_symmetry (wiring deferred until swap exists).
Does NOT mutate phase2_outputs.

Trilateral session: 2026-03-01
Authorized by: ChatGPT (Coordinator), Gemini (Structural Critic), Claude (Code Author)
"""

from __future__ import annotations

from typing import Any, Dict, List


def extract_gsae_observations(
    phase2_outputs: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Extract optional gsae_observation blocks from phase2 reviewer packs.

    Returns:
      [{"reviewer": <pack["reviewer"]>, "observation": <pack["gsae_observation"]>}, ...]

    Deterministic ordering: iterate reviewer names in sorted(phase2_outputs.keys()).
    If none present, return [].

    Notes:
    - Phase2 packs are already validated by validate_run; if a pack contains
      gsae_observation it has already been validated via validate_reviewer_pack
      (Task 9).
    """
    out: List[Dict[str, Any]] = []
    for name in sorted(phase2_outputs.keys()):
        pack = phase2_outputs[name]
        if not isinstance(pack, dict):
            continue
        obs = pack.get("gsae_observation")
        if obs is None:
            continue
        reviewer = pack.get("reviewer")
        out.append({"reviewer": reviewer, "observation": obs})
    return out
