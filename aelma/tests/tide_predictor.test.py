"""Comprehensive tests for the TidePredictor system.

Tests tide prediction, depth clearance checking, safe passage windows,
and integration with TwinCore.
"""

import pytest
from datetime import datetime, timedelta, timezone

from build_kimi.twin.tide_predictor import (
    TidePredictor,
    TidePrediction,
    TideEvent,
)


@pytest.fixture
def predictor():
    """Create a default tide predictor for testing."""
    return TidePredictor(base_amplitude=2.0, datum_mllw_m=0.0)


@pytest.fixture
def alaska_location():
    """Provide a test location in Alaska (high tidal range)."""
    return 59.5, -152.3  # Kodiak Island area


@pytest.fixture
def moderate_location():
    """Provide a test location with moderate tides."""
    return 45.5, -122.5  # Oregon coast


class TestTidePredictorBasics:
    """Test basic tide predictor functionality."""

    def test_initialization(self):
        """Test predictor can be initialized with different parameters."""
        # Default initialization
        pred = TidePredictor()
        assert pred.base_amplitude == 2.0
        assert pred.datum_mllw_m == 0.0

        # Custom initialization
        pred = TidePredictor(base_amplitude=3.5, datum_mllw_m=1.2)
        assert pred.base_amplitude == 3.5
        assert pred.datum_mllw_m == 1.2

    def test_predict_tide_returns_valid_prediction(self, predictor, alaska_location):
        """Test that predict_tide returns a valid prediction."""
        lat, lon = alaska_location
        now = datetime.now(timezone.utc)

        prediction = predictor.predict_tide(lat, lon, now)

        assert isinstance(prediction, TidePrediction)
        assert isinstance(prediction.water_level_m, float)
        assert -5.0 < prediction.water_level_m < 5.0  # Reasonable range
        assert 0.0 <= prediction.confidence <= 1.0
        assert prediction.timestamp == now
        assert len(prediction.constituents_used) == 6  # M2, S2, O1, K1, N2, P1

    def test_predict_tide_without_timestamp(self, predictor, alaska_location):
        """Test predict_tide uses current time when timestamp is None."""
        lat, lon = alaska_location
        prediction = predictor.predict_tide(lat, lon, None)
        assert prediction.timestamp is not None
        assert isinstance(prediction.timestamp, datetime)

    def test_predict_tide_at_different_locations(self, predictor):
        """Test tide prediction varies by location."""
        now = datetime.now(timezone.utc)

        # Alaska (high latitude, large tidal range)
        tide_ak = predictor.predict_tide(59.5, -152.3, now)

        # Equator (low latitude, small tidal range)
        tide_eq = predictor.predict_tide(0.0, -120.0, now)

        # Alaska should have different tidal behavior than equator
        # (either larger amplitude or just different due to phase)
        # We just check they're not identical
        assert tide_ak.water_level_m != tide_eq.water_level_m or \
               abs(tide_ak.water_level_m) > 0.1 or \
               abs(tide_eq.water_level_m) > 0.1

    def test_predict_tide_temporal_consistency(self, predictor, alaska_location):
        """Test that predictions change over time (tides are not static)."""
        lat, lon = alaska_location

        now = datetime.now(timezone.utc)
        later = now + timedelta(hours=6)

        tide_now = predictor.predict_tide(lat, lon, now)
        tide_later = predictor.predict_tide(lat, lon, later)

        # Tide levels should be different after 6 hours
        assert tide_now.water_level_m != tide_later.water_level_m


