"""Vessel action payload schemas for AELMA.

Follows the mini-agent payload-schema pattern: every vessel action that an
agent (or operator UI) can issue is described by a small JSON-Schema-like
spec stored in ``VESSEL_ACTION_SCHEMAS``. The specs are intentionally plain
dicts so they can be serialized to JSON and shipped to other components
(e.g. the viewer) without a validation dependency.

Each entry has the shape::

    {
        "description": str,
        "required": [str, ...],
        "properties": {
            "<field>": {
                "type": "string" | "number" | "integer" | "boolean" | "array",
                "enum": [...],          # optional, restrict allowed values
                "minimum": float,       # optional, numeric lower bound
                "maximum": float,       # optional, numeric upper bound
                "items": {...},         # optional, element spec for arrays
                "description": str,
            },
        },
    }

Validation itself lives in ``schema.validator.validate_action_payload``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

# A payload schema is a plain dict so it stays JSON-serializable.
PayloadSchema = Dict[str, Any]


@dataclass(frozen=True)
class ActionSpec:
    """Metadata wrapper around a raw payload schema.

    The raw schema dict is what the validator consumes; ``name`` and
    ``category`` are convenience metadata for tooling and docs.
    """

    name: str
    category: str
    schema: PayloadSchema
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "tags": list(self.tags),
            "schema": self.schema,
        }


VESSEL_ACTION_SCHEMAS: Dict[str, PayloadSchema] = {
    "haul_gear": {
        "description": "Haul fishing gear (pots, longline, trawl) back aboard.",
        "required": ["gear_id"],
        "properties": {
            "gear_id": {
                "type": "string",
                "description": "Identifier of the gear set to haul, e.g. 'POT-STRING-7'.",
            },
            "winch_speed_m_s": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 5.0,
                "description": "Target winch speed in m/s. Defaults to vessel standard.",
            },
            "emergency_stop": {
                "type": "boolean",
                "description": "If true, abort an in-progress haul immediately.",
            },
        },
    },
    "anchor_drop": {
        "description": "Drop anchor at the vessel's current or a specified position.",
        "required": [],
        "properties": {
            "lat": {
                "type": "number",
                "minimum": -90.0,
                "maximum": 90.0,
                "description": "Anchor position latitude. Defaults to current position.",
            },
            "lon": {
                "type": "number",
                "minimum": -180.0,
                "maximum": 180.0,
                "description": "Anchor position longitude. Defaults to current position.",
            },
            "scope_ratio": {
                "type": "number",
                "minimum": 1.0,
                "maximum": 10.0,
                "description": "Rode scope ratio (rode length / depth). Default 5.0.",
            },
        },
    },
    "raise_alert": {
        "description": "Raise an operator/crew alert on the vessel.",
        "required": ["severity", "code"],
        "properties": {
            "severity": {
                "type": "string",
                "enum": ["info", "warning", "critical"],
                "description": "Alert severity level.",
            },
            "code": {
                "type": "string",
                "description": "Machine-readable alert code, e.g. 'SHALLOW_WATER'.",
            },
            "message": {
                "type": "string",
                "description": "Human-readable alert detail.",
            },
        },
    },
    "clear_alerts": {
        "description": "Clear active alerts, either all or a selected set.",
        "required": [],
        "properties": {
            "all": {
                "type": "boolean",
                "description": "If true, clear every active alert.",
            },
            "codes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Alert codes to clear. Ignored when 'all' is true.",
            },
        },
    },
    "morph_to_navigation_mode": {
        "description": "Transition the vessel to a new navigation/operating mode.",
        "required": ["mode"],
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["transit", "fishing", "anchored", "maneuvering"],
                "description": "Target navigation mode.",
            },
            "confirm": {
                "type": "boolean",
                "description": "Operator confirmation for safety-relevant transitions.",
            },
        },
    },
}

# Structured view of the same schemas for tooling that prefers dataclasses.
ACTION_SPECS: Dict[str, ActionSpec] = {
    "haul_gear": ActionSpec(
        name="haul_gear",
        category="deck_operations",
        schema=VESSEL_ACTION_SCHEMAS["haul_gear"],
        tags=["gear", "winch"],
    ),
    "anchor_drop": ActionSpec(
        name="anchor_drop",
        category="navigation",
        schema=VESSEL_ACTION_SCHEMAS["anchor_drop"],
        tags=["anchor"],
    ),
    "raise_alert": ActionSpec(
        name="raise_alert",
        category="safety",
        schema=VESSEL_ACTION_SCHEMAS["raise_alert"],
        tags=["alert"],
    ),
    "clear_alerts": ActionSpec(
        name="clear_alerts",
        category="safety",
        schema=VESSEL_ACTION_SCHEMAS["clear_alerts"],
        tags=["alert"],
    ),
    "morph_to_navigation_mode": ActionSpec(
        name="morph_to_navigation_mode",
        category="navigation",
        schema=VESSEL_ACTION_SCHEMAS["morph_to_navigation_mode"],
        tags=["mode"],
    ),
}
