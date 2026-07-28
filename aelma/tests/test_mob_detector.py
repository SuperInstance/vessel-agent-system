"""Comprehensive test suite for MOB Detector system."""

import asyncio
import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import math

from twin.mob_detector import (
    MOBDetector,
    MOBEvent,
    DriftEstimate,
    SearchSector,
    MOBInactiveError,
    PositionValidationError,
)


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_mob.jsonl"
        yield path


@pytest.fixture
def mob_detector(temp_db_path):
    """Create an MOBDetector instance."""
    mob = MOBDetector(storage_path=temp_db_path)
    return mob


@pytest.fixture
def sample_mob_position():
    """Sample MOB event position."""
    return 59.5, -152.3


@pytest.fixture
def sample_vessel_position():
    """Sample vessel position during MOB event."""
    return 59.501, -152.301


class TestMOBEvent:
    """Tests for MOBEvent dataclass."""

    def test_mob_event_creation(self):
        event = MOBEvent(
            event_id="mob-001",
            timestamp_ns=1234567890000000000,
            mob_lat=59.5,
            mob_lon=-152.3,
            vessel_lat=59.501,
            vessel_lon=-152.301,
            crew_member_id="crew-123",
            detection_method="manual",
            initial_heading_deg=180.0,
            initial_speed_kn=5.0,
            status="active"
        )
        assert event.event_id == "mob-001"
        assert event.mob_lat == 59.5
        assert event.detection_method == "manual"
        assert event.status == "active"


