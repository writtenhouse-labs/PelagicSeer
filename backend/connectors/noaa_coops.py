from typing import Any

import httpx


COOPS_DATA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"


def get_latest_coops_observation(
    station: str,
    product: str,
    units: str = "english",
    time_zone: str = "gmt",
) -> dict[str, Any]:
    params = {
        "station": station,
        "product": product,
        "date": "latest",
        "datum": "MLLW",
        "time_zone": time_zone,
        "units": units,
        "format": "json",
        "application": "PelagicSeer",
    }

    with httpx.Client(timeout=15) as client:
        response = client.get(COOPS_DATA_URL, params=params)
        response.raise_for_status()

    payload = response.json()
    if "error" in payload:
        raise ValueError(payload["error"].get("message", "NOAA CO-OPS returned an error"))

    data = payload.get("data", [])
    if not data:
        raise ValueError("NOAA CO-OPS returned no observations for this request")

    return {
        "source": "noaa-coops",
        "station": station,
        "product": product,
        "units": units,
        "time_zone": time_zone,
        "observation": data[0],
    }
