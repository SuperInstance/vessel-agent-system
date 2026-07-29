"""Tests for the Environmental Stewardship system.

Covers fuel logging, emissions calculation, waste tracking, bycatch recording,
sustainability metrics, alert generation, integration tests, and edge cases.
"""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# Import the actual classes
from twin.environmental.stewardship import (
    ALERT_BYCATCH_RATIO_MAX_PCT,
    ALERT_EFFICIENCY_MIN_NM_PER_GAL,
    ALERT_EMISSIONS_BASELINE_PCT,
    ALERT_WASTE_NONCOMPLIANCE_MAX_PCT,
    AlertSeverity,
    BycatchDisposition,
    BycatchEvent,
    CarbonFootprint,
    DisposalMethod,
    EMISSION_FACTORS,
    EmissionFactor,
    EnvironmentalStewardship,
    FuelRecord,
    FuelType,
    SustainabilityMetric,
    SUSTAINABILITY_TARGETS,
    WasteRecord,
    WasteType,
)

# Test constants
T0 = 1_753_478_400_000_000_000  # Fixed epoch ns for deterministic tests


# ============================================================================ #
# Fuel Record Tests
# ============================================================================ #

class TestFuelRecord:
    """Test fuel record creation and validation."""

    def test_create_fuel_record(self):
        """Create a valid fuel record."""
        record = FuelRecord(
            timestamp_ns=T0,
            fuel_type=FuelType.DIESEL,
            quantity_gal=10.5,
            source="main_engine",
            location_lat=58.5,
            location_lon=-157.0,
            engine_hours=1250.5,
        )
        assert record.timestamp_ns == T0
        assert record.fuel_type == FuelType.DIESEL
        assert record.quantity_gal == 10.5
        assert record.source == "main_engine"
        assert record.location_lat == 58.5
        assert record.location_lon == -157.0
        assert record.engine_hours == 1250.5

    def test_fuel_record_validation_invalid_timestamp(self):
        """Non-integer timestamp should raise ValueError."""
        with pytest.raises(ValueError, match="timestamp_ns must be an integer"):
            FuelRecord(
                timestamp_ns="invalid",
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.5,
                source="main_engine",
            )

    def test_fuel_record_validation_negative_timestamp(self):
        """Negative timestamp should raise ValueError."""
        with pytest.raises(ValueError, match="timestamp_ns must be non-negative"):
            FuelRecord(
                timestamp_ns=-1,
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.5,
                source="main_engine",
            )

    def test_fuel_record_validation_invalid_quantity(self):
        """Non-numeric quantity should raise ValueError."""
        with pytest.raises(ValueError, match="quantity_gal must be a number"):
            FuelRecord(
                timestamp_ns=T0,
                fuel_type=FuelType.DIESEL,
                quantity_gal="invalid",
                source="main_engine",
            )

    def test_fuel_record_validation_negative_quantity(self):
        """Negative quantity should raise ValueError."""
        with pytest.raises(ValueError, match="quantity_gal must be non-negative"):
            FuelRecord(
                timestamp_ns=T0,
                fuel_type=FuelType.DIESEL,
                quantity_gal=-1.0,
                source="main_engine",
            )

    def test_fuel_record_validation_empty_source(self):
        """Empty source should raise ValueError."""
        with pytest.raises(ValueError, match="source must be a non-empty string"):
            FuelRecord(
                timestamp_ns=T0,
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.5,
                source="",
            )

    def test_fuel_record_fuel_type_conversion(self):
        """Fuel type should convert from string to enum."""
        record = FuelRecord(
            timestamp_ns=T0,
            fuel_type="DIESEL",
            quantity_gal=10.5,
            source="main_engine",
        )
        assert record.fuel_type == FuelType.DIESEL
        assert isinstance(record.fuel_type, FuelType)

    def test_fuel_record_to_dict(self):
        """Convert fuel record to dictionary."""
        record = FuelRecord(
            timestamp_ns=T0,
            fuel_type=FuelType.DIESEL,
            quantity_gal=10.5,
            source="main_engine",
            location_lat=58.5,
            location_lon=-157.0,
            engine_hours=1250.5,
        )
        data = record.to_dict()
        assert data["timestamp_ns"] == T0
        assert data["fuel_type"] == "DIESEL"
        assert data["quantity_gal"] == 10.5
        assert data["source"] == "main_engine"
        assert data["location_lat"] == 58.5
        assert data["location_lon"] == -157.0
        assert data["engine_hours"] == 1250.5

    def test_fuel_record_from_dict(self):
        """Create fuel record from dictionary."""
        data = {
            "timestamp_ns": T0,
            "fuel_type": "DIESEL",
            "quantity_gal": 10.5,
            "source": "main_engine",
            "location_lat": 58.5,
            "location_lon": -157.0,
            "engine_hours": 1250.5,
        }
        record = FuelRecord.from_dict(data)
        assert record.timestamp_ns == T0
        assert record.fuel_type == FuelType.DIESEL
        assert record.quantity_gal == 10.5


