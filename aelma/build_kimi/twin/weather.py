"""Marine weather integration for AELMA twin.

Fetches and caches marine weather forecasts from NOAA/PointCast and OpenWeatherMap.
Provides wind, wave, visibility, and marine alerts for vessel operations.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

log = logging.getLogger("aelma.twin.weather")


# --------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------- #


@dataclass(frozen=True)
class WindConditions:
    """Wind speed and direction."""
    speed_kn: float  # Wind speed in knots
    direction_deg: float  # Wind direction from 0-360 degrees
    gust_kn: float | None = None  # Gust speed in knots


@dataclass(frozen=True)
class WaveConditions:
    """Wave height and period."""
    height_m: float  # Significant wave height in meters
    period_s: float | None = None  # Wave period in seconds
    direction_deg: float | None = None  # Wave direction 0-360 degrees


@dataclass(frozen=True)
class WeatherConditions:
    """Current weather conditions at a location."""
    timestamp_ns: int
    lat: float
    lon: float

    # Marine conditions
    wind: WindConditions
    wave: WaveConditions
    visibility_m: float  # Visibility in meters

    # Atmospheric conditions
    air_temp_c: float  # Air temperature in Celsius
    pressure_hpa: float  # Atmospheric pressure in hPa
    humidity_pct: float  # Relative humidity 0-100

    # Precipitation
    precipitation_mm: float  # Precipitation in mm

    # General conditions
    condition_code: str  # Weather condition code
    description: str  # Human-readable description

    # Optional fields
    precipitation_type: str | None = None  # "rain", "snow", "sleet", etc.
    cloud_cover_pct: float = 0.0  # Cloud cover 0-100


@dataclass(frozen=True)
class WeatherAlert:
    """Marine weather alert or advisory."""
    severity: str  # "advisory", "watch", "warning"
    title: str
    description: str
    onset_ns: int
    expiry_ns: int | None = None
    alert_type: str | None = None  # "small_craft", "gale", "storm", etc.


@dataclass(frozen=True)
class WeatherForecast:
    """Weather forecast for a specific time."""
    valid_ns: int  # Valid time for this forecast point

    wind: WindConditions
    wave: WaveConditions
    visibility_m: float

    air_temp_c: float
    pressure_hpa: float
    precipitation_mm: float
    condition_code: str
    description: str


@dataclass
class CachedForecast:
    """Cached forecast data with TTL."""
    forecasts: list[WeatherForecast]
    alerts: list[WeatherAlert]
    cached_at_ns: int
    ttl_s: int = 900  # 15-minute default TTL


# --------------------------------------------------------------------- #
# Weather client
# --------------------------------------------------------------------- #


class WeatherClient:
    """Marine weather client with caching for AELMA twin.

    Supports two weather providers:
    1. NOAA/PointCast (requires API key, US waters)
    2. OpenWeatherMap (requires API key, global)

    Forecasts are cached for 15 minutes to reduce API calls.
    """

    def __init__(
        self,
        openweather_api_key: str | None = None,
        noaa_api_key: str | None = None,
        cache_ttl_s: int = 900,
        http_timeout_s: float = 10.0,
    ) -> None:
        """Initialize weather client with API keys and caching.

        Args:
            openweather_api_key: OpenWeatherMap API key (global coverage)
            noaa_api_key: NOAA/PointCast API key (US waters, marine-specific)
            cache_ttl_s: Cache time-to-live in seconds (default 900 = 15 min)
            http_timeout_s: HTTP request timeout in seconds
        """
        self._openweather_key = openweather_api_key
        self._noaa_key = noaa_api_key
        self._cache_ttl_s = cache_ttl_s
        self._timeout = http_timeout_s

        # Cache: key = "lat,lon" rounded to 2 decimals
        self._forecast_cache: dict[str, CachedForecast] = {}
        self._conditions_cache: dict[str, tuple[WeatherConditions, int]] = {}

        self._client = httpx.AsyncClient(timeout=http_timeout_s)

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()

    def _cache_key(self, lat: float, lon: float) -> str:
        """Generate cache key with 2-decimal precision (~1km)."""
        return f"{lat:.2f},{lon:.2f}"

    def _is_forecast_cache_valid(self, cached: CachedForecast) -> bool:
        """Check if cached forecast is still valid."""
        age_s = (time.time_ns() - cached.cached_at_ns) / 1e9
        return age_s < self._cache_ttl_s

    def _is_conditions_cache_valid(self, cached_at_ns: int) -> bool:
        """Check if cached conditions are still valid."""
        age_s = (time.time_ns() - cached_at_ns) / 1e9
        return age_s < self._cache_ttl_s

    async def fetch_forecast(
        self,
        lat: float,
        lon: float,
        hours_ahead: int = 24,
    ) -> tuple[list[WeatherForecast], list[WeatherAlert]]:
        """Fetch weather forecast for a location.

        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
            hours_ahead: Forecast horizon in hours (default 24)

        Returns:
            Tuple of (forecasts, alerts) where:
            - forecasts: List of WeatherForecast (typically 3-hour intervals)
            - alerts: List of active WeatherAlert

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If no API keys are configured
        """
        # Check cache
        cache_key = self._cache_key(lat, lon)
        if cache_key in self._forecast_cache:
            cached = self._forecast_cache[cache_key]
            if self._is_forecast_cache_valid(cached):
                log.debug(f"Forecast cache hit for {cache_key}")
                # Filter forecasts to requested horizon
                cutoff_ns = time.time_ns() + (hours_ahead * 3600 * 1e9)
                valid_forecasts = [f for f in cached.forecasts if f.valid_ns <= cutoff_ns]
                return valid_forecasts, cached.alerts

        # Fetch from API
        if self._openweather_key:
            forecasts, alerts = await self._fetch_openweather_forecast(lat, lon, hours_ahead)
        elif self._noaa_key:
            forecasts, alerts = await self._fetch_noaa_forecast(lat, lon, hours_ahead)
        else:
            raise ValueError("No weather API keys configured. Set openweather_api_key or noaa_api_key.")

        # Cache results
        self._forecast_cache[cache_key] = CachedForecast(
            forecasts=forecasts,
            alerts=alerts,
            cached_at_ns=time.time_ns(),
            ttl_s=self._cache_ttl_s,
        )
        log.info(f"Fetched and cached forecast for {cache_key}: {len(forecasts)} points, {len(alerts)} alerts")

        return forecasts, alerts

    async def get_current_conditions(self, lat: float, lon: float) -> WeatherConditions:
        """Get current weather conditions at a location.

        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees

        Returns:
            Current WeatherConditions

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If no API keys are configured
        """
        # Check cache
        cache_key = self._cache_key(lat, lon)
        if cache_key in self._conditions_cache:
            conditions, cached_at = self._conditions_cache[cache_key]
            if self._is_conditions_cache_valid(cached_at):
                log.debug(f"Conditions cache hit for {cache_key}")
                return conditions

        # Fetch from API
        if self._openweather_key:
            conditions = await self._fetch_openweather_current(lat, lon)
        elif self._noaa_key:
            conditions = await self._fetch_noaa_current(lat, lon)
        else:
            raise ValueError("No weather API keys configured. Set openweather_api_key or noaa_api_key.")

        # Cache results
        self._conditions_cache[cache_key] = (conditions, time.time_ns())
        log.info(f"Fetched and cached conditions for {cache_key}: {conditions.description}")

        return conditions

    async def check_alerts(self, lat: float, lon: float) -> list[WeatherAlert]:
        """Check for active weather alerts at a location.

        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees

        Returns:
            List of active WeatherAlert (empty if none)
        """
        # This will use cached alerts from fetch_forecast if available
        forecasts, alerts = await self.fetch_forecast(lat, lon, hours_ahead=24)
        return alerts

    async def _fetch_openweather_forecast(
        self,
        lat: float,
        lon: float,
        hours_ahead: int,
    ) -> tuple[list[WeatherForecast], list[WeatherAlert]]:
        """Fetch forecast from OpenWeatherMap."""
        if not self._openweather_key:
            raise ValueError("OpenWeatherMap API key not configured")

        # Use 5-day forecast endpoint
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self._openweather_key,
            "units": "metric",
            "cnt": min(40, (hours_ahead // 3) + 1),  # 3-hour intervals, max 40 points
        }

        response = await self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # Parse forecasts
        forecasts: list[WeatherForecast] = []
        for item in data.get("list", []):
            wind = item.get("wind", {})
            rain = item.get("rain", {}) or {}
            snow = item.get("snow", {}) or {}
            visibility = item.get("visibility", 10000)  # Default 10km

            # Determine wave conditions (not provided by OWM, use estimates)
            wave = WaveConditions(
                height_m=0.0,  # Not available from OpenWeatherMap
                period_s=None,
                direction_deg=None,
            )

            forecasts.append(WeatherForecast(
                valid_ns=int(item.get("dt", 0)) * 1_000_000_000,
                wind=WindConditions(
                    speed_kn=wind.get("speed", 0) * 1.94384,  # m/s to knots
                    direction_deg=wind.get("deg", 0),
                    gust_kn=wind.get("gust", 0) * 1.94384 if "gust" in wind else None,
                ),
                wave=wave,
                visibility_m=visibility,
                air_temp_c=item.get("main", {}).get("temp", 0),
                pressure_hpa=item.get("main", {}).get("pressure", 1013),
                precipitation_mm=rain.get("3h", 0) + snow.get("3h", 0),
                condition_code=item.get("weather", [{}])[0].get("main", "Unknown"),
                description=item.get("weather", [{}])[0].get("description", "unknown"),
            ))

        return forecasts, []

    async def _fetch_openweather_current(self, lat: float, lon: float) -> WeatherConditions:
        """Fetch current conditions from OpenWeatherMap."""
        if not self._openweather_key:
            raise ValueError("OpenWeatherMap API key not configured")

        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self._openweather_key,
            "units": "metric",
        }

        response = await self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        wind = data.get("wind", {})
        rain = data.get("rain", {}) or {}
        snow = data.get("snow", {}) or {}
        weather = data.get("weather", [{}])[0]

        return WeatherConditions(
            timestamp_ns=time.time_ns(),
            lat=lat,
            lon=lon,
            wind=WindConditions(
                speed_kn=wind.get("speed", 0) * 1.94384,  # m/s to knots
                direction_deg=wind.get("deg", 0),
                gust_kn=wind.get("gust", 0) * 1.94384 if "gust" in wind else None,
            ),
            wave=WaveConditions(
                height_m=0.0,  # Not available from OpenWeatherMap
                period_s=None,
                direction_deg=None,
            ),
            visibility_m=data.get("visibility", 10000),
            air_temp_c=data.get("main", {}).get("temp", 0),
            pressure_hpa=data.get("main", {}).get("pressure", 1013),
            humidity_pct=data.get("main", {}).get("humidity", 0),
            precipitation_mm=rain.get("1h", 0) + snow.get("1h", 0),
            condition_code=weather.get("main", "Unknown"),
            description=weather.get("description", "unknown"),
            precipitation_type=rain.get("1h", 0) > 0 and "rain" or snow.get("1h", 0) > 0 and "snow" or None,
            cloud_cover_pct=data.get("clouds", {}).get("all", 0),
        )

    async def _fetch_noaa_forecast(
        self,
        lat: float,
        lon: float,
        hours_ahead: int,
    ) -> tuple[list[WeatherForecast], list[WeatherAlert]]:
        """Fetch marine forecast from NOAA/PointCast.

        Note: This is a placeholder for NOAA API integration.
        In production, use NOAA's PointCast data or similar marine-specific sources.
        """
        if not self._noaa_key:
            raise ValueError("NOAA API key not configured")

        # TODO: Implement NOAA API integration
        # For now, return empty results
        log.warning("NOAA forecast API not yet implemented, returning empty forecast")
        return [], []

    async def _fetch_noaa_current(self, lat: float, lon: float) -> WeatherConditions:
        """Fetch current conditions from NOAA/PointCast.

        Note: This is a placeholder for NOAA API integration.
        """
        if not self._noaa_key:
            raise ValueError("NOAA API key not configured")

        # TODO: Implement NOAA API integration
        log.warning("NOAA current conditions API not yet implemented")
        raise NotImplementedError("NOAA current conditions API not yet implemented")

    def clear_cache(self) -> None:
        """Clear all cached weather data."""
        self._forecast_cache.clear()
        self._conditions_cache.clear()
        log.info("Weather cache cleared")


# --------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------- #


def wind_speed_category(speed_kn: float) -> str:
    """Classify wind speed by Beaufort scale."""
    if speed_kn < 1:
        return "calm"
    elif speed_kn < 4:
        return "light_air"
    elif speed_kn < 11:
        return "light_breeze"
    elif speed_kn < 17:
        return "gentle_breeze"
    elif speed_kn < 22:
        return "moderate_breeze"
    elif speed_kn < 28:
        return "fresh_breeze"
    elif speed_kn < 34:
        return "strong_breeze"
    elif speed_kn < 41:
        return "near_gale"
    elif speed_kn < 48:
        return "gale"
    elif speed_kn < 56:
        return "strong_gale"
    elif speed_kn < 64:
        return "storm"
    else:
        return "hurricane_force"


def wave_height_category(height_m: float) -> str:
    """Classify wave height for marine operations."""
    if height_m < 0.5:
        return "calm"
    elif height_m < 1.2:
        return "light"
    elif height_m < 2.5:
        return "moderate"
    elif height_m < 4.0:
        return "rough"
    elif height_m < 6.0:
        return "very_rough"
    elif height_m < 9.0:
        return "high"
    elif height_m < 14.0:
        return "very_high"
    else:
        return "phenomenal"


def visibility_category(visibility_m: float) -> str:
    """Classify visibility for marine operations."""
    if visibility_m >= 10000:
        return "excellent"
    elif visibility_m >= 5000:
        return "good"
    elif visibility_m >= 2000:
        return "moderate"
    elif visibility_m >= 1000:
        return "poor"
    else:
        return "very_poor"


def assess_weather_conditions(
    wind_kn: float,
    wave_m: float,
    visibility_m: float,
) -> tuple[str, str]:
    """Assess overall conditions for small vessel operations.

    Returns:
        Tuple of (category, recommendation) where:
        - category: "good", "caution", "hazardous", "dangerous"
        - recommendation: Human-readable guidance
    """
    # Wind factors
    wind_cat = wind_speed_category(wind_kn)
    wind_score = 0
    if wind_kn >= 34:  # Gale force
        wind_score += 3
    elif wind_kn >= 22:  # Strong breeze
        wind_score += 2
    elif wind_kn >= 15:  # Fresh breeze
        wind_score += 1

    # Wave factors
    wave_score = 0
    if wave_m >= 4.0:  # Rough or worse
        wave_score += 3
    elif wave_m >= 2.5:  # Moderate
        wave_score += 2
    elif wave_m >= 1.2:  # Light
        wave_score += 1

    # Visibility factors
    vis_score = 0
    if visibility_m < 1000:  # Poor visibility
        vis_score += 2
    elif visibility_m < 2000:  # Moderate visibility
        vis_score += 1

    # Overall assessment
    total_score = wind_score + wave_score + vis_score

    if total_score >= 6:
        return "dangerous", "Dangerous conditions - Seek safe harbor immediately"
    elif total_score >= 4:
        return "hazardous", "Hazardous conditions - Experienced crews only with proper equipment"
    elif total_score >= 2:
        return "caution", "Use caution - Monitor conditions and be prepared to return"
    else:
        return "good", "Good conditions - Normal operations acceptable"


# --------------------------------------------------------------------- #
# Mock weather client for testing
# --------------------------------------------------------------------- #


class MockWeatherClient:
    """Mock weather client for testing without API calls."""

    def __init__(self, cache_ttl_s: int = 900) -> None:
        """Initialize mock client."""
        self._cache_ttl_s = cache_ttl_s
        self._forecast_cache: dict[str, CachedForecast] = {}
        self._conditions_cache: dict[str, tuple[WeatherConditions, int]] = {}

    async def close(self) -> None:
        """No-op for mock."""
        pass

    def _cache_key(self, lat: float, lon: float) -> str:
        """Generate cache key."""
        return f"{lat:.2f},{lon:.2f}"

    def _is_forecast_cache_valid(self, cached: CachedForecast) -> bool:
        """Check cache validity."""
        age_s = (time.time_ns() - cached.cached_at_ns) / 1e9
        return age_s < self._cache_ttl_s

    def _is_conditions_cache_valid(self, cached_at_ns: int) -> bool:
        """Check cache validity."""
        age_s = (time.time_ns() - cached_at_ns) / 1e9
        return age_s < self._cache_ttl_s

    async def fetch_forecast(
        self,
        lat: float,
        lon: float,
        hours_ahead: int = 24,
    ) -> tuple[list[WeatherForecast], list[WeatherAlert]]:
        """Fetch mock forecast."""
        cache_key = self._cache_key(lat, lon)
        if cache_key in self._forecast_cache:
            cached = self._forecast_cache[cache_key]
            if self._is_forecast_cache_valid(cached):
                return cached.forecasts, cached.alerts

        # Generate realistic mock forecast
        forecasts: list[WeatherForecast] = []
        now = time.time_ns()

        # Base conditions
        base_wind = 15.0  # knots
        base_wave = 1.2  # meters
        base_temp = 15.0  # Celsius

        for i in range(8):  # 8 points (24 hours at 3-hour intervals)
            valid_ns = now + (i * 3 * 3600 * 1_000_000_000)

            # Add some variation
            wind_var = 5.0 * (i - 4) / 4.0  # -5 to +5 knots variation
            wave_var = 0.5 * (i - 4) / 4.0  # -0.5 to +0.5m variation
            temp_var = 3.0 * (i - 4) / 4.0  # -3 to +3°C variation

            forecasts.append(WeatherForecast(
                valid_ns=valid_ns,
                wind=WindConditions(
                    speed_kn=base_wind + wind_var,
                    direction_deg=(225.0 + i * 5) % 360,
                    gust_kn=base_wind + wind_var + 8.0,
                ),
                wave=WaveConditions(
                    height_m=base_wave + wave_var,
                    period_s=7.0 + 0.5 * i,
                    direction_deg=(225.0 + i * 5) % 360,
                ),
                visibility_m=10000.0,
                air_temp_c=base_temp + temp_var,
                pressure_hpa=1013.0 - i * 0.5,
                precipitation_mm=0.0,
                condition_code="Clear",
                description="clear sky",
            ))

        alerts = []

        self._forecast_cache[cache_key] = CachedForecast(
            forecasts=forecasts,
            alerts=alerts,
            cached_at_ns=now,
            ttl_s=self._cache_ttl_s,
        )

        return forecasts, alerts

    async def get_current_conditions(self, lat: float, lon: float) -> WeatherConditions:
        """Get mock current conditions."""
        cache_key = self._cache_key(lat, lon)
        if cache_key in self._conditions_cache:
            conditions, cached_at = self._conditions_cache[cache_key]
            if self._is_conditions_cache_valid(cached_at):
                return conditions

        conditions = WeatherConditions(
            timestamp_ns=time.time_ns(),
            lat=lat,
            lon=lon,
            wind=WindConditions(
                speed_kn=15.0,
                direction_deg=225.0,
                gust_kn=23.0,
            ),
            wave=WaveConditions(
                height_m=1.2,
                period_s=7.0,
                direction_deg=225.0,
            ),
            visibility_m=10000.0,
            air_temp_c=15.0,
            pressure_hpa=1013.0,
            humidity_pct=75.0,
            precipitation_mm=0.0,
            condition_code="Clear",
            description="clear sky",
            precipitation_type=None,
            cloud_cover_pct=10.0,
        )

        self._conditions_cache[cache_key] = (conditions, time.time_ns())
        return conditions

    async def check_alerts(self, lat: float, lon: float) -> list[WeatherAlert]:
        """Check mock alerts (empty for now)."""
        forecasts, alerts = await self.fetch_forecast(lat, lon)
        return alerts

    def clear_cache(self) -> None:
        """Clear cache."""
        self._forecast_cache.clear()
        self._conditions_cache.clear()
