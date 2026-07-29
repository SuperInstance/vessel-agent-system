# Environmental Stewardship System

Comprehensive environmental monitoring system for the AELMA twin commercial fishing vessel.

## Overview

The Environmental Stewardship system tracks fuel efficiency, carbon footprint, waste management, bycatch mitigation, and sustainability metrics for commercial fishing operations. It provides real-time monitoring, alert generation, and compliance tracking to support sustainable fishing practices.

## Features

### 1. Fuel Consumption Tracking
- **Fuel Types Supported**: Diesel, B20 Biodiesel, B100 Biodiesel, LNG, Electric
- **Tracking**: Quantity, source (engine/generator), location, engine hours
- **Emissions Calculation**: CO2, SOx, NOx, Particulate Matter based on EPA/IMO factors
- **Baseline Monitoring**: Automatic baseline calculation for emission trends

### 2. Carbon Footprint
- **Total Emissions**: CO2, SOx, NOx, PM in pounds
- **Emission Factors**: Per-gallon factors for each fuel type
- **Efficiency Metric**: 0-100 score based on total CO2 output
- **Trend Analysis**: Comparison against baseline with alerting

### 3. Waste Management
- **Waste Types**: Oily Bilge, Garbage, Sewage, Chemical, Fishing Waste, Plastic
- **Disposal Methods**: Port Facility, Incinerator, Legal Overboard, Retained, Gear Loss
- **Compliance Tracking**: Automatic verification of regulatory compliance
- **Certification**: Optional certification tracking for disposal events

### 4. Bycatch Monitoring
- **Event Tracking**: Species, quantity, disposition, release condition
- **Disposition Types**: Released Alive, Released Injured, Retained, Discarded
- **Survival Analysis**: Survival rate calculation
- **Bycatch Ratio**: Percentage of total catch
- **Species Breakdown**: Summary by species

### 5. Sustainability Metrics
- **Fuel Efficiency**: Nautical miles per gallon (target: 20 nm/gal, threshold: 15 nm/gal)
- **Carbon Intensity**: Pounds CO2 per nautical mile (target: 1.2 lb/nm, threshold: 1.5 lb/nm)
- **Bycatch Ratio**: Percentage of catch (target: 2.0%, threshold: 5.0%)
- **Waste Compliance**: Proper disposal percentage (target: 100%, threshold: 90%)
- **Overall Score**: 0-100 sustainability score

### 6. Alert System
- **High Emissions**: >10% above baseline
- **Low Fuel Efficiency**: <15 nm/gal
- **High Bycatch Ratio**: >5% of total catch
- **Waste Noncompliance**: >10% improper disposal

## Installation

The system is part of the AELMA twin and requires no additional dependencies beyond the standard twin environment.

## Usage

### Basic Setup

```python
from twin.environmental import EnvironmentalStewardship

# Initialize the system
stewardship = EnvironmentalStewardship(
    vessel_id="US-AK-FVEILEEN-51",
    data_dir="environmental_data",
)
```

### Fuel Consumption

```python
from twin.environmental import FuelType

# Log fuel consumption
stewardship.log_fuel_consumption(
    fuel_type=FuelType.DIESEL,
    quantity_gal=15.0,
    source="main_engine",
    location_lat=58.5,
    location_lon=-157.0,
    engine_hours=1250.5,
)

# Get carbon footprint
footprint = stewardship.get_carbon_footprint()
print(f"CO2 emissions: {footprint.total_co2_lb:.2f} lb")
```

### Waste Disposal

```python
from twin.environmental import WasteType, DisposalMethod

# Log waste disposal
stewardship.log_waste_disposal(
    waste_type=WasteType.OILY_BILGE,
    quantity_lb=50.0,
    disposal_method=DisposalMethod.PORT_FACILITY,
    certification="USCG_CERT_001",
)

# Get waste records
oily_bilge_records = stewardship.get_waste_records(waste_type=WasteType.OILY_BILGE)
```

### Bycatch Monitoring

```python
from twin.environmental import BycatchDisposition

# Log catch for ratio calculation
stewardship.log_catch(5000.0)  # 5000 lb of target catch

# Log bycatch event
stewardship.log_bycatch_event(
    species="Chinook Salmon",
    quantity_lb=15.0,
    disposition=BycatchDisposition.RELEASED_ALIVE,
    release_condition="Good",
)

# Get bycatch summary
summary = stewardship.get_bycatch_summary()
print(f"Survival rate: {summary['survival_rate_percent']:.1f}%")
print(f"Bycatch ratio: {summary['bycatch_ratio_percent']:.2f}%")
```

### Sustainability Metrics

```python
# Calculate all metrics
metrics = stewardship.calculate_sustainability_metrics()

# Check specific metrics
fuel_efficiency = stewardship.get_fuel_efficiency()
emission_intensity = stewardship.get_emission_intensity()
sustainability_score = stewardship.get_sustainability_score()

print(f"Fuel efficiency: {fuel_efficiency:.2f} nm/gal")
print(f"Carbon intensity: {emission_intensity:.3f} lb CO2/nm")
print(f"Sustainability score: {sustainability_score:.1f}/100")
```

