"""Environmental Stewardship system for the AELMA twin.

Tracks fuel efficiency, carbon footprint, waste management, bycatch mitigation,
and sustainability metrics for commercial fishing vessels.

The system maintains comprehensive records of:
- Fuel consumption by type and engine
- Carbon emissions (CO2, SOx, NOx, PM) calculated from fuel use
- Waste disposal tracking with regulatory compliance
- Bycatch events with disposition tracking
- Sustainability metrics and scoring

Alert thresholds:
- HIGH EMISSIONS: >10% above baseline
- LOW EFFICIENCY: <15 nm/gal
- BYCATCH RATIO: >5% of total catch
- WASTE NONCOMPLIANCE: >10% improper disposal
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# Emission factors (lb per gallon) for different fuel types
# Source: EPA and IMO regulatory guidelines
EMISSION_FACTORS = {
    "DIESEL": {
        "co2_per_gal": 22.38,
        "sox_per_gal": 0.03,  # Ultra-low sulfur diesel
        "nox_per_gal": 0.85,  # Tier 3 engine
        "pm_per_gal": 0.05,
    },
    "BIODIESEL_B20": {
        "co2_per_gal": 17.90,  # 20% reduction
        "sox_per_gal": 0.02,
        "nox_per_gal": 0.82,
        "pm_per_gal": 0.04,
    },
    "BIODIESEL_B100": {
        "co2_per_gal": 11.19,  # 50% reduction
        "sox_per_gal": 0.01,
        "nox_per_gal": 0.78,
        "pm_per_gal": 0.02,
    },
    "LNG": {
        "co2_per_gal": 14.67,  # LNG equivalent
        "sox_per_gal": 0.00,  # Zero sulfur
        "nox_per_gal": 0.45,  # 50% reduction
        "pm_per_gal": 0.00,  # Zero particulate
    },
    "ELECTRIC": {
        "co2_per_gal": 0.00,  # Zero direct emissions
        "sox_per_gal": 0.00,
        "nox_per_gal": 0.00,
        "pm_per_gal": 0.00,
    },
}

# Sustainability targets and thresholds
SUSTAINABILITY_TARGETS = {
    "fuel_efficiency_nm_per_gal": {"target": 20.0, "threshold": 15.0},
    "carbon_intensity_lb_per_nm": {"target": 1.2, "threshold": 1.5},
    "bycatch_ratio_percent": {"target": 2.0, "threshold": 5.0},
    "waste_compliance_percent": {"target": 100.0, "threshold": 90.0},
}

# Alert thresholds
ALERT_EMISSIONS_BASELINE_PCT = 10.0  # >10% above baseline
ALERT_EFFICIENCY_MIN_NM_PER_GAL = 15.0
ALERT_BYCATCH_RATIO_MAX_PCT = 5.0
ALERT_WASTE_NONCOMPLIANCE_MAX_PCT = 10.0


class FuelType(str, Enum):
    """Fuel types supported by the system."""

    DIESEL = "DIESEL"
    BIODIESEL_B20 = "BIODIESEL_B20"
    BIODIESEL_B100 = "BIODIESEL_B100"
    LNG = "LNG"
    ELECTRIC = "ELECTRIC"


class WasteType(str, Enum):
    """Waste types for tracking and disposal."""

    OILY_BILGE = "OILY_BILGE"
    GARBAGE = "GARBAGE"
    SEWAGE = "SEWAGE"
    CHEMICAL = "CHEMICAL"
    FISHING_WASTE = "FISHING_WASTE"
    PLASTIC = "PLASTIC"


class DisposalMethod(str, Enum):
    """Waste disposal methods with regulatory compliance."""

    PORT_FACILITY = "PORT_FACILITY"  # Shore-side disposal
    INCINERATOR = "INCINERATOR"  # Shipboard incineration
    OVERBOARD_LEGAL = "OVERBOARD_LEGAL"  # Legal discharge (>3nm, >25nm for some)
    RETAINED = "RETAINED"  # Held for disposal
    GEAR_LOSS = "GEAR_LOSS"  # Accidental loss


class BycatchDisposition(str, Enum):
    """Bycatch disposition options."""

    RELEASED_ALIVE = "RELEASED_ALIVE"
    RELEASED_INJURED = "RELEASED_INJURED"
    RETAINED = "RETAINED"
    DISCARDED = "DISCARDED"


class AlertSeverity(str, Enum):
    """Environmental alert severity levels."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FuelRecord:
    """A recorded fuel consumption event.

    Attributes:
        timestamp_ns: Event timestamp (nanoseconds since epoch)
        fuel_type: Type of fuel consumed
        quantity_gal: Fuel quantity in gallons
        source: Fuel source/engine identifier
        location_lat: Latitude at time of consumption
        location_lon: Longitude at time of consumption
        engine_hours: Engine hours at time of consumption
    """

    timestamp_ns: int
    fuel_type: FuelType
    quantity_gal: float
    source: str
    location_lat: float | None = None
    location_lon: float | None = None
    engine_hours: float | None = None

    def __post_init__(self):
        """Validate fuel record data."""
        if not isinstance(self.timestamp_ns, int):
            raise ValueError("timestamp_ns must be an integer")
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be non-negative")
        if isinstance(self.fuel_type, str):
            self.fuel_type = FuelType(self.fuel_type)
        if not isinstance(self.quantity_gal, (int, float)):
            raise ValueError("quantity_gal must be a number")
        if self.quantity_gal < 0:
            raise ValueError("quantity_gal must be non-negative")
        if not isinstance(self.source, str) or not self.source:
            raise ValueError("source must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp_ns": self.timestamp_ns,
            "fuel_type": self.fuel_type.value,
            "quantity_gal": self.quantity_gal,
            "source": self.source,
            "location_lat": self.location_lat,
            "location_lon": self.location_lon,
            "engine_hours": self.engine_hours,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FuelRecord:
        """Create FuelRecord from dictionary."""
        return cls(
            timestamp_ns=data["timestamp_ns"],
            fuel_type=FuelType(data["fuel_type"]),
            quantity_gal=data["quantity_gal"],
            source=data["source"],
            location_lat=data.get("location_lat"),
            location_lon=data.get("location_lon"),
            engine_hours=data.get("engine_hours"),
        )


@dataclass
class EmissionFactor:
    """Emission factors for a fuel type.

    Attributes:
        fuel_type: Type of fuel
        co2_per_gal: CO2 emissions per gallon (lb)
        sox_per_gal: SOx emissions per gallon (lb)
        nox_per_gal: NOx emissions per gallon (lb)
        pm_per_gal: Particulate matter per gallon (lb)
    """

    fuel_type: FuelType
    co2_per_gal: float
    sox_per_gal: float
    nox_per_gal: float
    pm_per_gal: float

    def __post_init__(self):
        """Validate emission factors."""
        if isinstance(self.fuel_type, str):
            self.fuel_type = FuelType(self.fuel_type)
        for attr in ["co2_per_gal", "sox_per_gal", "nox_per_gal", "pm_per_gal"]:
            value = getattr(self, attr)
            if not isinstance(value, (int, float)):
                raise ValueError(f"{attr} must be a number")
            if value < 0:
                raise ValueError(f"{attr} must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "fuel_type": self.fuel_type.value,
            "co2_per_gal": self.co2_per_gal,
            "sox_per_gal": self.sox_per_gal,
            "nox_per_gal": self.nox_per_gal,
            "pm_per_gal": self.pm_per_gal,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmissionFactor:
        """Create EmissionFactor from dictionary."""
        return cls(
            fuel_type=FuelType(data["fuel_type"]),
            co2_per_gal=data["co2_per_gal"],
            sox_per_gal=data["sox_per_gal"],
            nox_per_gal=data["nox_per_gal"],
            pm_per_gal=data["pm_per_gal"],
        )


@dataclass
class CarbonFootprint:
    """Aggregate carbon footprint metrics.

    Attributes:
        total_co2_lb: Total CO2 emissions (lb)
        total_sox_lb: Total SOx emissions (lb)
        total_nox_lb: Total NOx emissions (lb)
        total_pm_lb: Total particulate matter (lb)
        efficiency_metric: Overall efficiency score (0-100)
    """

    total_co2_lb: float
    total_sox_lb: float
    total_nox_lb: float
    total_pm_lb: float
    efficiency_metric: float = 0.0

    def __post_init__(self):
        """Validate carbon footprint data."""
        for attr in ["total_co2_lb", "total_sox_lb", "total_nox_lb", "total_pm_lb", "efficiency_metric"]:
            value = getattr(self, attr)
            if not isinstance(value, (int, float)):
                raise ValueError(f"{attr} must be a number")
            if value < 0:
                raise ValueError(f"{attr} must be non-negative")
        if self.efficiency_metric > 100:
            raise ValueError("efficiency_metric must be <= 100")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_co2_lb": self.total_co2_lb,
            "total_sox_lb": self.total_sox_lb,
            "total_nox_lb": self.total_nox_lb,
            "total_pm_lb": self.total_pm_lb,
            "efficiency_metric": self.efficiency_metric,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CarbonFootprint:
        """Create CarbonFootprint from dictionary."""
        return cls(
            total_co2_lb=data["total_co2_lb"],
            total_sox_lb=data["total_sox_lb"],
            total_nox_lb=data["total_nox_lb"],
            total_pm_lb=data["total_pm_lb"],
            efficiency_metric=data.get("efficiency_metric", 0.0),
        )


@dataclass
class WasteRecord:
    """A recorded waste disposal event.

    Attributes:
        waste_type: Type of waste
        quantity_lb: Waste quantity in pounds
        disposal_method: Disposal method used
        location_ns: Location timestamp (nanoseconds)
        certification: Regulatory certification (if applicable)
    """

    waste_type: WasteType
    quantity_lb: float
    disposal_method: DisposalMethod
    location_ns: int
    certification: str | None = None

    def __post_init__(self):
        """Validate waste record data."""
        if isinstance(self.waste_type, str):
            self.waste_type = WasteType(self.waste_type)
        if isinstance(self.disposal_method, str):
            self.disposal_method = DisposalMethod(self.disposal_method)
        if not isinstance(self.quantity_lb, (int, float)):
            raise ValueError("quantity_lb must be a number")
        if self.quantity_lb < 0:
            raise ValueError("quantity_lb must be non-negative")
        if not isinstance(self.location_ns, int):
            raise ValueError("location_ns must be an integer")
        if self.location_ns < 0:
            raise ValueError("location_ns must be non-negative")

    def is_compliant(self) -> bool:
        """Check if disposal method is compliant with regulations."""
        return self.disposal_method in {
            DisposalMethod.PORT_FACILITY,
            DisposalMethod.INCINERATOR,
            DisposalMethod.RETAINED,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "waste_type": self.waste_type.value,
            "quantity_lb": self.quantity_lb,
            "disposal_method": self.disposal_method.value,
            "location_ns": self.location_ns,
            "certification": self.certification,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WasteRecord:
        """Create WasteRecord from dictionary."""
        return cls(
            waste_type=WasteType(data["waste_type"]),
            quantity_lb=data["quantity_lb"],
            disposal_method=DisposalMethod(data["disposal_method"]),
            location_ns=data["location_ns"],
            certification=data.get("certification"),
        )


@dataclass
class BycatchEvent:
    """A recorded bycatch event.

    Attributes:
        species: Species identifier
        quantity_lb: Quantity in pounds
        disposition: Disposition of the bycatch
        release_condition: Condition if released (optional)
        location_ns: Location timestamp (nanoseconds)
    """

    species: str
    quantity_lb: float
    disposition: BycatchDisposition
    release_condition: str | None = None
    location_ns: int = 0

    def __post_init__(self):
        """Validate bycatch event data."""
        if not isinstance(self.species, str) or not self.species:
            raise ValueError("species must be a non-empty string")
        if not isinstance(self.quantity_lb, (int, float)):
            raise ValueError("quantity_lb must be a number")
        if self.quantity_lb < 0:
            raise ValueError("quantity_lb must be non-negative")
        if isinstance(self.disposition, str):
            self.disposition = BycatchDisposition(self.disposition)
        if not isinstance(self.location_ns, int):
            raise ValueError("location_ns must be an integer")
        if self.location_ns < 0:
            raise ValueError("location_ns must be non-negative")

    def is_survival(self) -> bool:
        """Check if bycatch resulted in survival."""
        return self.disposition == BycatchDisposition.RELEASED_ALIVE

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "species": self.species,
            "quantity_lb": self.quantity_lb,
            "disposition": self.disposition.value,
            "release_condition": self.release_condition,
            "location_ns": self.location_ns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BycatchEvent:
        """Create BycatchEvent from dictionary."""
        return cls(
            species=data["species"],
            quantity_lb=data["quantity_lb"],
            disposition=BycatchDisposition(data["disposition"]),
            release_condition=data.get("release_condition"),
            location_ns=data.get("location_ns", 0),
        )


@dataclass
class SustainabilityMetric:
    """A sustainability metric with target and threshold.

    Attributes:
        metric_name: Name of the metric
        value: Current value
        unit: Unit of measurement
        target: Target value
        threshold: Alert threshold value
    """

    metric_name: str
    value: float
    unit: str
    target: float
    threshold: float

    def __post_init__(self):
        """Validate sustainability metric."""
        if not isinstance(self.metric_name, str) or not self.metric_name:
            raise ValueError("metric_name must be a non-empty string")
        if not isinstance(self.unit, str) or not self.unit:
            raise ValueError("unit must be a non-empty string")
        for attr in ["value", "target", "threshold"]:
            value = getattr(self, attr)
            if not isinstance(value, (int, float)):
                raise ValueError(f"{attr} must be a number")

    def is_at_target(self) -> bool:
        """Check if metric meets target."""
        return self.value >= self.target if self.metric_name in [
            "fuel_efficiency_nm_per_gal",
            "waste_compliance_percent",
        ] else self.value <= self.target

    def is_threshold_exceeded(self) -> bool:
        """Check if threshold is exceeded."""
        return self.value < self.threshold if self.metric_name in [
            "fuel_efficiency_nm_per_gal",
            "waste_compliance_percent",
        ] else self.value > self.threshold

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "unit": self.unit,
            "target": self.target,
            "threshold": self.threshold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SustainabilityMetric:
        """Create SustainabilityMetric from dictionary."""
        return cls(
            metric_name=data["metric_name"],
            value=data["value"],
            unit=data["unit"],
            target=data["target"],
            threshold=data["threshold"],
        )


class EnvironmentalStewardship:
    """Environmental stewardship tracking system.

    Tracks fuel consumption, emissions, waste disposal, bycatch events,
    and calculates sustainability metrics for a fishing vessel.

    Attributes:
        vessel_id: Vessel identifier
        data_dir: Directory for data persistence
    """

    def __init__(
        self,
        vessel_id: str,
        data_dir: str | Path = "environmental_data",
    ) -> None:
        """Initialize the environmental stewardship system.

        Args:
            vessel_id: Vessel identifier
            data_dir: Directory for data persistence
        """
        if not isinstance(vessel_id, str) or not vessel_id:
            raise ValueError("vessel_id must be a non-empty string")

        self.vessel_id = vessel_id
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Data storage
        self._fuel_records: list[FuelRecord] = []
        self._waste_records: list[WasteRecord] = []
        self._bycatch_events: list[BycatchEvent] = []
        self._sustainability_metrics: dict[str, SustainabilityMetric] = {}

        # Baseline emissions (for alert calculation)
        self._baseline_co2_lb: float = 0.0
        self._baseline_calculated: bool = False

        # Total catch tracking (for bycatch ratio)
        self._total_catch_lb: float = 0.0

        # Total distance tracking (for efficiency metrics)
        self._total_distance_nm: float = 0.0

        # Load existing data
        self._load_data()

    def _load_data(self) -> None:
        """Load data from JSONL files."""
        # Load fuel records
        fuel_path = self.data_dir / "fuel.jsonl"
        if fuel_path.exists():
            with open(fuel_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self._fuel_records.append(FuelRecord.from_dict(json.loads(line)))

        # Load waste records
        waste_path = self.data_dir / "waste.jsonl"
        if waste_path.exists():
            with open(waste_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self._waste_records.append(WasteRecord.from_dict(json.loads(line)))

        # Load bycatch events
        bycatch_path = self.data_dir / "bycatch.jsonl"
        if bycatch_path.exists():
            with open(bycatch_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self._bycatch_events.append(BycatchEvent.from_dict(json.loads(line)))

        # Load sustainability metrics
        metrics_path = self.data_dir / "metrics.jsonl"
        if metrics_path.exists():
            with open(metrics_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        metric = SustainabilityMetric.from_dict(json.loads(line))
                        self._sustainability_metrics[metric.metric_name] = metric

    def _save_fuel_record(self, record: FuelRecord) -> None:
        """Append a fuel record to the JSONL file."""
        fuel_path = self.data_dir / "fuel.jsonl"
        with open(fuel_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

    def _save_waste_record(self, record: WasteRecord) -> None:
        """Append a waste record to the JSONL file."""
        waste_path = self.data_dir / "waste.jsonl"
        with open(waste_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

    def _save_bycatch_event(self, event: BycatchEvent) -> None:
        """Append a bycatch event to the JSONL file."""
        bycatch_path = self.data_dir / "bycatch.jsonl"
        with open(bycatch_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

    def log_fuel_consumption(
        self,
        fuel_type: FuelType | str,
        quantity_gal: float,
        source: str = "main_engine",
        location_lat: float | None = None,
        location_lon: float | None = None,
        engine_hours: float | None = None,
    ) -> FuelRecord:
        """Log fuel consumption event.

        Args:
            fuel_type: Type of fuel consumed
            quantity_gal: Fuel quantity in gallons
            source: Fuel source/engine identifier
            location_lat: Latitude at time of consumption
            location_lon: Longitude at time of consumption
            engine_hours: Engine hours at time of consumption

        Returns:
            The created FuelRecord
        """
        record = FuelRecord(
            timestamp_ns=time.time_ns(),
            fuel_type=fuel_type,
            quantity_gal=quantity_gal,
            source=source,
            location_lat=location_lat,
            location_lon=location_lon,
            engine_hours=engine_hours,
        )
        self._fuel_records.append(record)
        self._save_fuel_record(record)

        # Calculate baseline if not yet calculated
        if not self._baseline_calculated and len(self._fuel_records) >= 10:
            self._calculate_baseline()

        return record

    def _calculate_baseline(self) -> None:
        """Calculate baseline emissions from first 10 fuel records."""
        if len(self._fuel_records) < 10:
            return

        total_co2 = 0.0
        for record in self._fuel_records[:10]:
            factors = EMISSION_FACTORS.get(record.fuel_type.value, EMISSION_FACTORS["DIESEL"])
            total_co2 += record.quantity_gal * factors["co2_per_gal"]

        self._baseline_co2_lb = total_co2 / 10.0  # Average per record
        self._baseline_calculated = True

    def calculate_emissions(
        self,
        fuel_records: list[FuelRecord] | None = None,
    ) -> CarbonFootprint:
        """Calculate emissions from fuel records.

        Args:
            fuel_records: Optional list of fuel records (uses all if None)

        Returns:
            CarbonFootprint with total emissions
        """
        if fuel_records is None:
            fuel_records = self._fuel_records

        total_co2 = 0.0
        total_sox = 0.0
        total_nox = 0.0
        total_pm = 0.0

        for record in fuel_records:
            factors = EMISSION_FACTORS.get(record.fuel_type.value, EMISSION_FACTORS["DIESEL"])
            total_co2 += record.quantity_gal * factors["co2_per_gal"]
            total_sox += record.quantity_gal * factors["sox_per_gal"]
            total_nox += record.quantity_gal * factors["nox_per_gal"]
            total_pm += record.quantity_gal * factors["pm_per_gal"]

        # Calculate efficiency metric (inverse of total CO2)
        efficiency = 100.0 - min(100.0, total_co2 / 1000.0)

        return CarbonFootprint(
            total_co2_lb=total_co2,
            total_sox_lb=total_sox,
            total_nox_lb=total_nox,
            total_pm_lb=total_pm,
            efficiency_metric=efficiency,
        )

    def get_carbon_footprint(self) -> CarbonFootprint:
        """Get current carbon footprint from all fuel records.

        Returns:
            CarbonFootprint with total emissions
        """
        return self.calculate_emissions()

    def log_waste_disposal(
        self,
        waste_type: WasteType | str,
        quantity_lb: float,
        disposal_method: DisposalMethod | str,
        certification: str | None = None,
    ) -> WasteRecord:
        """Log waste disposal event.

        Args:
            waste_type: Type of waste
            quantity_lb: Waste quantity in pounds
            disposal_method: Disposal method used
            certification: Regulatory certification (if applicable)

        Returns:
            The created WasteRecord
        """
        record = WasteRecord(
            waste_type=waste_type,
            quantity_lb=quantity_lb,
            disposal_method=disposal_method,
            location_ns=time.time_ns(),
            certification=certification,
        )
        self._waste_records.append(record)
        self._save_waste_record(record)
        return record

    def get_waste_records(
        self,
        waste_type: WasteType | None = None,
    ) -> list[WasteRecord]:
        """Get waste records, optionally filtered by type.

        Args:
            waste_type: Optional waste type filter

        Returns:
            List of waste records
        """
        if waste_type is None:
            return list(self._waste_records)

        if isinstance(waste_type, str):
            waste_type = WasteType(waste_type)

        return [r for r in self._waste_records if r.waste_type == waste_type]

    def log_bycatch_event(
        self,
        species: str,
        quantity_lb: float,
        disposition: BycatchDisposition | str,
        release_condition: str | None = None,
    ) -> BycatchEvent:
        """Log bycatch event.

        Args:
            species: Species identifier
            quantity_lb: Quantity in pounds
            disposition: Disposition of the bycatch
            release_condition: Condition if released

        Returns:
            The created BycatchEvent
        """
        event = BycatchEvent(
            species=species,
            quantity_lb=quantity_lb,
            disposition=disposition,
            release_condition=release_condition,
            location_ns=time.time_ns(),
        )
        self._bycatch_events.append(event)
        self._save_bycatch_event(event)
        return event

    def get_bycatch_summary(self) -> dict[str, Any]:
        """Get bycatch summary statistics.

        Returns:
            Dict with bycatch statistics by disposition and species
        """
        total_bycatch = sum(e.quantity_lb for e in self._bycatch_events)
        released_alive = sum(e.quantity_lb for e in self._bycatch_events
                           if e.disposition == BycatchDisposition.RELEASED_ALIVE)
        released_injured = sum(e.quantity_lb for e in self._bycatch_events
                              if e.disposition == BycatchDisposition.RELEASED_INJURED)
        retained = sum(e.quantity_lb for e in self._bycatch_events
                      if e.disposition == BycatchDisposition.RETAINED)
        discarded = sum(e.quantity_lb for e in self._bycatch_events
                       if e.disposition == BycatchDisposition.DISCARDED)

        # Species breakdown
        by_species: dict[str, float] = {}
        for event in self._bycatch_events:
            by_species[event.species] = by_species.get(event.species, 0.0) + event.quantity_lb

        # Survival rate
        survival_rate = (released_alive / total_bycatch * 100) if total_bycatch > 0 else 100.0

        # Bycatch ratio (as percentage of total catch)
        bycatch_ratio = (total_bycatch / self._total_catch_lb * 100) if self._total_catch_lb > 0 else 0.0

        return {
            "total_bycatch_lb": total_bycatch,
            "released_alive_lb": released_alive,
            "released_injured_lb": released_injured,
            "retained_lb": retained,
            "discarded_lb": discarded,
            "by_species": by_species,
            "survival_rate_percent": survival_rate,
            "bycatch_ratio_percent": bycatch_ratio,
        }

    def log_catch(self, weight_lb: float) -> None:
        """Log catch data for bycatch ratio calculation.

        Args:
            weight_lb: Catch weight in pounds
        """
        self._total_catch_lb += weight_lb

    def log_distance(self, distance_nm: float) -> None:
        """Log distance traveled for efficiency metrics.

        Args:
            distance_nm: Distance traveled in nautical miles
        """
        self._total_distance_nm += distance_nm

    def calculate_sustainability_metrics(self) -> dict[str, SustainabilityMetric]:
        """Calculate all sustainability metrics.

        Returns:
            Dict of sustainability metrics by name
        """
        metrics = {}

        # Fuel efficiency (nm/gal)
        total_fuel = sum(r.quantity_gal for r in self._fuel_records)
        fuel_efficiency = (self._total_distance_nm / total_fuel) if total_fuel > 0 else 0.0
        metrics["fuel_efficiency_nm_per_gal"] = SustainabilityMetric(
            metric_name="fuel_efficiency_nm_per_gal",
            value=fuel_efficiency,
            unit="nm/gal",
            target=SUSTAINABILITY_TARGETS["fuel_efficiency_nm_per_gal"]["target"],
            threshold=SUSTAINABILITY_TARGETS["fuel_efficiency_nm_per_gal"]["threshold"],
        )

        # Carbon intensity (lb CO2/nm)
        carbon = self.get_carbon_footprint()
        carbon_intensity = (carbon.total_co2_lb / self._total_distance_nm) if self._total_distance_nm > 0 else 0.0
        metrics["carbon_intensity_lb_per_nm"] = SustainabilityMetric(
            metric_name="carbon_intensity_lb_per_nm",
            value=carbon_intensity,
            unit="lb/nm",
            target=SUSTAINABILITY_TARGETS["carbon_intensity_lb_per_nm"]["target"],
            threshold=SUSTAINABILITY_TARGETS["carbon_intensity_lb_per_nm"]["threshold"],
        )

        # Bycatch ratio
        bycatch_summary = self.get_bycatch_summary()
        bycatch_ratio = bycatch_summary["bycatch_ratio_percent"]
        metrics["bycatch_ratio_percent"] = SustainabilityMetric(
            metric_name="bycatch_ratio_percent",
            value=bycatch_ratio,
            unit="%",
            target=SUSTAINABILITY_TARGETS["bycatch_ratio_percent"]["target"],
            threshold=SUSTAINABILITY_TARGETS["bycatch_ratio_percent"]["threshold"],
        )

        # Waste compliance
        total_waste = sum(r.quantity_lb for r in self._waste_records)
        compliant_waste = sum(r.quantity_lb for r in self._waste_records if r.is_compliant())
        waste_compliance = (compliant_waste / total_waste * 100) if total_waste > 0 else 100.0
        metrics["waste_compliance_percent"] = SustainabilityMetric(
            metric_name="waste_compliance_percent",
            value=waste_compliance,
            unit="%",
            target=SUSTAINABILITY_TARGETS["waste_compliance_percent"]["target"],
            threshold=SUSTAINABILITY_TARGETS["waste_compliance_percent"]["threshold"],
        )

        self._sustainability_metrics = metrics
        return metrics

    def get_fuel_efficiency(self) -> float:
        """Get current fuel efficiency.

        Returns:
            Fuel efficiency in nm/gal
        """
        total_fuel = sum(r.quantity_gal for r in self._fuel_records)
        return (self._total_distance_nm / total_fuel) if total_fuel > 0 else 0.0

    def get_emission_intensity(self) -> float:
        """Get current carbon emission intensity.

        Returns:
            CO2 emissions per nautical mile (lb/nm)
        """
        carbon = self.get_carbon_footprint()
        return (carbon.total_co2_lb / self._total_distance_nm) if self._total_distance_nm > 0 else 0.0

    def get_sustainability_score(self) -> float:
        """Calculate overall sustainability score (0-100).

        Returns:
            Sustainability score
        """
        metrics = self.calculate_sustainability_metrics()

        # Score each metric (0-25 each)
        fuel_score = 25.0 * min(1.0, metrics["fuel_efficiency_nm_per_gal"].value /
                               metrics["fuel_efficiency_nm_per_gal"].target)
        carbon_score = 25.0 * (1.0 - min(1.0, metrics["carbon_intensity_lb_per_nm"].value /
                                 metrics["carbon_intensity_lb_per_nm"].threshold))
        bycatch_score = 25.0 * (1.0 - min(1.0, metrics["bycatch_ratio_percent"].value /
                                  5.0))  # 5% = 0 score
        waste_score = 25.0 * (metrics["waste_compliance_percent"].value / 100.0)

        return fuel_score + carbon_score + bycatch_score + waste_score

    def get_alerts(self) -> list[dict[str, Any]]:
        """Generate environmental alerts based on thresholds.

        Returns:
            List of alert dicts
        """
        alerts = []
        metrics = self.calculate_sustainability_metrics()

        # High emissions alert
        if self._baseline_calculated:
            carbon = self.get_carbon_footprint()
            if carbon.total_co2_lb > self._baseline_co2_lb * (1.0 + ALERT_EMISSIONS_BASELINE_PCT / 100.0):
                alerts.append({
                    "severity": AlertSeverity.HIGH.value,
                    "code": "HIGH_EMISSIONS",
                    "message": f"Emissions {ALERT_EMISSIONS_BASELINE_PCT:.0f}% above baseline",
                    "value": carbon.total_co2_lb,
                    "baseline": self._baseline_co2_lb,
                })

        # Low fuel efficiency alert
        fuel_eff = metrics["fuel_efficiency_nm_per_gal"].value
        if fuel_eff < ALERT_EFFICIENCY_MIN_NM_PER_GAL:
            alerts.append({
                "severity": AlertSeverity.MEDIUM.value,
                "code": "LOW_FUEL_EFFICIENCY",
                "message": f"Fuel efficiency below threshold: {fuel_eff:.1f} nm/gal",
                "value": fuel_eff,
                "threshold": ALERT_EFFICIENCY_MIN_NM_PER_GAL,
            })

        # High bycatch ratio alert
        bycatch_ratio = metrics["bycatch_ratio_percent"].value
        if bycatch_ratio > ALERT_BYCATCH_RATIO_MAX_PCT:
            alerts.append({
                "severity": AlertSeverity.HIGH.value,
                "code": "HIGH_BYCATCH_RATIO",
                "message": f"Bycatch ratio exceeds threshold: {bycatch_ratio:.1f}% of catch",
                "value": bycatch_ratio,
                "threshold": ALERT_BYCATCH_RATIO_MAX_PCT,
            })

        # Waste noncompliance alert
        waste_compliance = metrics["waste_compliance_percent"].value
        if waste_compliance < (100.0 - ALERT_WASTE_NONCOMPLIANCE_MAX_PCT):
            alerts.append({
                "severity": AlertSeverity.CRITICAL.value,
                "code": "WASTE_NONCOMPLIANCE",
                "message": f"Waste disposal noncompliant: {100.0 - waste_compliance:.1f}% improper",
                "value": 100.0 - waste_compliance,
                "threshold": ALERT_WASTE_NONCOMPLIANCE_MAX_PCT,
            })

        return alerts

    def get_watcher_frame(self) -> dict[str, Any]:
        """Get environmental data for watcher evaluation.

        Returns:
            Dict with environmental metrics for watcher rules
        """
        metrics = self.calculate_sustainability_metrics()

        return {
            "fuel_efficiency_nm_per_gal": metrics["fuel_efficiency_nm_per_gal"].value,
            "carbon_intensity_lb_per_nm": metrics["carbon_intensity_lb_per_nm"].value,
            "bycatch_ratio_percent": metrics["bycatch_ratio_percent"].value,
            "waste_compliance_percent": metrics["waste_compliance_percent"].value,
            "sustainability_score": self.get_sustainability_score(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for snapshot serialization.

        Returns:
            Dict with all environmental data
        """
        carbon = self.get_carbon_footprint()
        bycatch_summary = self.get_bycatch_summary()
        metrics = self.calculate_sustainability_metrics()

        return {
            "vessel_id": self.vessel_id,
            "carbon_footprint": carbon.to_dict(),
            "bycatch_summary": bycatch_summary,
            "sustainability_metrics": {
                name: metric.to_dict()
                for name, metric in metrics.items()
            },
            "sustainability_score": self.get_sustainability_score(),
            "total_fuel_gal": sum(r.quantity_gal for r in self._fuel_records),
            "total_distance_nm": self._total_distance_nm,
            "total_catch_lb": self._total_catch_lb,
            "total_waste_lb": sum(r.quantity_lb for r in self._waste_records),
            "fuel_record_count": len(self._fuel_records),
            "waste_record_count": len(self._waste_records),
            "bycatch_event_count": len(self._bycatch_events),
            "baseline_calculated": self._baseline_calculated,
            "baseline_co2_lb": self._baseline_co2_lb if self._baseline_calculated else 0.0,
        }
