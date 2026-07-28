#!/usr/bin/env python3
"""Example script demonstrating AELMA weather integration.

This script shows:
1. Fetching weather forecasts
2. Getting current conditions
3. Checking weather alerts
4. Assessing overall conditions
"""

import asyncio
import sys
from pathlib import pathlib

# Add parent directory to path for imports
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from build_kimi.twin.weather import (
    MockWeatherClient,
    assess_weather_conditions,
    wind_speed_category,
    wave_height_category,
    visibility_category,
)
from build_kimi.twin.core import TwinCore


async def example_basic_weather_fetch():
    """Example 1: Basic weather fetching with mock client."""
    print("=" * 60)
    print("Example 1: Basic Weather Fetch")
    print("=" * 60)

    # Create mock weather client
    client = MockWeatherClient(cache_ttl_s=900)

    # Seattle coordinates
    lat, lon = 47.6062, -122.3321

    try:
        # Fetch 24-hour forecast
        print(f"\nFetching 24-hour forecast for Seattle ({lat:.2f}, {lon:.2f})...")
        forecasts, alerts = await client.fetch_forecast(lat, lon, hours_ahead=24)

        print(f"Received {len(forecasts)} forecast points")
        print(f"Active alerts: {len(alerts)}")

        # Show first forecast
        if forecasts:
            f = forecasts[0]
            print(f"\n--- Current Conditions ---")
            print(f"Wind: {f.wind.speed_kn:.1f} kn @ {f.wind.direction_deg:.0f}°")
            print(f"  Gusts: {f.wind.gust_kn:.1f} kn" if f.wind.gust_kn else "  Gusts: N/A")
            print(f"Waves: {f.wave.height_m:.1f} m @ {f.wave.period_s:.0f}s" if f.wave.period_s else f"Waves: {f.wave.height_m:.1f} m")
            print(f"Visibility: {f.visibility_m/1000:.1f} km")
            print(f"Temperature: {f.air_temp_c:.1f}°C")
            print(f"Pressure: {f.pressure_hpa:.0f} hPa")
            print(f"Conditions: {f.description}")

        # Show future forecasts
        print(f"\n--- 24-Hour Forecast ---")
        for i, f in enumerate(forecasts):
            hours_from_now = (f.valid_ns - forecasts[0].valid_ns) / (3600 * 1_000_000_000)
            print(f"+{hours_from_now:.0f}h: {f.wind.speed_kn:.1f}kn wind, "
                  f"{f.wave.height_m:.1f}m waves, {f.description}")

    finally:
        await client.close()


async def example_current_conditions():
    """Example 2: Get current weather conditions."""
    print("\n" + "=" * 60)
    print("Example 2: Current Weather Conditions")
    print("=" * 60)

    client = MockWeatherClient()

    try:
        # San Francisco coordinates
        lat, lon = 37.7749, -122.4194

        print(f"\nFetching current conditions for San Francisco...")
        conditions = await client.get_current_conditions(lat, lon)

        print(f"\n--- Current Conditions ---")
        print(f"Location: {conditions.lat:.2f}, {conditions.lon:.2f}")
        print(f"Time: {conditions.timestamp_ns / 1e9:.0f}")

        # Wind
        wind_cat = wind_speed_category(conditions.wind.speed_kn)
        print(f"\nWind:")
        print(f"  Speed: {conditions.wind.speed_kn:.1f} kn ({wind_cat})")
        print(f"  Direction: {conditions.wind.direction_deg:.0f}°")
        if conditions.wind.gust_kn:
            print(f"  Gusts: {conditions.wind.gust_kn:.1f} kn")

        # Waves
        wave_cat = wave_height_category(conditions.wave.height_m)
        print(f"\nWaves:")
        print(f"  Height: {conditions.wave.height_m:.1f} m ({wave_cat})")
        if conditions.wave.period_s:
            print(f"  Period: {conditions.wave.period_s:.0f} s")
        if conditions.wave.direction_deg:
            print(f"  Direction: {conditions.wave.direction_deg:.0f}°")

        # Visibility
        vis_cat = visibility_category(conditions.visibility_m)
        print(f"\nVisibility:")
        print(f"  Distance: {conditions.visibility_m/1000:.1f} km ({vis_cat})")

        # Atmospheric
        print(f"\nAtmospheric:")
        print(f"  Temperature: {conditions.air_temp_c:.1f}°C")
        print(f"  Pressure: {conditions.pressure_hpa:.0f} hPa")
        print(f"  Humidity: {conditions.humidity_pct:.0f}%")
        print(f"  Cloud cover: {conditions.cloud_cover_pct:.0f}%")

        # Conditions
        print(f"\nWeather:")
        print(f"  Code: {conditions.condition_code}")
        print(f"  Description: {conditions.description}")
        if conditions.precipitation_mm > 0:
            print(f"  Precipitation: {conditions.precipitation_mm:.1f} mm ({conditions.precipitation_type})")

        # Overall assessment
        category, recommendation = assess_weather_conditions(
            conditions.wind.speed_kn,
            conditions.wave.height_m,
            conditions.visibility_m,
        )
        print(f"\n--- Assessment ---")
        print(f"Category: {category.upper()}")
        print(f"Recommendation: {recommendation}")

    finally:
        await client.close()


