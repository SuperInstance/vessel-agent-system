"""Comprehensive test suite for QuotaManager system."""

import asyncio
import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import os

from twin.quota_manager import (
    QuotaManager,
    SpeciesQuota,
    CatchEvent,
    QuotaExhaustedError,
    QuotaValidationError,
)


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_quota.jsonl"
        yield path


@pytest.fixture
def quota_manager(temp_db_path):
    """Create a QuotaManager instance with test data."""
    qm = QuotaManager(storage_path=temp_db_path)
    # Set up some initial quotas
    qm.set_species_quota("chinook", 1000.0, quota_source="IFQ")
    qm.set_species_quota("halibut", 500.0, quota_source="CDQ")
    qm.set_species_quota("cod", 2000.0, quota_source="IFQ")
    return qm


@pytest.fixture
def sample_position():
    """Sample position for catch events."""
    return 59.5, -152.3


class TestSpeciesQuota:
    """Tests for SpeciesQuota dataclass."""

    def test_species_quota_creation(self):
        quota = SpeciesQuota(
            species="chinook",
            total_limit_lb=1000.0,
            current_catch_lb=100.0,
            reserve_percent=10.0,
            quota_source="IFQ"
        )
        assert quota.species == "chinook"
        assert quota.total_limit_lb == 1000.0
        assert quota.current_catch_lb == 100.0
        assert quota.reserve_percent == 10.0
        assert quota.quota_source == "IFQ"

    def test_remaining_quota_calculation(self):
        quota = SpeciesQuota(
            species="chinook",
            total_limit_lb=1000.0,
            current_catch_lb=200.0,
            reserve_percent=10.0
        )
        # Remaining = total - catch - reserve (100)
        expected = 1000.0 - 200.0 - 100.0
        assert quota.remaining_quota() == expected

    def test_quota_percent_used(self):
        quota = SpeciesQuota(
            species="chinook",
            total_limit_lb=1000.0,
            current_catch_lb=250.0
        )
        assert quota.percent_used() == 25.0


class TestQuotaManagerBasics:
    """Basic QuotaManager functionality tests."""

    def test_quota_manager_initialization(self, temp_db_path):
        qm = QuotaManager(storage_path=temp_db_path)
        assert qm is not None
        assert len(qm.get_all_quotas()) == 0

    def test_set_species_quota(self, quota_manager):
        quota = quota_manager.set_species_quota("sockeye", 1500.0, quota_source="CDQ")
        assert quota is not None
        assert quota.species == "sockeye"
        assert quota.total_limit_lb == 1500.0
        assert quota.current_catch_lb == 0.0

    def test_get_species_quota(self, quota_manager):
        quota = quota_manager.get_species_quota("chinook")
        assert quota is not None
        assert quota.species == "chinook"
        assert quota.total_limit_lb == 1000.0

    def test_get_nonexistent_species_quota(self, quota_manager):
        quota = quota_manager.get_species_quota("nonexistent")
        assert quota is None

    def test_get_all_quotas(self, quota_manager):
        quotas = quota_manager.get_all_quotas()
        assert len(quotas) == 3
        assert "chinook" in quotas
        assert "halibut" in quotas
        assert "cod" in quotas

    def test_update_existing_quota(self, quota_manager):
        updated = quota_manager.set_species_quota("chinook", 1500.0)
        assert updated.total_limit_lb == 1500.0
        # Current catch should be preserved
        assert updated.current_catch_lb == 0.0


class TestCatchLogging:
    """Tests for catch logging and quota deduction."""

    def test_log_catch(self, quota_manager, sample_position):
        lat, lon = sample_position
        catch = quota_manager.log_catch(
            species="chinook",
            weight_lb=50.0,
            lat=lat,
            lon=lon,
            gear_type="troll",
            vessel_id="FV-EILEEN"
        )
        assert catch is not None
        assert catch.species == "chinook"
        assert catch.weight_lb == 50.0
        assert catch.lat == lat
        assert catch.lon == lon
        assert not catch.released

        # Check quota was deducted
        quota = quota_manager.get_species_quota("chinook")
        assert quota.current_catch_lb == 50.0

    def test_log_multiple_catches(self, quota_manager, sample_position):
        lat, lon = sample_position
        quota_manager.log_catch("chinook", 50.0, lat, lon, "troll", "FV-EILEEN")
        quota_manager.log_catch("chinook", 30.0, lat, lon, "troll", "FV-EILEEN")
        quota_manager.log_catch("chinook", 20.0, lat, lon, "troll", "FV-EILEEN")

        quota = quota_manager.get_species_quota("chinook")
        assert quota.current_catch_lb == 100.0

    def test_log_catch_deducts_from_correct_species(self, quota_manager, sample_position):
        lat, lon = sample_position
        quota_manager.log_catch("halibut", 100.0, lat, lon, "longline", "FV-EILEEN")

        halibut_quota = quota_manager.get_species_quota("halibut")
        chinook_quota = quota_manager.get_species_quota("chinook")

        assert halibut_quota.current_catch_lb == 100.0
        assert chinook_quota.current_catch_lb == 0.0

    def test_log_catch_with_crew_member(self, quota_manager, sample_position):
        lat, lon = sample_position
        catch = quota_manager.log_catch(
            "chinook", 50.0, lat, lon, "troll", "FV-EILEEN",
            crew_member="captain"
        )
        assert catch.crew_member == "captain"

    def test_get_catch_history(self, quota_manager, sample_position):
        lat, lon = sample_position
        quota_manager.log_catch("chinook", 50.0, lat, lon, "troll", "FV-EILEEN")
        quota_manager.log_catch("halibut", 100.0, lat, lon, "longline", "FV-EILEEN")

        history = quota_manager.get_catch_history()
        assert len(history) == 2

        chinook_history = quota_manager.get_catch_history(species="chinook")
        assert len(chinook_history) == 1
        assert chinook_history[0]["species"] == "chinook"