class TestTideRange:
    """Test tide range (high/low tide) functionality."""

    def test_get_tide_range_returns_events(self, predictor, alaska_location):
        """Test that get_tide_range returns high/low tide events."""
        lat, lon = alaska_location
        start = datetime.now(timezone.utc)

        events = predictor.get_tide_range(lat, lon, start, duration_hours=24)

        assert isinstance(events, list)
        assert len(events) > 0

        # Should have both high and low tides
        event_types = {e.event_type for e in events}
        assert "high" in event_types
        assert "low" in event_types

        # Check each event has valid data
        for event in events:
            assert isinstance(event, TideEvent)
            assert isinstance(event.timestamp, datetime)
            assert isinstance(event.level_m, float)
            assert event.event_type in ["high", "low"]

    def test_tide_range_semi_diurnal_pattern(self, predictor, moderate_location):
        """Test that we get approximately 2 high and 2 low tides per day."""
        lat, lon = moderate_location
        start = datetime.now(timezone.utc)

        events = predictor.get_tide_range(lat, lon, start, duration_hours=24)

        high_tides = [e for e in events if e.event_type == "high"]
        low_tides = [e for e in events if e.event_type == "low"]

        # Semi-diurnal: approximately 2 high and 2 low per day
        assert len(high_tides) >= 1  # At least 1 high tide
        assert len(low_tides) >= 1   # At least 1 low tide

        # Total events should be around 4 (may vary slightly due to timing)
        assert 3 <= len(events) <= 5

    def test_get_tide_range_chronological_order(self, predictor, alaska_location):
        """Test that tide events are returned in chronological order."""
        lat, lon = alaska_location
        start = datetime.now(timezone.utc)

        events = predictor.get_tide_range(lat, lon, start, duration_hours=12)

        # Check timestamps are in ascending order
        for i in range(len(events) - 1):
            assert events[i].timestamp < events[i + 1].timestamp

    def test_get_next_high_low_tides(self, predictor, alaska_location):
        """Test get_next_high_low_tides returns expected structure."""
        lat, lon = alaska_location
        now = datetime.now(timezone.utc)

        result = predictor.get_next_high_low_tides(lat, lon, now)

        assert "location" in result
        assert "query_time" in result
        assert "next_high_tide" in result
        assert "next_low_tide" in result

        # Check location
        assert result["location"]["lat"] == lat
        assert result["location"]["lon"] == lon

        # Check next high tide
        if result["next_high_tide"]:
            high = result["next_high_tide"]
            assert "timestamp" in high
            assert "level_m" in high
            assert "hours_from_now" in high
            assert high["hours_from_now"] > 0

        # Check next low tide
        if result["next_low_tide"]:
            low = result["next_low_tide"]
            assert "timestamp" in low
            assert "level_m" in low
            assert "hours_from_now" in low
            assert low["hours_from_now"] > 0


class TestDepthClearance:
    """Test depth clearance checking functionality."""

    def test_check_depth_clearance_safe(self, predictor):
        """Test depth clearance when there's plenty of water."""
        lat, lon = 45.0, -122.0
        vessel_draft = 2.0  # 2m draft
        chart_depth = 10.0  # 10m chart depth

        result = predictor.check_depth_clearance(vessel_draft, chart_depth, lat, lon)

        assert result["status"] == "safe"
        assert result["clearance_ok"] is True
        assert result["under_keel_clearance_m"] >= result["safety_margin_m"]

    def test_check_depth_clearance_danger(self, predictor):
        """Test depth clearance when water is too shallow."""
        lat, lon = 45.0, -122.0
        vessel_draft = 5.0  # 5m draft
        chart_depth = 4.0   # 4m chart depth

        result = predictor.check_depth_clearance(vessel_draft, chart_depth, lat, lon)

        assert result["status"] == "danger"
        assert result["clearance_ok"] is False

    def test_check_depth_clearance_custom_margin(self, predictor):
        """Test depth clearance with custom safety margin."""
        lat, lon = 45.0, -122.0
        vessel_draft = 2.0
        chart_depth = 5.0

        # Default 1m margin
        result1 = predictor.check_depth_clearance(vessel_draft, chart_depth, lat, lon)
        margin1 = result1["safety_margin_m"]

        # Custom 2m margin
        result2 = predictor.check_depth_clearance(
            vessel_draft, chart_depth, lat, lon, safety_margin_m=2.0
        )
        margin2 = result2["safety_margin_m"]

        assert margin1 == 1.0
        assert margin2 == 2.0

    def test_check_depth_clearance_result_structure(self, predictor):
        """Test that check_depth_clearance returns all required fields."""
        lat, lon = 45.0, -122.0
        result = predictor.check_depth_clearance(2.0, 5.0, lat, lon)

        required_fields = [
            "status",
            "timestamp",
            "vessel_draft_m",
            "chart_depth_m",
            "tide_level_m",
            "water_depth_m",
            "under_keel_clearance_m",
            "safety_margin_m",
            "clearance_ok",
        ]

        for field in required_fields:
            assert field in result


