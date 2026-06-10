"""OBIS (Ocean Biodiversity Information System) connector.

OBIS aggregates marine species occurrence records from around the world. Its
v3 REST API is open (no token) and supports filtering occurrences by species
name and a WKT geometry, which we build as a bounding box around a lat/lon.

This is the deterministic first version of the SpeciesContextAgent from
docs/noaa_data_sources.md: "where has this species been observed near here?"
"""

import os
from typing import Any

import httpx

OBIS_OCCURRENCE_URL = "https://api.obis.org/v3/occurrence"
OBIS_CHECKLIST_URL = "https://api.obis.org/v3/checklist"
HTTP_TIMEOUT_SECONDS = float(os.getenv("PELAGICSEER_HTTP_TIMEOUT_SECONDS", "300"))

OCEAN_BOUNDS = {
    "Atlantic Ocean": [(-70.0, -80.0, 80.0, 20.0)],
    "Pacific Ocean": [(-70.0, -180.0, 65.0, -70.0), (-70.0, 120.0, 65.0, 180.0)],
    "Indian Ocean": [(-60.0, 20.0, 30.0, 120.0)],
    "Southern Ocean": [(-80.0, -180.0, -60.0, 180.0)],
    "Arctic Ocean": [(65.0, -180.0, 90.0, 180.0)],
}


def _bbox_wkt(latitude: float, longitude: float, buffer_deg: float) -> str:
    """Build a WKT polygon (lon/lat order) for a square around the point."""
    min_lat, max_lat = latitude - buffer_deg, latitude + buffer_deg
    min_lon, max_lon = longitude - buffer_deg, longitude + buffer_deg
    return (
        f"POLYGON (({min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    )


def _bounds_wkt(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> str:
    """Build a WKT polygon from explicit lat/lon bounds."""
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
    startdate: str | None = None,
    enddate: str | None = None,
) -> dict[str, Any]:
    """Return OBIS occurrence records for a species near a lat/lon.

    ``total`` is the full count of matching records; ``occurrences`` is a
    sample of up to ``size`` records with the fishing-relevant fields. Also
    summarizes the observed depth and year ranges. ``startdate``/``enddate``
    (ISO ``YYYY-MM-DD``) restrict occurrences to a window when given together.
    """
    params: dict[str, Any] = {
        "scientificname": scientificname,
        "geometry": _bbox_wkt(latitude, longitude, buffer_deg),
        "size": size,
    }
    if startdate and enddate:
        params["startdate"] = startdate
        params["enddate"] = enddate

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
        "date_range": {"start": startdate, "end": enddate} if startdate and enddate else None,
        "occurrences": occurrences,
    }


def get_species_ocean_map(
    scientificname: str,
    ocean: str | None = None,
    size: int = 1000,
    precision: int = 1,
    startdate: str | None = None,
    enddate: str | None = None,
    search_rank: str = "Species",
) -> dict[str, Any]:
    """Return OBIS occurrence points aggregated for a named ocean."""
    if ocean is not None and ocean not in OCEAN_BOUNDS:
        raise ValueError(f"Unknown ocean '{ocean}'")

    requested_size = max(1, min(size, 5000))
    all_results: list[dict[str, Any]] = []
    total = 0
    search_bounds = {ocean: OCEAN_BOUNDS[ocean]} if ocean else OCEAN_BOUNDS

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        for bounds_list in search_bounds.values():
            for bounds in bounds_list:
                params = {
                    "scientificname": scientificname,
                    "geometry": _bounds_wkt(*bounds),
                    "size": requested_size,
                }
                if startdate and enddate:
                    params["startdate"] = startdate
                    params["enddate"] = enddate
                response = client.get(OBIS_OCCURRENCE_URL, params=params)
                response.raise_for_status()
                payload = response.json()
                total += payload.get("total", 0)
                all_results.extend(payload.get("results", []))

    buckets: dict[tuple[float, float], dict[str, Any]] = {}
    years: list[int] = []
    for row in all_results:
        latitude = row.get("decimalLatitude")
        longitude = row.get("decimalLongitude")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            continue

        year = row.get("date_year")
        if isinstance(year, int):
            years.append(year)

        key = (round(float(latitude), precision), round(float(longitude), precision))
        bucket = buckets.setdefault(
            key,
            {
                "latitude": key[0],
                "longitude": key[1],
                "occurrences": 0,
                "scientific_name": row.get("scientificName") or scientificname,
            },
        )
        bucket["occurrences"] += 1

    points = sorted(buckets.values(), key=lambda p: p["occurrences"], reverse=True)
    max_occurrences = max((point["occurrences"] for point in points), default=0)
    for point in points:
        point["radius_m"] = 25000 + (point["occurrences"] / max_occurrences) * 175000 if max_occurrences else 25000

    return {
        "source": "obis",
        "scientificname": scientificname,
        "search_rank": search_rank,
        "ocean": ocean,
        "search_area": ocean or "All oceans",
        "total": total,
        "returned": len(all_results),
        "point_count": len(points),
        "date_range": {"start": startdate, "end": enddate} if startdate and enddate else None,
        "year_range": {"min": min(years), "max": max(years)} if years else None,
        "points": points,
    }


def get_area_species(
    latitude: float,
    longitude: float,
    buffer_deg: float = 2.0,
    startdate: str | None = None,
    enddate: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """Return the species observed in a box around a lat/lon, ranked by records.

    Answers "what's here?" rather than "is *this* species here?": queries the
    OBIS checklist endpoint for everything recorded in the bounding box and
    returns the most-recorded taxa. ``startdate``/``enddate`` (ISO) restrict the
    window when given together.
    """
    params: dict[str, Any] = {"geometry": _bbox_wkt(latitude, longitude, buffer_deg)}
    if startdate and enddate:
        params["startdate"] = startdate
        params["enddate"] = enddate

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.get(OBIS_CHECKLIST_URL, params=params)
        response.raise_for_status()

    payload = response.json()
    results = payload.get("results", [])

    species: list[dict[str, Any]] = []
    for row in results:
        scientific_name = row.get("scientificName")
        if not scientific_name:
            continue
        species.append(
            {
                "scientific_name": scientific_name,
                "records": row.get("records", 0),
                "taxon_rank": row.get("taxonRank"),
            }
        )

    species.sort(key=lambda item: item.get("records", 0), reverse=True)

    return {
        "source": "obis",
        "latitude": latitude,
        "longitude": longitude,
        "buffer_deg": buffer_deg,
        "date_range": {"start": startdate, "end": enddate} if startdate and enddate else None,
        "total_species": len(species),
        "species": species[:limit],
    }
