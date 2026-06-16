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
from connectors.noaa_ncei import get_ncei_temperature_anomaly
from connectors.noaa_ndbc import find_nearest_ndbc_stations, get_latest_ndbc_observation
from connectors.nws import get_nws_forecast, get_nws_marine_wave
from services.integration_logging import integration_span

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


def _ndbc_observed_time(observation: dict[str, Any]) -> str | None:
    year = observation.get("YY") or observation.get("#YY")
    month = observation.get("MM")
    day = observation.get("DD")
    hour = observation.get("hh")
    minute = observation.get("mm")
    if not all((year, month, day, hour, minute)):
        return None
    return f"{year}-{month}-{day} {hour}:{minute} UTC"


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
        with integration_span(
            "noaa-erddap",
            "sst",
            latitude=latitude,
            longitude=longitude,
            target_date=target_date,
        ) as span:
            erddap = get_erddap_sst(latitude, longitude, target_date=target_date)
            span.add(
                dataset=erddap.get("dataset"),
                observed_time=erddap.get("observed_time"),
                fields_returned=int(erddap.get("sea_surface_temp_f") is not None),
            )
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
        with integration_span(
            "noaa-erddap",
            "chlorophyll",
            latitude=latitude,
            longitude=longitude,
            target_date=target_date,
        ) as span:
            chla = get_erddap_chlorophyll(latitude, longitude, target_date=target_date)
            span.add(
                dataset=chla.get("dataset"),
                observed_time=chla.get("observed_time"),
                fields_returned=int(chla.get("chlorophyll_mg_m3") is not None),
            )
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

    # Future window: pull the NWS forecast for the target day and record wind
    # and (coastal) wave height *before* the buoy step so forecast values win
    # over stale latest observations. SST has no free forecast, so it stays the
    # ERDDAP latest proxy above. Air temp and the narrative are extra context.
    forecast_date = plan.target_date if (plan is not None and plan.mode == "forecast") else None
    if forecast_date is not None:
        try:
            with integration_span(
                "nws",
                "forecast",
                latitude=latitude,
                longitude=longitude,
                target_date=forecast_date,
            ) as span:
                forecast = get_nws_forecast(latitude, longitude, target_date=forecast_date)
                span.add(
                    forecast_office=forecast.get("forecast_office"),
                    forecast_time=forecast.get("forecast_time"),
                    fields_returned=sum(
                        value is not None
                        for value in (
                            forecast.get("wind_speed_kts"),
                            forecast.get("air_temp_f"),
                            forecast.get("short_forecast"),
                        )
                    ),
                )
            record("wind_speed_kts", forecast.get("wind_speed_kts"), "nws-forecast")
            if forecast.get("air_temp_f") is not None:
                conditions["air_temp_f"] = forecast["air_temp_f"]
                provenance["air_temp_f"] = "nws-forecast"
            if forecast.get("short_forecast"):
                conditions["weather_forecast"] = forecast["short_forecast"]
            sources.append(
                {
                    "id": "nws-forecast",
                    "status": "ok",
                    "forecast_office": forecast.get("forecast_office"),
                    "forecast_time": forecast.get("forecast_time"),
                }
            )
        except (httpx.HTTPError, ValueError) as exc:
            sources.append({"id": "nws-forecast", "status": "error", "detail": str(exc)})

        try:
            with integration_span(
                "nws",
                "marine_wave",
                latitude=latitude,
                longitude=longitude,
                target_date=forecast_date,
            ) as span:
                wave = get_nws_marine_wave(latitude, longitude, target_date=forecast_date)
                span.add(
                    valid_time=wave.get("valid_time"),
                    fields_returned=int(wave.get("wave_height_ft") is not None),
                )
            record("wave_height_ft", wave.get("wave_height_ft"), "nws-forecast")
            sources.append(
                {"id": "nws-forecast-wave", "status": "ok", "valid_time": wave.get("valid_time")}
            )
        except (httpx.HTTPError, ValueError) as exc:
            sources.append({"id": "nws-forecast-wave", "status": "error", "detail": str(exc)})

    # Nearest NDBC buoy for waves, wind, pressure, and SST fallback. Some
    # active stations do not expose a realtime2 text feed, so try a few nearby
    # stations before marking the source unavailable.
    try:
        with integration_span(
            "noaa-ndbc",
            "nearest_stations",
            latitude=latitude,
            longitude=longitude,
        ) as span:
            stations = find_nearest_ndbc_stations(latitude, longitude)
            span.add(records_returned=len(stations))
        station_errors: list[str] = []
        for station in stations:
            try:
                with integration_span(
                    "noaa-ndbc",
                    "latest_observation",
                    station=station.get("station"),
                    station_name=station.get("name"),
                    distance_nm=station.get("distance_nm"),
                ) as span:
                    observation = get_latest_ndbc_observation(station["station"])["observation"]
                    span.add(
                        fields_returned=sum(value not in (None, "MM") for value in observation.values()),
                        observation_keys=len(observation),
                        observed_time=_ndbc_observed_time(observation),
                    )
                for field, value in _normalize_ndbc(observation).items():
                    record(field, value, "noaa-ndbc")
                sources.append(
                    {
                        "id": "noaa-ndbc",
                        "status": "ok",
                        "station": station["station"],
                        "station_name": station.get("name"),
                        "latitude": station.get("latitude"),
                        "longitude": station.get("longitude"),
                        "distance_nm": station.get("distance_nm"),
                        "observed_time": _ndbc_observed_time(observation),
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
            with integration_span(
                "noaa-coops",
                "nearest_stations",
                station_type=station_type,
                latitude=latitude,
                longitude=longitude,
            ) as span:
                coops_stations = find_nearest_coops_stations(
                    latitude, longitude, station_type=station_type, limit=_COOPS_STATION_TRIES
                )
                span.add(records_returned=len(coops_stations))
        except (httpx.HTTPError, ValueError) as exc:
            sources.append({"id": source_id, "status": "error", "detail": str(exc)})
            continue

        station_errors = []
        for station in coops_stations:
            try:
                with integration_span(
                    "noaa-coops",
                    "latest_observation",
                    product=product,
                    station=station.get("station"),
                    station_name=station.get("name"),
                    distance_nm=station.get("distance_nm"),
                ) as span:
                    value, observed_time = _coops_value(station["station"], product, value_key, plan)
                    span.add(observed_time=observed_time, fields_returned=int(value is not None))
                record(field, round(value, 2), "noaa-coops")
                sources.append(
                    {
                        "id": source_id,
                        "status": "ok",
                        "station": station["station"],
                        "station_name": station.get("name"),
                        "latitude": station.get("latitude"),
                        "longitude": station.get("longitude"),
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


def collect_climate_anomaly(
    latitude: float,
    longitude: float,
    plan: TemporalPlan | None = None,
) -> dict[str, Any]:
    """NCEI temperature anomaly vs. recent local climatology for the window.

    Historical-window context: how the period's temperature compares to the
    same time of year over the preceding years at the nearest land station.
    Token-gated (NOAA_NCDC_TOKEN) and makes several CDO calls, so callers should
    only invoke it off the live/forecast hot path. Degrades to
    ``{"available": False, ...}`` without a token or data.
    """
    target_date = plan.target_date if plan is not None else None
    try:
        with integration_span(
            "noaa-ncei",
            "temperature_anomaly",
            latitude=latitude,
            longitude=longitude,
            target_date=target_date,
        ) as span:
            result = get_ncei_temperature_anomaly(latitude, longitude, target_date=target_date)
            span.add(records_returned=len(result.get("daily_values", [])))
        return {"available": True, **result}
    except (httpx.HTTPError, ValueError) as exc:
        return {"available": False, "detail": str(exc)}
