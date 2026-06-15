from datetime import date
from typing import Any
import os

import httpx

# CoastWatch ERDDAP griddap. jplMURSST41 is a global, daily, 0.01-degree
# analysed sea surface temperature product, queryable at any lat/lon by
# selecting the nearest grid cell.
ERDDAP_SST_URL = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.json"
# Backwards-compatible alias for the original name.
ERDDAP_GRIDDAP_URL = ERDDAP_SST_URL

# erdMH1chla8day is a global MODIS-Aqua 8-day composite chlorophyll-a product.
# The 8-day composite is used (rather than the 1-day) because daily ocean-color
# is heavily cloud-masked, so a point lookup more often returns a real value.
# Chlorophyll is a productivity proxy: it tracks the plankton that feed the
# bait that feeds pelagic gamefish.
ERDDAP_CHLA_URL = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/erdMH1chla8day.json"

HTTP_TIMEOUT_SECONDS = float(os.getenv("PELAGICSEER_ERDDAP_TIMEOUT_SECONDS", "20"))


def _celsius_to_fahrenheit(celsius: float) -> float:
    return round(celsius * 9 / 5 + 32, 1)


def _time_selector(target_date: date | None) -> str:
    """ERDDAP time index: the latest slice, or the slice nearest a date."""
    return "last" if target_date is None else f"({target_date.isoformat()})"


def _query_griddap_point(
    base_url: str,
    variable: str,
    latitude: float,
    longitude: float,
    target_date: date | None,
) -> dict[str, Any]:
    """Sample a single ``[time][lat][lon]`` grid cell and return its row dict.

    Raises ValueError if the dataset has no value at this location/time (common
    very close to shore or under cloud cover, where the product is masked).
    """
    # The time index is bracketed as either [(last)] or [(YYYY-MM-DD)]; lat/lon
    # always carry their own parentheses. ERDDAP griddap takes its selection as
    # the raw query string appended directly (passing it as params would add a
    # trailing "=" that ERDDAP rejects as an empty assignment).
    time_index = "(last)" if target_date is None else _time_selector(target_date)
    query = f"{variable}[{time_index}][({latitude})][({longitude})]"
    url = f"{base_url}?{query}"

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.get(url)
        response.raise_for_status()

    table = response.json().get("table", {})
    rows = table.get("rows", [])
    if not rows:
        raise ValueError(f"NOAA ERDDAP returned no {variable} for this location")

    columns = table.get("columnNames", [])
    row = dict(zip(columns, rows[0], strict=False))
    if row.get(variable) is None:
        raise ValueError(f"NOAA ERDDAP returned no {variable} value at this grid cell")
    return row


def get_erddap_sst(
    latitude: float,
    longitude: float,
    target_date: date | None = None,
) -> dict[str, Any]:
    """Fetch satellite sea surface temperature for a lat/lon.

    Queries the nearest grid cell of the most recent time slice, or of the
    slice nearest ``target_date`` when given (for historical windows). Raises
    ValueError if the dataset has no value at this location/time.
    """
    row = _query_griddap_point(ERDDAP_SST_URL, "analysed_sst", latitude, longitude, target_date)
    return {
        "source": "noaa-erddap",
        "dataset": "jplMURSST41",
        "latitude": latitude,
        "longitude": longitude,
        "observed_time": row.get("time"),
        "sea_surface_temp_f": _celsius_to_fahrenheit(float(row["analysed_sst"])),
    }


def get_erddap_chlorophyll(
    latitude: float,
    longitude: float,
    target_date: date | None = None,
) -> dict[str, Any]:
    """Fetch satellite chlorophyll-a (mg/m^3) for a lat/lon.

    Uses the latest 8-day composite, or the composite nearest ``target_date``.
    Raises ValueError when the cell is masked (cloud cover / very near shore).
    """
    row = _query_griddap_point(ERDDAP_CHLA_URL, "chlorophyll", latitude, longitude, target_date)
    return {
        "source": "noaa-erddap",
        "dataset": "erdMH1chla8day",
        "latitude": latitude,
        "longitude": longitude,
        "observed_time": row.get("time"),
        "chlorophyll_mg_m3": round(float(row["chlorophyll"]), 3),
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
