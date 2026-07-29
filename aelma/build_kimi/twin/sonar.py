"""Sonar fish target tracking system for the AELMA twin.

Parses NMEA 0183 sounder sentences ($SDDBT, $SDDBS, $SDSSF) and tracks
fish targets with depth, size, and bottom hardness information. Supports
vendor normalization across Humminbird, Lowrance, and Garmin devices.

Integrates with BathymetryGrid for depth sounding fusion and persists
target data to JSONL for analytics and visualization.

Example:
    >>> sonar = SonarTargetTracker()
    >>> sonar.set_position(47.6, -122.4)
    >>> targets = sonar.process_sentence("$SDDBT,12.3,f,3.75,M,,F*12")
    >>> sonar.get_fish_targets(min_size_cm=30, max_depth_m=50)
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# Constants for fish target validation
MIN_DEPTH_M = 0.5
MAX_DEPTH_M = 300.0
MIN_SIZE_CM = 5.0
MAX_SIZE_CM = 200.0
BIOMASS_FACTOR = 0.001  # kg per cm^3 (approximate fish density)
MAX_TARGETS_MEMORY = 10000  # Maximum targets to keep in memory


class BottomType(Enum):
    """Bottom composition classification."""
    SOFT = "soft"
    MIXED = "mixed"
    HARD = "hard"
    UNKNOWN = "unknown"


class Vendor(Enum):
    """Sonar device vendors."""
    GENERIC = "generic"
    HUMMINBIRD = "humminbird"
    LOWRANCE = "lowrance"
    GARMIN = "garmin"
    RAYMARINE = "raymarine"


@dataclass
class VendorSettings:
    """Vendor-specific sonar configuration."""
    vendor: Vendor = Vendor.GENERIC
    max_depth_m: float = MAX_DEPTH_M
    frequency_khz: int = 200
    beam_width_deg: float = 20.0
    bottom_threshold: float = 0.7  # Signal strength threshold for bottom detection

    def __post_init__(self) -> None:
        """Validate vendor settings."""
        if not isinstance(self.vendor, Vendor):
            self.vendor = Vendor.GENERIC
        if self.max_depth_m <= 0 or self.max_depth_m > MAX_DEPTH_M * 2:
            self.max_depth_m = MAX_DEPTH_M
        if self.frequency_khz not in (50, 83, 200, 455, 800):
            self.frequency_khz = 200
        if not 0 < self.beam_width_deg <= 60:
            self.beam_width_deg = 20.0
        if not 0.0 <= self.bottom_threshold <= 1.0:
            self.bottom_threshold = 0.7


@dataclass
class FishTarget:
    """A single fish target detection."""
    depth_m: float
    size_cm: float
    hardness: float  # 0.0 (soft) to 1.0 (hard)
    vendor: Vendor
    lat: float | None = None
    lon: float | None = None
    timestamp_ns: int = field(default_factory=lambda: time.time_ns())
    target_id: str = ""
    bottom_type: BottomType = BottomType.UNKNOWN
    signal_strength: float = 0.0
    frequency_khz: int = 200

    def __post_init__(self) -> None:
        """Validate fish target data."""
        # Validate depth
        if not isinstance(self.depth_m, (int, float)) or self.depth_m < MIN_DEPTH_M:
            self.depth_m = MIN_DEPTH_M
        if self.depth_m > MAX_DEPTH_M:
            self.depth_m = MAX_DEPTH_M

        # Validate size
        if not isinstance(self.size_cm, (int, float)) or self.size_cm < MIN_SIZE_CM:
            self.size_cm = MIN_SIZE_CM
        if self.size_cm > MAX_SIZE_CM:
            self.size_cm = MAX_SIZE_CM

        # Validate hardness
        if not isinstance(self.hardness, (int, float)):
            self.hardness = 0.5
        self.hardness = max(0.0, min(1.0, float(self.hardness)))

        # Validate vendor
        if not isinstance(self.vendor, Vendor):
            self.vendor = Vendor.GENERIC

        # Validate position
        if self.lat is not None:
            if not isinstance(self.lat, (int, float)) or not -90 <= self.lat <= 90:
                self.lat = None
        if self.lon is not None:
            if not isinstance(self.lon, (int, float)) or not -180 <= self.lon <= 180:
                self.lon = None

        # Validate timestamp
        if not isinstance(self.timestamp_ns, int) or self.timestamp_ns <= 0:
            self.timestamp_ns = time.time_ns()

        # Validate bottom type
        if not isinstance(self.bottom_type, BottomType):
            if isinstance(self.bottom_type, str):
                try:
                    self.bottom_type = BottomType(self.bottom_type.lower())
                except ValueError:
                    self.bottom_type = self._classify_bottom()
            else:
                self.bottom_type = self._classify_bottom()

        # Validate signal strength
        if not isinstance(self.signal_strength, (int, float)):
            self.signal_strength = 0.0
        self.signal_strength = max(0.0, min(1.0, float(self.signal_strength)))

        # Generate target ID if not provided
        if not self.target_id:
            self.target_id = f"target_{int(self.timestamp_ns)}_{int(self.depth_m * 10)}"

        # Validate frequency
        if not isinstance(self.frequency_khz, int) or self.frequency_khz not in (50, 83, 200, 455, 800):
            self.frequency_khz = 200

    def _classify_bottom(self) -> BottomType:
        """Classify bottom type from hardness value."""
        if self.hardness < 0.3:
            return BottomType.SOFT
        elif self.hardness < 0.7:
            return BottomType.MIXED
        else:
            return BottomType.HARD

    def estimate_biomass_kg(self) -> float:
        """Estimate fish biomass in kg using volume formula."""
        # Approximate fish as ellipsoid: volume = (4/3) * pi * (size/2)^3
        # Convert cm to m: volume_m^3 = volume_cm^3 / 1_000_000
        volume_cm3 = (4/3) * math.pi * math.pow(self.size_cm / 2, 3)
        return volume_cm3 * BIOMASS_FACTOR

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "target_id": self.target_id,
            "depth_m": round(self.depth_m, 2),
            "size_cm": round(self.size_cm, 1),
            "hardness": round(self.hardness, 3),
            "bottom_type": self.bottom_type.value,
            "vendor": self.vendor.value,
            "lat": round(self.lat, 6) if self.lat is not None else None,
            "lon": round(self.lon, 6) if self.lon is not None else None,
            "timestamp_ns": self.timestamp_ns,
            "biomass_kg": round(self.estimate_biomass_kg(), 4),
            "signal_strength": round(self.signal_strength, 3),
            "frequency_khz": self.frequency_khz,
        }


class SonarTargetTracker:
    """Tracker for fish targets from NMEA 0183 sounder sentences.

    Maintains an in-memory buffer of recent detections and persists
    all targets to a JSONL file for analytics. Supports position
    geotagging and optional bathymetry grid fusion.

    Example:
        >>> tracker = SonarTargetTracker(persistence_path="sonar_targets.jsonl")
        >>> tracker.set_position(47.6, -122.4)
        >>> targets = tracker.process_sentence("$SDDBT,12.3,f,3.75,M,,F*12")
        >>> snapshot = tracker.to_dict()
    """

    def __init__(
        self,
        persistence_path: str | Path = "sonar_targets.jsonl",
        vendor_settings: VendorSettings | None = None,
        max_targets: int = MAX_TARGETS_MEMORY,
    ) -> None:
        """Initialize the sonar target tracker.

        Args:
            persistence_path: Path to JSONL file for target persistence.
            vendor_settings: Vendor-specific configuration (uses defaults if None).
            max_targets: Maximum number of targets to keep in memory.
        """
        self.persistence_path = Path(persistence_path)
        self.vendor_settings = vendor_settings or VendorSettings()
        self.max_targets = max_targets

        # Position for geotagging
        self._lat: float | None = None
        self._lon: float | None = None

        # In-memory target buffer (circular buffer via dict)
        self._targets: dict[str, FishTarget] = {}

        # Bottom hardness tracking for classification
        self._bottom_readings: list[float] = []
        self._max_bottom_samples = 100

        # Statistics
        self._total_targets_processed = 0
        self._total_sentences_processed = 0
        self._parse_errors = 0

    def set_position(self, lat: float, lon: float) -> None:
        """Set vessel position for geotagging future targets.

        Args:
            lat: Latitude in decimal degrees (-90 to 90).
            lon: Longitude in decimal degrees (-180 to 180).

        Raises:
            ValueError: If lat/lon are out of valid range.
        """
        if not isinstance(lat, (int, float)) or not -90 <= lat <= 90:
            raise ValueError(f"Invalid latitude: {lat}")
        if not isinstance(lon, (int, float)) or not -180 <= lon <= 180:
            raise ValueError(f"Invalid longitude: {lon}")

        self._lat = float(lat)
        self._lon = float(lon)

    def get_position(self) -> tuple[float | None, float | None]:
        """Get current vessel position.

        Returns:
            Tuple of (lat, lon) or (None, None) if not set.
        """
        return self._lat, self._lon

    def process_sentence(self, sentence: str) -> list[dict[str, Any]]:
        """Parse an NMEA 0183 sounder sentence and extract targets.

        Supported sentence types:
        - $SDDBT: Depth below transducer
        - $SDDBS: Depth below surface
        - $SDSSF: Single fish target (vendor-specific)

        Args:
            sentence: NMEA 0183 sentence string (must include checksum).

        Returns:
            List of detected target dictionaries (may be empty).

        Raises:
            ValueError: If sentence format is invalid or checksum fails.
        """
        if not sentence or not isinstance(sentence, str):
            self._parse_errors += 1
            return []

        sentence = sentence.strip()
        if not sentence.startswith("$"):
            self._parse_errors += 1
            return []

        # Validate checksum
        if "*" in sentence:
            try:
                data, checksum_str = sentence.rsplit("*", 1)
                if not self._validate_checksum(data[1:], checksum_str):
                    self._parse_errors += 1
                    raise ValueError(f"Checksum validation failed: {sentence}")
            except (ValueError, IndexError):
                self._parse_errors += 1
                raise ValueError(f"Invalid checksum format: {sentence}")

        self._total_sentences_processed += 1

        # Parse sentence type
        if sentence.startswith("$SDDBT"):
            return self._parse_depth_below_transducer(sentence)
        elif sentence.startswith("$SDDBS"):
            return self._parse_depth_below_surface(sentence)
        elif sentence.startswith("$SDSSF"):
            return self._parse_single_fish(sentence)
        else:
            # Unsupported sentence type
            return []

    def _validate_checksum(self, data: str, checksum: str) -> bool:
        """Validate NMEA XOR checksum.

        Args:
            data: Sentence data after $ and before *.
            checksum: Two-character hex checksum string.

        Returns:
            True if checksum matches, False otherwise.
        """
        try:
            calculated = 0
            for char in data:
                calculated ^= ord(char)
            expected = int(checksum, 16)
            return calculated == expected
        except (ValueError, TypeError):
            return False

    def _parse_depth_below_transducer(self, sentence: str) -> list[dict[str, Any]]:
        """Parse $SDDBT sentence (Depth Below Transducer).

        Format: $SDDBT,depth,f,depth,M,depth,F*checksum
        Example: $SDDBT,12.3,f,3.75,M,,F*12

        Returns:
            List with one generic target if depth is valid.
        """
        try:
            # Remove $SDDBT and checksum
            clean = sentence.split("*", 1)[0]
            fields = clean.split(",")

            if len(fields) < 4:
                return []

            # Extract depth in meters
            depth_m = 0.0
            for i, field in enumerate(fields):
                if i > 0 and field and field.upper() == "M":
                    # Previous field is depth in meters
                    try:
                        depth_m = float(fields[i - 1])
                        break
                    except (ValueError, IndexError):
                        continue

            if not depth_m or depth_m < MIN_DEPTH_M or depth_m > self.vendor_settings.max_depth_m:
                return []

            # Create a generic bottom target
            target = FishTarget(
                depth_m=depth_m,
                size_cm=100.0,  # Generic size for bottom detection
                hardness=0.5,  # Unknown hardness
                vendor=self.vendor_settings.vendor,
                lat=self._lat,
                lon=self._lon,
                bottom_type=self._classify_bottom_from_depth(depth_m),
                signal_strength=0.8,
                frequency_khz=self.vendor_settings.frequency_khz,
            )

            return self._add_target(target)

        except (ValueError, IndexError, AttributeError):
            self._parse_errors += 1
            return []

    def _parse_depth_below_surface(self, sentence: str) -> list[dict[str, Any]]:
        """Parse $SDDBS sentence (Depth Below Surface).

        Format: $SDDBS,depth,f,depth,M,depth,F*checksum
        Similar to $SDDBT but depth is measured from water surface.

        Returns:
            List with one generic target if depth is valid.
        """
        # Same parsing logic as DBT for depth extraction
        return self._parse_depth_below_transducer(sentence)

    def _parse_single_fish(self, sentence: str) -> list[dict[str, Any]]:
        """Parse $SDSSF sentence (Single Fish Target - vendor-specific).

        Format varies by vendor:
        Humminbird: $SDSSF,depth_m,size_cm,hardness,signal*checksum
        Lowrance: $SDSSF,depth_m,size_cm,signal*checksum
        Garmin: $SDSSF,depth_m,target_id,strength*checksum

        Returns:
            List with one or more fish targets.
        """
        try:
            # Remove $SDSSF and checksum
            clean = sentence.split("*", 1)[0]
            fields = clean.split(",")

            if len(fields) < 3:
                return []

            # Extract depth (field 1)
            try:
                depth_m = float(fields[1])
            except (ValueError, IndexError):
                return []

            if depth_m < MIN_DEPTH_M or depth_m > self.vendor_settings.max_depth_m:
                return []

            # Extract size (field 2, might be in different units)
            try:
                size_raw = float(fields[2])
                # Vendor normalization: convert to cm
                size_cm = self._normalize_size(size_raw, self.vendor_settings.vendor)
            except (ValueError, IndexError):
                size_cm = 30.0  # Default size

            # Extract hardness (field 3, if available)
            hardness = 0.5
            if len(fields) >= 4 and fields[3]:
                try:
                    hardness = float(fields[3])
                except ValueError:
                    hardness = 0.5

            # Extract signal strength (field 4 or 3, if available)
            signal_strength = 0.7
            if len(fields) >= 5 and fields[4]:
                try:
                    signal_strength = float(fields[4])
                except ValueError:
                    signal_strength = 0.7
            elif len(fields) >= 4 and fields[3]:
                try:
                    signal_strength = float(fields[3])
                except ValueError:
                    signal_strength = 0.7

            # Create fish target
            target = FishTarget(
                depth_m=depth_m,
                size_cm=size_cm,
                hardness=hardness,
                vendor=self.vendor_settings.vendor,
                lat=self._lat,
                lon=self._lon,
                signal_strength=signal_strength,
                frequency_khz=self.vendor_settings.frequency_khz,
            )

            return self._add_target(target)

        except (ValueError, IndexError, AttributeError):
            self._parse_errors += 1
            return []

    def _normalize_size(self, size_raw: float, vendor: Vendor) -> float:
        """Normalize fish size to centimeters based on vendor.

        Args:
            size_raw: Raw size value from sonar.
            vendor: Device vendor enum.

        Returns:
            Size in centimeters.
        """
        if vendor == Vendor.HUMMINBIRD:
            # Humminbird uses cm directly
            return max(MIN_SIZE_CM, min(MAX_SIZE_CM, size_raw))
        elif vendor == Vendor.LOWRANCE:
            # Lowrance uses inches, convert to cm
            return max(MIN_SIZE_CM, min(MAX_SIZE_CM, size_raw * 2.54))
        elif vendor == Vendor.GARMIN:
            # Garmin uses mm, convert to cm
            return max(MIN_SIZE_CM, min(MAX_SIZE_CM, size_raw / 10.0))
        else:
            # Generic: assume cm
            return max(MIN_SIZE_CM, min(MAX_SIZE_CM, size_raw))

    def _classify_bottom_from_depth(self, depth_m: float) -> BottomType:
        """Classify bottom type from depth and hardness readings.

        Args:
            depth_m: Depth in meters.

        Returns:
            BottomType enum value.
        """
        # Use recent hardness readings if available
        if self._bottom_readings:
            avg_hardness = sum(self._bottom_readings) / len(self._bottom_readings)
            if avg_hardness < 0.3:
                return BottomType.SOFT
            elif avg_hardness < 0.7:
                return BottomType.MIXED
            else:
                return BottomType.HARD

        # Fallback to depth-based heuristic
        # Deeper water tends to have softer bottoms (sediment)
        if depth_m > 50:
            return BottomType.SOFT
        elif depth_m > 20:
            return BottomType.MIXED
        else:
            return BottomType.HARD

    def _add_target(self, target: FishTarget) -> list[dict[str, Any]]:
        """Add target to buffer and persist to JSONL.

        Args:
            target: FishTarget instance to add.

        Returns:
            List containing the target dictionary.
        """
        self._total_targets_processed += 1

        # Add to in-memory buffer
        self._targets[target.target_id] = target

        # Enforce max targets limit (remove oldest)
        if len(self._targets) > self.max_targets:
            # Remove oldest by timestamp
            oldest_id = min(self._targets.keys(),
                          key=lambda k: self._targets[k].timestamp_ns)
            del self._targets[oldest_id]

        # Track hardness for bottom classification
        self._bottom_readings.append(target.hardness)
        if len(self._bottom_readings) > self._max_bottom_samples:
            self._bottom_readings.pop(0)

        # Persist to JSONL
        self._persist_target(target)

        return [target.to_dict()]

    def _persist_target(self, target: FishTarget) -> None:
        """Append target to JSONL persistence file.

        Args:
            target: FishTarget to persist.
        """
        try:
            # Create parent directory if needed
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)

            # Append to JSONL file
            with open(self.persistence_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(target.to_dict()) + "\n")

        except (OSError, IOError) as exc:
            # Log error but don't fail - persistence is optional
            pass

    def get_fish_targets(
        self,
        min_size_cm: float = MIN_SIZE_CM,
        max_depth_m: float = MAX_DEPTH_M,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get filtered fish targets.

        Args:
            min_size_cm: Minimum fish size in centimeters.
            max_depth_m: Maximum depth in meters.
            limit: Maximum number of targets to return.

        Returns:
            List of target dictionaries, sorted by timestamp (newest first).
        """
        targets = [
            t.to_dict() for t in self._targets.values()
            if t.size_cm >= min_size_cm and t.depth_m <= max_depth_m
        ]

        # Sort by timestamp (newest first)
        targets.sort(key=lambda x: x["timestamp_ns"], reverse=True)

        return targets[:limit]

    def get_bottom_type(self) -> dict[str, Any]:
        """Get current bottom type classification.

        Returns:
            Dict with bottom_type, hardness_avg, and sample_count.
        """
        if not self._bottom_readings:
            return {
                "bottom_type": BottomType.UNKNOWN.value,
                "hardness_avg": 0.0,
                "sample_count": 0,
            }

        avg_hardness = sum(self._bottom_readings) / len(self._bottom_readings)
        bottom_type = self._classify_bottom_from_depth(0)  # Use hardness only

        return {
            "bottom_type": bottom_type.value,
            "hardness_avg": round(avg_hardness, 3),
            "sample_count": len(self._bottom_readings),
        }

    def estimate_biomass(
        self,
        min_size_cm: float = MIN_SIZE_CM,
        max_depth_m: float = MAX_DEPTH_M,
    ) -> dict[str, Any]:
        """Estimate total fish biomass for filtered targets.

        Args:
            min_size_cm: Minimum fish size in centimeters.
            max_depth_m: Maximum depth in meters.

        Returns:
            Dict with total_biomass_kg, target_count, and avg_size_cm.
        """
        filtered_targets = [
            t for t in self._targets.values()
            if t.size_cm >= min_size_cm and t.depth_m <= max_depth_m
        ]

        if not filtered_targets:
            return {
                "total_biomass_kg": 0.0,
                "target_count": 0,
                "avg_size_cm": 0.0,
            }

        total_biomass = sum(t.estimate_biomass_kg() for t in filtered_targets)
        avg_size = sum(t.size_cm for t in filtered_targets) / len(filtered_targets)

        return {
            "total_biomass_kg": round(total_biomass, 3),
            "target_count": len(filtered_targets),
            "avg_size_cm": round(avg_size, 2),
        }

    def to_dict(self) -> dict[str, Any]:
        """Get complete tracker snapshot.

        Returns:
            Dict with targets, statistics, bottom type, and position.
        """
        return {
            "position": {
                "lat": round(self._lat, 6) if self._lat is not None else None,
                "lon": round(self._lon, 6) if self._lon is not None else None,
            },
            "targets": [t.to_dict() for t in list(self._targets.values())[:100]],  # Limit to 100
            "target_count": len(self._targets),
            "bottom_type": self.get_bottom_type(),
            "statistics": {
                "total_targets_processed": self._total_targets_processed,
                "total_sentences_processed": self._total_sentences_processed,
                "parse_errors": self._parse_errors,
                "vendor": self.vendor_settings.vendor.value,
                "max_targets": self.max_targets,
            },
        }

    def get_watcher_frame(self) -> dict[str, Any]:
        """Get frame data for watcher rule evaluation.

        Returns:
            Dict with sonar-relevant telemetry fields.
        """
        frame = {
            "timestamp_ns": time.time_ns(),
            "sonar_targets_count": len(self._targets),
            "sonar_sentences_processed": self._total_sentences_processed,
            "sonar_parse_errors": self._parse_errors,
        }

        # Add bottom type info
        bottom_info = self.get_bottom_type()
        frame["sonar_bottom_type"] = bottom_info["bottom_type"]
        frame["sonar_bottom_hardness"] = bottom_info["hardness_avg"]

        # Add biomass estimate for recent targets
        biomass = self.estimate_biomass(min_size_cm=30, max_depth_m=50)
        frame["sonar_biomass_kg"] = biomass["total_biomass_kg"]
        frame["sonar_target_count"] = biomass["target_count"]

        # Add largest recent target
        recent_targets = self.get_fish_targets(limit=10)
        if recent_targets:
            frame["sonar_largest_target_cm"] = max(t["size_cm"] for t in recent_targets)
            frame["sonar_deepest_target_m"] = max(t["depth_m"] for t in recent_targets)
        else:
            frame["sonar_largest_target_cm"] = 0.0
            frame["sonar_deepest_target_m"] = 0.0

        return frame

    def get_alerts(self) -> list[dict[str, Any]]:
        """Get sonar-related alerts.

        Returns:
            List of alert dictionaries for significant events.
        """
        alerts = []

        # Alert for many targets (fish school detected)
        if len(self._targets) > 50:
            biomass = self.estimate_biomass()
            alerts.append({
                "severity": "info",
                "code": "FISH_SCHOOL_DETECTED",
                "message": f"Large fish school detected: {len(self._targets)} targets, "
                          f"{biomass['total_biomass_kg']:.1f}kg biomass",
                "timestamp_ns": time.time_ns(),
            })

        # Alert for very large fish
        large_targets = [t for t in self._targets.values() if t.size_cm > 100]
        if large_targets:
            max_size = max(t.size_cm for t in large_targets)
            alerts.append({
                "severity": "info",
                "code": "LARGE_FISH_DETECTED",
                "message": f"Large fish detected: {max_size:.1f}cm",
                "timestamp_ns": time.time_ns(),
            })

        # Alert for hard bottom (potential hazard)
        bottom = self.get_bottom_type()
        if bottom["bottom_type"] == BottomType.HARD.value and bottom["sample_count"] >= 10:
            alerts.append({
                "severity": "warning",
                "code": "HARD_BOTTOM_DETECTED",
                "message": f"Hard bottom detected (hardness={bottom['hardness_avg']:.2f})",
                "timestamp_ns": time.time_ns(),
            })

        return alerts

    def clear_targets(self) -> None:
        """Clear all in-memory targets (does not affect persisted data)."""
        self._targets.clear()
        self._bottom_readings.clear()

    def load_from_jsonl(self) -> int:
        """Load previously persisted targets from JSONL file.

        Returns:
            Number of targets loaded.
        """
        if not self.persistence_path.exists():
            return 0

        try:
            count = 0
            with open(self.persistence_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        target = FishTarget(
                            depth_m=data["depth_m"],
                            size_cm=data["size_cm"],
                            hardness=data["hardness"],
                            vendor=Vendor(data.get("vendor", "generic")),
                            lat=data.get("lat"),
                            lon=data.get("lon"),
                            timestamp_ns=data["timestamp_ns"],
                            target_id=data.get("target_id", ""),
                            bottom_type=BottomType(data.get("bottom_type", "unknown")),
                            signal_strength=data.get("signal_strength", 0.0),
                            frequency_khz=data.get("frequency_khz", 200),
                        )
                        self._targets[target.target_id] = target
                        count += 1
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue

            return count

        except (OSError, IOError):
            return 0

    def set_vendor(self, vendor: str | Vendor) -> None:
        """Set sonar vendor for normalization.

        Args:
            vendor: Vendor name string or Vendor enum.
        """
        if isinstance(vendor, str):
            try:
                vendor = Vendor(vendor.lower())
            except ValueError:
                vendor = Vendor.GENERIC

        self.vendor_settings.vendor = vendor

    def get_vendor(self) -> Vendor:
        """Get current sonar vendor.

        Returns:
            Vendor enum value.
        """
        return self.vendor_settings.vendor
