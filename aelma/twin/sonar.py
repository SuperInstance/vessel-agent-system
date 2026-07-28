"""Sonar integration for the AELMA twin: fish target tracking via NMEA.

Parses sounder sentences from Humminbird, Lowrance, and Garmin units,
tracks fish targets (depth, size, bottom hardness), classifies bottom
type, estimates a biomass proxy, and fuses depths into the
:class:`~twin.bathymetry.BathymetryGrid`.

Supported sentences::

    $SDDBT  -- depth below transducer (all vendors, field 3 = meters)
    $SDDBS  -- depth below surface   (all vendors, field 3 = meters)
    $SDSSF  -- fish target report: depth_m, size, hardness
               (vendor-specific size/hardness units, normalized here)

Vendor units for $SDSSF:
    humminbird -- size in inches, hardness 0-100
    lowrance   -- size in cm,     hardness 0-1
    garmin     -- size in cm,     hardness 0-255
    generic    -- size in cm,     hardness 0-1

Vendor is auto-detected from proprietary talker prefixes when
``vendor="auto"``: ``$PH`` (Humminbird), ``$PL`` (Lowrance), ``$PG``
(Garmin).

Fish targets are appended to a JSONL file (one JSON object per line)::

    {"kind": "sonar_fish_target", "lat": ..., "lon": ...,
     "depth_m": ..., "size_cm": ..., "hardness": ...,
     "vendor": "lowrance", "ts": "...ISO...", "_seq": 0}

Stdlib only, synchronous I/O (sounder traffic is low-frequency).
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .bathymetry import BathymetryGrid

log = logging.getLogger("aelma.twin.sonar")

#: Record kind identifier for JSONL storage.
KIND_TARGET = "sonar_fish_target"

#: Maximum fish targets retained in memory (JSONL file keeps them all).
MAX_TARGETS = 2000

#: Bottom-type classification thresholds on mean hardness (0-1 scale).
SOFT_MAX = 0.33
MIXED_MAX = 0.66

#: Biomass proxy: mass_kg = size_cm^3 * BIOMASS_FACTOR (50 cm -> ~1.25 kg).
BIOMASS_FACTOR = 1e-5

_VALID_VENDORS = {"auto", "generic", "humminbird", "lowrance", "garmin"}

# $SDSSF normalization: (size -> cm, hardness -> 0-1) per vendor.
_SIZE_TO_CM = {
    "humminbird": lambda s: s * 2.54,
    "lowrance": lambda s: s,
    "garmin": lambda s: s,
    "generic": lambda s: s,
}
_HARDNESS_TO_UNIT = {
    "humminbird": lambda h: h / 100.0,
    "lowrance": lambda h: h,
    "garmin": lambda h: h / 255.0,
    "generic": lambda h: h,
}

# Proprietary talker prefixes -> vendor (used when vendor="auto").
_PREFIX_VENDOR = {"PH": "humminbird", "PL": "lowrance", "PG": "garmin"}


def _utc_now_iso() -> str:
    """Get current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _safe_float(text: str | None) -> float | None:
    """Parse *text* as float, returning None on empty or failure."""
    if not text:
        return None
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def _verify_checksum(sentence: str) -> None:
    """Validate the XOR checksum of an NMEA 0183 sentence.

    Raises:
        ValueError: If the sentence is malformed or checksum mismatches.
    """
    stripped = sentence.strip()
    if not stripped.startswith("$"):
        raise ValueError(f"Sentence must start with '$': {stripped!r}")
    star_idx = stripped.rfind("*")
    if star_idx == -1:
        raise ValueError(f"Sentence missing '*': {stripped!r}")
    body = stripped[1:star_idx]
    provided = stripped[star_idx + 1:].split(",")[0].strip()
    if len(provided) < 2:
        raise ValueError(f"Checksum too short: {stripped!r}")
    computed = 0
    for ch in body:
        computed ^= ord(ch)
    if f"{computed:02X}" != provided.upper():
        raise ValueError(f"Checksum mismatch in {stripped!r}")


def _split_fields(sentence: str) -> list[str]:
    """Return the comma-separated fields of a sentence body."""
    stripped = sentence.strip()
    star_idx = stripped.rfind("*")
    return stripped[1:star_idx].split(",")