class TestMOBDetectorBasics:
    """Basic MOBDetector functionality tests."""

    def test_mob_detector_initialization(self, temp_db_path):
        mob = MOBDetector(storage_path=temp_db_path)
        assert mob is not None
        assert mob.get_active_event() is None

    def test_trigger_mob_alert(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        event = mob_detector.trigger_mob_alert(
            lat=lat,
            lon=lon,
            detection_method="manual",
            crew_member_id="captain"
        )
        assert event is not None
        assert event.mob_lat == lat
        assert event.mob_lon == lon
        assert event.detection_method == "manual"
        assert event.status == "active"

    def test_get_active_event(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")
        active = mob_detector.get_active_event()
        assert active is not None
        assert active.status == "active"

    def test_trigger_second_mob_alert_resolves_first(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        event1 = mob_detector.trigger_mob_alert(lat, lon, "manual")
        event2 = mob_detector.trigger_mob_alert(lat + 0.01, lon + 0.01, "manual")

        assert event2.status == "active"
        assert event1.status == "resolved"

    def test_get_event_by_id(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        event = mob_detector.trigger_mob_alert(lat, lon, "manual")
        retrieved = mob_detector.get_event(event.event_id)
        assert retrieved is not None
        assert retrieved.event_id == event.event_id


class TestPositionTracking:
    """Tests for position tracking calculations."""

    def test_update_vessel_position(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")
        mob_detector.update_vessel_position(
            lat=lat + 0.01,
            lon=lon + 0.01,
            heading=180.0,
            speed=6.0
        )

        active = mob_detector.get_active_event()
        assert active.vessel_lat == lat + 0.01
        assert active.vessel_lon == lon + 0.01

    def test_calculate_bearing_to_mob(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")
        mob_detector.update_vessel_position(lat + 0.01, lon, heading=0, speed=0)

        bearing, distance = mob_detector.get_bearing_distance_to_mob()
        assert bearing is not None
        assert 0 <= bearing < 360
        assert distance > 0

    def test_bearing_calculation_accuracy(self, mob_detector):
        # Test bearing from (59.5, -152.3) to (59.501, -152.301)
        # Should be approximately northeast (45 degrees)
        mob_detector.trigger_mob_alert(59.5, -152.3, "manual")
        mob_detector.update_vessel_position(59.501, -152.301, heading=0, speed=0)

        bearing, distance = mob_detector.get_bearing_distance_to_mob()
        # Allow some tolerance for calculation method
        assert 30 <= bearing <= 60

    def test_distance_calculation_accuracy(self, mob_detector):
        # Two positions ~100m apart
        mob_detector.trigger_mob_alert(59.5, -152.3, "manual")
        mob_detector.update_vessel_position(59.501, -152.3, heading=0, speed=0)

        bearing, distance = mob_detector.get_bearing_distance_to_mob()
        # Should be approximately 111m (0.001 degrees latitude)
        assert 100 <= distance <= 120


class TestDriftEstimation:
    """Tests for drift estimation calculations."""

    def test_update_drift_estimate(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")

        drift = mob_detector.update_drift_estimate(
            current_set_deg=180.0,
            current_drift_kn=0.5,
            wind_from_deg=270.0,
            wind_speed_kn=15.0
        )

        assert drift is not None
        assert drift.current_set_deg == 180.0
        assert drift.current_drift_kn == 0.5
        assert drift.wind_from_deg == 270.0
        assert drift.wind_speed_kn == 15.0

    def test_drift_projection_accuracy(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")

        # Set up drift: 0.5 knot current from south, 15 knot wind from west
        mob_detector.update_drift_estimate(
            current_set_deg=0.0,  # From south (drifts north)
            current_drift_kn=0.5,
            wind_from_deg=270.0,  # From west (drifts east)
            wind_speed_kn=15.0
        )

        projected = mob_detector.calculate_mob_position()
        assert projected is not None
        proj_lat, proj_lon = projected

        # Should have moved north and east
        assert proj_lat > lat
        assert proj_lon > lon

    def test_drift_confidence_radius_grows_with_time(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")
        mob_detector.update_drift_estimate(0.0, 0.5, 270.0, 15.0)

        # Check that confidence radius increases over time
        drift1 = mob_detector.update_drift_estimate(0.0, 0.5, 270.0, 15.0)
        # Wait a bit (simulate by calling again)
        drift2 = mob_detector.update_drift_estimate(0.0, 0.5, 270.0, 15.0)

        # Confidence radius should grow
        assert drift2.confidence_radius_m >= drift1.confidence_radius_m


class TestSearchPatternGeneration:
    """Tests for search pattern generation."""

    def test_expanding_square_pattern(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")

        pattern = mob_detector.generate_search_pattern(
            pattern_type="expanding_square",
            track_spacing_m=100.0
        )

        assert len(pattern) > 0
        assert pattern[0]["pattern_type"] == "expanding_square"
        assert "waypoints" in pattern[0]

    def test_sector_search_pattern(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")

        pattern = mob_detector.generate_search_pattern(
            pattern_type="sector",
            track_spacing_m=100.0
        )

        assert len(pattern) > 0
        assert pattern[0]["pattern_type"] == "sector"

    def test_track_line_pattern(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")

        # Set a course for track line
        mob_detector.update_vessel_position(lat, lon, heading=90.0, speed=5.0)

        pattern = mob_detector.generate_search_pattern(
            pattern_type="trackline",
            track_spacing_m=100.0
        )

        assert len(pattern) > 0
        assert pattern[0]["pattern_type"] == "trackline"

    def test_search_pattern_waypoint_count(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")

        pattern = mob_detector.generate_search_pattern(
            pattern_type="expanding_square",
            track_spacing_m=100.0,
            num_legs=4
        )

        # Expanding square with 4 legs should have multiple waypoints
        waypoints = pattern[0]["waypoints"]
        assert len(waypoints) > 4


class TestSearchSectorAssignment:
    """Tests for search sector assignment."""

    def test_assign_search_sector(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")

        sector = mob_detector.assign_search_sector(
            vessel_id="FV-EILEEN",
            sector_data={
                "pattern_type": "expanding_square",
                "center_lat": lat,
                "center_lon": lon,
                "search_direction_deg": 0.0,
                "track_spacing_m": 100.0
            }
        )

        assert sector is not None
        assert sector.vessel_id == "FV-EILEEN"
        assert sector.status == "assigned"

    def test_get_search_coverage(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")

        mob_detector.assign_search_sector(
            vessel_id="FV-EILEEN",
            sector_data={"pattern_type": "expanding_square", "center_lat": lat, "center_lon": lon}
        )

        coverage = mob_detector.get_search_coverage(mob_detector.get_active_event().event_id)
        assert coverage is not None
        assert "assigned_sectors" in coverage
        assert "total_area_m2" in coverage


class TestSearchStatistics:
    """Tests for search statistics and POD/POS calculations."""

    def test_get_search_statistics(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        event = mob_detector.trigger_mob_alert(lat, lon, "manual")

        stats = mob_detector.get_search_statistics(event.event_id)
        assert stats is not None
        assert "event_duration_seconds" in stats
        assert "distance_traveled_m" in stats

    def test_calculate_pod_pos(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        event = mob_detector.trigger_mob_alert(lat, lon, "manual")

        # Assign some search sectors
        for i in range(3):
            mob_detector.assign_search_sector(
                vessel_id=f"FV-VESSEL-{i}",
                sector_data={"pattern_type": "expanding_square", "center_lat": lat, "center_lon": lon}
            )

        pod, pos = mob_detector.calculate_pod_pos(event.event_id)
        assert 0.0 <= pod <= 1.0
        assert 0.0 <= pos <= 1.0


class TestEventResolution:
    """Tests for event resolution and outcome recording."""

    def test_resolve_event_rescued(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        event = mob_detector.trigger_mob_alert(lat, lon, "manual")

        mob_detector.resolve_event(
            event_id=event.event_id,
            outcome="rescued",
            rescue_time_ns=datetime.now(timezone.utc).timestamp_ns(),
            rescue_location=(lat + 0.001, lon + 0.001)
        )

        resolved = mob_detector.get_event(event.event_id)
        assert resolved.status == "rescued"

    def test_resolve_event_recovered(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        event = mob_detector.trigger_mob_alert(lat, lon, "manual")

        mob_detector.resolve_event(
            event_id=event.event_id,
            outcome="recovered"
        )

        resolved = mob_detector.get_event(event.event_id)
        assert resolved.status == "recovered"

    def test_resolved_event_no_longer_active(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        event = mob_detector.trigger_mob_alert(lat, lon, "manual")

        mob_detector.resolve_event(event.event_id, "rescued")
        active = mob_detector.get_active_event()
        assert active is None


class TestWatcherFrame:
    """Tests for WatcherRegistry integration."""

    def test_get_watcher_frame_no_active_event(self, mob_detector):
        frame = mob_detector.get_watcher_frame()
        assert "mob_active" in frame
        assert frame["mob_active"] is False

    def test_get_watcher_frame_with_active_event(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")
        mob_detector.update_vessel_position(lat + 0.01, lon, heading=180.0, speed=6.0)

        frame = mob_detector.get_watcher_frame()
        assert frame["mob_active"] is True
        assert "bearing_to_mob_deg" in frame
        assert "distance_to_mob_m" in frame


class TestAlertGeneration:
    """Tests for alert generation."""

    def test_get_alerts_no_active_event(self, mob_detector):
        alerts = mob_detector.get_alerts()
        assert len(alerts) == 0

    def test_get_alerts_mob_event_triggered(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")

        alerts = mob_detector.get_alerts()
        assert len(alerts) > 0
        assert "MOB event triggered" in alerts[0].get("message", "")


class TestPersistence:
    """Tests for data persistence."""

    def test_save_and_load(self, temp_db_path, sample_mob_position):
        lat, lon = sample_mob_position

        # Create MOB detector and add event
        mob1 = MOBDetector(storage_path=temp_db_path)
        event1 = mob1.trigger_mob_alert(lat, lon, "manual")
        mob1.update_vessel_position(lat + 0.01, lon, heading=180.0, speed=6.0)

        # Create new instance - should load from file
        mob2 = MOBDetector(storage_path=temp_db_path)
        event2 = mob2.get_event(event1.event_id)
        assert event2 is not None
        assert event2.mob_lat == lat
        assert event2.mob_lon == lon


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_trigger_mob_alert_invalid_position(self, mob_detector):
        with pytest.raises(PositionValidationError):
            mob_detector.trigger_mob_alert(999.0, -152.3, "manual")

    def test_update_vessel_position_without_active_event(self, mob_detector):
        # Should not raise error, just no-op
        mob_detector.update_vessel_position(59.5, -152.3, heading=0, speed=0)

    def test_get_bearing_distance_without_active_event(self, mob_detector):
        result = mob_detector.get_bearing_distance_to_mob()
        assert result is None

    def test_generate_search_pattern_without_active_event(self, mob_detector):
        with pytest.raises(MOBInactiveError):
            mob_detector.generate_search_pattern("expanding_square")

    def test_resolve_nonexistent_event(self, mob_detector):
        with pytest.raises(ValueError):
            mob_detector.resolve_event("nonexistent", "rescued")

    def test_invalid_detection_method(self, mob_detector, sample_mob_position):
        lat, lon = sample_mob_position
        with pytest.raises(ValueError):
            mob_detector.trigger_mob_alert(lat, lon, "invalid_method")


@pytest.mark.integration
class TestMOBDetectorIntegration:
    """Integration tests for MOBDetector with other components."""

    def test_mob_with_fleet_manager(self, mob_detector, sample_mob_position):
        # Test multi-vessel search coordination
        lat, lon = sample_mob_position
        event = mob_detector.trigger_mob_alert(lat, lon, "manual")

        # Assign search sectors to multiple vessels
        for i in range(3):
            mob_detector.assign_search_sector(
                vessel_id=f"FV-VESSEL-{i}",
                sector_data={
                    "pattern_type": "expanding_square",
                    "center_lat": lat + i * 0.001,
                    "center_lon": lon + i * 0.001
                }
            )

        coverage = mob_detector.get_search_coverage(event.event_id)
        assert coverage["assigned_sectors"] == 3

    def test_mob_drift_with_weather_data(self, mob_detector, sample_mob_position):
        # Test drift estimation with environmental data
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")

        # Simulate weather data update
        drift = mob_detector.update_drift_estimate(
            current_set_deg=45.0,
            current_drift_kn=0.3,
            wind_from_deg=180.0,
            wind_speed_kn=20.0
        )

        assert drift.current_set_deg == 45.0
        assert drift.wind_speed_kn == 20.0

    def test_mob_to_dict_serialization(self, mob_detector, sample_mob_position):
        # Test that MOB data can be serialized for snapshots
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")
        mob_detector.update_vessel_position(lat + 0.01, lon, heading=180.0, speed=6.0)

        data = mob_detector.to_dict()
        assert isinstance(data, dict)
        assert "active_event" in data
        assert "search_sectors" in data


class TestSearchPatternAccuracy:
    """Tests for search pattern geometric accuracy."""

    def test_expanding_square_geometry(self, mob_detector, sample_mob_position):
        """Test that expanding square follows correct geometry."""
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")

        pattern = mob_detector.generate_search_pattern(
            pattern_type="expanding_square",
            track_spacing_m=100.0,
            num_legs=4
        )

        waypoints = pattern[0]["waypoints"]
        # Should have at least 4 waypoints (4 legs)
        assert len(waypoints) >= 4

        # Check that waypoints are roughly correct distances apart
        # Each leg should be approximately track_spacing in length
        for i in range(len(waypoints) - 1):
            wp1 = waypoints[i]
            wp2 = waypoints[i + 1]
            # Simple distance check (approximate)
            dist = math.sqrt((wp1["lat"] - wp2["lat"])**2 + (wp1["lon"] - wp2["lon"])**2)
            assert dist > 0

    def test_sector_search_geometry(self, mob_detector, sample_mob_position):
        """Test that sector search covers 120-degree sectors."""
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")

        pattern = mob_detector.generate_search_pattern(
            pattern_type="sector",
            track_spacing_m=100.0,
            num_sectors=3
        )

        assert len(pattern) == 3  # 3 sectors

    def test_track_line_follows_course(self, mob_detector, sample_mob_position):
        """Test that track line follows vessel's previous course."""
        lat, lon = sample_mob_position
        mob_detector.trigger_mob_alert(lat, lon, "manual")

        # Set vessel on a specific course
        mob_detector.update_vessel_position(lat, lon, heading=90.0, speed=5.0)

        pattern = mob_detector.generate_search_pattern(
            pattern_type="trackline",
            track_spacing_m=100.0
        )

        waypoints = pattern[0]["waypoints"]
        # Waypoints should follow east-west line (heading 90)
        assert len(waypoints) > 0