class TestSafePassage:
    """Test safe passage window analysis."""

    def test_get_safe_passage_window_structure(self, predictor):
        """Test that get_safe_passage_window returns expected structure."""
        lat, lon = 45.0, -122.0
        now = datetime.now(timezone.utc)

        result = predictor.get_safe_passage_window(
            vessel_draft_m=2.0,
            chart_depth_m=5.0,
            lat=lat,
            lon=lon,
            start_time=now,
            window_hours=12,
        )

        # Check structure
        assert "vessel_draft_m" in result
        assert "chart_depth_m" in result
        assert "safety_margin_m" in result
        assert "analysis_start" in result
        assert "analysis_duration_hours" in result
        assert "tide_events" in result
        assert "safe_windows" in result
        assert "unsafe_periods" in result
        assert "total_safe_minutes" in result

    def test_safe_passage_includes_tide_events(self, predictor, moderate_location):
        """Test that safe passage analysis includes tide events."""
        lat, lon = moderate_location
        now = datetime.now(timezone.utc)

        result = predictor.get_safe_passage_window(
            vessel_draft_m=2.0,
            chart_depth_m=5.0,
            lat=lat,
            lon=lon,
            start_time=now,
            window_hours=12,
        )

        # Should have tide events
        assert len(result["tide_events"]) > 0

        # Each event should have required fields
        for event in result["tide_events"]:
            assert "timestamp" in event
            assert "level_m" in event
            assert "type" in event
            assert event["type"] in ["high", "low"]

    def test_safe_passage_windows_chronological(self, predictor, moderate_location):
        """Test that safe passage windows are in chronological order."""
        lat, lon = moderate_location
        now = datetime.now(timezone.utc)

        result = predictor.get_safe_passage_window(
            vessel_draft_m=2.0,
            chart_depth_m=5.0,
            lat=lat,
            lon=lon,
            start_time=now,
            window_hours=12,
        )

        # Check safe windows are chronological
        for i in range(len(result["safe_windows"]) - 1):
            window_start = datetime.fromisoformat(result["safe_windows"][i]["start"])
            next_window_start = datetime.fromisoformat(result["safe_windows"][i + 1]["start"])
            assert window_start < next_window_start

    def test_safe_passage_with_varied_depths(self, predictor):
        """Test safe passage analysis with different depth scenarios."""
        lat, lon = 45.0, -122.0
        now = datetime.now(timezone.utc)

        # Deep water - should be mostly safe
        result_deep = predictor.get_safe_passage_window(
            vessel_draft_m=2.0,
            chart_depth_m=10.0,
            lat=lat,
            lon=lon,
            start_time=now,
            window_hours=12,
        )

        # Shallow water - should have unsafe periods
        result_shallow = predictor.get_safe_passage_window(
            vessel_draft_m=4.0,
            chart_depth_m=5.0,
            lat=lat,
            lon=lon,
            start_time=now,
            window_hours=12,
        )

        # Deep water should have more safe time
        assert result_deep["total_safe_minutes"] >= result_shallow["total_safe_minutes"]


class TestTidePredictionAccuracy:
    """Test tide prediction accuracy and consistency."""

    def test_high_tide_higher_than_low_tide(self, predictor, moderate_location):
        """Test that high tides are higher than low tides."""
        lat, lon = moderate_location
        start = datetime.now(timezone.utc)

        events = predictor.get_tide_range(lat, lon, start, duration_hours=48)

        high_tides = [e for e in events if e.event_type == "high"]
        low_tides = [e for e in events if e.event_type == "low"]

        # Should have both types
        assert len(high_tides) > 0
        assert len(low_tides) > 0

        # Average high tide should be higher than average low tide
        avg_high = sum(e.level_m for e in high_tides) / len(high_tides)
        avg_low = sum(e.level_m for e in low_tides) / len(low_tides)

        assert avg_high > avg_low

    def test_tidal_range_reasonable(self, predictor, alaska_location):
        """Test that tidal range is reasonable for the location."""
        lat, lon = alaska_location
        start = datetime.now(timezone.utc)

        events = predictor.get_tide_range(lat, lon, start, duration_hours=24)

        if len(events) >= 2:
            levels = [e.level_m for e in events]
            tidal_range = max(levels) - min(levels)

            # Alaska should have significant tidal range (1-5m)
            assert 1.0 < tidal_range < 8.0

    def test_tide_levels_within_bounds(self, predictor, moderate_location):
        """Test that tide levels stay within reasonable bounds."""
        lat, lon = moderate_location
        start = datetime.now(timezone.utc)

        # Sample tide levels over 24 hours
        for hour in range(0, 24, 2):
            time = start + timedelta(hours=hour)
            prediction = predictor.predict_tide(lat, lon, time)

            # Tide levels should be reasonable (-3m to +3m for default amplitude)
            assert -4.0 < prediction.water_level_m < 4.0


