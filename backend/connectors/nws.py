"""NOAA National Weather Service (api.weather.gov) connector.

The NWS API is the forecast source behind the temporal router's *forecast* mode:
for a future window we want a real wind/wave/temperature outlook rather than a
stale "latest observation" proxy. It is open (no token) but requires a
descriptive ``User-Agent`` header, and only covers U.S. points — locations
outside coverage raise ValueError so callers degrade gracefully.

Flow: ``/points/{lat},{lon}`` resolves a coordinate to its forecast office and
grid, exposing a 12-hour ``forecast`` (wind, temperature, narrative) and a raw
``forecastGridData`` grid (which carries ``waveHeight`` for coastal/marine
cells). We read the period/value covering the requested target date.
"""

import os
import re
from datetime import date
from typing import Any

import httpx

NWS_BASE_URL = "https://api.weather.gov"
HTTP_TIMEOUT_SECONDS = float(os.getenv("PELAGICSEER_HTTP_TIMEOUT_SECONDS", "15"))
# NWS blocks requests without a descriptive User-Agent; make it overridable.
_USER_AGENT = os.getenv(
    "PELAGICSEER_NWS_USER_AGENT",
    "PelagicSeer/1.0 (fishing advisor; https://github.com/Writtenhouse-Labs/PelagicSeer)",
)
_HEADERS = {"User-Agent": _USER_AGENT, "Accept": "application/geo+json"}

_MPH_TO_KTS = 0.868976
_M_TO_FT = 3.28084


def _get(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, headers=_HEADERS, follow_redirects=True) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
    return response.json()


def _parse_wind_kts(wind_speed: str | None) -> float | None:
    """NWS reports wind like ``"10 mph"`` or ``"5 to 10 mph"``; take the high end."""
    numbers = [int(n) for n in re.findall(r"\d+", wind_speed or "")]
    if not numbers:
        return None
    return round(max(numbers) * _MPH_TO_KTS, 1)


def get_nws_point(latitude: float, longitude: float) -> dict[str, Any]:
    """Resolve a coordinate to its NWS forecast metadata (office, grid, URLs)."""
    payload = _get(f"{NWS_BASE_URL}/points/{latitude:.4f},{longitude:.4f}")
    properties = payload.get("properties", {})
    if not properties.get("forecast"):
        raise ValueError("NWS has no forecast grid for this location (likely outside U.S. coverage)")
    return properties


def _select_period(periods: list[dict[str, Any]], target_date: date | None) -> dict[str, Any]:
    """Pick the forecast period for the target date (prefer daytime), else soonest."""
    if target_date is None:
        return periods[0]
    iso = target_date.isoformat()
    daytime = [p for p in periods if (p.get("startTime") or "")[:10] == iso and p.get("isDaytime")]
    if daytime:
        return daytime[0]
    same_day = [p for p in periods if (p.get("startTime") or "")[:10] == iso]
    if same_day:
        return same_day[0]
    return periods[0]


def get_nws_forecast(
    latitude: float,
    longitude: float,
    target_date: date | None = None,
) -> dict[str, Any]:
    """Return the NWS wind/temperature/narrative forecast for a point.

    Selects the 12-hour period covering ``target_date`` (preferring daytime),
    or the soonest period when no date is given. Raises ValueError outside U.S.
    coverage or when no periods are returned.
    """
    properties = get_nws_point(latitude, longitude)
    forecast = _get(properties["forecast"])
    periods = forecast.get("properties", {}).get("periods", [])
    if not periods:
        raise ValueError("NWS returned no forecast periods")

    period = _select_period(periods, target_date)
    air_temp_f = period.get("temperature") if period.get("temperatureUnit") == "F" else None
    return {
        "source": "nws-forecast",
        "forecast_office": properties.get("gridId"),
        "forecast_time": period.get("startTime"),
        "period_name": period.get("name"),
        "is_daytime": period.get("isDaytime"),
        "wind_speed_kts": _parse_wind_kts(period.get("windSpeed")),
        "wind_direction": period.get("windDirection"),
        "air_temp_f": air_temp_f,
        "short_forecast": period.get("shortForecast"),
        "periods_available": len(periods),
    }


def _select_grid_value(values: list[dict[str, Any]], target_date: date | None) -> dict[str, Any] | None:
    """Pick a gridpoint time-series entry covering the target date.

    Grid ``validTime`` looks like ``"2026-07-01T18:00:00+00:00/PT6H"``; we match
    on the start date and fall back to the first entry.
    """
    usable = [v for v in values if v.get("value") is not None]
    if not usable:
        return None
    if target_date is None:
        return usable[0]
    iso = target_date.isoformat()
    same_day = [v for v in usable if (v.get("validTime") or "")[:10] == iso]
    return same_day[0] if same_day else usable[0]


def get_nws_marine_wave(
    latitude: float,
    longitude: float,
    target_date: date | None = None,
) -> dict[str, Any]:
    """Return the forecast significant wave height (ft) for a coastal point.

    Reads ``waveHeight`` from the raw forecast grid, which is only populated for
    coastal/marine cells — inland points raise ValueError.
    """
    properties = get_nws_point(latitude, longitude)
    grid_url = properties.get("forecastGridData")
    if not grid_url:
        raise ValueError("NWS point has no forecast grid data")

    grid = _get(grid_url).get("properties", {})
    wave = grid.get("waveHeight") or {}
    chosen = _select_grid_value(wave.get("values", []), target_date)
    if chosen is None:
        raise ValueError("NWS forecast grid has no wave height (likely an inland point)")
    return {
        "source": "nws-forecast",
        "wave_height_ft": round(float(chosen["value"]) * _M_TO_FT, 1),
        "valid_time": chosen.get("validTime"),
    }
