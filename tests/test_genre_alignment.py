#!/usr/bin/env python3
"""
tests/test_genre_alignment.py — GSAE Tier C validation + skeleton tests

Task 6: validator stress tests, config integrity, skeleton smoke test.
No symmetry math tested (compute_symmetry is still NotImplementedError).

Uses real schema_constants + real validators (no mocks).
Assertion rule: RuntimeError messages must start with validator function name.
"""

from __future__ import annotations

import copy
import json
import os

import pytest

from engine.core.validators import (
    _validate_gsae_settings,
    _validate_gsae_symmetry_artifact,
    _validate_gsae_symmetry_packet,
)


# ---------------------------------------------------------------------------
# Fixtures — canonical valid objects
# ---------------------------------------------------------------------------

def _valid_packet() -> dict:
    return {
        "classification_bucket": "reporting",
        "intent_level": "informational",
        "requires_corrob": True,
        "omission_load_bearing": False,
        "severity_tier": "moderate",
        "confidence_band": "sb_mid",
    }


def _valid_settings() -> dict:
    return {
        "enabled": True,
        "epsilon": 0.1,
        "tau": 0.25,
        "weights": {
            "classification_bucket": 0.25,
            "intent_level": 0.25,
            "severity_tier": 0.2,
            "requires_corrob": 0.1,
            "omission_load_bearing": 0.1,
            "confidence_band": 0.1,
        },
        "version": "0.2",
    }


def _valid_artifact_pass() -> dict:
    return {
        "symmetry_status": "PASS",
        "delta": 0.05,
        "epsilon": 0.1,
        "tau": 0.25,
        "soft_symmetry_flag": False,
        "quarantine_fields": [],
        "field_deltas": {"classification_bucket": 0.0, "severity_tier": 0.1},
        "notes": [],
    }


def _valid_artifact_quarantine() -> dict:
    return {
        "symmetry_status": "QUARANTINE",
        "delta": 0.7,
        "epsilon": 0.1,
        "tau": 0.25,
        "soft_symmetry_flag": True,
        "quarantine_fields": ["classification_bucket", "severity_tier"],
        "field_deltas": {"classification_bucket": 1.0, "severity_tier": 0.5},
        "notes": ["Two fields quarantined"],
    }


def _valid_artifact_unknown() -> dict:
    return {
        "symmetry_status": "UNKNOWN",
        "delta": None,
        "epsilon": 0.1,
        "tau": 0.25,
        "soft_symmetry_flag": False,
        "quarantine_fields": [],
        "field_deltas": {},
        "notes": ["Insufficient determinate fields"],
    }


def _valid_artifact_soft_flag() -> dict:
    return {
        "symmetry_status": "SOFT_FLAG",
        "delta": 0.15,
        "epsilon": 0.1,
        "tau": 0.25,
        "soft_symmetry_flag": True,
        "quarantine_fields": [],
        "field_deltas": {"intent_level": 0.15},
        "notes": ["Marginal divergence detected"],
    }


# ===================================================================
# GROUP A — Validator stress tests
# ===================================================================


# --- A1: _validate_gsae_symmetry_packet ---

