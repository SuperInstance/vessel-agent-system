"""Comprehensive tests for MOBDetector.

Tests all MOB detection, position tracking, search pattern generation,
drift estimation, and integration functionality.

This is a LIFE-CRITICAL safety system - tests are comprehensive and
cover all edge cases and failure modes.
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

import pytest

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from twin.mob_detector import (
    DetectionMethod,
    DriftEstimate,
    EventStatus,
    MOBEvent,
    MOBDetector,
    SearchPatternType,
    SearchSector,
    SearchSectorStatus,
)

# Test constants
SITKA_LAT = 57.0531
SITKA_LON = -135.3300
T0 = 1_753_478_400_000_000_000  # Fixed epoch ns for deterministic tests


# --------------------------------------------------------------------- #
# Data model tests
# --------------------------------------------------------------------- #
class TestMOBEvent:
    """MOB event data model."""

    def test_create_event(self):
        """Create basic MOB event."""
        event = MOBEvent(
            event_id="test123",
            timestamp_ns=T0,
            mob_lat=SITKA_LAT,
            mob_lon=SITKA_LON,
            vessel_lat=SITKA_LAT,
            vessel_lon=SITKA_LON,
        )
        assert event.event_id == "test123"
        assert event.mob_lat == SITKA_LAT
        assert event.mob_lon == SITKA_LON
        assert event.status == EventStatus.ACTIVE
        assert event.crew_member_id is None

    def test_event_with_crew(self):
        """Create event with crew member."""
        event = MOBEvent(
            event_id="crew123",
            timestamp_ns=T0,
            mob_lat=SITKA_LAT,
            mob_lon=SITKA_LON,
            vessel_lat=SITKA_LAT,
            vessel_lon=SITKA_LON,
            crew_member_id="alice",
            detection_method=DetectionMethod.MANUAL,
        )
        assert event.crew_member_id == "alice"
        assert event.detection_method == DetectionMethod.MANUAL

    def test_event_serialization(self):
        """Test event to_dict/from_dict roundtrip."""
        event = MOBEvent(
            event_id="ser123",
            timestamp_ns=T0,
            mob_lat=SITKA_LAT,
            mob_lon=SITKA_LON,
            vessel_lat=SITKA_LAT,
            vessel_lon=SITKA_LON,
            crew_member_id="bob",
            detection_method=DetectionMethod.FALL,
            initial_heading_deg=45.0,
            initial_speed_kn=5.5,
        )
        data = event.to_dict()
        restored = MOBEvent.from_dict(data)
        assert restored.event_id == event.event_id
        assert restored.mob_lat == event.mob_lat
        assert restored.mob_lon == event.mob_lon
        assert restored.crew_member_id == event.crew_member_id
        assert restored.detection_method == event.detection_method
        assert restored.initial_heading_deg == event.initial_heading_deg
        assert restored.initial_speed_kn == event.initial_speed_kn


class TestDriftEstimate:
    """Drift estimation data model."""

    def test_create_drift_estimate(self):
        """Create basic drift estimate."""
        estimate = DriftEstimate(
            timestamp_ns=T0,
            projected_lat=SITKA_LAT,
            projected_lon=SITKA_LON,
            confidence_radius_m=100.0,
            current_set_deg=180.0,
            current_drift_kn=1.5,
            wind_from_deg=270.0,
            wind_speed_kn=10.0,
        )
        assert estimate.projected_lat == SITKA_LAT
        assert estimate.confidence_radius_m == 100.0
        assert estimate.current_set_deg == 180.0

    def test_dr_estimate_serialization(self):
        """Test drift estimate serialization."""
        estimate = DriftEstimate(
            timestamp_ns=T0,
            projected_lat=SITKA_LAT,
            projected_lon=SITKA_LON,
            confidence_radius_m=150.0,
            current_set_deg=90.0,
            current_drift_kn=2.0,
            wind_from_deg=45.0,
            wind_speed_kn=15.0,
            leeway_speed_kn=3.0,
            leeway_direction_deg=225.0,
        )
        data = estimate.to_dict()
        restored = DriftEstimate.from_dict(data)
        assert restored.projected_lat == estimate.projected_lat
        assert restored.leeway_speed_kn == estimate.leeway_speed_kn
        assert restored.leeway_direction_deg == estimate.leeway_direction_deg


class TestSearchSector:
    """Search sector data model."""

    def test_create_sector(self):
        """Create basic search sector."""
        sector = SearchSector(
            sector_id="sector1",
            vessel_id="vessel_a",
            center_lat=SITKA_LAT,
            center_lon=SITKA_LON,
            pattern_type=SearchPatternType.EXPANDING_SQUARE,
            track_spacing_m=100.0,
        )
        assert sector.sector_id == "sector1"
        assert sector.vessel_id == "vessel_a"
        assert sector.status == SearchSectorStatus.ASSIGNED

    def test_sector_serialization(self):
        """Test sector serialization."""
        sector = SearchSector(
            sector_id="sector2",
            vessel_id="vessel_b",
            center_lat=SITKA_LAT,
            center_lon=SITKA_LON,
            pattern_type=SearchPatternType.SECTOR,
            track_spacing_m=150.0,
            status=SearchSectorStatus.IN_PROGRESS,
            completed_legs=5,
            coverage_area_sqm=50000.0,
        )
        data = sector.to_dict()
        restored = SearchSector.from_dict(data)
        assert restored.sector_id == sector.sector_id
        assert restored.completed_legs == sector.completed_legs
        assert restored.coverage_area_sqm == sector.coverage_area_sqm


# --------------------------------------------------------------------- #
# MOBDetector initialization and event management
# --------------------------------------------------------------------- #
class TestMOBDetectorInit:
    """MOBDetector initialization and basic operations."""

    def test_init_default_path(self):
        """Initialize with default storage path."""
        # Use a temp file to avoid loading events from other tests
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "mob_events.jsonl"
            detector = MOBDetector(storage_path=path)
            assert detector.storage_path == path
            assert detector.get_active_event() is None

    def test_init_custom_path(self):
        """Initialize with custom storage path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "custom_mob.jsonl"
            detector = MOBDetector(storage_path=path)
            assert detector.storage_path == path

    def test_persistence_load(self):
        """Test loading persisted events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "persist_test.jsonl"

            # Create detector, add event
            detector1 = MOBDetector(storage_path=path)
            detector1.update_vessel_position(SITKA_LAT, SITKA_LON, 90.0, 5.0)
            event1 = detector1.trigger_mob_alert(
                SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL, "alice"
            )

            # Create new detector, should load event
            detector2 = MOBDetector(storage_path=path)
            loaded = detector2.get_event(event1.event_id)
            assert loaded is not None
            assert loaded.event_id == event1.event_id
            assert loaded.mob_lat == event1.mob_lat


class TestMOBEventTriggering:
    """MOB event triggering and management."""

    def test_trigger_manual_alert(self):
        """Trigger manual MOB alert."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 90.0, 5.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL, "bob"
        )

        assert event.event_id is not None
        assert event.mob_lat == SITKA_LAT
        assert event.mob_lon == SITKA_LON
        assert event.crew_member_id == "bob"
        assert event.detection_method == DetectionMethod.MANUAL
        assert event.status == EventStatus.ACTIVE
        assert event.initial_heading_deg == 90.0
        assert event.initial_speed_kn == 5.0

    def test_trigger_multiple_detection_methods(self):
        """Test all detection methods."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        methods = [
            DetectionMethod.BEACON_LOSS,
            DetectionMethod.FALL,
            DetectionMethod.LIFELINE,
            DetectionMethod.CAMERA,
            DetectionMethod.AIS,
        ]

        for method in methods:
            event = detector.trigger_mob_alert(
                SITKA_LAT, SITKA_LON, method, f"crew_{method}"
            )
            assert event.detection_method == method

    def test_trigger_invalid_position(self):
        """Reject invalid position coordinates."""
        detector = MOBDetector()

        # Invalid latitude
        with pytest.raises(ValueError, match="Invalid latitude"):
            detector.trigger_mob_alert(95.0, SITKA_LON, DetectionMethod.MANUAL)

        # Invalid longitude
        with pytest.raises(ValueError, match="Invalid longitude"):
            detector.trigger_mob_alert(SITKA_LAT, 185.0, DetectionMethod.MANUAL)

    def test_multiple_events_suspends_active(self):
        """New event suspends existing active event."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        # First event
        event1 = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL, "alice"
        )
        assert event1.status == EventStatus.ACTIVE
        assert detector.get_active_event().event_id == event1.event_id

        # Second event
        event2 = detector.trigger_mob_alert(
            SITKA_LAT + 0.01, SITKA_LON + 0.01, DetectionMethod.BEACON_LOSS, "bob"
        )
        assert event2.status == EventStatus.ACTIVE

        # First event should be suspended
        loaded_event1 = detector.get_event(event1.event_id)
        assert loaded_event1.status == EventStatus.SUSPENDED

    def test_get_active_event_none(self):
        """get_active_event returns None when no active event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = MOBDetector(storage_path=Path(tmpdir) / "mob.json")
            assert detector.get_active_event() is None

    def test_get_event_by_id(self):
        """Retrieve specific event by ID."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL, "charlie"
        )

        retrieved = detector.get_event(event.event_id)
        assert retrieved is not None
        assert retrieved.event_id == event.event_id
        assert retrieved.crew_member_id == "charlie"

    def test_resolve_event_rescued(self):
        """Resolve event as rescued."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL, "diana"
        )
        assert event.status == EventStatus.ACTIVE

        resolved = detector.resolve_event(event.event_id, "rescued")
        assert resolved.status == EventStatus.RESOLVED
        assert resolved.outcome == "rescued"
        assert resolved.resolved_at_ns is not None
        assert detector.get_active_event() is None

    def test_resolve_event_invalid_outcome(self):
        """Reject invalid resolution outcome."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL, "eve"
        )

        with pytest.raises(ValueError, match="Invalid outcome"):
            detector.resolve_event(event.event_id, "invalid_outcome")

    def test_resolve_unknown_event(self):
        """Attempt to resolve unknown event returns None."""
        detector = MOBDetector()
        result = detector.resolve_event("unknown_id", "rescued")
        assert result is None


