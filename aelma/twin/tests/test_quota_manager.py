"""Comprehensive tests for QuotaManager: quota tracking, catch logging, analytics."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from twin.quota_manager import (
    CatchEvent,
    QuotaManager,
    SpeciesQuota,
    ALERT_THRESHOLDS,
    VALID_SPECIES,
    QUOTA_SOURCES,
    _generate_catch_id,
    _now_ns,
)

T0 = 1_753_478_400_000_000_000  # Fixed epoch ns for deterministic tests
SITKA_LAT, SITKA_LON = 57.0531, -135.3300


# --------------------------------------------------------------------- #
# Dataclass validation
# --------------------------------------------------------------------- #

class TestSpeciesQuota:
    """SpeciesQuota dataclass validation."""

    def test_valid_quota(self):
        quota = SpeciesQuota(
            species="chinook",
            total_limit_lb=1000.0,
            current_catch_lb=100.0,
            reserve_percent=10.0,
            quota_source="IFQ",
        )
        assert quota.species == "chinook"
        assert quota.total_limit_lb == 1000.0
        assert quota.remaining_lb() == 900.0
        assert quota.usable_lb() == 800.0  # 900 - 10% reserve
        assert quota.percent_used() == 10.0

    def test_invalid_species_raises(self):
        with pytest.raises(ValueError, match="Invalid species"):
            SpeciesQuota(
                species="tuna",
                total_limit_lb=1000.0,
            )

    def test_negative_total_limit_raises(self):
        with pytest.raises(ValueError, match="total_limit_lb must be positive"):
            SpeciesQuota(
                species="chinook",
                total_limit_lb=-100.0,
            )

    def test_negative_current_catch_raises(self):
        with pytest.raises(ValueError, match="current_catch_lb cannot be negative"):
            SpeciesQuota(
                species="chinook",
                total_limit_lb=1000.0,
                current_catch_lb=-50.0,
            )

    def test_invalid_reserve_percent_raises(self):
        with pytest.raises(ValueError, match="reserve_percent must be between 0 and 100"):
            SpeciesQuota(
                species="chinook",
                total_limit_lb=1000.0,
                reserve_percent=150.0,
            )

    def test_invalid_quota_source_raises(self):
        with pytest.raises(ValueError, match="Invalid quota_source"):
            SpeciesQuota(
                species="chinook",
                total_limit_lb=1000.0,
                quota_source="INVALID",
            )

    def test_catch_exceeds_limit_raises(self):
        with pytest.raises(ValueError, match="cannot exceed"):
            SpeciesQuota(
                species="chinook",
                total_limit_lb=1000.0,
                current_catch_lb=1500.0,
            )

    def test_remaining_lb_calculation(self):
        quota = SpeciesQuota(
            species="halibut",
            total_limit_lb=500.0,
            current_catch_lb=200.0,
        )
        assert quota.remaining_lb() == 300.0

        quota.current_catch_lb = 500.0
        assert quota.remaining_lb() == 0.0

    def test_usable_lb_includes_reserve(self):
        quota = SpeciesQuota(
            species="cod",
            total_limit_lb=1000.0,
            current_catch_lb=0.0,
            reserve_percent=20.0,
        )
        assert quota.usable_lb() == 800.0  # 1000 - 20%

    def test_percent_used_calculation(self):
        quota = SpeciesQuota(
            species="coho",
            total_limit_lb=1000.0,
            current_catch_lb=250.0,
        )
        assert quota.percent_used() == 25.0

    def test_to_dict(self):
        quota = SpeciesQuota(
            species="sockeye",
            total_limit_lb=2000.0,
            current_catch_lb=500.0,
        )
        d = quota.to_dict()
        assert d["species"] == "sockeye"
        assert d["total_limit_lb"] == 2000.0
        assert d["current_catch_lb"] == 500.0


class TestCatchEvent:
    """CatchEvent dataclass validation."""

    def test_valid_catch(self):
        catch = CatchEvent(
            catch_id="test_001",
            species="chinook",
            weight_lb=15.5,
            lat=SITKA_LAT,
            lon=SITKA_LON,
            timestamp_ns=T0,
            gear_type="purse_seine",
            vessel_id="US-AK-FVEILEEN-51",
        )
        assert catch.species == "chinook"
        assert catch.weight_lb == 15.5
        assert catch.lat == SITKA_LAT
        assert catch.lon == SITKA_LON

    def test_invalid_species_raises(self):
        with pytest.raises(ValueError, match="Invalid species"):
            CatchEvent(
                catch_id="test_001",
                species="tuna",
                weight_lb=15.5,
                lat=SITKA_LAT,
                lon=SITKA_LON,
                timestamp_ns=T0,
                gear_type="purse_seine",
                vessel_id="US-AK-FVEILEEN-51",
            )

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError, match="weight_lb must be positive"):
            CatchEvent(
                catch_id="test_001",
                species="chinook",
                weight_lb=-5.0,
                lat=SITKA_LAT,
                lon=SITKA_LON,
                timestamp_ns=T0,
                gear_type="purse_seine",
                vessel_id="US-AK-FVEILEEN-51",
            )

    def test_lat_out_of_range_raises(self):
        with pytest.raises(ValueError, match="lat out of range"):
            CatchEvent(
                catch_id="test_001",
                species="chinook",
                weight_lb=15.5,
                lat=95.0,
                lon=SITKA_LON,
                timestamp_ns=T0,
                gear_type="purse_seine",
                vessel_id="US-AK-FVEILEEN-51",
            )

    def test_lon_out_of_range_raises(self):
        with pytest.raises(ValueError, match="lon out of range"):
            CatchEvent(
                catch_id="test_001",
                species="chinook",
                weight_lb=15.5,
                lat=SITKA_LAT,
                lon=185.0,
                timestamp_ns=T0,
                gear_type="purse_seine",
                vessel_id="US-AK-FVEILEEN-51",
            )

    def test_invalid_timestamp_ns_raises(self):
        with pytest.raises(ValueError, match="timestamp_ns must be positive int"):
            CatchEvent(
                catch_id="test_001",
                species="chinook",
                weight_lb=15.5,
                lat=SITKA_LAT,
                lon=SITKA_LON,
                timestamp_ns=-1,
                gear_type="purse_seine",
                vessel_id="US-AK-FVEILEEN-51",
            )

    def test_empty_gear_type_raises(self):
        with pytest.raises(ValueError, match="gear_type must be a non-empty string"):
            CatchEvent(
                catch_id="test_001",
                species="chinook",
                weight_lb=15.5,
                lat=SITKA_LAT,
                lon=SITKA_LON,
                timestamp_ns=T0,
                gear_type="",
                vessel_id="US-AK-FVEILEEN-51",
            )

    def test_empty_vessel_id_raises(self):
        with pytest.raises(ValueError, match="vessel_id must be a non-empty string"):
            CatchEvent(
                catch_id="test_001",
                species="chinook",
                weight_lb=15.5,
                lat=SITKA_LAT,
                lon=SITKA_LON,
                timestamp_ns=T0,
                gear_type="purse_seine",
                vessel_id="",
            )

    def test_released_without_reason_raises(self):
        with pytest.raises(ValueError, match="release_reason required"):
            CatchEvent(
                catch_id="test_001",
                species="chinook",
                weight_lb=15.5,
                lat=SITKA_LAT,
                lon=SITKA_LON,
                timestamp_ns=T0,
                gear_type="purse_seine",
                vessel_id="US-AK-FVEILEEN-51",
                released=True,
            )

    def test_released_with_reason_succeeds(self):
        catch = CatchEvent(
            catch_id="test_001",
            species="chinook",
            weight_lb=15.5,
            lat=SITKA_LAT,
            lon=SITKA_LON,
            timestamp_ns=T0,
            gear_type="purse_seine",
            vessel_id="US-AK-FVEILEEN-51",
            released=True,
            release_reason="size_limit",
        )
        assert catch.released is True
        assert catch.release_reason == "size_limit"

    def test_to_dict(self):
        catch = CatchEvent(
            catch_id="test_001",
            species="chinook",
            weight_lb=15.5,
            lat=SITKA_LAT,
            lon=SITKA_LON,
            timestamp_ns=T0,
            gear_type="purse_seine",
            vessel_id="US-AK-FVEILEEN-51",
        )
        d = catch.to_dict()
        assert d["catch_id"] == "test_001"
        assert d["species"] == "chinook"
        assert d["weight_lb"] == 15.5


# --------------------------------------------------------------------- #
# QuotaManager initialization
# --------------------------------------------------------------------- #

class TestQuotaManagerInit:
    """QuotaManager initialization and basic operations."""

    def test_init_no_storage(self):
        qm = QuotaManager(storage_path=None)
        assert qm.vessel_id == "US-AK-FVEILEEN-51"
        assert len(qm.quotas) == 0
        assert len(qm._catches) == 0

    def test_init_with_custom_vessel_id(self):
        qm = QuotaManager(storage_path=None, vessel_id="US-AK-TEST-123")
        assert qm.vessel_id == "US-AK-TEST-123"

    def test_init_with_custom_reserve(self):
        qm = QuotaManager(storage_path=None, default_reserve_percent=15.0)
        assert qm.default_reserve_percent == 15.0

    def test_init_loads_from_storage(self, tmp_path):
        # First create some data
        qm1 = QuotaManager(storage_path=tmp_path)
        qm1.set_species_quota("chinook", 1000.0)
        qm1.log_catch("chinook", 50.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0)

        # Create new manager - should load data
        qm2 = QuotaManager(storage_path=tmp_path)
        assert "chinook" in qm2.quotas
        assert qm2.quotas["chinook"].total_limit_lb == 1000.0
        assert len(qm2._catches) == 1


# --------------------------------------------------------------------- #
# Quota management
# --------------------------------------------------------------------- #

class TestQuotaManagement:
    """Quota CRUD operations."""

    def test_set_species_quota(self):
        qm = QuotaManager(storage_path=None)
        quota = qm.set_species_quota("chinook", 1000.0)
        assert quota.species == "chinook"
        assert quota.total_limit_lb == 1000.0
        assert quota.current_catch_lb == 0.0
        assert "chinook" in qm.quotas

    def test_set_quota_with_custom_params(self):
        qm = QuotaManager(storage_path=None)
        quota = qm.set_species_quota(
            species="halibut",
            total_limit_lb=500.0,
            current_catch_lb=100.0,
            reserve_percent=15.0,
            quota_source="CDQ",
        )
        assert quota.total_limit_lb == 500.0
        assert quota.current_catch_lb == 100.0
        assert quota.reserve_percent == 15.0
        assert quota.quota_source == "CDQ"

    def test_get_species_quota(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("coho", 800.0)
        quota = qm.get_species_quota("coho")
        assert quota is not None
        assert quota.total_limit_lb == 800.0

    def test_get_nonexistent_quota_returns_none(self):
        qm = QuotaManager(storage_path=None)
        assert qm.get_species_quota("tuna") is None

    def test_get_all_quotas(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        qm.set_species_quota("coho", 800.0)
        quotas = qm.get_all_quotas()
        assert len(quotas) == 2
        assert "chinook" in quotas
        assert "coho" in quotas

    def test_update_species_quota_total_limit(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        updated = qm.update_species_quota("chinook", total_limit_lb=1500.0)
        assert updated is not None
        assert updated.total_limit_lb == 1500.0

    def test_update_species_quota_current_catch(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        updated = qm.update_species_quota("chinook", current_catch_lb=250.0)
        assert updated is not None
        assert updated.current_catch_lb == 250.0

    def test_update_nonexistent_quota_returns_none(self):
        qm = QuotaManager(storage_path=None)
        assert qm.update_species_quota("tuna", total_limit_lb=1000.0) is None

    def test_remove_species_quota(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        assert qm.remove_species_quota("chinook") is True
        assert "chinook" not in qm.quotas

    def test_remove_nonexistent_quota_returns_false(self):
        qm = QuotaManager(storage_path=None)
        assert qm.remove_species_quota("tuna") is False

    def test_transfer_quota(self):
        qm = QuotaManager(storage_path=tmp_path)
        transfer = qm.transfer_quota(
            from_vessel="US-AK-VESSEL1",
            to_vessel="US-AK-VESSEL2",
            species="chinook",
            amount_lb=100.0,
        )
        assert transfer["species"] == "chinook"
        assert transfer["amount_lb"] == 100.0
        assert transfer["from_vessel"] == "US-AK-VESSEL1"
        assert transfer["to_vessel"] == "US-AK-VESSEL2"

    def test_transfer_quota_negative_amount_raises(self):
        qm = QuotaManager(storage_path=None)
        with pytest.raises(ValueError, match="amount_lb must be positive"):
            qm.transfer_quota(
                from_vessel="V1",
                to_vessel="V2",
                species="chinook",
                amount_lb=-50.0,
            )


# --------------------------------------------------------------------- #
# Catch logging
# --------------------------------------------------------------------- #

class TestCatchLogging:
    """Catch event logging and quota deduction."""

    def test_log_catch(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        catch = qm.log_catch(
            species="chinook",
            weight_lb=50.0,
            lat=SITKA_LAT,
            lon=SITKA_LON,
            gear_type="purse_seine",
            timestamp_ns=T0,
        )
        assert catch.species == "chinook"
        assert catch.weight_lb == 50.0
        assert qm.quotas["chinook"].current_catch_lb == 50.0

    def test_log_catch_deducts_from_quota(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("coho", 800.0)
        qm.log_catch("coho", 100.0, SITKA_LAT, SITKA_LON, "gillnet", timestamp_ns=T0)
        qm.log_catch("coho", 50.0, SITKA_LAT, SITKA_LON, "gillnet", timestamp_ns=T0 + 1)
        assert qm.quotas["coho"].current_catch_lb == 150.0

    def test_log_catch_without_quota_raises(self):
        qm = QuotaManager(storage_path=None)
        with pytest.raises(ValueError, match="No quota set for species"):
            qm.log_catch("chinook", 50.0, SITKA_LAT, SITKA_LON, "purse_seine")

    def test_log_catch_insufficient_quota_raises(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 100.0, reserve_percent=10.0)
        with pytest.raises(ValueError, match="Insufficient quota"):
            qm.log_catch("chinook", 95.0, SITKA_LAT, SITKA_LON, "purse_seine")

    def test_log_catch_respects_reserve(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0, reserve_percent=20.0)
        # Can catch up to 800 (1000 - 20%)
        catch = qm.log_catch("chinook", 800.0, SITKA_LAT, SITKA_LON, "purse_seine")
        assert catch.weight_lb == 800.0

    def test_log_catch_exceeding_reserve_raises(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0, reserve_percent=20.0)
        with pytest.raises(ValueError, match="Insufficient quota"):
            qm.log_catch("chinook", 850.0, SITKA_LAT, SITKA_LON, "purse_seine")

    def test_log_catch_with_crew_member(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("halibut", 500.0)
        catch = qm.log_catch(
            species="halibut",
            weight_lb=30.0,
            lat=SITKA_LAT,
            lon=SITKA_LON,
            gear_type="longline",
            crew_member="captain",
        )
        assert catch.crew_member == "captain"

    def test_log_release_restores_quota(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        catch = qm.log_catch("chinook", 100.0, SITKA_LAT, SITKA_LON, "purse_seine")
        assert qm.quotas["chinook"].current_catch_lb == 100.0

        qm.log_release(catch.catch_id, "size_limit")
        assert qm.quotas["chinook"].current_catch_lb == 0.0

    def test_log_release_nonexistent_catch_returns_none(self):
        qm = QuotaManager(storage_path=None)
        result = qm.log_release("nonexistent_id", "size_limit")
        assert result is None

    def test_log_release_already_released_returns_catch(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        catch = qm.log_catch("chinook", 50.0, SITKA_LAT, SITKA_LON, "purse_seine")
        qm.log_release(catch.catch_id, "size_limit")

        # Release again
        result = qm.log_release(catch.catch_id, "size_limit")
        assert result is not None
        assert result.released is True

    def test_get_catch_history(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        qm.log_catch("chinook", 50.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0)
        qm.log_catch("chinook", 30.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0 + 1)

        history = qm.get_catch_history(species="chinook")
        assert len(history) == 2

    def test_get_catch_history_filtered_by_species(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        qm.set_species_quota("coho", 800.0)
        qm.log_catch("chinook", 50.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0)
        qm.log_catch("coho", 30.0, SITKA_LAT, SITKA_LON, "gillnet", timestamp_ns=T0 + 1)

        chinook_history = qm.get_catch_history(species="chinook")
        coho_history = qm.get_catch_history(species="coho")

        assert len(chinook_history) == 1
        assert len(coho_history) == 1
        assert chinook_history[0].species == "chinook"
        assert coho_history[0].species == "coho"

    def test_get_catch_history_respects_limit(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        for i in range(10):
            qm.log_catch("chinook", 10.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0 + i)

        history = qm.get_catch_history(species="chinook", limit=5)
        assert len(history) == 5


# --------------------------------------------------------------------- #
# Quota queries
# --------------------------------------------------------------------- #

class TestQuotaQueries:
    """Quota status and availability queries."""

    def test_get_remaining_quota(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        qm.log_catch("chinook", 200.0, SITKA_LAT, SITKA_LON, "purse_seine")
        assert qm.get_remaining_quota("chinook") == 800.0

    def test_get_remaining_quota_nonexistent_species(self):
        qm = QuotaManager(storage_path=None)
        assert qm.get_remaining_quota("tuna") == 0.0

    def test_get_quota_percent_used(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        qm.log_catch("chinook", 250.0, SITKA_LAT, SITKA_LON, "purse_seine")
        assert qm.get_quota_percent_used("chinook") == 25.0

    def test_get_quota_percent_used_nonexistent_species(self):
        qm = QuotaManager(storage_path=None)
        assert qm.get_quota_percent_used("tuna") == 0.0

    def test_check_quota_available_true(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0, reserve_percent=10.0)
        assert qm.check_quota_available("chinook", 500.0) is True

    def test_check_quota_available_false_no_quota(self):
        qm = QuotaManager(storage_path=None)
        assert qm.check_quota_available("chinook", 100.0) is False

    def test_check_quota_available_false_insufficient(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 100.0, reserve_percent=10.0)
        assert qm.check_quota_available("chinook", 95.0) is False

    def test_get_quota_status(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0, reserve_percent=15.0)
        qm.log_catch("chinook", 200.0, SITKA_LAT, SITKA_LON, "purse_seine")

        status = qm.get_quota_status()
        assert "chinook" in status
        chinook_status = status["chinook"]
        assert chinook_status["total_limit_lb"] == 1000.0
        assert chinook_status["current_catch_lb"] == 200.0
        assert chinook_status["remaining_lb"] == 800.0
        assert chinook_status["usable_lb"] == 650.0  # 800 - 15% reserve
        assert chinook_status["percent_used"] == 20.0


# --------------------------------------------------------------------- #
# Analytics
# --------------------------------------------------------------------- #

class TestAnalytics:
    """Catch rate, exhaustion projections, and bycatch."""

    def test_calculate_catch_rate(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)

        # Log catches over 10 hours
        for i in range(10):
            qm.log_catch(
                "chinook",
                10.0,
                SITKA_LAT,
                SITKA_LON,
                "purse_seine",
                timestamp_ns=T0 + i * 3600_000_000_000,
            )

        # Rate should be 100 lb / 24 hr = 4.17 lb/hr (window covers all catches)
        rate = qm.calculate_catch_rate("chinook", window_hours=24.0)
        assert rate == pytest.approx(10.0 * 10 / 24.0, rel=0.01)

    def test_calculate_catch_rate_ignores_released(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)

        catch1 = qm.log_catch("chinook", 100.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0)
        catch2 = qm.log_catch("chinook", 50.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0 + 1)
        qm.log_release(catch1.catch_id, "size_limit")

        # Only catch2 counts (50 lb)
        rate = qm.calculate_catch_rate("chinook", window_hours=1.0)
        assert rate == pytest.approx(50.0)

    def test_project_exhaustion_date(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0, reserve_percent=10.0)

        # Catch at 100 lb/hr
        for i in range(10):
            qm.log_catch(
                "chinook",
                100.0,
                SITKA_LAT,
                SITKA_LON,
                "purse_seine",
                timestamp_ns=T0 + i * 3600_000_000_000,
            )

        projection = qm.project_exhaustion_date("chinook")
        assert projection is not None
        # Should project based on 100 lb/hr over 900 usable lb = 9 hours

    def test_project_exhaustion_already_exhausted(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 100.0, reserve_percent=10.0)
        qm.log_catch("chinook", 90.0, SITKA_LAT, SITKA_LON, "purse_seine")

        projection = qm.project_exhaustion_date("chinook")
        assert projection is not None  # Returns current time

    def test_project_exhaustion_no_recent_catch(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        # No catches yet
        projection = qm.project_exhaustion_date("chinook")
        assert projection is None  # Can't project without catch rate

    def test_get_bycatch_report(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        qm.set_species_quota("coho", 800.0)
        qm.set_species_quota("halibut", 500.0)

        qm.log_catch("chinook", 100.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0)
        qm.log_catch("coho", 30.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0 + 1)
        qm.log_catch("halibut", 20.0, SITKA_LAT, SITKA_LON, "longline", timestamp_ns=T0 + 2)

        bycatch = qm.get_bycatch_report("chinook")
        assert bycatch["coho"] == 30.0
        assert bycatch["halibut"] == 20.0
        assert "chinook" not in bycatch

    def test_get_bycatch_report_ignores_released(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        qm.set_species_quota("coho", 800.0)

        catch1 = qm.log_catch("coho", 30.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0)
        qm.log_catch("chinook", 100.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0 + 1)
        qm.log_release(catch1.catch_id, "size_limit")

        bycatch = qm.get_bycatch_report("chinook")
        assert "coho" not in bycatch  # Released, not counted

    def test_get_species_summary(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0, reserve_percent=10.0)
        qm.log_catch("chinook", 100.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0)

        summary = qm.get_species_summary("chinook")
        assert summary["species"] == "chinook"
        assert summary["quota_set"] is True
        assert summary["total_limit_lb"] == 1000.0
        assert summary["current_catch_lb"] == 100.0
        assert summary["remaining_lb"] == 900.0
        assert summary["usable_lb"] == 800.0
        assert summary["percent_used"] == 10.0
        assert summary["catch_count"] == 1

    def test_get_species_summary_no_quota(self):
        qm = QuotaManager(storage_path=None)
        summary = qm.get_species_summary("tuna")
        assert summary["quota_set"] is False


# --------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------- #

class TestAlerts:
    """Quota threshold alert generation."""

    def test_alert_at_80_percent(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0, reserve_percent=0.0)

        # Catch exactly 80%
        qm.log_catch("chinook", 800.0, SITKA_LAT, SITKA_LON, "purse_seine")
        alerts = qm.get_alerts("chinook")
        assert len(alerts) >= 1
        assert any(a["threshold"] == 80.0 for a in alerts)

    def test_alert_at_90_percent(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0, reserve_percent=0.0)

        qm.log_catch("chinook", 900.0, SITKA_LAT, SITKA_LON, "purse_seine")
        alerts = qm.get_alerts("chinook")
        assert any(a["threshold"] == 90.0 for a in alerts)

    def test_alert_at_95_percent(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0, reserve_percent=0.0)

        qm.log_catch("chinook", 950.0, SITKA_LAT, SITKA_LON, "purse_seine")
        alerts = qm.get_alerts("chinook")
        assert any(a["threshold"] == 95.0 for a in alerts)

    def test_alert_at_100_percent(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0, reserve_percent=0.0)

        qm.log_catch("chinook", 1000.0, SITKA_LAT, SITKA_LON, "purse_seine")
        alerts = qm.get_alerts("chinook")
        assert any(a["threshold"] == 100.0 for a in alerts)

    def test_alert_only_once_per_threshold(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0, reserve_percent=0.0)

        qm.log_catch("chinook", 850.0, SITKA_LAT, SITKA_LON, "purse_seine")
        alerts_after_85 = qm.get_alerts("chinook")
        count_80 = sum(1 for a in alerts_after_85 if a["threshold"] == 80.0)

        qm.log_catch("chinook", 50.0, SITKA_LAT, SITKA_LON, "purse_seine")
        alerts_after_90 = qm.get_alerts("chinook")
        count_80_again = sum(1 for a in alerts_after_90 if a["threshold"] == 80.0)

        assert count_80 == count_80_again  # No duplicate 80% alert

    def test_get_alerts_respects_limit(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0, reserve_percent=0.0)
        qm.set_species_quota("coho", 1000.0, reserve_percent=0.0)

        qm.log_catch("chinook", 900.0, SITKA_LAT, SITKA_LON, "purse_seine")
        qm.log_catch("coho", 900.0, SITKA_LAT, SITKA_LON, "gillnet")

        all_alerts = qm.get_alerts(limit=1)
        assert len(all_alerts) == 1


# --------------------------------------------------------------------- #
# Integration
# --------------------------------------------------------------------- #

class TestIntegration:
    """TwinCore integration APIs."""

    def test_to_dict(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        qm.log_catch("chinook", 100.0, SITKA_LAT, SITKA_LON, "purse_seine")

        d = qm.to_dict()
        assert d["vessel_id"] == "US-AK-FVEILEEN-51"
        assert "chinook" in d["quotas"]
        assert d["catch_count"] == 1

    def test_get_watcher_frame(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0, reserve_percent=10.0)
        qm.log_catch("chinook", 100.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0)

        frame = qm.get_watcher_frame()
        assert "quota_chinook_percent_used" in frame
        assert "quota_chinook_remaining_lb" in frame
        assert "quota_chinook_usable_lb" in frame
        assert frame["quota_chinook_percent_used"] == 10.0
        assert frame["quota_chinook_remaining_lb"] == 900.0
        assert frame["quota_chinook_usable_lb"] == 800.0

    def test_get_watcher_frame_includes_catch_rates(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        qm.log_catch("chinook", 100.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0)

        frame = qm.get_watcher_frame()
        assert "quota_catch_rate_chinook_lb_per_hr" in frame

    def test_get_watcher_frame_alert_count(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0, reserve_percent=0.0)
        qm.log_catch("chinook", 900.0, SITKA_LAT, SITKA_LON, "purse_seine")

        frame = qm.get_watcher_frame()
        assert frame["quota_alert_count"] >= 1


# --------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------- #

class TestPersistence:
    """JSONL persistence and loading."""

    def test_quota_persistence_roundtrip(self, tmp_path):
        qm1 = QuotaManager(storage_path=tmp_path)
        qm1.set_species_quota("chinook", 1000.0)
        qm1.set_species_quota("coho", 800.0)

        # Create new instance
        qm2 = QuotaManager(storage_path=tmp_path)
        assert "chinook" in qm2.quotas
        assert "coho" in qm2.quotas
        assert qm2.quotas["chinook"].total_limit_lb == 1000.0
        assert qm2.quotas["coho"].total_limit_lb == 800.0

    def test_catch_persistence_roundtrip(self, tmp_path):
        qm1 = QuotaManager(storage_path=tmp_path)
        qm1.set_species_quota("chinook", 1000.0)
        qm1.log_catch("chinook", 100.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0)
        qm1.log_catch("chinook", 50.0, SITKA_LAT, SITKA_LON, "purse_seine", timestamp_ns=T0 + 1)

        # Create new instance
        qm2 = QuotaManager(storage_path=tmp_path)
        assert len(qm2._catches) == 2
        assert sum(c.weight_lb for c in qm2._catches if not c.released) == 150.0

    def test_release_persistence_roundtrip(self, tmp_path):
        qm1 = QuotaManager(storage_path=tmp_path)
        qm1.set_species_quota("chinook", 1000.0)
        catch = qm1.log_catch("chinook", 100.0, SITKA_LAT, SITKA_LON, "purse_seine")
        qm1.log_release(catch.catch_id, "size_limit")

        # Create new instance
        qm2 = QuotaManager(storage_path=tmp_path)
        assert qm2.quotas["chinook"].current_catch_lb == 0.0

        # Find the released catch
        released_catch = None
        for c in qm2._catches:
            if c.catch_id == catch.catch_id:
                released_catch = c
                break
        assert released_catch is not None
        assert released_catch.released is True

    def test_transfer_persistence(self, tmp_path):
        qm1 = QuotaManager(storage_path=tmp_path)
        qm1.transfer_quota("V1", "V2", "chinook", 100.0)

        # Transfer records are logged but not loaded into state
        # They exist in the file for audit trail
        assert (tmp_path / "catch.jsonl").exists()


# --------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------- #

class TestEdgeCases:
    """Edge cases and error conditions."""

    def test_zero_weight_catch_raises(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        with pytest.raises(ValueError, match="weight_lb must be positive"):
            qm.log_catch("chinook", 0.0, SITKA_LAT, SITKA_LON, "purse_seine")

    def test_catch_id_is_unique(self):
        ids = [_generate_catch_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All unique

    def test_all_valid_species(self):
        for species in VALID_SPECIES:
            qm = QuotaManager(storage_path=None)
            qm.set_species_quota(species, 1000.0)
            assert species in qm.quotas

    def test_all_quota_sources(self):
        for source in QUOTA_SOURCES:
            qm = QuotaManager(storage_path=None)
            qm.set_species_quota("chinook", 1000.0, quota_source=source)
            assert qm.quotas["chinook"].quota_source == source

    def test_quota_with_expiry_date(self):
        qm = QuotaManager(storage_path=None)
        quota = qm.set_species_quota(
            "chinook",
            1000.0,
            expiry_date="2026-12-31T23:59:59.000000+00:00",
        )
        assert quota.expiry_date == "2026-12-31T23:59:59.000000+00:00"

    def test_multiple_species_independent(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1000.0)
        qm.set_species_quota("coho", 800.0)
        qm.set_species_quota("halibut", 500.0)

        qm.log_catch("chinook", 200.0, SITKA_LAT, SITKA_LON, "purse_seine")
        qm.log_catch("coho", 100.0, SITKA_LAT, SITKA_LON, "gillnet")

        assert qm.quotas["chinook"].current_catch_lb == 200.0
        assert qm.quotas["coho"].current_catch_lb == 100.0
        assert qm.quotas["halibut"].current_catch_lb == 0.0

    def test_large_quota_values(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 1_000_000.0)  # 1 million lb
        qm.log_catch("chinook", 50_000.0, SITKA_LAT, SITKA_LON, "purse_seine")
        assert qm.quotas["chinook"].current_catch_lb == 50_000.0

    def test_small_quota_values(self):
        qm = QuotaManager(storage_path=None)
        qm.set_species_quota("chinook", 10.0)
        qm.log_catch("chinook", 1.5, SITKA_LAT, SITKA_LON, "purse_seine")
        assert qm.quotas["chinook"].current_catch_lb == 1.5