class TestValidateGSAESymmetryPacket:

    def test_valid_packet_passes(self):
        _validate_gsae_symmetry_packet(_valid_packet())

    def test_extra_key_fails(self):
        pkt = _valid_packet()
        pkt["rogue_key"] = "surprise"
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_packet(pkt)
        assert str(exc.value).startswith("_validate_gsae_symmetry_packet")

    def test_missing_key_fails(self):
        pkt = _valid_packet()
        del pkt["intent_level"]
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_packet(pkt)
        assert str(exc.value).startswith("_validate_gsae_symmetry_packet")

    def test_invalid_classification_bucket_fails(self):
        pkt = _valid_packet()
        pkt["classification_bucket"] = "analysis"  # from ARTICLE_CLASSIFICATIONS, not bucket vocab
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_packet(pkt)
        assert str(exc.value).startswith("_validate_gsae_symmetry_packet")

    def test_invalid_severity_tier_fails(self):
        pkt = _valid_packet()
        pkt["severity_tier"] = "extreme"
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_packet(pkt)
        assert str(exc.value).startswith("_validate_gsae_symmetry_packet")

    def test_invalid_confidence_band_fails(self):
        pkt = _valid_packet()
        pkt["confidence_band"] = "high"  # from CONFIDENCE_VALUES, not sb_* vocab
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_packet(pkt)
        assert str(exc.value).startswith("_validate_gsae_symmetry_packet")

    def test_requires_corrob_not_bool_fails(self):
        pkt = _valid_packet()
        pkt["requires_corrob"] = "yes"
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_packet(pkt)
        assert str(exc.value).startswith("_validate_gsae_symmetry_packet")

    def test_omission_load_bearing_not_bool_fails(self):
        pkt = _valid_packet()
        pkt["omission_load_bearing"] = 1
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_packet(pkt)
        assert str(exc.value).startswith("_validate_gsae_symmetry_packet")

    def test_intent_level_empty_fails(self):
        pkt = _valid_packet()
        pkt["intent_level"] = "   "
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_packet(pkt)
        assert str(exc.value).startswith("_validate_gsae_symmetry_packet")

    def test_not_a_dict_fails(self):
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_packet("not a dict")
        assert str(exc.value).startswith("_validate_gsae_symmetry_packet")

    def test_all_valid_bucket_values(self):
        """Every classification_bucket value in the vocab passes."""
        from engine.core.schema_constants import CLASSIFICATION_BUCKET_VALUES
        for val in sorted(CLASSIFICATION_BUCKET_VALUES):
            pkt = _valid_packet()
            pkt["classification_bucket"] = val
            _validate_gsae_symmetry_packet(pkt)

    def test_all_valid_severity_tiers(self):
        from engine.core.schema_constants import SEVERITY_TIER_VALUES_ORDERED
        for val in SEVERITY_TIER_VALUES_ORDERED:
            pkt = _valid_packet()
            pkt["severity_tier"] = val
            _validate_gsae_symmetry_packet(pkt)

    def test_all_valid_confidence_bands(self):
        from engine.core.schema_constants import SYMMETRY_BAND_VALUES_ORDERED
        for val in SYMMETRY_BAND_VALUES_ORDERED:
            pkt = _valid_packet()
            pkt["confidence_band"] = val
            _validate_gsae_symmetry_packet(pkt)


# --- A2: _validate_gsae_settings ---

