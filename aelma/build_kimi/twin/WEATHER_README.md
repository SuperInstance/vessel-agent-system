# Marine Weather Integration for AELMA

Complete weather integration system for AELMA twin with marine-specific forecasts, automatic caching, and alert detection.

## Features

- **Marine Weather Data**: Wind speed/direction, wave height/period, visibility, air pressure, temperature
- **Multiple Providers**: OpenWeatherMap (global) and NOAA (US waters, marine-specific)
- **Smart Caching**: 15-minute TTL cache reduces API calls and improves performance
- **Auto-Refresh**: Weather automatically updates on position changes (every 15 minutes)
- **Alert Detection**: Built-in watcher rules for hazardous conditions
- **Route Optimization Ready**: Weather data included in vessel state snapshots

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TwinCore Weather Integration               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Position Update → Auto-Fetch Weather → Cache → Snapshot     │
│                         ↓                                     │
│                    Watcher Rules → Alerts                    │
│                                                               │
│  ┌──────────────────┐      ┌──────────────────┐              │
│  │ WeatherClient    │      │ MockWeatherClient│              │
│  │                  │      │ (for testing)     │              │
│  │ • OpenWeatherMap │      │                    │              │
│  │ • NOAA           │      │ • Realistic data   │              │
│  │ • Caching        │      │ • No API calls     │              │
│  └──────────────────┘      └──────────────────┘              │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Get API Key

**OpenWeatherMap (Free Tier):**
- Sign up at: https://openweathermap.org/api
- Get free API key (1,000 calls/day)
- Supports global coverage

**NOAA (US Waters Only):**
- Marine-specific forecasts for US waters
- Better wave data for coastal regions

### 2. Enable Weather in TwinCore

```python
from build_kimi.twin.core import TwinCore

# With OpenWeatherMap
core = TwinCore(
    vessel_id="US-AK-FVEILEEN-51",
    enable_weather=True,
    weather_api_key="your-openweather-api-key",
    weather_provider="openweather",
)

# With NOAA
core = TwinCore(
    vessel_id="US-AK-FVEILEEN-51",
    enable_weather=True,
    weather_api_key="your-noaa-api-key",
    weather_provider="noaa",
)

# With mock client (for testing)
core = TwinCore(
    vessel_id="US-AK-FVEILEEN-51",
    enable_weather=True,
    use_mock_weather=True,
)
```

### 3. Run TwinCore

```python
await core.run()
```

Weather will automatically fetch when the vessel moves.

## Weather Data Structure

### Current Conditions

```python
{
    "wind_speed_kn": 15.0,        # Wind speed in knots
    "wind_direction_deg": 225.0,  # Wind direction 0-360°
    "wave_height_m": 1.2,         # Significant wave height in meters
    "visibility_m": 10000.0,       # Visibility in meters
    "air_temp_c": 15.0,           # Air temperature in Celsius
    "pressure_hpa": 1013.0,       # Atmospheric pressure in hPa
    "weather_condition": "Clear", # Condition description
    "weather_category": "good",   # Overall assessment
}
```

### Forecast

```python
{
    "valid_ns": 1234567890000000000,  # Valid time (nanoseconds)
    "wind_speed_kn": 15.0,
    "wind_direction_deg": 225.0,
    "wave_height_m": 1.2,
    "visibility_m": 10000.0,
    "air_temp_c": 15.0,
    "description": "clear sky",
}
```

### Alerts

```python
{
    "severity": "warning",         # advisory, watch, warning
    "title": "Small Craft Advisory",
    "description": "Conditions hazardous to small craft",
    "onset_ns": 1234567890000000000,
    "expiry_ns": 1234567900000000000,
}
```

## Watcher Rules

The system includes built-in watcher rules that fire automatically:

### High Wind Warning
- **Triggers**: Wind ≥ 34 knots (gale force)
- **Severity**: warning
- **Priority**: 0.80

### Storm Warning
- **Triggers**: Wind ≥ 48 knots (storm force)
- **Severity**: critical
- **Priority**: 0.95

### Rough Seas Warning
- **Triggers**: Waves ≥ 2.5 meters
- **Severity**: warning
- **Priority**: 0.75

### Poor Visibility Warning
- **Triggers**: Visibility < 2000 meters
- **Severity**: warning
- **Priority**: 0.70

### Weather Deterioration
- **Triggers**: Overall category = "hazardous"
- **Severity**: warning
- **Priority**: 0.85

## Weather Categories

The system assesses overall conditions using three factors:

