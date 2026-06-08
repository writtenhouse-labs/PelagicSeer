from typing import Any
import os

import httpx

# CoastWatch ERDDAP griddap. jplMURSST41 is a global, daily, 0.01-degree
# analysed sea surface temperature product, queryable at any lat/lon by
# selecting the nearest grid cell.
ERDDAP_GRIDDAP_URL = (
    "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.json"
)
HTTP_TIMEOUT_SECONDS = float(os.getenv("PELAGICSEER_HTTP_TIMEOUT_SECONDS", "300"))


def _celsius_to_fahrenheit(celsius: float) -> float:
    return round(celsius * 9 / 5 + 32, 1)


def get_erddap_sst(latitude: float, longitude: float) -> dict[str, Any]:
    """Fetch the latest satellite sea surface temperature for a lat/lon.

    Queries the nearest grid cell of the most recent time slice. Raises
    ValueError if the dataset has no value at this location (common very
    close to shore, where the satellite product is masked).
    """
    # ERDDAP griddap takes its selection as the raw query string; it must be
    # appended directly rather than passed as params (which would append a
    # trailing "=" that ERDDAP rejects as an empty assignment).
    query = f"analysed_sst[(last)][({latitude})][({longitude})]"
    url = f"{ERDDAP_GRIDDAP_URL}?{query}"

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.get(url)
        response.raise_for_status()

    table = response.json().get("table", {})
    rows = table.get("rows", [])
    if not rows:
        raise ValueError("NOAA ERDDAP returned no SST for this location")

    columns = table.get("columnNames", [])
    row = dict(zip(columns, rows[0], strict=False))

    sst_c = row.get("analysed_sst")
    if sst_c is None:
        raise ValueError("NOAA ERDDAP returned no SST value at this grid cell")

    return {
        "source": "noaa-erddap",
        "dataset": "jplMURSST41",
        "latitude": latitude,
        "longitude": longitude,
        "observed_time": row.get("time"),
        "sea_surface_temp_f": _celsius_to_fahrenheit(float(sst_c)),
    }


def get_mock_conditions(latitude: float, longitude: float) -> dict:
    """Return NOAA ERDDAP-shaped mock marine conditions for local development."""
    return {
        "source": "mock-noaa-erddap",
        "latitude": latitude,
        "longitude": longitude,
        "sea_surface_temp_f": 72.4,
        "wind_speed_kts": 9.0,
        "wave_height_ft": 2.1,
        "barometric_pressure_mb": 1016.2,
        "current_speed_kts": 0.8,
        "visibility_nm": 8.5,
    }
