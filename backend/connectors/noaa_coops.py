"""NOAA CO-OPS (Tides and Currents) connector.

CO-OPS serves station-based near-real-time and historical observations: water
level/tide, currents, water temperature, salinity, wind, and barometric
pressure. Stations are sparse and product-specific (a currents station is not
the same as a water-level station), so this connector also resolves the nearest
station *of a given type* via the CO-OPS metadata API (mdapi) before fetching.

All HTTP failures and CO-OPS error payloads raise so callers can degrade
gracefully and report which source was unavailable.
"""

import math
import os
from datetime import date
from typing import Any

import httpx


COOPS_DATA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
COOPS_MDAPI_STATIONS_URL = (
    "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
)
HTTP_TIMEOUT_SECONDS = float(os.getenv("PELAGICSEER_HTTP_TIMEOUT_SECONDS", "300"))

# datagetter products that carry a vertical datum; sending datum for the others
# (currents, salinity, wind, ...) is unnecessary and can be rejected.
_DATUM_PRODUCTS = {"water_level", "predictions", "hourly_height", "high_low"}


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in nautical miles."""
    radius_nm = 3440.065
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius_nm * 2 * math.asin(math.sqrt(a))


def find_nearest_coops_stations(
    latitude: float,
    longitude: float,
    station_type: str = "waterlevels",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return the nearest CO-OPS stations of a given type, closest first.

    ``station_type`` is an mdapi station type, e.g. ``waterlevels``,
    ``currents``, or ``physocean`` (physical oceanography: water temperature,
    salinity/conductivity). Raises ValueError if no stations are listed.
    """
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.get(COOPS_MDAPI_STATIONS_URL, params={"type": station_type})
        response.raise_for_status()

    stations = response.json().get("stations", [])
    located: list[dict[str, Any]] = []
    for station in stations:
        lat, lon = station.get("lat"), station.get("lng")
        station_id = station.get("id")
        if station_id is None or lat is None or lon is None:
            continue
        located.append(
            {
                "station": str(station_id),
                "name": station.get("name"),
                "latitude": float(lat),
                "longitude": float(lon),
                "distance_nm": round(_haversine_nm(latitude, longitude, float(lat), float(lon)), 1),
            }
        )

    if not located:
        raise ValueError(f"NOAA CO-OPS listed no '{station_type}' stations")

    located.sort(key=lambda s: s["distance_nm"])
    return located[:limit]


def _request_observations(params: dict[str, Any]) -> list[dict[str, Any]]:
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.get(COOPS_DATA_URL, params=params)
        response.raise_for_status()

    payload = response.json()
    if "error" in payload:
        raise ValueError(payload["error"].get("message", "NOAA CO-OPS returned an error"))

    # Currents come back under "data"; predictions under "predictions".
    data = payload.get("data") or payload.get("predictions") or []
    if not data:
        raise ValueError("NOAA CO-OPS returned no observations for this request")
    return data


def get_latest_coops_observation(
    station: str,
    product: str,
    units: str = "english",
    time_zone: str = "gmt",
) -> dict[str, Any]:
    """Fetch the single most recent observation for a station/product."""
    params: dict[str, Any] = {
        "station": station,
        "product": product,
        "date": "latest",
        "time_zone": time_zone,
        "units": units,
        "format": "json",
        "application": "PelagicSeer",
    }
    if product in _DATUM_PRODUCTS:
        params["datum"] = "MLLW"

    data = _request_observations(params)
    return {
        "source": "noaa-coops",
        "station": station,
        "product": product,
        "units": units,
        "time_zone": time_zone,
        "observation": data[0],
    }


def get_coops_observations(
    station: str,
    product: str,
    begin_date: date,
    end_date: date,
    units: str = "english",
    time_zone: str = "gmt",
) -> dict[str, Any]:
    """Fetch observations for a station/product over a date range.

    Returns every row CO-OPS provides for the window (its 6-min/hourly series),
    so callers can take the most recent reading or summarize the window.
    """
    params: dict[str, Any] = {
        "station": station,
        "product": product,
        "begin_date": begin_date.strftime("%Y%m%d"),
        "end_date": end_date.strftime("%Y%m%d"),
        "time_zone": time_zone,
        "units": units,
        "format": "json",
        "application": "PelagicSeer",
    }
    if product in _DATUM_PRODUCTS:
        params["datum"] = "MLLW"

    data = _request_observations(params)
    return {
        "source": "noaa-coops",
        "station": station,
        "product": product,
        "units": units,
        "time_zone": time_zone,
        "date_range": {"start": begin_date.isoformat(), "end": end_date.isoformat()},
        "observations": data,
    }
