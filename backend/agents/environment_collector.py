"""Collects live environmental conditions for a lat/lon from NOAA sources.

This is the deterministic first version of the EnvironmentCollectorAgent from
docs/noaa_data_sources.md. Given a location it gathers satellite SST (ERDDAP)
and the nearest buoy's wave/wind/pressure (NDBC), normalizes everything into a
single english-unit conditions dict, and records where each value came from.

Every source is fetched independently and failures are swallowed per-source so
that /advice can degrade gracefully and report confidence rather than erroring
when one offshore API is unavailable.
"""

from typing import Any

import httpx

from connectors.noaa_erddap import get_erddap_sst, get_mock_conditions
from connectors.noaa_ndbc import find_nearest_ndbc_stations, get_latest_ndbc_observation

# Canonical fields the fishing advisor scores against.
CONDITION_FIELDS = (
    "sea_surface_temp_f",
    "wind_speed_kts",
    "wave_height_ft",
    "barometric_pressure_mb",
    "current_speed_kts",
)

_MS_TO_KTS = 1.94384
_M_TO_FT = 3.28084


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_ndbc(observation: dict[str, Any]) -> dict[str, float]:
    """Convert raw NDBC metric fields into the english-unit condition fields."""
    fields: dict[str, float] = {}

    wvht = _to_float(observation.get("WVHT"))
    if wvht is not None:
        fields["wave_height_ft"] = round(wvht * _M_TO_FT, 1)

    wspd = _to_float(observation.get("WSPD"))
    if wspd is not None:
        fields["wind_speed_kts"] = round(wspd * _MS_TO_KTS, 1)

    pres = _to_float(observation.get("PRES"))
    if pres is not None:
        fields["barometric_pressure_mb"] = round(pres, 1)

    wtmp = _to_float(observation.get("WTMP"))
    if wtmp is not None:
        fields["sea_surface_temp_f"] = round(wtmp * 9 / 5 + 32, 1)

    return fields


def collect_conditions(latitude: float, longitude: float) -> dict[str, Any]:
    """Return normalized live conditions plus provenance for a lat/lon.

    The returned dict always contains the canonical condition fields (set to
    None when no source supplied them), a ``provenance`` map from field to
    source, a ``sources`` list of what was queried, and ``missing`` listing
    fields no source could provide.
    """
    conditions: dict[str, Any] = {field: None for field in CONDITION_FIELDS}
    provenance: dict[str, str] = {}
    sources: list[dict[str, Any]] = []

    def record(field: str, value: float | None, source: str) -> None:
        if value is not None and conditions.get(field) is None:
            conditions[field] = value
            provenance[field] = source

    # Satellite SST from ERDDAP — works at any lat/lon, so it is the primary
    # sea-surface-temperature source and is recorded before the buoy fallback.
    try:
        erddap = get_erddap_sst(latitude, longitude)
        record("sea_surface_temp_f", erddap.get("sea_surface_temp_f"), "noaa-erddap")
        sources.append(
            {
                "id": "noaa-erddap",
                "status": "ok",
                "dataset": erddap.get("dataset"),
                "observed_time": erddap.get("observed_time"),
            }
        )
    except (httpx.HTTPError, ValueError) as exc:
        sources.append({"id": "noaa-erddap", "status": "error", "detail": str(exc)})

    # Nearest NDBC buoy for waves, wind, pressure, and SST fallback. Some
    # active stations do not expose a realtime2 text feed, so try a few nearby
    # stations before marking the source unavailable.
    try:
        stations = find_nearest_ndbc_stations(latitude, longitude)
        station_errors: list[str] = []
        for station in stations:
            try:
                observation = get_latest_ndbc_observation(station["station"])["observation"]
                for field, value in _normalize_ndbc(observation).items():
                    record(field, value, "noaa-ndbc")
                sources.append(
                    {
                        "id": "noaa-ndbc",
                        "status": "ok",
                        "station": station["station"],
                        "station_name": station.get("name"),
                        "distance_nm": station.get("distance_nm"),
                    }
                )
                break
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                station_errors.append(f"{station['station']}: {exc}")
        else:
            raise ValueError("; ".join(station_errors))
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        sources.append({"id": "noaa-ndbc", "status": "error", "detail": str(exc)})

    missing = [field for field in CONDITION_FIELDS if conditions[field] is None]

    return {
        "source": "noaa-live",
        "latitude": latitude,
        "longitude": longitude,
        **conditions,
        "provenance": provenance,
        "sources": sources,
        "missing": missing,
    }


def collect_conditions_with_fallback(latitude: float, longitude: float) -> dict[str, Any]:
    """Collect live conditions, falling back to mock data if nothing was live.

    If every source failed we return the development mock so the app stays
    usable offline, clearly tagged so callers can see it is not live data.
    """
    conditions = collect_conditions(latitude, longitude)
    if len(conditions["missing"]) == len(CONDITION_FIELDS):
        mock = get_mock_conditions(latitude, longitude)
        mock["degraded_to_mock"] = True
        mock["live_sources"] = conditions["sources"]
        return mock
    return conditions