# ============================================================================ #
# Emission Factor Tests
# ============================================================================ #

class TestEmissionFactor:
    """Test emission factor creation and validation."""

    def test_create_emission_factor(self):
        """Create a valid emission factor."""
        factor = EmissionFactor(
            fuel_type=FuelType.DIESEL,
            co2_per_gal=22.38,
            sox_per_gal=0.03,
            nox_per_gal=0.85,
            pm_per_gal=0.05,
        )
        assert factor.fuel_type == FuelType.DIESEL
        assert factor.co2_per_gal == 22.38
        assert factor.sox_per_gal == 0.03
        assert factor.nox_per_gal == 0.85
        assert factor.pm_per_gal == 0.05

    def test_emission_factor_validation_negative_value(self):
        """Negative emission factor should raise ValueError."""
        with pytest.raises(ValueError, match="must be non-negative"):
            EmissionFactor(
                fuel_type=FuelType.DIESEL,
                co2_per_gal=-1.0,
                sox_per_gal=0.03,
                nox_per_gal=0.85,
                pm_per_gal=0.05,
            )

    def test_emission_factor_to_dict(self):
        """Convert emission factor to dictionary."""
        factor = EmissionFactor(
            fuel_type=FuelType.DIESEL,
            co2_per_gal=22.38,
            sox_per_gal=0.03,
            nox_per_gal=0.85,
            pm_per_gal=0.05,
        )
        data = factor.to_dict()
        assert data["fuel_type"] == "DIESEL"
        assert data["co2_per_gal"] == 22.38

    def test_emission_factor_from_dict(self):
        """Create emission factor from dictionary."""
        data = {
            "fuel_type": "DIESEL",
            "co2_per_gal": 22.38,
            "sox_per_gal": 0.03,
            "nox_per_gal": 0.85,
            "pm_per_gal": 0.05,
        }
        factor = EmissionFactor.from_dict(data)
        assert factor.fuel_type == FuelType.DIESEL
        assert factor.co2_per_gal == 22.38


# ============================================================================ #
# Carbon Footprint Tests
# ============================================================================ #

class TestCarbonFootprint:
    """Test carbon footprint creation and validation."""

    def test_create_carbon_footprint(self):
        """Create a valid carbon footprint."""
        footprint = CarbonFootprint(
            total_co2_lb=1000.0,
            total_sox_lb=10.0,
            total_nox_lb=50.0,
            total_pm_lb=5.0,
            efficiency_metric=75.0,
        )
        assert footprint.total_co2_lb == 1000.0
        assert footprint.total_sox_lb == 10.0
        assert footprint.total_nox_lb == 50.0
        assert footprint.total_pm_lb == 5.0
        assert footprint.efficiency_metric == 75.0

    def test_carbon_footprint_validation_efficiency_too_high(self):
        """Efficiency metric > 100 should raise ValueError."""
        with pytest.raises(ValueError, match="efficiency_metric must be <= 100"):
            CarbonFootprint(
                total_co2_lb=1000.0,
                total_sox_lb=10.0,
                total_nox_lb=50.0,
                total_pm_lb=5.0,
                efficiency_metric=101.0,
            )