### Alerts

```python
# Get environmental alerts
alerts = stewardship.get_alerts()

for alert in alerts:
    print(f"[{alert['severity']}] {alert['code']}")
    print(f"  {alert['message']}")
```

### Watcher Integration

```python
# Get data for watcher evaluation
frame = stewardship.get_watcher_frame()

# Frame contains:
# - fuel_efficiency_nm_per_gal
# - carbon_intensity_lb_per_nm
# - bycatch_ratio_percent
# - waste_compliance_percent
# - sustainability_score
```

### Snapshot

```python
# Get complete system snapshot
snapshot = stewardship.to_dict()

# Snapshot includes:
# - Vessel ID
# - Carbon footprint
# - Bycatch summary
# - Sustainability metrics
# - Overall score
# - Record counts
# - Baseline status
```

## Emission Factors

The system uses EPA and IMO regulatory emission factors:

### Diesel
- CO2: 22.38 lb/gal
- SOx: 0.03 lb/gal (ultra-low sulfur)
- NOx: 0.85 lb/gal (Tier 3)
- PM: 0.05 lb/gal

### B20 Biodiesel
- CO2: 17.90 lb/gal (20% reduction)
- SOx: 0.02 lb/gal
- NOx: 0.82 lb/gal
- PM: 0.04 lb/gal

### B100 Biodiesel
- CO2: 11.19 lb/gal (50% reduction)
- SOx: 0.01 lb/gal
- NOx: 0.78 lb/gal
- PM: 0.02 lb/gal

### LNG
- CO2: 14.67 lb/gal
- SOx: 0.00 lb/gal (zero sulfur)
- NOx: 0.45 lb/gal (50% reduction)
- PM: 0.00 lb/gal (zero particulate)

### Electric
- CO2: 0.00 lb/gal (zero direct emissions)
- SOx: 0.00 lb/gal
- NOx: 0.00 lb/gal
- PM: 0.00 lb/gal

## Data Persistence

The system maintains append-only JSONL files for all data:

- `fuel.jsonl`: Fuel consumption records
- `waste.jsonl`: Waste disposal records
- `bycatch.jsonl`: Bycatch events
- `metrics.jsonl`: Sustainability metrics

All data is automatically persisted and loaded on system initialization.

## Testing

The system includes 55 comprehensive tests covering:

- Data class creation and validation
- Fuel logging and emissions calculation
- Waste tracking and compliance
- Bycatch recording and summaries
- Sustainability metrics calculation
- Alert generation
- Persistence and data loading
- Edge cases and error handling

Run tests:

```bash
python -m pytest twin/environmental/tests/test_stewardship.py -v
```

## Integration

The Environmental Stewardship system integrates with:

1. **TwinCore**: Primary integration point for vessel data
2. **WatcherRegistry**: Provides environmental metrics for rule evaluation
3. **TripSummary**: Contributes environmental data to trip summaries
4. **ReportGenerator**: Supports environmental reporting

## API Reference

### Classes

- `EnvironmentalStewardship`: Main stewardship system
- `FuelRecord`: Fuel consumption event
- `EmissionFactor`: Emission factors for fuel type
- `CarbonFootprint`: Aggregate carbon metrics
- `WasteRecord`: Waste disposal event
- `BycatchEvent`: Bycatch event
- `SustainabilityMetric`: Metric with target and threshold

### Enums

- `FuelType`: Diesel, B20, B100, LNG, Electric
- `WasteType`: Oily Bilge, Garbage, Sewage, Chemical, Fishing Waste, Plastic
- `DisposalMethod`: Port Facility, Incinerator, Legal Overboard, Retained, Gear Loss
- `BycatchDisposition`: Released Alive, Released Injured, Retained, Discarded
- `AlertSeverity`: Info, Low, Medium, High, Critical

## Compliance

The system supports regulatory compliance for:

- **MARPOL Annex VI**: Air emissions from ships
- **EPA Vessel General Permit (VGP)**: Discharge requirements
- **NOAA Fisheries**: Bycatch reporting and mitigation
- **State Regulations**: Alaska Department of Fish and Game

## Performance

- **Fuel Records**: Handles 1000+ records efficiently
- **Emission Calculations**: Real-time calculation from all records
- **Alert Generation**: Threshold-based alerting with configurable limits
- **Persistence**: Append-only writes for high throughput

## Future Enhancements

Potential additions:

1. **Carbon Credit Tracking**: Integration with carbon offset programs
2. **Fuel Trend Analysis**: Predictive analytics for fuel consumption
3. **Waste Reduction Metrics**: Track waste reduction over time
4. **Bycatch Prediction**: ML-based bycatch risk assessment
5. **Regulatory Reporting**: Automated report generation for compliance

## Contributing

When contributing to the Environmental Stewardship system:

1. Maintain 100% test coverage
2. Follow existing dataclass patterns
3. Add validation for new fields
4. Update documentation for new features
5. Include persistence testing for new data types

## License

Part of the AELMA twin system. See main project license for details.