async def example_weather_alerts():
    """Example 3: Check for weather alerts."""
    print("\n" + "=" * 60)
    print("Example 3: Weather Alerts")
    print("=" * 60)

    client = MockWeatherClient()

    try:
        # Gulf of Mexico coordinates
        lat, lon = 26.0, -90.0

        print(f"\nChecking alerts for Gulf of Mexico...")
        alerts = await client.check_alerts(lat, lon)

        print(f"\nActive alerts: {len(alerts)}")

        if alerts:
            for alert in alerts:
                print(f"\n--- {alert.severity.upper()} ---")
                print(f"Title: {alert.title}")
                print(f"Description: {alert.description}")
                if alert.alert_type:
                    print(f"Type: {alert.alert_type}")
        else:
            print("No active alerts")

    finally:
        await client.close()


async def example_twin_core_integration():
    """Example 4: TwinCore with weather integration."""
    print("\n" + "=" * 60)
    print("Example 4: TwinCore Weather Integration")
    print("=" * 60)

    # Create TwinCore with mock weather
    core = TwinCore(
        vessel_id="US-AK-EXAMPLE-01",
        enable_weather=True,
        use_mock_weather=True,
        enable_watchers=True,
    )

    print("\nTwinCore initialized with weather integration")

    # Simulate position update
    import time
    now_ns = time.time_ns()

    lat_packet = {
        "timestamp_ns": now_ns,
        "source": "manual",
        "channel": "position.lat",
        "value": 47.6062,
    }

    lon_packet = {
        "timestamp_ns": now_ns,
        "source": "manual",
        "channel": "position.lon",
        "value": -122.3321,
    }

    print("\nSimulating position update...")
    core.handle_packet(lat_packet)
    core.handle_packet(lon_packet)

    # Wait for async weather fetch
    print("Waiting for weather fetch...")
    await asyncio.sleep(0.2)

    # Build snapshot
    print("\nBuilding vessel snapshot...")
    snapshot = core.build_snapshot()

    if "weather" in snapshot:
        weather = snapshot["weather"]
        conditions = weather["conditions"]

        print(f"\n--- Weather in Snapshot ---")
        print(f"Wind: {conditions['wind_speed_kn']:.1f} kn @ {conditions['wind_direction_deg']:.0f}°")
        print(f"Waves: {conditions['wave_height_m']:.1f} m")
        print(f"Visibility: {conditions['visibility_m']/1000:.1f} km")
        print(f"Conditions: {conditions['weather_condition']}")
        print(f"Category: {conditions['weather_category']}")

        forecasts = weather["forecasts"]
        print(f"\nForecast points: {len(forecasts)}")

        alerts = weather["alerts"]
        print(f"Active alerts: {len(alerts)}")

    # Check watcher rules
    print("\n--- Watcher Evaluation ---")
    frame = core._build_frame()

    if "wind_speed_kn" in frame:
        print(f"Wind in frame: {frame['wind_speed_kn']:.1f} kn")
    if "wave_height_m" in frame:
        print(f"Waves in frame: {frame['wave_height_m']:.1f} m")
    if "weather_category" in frame:
        print(f"Weather category: {frame['weather_category']}")

    # Cleanup
    await core._weather_client.close()
    print("\nWeather client closed")


async def example_condition_assessment():
    """Example 5: Assess various weather conditions."""
    print("\n" + "=" * 60)
    print("Example 5: Condition Assessment Examples")
    print("=" * 60)

    scenarios = [
        ("Good conditions", 10.0, 0.8, 10000.0),
        ("Caution conditions", 18.0, 1.5, 3000.0),
        ("Hazardous conditions", 30.0, 3.5, 1500.0),
        ("Dangerous conditions", 50.0, 5.0, 500.0),
    ]

    for name, wind, wave, vis in scenarios:
        category, recommendation = assess_weather_conditions(wind, wave, vis)
        print(f"\n{name}:")
        print(f"  Wind: {wind:.1f} kn, Waves: {wave:.1f} m, Visibility: {vis/1000:.1f} km")
        print(f"  Category: {category.upper()}")
        print(f"  Recommendation: {recommendation}")


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("AELMA Weather Integration Examples")
    print("=" * 60)

    try:
        await example_basic_weather_fetch()
        await example_current_conditions()
        await example_weather_alerts()
        await example_twin_core_integration()
        await example_condition_assessment()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