class TestValidateGSAESettings:

    def test_valid_settings_passes(self):
        _validate_gsae_settings(_valid_settings())

    def test_bool_trap_epsilon_fails(self):
        s = _valid_settings()
        s["epsilon"] = True
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_settings(s)
        assert str(exc.value).startswith("_validate_gsae_settings")

    def test_bool_trap_tau_fails(self):
        s = _valid_settings()
        s["tau"] = False
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_settings(s)
        assert str(exc.value).startswith("_validate_gsae_settings")

    def test_epsilon_greater_than_tau_fails(self):
        s = _valid_settings()
        s["epsilon"] = 0.6
        s["tau"] = 0.3
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_settings(s)
        assert str(exc.value).startswith("_validate_gsae_settings")

    def test_epsilon_equals_tau_passes(self):
        s = _valid_settings()
        s["epsilon"] = 0.2
        s["tau"] = 0.2
        _validate_gsae_settings(s)

    def test_negative_epsilon_fails(self):
        s = _valid_settings()
        s["epsilon"] = -0.01
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_settings(s)
        assert str(exc.value).startswith("_validate_gsae_settings")

    def test_weights_missing_key_fails(self):
        s = _valid_settings()
        del s["weights"]["intent_level"]
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_settings(s)
        assert str(exc.value).startswith("_validate_gsae_settings")

    def test_weights_extra_key_fails(self):
        s = _valid_settings()
        s["weights"]["rogue_field"] = 0.5
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_settings(s)
        assert str(exc.value).startswith("_validate_gsae_settings")

    def test_weights_bool_value_fails(self):
        s = _valid_settings()
        s["weights"]["intent_level"] = False
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_settings(s)
        assert str(exc.value).startswith("_validate_gsae_settings")

    def test_weights_negative_value_fails(self):
        s = _valid_settings()
        s["weights"]["severity_tier"] = -0.1
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_settings(s)
        assert str(exc.value).startswith("_validate_gsae_settings")

    def test_int_epsilon_tau_accepted(self):
        """int values for epsilon/tau should be accepted (JSON compat)."""
        s = _valid_settings()
        s["epsilon"] = 0
        s["tau"] = 1
        _validate_gsae_settings(s)

    def test_int_weight_values_accepted(self):
        """int values for weights should be accepted (JSON compat)."""
        s = _valid_settings()
        for k in s["weights"]:
            s["weights"][k] = 1
        _validate_gsae_settings(s)

    def test_enabled_not_bool_fails(self):
        s = _valid_settings()
        s["enabled"] = 1
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_settings(s)
        assert str(exc.value).startswith("_validate_gsae_settings")

    def test_version_empty_fails(self):
        s = _valid_settings()
        s["version"] = ""
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_settings(s)
        assert str(exc.value).startswith("_validate_gsae_settings")

    def test_extra_settings_key_fails(self):
        s = _valid_settings()
        s["extra"] = "nope"
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_settings(s)
        assert str(exc.value).startswith("_validate_gsae_settings")

    def test_missing_settings_key_fails(self):
        s = _valid_settings()
        del s["version"]
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_settings(s)
        assert str(exc.value).startswith("_validate_gsae_settings")


# --- A3: _validate_gsae_symmetry_artifact ---

class TestValidateGSAESymmetryArtifact:

    def test_pass_artifact_valid(self):
        _validate_gsae_symmetry_artifact(_valid_artifact_pass())

    def test_quarantine_artifact_valid(self):
        _validate_gsae_symmetry_artifact(_valid_artifact_quarantine())

    def test_unknown_artifact_valid(self):
        _validate_gsae_symmetry_artifact(_valid_artifact_unknown())

    def test_soft_flag_artifact_valid(self):
        _validate_gsae_symmetry_artifact(_valid_artifact_soft_flag())

    def test_unknown_with_delta_not_none_fails(self):
        art = _valid_artifact_unknown()
        art["delta"] = 0.3
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_artifact(art)
        assert str(exc.value).startswith("_validate_gsae_symmetry_artifact")

    def test_pass_with_delta_none_fails(self):
        art = _valid_artifact_pass()
        art["delta"] = None
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_artifact(art)
        assert str(exc.value).startswith("_validate_gsae_symmetry_artifact")

    def test_soft_flag_with_flag_false_fails(self):
        art = _valid_artifact_soft_flag()
        art["soft_symmetry_flag"] = False
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_artifact(art)
        assert str(exc.value).startswith("_validate_gsae_symmetry_artifact")

    def test_pass_with_flag_true_fails(self):
        art = _valid_artifact_pass()
        art["soft_symmetry_flag"] = True
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_artifact(art)
        assert str(exc.value).startswith("_validate_gsae_symmetry_artifact")

    def test_quarantine_with_flag_false_fails(self):
        art = _valid_artifact_quarantine()
        art["soft_symmetry_flag"] = False
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_artifact(art)
        assert str(exc.value).startswith("_validate_gsae_symmetry_artifact")

    def test_pass_with_quarantine_fields_nonempty_fails(self):
        art = _valid_artifact_pass()
        art["quarantine_fields"] = ["severity_tier"]
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_artifact(art)
        assert str(exc.value).startswith("_validate_gsae_symmetry_artifact")

    def test_field_deltas_rogue_key_fails(self):
        art = _valid_artifact_pass()
        art["field_deltas"] = {"rogue_field": 0.5}
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_artifact(art)
        assert str(exc.value).startswith("_validate_gsae_symmetry_artifact")

    def test_field_deltas_bool_value_fails(self):
        art = _valid_artifact_pass()
        art["field_deltas"] = {"classification_bucket": True}
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_artifact(art)
        assert str(exc.value).startswith("_validate_gsae_symmetry_artifact")

    def test_quarantine_fields_rogue_field_fails(self):
        art = _valid_artifact_quarantine()
        art["quarantine_fields"] = ["nonexistent_field"]
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_artifact(art)
        assert str(exc.value).startswith("_validate_gsae_symmetry_artifact")

    def test_invalid_symmetry_status_fails(self):
        art = _valid_artifact_pass()
        art["symmetry_status"] = "INVALID"
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_artifact(art)
        assert str(exc.value).startswith("_validate_gsae_symmetry_artifact")

    def test_extra_artifact_key_fails(self):
        art = _valid_artifact_pass()
        art["extra"] = "nope"
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_artifact(art)
        assert str(exc.value).startswith("_validate_gsae_symmetry_artifact")

    def test_missing_artifact_key_fails(self):
        art = _valid_artifact_pass()
        del art["notes"]
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_artifact(art)
        assert str(exc.value).startswith("_validate_gsae_symmetry_artifact")

    def test_notes_empty_string_fails(self):
        art = _valid_artifact_pass()
        art["notes"] = [""]
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_artifact(art)
        assert str(exc.value).startswith("_validate_gsae_symmetry_artifact")

    def test_delta_bool_fails(self):
        art = _valid_artifact_pass()
        art["delta"] = True
        with pytest.raises(RuntimeError) as exc:
            _validate_gsae_symmetry_artifact(art)
        assert str(exc.value).startswith("_validate_gsae_symmetry_artifact")

    def test_field_deltas_none_value_accepted(self):
        """None values in field_deltas are valid (indeterminate field)."""
        art = _valid_artifact_pass()
        art["field_deltas"] = {"intent_level": None, "severity_tier": 0.1}
        _validate_gsae_symmetry_artifact(art)