# --------------------------------------------------------------------- #
# Position tracking
# --------------------------------------------------------------------- #
class TestPositionTracking:
    """MOB and vessel position tracking."""

    def test_update_vessel_position(self):
        """Update vessel position/heading/speed."""
        detector = MOBDetector()

        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 45.0, 8.5)

        assert detector._vessel_state["lat"] == SITKA_LAT
        assert detector._vessel_state["lon"] == SITKA_LON
        assert detector._vessel_state["heading_deg"] == 45.0
        assert detector._vessel_state["speed_kn"] == 8.5

    def test_position_recorded_in_active_event(self):
        """Position updates are recorded in active event."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        # Update position
        detector.update_vessel_position(SITKA_LAT + 0.001, SITKA_LON + 0.001, 90.0, 6.0)

        # Should be in history
        assert len(event.vessel_position_history) > 1
        latest = event.vessel_position_history[-1]
        assert latest["lat"] == SITKA_LAT + 0.001
        assert latest["heading_deg"] == 90.0

    def test_calculate_mob_position_initial(self):
        """Calculate MOB position from initial event."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        mob_lat, mob_lon = detector.calculate_mob_position()
        assert mob_lat == event.mob_lat
        assert mob_lon == event.mob_lon

    def test_calculate_mob_position_with_drift(self):
        """Calculate MOB position from drift estimate."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        # Add drift estimate
        estimate = detector.update_drift_estimate(180.0, 1.0, 270.0, 10.0)

        mob_lat, mob_lon = detector.calculate_mob_position()
        assert mob_lat == estimate.projected_lat
        assert mob_lon == estimate.projected_lon

    def test_calculate_mob_position_no_active_event(self):
        """Calculate MOB position returns None when no active event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = MOBDetector(storage_path=Path(tmpdir) / "mob.json")
            result = detector.calculate_mob_position()
            assert result is None

    def test_bearing_distance_to_mob(self):
        """Calculate bearing and distance to MOB."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        # MOB 100m north
        mob_lat = SITKA_LAT + (100.0 / 111000.0)
        event = detector.trigger_mob_alert(mob_lat, SITKA_LON, DetectionMethod.MANUAL)

        bearing, distance = detector.get_bearing_distance_to_mob()
        assert bearing == pytest.approx(0.0, abs=1.0)  # North
        assert distance == pytest.approx(100.0, abs=5.0)

    def test_bearing_distance_no_vessel_position(self):
        """Bearing/distance returns None when vessel position unknown."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        # Clear vessel state
        detector._vessel_state = {}

        result = detector.get_bearing_distance_to_mob()
        assert result is None

    def test_bearing_distance_no_active_event(self):
        """Bearing/distance returns None when no active event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = MOBDetector(storage_path=Path(tmpdir) / "mob.json")
            detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

            result = detector.get_bearing_distance_to_mob()
            assert result is None


# --------------------------------------------------------------------- #
# Drift estimation
# --------------------------------------------------------------------- #
class TestDriftEstimation:
    """MOB drift estimation with current and wind."""

    def test_update_drift_estimate(self):
        """Update drift estimate for active event."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        estimate = detector.update_drift_estimate(
            current_set_deg=180.0,  # South
            current_drift_kn=1.5,
            wind_from_deg=270.0,  # West
            wind_speed_kn=15.0,
        )

        assert estimate.timestamp_ns > event.timestamp_ns
        assert estimate.current_set_deg == 180.0
        assert estimate.current_drift_kn == 1.5
        assert estimate.wind_from_deg == 270.0
        assert estimate.wind_speed_kn == 15.0
        assert estimate.leeway_speed_kn > 0
        assert estimate.leeway_direction_deg == pytest.approx(90.0, abs=5.0)  # East (downwind)

    def test_drift_estimate_no_active_event(self):
        """Drift estimate raises error without active event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = MOBDetector(storage_path=Path(tmpdir) / "mob.json")

            with pytest.raises(RuntimeError, match="No active MOB event"):
                detector.update_drift_estimate(180.0, 1.0, 270.0, 10.0)

    def test_drift_leeway_calculation(self):
        """Leeway is ~0.20 of wind speed, downwind."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        # Wind from north at 20 kn
        estimate = detector.update_drift_estimate(
            current_set_deg=0.0,
            current_drift_kn=0.0,
            wind_from_deg=0.0,  # From north
            wind_speed_kn=20.0,
        )

        # Leeway should be ~4 kn (0.20 × 20), heading south (180°)
        assert estimate.leeway_speed_kn == pytest.approx(4.0, abs=0.5)
        assert estimate.leeway_direction_deg == pytest.approx(180.0, abs=5.0)

    def test_drift_confidence_growth(self):
        """Confidence radius grows with sqrt(time)."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        # First estimate (t=0)
        est1 = detector.update_drift_estimate(90.0, 1.0, 180.0, 10.0)

        # Simulate time passing (1 hour)
        import time
        event.timestamp_ns = int(time.time_ns() - 3600e9)

        est2 = detector.update_drift_estimate(90.0, 1.0, 180.0, 10.0)

        # Second estimate should have larger confidence radius
        assert est2.confidence_radius_m > est1.confidence_radius_m

    def test_drift_estimate_stored_in_event(self):
        """Drift estimates are stored in event history."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        detector.update_drift_estimate(45.0, 2.0, 315.0, 12.0)
        detector.update_drift_estimate(90.0, 1.5, 270.0, 8.0)

        assert len(event.drift_estimates) == 2