class TestCatchRelease:
    """Tests for catch release and quota restoration."""

    def test_log_catch_release(self, quota_manager, sample_position):
        lat, lon = sample_position
        catch = quota_manager.log_catch("chinook", 50.0, lat, lon, "troll", "FV-EILEEN")
        catch_id = catch.catch_id

        quota_manager.log_release(catch_id, "regulatory_size_limit")

        # Check catch was marked as released
        history = quota_manager.get_catch_history()
        released_catch = [c for c in history if c["catch_id"] == catch_id][0]
        assert released_catch["released"] is True
        assert released_catch["release_reason"] == "regulatory_size_limit"

        # Check quota was restored
        quota = quota_manager.get_species_quota("chinook")
        assert quota.current_catch_lb == 0.0

    def test_release_nonexistent_catch(self, quota_manager):
        with pytest.raises(ValueError):
            quota_manager.log_release("nonexistent_id", "reason")


class TestQuotaValidation:
    """Tests for quota validation and blocking."""

    def test_check_quota_available(self, quota_manager):
        assert quota_manager.check_quota_available("chinook", 500.0) is True
        quota_manager.log_catch("chinook", 600.0, 59.5, -152.3, "troll", "FV-EILEEN")
        # 1000 - 600 = 400 remaining, 100 reserve = 300 available
        assert quota_manager.check_quota_available("chinook", 300.0) is True
        assert quota_manager.check_quota_available("chinook", 301.0) is False

    def test_log_catch_exceeds_quota_raises_error(self, quota_manager, sample_position):
        lat, lon = sample_position
        # Log catch that would exceed quota
        with pytest.raises(QuotaExhaustedError):
            quota_manager.log_catch("chinook", 950.0, lat, lon, "troll", "FV-EILEEN",
                                   validate_quota=True)

    def test_log_catch_exactly_to_quota_limit(self, quota_manager, sample_position):
        lat, lon = sample_position
        # Log exactly to limit (900 available after reserve)
        quota_manager.log_catch("chinook", 900.0, lat, lon, "troll", "FV-EILEEN",
                               validate_quota=True)
        quota = quota_manager.get_species_quota("chinook")
        assert quota.current_catch_lb == 900.0


class TestQuotaQueries:
    """Tests for quota query methods."""

    def test_get_remaining_quota(self, quota_manager):
        quota_manager.log_catch("chinook", 200.0, 59.5, -152.3, "troll", "FV-EILEEN")
        remaining = quota_manager.get_remaining_quota("chinook")
        # 1000 - 200 - 100 (reserve) = 700
        assert remaining == 700.0

    def test_get_quota_percent_used(self, quota_manager):
        quota_manager.log_catch("chinook", 250.0, 59.5, -152.3, "troll", "FV-EILEEN")
        percent = quota_manager.get_quota_percent_used("chinook")
        assert percent == 25.0

    def test_get_quota_status(self, quota_manager):
        quota_manager.log_catch("chinook", 200.0, 59.5, -152.3, "troll", "FV-EILEEN")
        status = quota_manager.get_quota_status()

        assert "chinook" in status
        assert status["chinook"]["total_limit_lb"] == 1000.0
        assert status["chinook"]["current_catch_lb"] == 200.0
        assert status["chinook"]["remaining_lb"] == 700.0
        assert status["chinook"]["percent_used"] == 20.0


class TestQuotaAnalytics:
    """Tests for quota analytics and projections."""

    def test_calculate_catch_rate(self, quota_manager, sample_position):
        lat, lon = sample_position
        now = datetime.now(timezone.utc)

        # Log catches over the last few hours
        for i in range(5):
            quota_manager.log_catch("chinook", 20.0, lat, lon, "troll", "FV-EILEEN")

        rate = quota_manager.calculate_catch_rate("chinook", window_hours=24.0)
        # 100 lb over 24 hours = ~4.17 lb/hour
        assert rate > 0

    def test_project_exhaustion_date(self, quota_manager, sample_position):
        lat, lon = sample_position

        # Log some catch
        for i in range(5):
            quota_manager.log_catch("chinook", 50.0, lat, lon, "troll", "FV-EILEEN")

        projection = quota_manager.project_exhaustion_date("chinook")
        assert projection is not None
        assert isinstance(projection, datetime)

    def test_get_bycatch_report(self, quota_manager, sample_position):
        lat, lon = sample_position
        # Log target species
        quota_manager.log_catch("chinook", 100.0, lat, lon, "troll", "FV-EILEEN")
        # Log bycatch
        quota_manager.log_catch("cod", 20.0, lat, lon, "troll", "FV-EILEEN")

        report = quota_manager.get_bycatch_report(target_species="chinook")
        assert "cod" in report
        assert report["cod"] == 20.0


