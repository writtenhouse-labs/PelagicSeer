"""OBIS (Ocean Biodiversity Information System) connector.

OBIS aggregates marine species occurrence records from around the world. Its
v3 REST API is open (no token) and supports filtering occurrences by species
name and a WKT geometry, which we build as a bounding box around a lat/lon.

This is the deterministic first version of the SpeciesContextAgent from
docs/noaa_data_sources.md: "where has this species been observed near here?"
"""

from typing import Any
import os

import httpx

OBIS_OCCURRENCE_URL = "https://api.obis.org/v3/occurrence"
HTTP_TIMEOUT_SECONDS = float(os.getenv("PELAGICSEER_HTTP_TIMEOUT_SECONDS", "300"))


def _bbox_wkt(latitude: float, longitude: float, buffer_deg: float) -> str:
    """Build a WKT polygon (lon/lat order) for a square around the point."""
    min_lat, max_lat = latitude - buffer_deg, latitude + buffer_deg
    min_lon, max_lon = longitude - buffer_deg, longitude + buffer_deg
    return (
        f"POLYGON (({min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    )


def get_species_occurrences(
    scientificname: str,
    latitude: float,
    longitude: float,
    buffer_deg: float = 1.0,
    size: int = 100,
) -> dict[str, Any]:
    """Return OBIS occurrence records for a species near a lat/lon.

    ``total`` is the full count of matching records; ``occurrences`` is a
    sample of up to ``size`` records with the fishing-relevant fields. Also
    summarizes the observed depth and year ranges.
    """
    params = {
        "scientificname": scientificname,
        "geometry": _bbox_wkt(latitude, longitude, buffer_deg),
        "size": size,
    }

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.get(OBIS_OCCURRENCE_URL, params=params)
        response.raise_for_status()

    payload = response.json()
    results = payload.get("results", [])

    occurrences: list[dict[str, Any]] = []
    depths: list[float] = []
    years: list[int] = []
    for row in results:
        depth = row.get("depth")
        if isinstance(depth, (int, float)):
            depths.append(depth)
        year = row.get("date_year")
        if isinstance(year, int):
            years.append(year)
        occurrences.append(
            {
                "scientific_name": row.get("scientificName"),
                "latitude": row.get("decimalLatitude"),
                "longitude": row.get("decimalLongitude"),
                "depth_m": depth,
                "event_date": row.get("eventDate"),
                "year": year,
            }
        )

    return {
        "source": "obis",
        "scientificname": scientificname,
        "latitude": latitude,
        "longitude": longitude,
        "buffer_deg": buffer_deg,
        "total": payload.get("total", len(results)),
        "returned": len(occurrences),
        "depth_range_m": {"min": min(depths), "max": max(depths)} if depths else None,
        "year_range": {"min": min(years), "max": max(years)} if years else None,
        "occurrences": occurrences,
    }
