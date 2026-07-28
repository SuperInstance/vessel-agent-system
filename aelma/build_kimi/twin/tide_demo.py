#!/usr/bin/env python
"""Tide prediction demonstration for AELMA.

Shows the tide prediction system in action with real-world examples.
"""

from datetime import datetime, timedelta, timezone

from tide_predictor import TidePredictor


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def demo_basic_prediction():
    """Demonstrate basic tide prediction."""
    print_section("Basic Tide Prediction")

    predictor = TidePredictor(base_amplitude=2.0, datum_mllw_m=0.0)

    # Alaska location (high tidal range)
    lat, lon = 59.5, -152.3  # Kodiak Island
    now = datetime.now(timezone.utc)

    tide = predictor.predict_tide(lat, lon, now)

    print(f"\nLocation: Kodiak Island, Alaska ({lat}°N, {lon}°W)")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"\nCurrent water level: {tide.water_level_m:+.2f}m MLLW")
    print(f"Confidence: {tide.confidence:.2%}")
    print(f"Constituents used: {', '.join(tide.constituents_used)}")


def demo_tide_events():
    """Demonstrate high/low tide detection."""
    print_section("High/Low Tide Events")

    predictor = TidePredictor(base_amplitude=2.0)

    lat, lon = 45.5, -122.5  # Oregon coast
    now = datetime.now(timezone.utc)

    events = predictor.get_tide_range(lat, lon, now, duration_hours=24)

    print(f"\nLocation: Oregon Coast ({lat}°N, {lon}°W)")
    print(f"Period: Next 24 hours")
    print(f"\nTide events found: {len(events)}")

    for event in events:
        time_str = event.timestamp.strftime('%H:%M')
        print(f"  {event.event_type.upper():4s} at {time_str} -> {event.level_m:+.2f}m MLLW")


def demo_next_tides():
    """Demonstrate next high/low tide query."""
    print_section("Next High/Low Tides")

    predictor = TidePredictor(base_amplitude=2.0)

    lat, lon = 59.5, -152.3  # Kodiak Island
    now = datetime.now(timezone.utc)

    next_tides = predictor.get_next_high_low_tides(lat, lon, now)

    print(f"\nLocation: Kodiak Island, Alaska")
    print(f"Query time: {now.strftime('%Y-%m-%d %H:%M UTC')}")

    if next_tides.get("next_high_tide"):
        high = next_tides["next_high_tide"]
        high_time = datetime.fromisoformat(high["timestamp"]).strftime('%H:%M')
        print(f"\nNext HIGH TIDE:")
        print(f"  Time: {high_time} UTC (in {high['hours_from_now']:.1f} hours)")
        print(f"  Level: {high['level_m']:+.2f}m MLLW")

    if next_tides.get("next_low_tide"):
        low = next_tides["next_low_tide"]
        low_time = datetime.fromisoformat(low["timestamp"]).strftime('%H:%M')
        print(f"\nNext LOW TIDE:")
        print(f"  Time: {low_time} UTC (in {low['hours_from_now']:.1f} hours)")
        print(f"  Level: {low['level_m']:+.2f}m MLLW")


def demo_depth_clearance():
    """Demonstrate depth clearance checking."""
    print_section("Depth Clearance Check")

    predictor = TidePredictor(base_amplitude=2.0)

    lat, lon = 59.5, -152.3  # Kodiak Island
    now = datetime.now(timezone.utc)

    # Example vessel
    vessel_draft = 2.5  # meters
    chart_depth = 5.0   # meters (MLLW)

    clearance = predictor.check_depth_clearance(
        vessel_draft_m=vessel_draft,
        chart_depth_m=chart_depth,
        lat=lat,
        lon=lon,
        timestamp=now,
        safety_margin_m=1.0
    )

    print(f"\nVessel draft: {vessel_draft}m")
    print(f"Chart depth (MLLW): {chart_depth}m")
    print(f"Safety margin: {clearance['safety_margin_m']}m")
    print(f"\nResults:")

    status_symbol = "[OK]" if clearance["clearance_ok"] else "[!!]"
    print(f"  {status_symbol} Status: {clearance['status'].upper()}")
    print(f"  Current tide: {clearance['tide_level_m']:+.2f}m")
    print(f"  Water depth: {clearance['water_depth_m']:.2f}m")
    print(f"  Under-keel clearance: {clearance['under_keel_clearance_m']:.2f}m")
    print(f"  Clearance OK: {clearance['clearance_ok']}")


def demo_safe_passage():
    """Demonstrate safe passage planning."""
    print_section("Safe Passage Planning")

    predictor = TidePredictor(base_amplitude=2.0)

    lat, lon = 45.5, -122.5  # Oregon coast
    now = datetime.now(timezone.utc)

    analysis = predictor.get_safe_passage_window(
        vessel_draft_m=2.5,
        chart_depth_m=5.0,
        lat=lat,
        lon=lon,
        start_time=now,
        window_hours=12,
        safety_margin_m=1.0
    )

    print(f"\nLocation: Oregon Coast")
    print(f"Analysis period: 12 hours")
    print(f"Vessel draft: 2.5m, Chart depth: 5.0m")

    print(f"\nTide Events:")
    for event in analysis["tide_events"]:
        time_str = datetime.fromisoformat(event["timestamp"]).strftime('%H:%M')
        print(f"  {event['type'].upper():4s} at {time_str} -> {event['level_m']:+.2f}m")

    print(f"\nSafe Windows: {len(analysis['safe_windows'])}")
    for i, window in enumerate(analysis["safe_windows"], 1):
        start = datetime.fromisoformat(window["start"]).strftime('%H:%M')
        end = datetime.fromisoformat(window["end"]).strftime('%H:%M')
        print(f"  {i}. {start} - {end} ({window['duration_minutes']:.0f} min)")

    print(f"\nTotal safe time: {analysis['total_safe_minutes']:.0f} minutes")
    print(f"Unsafe periods: {len(analysis['unsafe_periods'])}")


def demo_regional_comparison():
    """Demonstrate tidal differences by region."""
    print_section("Regional Tidal Comparison")

    predictor = TidePredictor(base_amplitude=2.0)
    now = datetime.now(timezone.utc)

    locations = [
        ("Kodiak, Alaska", 59.5, -152.3),
        ("Seattle, WA", 47.6, -122.3),
        ("San Francisco, CA", 37.8, -122.4),
        ("Equator", 0.0, -120.0),
    ]

    print(f"\nWater levels at {now.strftime('%Y-%m-%d %H:%M UTC')}:\n")

    for name, lat, lon in locations:
        tide = predictor.predict_tide(lat, lon, now)
        print(f"  {name:20s}: {tide.water_level_m:+.2f}m MLLW")


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 70)
    print("  AELMA TIDE PREDICTION SYSTEM DEMONSTRATION")
    print("  NOAA Harmonic Constituent Method")
    print("=" * 70)

    demo_basic_prediction()
    demo_tide_events()
    demo_next_tides()
    demo_depth_clearance()
    demo_safe_passage()
    demo_regional_comparison()

    print("\n" + "=" * 70)
    print("  For more information, see: docs/tide_prediction.md")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
