"""NOAA NCEI / NCDC Climate Data Online (CDO) connector.

CDO serves historical and climatology records (the old "NCDC" name; the agency
is now NCEI). It authenticates with a plain ``token`` request header — not a
Bearer token — read from the NOAA_NCDC_TOKEN environment variable so the secret
never lives in source control.

Get a free token at https://www.ncdc.noaa.gov/cdo-web/token and set it before
running, e.g. in PowerShell:

    [Environment]::SetEnvironmentVariable('NOAA_NCDC_TOKEN', 'your-token', 'User')

Notes / CDO constraints worth knowing:
- /data requires a datasetid and a date range no longer than one year.
- Results are paged (max 1000 per call).
- GHCND (daily summaries) is land/coastal station data, useful for coastal
  climate context rather than open-ocean conditions.
"""

import math
import os
from datetime import date, timedelta
from typing import Any

import httpx

NCEI_BASE_URL = "https://www.ncdc.noaa.gov/cdo-web/api/v2"
HTTP_TIMEOUT_SECONDS = float(os.getenv("PELAGICSEER_HTTP_TIMEOUT_SECONDS", "300"))


def _token() -> str:
    token = os.environ.get("NOAA_NCDC_TOKEN")
    if not token:
        raise ValueError("NOAA_NCDC_TOKEN is not set; cannot query NOAA NCEI/CDO")
    return token


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius_km * 2 * math.asin(math.sqrt(a))


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    headers = {"token": _token()}
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.get(f"{NCEI_BASE_URL}/{path}", params=params, headers=headers)
        response.raise_for_status()
    # CDO returns an empty body (not an error) when a query has no results.
    return response.json() if response.text.strip() else {}


def get_ncei_datasets(limit: int = 25) -> dict[str, Any]:
    """List available CDO datasets. Lightweight call useful to verify the token."""
    payload = _get("datasets", {"limit": limit})
    datasets = [
        {"id": item.get("id"), "name": item.get("name")}
        for item in payload.get("results", [])
    ]
    return {"source": "noaa-ncei", "datasets": datasets}


def find_nearest_ncei_station(
    latitude: float,
    longitude: float,
    datasetid: str = "GHCND",
    buffer_deg: float = 1.0,
    active_after: date | None = None,
) -> dict[str, Any]:
    """Find the nearest CDO station to a lat/lon within a bounding box.

    When ``active_after`` is given, only stations still reporting on or after
    that date are considered (CDO returns each station's ``maxdate``). This
    avoids picking a closer-but-discontinued station that has no recent data.
    """
    extent = (
        f"{latitude - buffer_deg},{longitude - buffer_deg},"
        f"{latitude + buffer_deg},{longitude + buffer_deg}"
    )
    payload = _get(
        "stations",
        {"datasetid": datasetid, "extent": extent, "limit": 1000},
    )
    stations = payload.get("results", [])
    if not stations:
        raise ValueError("NOAA NCEI found no stations near this location")

    if active_after is not None:
        cutoff = active_after.isoformat()
        # maxdate is a "YYYY-MM-DD" string, so lexical compare matches date order.
        active = [s for s in stations if (s.get("maxdate") or "") >= cutoff]
        if not active:
            raise ValueError(
                "NOAA NCEI found nearby stations, but none reporting in the requested window"
            )
        stations = active

    nearest = min(
        stations,
        key=lambda s: _haversine_km(latitude, longitude, s["latitude"], s["longitude"]),
    )
    distance_km = _haversine_km(
        latitude, longitude, nearest["latitude"], nearest["longitude"]
    )
    return {
        "station_id": nearest.get("id"),
        "name": nearest.get("name"),
        "latitude": nearest.get("latitude"),
        "longitude": nearest.get("longitude"),
        "distance_km": round(distance_km, 1),
        "mindate": nearest.get("mindate"),
        "maxdate": nearest.get("maxdate"),
    }


def get_ncei_station_summary(
    latitude: float,
    longitude: float,
    days: int = 30,
    datatypeids: tuple[str, ...] = ("TMAX", "TMIN", "PRCP"),
    today: date | None = None,
) -> dict[str, Any]:
    """Find the nearest station and return recent daily summaries for it.

    Defaults to daily max/min air temperature and precipitation (GHCND), which
    give coastal climate context to pair with the live marine sources.
    """
    end = today or date.today()
    start = end - timedelta(days=days)
    station = find_nearest_ncei_station(
        latitude, longitude, datasetid="GHCND", active_after=start
    )
    params: dict[str, Any] = {
        "datasetid": "GHCND",
        "stationid": station["station_id"],
        "startdate": start.isoformat(),
        "enddate": end.isoformat(),
        "units": "standard",
        "limit": 1000,
    }
    # CDO accepts repeated datatypeid params; httpx serializes a list as repeats.
    params["datatypeid"] = list(datatypeids)

    payload = _get("data", params)
    observations = [
        {
            "date": row.get("date"),
            "datatype": row.get("datatype"),
            "value": row.get("value"),
        }
        for row in payload.get("results", [])
    ]

    return {
        "source": "noaa-ncei",
        "dataset": "GHCND",
        "station": station,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "record_count": len(observations),
        "observations": observations,
    }
