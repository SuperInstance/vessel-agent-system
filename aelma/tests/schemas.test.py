"""Tests for the AELMA vessel-action payload schemas and validator.

Run from the repo root:  python -m pytest tests/schemas.test.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

AELMA_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AELMA_ROOT))

from schema.actions import ACTION_SPECS, VESSEL_ACTION_SCHEMAS  # noqa: E402
from schema.validator import (  # noqa: E402
    UnknownActionError,
    is_valid,
    validate_action_payload,
)


# ---------------------------------------------------------------------------
# Schema registry shape
# ---------------------------------------------------------------------------


def test_all_expected_actions_registered():
    for action in (
        "haul_gear",
        "anchor_drop",
        "raise_alert",
        "clear_alerts",
        "morph_to_navigation_mode",
    ):
        assert action in VESSEL_ACTION_SCHEMAS, f"missing schema for {action}"


def test_schemas_are_well_formed():
    for name, spec in VESSEL_ACTION_SCHEMAS.items():
        assert isinstance(spec["description"], str) and spec["description"]
        for req in spec.get("required", []):
            assert req in spec["properties"], f"{name}: required {req} not in properties"
        for fname, fspec in spec["properties"].items():
            assert "type" in fspec, f"{name}.{fname} missing type"
            assert fspec["type"] in (
                "string", "number", "integer", "boolean", "array", "object"
            ), f"{name}.{fname} bad type {fspec['type']}"


def test_action_specs_mirror_schemas():
    assert set(ACTION_SPECS) == set(VESSEL_ACTION_SCHEMAS)
    for name, spec in ACTION_SPECS.items():
        assert spec.schema is VESSEL_ACTION_SCHEMAS[name]
        d = spec.to_dict()
        assert d["name"] == name and d["schema"] is spec.schema


# ---------------------------------------------------------------------------
# haul_gear
# ---------------------------------------------------------------------------


def test_haul_gear_valid_minimal():
    assert validate_action_payload("haul_gear", {"gear_id": "POT-STRING-7"}) == []


def test_haul_gear_valid_full():
    payload = {"gear_id": "POT-STRING-7", "winch_speed_m_s": 1.5, "emergency_stop": False}
    assert validate_action_payload("haul_gear", payload) == []


def test_haul_gear_missing_required():
    errors = validate_action_payload("haul_gear", {})
    assert any("gear_id" in e for e in errors)


def test_haul_gear_winch_speed_out_of_range():
    errors = validate_action_payload(
        "haul_gear", {"gear_id": "POT-1", "winch_speed_m_s": 99.0}
    )
    assert any("maximum" in e for e in errors)


def test_haul_gear_bool_is_not_a_number():
    errors = validate_action_payload(
        "haul_gear", {"gear_id": "POT-1", "winch_speed_m_s": True}
    )
    assert any("expected number" in e for e in errors)


# ---------------------------------------------------------------------------
# anchor_drop
# ---------------------------------------------------------------------------


def test_anchor_drop_empty_payload_ok():
    assert validate_action_payload("anchor_drop", {}) == []


def test_anchor_drop_lat_lon_bounds():
    errors = validate_action_payload("anchor_drop", {"lat": 91.0})
    assert any("maximum" in e for e in errors)
    errors = validate_action_payload("anchor_drop", {"lon": -181.0})
    assert any("minimum" in e for e in errors)


def test_anchor_drop_scope_ratio_bounds():
    errors = validate_action_payload("anchor_drop", {"scope_ratio": 0.5})
    assert any("minimum" in e for e in errors)


# ---------------------------------------------------------------------------
# raise_alert / clear_alerts
# ---------------------------------------------------------------------------


def test_raise_alert_valid():
    payload = {"severity": "critical", "code": "SHALLOW_WATER", "message": "depth < 10m"}
    assert validate_action_payload("raise_alert", payload) == []


def test_raise_alert_bad_severity():
    errors = validate_action_payload("raise_alert", {"severity": "fatal", "code": "X"})
    assert any("not in" in e for e in errors)


def test_raise_alert_missing_code():
    errors = validate_action_payload("raise_alert", {"severity": "info"})
    assert any("code" in e for e in errors)


def test_clear_alerts_codes_array_items_checked():
    assert validate_action_payload("clear_alerts", {"codes": ["A", "B"]}) == []
    errors = validate_action_payload("clear_alerts", {"codes": ["A", 3]})
    assert any("codes[1]" in e for e in errors)


# ---------------------------------------------------------------------------
# morph_to_navigation_mode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["transit", "fishing", "anchored", "maneuvering"])
def test_morph_modes_all_valid(mode):
    payload = {"mode": mode, "confirm": True}
    assert validate_action_payload("morph_to_navigation_mode", payload) == []


def test_morph_mode_rejects_unknown_mode():
    errors = validate_action_payload("morph_to_navigation_mode", {"mode": "warp_drive"})
    assert any("not in" in e for e in errors)


# ---------------------------------------------------------------------------
# Generic validator behavior
# ---------------------------------------------------------------------------


def test_unknown_action_raises():
    with pytest.raises(UnknownActionError):
        validate_action_payload("self_destruct", {})


def test_unexpected_field_rejected():
    errors = validate_action_payload("haul_gear", {"gear_id": "POT-1", "surprise": 1})
    assert any("unexpected field" in e for e in errors)


def test_non_dict_payload_rejected():
    errors = validate_action_payload("haul_gear", ["not", "a", "dict"])
    assert errors and "must be an object" in errors[0]


def test_is_valid_wrapper():
    assert is_valid("anchor_drop", {"scope_ratio": 5.0})
    assert not is_valid("anchor_drop", {"scope_ratio": 500.0})
