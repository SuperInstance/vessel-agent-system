#!/usr/bin/env python3
"""Environmental Stewardship System Demo.

Demonstrates the environmental monitoring capabilities including:
- Fuel consumption tracking
- Emissions calculation
- Waste disposal tracking
- Bycatch monitoring
- Sustainability metrics
- Alert generation
"""

from __future__ import annotations

import tempfile
from twin.environmental import (
    AlertSeverity,
    BycatchDisposition,
    DisposalMethod,
    EnvironmentalStewardship,
    FuelType,
    WasteType,
)


def demo_stewardship():
    """Demonstrate the Environmental Stewardship system."""
    print("=" * 70)
    print("ENVIRONMENTAL STEWARDSHIP SYSTEM DEMO")
    print("=" * 70)
    print()

    # Create temporary directory for demo data
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize the stewardship system
        stewardship = EnvironmentalStewardship(
            vessel_id="US-AK-FVEILEEN-51",
            data_dir=tmpdir,
        )
        print(f"✓ Initialized Environmental Stewardship for {stewardship.vessel_id}")
        print()

        # ------------------------------------------------------------------
        # Fuel Consumption Tracking
        # ------------------------------------------------------------------
        print("FUEL CONSUMPTION TRACKING")
        print("-" * 70)

        # Log various fuel consumption events
        stewardship.log_fuel_consumption(
            fuel_type=FuelType.DIESEL,
            quantity_gal=15.0,
            source="main_engine",
            location_lat=58.5,
            location_lon=-157.0,
            engine_hours=1250.5,
        )
        print("✓ Logged diesel consumption: 15.0 gal (main engine)")

        stewardship.log_fuel_consumption(
            fuel_type=FuelType.BIODIESEL_B20,
            quantity_gal=8.0,
            source="generator",
        )
        print("✓ Logged B20 biodiesel consumption: 8.0 gal (generator)")

        stewardship.log_fuel_consumption(
            fuel_type=FuelType.DIESEL,
            quantity_gal=12.0,
            source="main_engine",
        )
        print("✓ Logged diesel consumption: 12.0 gal (main engine)")

        # Log distance traveled
        stewardship.log_distance(150.0)  # 150 nautical miles
        print("✓ Logged distance: 150.0 nm")
        print()

        # ------------------------------------------------------------------
        # Emissions Calculation
        # ------------------------------------------------------------------
        print("EMISSIONS CALCULATION")
        print("-" * 70)

        footprint = stewardship.get_carbon_footprint()
        print(f"✓ Total CO2 emissions: {footprint.total_co2_lb:.2f} lb")
        print(f"✓ Total SOx emissions: {footprint.total_sox_lb:.2f} lb")
        print(f"✓ Total NOx emissions: {footprint.total_nox_lb:.2f} lb")
        print(f"✓ Total PM emissions: {footprint.total_pm_lb:.2f} lb")
        print(f"✓ Efficiency metric: {footprint.efficiency_metric:.1f}/100")
        print()

        # ------------------------------------------------------------------
        # Waste Disposal Tracking
        # ------------------------------------------------------------------
        print("WASTE DISPOSAL TRACKING")
        print("-" * 70)

        stewardship.log_waste_disposal(
            waste_type=WasteType.OILY_BILGE,
            quantity_lb=50.0,
            disposal_method=DisposalMethod.PORT_FACILITY,
            certification="USCG_CERT_001",
        )
        print("✓ Logged oily bilge disposal: 50.0 lb (port facility)")

        stewardship.log_waste_disposal(
            waste_type=WasteType.GARBAGE,
            quantity_lb=30.0,
            disposal_method=DisposalMethod.INCINERATOR,
        )
        print("✓ Logged garbage disposal: 30.0 lb (incinerator)")

        stewardship.log_waste_disposal(
            waste_type=WasteType.SEWAGE,
            quantity_lb=200.0,
            disposal_method=DisposalMethod.OVERBOARD_LEGAL,
        )
        print("✓ Logged sewage disposal: 200.0 lb (legal overboard)")
        print()

        # ------------------------------------------------------------------
        # Bycatch Monitoring
        # ------------------------------------------------------------------
        print("BYCATCH MONITORING")
        print("-" * 70)

        # Log catch data for bycatch ratio calculation
        stewardship.log_catch(5000.0)  # 5000 lb of target catch
        print("✓ Logged target catch: 5000.0 lb")

        # Log bycatch events
        stewardship.log_bycatch_event(
            species="Chinook Salmon",
            quantity_lb=15.0,
            disposition=BycatchDisposition.RELEASED_ALIVE,
            release_condition="Good",
        )
        print("✓ Logged bycatch: Chinook Salmon 15.0 lb (released alive)")

        stewardship.log_bycatch_event(
            species="Coho Salmon",
            quantity_lb=8.0,
            disposition=BycatchDisposition.RELEASED_INJURED,
            release_condition="Fair",
        )
        print("✓ Logged bycatch: Coho Salmon 8.0 lb (released injured)")

        stewardship.log_bycatch_event(
            species="Halibut",
            quantity_lb=5.0,
            disposition=BycatchDisposition.DISCARDED,
        )
        print("✓ Logged bycatch: Halibut 5.0 lb (discarded)")
        print()

        # Get bycatch summary
        bycatch_summary = stewardship.get_bycatch_summary()
        print("BYCATCH SUMMARY:")
        print(f"  Total bycatch: {bycatch_summary['total_bycatch_lb']:.1f} lb")
        print(f"  Released alive: {bycatch_summary['released_alive_lb']:.1f} lb")
        print(f"  Released injured: {bycatch_summary['released_injured_lb']:.1f} lb")
        print(f"  Discarded: {bycatch_summary['discarded_lb']:.1f} lb")
        print(f"  Survival rate: {bycatch_summary['survival_rate_percent']:.1f}%")
        print(f"  Bycatch ratio: {bycatch_summary['bycatch_ratio_percent']:.2f}% of catch")
        print()

        # ------------------------------------------------------------------
        # Sustainability Metrics
        # ------------------------------------------------------------------
        print("SUSTAINABILITY METRICS")
        print("-" * 70)

        metrics = stewardship.calculate_sustainability_metrics()
        for name, metric in metrics.items():
            target_status = "✓" if metric.is_at_target() else "✗"
            threshold_status = "✓" if not metric.is_threshold_exceeded() else "✗"
            print(f"{target_status} {metric.metric_name}: {metric.value:.2f} {metric.unit}")
            print(f"  Target: {metric.target:.1f} {metric.unit} | Threshold: {metric.threshold:.1f} {metric.unit} {threshold_status}")
        print()

        # ------------------------------------------------------------------
        # Overall Performance
        # ------------------------------------------------------------------
        print("OVERALL PERFORMANCE")
        print("-" * 70)

        fuel_efficiency = stewardship.get_fuel_efficiency()
        emission_intensity = stewardship.get_emission_intensity()
        sustainability_score = stewardship.get_sustainability_score()

        print(f"✓ Fuel efficiency: {fuel_efficiency:.2f} nm/gal")
        print(f"✓ Carbon intensity: {emission_intensity:.3f} lb CO2/nm")
        print(f"✓ Sustainability score: {sustainability_score:.1f}/100")
        print()

        # ------------------------------------------------------------------
        # Alerts
        # ------------------------------------------------------------------
        print("ENVIRONMENTAL ALERTS")
        print("-" * 70)

        alerts = stewardship.get_alerts()
        if alerts:
            for alert in alerts:
                print(f"[{alert['severity'].upper()}] {alert['code']}")
                print(f"  {alert['message']}")
        else:
            print("✓ No environmental alerts - all metrics within thresholds")
        print()

        # ------------------------------------------------------------------
        # Snapshot
        # ------------------------------------------------------------------
        print("SYSTEM SNAPSHOT")
        print("-" * 70)

        snapshot = stewardship.to_dict()
        print(f"Vessel: {snapshot['vessel_id']}")
        print(f"Total fuel consumed: {snapshot['total_fuel_gal']:.1f} gal")
        print(f"Total distance: {snapshot['total_distance_nm']:.1f} nm")
        print(f"Total catch: {snapshot['total_catch_lb']:.1f} lb")
        print(f"Total waste: {snapshot['total_waste_lb']:.1f} lb")
        print(f"Fuel records: {snapshot['fuel_record_count']}")
        print(f"Waste records: {snapshot['waste_record_count']}")
        print(f"Bycatch events: {snapshot['bycatch_event_count']}")
        print(f"Baseline calculated: {snapshot['baseline_calculated']}")
        print()

        # ------------------------------------------------------------------
        # Watcher Integration
        # ------------------------------------------------------------------
        print("WATCHER INTEGRATION FRAME")
        print("-" * 70)

        watcher_frame = stewardship.get_watcher_frame()
        for key, value in watcher_frame.items():
            print(f"  {key}: {value}")
        print()

        print("=" * 70)
        print("DEMO COMPLETE")
        print("=" * 70)


if __name__ == "__main__":
    demo_stewardship()
