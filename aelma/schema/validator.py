"""Payload validator for AELMA vessel actions.

Validates an action payload against the specs in
``schema.actions.VESSEL_ACTION_SCHEMAS``. Dependency-free: it implements
just the subset of JSON-Schema semantics the action specs use
(type / enum / minimum / maximum / required / items).

Usage::

    errors = validate_action_payload("haul_gear", {"gear_id": "POT-7"})
    if errors:
        ...  # list of human-readable error strings
"""
from __future__ import annotations

from typing import Any, Dict, List

try:  # works both as a package import and from the repo root
    from schema.actions import VESSEL_ACTION_SCHEMAS
except ModuleNotFoundError:  # pragma: no cover - direct script use
    from actions import VESSEL_ACTION_SCHEMAS  # type: ignore


class UnknownActionError(ValueError):
    """Raised when validating a payload for an action with no schema."""


_TYPE_CHECKS: Dict[str, Any] = {
    "string": lambda v: isinstance(v, str),
    # bool is a subclass of int; exclude it from numeric checks.
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def validate_action_payload(action: str, payload: Dict[str, Any]) -> List[str]:
    """Validate ``payload`` against the schema for ``action``.

    Returns a list of error strings; an empty list means the payload is
    valid. Raises :class:`UnknownActionError` for an unregistered action.
    """
    if action not in VESSEL_ACTION_SCHEMAS:
        raise UnknownActionError(
            f"unknown action {action!r}; known: {sorted(VESSEL_ACTION_SCHEMAS)}"
        )

    spec = VESSEL_ACTION_SCHEMAS[action]
    properties: Dict[str, Dict[str, Any]] = spec.get("properties", {})
    errors: List[str] = []

    if not isinstance(payload, dict):
        return [f"payload must be an object, got {type(payload).__name__}"]

    for field_name in spec.get("required", []):
        if field_name not in payload:
            errors.append(f"missing required field {field_name!r}")

    for key, value in payload.items():
        if key not in properties:
            errors.append(f"unexpected field {key!r}")
            continue
        errors.extend(_validate_field(key, value, properties[key]))

    return errors


def is_valid(action: str, payload: Dict[str, Any]) -> bool:
    """Convenience wrapper: True when the payload validates cleanly."""
    return not validate_action_payload(action, payload)


def _validate_field(name: str, value: Any, spec: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    expected = spec.get("type")
    if expected is not None:
        check = _TYPE_CHECKS.get(expected)
        if check is None:
            errors.append(f"field {name!r}: unknown schema type {expected!r}")
        elif not check(value):
            errors.append(
                f"field {name!r}: expected {expected}, got {type(value).__name__}"
            )
            return errors  # further checks are meaningless on a wrong type

    if "enum" in spec and value not in spec["enum"]:
        errors.append(f"field {name!r}: {value!r} not in {spec['enum']}")

    if "minimum" in spec and isinstance(value, (int, float)) and value < spec["minimum"]:
        errors.append(f"field {name!r}: {value!r} below minimum {spec['minimum']}")

    if "maximum" in spec and isinstance(value, (int, float)) and value > spec["maximum"]:
        errors.append(f"field {name!r}: {value!r} above maximum {spec['maximum']}")

    if expected == "array" and "items" in spec and isinstance(value, list):
        for i, item in enumerate(value):
            errors.extend(_validate_field(f"{name}[{i}]", item, spec["items"]))

    return errors
