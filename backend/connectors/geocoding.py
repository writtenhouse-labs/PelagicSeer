from typing import Any
import os

import httpx


NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "PelagicSeer local development"
HTTP_TIMEOUT_SECONDS = float(os.getenv("PELAGICSEER_HTTP_TIMEOUT_SECONDS", "15"))


def geocode_city_state(city: str, state: str) -> dict[str, Any]:
    """Resolve a US city/state pair to coordinates."""
    params = {
        "city": city.strip(),
        "state": state.strip(),
        "country": "USA",
        "format": "jsonv2",
        "limit": 1,
    }
    headers = {"User-Agent": USER_AGENT}

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, headers=headers) as client:
        response = client.get(NOMINATIM_SEARCH_URL, params=params)
        response.raise_for_status()

    results = response.json()
    if not results:
        raise ValueError(f"Could not find coordinates for {city}, {state}")

    match = results[0]
    return {
        "city": city.strip(),
        "state": state.strip(),
        "latitude": float(match["lat"]),
        "longitude": float(match["lon"]),
        "display_name": match.get("display_name"),
    }