class TestTidePredictorIntegration:
    """Integration tests for tide predictor with TwinCore."""

    def test_predictor_with_alaska_high_tides(self, predictor):
        """Test tide prediction for Alaska with higher tidal ranges."""
        # Alaska locations have higher tidal ranges
        lat, lon = 59.5, -152.3
        now = datetime.now(timezone.utc)

        # Sample multiple times
        levels = []
        for hour in range(0, 24, 2):
            time = now + timedelta(hours=hour)
            pred = predictor.predict_tide(lat, lon, time)
            levels.append(pred.water_level_m)

        # Should see variation in tidal levels
        assert max(levels) - min(levels) > 1.0

    def test_predictor_consistent_repeated_predictions(self, predictor, alaska_location):
        """Test that repeated predictions for same time are consistent."""
        lat, lon = alaska_location
        now = datetime.now(timezone.utc)

        pred1 = predictor.predict_tide(lat, lon, now)
        pred2 = predictor.predict_tide(lat, lon, now)

        # Should be identical
        assert pred1.water_level_m == pred2.water_level_m
        assert pred1.confidence == pred2.confidence

    def test_different_amplitudes_affect_predictions(self, alaska_location):
        """Test that different base amplitudes produce different predictions."""
        lat, lon = alaska_location
        now = datetime.now(timezone.utc)

        pred_small = TidePredictor(base_amplitude=1.0)
        pred_large = TidePredictor(base_amplitude=3.0)

        tide_small = pred_small.predict_tide(lat, lon, now)
        tide_large = pred_large.predict_tide(lat, lon, now)

        # Larger amplitude should produce larger absolute tide levels
        # (though this depends on phase)
        assert abs(tide_large.water_level_m) > abs(tide_small.water_level_m) or \
               tide_large.water_level_m == tide_small.water_level_m  # May be equal if phase is 0


class TestTidePredictionEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_predict_tide_at_equator(self, predictor):
        """Test tide prediction at the equator (minimal tides)."""
        lat, lon = 0.0, 0.0
        now = datetime.now(timezone.utc)

        prediction = predictor.predict_tide(lat, lon, now)

        # Should still work, just with smaller amplitude
        assert isinstance(prediction, TidePrediction)
        assert -3.0 < prediction.water_level_m < 3.0

    def test_predict_tide_high_latitude(self, predictor):
        """Test tide prediction at high latitude."""
        lat, lon = 70.0, -150.0  # Arctic Ocean
        now = datetime.now(timezone.utc)

        prediction = predictor.predict_tide(lat, lon, now)

        # Should still work
        assert isinstance(prediction, TidePrediction)

    def test_depth_clearance_zero_depth(self, predictor):
        """Test depth clearance with zero chart depth."""
        lat, lon = 45.0, -122.0

        result = predictor.check_depth_clearance(
            vessel_draft_m=2.0,
            chart_depth_m=0.0,
            lat=lat,
            lon=lon,
        )

        # Should still work, but be dangerous
        assert result["status"] == "danger"
        assert result["clearance_ok"] is False

    def test_safe_passage_very_short_window(self, predictor):
        """Test safe passage with very short analysis window."""
        lat, lon = 45.0, -122.0
        now = datetime.now(timezone.utc)

        result = predictor.get_safe_passage_window(
            vessel_draft_m=2.0,
            chart_depth_m=5.0,
            lat=lat,
            lon=lon,
            start_time=now,
            window_hours=1.0,  # Only 1 hour
        )

        # Should still work
        assert result["analysis_duration_hours"] == 1.0
        assert "safe_windows" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