# ============================================================================ #
# Waste Record Tests
# ============================================================================ #

class TestWasteRecord:
    """Test waste record creation and validation."""

    def test_create_waste_record(self):
        """Create a valid waste record."""
        record = WasteRecord(
            waste_type=WasteType.OILY_BILGE,
            quantity_lb=50.0,
            disposal_method=DisposalMethod.PORT_FACILITY,
            location_ns=T0,
            certification="USCG_CERT_001",
        )
        assert record.waste_type == WasteType.OILY_BILGE
        assert record.quantity_lb == 50.0
        assert record.disposal_method == DisposalMethod.PORT_FACILITY
        assert record.location_ns == T0
        assert record.certification == "USCG_CERT_001"

    def test_waste_record_is_compliant(self):
        """Check if waste disposal is compliant."""
        # Compliant methods
        for method in [DisposalMethod.PORT_FACILITY, DisposalMethod.INCINERATOR, DisposalMethod.RETAINED]:
            record = WasteRecord(
                waste_type=WasteType.GARBAGE,
                quantity_lb=10.0,
                disposal_method=method,
                location_ns=T0,
            )
            assert record.is_compliant()

        # Non-compliant method
        record = WasteRecord(
            waste_type=WasteType.GARBAGE,
            quantity_lb=10.0,
            disposal_method=DisposalMethod.OVERBOARD_LEGAL,
            location_ns=T0,
        )
        assert not record.is_compliant()


# ============================================================================ #
# Bycatch Event Tests
# ============================================================================ #

class TestBycatchEvent:
    """Test bycatch event creation and validation."""

    def test_create_bycatch_event(self):
        """Create a valid bycatch event."""
        event = BycatchEvent(
            species="Salmon",
            quantity_lb=5.0,
            disposition=BycatchDisposition.RELEASED_ALIVE,
            release_condition="Good",
            location_ns=T0,
        )
        assert event.species == "Salmon"
        assert event.quantity_lb == 5.0
        assert event.disposition == BycatchDisposition.RELEASED_ALIVE
        assert event.release_condition == "Good"
        assert event.location_ns == T0

    def test_bycatch_event_validation_empty_species(self):
        """Empty species should raise ValueError."""
        with pytest.raises(ValueError, match="species must be a non-empty string"):
            BycatchEvent(
                species="",
                quantity_lb=5.0,
                disposition=BycatchDisposition.RELEASED_ALIVE,
            )

    def test_bycatch_event_is_survival(self):
        """Check if bycatch resulted in survival."""
        # Survival
        event = BycatchEvent(
            species="Salmon",
            quantity_lb=5.0,
            disposition=BycatchDisposition.RELEASED_ALIVE,
            location_ns=T0,
        )
        assert event.is_survival()

        # No survival
        event = BycatchEvent(
            species="Salmon",
            quantity_lb=5.0,
            disposition=BycatchDisposition.DISCARDED,
            location_ns=T0,
        )
        assert not event.is_survival()


# ============================================================================ #
# Sustainability Metric Tests
# ============================================================================ #

class TestSustainabilityMetric:
    """Test sustainability metric creation and validation."""

    def test_create_sustainability_metric(self):
        """Create a valid sustainability metric."""
        metric = SustainabilityMetric(
            metric_name="fuel_efficiency",
            value=20.0,
            unit="nm/gal",
            target=25.0,
            threshold=15.0,
        )
        assert metric.metric_name == "fuel_efficiency"
        assert metric.value == 20.0
        assert metric.unit == "nm/gal"
        assert metric.target == 25.0
        assert metric.threshold == 15.0

    def test_sustainability_metric_validation_empty_name(self):
        """Empty metric name should raise ValueError."""
        with pytest.raises(ValueError, match="metric_name must be a non-empty string"):
            SustainabilityMetric(
                metric_name="",
                value=20.0,
                unit="nm/gal",
                target=25.0,
                threshold=15.0,
            )

    def test_sustainability_metric_is_at_target(self):
        """Check if metric meets target."""
        metric = SustainabilityMetric(
            metric_name="fuel_efficiency_nm_per_gal",
            value=20.0,
            unit="nm/gal",
            target=15.0,
            threshold=10.0,
        )
        assert metric.is_at_target()

        metric.value = 10.0
        assert not metric.is_at_target()

    def test_sustainability_metric_is_threshold_exceeded(self):
        """Check if threshold is exceeded."""
        metric = SustainabilityMetric(
            metric_name="fuel_efficiency_nm_per_gal",
            value=20.0,
            unit="nm/gal",
            target=25.0,
            threshold=15.0,
        )
        assert not metric.is_threshold_exceeded()

        metric.value = 10.0
        assert metric.is_threshold_exceeded()