# --------------------------------------------------------------------- #
# Search pattern generation
# --------------------------------------------------------------------- #
class TestSearchPatterns:
    """Search pattern generation (expanding square, sector, trackline)."""

    def test_generate_expanding_square(self):
        """Generate expanding square search pattern."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        legs = detector.generate_search_pattern(
            pattern_type=SearchPatternType.EXPANDING_SQUARE,
            track_spacing_m=100.0,
            initial_bearing_deg=0.0,
            max_legs=10,
        )

        assert len(legs) == 10

        # Check leg sequence: 1, 1, 2, 2, 3, 3, ...
        lengths = [leg["length_m"] for leg in legs]
        expected = [100, 100, 200, 200, 300, 300, 400, 400, 500, 500]
        assert lengths == expected

    def test_expanding_square_turns(self):
        """Expanding square turns alternate left/right."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        legs = detector.generate_search_pattern(
            pattern_type=SearchPatternType.EXPANDING_SQUARE,
            track_spacing_m=100.0,
            initial_bearing_deg=0.0,
            max_legs=6,
        )

        # Turns should alternate +90, -90, +90, -90...
        turns = [leg.get("turn_deg") for leg in legs]
        assert turns == [90, -90, 90, -90, 90, -90]

    def test_generate_sector_search(self):
        """Generate sector search pattern."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        legs = detector.generate_search_pattern(
            pattern_type=SearchPatternType.SECTOR,
            track_spacing_m=100.0,
            initial_bearing_deg=0.0,
            num_sectors=3,
        )

        # 3 sectors × 2 legs each = 6 legs
        assert len(legs) == 6

        # All outbound legs should have same length (radius)
        outbound_legs = [leg for leg in legs if leg.get("type") == "outbound"]
        assert len(outbound_legs) == 3
        radius = 100.0 * 5  # track_spacing × 5
        assert all(leg["length_m"] == radius for leg in outbound_legs)

    def test_generate_trackline(self):
        """Generate trackline search pattern."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        legs = detector.generate_search_pattern(
            pattern_type=SearchPatternType.TRACKLINE,
            track_spacing_m=150.0,
            initial_bearing_deg=90.0,
            track_length_m=2000.0,
            num_parallel_tracks=5,
        )

        assert len(legs) == 5

        # All legs should have same length
        assert all(leg["length_m"] == 2000.0 for leg in legs)

        # All should have same bearing
        assert all(leg["bearing_deg"] == 90.0 for leg in legs)

    def test_generate_pattern_no_active_event(self):
        """Pattern generation raises error without active event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = MOBDetector(storage_path=Path(tmpdir) / "mob.json")

            with pytest.raises(RuntimeError, match="No active MOB event"):
                detector.generate_search_pattern(
                    pattern_type=SearchPatternType.EXPANDING_SQUARE
                )

    def test_generate_pattern_invalid_type(self):
        """Invalid pattern type raises error."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        with pytest.raises(ValueError, match="Unknown pattern type"):
            detector.generate_search_pattern(pattern_type="invalid_pattern")


