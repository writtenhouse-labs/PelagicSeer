"""NOAA NCEI bathymetry connector.

Uses the public ETOPO 2022 ArcGIS ImageServer to sample seafloor elevation at
and around a point. Negative elevation means water depth below mean sea level.
"""

import os
from typing import Any

import httpx


ETOPO_IMAGE_SERVER_URL = os.getenv(
    "ETOPO_IMAGE_SERVER_URL",
    "https://gis.ngdc.noaa.gov/arcgis/rest/services/DEM_mosaics/DEM_global_mosaic/ImageServer",
).rstrip("/")
HTTP_TIMEOUT_SECONDS = float(os.getenv("PELAGICSEER_HTTP_TIMEOUT_SECONDS", "15"))
_M_TO_FT = 3.28084


def _sample_elevation(latitude: float, longitude: float) -> float:
    geometry = {
        "x": longitude,
        "y": latitude,
        "spatialReference": {"wkid": 4326},
    }
    params = {
        "f": "json",
        "geometry": geometry,
        "geometryType": "esriGeometryPoint",
        "returnGeometry": "false",
        "returnCatalogItems": "false",
    }
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = client.get(f"{ETOPO_IMAGE_SERVER_URL}/identify", params=params)
        response.raise_for_status()
    payload = response.json()
    value = payload.get("value")
    if value in (None, "NoData"):
        raise ValueError("ETOPO did not return an elevation value for this point")
    return float(value)


def _structure_label(depth_m: float, relief_m: float) -> str:
    if depth_m <= 0:
        return "land"
    if relief_m >= 200:
        return "strong_depth_break"
    if relief_m >= 60:
        return "moderate_depth_break"
    if 30 <= depth_m <= 250:
        return "shelf_or_nearshore"
    if depth_m >= 1000:
        return "deep_water"
    return "gradual_bottom"


def get_bathymetry_context(
    latitude: float,
    longitude: float,
    sample_offset_deg: float = 0.05,
) -> dict[str, Any]:
    """Return depth and nearby relief context from NOAA ETOPO 2022."""
    center_elevation_m = _sample_elevation(latitude, longitude)
    offsets = [
        ("center", latitude, longitude, center_elevation_m),
        ("north", latitude + sample_offset_deg, longitude, _sample_elevation(latitude + sample_offset_deg, longitude)),
        ("south", latitude - sample_offset_deg, longitude, _sample_elevation(latitude - sample_offset_deg, longitude)),
        ("east", latitude, longitude + sample_offset_deg, _sample_elevation(latitude, longitude + sample_offset_deg)),
        ("west", latitude, longitude - sample_offset_deg, _sample_elevation(latitude, longitude - sample_offset_deg)),
    ]
    elevations = [sample[3] for sample in offsets]
    depths = [max(0.0, -elevation) for elevation in elevations]
    center_depth_m = max(0.0, -center_elevation_m)
    relief_m = max(depths) - min(depths)
    slope_proxy_m_per_deg = relief_m / (sample_offset_deg * 2)
    label = _structure_label(center_depth_m, relief_m)

    return {
        "source": "noaa-ncei-etopo",
        "dataset": "ETOPO 2022 15 Arc-Second Global Relief Model",
        "latitude": latitude,
        "longitude": longitude,
        "available": True,
        "elevation_m": round(center_elevation_m, 2),
        "depth_m": round(center_depth_m, 2),
        "depth_ft": round(center_depth_m * _M_TO_FT, 1),
        "nearby_relief_m": round(relief_m, 2),
        "nearby_relief_ft": round(relief_m * _M_TO_FT, 1),
        "slope_proxy_m_per_deg": round(slope_proxy_m_per_deg, 2),
        "structure": label,
        "samples": [
            {
                "position": position,
                "latitude": sample_lat,
                "longitude": sample_lon,
                "elevation_m": round(elevation, 2),
                "depth_m": round(max(0.0, -elevation), 2),
            }
            for position, sample_lat, sample_lon, elevation in offsets
        ],
        "notes": "Negative ETOPO elevation is water depth; nearby relief is sampled at cardinal offsets.",
    }