# ============================================================================ #
# Environmental Stewardship Tests
# ============================================================================ #

class TestEnvironmentalStewardship:
    """Test environmental stewardship system functionality."""

    def test_create_stewardship(self):
        """Create a valid environmental stewardship system."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            assert stewardship.vessel_id == "US-AK-FVEILEEN-51"
            assert stewardship.data_dir == Path(tmpdir)

    def test_stewardship_validation_empty_vessel_id(self):
        """Empty vessel_id should raise ValueError."""
        with pytest.raises(ValueError, match="vessel_id must be a non-empty string"):
            EnvironmentalStewardship(vessel_id="")

    def test_log_fuel_consumption(self):
        """Log fuel consumption event."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            record = stewardship.log_fuel_consumption(
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.5,
                source="main_engine",
                location_lat=58.5,
                location_lon=-157.0,
                engine_hours=1250.5,
            )
            assert record.fuel_type == FuelType.DIESEL
            assert record.quantity_gal == 10.5
            assert len(stewardship._fuel_records) == 1

    def test_log_fuel_consumption_multiple_fuels(self):
        """Log multiple fuel types."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.0,
                source="main_engine",
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.BIODIESEL_B20,
                quantity_gal=5.0,
                source="generator",
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.LNG,
                quantity_gal=15.0,
                source="aux_engine",
            )
            assert len(stewardship._fuel_records) == 3

    def test_calculate_emissions(self):
        """Calculate emissions from fuel records."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.0,
                source="main_engine",
            )
            carbon = stewardship.calculate_emissions()
            assert carbon.total_co2_lb == pytest.approx(223.8, rel=1e-3)
            assert carbon.total_sox_lb == pytest.approx(0.3, rel=1e-3)
            assert carbon.total_nox_lb == pytest.approx(8.5, rel=1e-3)
            assert carbon.total_pm_lb == pytest.approx(0.5, rel=1e-3)

    def test_get_carbon_footprint(self):
        """Get current carbon footprint."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.0,
                source="main_engine",
            )
            footprint = stewardship.get_carbon_footprint()
            assert footprint.total_co2_lb == pytest.approx(223.8, rel=1e-3)
            assert footprint.efficiency_metric > 0

    def test_log_waste_disposal(self):
        """Log waste disposal event."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            record = stewardship.log_waste_disposal(
                waste_type=WasteType.OILY_BILGE,
                quantity_lb=50.0,
                disposal_method=DisposalMethod.PORT_FACILITY,
                certification="USCG_CERT_001",
            )
            assert record.waste_type == WasteType.OILY_BILGE
            assert record.quantity_lb == 50.0
            assert record.disposal_method == DisposalMethod.PORT_FACILITY
            assert len(stewardship._waste_records) == 1

    def test_get_waste_records(self):
        """Get waste records with filtering."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_waste_disposal(
                waste_type=WasteType.OILY_BILGE,
                quantity_lb=50.0,
                disposal_method=DisposalMethod.PORT_FACILITY,
            )
            stewardship.log_waste_disposal(
                waste_type=WasteType.GARBAGE,
                quantity_lb=20.0,
                disposal_method=DisposalMethod.INCINERATOR,
            )
            stewardship.log_waste_disposal(
                waste_type=WasteType.OILY_BILGE,
                quantity_lb=30.0,
                disposal_method=DisposalMethod.PORT_FACILITY,
            )

            all_waste = stewardship.get_waste_records()
            assert len(all_waste) == 3

            oily_bilge = stewardship.get_waste_records(waste_type=WasteType.OILY_BILGE)
            assert len(oily_bilge) == 2

    def test_log_bycatch_event(self):
        """Log bycatch event."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            event = stewardship.log_bycatch_event(
                species="Salmon",
                quantity_lb=5.0,
                disposition=BycatchDisposition.RELEASED_ALIVE,
                release_condition="Good",
            )
            assert event.species == "Salmon"
            assert event.quantity_lb == 5.0
            assert event.disposition == BycatchDisposition.RELEASED_ALIVE
            assert len(stewardship._bycatch_events) == 1

    def test_get_bycatch_summary(self):
        """Get bycatch summary statistics."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_bycatch_event(
                species="Salmon",
                quantity_lb=5.0,
                disposition=BycatchDisposition.RELEASED_ALIVE,
            )
            stewardship.log_bycatch_event(
                species="Cod",
                quantity_lb=3.0,
                disposition=BycatchDisposition.RELEASED_INJURED,
            )
            stewardship.log_bycatch_event(
                species="Halibut",
                quantity_lb=2.0,
                disposition=BycatchDisposition.DISCARDED,
            )

            summary = stewardship.get_bycatch_summary()
            assert summary["total_bycatch_lb"] == 10.0
            assert summary["released_alive_lb"] == 5.0
            assert summary["released_injured_lb"] == 3.0
            assert summary["discarded_lb"] == 2.0
            assert summary["retained_lb"] == 0.0
            assert summary["survival_rate_percent"] == 50.0
            assert "by_species" in summary

    def test_log_catch(self):
        """Log catch data for bycatch ratio."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_catch(1000.0)
            stewardship.log_catch(500.0)
            assert stewardship._total_catch_lb == 1500.0

    def test_log_distance(self):
        """Log distance for efficiency metrics."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_distance(10.0)
            stewardship.log_distance(15.0)
            assert stewardship._total_distance_nm == 25.0

    def test_calculate_sustainability_metrics(self):
        """Calculate all sustainability metrics."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.0,
                source="main_engine",
            )
            stewardship.log_distance(200.0)
            stewardship.log_catch(1000.0)
            stewardship.log_waste_disposal(
                waste_type=WasteType.GARBAGE,
                quantity_lb=50.0,
                disposal_method=DisposalMethod.PORT_FACILITY,
            )

            metrics = stewardship.calculate_sustainability_metrics()
            assert "fuel_efficiency_nm_per_gal" in metrics
            assert "carbon_intensity_lb_per_nm" in metrics
            assert "bycatch_ratio_percent" in metrics
            assert "waste_compliance_percent" in metrics

    def test_get_fuel_efficiency(self):
        """Get current fuel efficiency."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.0,
                source="main_engine",
            )
            stewardship.log_distance(200.0)
            efficiency = stewardship.get_fuel_efficiency()
            assert efficiency == 20.0

    def test_get_emission_intensity(self):
        """Get current carbon emission intensity."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.0,
                source="main_engine",
            )
            stewardship.log_distance(200.0)
            intensity = stewardship.get_emission_intensity()
            assert intensity == pytest.approx(1.119, rel=1e-3)

    def test_get_sustainability_score(self):
        """Get overall sustainability score."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.0,
                source="main_engine",
            )
            stewardship.log_distance(200.0)
            stewardship.log_catch(1000.0)
            stewardship.log_waste_disposal(
                waste_type=WasteType.GARBAGE,
                quantity_lb=50.0,
                disposal_method=DisposalMethod.PORT_FACILITY,
            )

            score = stewardship.get_sustainability_score()
            assert 0 <= score <= 100

    def test_get_alerts_high_emissions(self):
        """Generate high emissions alert."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            # Log initial fuel to establish baseline
            for _ in range(10):
                stewardship.log_fuel_consumption(
                    fuel_type=FuelType.DIESEL,
                    quantity_gal=10.0,
                    source="main_engine",
                )
            # Log high consumption
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.DIESEL,
                quantity_gal=15.0,
                source="main_engine",
            )

            alerts = stewardship.get_alerts()
            high_emission_alerts = [a for a in alerts if a["code"] == "HIGH_EMISSIONS"]
            assert len(high_emission_alerts) > 0

    def test_get_alerts_low_efficiency(self):
        """Generate low fuel efficiency alert."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.0,
                source="main_engine",
            )
            stewardship.log_distance(100.0)  # 10 nm/gal (below threshold)

            alerts = stewardship.get_alerts()
            low_eff_alerts = [a for a in alerts if a["code"] == "LOW_FUEL_EFFICIENCY"]
            assert len(low_eff_alerts) > 0

    def test_get_alerts_high_bycatch_ratio(self):
        """Generate high bycatch ratio alert."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_catch(100.0)
            stewardship.log_bycatch_event(
                species="Salmon",
                quantity_lb=6.0,  # 6% of catch (above threshold)
                disposition=BycatchDisposition.RELEASED_ALIVE,
            )

            alerts = stewardship.get_alerts()
            bycatch_alerts = [a for a in alerts if a["code"] == "HIGH_BYCATCH_RATIO"]
            assert len(bycatch_alerts) > 0

    def test_get_alerts_waste_noncompliance(self):
        """Generate waste noncompliance alert."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            # Log compliant waste
            stewardship.log_waste_disposal(
                waste_type=WasteType.GARBAGE,
                quantity_lb=50.0,
                disposal_method=DisposalMethod.PORT_FACILITY,
            )
            # Log noncompliant waste (>10% improper)
            stewardship.log_waste_disposal(
                waste_type=WasteType.GARBAGE,
                quantity_lb=10.0,
                disposal_method=DisposalMethod.OVERBOARD_LEGAL,
            )

            alerts = stewardship.get_alerts()
            waste_alerts = [a for a in alerts if a["code"] == "WASTE_NONCOMPLIANCE"]
            assert len(waste_alerts) > 0

    def test_get_watcher_frame(self):
        """Get environmental data for watcher evaluation."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.0,
                source="main_engine",
            )
            stewardship.log_distance(200.0)
            stewardship.log_catch(1000.0)
            stewardship.log_waste_disposal(
                waste_type=WasteType.GARBAGE,
                quantity_lb=50.0,
                disposal_method=DisposalMethod.PORT_FACILITY,
            )

            frame = stewardship.get_watcher_frame()
            assert "fuel_efficiency_nm_per_gal" in frame
            assert "carbon_intensity_lb_per_nm" in frame
            assert "bycatch_ratio_percent" in frame
            assert "waste_compliance_percent" in frame
            assert "sustainability_score" in frame

    def test_to_dict(self):
        """Convert to dictionary for snapshot serialization."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.0,
                source="main_engine",
            )
            stewardship.log_distance(200.0)
            stewardship.log_catch(1000.0)
            stewardship.log_waste_disposal(
                waste_type=WasteType.GARBAGE,
                quantity_lb=50.0,
                disposal_method=DisposalMethod.PORT_FACILITY,
            )

            data = stewardship.to_dict()
            assert data["vessel_id"] == "US-AK-FVEILEEN-51"
            assert "carbon_footprint" in data
            assert "bycatch_summary" in data
            assert "sustainability_metrics" in data
            assert "sustainability_score" in data

    def test_persistence_fuel_records(self):
        """Test fuel record persistence."""
        with TemporaryDirectory() as tmpdir:
            stewardship1 = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship1.log_fuel_consumption(
                fuel_type=FuelType.DIESEL,
                quantity_gal=10.0,
                source="main_engine",
            )

            # Create new instance - should load persisted data
            stewardship2 = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            assert len(stewardship2._fuel_records) == 1
            assert stewardship2._fuel_records[0].quantity_gal == 10.0

    def test_persistence_waste_records(self):
        """Test waste record persistence."""
        with TemporaryDirectory() as tmpdir:
            stewardship1 = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship1.log_waste_disposal(
                waste_type=WasteType.GARBAGE,
                quantity_lb=50.0,
                disposal_method=DisposalMethod.PORT_FACILITY,
            )

            # Create new instance - should load persisted data
            stewardship2 = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            assert len(stewardship2._waste_records) == 1
            assert stewardship2._waste_records[0].quantity_lb == 50.0

    def test_persistence_bycatch_events(self):
        """Test bycatch event persistence."""
        with TemporaryDirectory() as tmpdir:
            stewardship1 = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship1.log_bycatch_event(
                species="Salmon",
                quantity_lb=5.0,
                disposition=BycatchDisposition.RELEASED_ALIVE,
            )

            # Create new instance - should load persisted data
            stewardship2 = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            assert len(stewardship2._bycatch_events) == 1
            assert stewardship2._bycatch_events[0].quantity_lb == 5.0

    def test_emission_factors_constants(self):
        """Test emission factors constants."""
        assert "DIESEL" in EMISSION_FACTORS
        assert "BIODIESEL_B20" in EMISSION_FACTORS
        assert "LNG" in EMISSION_FACTORS
        assert "ELECTRIC" in EMISSION_FACTORS

        # Check diesel factors
        diesel_factors = EMISSION_FACTORS["DIESEL"]
        assert diesel_factors["co2_per_gal"] == 22.38
        assert diesel_factors["sox_per_gal"] == 0.03
        assert diesel_factors["nox_per_gal"] == 0.85
        assert diesel_factors["pm_per_gal"] == 0.05

    def test_sustainability_targets_constants(self):
        """Test sustainability targets constants."""
        assert "fuel_efficiency_nm_per_gal" in SUSTAINABILITY_TARGETS
        assert "carbon_intensity_lb_per_nm" in SUSTAINABILITY_TARGETS
        assert "bycatch_ratio_percent" in SUSTAINABILITY_TARGETS
        assert "waste_compliance_percent" in SUSTAINABILITY_TARGETS

    def test_alert_constants(self):
        """Test alert threshold constants."""
        assert ALERT_EMISSIONS_BASELINE_PCT == 10.0
        assert ALERT_EFFICIENCY_MIN_NM_PER_GAL == 15.0
        assert ALERT_BYCATCH_RATIO_MAX_PCT == 5.0
        assert ALERT_WASTE_NONCOMPLIANCE_MAX_PCT == 10.0

    def test_electric_fuel_zero_emissions(self):
        """Test electric fuel has zero emissions."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.ELECTRIC,
                quantity_gal=10.0,
                source="electric_motor",
            )

            carbon = stewardship.get_carbon_footprint()
            assert carbon.total_co2_lb == 0.0
            assert carbon.total_sox_lb == 0.0
            assert carbon.total_nox_lb == 0.0
            assert carbon.total_pm_lb == 0.0

    def test_lng_fuel_zero_sox_and_pm(self):
        """Test LNG fuel has zero SOx and PM."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.LNG,
                quantity_gal=10.0,
                source="lng_engine",
            )

            carbon = stewardship.get_carbon_footprint()
            assert carbon.total_sox_lb == 0.0
            assert carbon.total_pm_lb == 0.0
            assert carbon.total_co2_lb > 0.0
            assert carbon.total_nox_lb > 0.0

    def test_biodiesel_reduced_emissions(self):
        """Test biodiesel has reduced emissions."""
        with TemporaryDirectory() as tmpdir:
            stewardship = EnvironmentalStewardship(
                vessel_id="US-AK-FVEILEEN-51",
                data_dir=tmpdir,
            )
            stewardship.log_fuel_consumption(
                fuel_type=FuelType.BIODIESEL_B20,
                quantity_gal=10.0,
                source="main_engine",
            )

            carbon = stewardship.get_carbon_footprint()
            # B20 should have 20% lower CO2 than diesel
            assert carbon.total_co2_lb == pytest.approx(179.0, rel=1e-3)
