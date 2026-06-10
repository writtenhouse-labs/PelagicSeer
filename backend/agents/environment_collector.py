"""Collects live ocean conditions for a lat/lon from NOAA sources.

This is the OceanConditionsAgent: given a location (and an optional temporal
plan) it gathers satellite SST and chlorophyll (ERDDAP), the nearest buoy's
wave/wind/pressure (NDBC), and the nearest CO-OPS stations' currents, water
level, and salinity, then normalizes everything into a single english-unit
conditions dict and records where each value came from.

Every source is fetched independently and failures are swallowed per-source so
that /advice can degrade gracefully and report confidence rather than erroring
when one offshore API is unavailable. When the temporal plan is historical the
collectors query the relevant past day instead of the latest observation.
"""

from datetime import date, timedelta
from typing import Any

import httpx

from agents.temporal_router import TemporalPlan
from connectors.noaa_coops import (
    find_nearest_coops_stations,
    get_coops_observations,
    get_latest_coops_observation,
)
from connectors.noaa_erddap import get_erddap_chlorophyll, get_erddap_sst, get_mock_conditions
from connectors.noaa_ndbc import find_nearest_ndbc_stations, get_latest_ndbc_observation

# Canonical fields the fishing advisor scores against.
CONDITION_FIELDS = (
    "sea_surface_temp_f",
    "wind_speed_kts",
    "wave_height_ft",
    "barometric_pressure_mb",
    "current_speed_kts",
)

# Additional ocean context reported alongside the scorable fields but not part
# of the confidence/completeness math.
EXTRA_FIELDS = (
    "chlorophyll_mg_m3",
    "water_level_ft",
    "salinity_psu",
)

# CO-OPS stations are product-specific; for each canonical/extra field we know
# which mdapi station type and datagetter product/value-key provide it.
_COOPS_SOURCES = (
    # (station_type, product, value_key, target_field)
    ("currents", "currents", "s", "current_speed_kts"),
    ("waterlevels", "water_level", "v", "water_level_ft"),
    ("physocean", "salinity", "s", "salinity_psu"),
)
_COOPS_STATION_TRIES = 3
_COOPS_HISTORICAL_LOOKBACK_DAYS = 3

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


def _coops_value(
    station: str,
    product: str,
    value_key: str,
    plan: TemporalPlan | None,
) -> tuple[float, str | None]:
    """Return the most recent (value, observed_time) for a CO-OPS station/product.

    Pulls a short historical window ending at the plan's target date when the
    plan is historical, otherwise the single latest observation.
    """
    if plan is not None and plan.mode == "historical":
        window_start = plan.target_date - timedelta(days=_COOPS_HISTORICAL_LOOKBACK_DAYS)
        rows = get_coops_observations(station, product, window_start, plan.target_date)["observations"]
    else:
        rows = [get_latest_coops_observation(station, product)["observation"]]

    for row in reversed(rows):
        value = _to_float(row.get(value_key))
        if value is not None:
            return value, row.get("t")
    raise ValueError(f"no parseable {product} value at station {station}")


def collect_conditions(
    latitude: float,
    longitude: float,
    plan: TemporalPlan | None = None,
) -> dict[str, Any]:
    """Return normalized conditions plus provenance for a lat/lon.

    The returned dict always contains the canonical condition fields (set to
    None when no source supplied them), any available extra ocean context, a
    ``provenance`` map from field to source, a ``sources`` list of what was
    queried, and ``missing`` listing canonical fields no source could provide.
    When ``plan`` is historical, gridded and station sources query the relevant
    past day rather than the latest observation.
    """
    conditions: dict[str, Any] = {field: None for field in CONDITION_FIELDS}
    provenance: dict[str, str] = {}
    sources: list[dict[str, Any]] = []
    target_date = plan.target_date if (plan is not None and plan.mode == "historical") else None

    def record(field: str, value: float | None, source: str) -> None:
        if value is not None and conditions.get(field) is None:
            conditions[field] = value
            provenance[field] = source

    # Satellite SST from ERDDAP — works at any lat/lon, so it is the primary
    # sea-surface-temperature source and is recorded before the buoy fallback.
    try:
        erddap = get_erddap_sst(latitude, longitude, target_date=target_date)
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

    # Satellite chlorophyll-a from ERDDAP — productivity proxy, extra context.
    try:
        chla = get_erddap_chlorophyll(latitude, longitude, target_date=target_date)
        record("chlorophyll_mg_m3", chla.get("chlorophyll_mg_m3"), "noaa-erddap")
        sources.append(
            {
                "id": "noaa-erddap-chla",
                "status": "ok",
                "dataset": chla.get("dataset"),
                "observed_time": chla.get("observed_time"),
            }
        )
    except (httpx.HTTPError, ValueError) as exc:
        sources.append({"id": "noaa-erddap-chla", "status": "error", "detail": str(exc)})

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

    # CO-OPS stations for currents, water level/tide, and salinity. Each product
    # lives at a different station type, so we resolve and try the nearest few
    # of each before giving up on that product.
    for station_type, product, value_key, field in _COOPS_SOURCES:
        source_id = f"noaa-coops:{product}"
        if conditions.get(field) is not None:
            continue
        try:
            coops_stations = find_nearest_coops_stations(
                latitude, longitude, station_type=station_type, limit=_COOPS_STATION_TRIES
            )
        except (httpx.HTTPError, ValueError) as exc:
            sources.append({"id": source_id, "status": "error", "detail": str(exc)})
            continue

        station_errors = []
        for station in coops_stations:
            try:
                value, observed_time = _coops_value(station["station"], product, value_key, plan)
                record(field, round(value, 2), "noaa-coops")
                sources.append(
                    {
                        "id": source_id,
                        "status": "ok",
                        "station": station["station"],
                        "station_name": station.get("name"),
                        "distance_nm": station.get("distance_nm"),
                        "observed_time": observed_time,
                    }
                )
                break
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                station_errors.append(f"{station['station']}: {exc}")
        else:
            sources.append({"id": source_id, "status": "error", "detail": "; ".join(station_errors)})

    missing = [field for field in CONDITION_FIELDS if conditions[field] is None]

    result: dict[str, Any] = {
        "source": "noaa-live",
        "latitude": latitude,
        "longitude": longitude,
        **conditions,
        "provenance": provenance,
        "sources": sources,
        "missing": missing,
    }
    if plan is not None:
        result["temporal_mode"] = plan.mode
        result["target_date"] = plan.target_date.isoformat()
    return result


def collect_conditions_with_fallback(
    latitude: float,
    longitude: float,
    plan: TemporalPlan | None = None,
) -> dict[str, Any]:
    """Collect conditions, falling back to mock data if nothing was live.

    If every canonical field is missing we return the development mock so the
    app stays usable offline, clearly tagged so callers can see it is not live
    data.
    """
    conditions = collect_conditions(latitude, longitude, plan=plan)
    if len(conditions["missing"]) == len(CONDITION_FIELDS):
        mock = get_mock_conditions(latitude, longitude)
        mock["degraded_to_mock"] = True
        mock["live_sources"] = conditions["sources"]
        if plan is not None:
            mock["temporal_mode"] = plan.mode
        return mock
    return conditions
