"""NOAA Fisheries DisMAP (Distribution Mapping and Analysis Portal) connector.

DisMAP publishes the results of NOAA's fishery-independent bottom-trawl surveys
as ArcGIS REST Feature Services, one per survey region. Each region's layer
carries per-sample biomass (``WTCPUE`` — weight catch-per-unit-effort) tagged
with species, year, depth, and lat/lon, which is a real distribution and
abundance signal for survey (mostly groundfish/benthic) species.

The ArcGIS REST org base is resolved from the pinned InPort registry (or the
``PELAGICSEER_DISMAP_REST_URL`` / ``PELAGICSEER_DISMAP_SAMPLE_DATE`` env vars),
so the catalog discovery step controls which endpoint is queried. A point is
mapped to a survey region by bounding box; locations outside every DisMAP
survey region degrade with a clear message rather than erroring.
"""

import os
from typing import Any

from connectors.arcgis_rest import query_arcgis_layer

# Default ArcGIS Online org hosting the DisMAP feature services. Overridable via
# env so the pinned registry / discovery can repoint it without code changes.
DISMAP_REST_BASE = os.getenv(
    "PELAGICSEER_DISMAP_REST_URL",
    "https://services2.arcgis.com/C8EMgrsFcRFL6LrL/arcgis/rest/services",
)
# DisMAP republishes dated snapshots; the service name embeds the snapshot date.
# 20240701 is the snapshot confirmed queryable for every region's layer 1 (later
# snapshots exist but did not resolve as queryable feature layers). Override via
# env when discovery confirms a newer working snapshot.
DISMAP_SNAPSHOT = os.getenv("PELAGICSEER_DISMAP_SNAPSHOT", "20240701")

# Each DisMAP region as (code, display name, service prefix, (min_lat, min_lon,
# max_lat, max_lon)). Boxes are approximate and ordered most-specific-first so a
# point is attributed to a single region. The service prefix is the published
# feature-service name stem (some regions are season-split, e.g. WC_ANN); the
# sample-locations layer lives at id 1.
DISMAP_REGIONS: tuple[tuple[str, str, str, tuple[float, float, float, float]], ...] = (
    ("GMEX", "Gulf of Mexico", "GMEX", (24.0, -98.0, 31.0, -80.5)),
    ("SEUS", "Southeast U.S.", "SEUS_SUM", (24.0, -82.0, 35.5, -75.0)),
    ("NEUS", "Northeast U.S.", "NEUS_FAL", (35.0, -77.0, 45.5, -65.0)),
    ("WC", "U.S. West Coast", "WC_ANN", (32.0, -125.5, 49.0, -116.5)),
    ("GOA", "Gulf of Alaska", "GOA", (52.0, -170.0, 61.0, -130.0)),
    ("EBS", "Eastern Bering Sea", "EBS", (54.0, -179.0, 62.0, -157.0)),
    ("NBS", "Northern Bering Sea", "NBS", (60.0, -179.0, 66.5, -158.0)),
    ("HI", "Hawaii", "HI", (18.0, -161.0, 23.5, -154.0)),
)

_SAMPLE_LAYER_ID = 1
_OUT_FIELDS = "Species,CommonName,WTCPUE,Year,Latitude,Longitude,Depth,Region,Season"


def region_for_point(latitude: float, longitude: float) -> tuple[str, str] | None:
    """Return the (code, name) of the DisMAP region containing a point, if any."""
    for code, name, _prefix, (min_lat, min_lon, max_lat, max_lon) in DISMAP_REGIONS:
        if min_lat <= latitude <= max_lat and min_lon <= longitude <= max_lon:
            return code, name
    return None


def _service_prefix(region_code: str) -> str:
    for code, _name, prefix, _bounds in DISMAP_REGIONS:
        if code == region_code:
            return prefix
    # Unknown region code: assume the code is itself the service prefix.
    return region_code


def dismap_layer_url(region_code: str) -> str:
    """Build the ArcGIS REST layer URL for a region's sample-locations layer."""
    prefix = _service_prefix(region_code)
    return (
        f"{DISMAP_REST_BASE}/{prefix}_Sample_Locations_{DISMAP_SNAPSHOT}"
        f"/FeatureServer/{_SAMPLE_LAYER_ID}"
    )


def _summarize(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "mean": round(sum(values) / len(values), 3),
    }


def get_dismap_distribution(
    species: str,
    latitude: float,
    longitude: float,
    region: str | None = None,
    max_records: int = 500,
) -> dict[str, Any]:
    """Return DisMAP survey distribution for a species near a lat/lon.

    Resolves the survey region from the point (unless ``region`` is given),
    queries that region's layer for the species, and summarizes biomass
    (WTCPUE), depth, and year along with sample points. Raises ValueError when
    no DisMAP region covers the location.
    """
    if region is None:
        resolved = region_for_point(latitude, longitude)
        if resolved is None:
            raise ValueError("No DisMAP survey region covers this location")
        region_code, region_name = resolved
    else:
        region_code = region
        region_name = next(
            (name for code, name, _ in DISMAP_REGIONS if code == region_code), region_code
        )

    escaped = species.replace("'", "''")
    result = query_arcgis_layer(
        dismap_layer_url(region_code),
        where=f"Species = '{escaped}'",
        out_fields=_OUT_FIELDS,
        result_record_count=max_records,
        order_by="Year DESC",
    )

    points: list[dict[str, Any]] = []
    wtcpue_values: list[float] = []
    years: list[int] = []
    depths: list[float] = []
    common_name: str | None = None
    for feature in result["features"]:
        attributes = feature["attributes"]
        common_name = common_name or attributes.get("CommonName")
        wtcpue = attributes.get("WTCPUE")
        year = attributes.get("Year")
        depth = attributes.get("Depth")
        if isinstance(wtcpue, (int, float)) and wtcpue > 0:
            wtcpue_values.append(float(wtcpue))
        if isinstance(year, int):
            years.append(year)
        if isinstance(depth, (int, float)):
            depths.append(float(depth))
        points.append(
            {
                "latitude": attributes.get("Latitude"),
                "longitude": attributes.get("Longitude"),
                "wtcpue": wtcpue,
                "year": year,
                "depth_m": depth,
            }
        )

    return {
        "source": "noaa-dismap",
        "scientificname": species,
        "common_name": common_name,
        "region": region_code,
        "region_name": region_name,
        "latitude": latitude,
        "longitude": longitude,
        "returned": result["returned"],
        "present_samples": len(wtcpue_values),
        "wtcpue": _summarize(wtcpue_values),
        "depth_range_m": {"min": min(depths), "max": max(depths)} if depths else None,
        "year_range": {"min": min(years), "max": max(years)} if years else None,
        "points": points,
    }