class TestQuotaTransfers:
    """Tests for quota transfer functionality."""

    def test_transfer_quota(self, quota_manager):
        # Transfer 100 lb of chinook from this vessel to another
        quota_manager.transfer_quota(
            from_vessel="FV-EILEEN",
            to_vessel="FV-OTHER",
            species="chinook",
            amount_lb=100.0
        )

        # Check quota was reduced
        quota = quota_manager.get_species_quota("chinook")
        assert quota.total_limit_lb == 900.0  # 1000 - 100


class TestAlertGeneration:
    """Tests for alert generation."""

    def test_get_alerts_no_alerts(self, quota_manager):
        alerts = quota_manager.get_alerts()
        assert len(alerts) == 0

    def test_get_alerts_threshold_crossing(self, quota_manager, sample_position):
        lat, lon = sample_position
        # Log catch to cross 80% threshold
        quota_manager.log_catch("chinook", 850.0, lat, lon, "troll", "FV-EILEEN")

        alerts = quota_manager.get_alerts()
        assert len(alerts) > 0
        assert any("80%" in alert.get("message", "") for alert in alerts)


class TestWatcherFrame:
    """Tests for WatcherRegistry integration."""

    def test_get_watcher_frame(self, quota_manager):
        frame = quota_manager.get_watcher_frame()
        assert "chinook" in frame
        assert "halibut" in frame
        assert frame["chinook"]["percent_used"] >= 0
        assert frame["halibut"]["remaining_lb"] >= 0


class TestPersistence:
    """Tests for data persistence."""

    def test_save_and_load(self, temp_db_path, sample_position):
        lat, lon = sample_position

        # Create quota manager and add data
        qm1 = QuotaManager(storage_path=temp_db_path)
        qm1.set_species_quota("chinook", 1000.0)
        qm1.log_catch("chinook", 100.0, lat, lon, "troll", "FV-EILEEN")

        # Create new instance - should load from file
        qm2 = QuotaManager(storage_path=temp_db_path)
        quotas = qm2.get_all_quotas()
        assert len(quotas) == 1
        assert quotas["chinook"]["total_limit_lb"] == 1000.0
        assert quotas["chinook"]["current_catch_lb"] == 100.0


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_log_catch_negative_weight(self, quota_manager, sample_position):
        lat, lon = sample_position
        with pytest.raises(QuotaValidationError):
            quota_manager.log_catch("chinook", -50.0, lat, lon, "troll", "FV-EILEEN")

    def test_log_catch_zero_weight(self, quota_manager, sample_position):
        lat, lon = sample_position
        with pytest.raises(QuotaValidationError):
            quota_manager.log_catch("chinook", 0.0, lat, lon, "troll", "FV-EILEEN")

    def test_log_catch_invalid_species(self, quota_manager, sample_position):
        lat, lon = sample_position
        with pytest.raises(QuotaValidationError):
            quota_manager.log_catch("invalid_species", 50.0, lat, lon, "troll", "FV-EILEEN")

    def test_set_quota_negative_limit(self, quota_manager):
        with pytest.raises(QuotaValidationError):
            quota_manager.set_species_quota("chinook", -1000.0)

    def test_invalid_position(self, quota_manager):
        with pytest.raises(QuotaValidationError):
            quota_manager.log_catch("chinook", 50.0, 999.0, -152.3, "troll", "FV-EILEEN")

    def test_quota_expiry(self, quota_manager):
        expiry = datetime.now(timezone.utc) + timedelta(days=1)
        quota = quota_manager.set_species_quota("chinook", 1000.0, expiry_date=expiry)
        assert quota.expiry_date is not None


class TestOpLogIntegration:
    """Tests for OpLog integration."""

    def test_quota_actions_logged_to_oplog(self, quota_manager, sample_position):
        lat, lon = sample_position
        # This test would require OpLog integration
        # For now, we test that the data structure supports it
        quota_manager.log_catch("chinook", 50.0, lat, lon, "troll", "FV-EILEEN",
                               crew_member="captain")

        catch_events = quota_manager.get_catch_history()
        assert len(catch_events) == 1
        assert catch_events[0]["crew_member"] == "captain"


@pytest.mark.integration
class TestQuotaManagerIntegration:
    """Integration tests for QuotaManager with other components."""

    def test_quota_with_watcher_registry(self, quota_manager):
        # Test that quota data can be used in WatcherRegistry evaluation
        frame = quota_manager.get_watcher_frame()
        assert isinstance(frame, dict)
        assert "chinook" in frame

    def test_quota_to_dict_serialization(self, quota_manager):
        # Test that quota data can be serialized for snapshots
        data = quota_manager.to_dict()
        assert isinstance(data, dict)
        assert "quotas" in data
        assert "catch_history" in data