# --------------------------------------------------------------------- #
# Search sector assignment
# --------------------------------------------------------------------- #
class TestSearchSectors:
    """Search sector assignment and tracking."""

    def test_assign_search_sector(self):
        """Assign search sector to vessel."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        sector = detector.assign_search_sector(
            vessel_id="vessel_rescue",
            pattern_type=SearchPatternType.EXPANDING_SQUARE,
            center_lat=SITKA_LAT,
            center_lon=SITKA_LON,
            track_spacing_m=100.0,
        )

        assert sector.vessel_id == "vessel_rescue"
        assert sector.pattern_type == SearchPatternType.EXPANDING_SQUARE
        assert sector.track_spacing_m == 100.0
        assert sector.status == SearchSectorStatus.ASSIGNED

    def test_assign_sector_no_active_event(self):
        """Sector assignment raises error without active event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = MOBDetector(storage_path=Path(tmpdir) / "mob.json")

            with pytest.raises(RuntimeError, match="No active MOB event"):
                detector.assign_search_sector(
                    vessel_id="vessel_x",
                    pattern_type=SearchPatternType.EXPANDING_SQUARE,
                    center_lat=SITKA_LAT,
                    center_lon=SITKA_LON,
                )

    def test_sector_stored_in_event(self):
        """Assigned sectors are stored in event."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        detector.assign_search_sector(
            vessel_id="vessel_a",
            pattern_type=SearchPatternType.SECTOR,
            center_lat=SITKA_LAT,
            center_lon=SITKA_LON,
        )
        detector.assign_search_sector(
            vessel_id="vessel_b",
            pattern_type=SearchPatternType.TRACKLINE,
            center_lat=SITKA_LAT + 0.01,
            center_lon=SITKA_LON,
        )

        assert len(event.search_sectors) == 2

    def test_get_search_coverage(self):
        """Calculate search coverage statistics."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        # Assign sector
        sector = detector.assign_search_sector(
            vessel_id="vessel_x",
            pattern_type=SearchPatternType.EXPANDING_SQUARE,
            center_lat=SITKA_LAT,
            center_lon=SITKA_LON,
        )
        # Update coverage
        event.search_sectors[-1]["coverage_area_sqm"] = 5000.0

        coverage = detector.get_search_coverage(event.event_id)

        assert coverage["event_id"] == event.event_id
        assert coverage["total_sectors"] == 1
        assert coverage["total_area_sqm"] == 5000.0

    def test_get_coverage_unknown_event(self):
        """Coverage calculation raises error for unknown event."""
        detector = MOBDetector()

        with pytest.raises(RuntimeError, match="Event not found"):
            detector.get_search_coverage("unknown_event")

    def test_get_coverage_empty_sectors(self):
        """Coverage returns zeros when no sectors assigned."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        coverage = detector.get_search_coverage(event.event_id)

        assert coverage["total_sectors"] == 0
        assert coverage["total_area_sqm"] == 0.0
        assert coverage["completed_sectors"] == 0


# --------------------------------------------------------------------- #
# Analytics
# --------------------------------------------------------------------- #
class TestAnalytics:
    """MOB search analytics and statistics."""

    def test_get_search_statistics(self):
        """Get comprehensive search statistics."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 45.0, 6.5)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL, "frank"
        )

        # Add some data
        detector.update_drift_estimate(180.0, 1.5, 270.0, 10.0)
        detector.assign_search_sector(
            vessel_id="vessel_1",
            pattern_type=SearchPatternType.EXPANDING_SQUARE,
            center_lat=SITKA_LAT,
            center_lon=SITKA_LON,
        )

        stats = detector.get_search_statistics(event.event_id)

        assert stats["event_id"] == event.event_id
        assert stats["status"] == EventStatus.ACTIVE
        assert stats["detection_method"] == DetectionMethod.MANUAL
        assert stats["crew_member_id"] == "frank"
        assert stats["drift_estimates"] == 1
        assert stats["search_sectors_assigned"] == 1
        assert stats["vessels_participating"] == 1

    def test_calculate_pod_pos(self):
        """Calculate POD and POS probabilities."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL
        )

        # No coverage yet
        pod, pos = detector.calculate_pod_pos(event.event_id)
        assert pod == pytest.approx(0.0, abs=0.01)
        assert pos == pytest.approx(0.0, abs=0.01)

        # Add coverage
        sector = detector.assign_search_sector(
            vessel_id="vessel_x",
            pattern_type=SearchPatternType.EXPANDING_SQUARE,
            center_lat=SITKA_LAT,
            center_lon=SITKA_LON,
        )
        # Simulate progress
        event.search_sectors[-1]["coverage_area_sqm"] = 10000.0
        event.search_sectors[-1]["progress_pct"] = 100.0

        pod, pos = detector.calculate_pod_pos(event.event_id)

        # POD should be high with full coverage
        assert pod > 0.8
        # POS should be slightly lower due to survival probability
        assert pos < pod
        assert pos > 0.0

    def test_statistics_unknown_event(self):
        """Statistics raises error for unknown event."""
        detector = MOBDetector()

        with pytest.raises(RuntimeError, match="Event not found"):
            detector.get_search_statistics("unknown_event")


# --------------------------------------------------------------------- #
# Integration
# --------------------------------------------------------------------- #
class TestIntegration:
    """Integration with TwinCore, Watchers, Notifications."""

    def test_to_dict(self):
        """Export detector state as dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = MOBDetector(storage_path=Path(tmpdir) / "mob.json")
            detector.update_vessel_position(SITKA_LAT, SITKA_LON, 90.0, 5.5)

            event = detector.trigger_mob_alert(
                SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL, "grace"
            )

            state = detector.to_dict()

            assert "active_event" in state
            assert state["active_event"] is not None
            assert state["active_event"]["event_id"] == event.event_id
            assert state["total_events"] == 1
            assert state["vessel_state"]["lat"] == SITKA_LAT

    def test_get_watcher_frame_no_event(self):
        """Watcher frame returns inactive when no event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = MOBDetector(storage_path=Path(tmpdir) / "mob.json")
            detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

            frame = detector.get_watcher_frame()

            assert frame["mob_active"] is False
            assert frame["mob_event_id"] is None
            assert frame["mob_lat"] is None
            assert frame["mob_alert_critical"] is False

    def test_get_watcher_frame_active_event(self):
        """Watcher frame returns active event data."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL, "henry"
        )

        # MOB 50m north of vessel
        mob_lat = SITKA_LAT + (50.0 / 111000.0)
        event.mob_lat = mob_lat

        frame = detector.get_watcher_frame()

        assert frame["mob_active"] is True
        assert frame["mob_event_id"] == event.event_id
        assert frame["mob_lat"] == mob_lat
        assert frame["mob_bearing_from_vessel_deg"] == pytest.approx(0.0, abs=2.0)
        assert frame["mob_distance_from_vessel_m"] == pytest.approx(50.0, abs=5.0)
        assert frame["mob_alert_critical"] is True  # < 100m

    def test_get_alerts_no_event(self):
        """No alerts when no active event."""
        detector = MOBDetector()
        alerts = detector.get_alerts()
        assert alerts == []

    def test_get_alerts_critical_distance(self):
        """Critical alert for close proximity."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL, "iris"
        )

        # MOB 30m away
        mob_lat = SITKA_LAT + (30.0 / 111000.0)
        event.mob_lat = mob_lat

        alerts = detector.get_alerts()

        assert len(alerts) == 1
        assert alerts[0]["type"] == "mob_active"
        assert alerts[0]["severity"] == "critical"
        assert alerts[0]["priority"] == pytest.approx(1.0, abs=0.01)
        assert alerts[0]["data"]["distance_m"] < 50

    def test_get_alerts_medium_distance(self):
        """Warning alert for medium distance."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL, "jack"
        )

        # MOB 300m away
        mob_lat = SITKA_LAT + (300.0 / 111000.0)
        event.mob_lat = mob_lat

        alerts = detector.get_alerts()

        assert len(alerts) == 1
        assert alerts[0]["severity"] == "warning"
        assert 0.6 <= alerts[0]["priority"] <= 0.8

    def test_get_alerts_with_drift(self):
        """Alerts include drift estimate data."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)

        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL, "kate"
        )

        detector.update_drift_estimate(180.0, 1.5, 270.0, 15.0)

        frame = detector.get_watcher_frame()

        # Should have drift radius
        assert frame["mob_drift_radius_m"] is not None
        assert frame["mob_drift_radius_m"] > 50


# --------------------------------------------------------------------- #
# Edge cases and error handling
# --------------------------------------------------------------------- #
class TestEdgeCases:
    """Edge cases and error handling."""

    def test_trigger_at_exact_bounds(self):
        """Accept valid coordinates at exact bounds."""
        detector = MOBDetector()

        # Should not raise
        detector.trigger_mob_alert(90.0, 180.0, DetectionMethod.MANUAL)
        detector.trigger_mob_alert(-90.0, -180.0, DetectionMethod.MANUAL)

    def test_position_update_with_none_heading_speed(self):
        """Handle position updates with missing heading/speed."""
        detector = MOBDetector()
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, None, None)

        assert detector._vessel_state["lat"] == SITKA_LAT
        assert detector._vessel_state["heading_deg"] is None
        assert detector._vessel_state["speed_kn"] is None

    def test_event_without_vessel_state(self):
        """Create event without prior vessel state."""
        detector = MOBDetector()

        # No vessel state set
        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.BEACON_LOSS, "liam"
        )

        # Should use MOB position as vessel position
        assert event.vessel_lat == SITKA_LAT
        assert event.vessel_lon == SITKA_LON
        assert event.initial_heading_deg is None
        assert event.initial_speed_kn is None

    def test_persistence_error_handling(self):
        """Handle persistence errors gracefully."""
        import os

        detector = MOBDetector(storage_path="/invalid/path/mob.jsonl")

        # Should not raise, just log error
        detector.update_vessel_position(SITKA_LAT, SITKA_LON, 0.0, 0.0)
        event = detector.trigger_mob_alert(
            SITKA_LAT, SITKA_LON, DetectionMethod.MANUAL, "mary"
        )

        # Event should still be in memory
        assert detector.get_active_event() is not None


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