def classify_bottom(hardness: float) -> str:
    """Classify a 0-1 bottom hardness value as soft/mixed/hard."""
    if hardness < SOFT_MAX:
        return "soft"
    if hardness < MIXED_MAX:
        return "mixed"
    return "hard"


class SonarClient:
    """Track fish targets and bottom characteristics from sonar NMEA data.

    Parameters
    ----------
    storage_path:
        Destination JSONL file for fish targets. Parent directories are
        created on first append; an existing file is resumed (targets are
        reloaded into memory, ``_seq`` continues). ``None`` disables
        persistence.
    vendor:
        ``"humminbird"``, ``"lowrance"``, ``"garmin"``, ``"generic"``, or
        ``"auto"`` (detect from proprietary talker prefixes).
    bathymetry:
        Optional :class:`~twin.bathymetry.BathymetryGrid`. When attached,
        every depth sounding received while a position is set is fused
        into the grid as a ``"sounder"`` source sample.
    """

    def __init__(
        self,
        storage_path: str | Path | None = None,
        vendor: str = "auto",
        bathymetry: BathymetryGrid | None = None,
    ) -> None:
        if vendor not in _VALID_VENDORS:
            raise ValueError(
                f"SonarClient: vendor must be one of {sorted(_VALID_VENDORS)}, "
                f"got {vendor!r}"
            )
        self.vendor = vendor
        self._bathymetry = bathymetry
        self._path = Path(storage_path) if storage_path is not None else None
        self._targets: deque[dict[str, Any]] = deque(maxlen=MAX_TARGETS)
        self._hardness_samples: deque[float] = deque(maxlen=MAX_TARGETS)
        self._position: tuple[float, float] | None = None
        self._depth_m: float | None = None
        self._seq = 0
        if self._path is not None:
            self._load()

    # ------------------------------------------------------------------
    # State inputs
    # ------------------------------------------------------------------

    def set_position(self, lat: float, lon: float) -> None:
        """Set the current vessel position used to geotag new targets."""
        if not -90.0 <= lat <= 90.0:
            raise ValueError(f"SonarClient.set_position: lat out of range: {lat!r}")
        if not -180.0 <= lon <= 180.0:
            raise ValueError(f"SonarClient.set_position: lon out of range: {lon!r}")
        self._position = (float(lat), float(lon))

    @property
    def depth_m(self) -> float | None:
        """Most recent depth sounding in meters, or None."""
        return self._depth_m

    # ------------------------------------------------------------------
    # NMEA processing
    # ------------------------------------------------------------------

    def process_sentence(self, sentence: str) -> list[dict[str, Any]]:
        """Process one NMEA 0183 sentence from the sounder.

        Returns a list of event dicts: ``{"type": "depth", ...}`` for
        $SDDBT/$SDDBS and ``{"type": "fish_target", ...}`` for $SDSSF.
        Unknown sentence types are ignored (empty list).

        Raises:
            ValueError: If the checksum is invalid or sentence malformed.
        """
        stripped = sentence.strip()
        if not stripped:
            return []
        _verify_checksum(stripped)
        fields = _split_fields(stripped)
        if not fields or not fields[0]:
            return []
        self._detect_vendor(stripped)
        stype = fields[0].upper()
        if stype in ("SDDBT", "SDDBS"):
            return self._handle_depth(fields, stype)
        if stype == "SDSSF":
            return self._handle_fish_target(fields)
        return []

    def _detect_vendor(self, sentence: str) -> None:
        """Auto-detect vendor from proprietary talker prefixes."""
        if self.vendor != "auto":
            return
        vendor = _PREFIX_VENDOR.get(sentence[1:3].upper())
        if vendor is not None:
            self.vendor = vendor

    def _effective_vendor(self) -> str:
        """Vendor used for unit normalization (auto falls back to generic)."""
        return "generic" if self.vendor == "auto" else self.vendor

    def _handle_depth(self, fields: list[str], stype: str) -> list[dict[str, Any]]:
        """$SDDBT / $SDDBS: meters in field 3."""
        depth = _safe_float(fields[3]) if len(fields) > 3 else None
        if depth is None or depth < 0.0:
            return []
        self._depth_m = depth
        if self._bathymetry is not None and self._position is not None:
            lat, lon = self._position
            self._bathymetry.fuse(lat, lon, depth, time.time_ns(), source="sounder")
        return [{"type": "depth", "depth_m": depth, "sentence": stype}]

    def _handle_fish_target(self, fields: list[str]) -> list[dict[str, Any]]:
        """$SDSSF,depth_m,size,hardness -- vendor-normalized fish target."""
        if len(fields) < 4:
            return []
        depth = _safe_float(fields[1])
        size_raw = _safe_float(fields[2])
        hardness_raw = _safe_float(fields[3])
        if depth is None or size_raw is None or hardness_raw is None:
            return []
        vendor = self._effective_vendor()
        size_cm = _SIZE_TO_CM[vendor](size_raw)
        hardness = min(max(_HARDNESS_TO_UNIT[vendor](hardness_raw), 0.0), 1.0)
        if depth < 0.0 or size_cm <= 0.0:
            return []
        lat, lon = self._position if self._position is not None else (None, None)
        target = {
            "kind": KIND_TARGET,
            "lat": lat,
            "lon": lon,
            "depth_m": float(depth),
            "size_cm": float(size_cm),
            "hardness": float(hardness),
            "vendor": vendor,
            "ts": _utc_now_iso(),
            "_seq": self._seq,
        }
        self._seq += 1
        self._targets.append(target)
        self._hardness_samples.append(hardness)
        self._append(target)
        return [{"type": "fish_target", "target": dict(target)}]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_fish_targets(
        self,
        min_size_cm: float | None = None,
        max_depth_m: float | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return tracked fish targets, most recent first.

        Args:
            min_size_cm: Drop targets smaller than this.
            max_depth_m: Drop targets deeper than this.
            limit: Maximum number of targets to return.
        """
        out: list[dict[str, Any]] = []
        for target in reversed(self._targets):
            if min_size_cm is not None and target["size_cm"] < min_size_cm:
                continue
            if max_depth_m is not None and target["depth_m"] > max_depth_m:
                continue
            out.append(dict(target))
            if limit is not None and len(out) >= limit:
                break
        return out

    def get_bottom_type(self) -> dict[str, Any]:
        """Classify bottom composition from recent hardness samples.

        Returns ``{"type": "soft"|"mixed"|"hard"|"unknown", "hardness":
        mean or None, "sample_count": n}``.
        """
        n = len(self._hardness_samples)
        if n == 0:
            return {"type": "unknown", "hardness": None, "sample_count": 0}
        mean = sum(self._hardness_samples) / n
        return {
            "type": classify_bottom(mean),
            "hardness": round(mean, 4),
            "sample_count": n,
        }

    def estimate_biomass(
        self,
        min_size_cm: float | None = None,
        max_depth_m: float | None = None,
    ) -> dict[str, Any]:
        """Estimate a biomass proxy from tracked fish targets.

        Uses ``mass_kg = size_cm^3 * 1e-5`` per target (a 50 cm fish is
        roughly 1.25 kg). This is a relative index, not an absolute stock
        assessment. Returns total kg, target count, and mean size.
        """
        targets = self.get_fish_targets(
            min_size_cm=min_size_cm, max_depth_m=max_depth_m
        )
        if not targets:
            return {"biomass_kg": 0.0, "target_count": 0, "avg_size_cm": None}
        total = sum(t["size_cm"] ** 3 * BIOMASS_FACTOR for t in targets)
        avg = sum(t["size_cm"] for t in targets) / len(targets)
        return {
            "biomass_kg": round(total, 3),
            "target_count": len(targets),
            "avg_size_cm": round(avg, 2),
        }

    # ------------------------------------------------------------------
    # JSONL persistence
    # ------------------------------------------------------------------

    def _append(self, target: dict[str, Any]) -> None:
        """Append one target record to the JSONL file and flush."""
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(target, separators=(",", ":")) + "\n")

    def _load(self) -> None:
        """Reload targets from the JSONL file, tolerating a missing file."""
        if self._path is None or not self._path.exists():
            return
        max_seq = -1
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    log.warning("Skipping malformed line in %s", self._path)
                    continue
                if record.get("kind") != KIND_TARGET:
                    continue
                self._targets.append(record)
                hardness = record.get("hardness")
                if isinstance(hardness, (int, float)):
                    self._hardness_samples.append(float(hardness))
                seq = record.get("_seq", -1)
                if isinstance(seq, int) and seq > max_seq:
                    max_seq = seq
        self._seq = max_seq + 1