# ===================================================================
# GROUP B — Config integrity
# ===================================================================


class TestConfigIntegrity:

    def test_config_has_gsae_settings(self):
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "engine", "core", "config.json"
        )
        with open(config_path) as f:
            config = json.load(f)
        assert "gsae_settings" in config

    def test_config_gsae_settings_validates(self):
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "engine", "core", "config.json"
        )
        with open(config_path) as f:
            config = json.load(f)
        _validate_gsae_settings(config["gsae_settings"])

    def test_config_weights_match_v01_spec(self):
        """Weights must match Tier C v0.1 locked defaults."""
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "engine", "core", "config.json"
        )
        with open(config_path) as f:
            config = json.load(f)
        w = config["gsae_settings"]["weights"]
        assert w["classification_bucket"] == 0.25
        assert w["intent_level"] == 0.25
        assert w["severity_tier"] == 0.2
        assert w["requires_corrob"] == 0.1
        assert w["omission_load_bearing"] == 0.1
        assert w["confidence_band"] == 0.1


# ===================================================================
# GROUP C — Skeleton smoke test
# ===================================================================


class TestSkeletonSmoke:

    def test_compute_symmetry_raises_not_implemented(self):
        from engine.eo.genre_alignment import compute_symmetry

        pkt_a = _valid_packet()
        pkt_b = _valid_packet()
        settings = _valid_settings()

        with pytest.raises(NotImplementedError):
            compute_symmetry(pkt_a, pkt_b, settings)

    def test_import_types_from_core_schemas(self):
        """GSAESymmetryPacket, GSAESettings, GSAESymmetryArtifact importable from core."""
        from engine.core.schemas import (
            GSAESettings,
            GSAESymmetryArtifact,
            GSAESymmetryPacket,
        )
        assert GSAESymmetryPacket is not None
        assert GSAESettings is not None
        assert GSAESymmetryArtifact is not None