| Category | Wind | Waves | Visibility | Recommendation |
|----------|------|-------|------------|----------------|
| **good** | < 15 kn | < 1.2m | > 2000m | Normal operations |
| **caution** | 15-22 kn | 1.2-2.5m | 1000-2000m | Use caution |
| **hazardous** | 22-34 kn | 2.5-4m | 500-1000m | Experienced crews only |
| **dangerous** | > 34 kn | > 4m | < 500m | Seek safe harbor |

## Caching Behavior

Weather forecasts are cached with a 15-minute TTL:

- **Cache Key**: Latitude and longitude rounded to 2 decimals (~1km precision)
- **TTL**: 900 seconds (15 minutes) by default
- **Auto-Refresh**: Weather fetches only when:
  - 15 minutes have passed since last fetch
  - Vessel position changes significantly

```python
# Customize cache TTL
core = TwinCore(
    vessel_id="US-AK-FVEILEEN-51",
    enable_weather=True,
    weather_api_key="your-key",
    weather_cache_ttl_s=1800,  # 30 minutes
)
```

## VesselStateSnapshot

Weather data is included in the snapshot broadcast to viewers:

```python
snapshot = core.build_snapshot()
# snapshot["weather"]["conditions"] - Current conditions
# snapshot["weather"]["forecasts"] - 24-hour forecast (8 points)
# snapshot["weather"]["alerts"] - Active weather alerts
```

## Testing

Use MockWeatherClient for testing without API calls:

```python
from build_kimi.twin.weather import MockWeatherClient

client = MockWeatherClient(cache_ttl_s=900)

# Fetch forecast (returns realistic marine data)
forecasts, alerts = await client.fetch_forecast(47.6, -122.4, hours_ahead=24)

# Get current conditions
conditions = await client.get_current_conditions(47.6, -122.4)

# Check alerts
alerts = await client.check_alerts(47.6, -122.4)

await client.close()
```

## Running Tests

```bash
# Run all weather tests
pytest tests/test_weather.py -v

# Run specific test class
pytest tests/test_weather.py::TestMockWeatherClient -v

# Run with coverage
pytest tests/test_weather.py --cov=build_kimi.twin.weather
```

## API Limits

### OpenWeatherMap Free Tier
- **Calls/day**: 1,000
- **Forecast points**: 5-day / 3-hour forecast (40 points)
- **Coverage**: Global
- **Cost**: Free

### NOAA
- **Calls/day**: Unlimited (within reason)
- **Forecast points**: Marine-specific forecasts
- **Coverage**: US waters only
- **Cost**: Free

## Performance

With caching enabled (default):
- **First fetch**: ~100-500ms (API call)
- **Cached fetch**: ~1-5ms (from cache)
- **Memory**: ~1KB per cached location
- **API calls**: ~4 per hour (per vessel) with 15-minute TTL

## Troubleshooting

### Weather Not Updating

```python
# Check if weather is enabled
print(core.enable_weather)  # Should be True

# Check if client is initialized
print(core._weather_client)  # Should not be None

# Check last fetch time
print(core._last_weather_fetch_ns)  # Should be recent

# Manually trigger fetch
await core._fetch_weather_async(lat, lon)
```

### API Errors

```python
# Check logs
import logging
logging.basicConfig(level=logging.DEBUG)

# Verify API key
# OpenWeatherMap keys start with a letter/digit and are 32 chars
# NOAA keys vary in format

# Test API manually
curl "https://api.openweathermap.org/data/2.5/weather?lat=47.6&lon=-122.4&appid=YOUR_KEY&units=metric"
```

### Cache Issues

```python
# Clear cache
core._weather_client.clear_cache()

# Adjust TTL
core = TwinCore(
    vessel_id="US-AK-FVEILEEN-51",
    enable_weather=True,
    weather_cache_ttl_s=300,  # 5 minutes
)
```

## Route Optimization (Future)

Weather data can be used for route optimization:

```python
# Get weather along planned route
for waypoint in route:
    weather = await core._weather_client.fetch_forecast(
        waypoint.lat, waypoint.lon, hours_ahead=24
    )
    # Assess conditions
    category, recommendation = assess_weather_conditions(
        weather[0].wind.speed_kn,
        weather[0].wave.height_m,
        weather[0].visibility_m,
    )
    # Adjust route if hazardous
    if category == "dangerous":
        reroute_away(waypoint)
```

## License

MIT License - Part of AELMA (Autonomous Electronic Logging & Marine Analytics)

## Support

For issues or questions:
- GitHub Issues: https://github.com/SuperInstance/aelma/issues
- Documentation: See `/docs` directory
