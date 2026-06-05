import math
from typing import Any
from xml.etree import ElementTree

import httpx


NDBC_REALTIME_URL = "https://www.ndbc.noaa.gov/data/realtime2/{station}.txt"
NDBC_ACTIVE_STATIONS_URL = "https://www.ndbc.noaa.gov/activestations.xml"

# Parsed station list is cached for the process lifetime; the active-station
# roster changes rarely and the file is ~1 MB, so we avoid refetching per call.
_station_cache: list[dict[str, Any]] | None = None


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in nautical miles."""
    radius_nm = 3440.065
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius_nm * 2 * math.asin(math.sqrt(a))


def load_active_stations() -> list[dict[str, Any]]:
    """Fetch and cache the NDBC active-station roster with coordinates."""
    global _station_cache
    if _station_cache is not None:
        return _station_cache

    with httpx.Client(timeout=20) as client:
        response = client.get(NDBC_ACTIVE_STATIONS_URL)
        response.raise_for_status()

    root = ElementTree.fromstring(response.text)
    stations: list[dict[str, Any]] = []
    for element in root.findall("station"):
        lat, lon = element.get("lat"), element.get("lon")
        station_id = element.get("id")
        if not (station_id and lat and lon):
            continue
        stations.append(
            {
                "station": station_id.upper(),
                "name": element.get("name"),
                "latitude": float(lat),
                "longitude": float(lon),
                "type": element.get("type"),
            }
        )

    if not stations:
        raise ValueError("NOAA NDBC active-station list was empty")

    _station_cache = stations
    return stations


def find_nearest_ndbc_station(latitude: float, longitude: float) -> dict[str, Any]:
    """Return the active NDBC station closest to the given lat/lon."""
    stations = load_active_stations()
    nearest = min(
        stations,
        key=lambda s: _haversine_nm(latitude, longitude, s["latitude"], s["longitude"]),
    )
    distance_nm = _haversine_nm(
        latitude, longitude, nearest["latitude"], nearest["longitude"]
    )
    return {**nearest, "distance_nm": round(distance_nm, 1)}


def get_latest_ndbc_observation(station: str) -> dict[str, Any]:
    url = NDBC_REALTIME_URL.format(station=station.upper())

    with httpx.Client(timeout=15) as client:
        response = client.get(url)
        response.raise_for_status()

    lines = [line.strip() for line in response.text.splitlines() if line.strip()]
    if len(lines) < 3:
        raise ValueError("NOAA NDBC returned no realtime observations for this station")

    headers = lines[0].lstrip("#").split()
    values = lines[2].split()
    observation = {
        key: None if value == "MM" else value
        for key, value in zip(headers, values, strict=False)
    }

    return {
        "source": "noaa-ndbc",
        "station": station.upper(),
        "observation": observation,
    }
