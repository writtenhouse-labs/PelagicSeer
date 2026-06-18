"""Global Fishing Watch connector.

Queries the GFW 4Wings report API for apparent fishing effort in a box around
a lat/lon. The API token is read from the GFW_API_TOKEN environment variable so
the secret never lives in source control.

Get a free token at https://globalfishingwatch.org/our-apis/tokens and set it
before running the API, e.g. in PowerShell:

    $env:GFW_API_TOKEN = "your-token-here"
"""

import os
from datetime import date, timedelta
from typing import Any

import httpx

GFW_REPORT_URL = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
GFW_EFFORT_DATASET = "public-global-fishing-effort:latest"
HTTP_TIMEOUT_SECONDS = float(os.getenv("PELAGICSEER_HTTP_TIMEOUT_SECONDS", "15"))


def _bbox_polygon(latitude: float, longitude: float, buffer_deg: float) -> dict[str, Any]:
    """Build a square GeoJSON polygon centered on the point."""
    min_lat, max_lat = latitude - buffer_deg, latitude + buffer_deg
    min_lon, max_lon = longitude - buffer_deg, longitude + buffer_deg
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def get_fishing_effort(
    latitude: float,
    longitude: float,
    buffer_deg: float = 0.5,
    days: int = 30,
    today: date | None = None,
) -> dict[str, Any]:
    """Return recent apparent fishing effort near a lat/lon.

    Raises ValueError if no GFW_API_TOKEN is configured, or if the API
    returns an error / no coverage for the requested box and window.
    """
    token = os.environ.get("GFW_API_TOKEN")
    if not token:
        raise ValueError("GFW_API_TOKEN is not set; cannot query Global Fishing Watch")

    end = today or date.today()
    start = end - timedelta(days=days)

    params = {
        "spatial-resolution": "LOW",
        "temporal-resolution": "MONTHLY",
        "datasets[0]": GFW_EFFORT_DATASET,
        "date-range": f"{start.isoformat()},{end.isoformat()}",
        "format": "JSON",
        "group-by": "FLAG",
    }
    body = {"geojson": _bbox_polygon(latitude, longitude, buffer_deg)}
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.post(GFW_REPORT_URL, params=params, json=body, headers=headers)
        response.raise_for_status()

    payload = response.json()
    entries = payload.get("entries", [])

    # The report returns one row per grid cell / month / flag. Aggregate into
    # a compact summary: total effort, a flag breakdown, and a monthly trend
    # (the monthly series doubles as a seasonality signal for fishing advice).
    total_hours = 0.0
    by_flag: dict[str, float] = {}
    by_month: dict[str, float] = {}
    record_count = 0

    for entry in entries:
        for dataset_rows in entry.values():
            for row in dataset_rows or []:
                hours = row.get("hours")
                if not isinstance(hours, (int, float)):
                    continue
                record_count += 1
                total_hours += hours
                flag = row.get("flag") or "UNKNOWN"
                by_flag[flag] = by_flag.get(flag, 0.0) + hours
                month = row.get("date") or "unknown"
                by_month[month] = by_month.get(month, 0.0) + hours

    def _rounded_sorted(mapping: dict[str, float], by_key: bool) -> dict[str, float]:
        items = sorted(mapping.items(), key=(lambda kv: kv[0]) if by_key else (lambda kv: -kv[1]))
        return {key: round(value, 1) for key, value in items}

    return {
        "source": "global-fishing-watch",
        "latitude": latitude,
        "longitude": longitude,
        "buffer_deg": buffer_deg,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "total_apparent_fishing_hours": round(total_hours, 1),
        "record_count": record_count,
        "by_flag": _rounded_sorted(by_flag, by_key=False),
        "by_month": _rounded_sorted(by_month, by_key=True),
    }
