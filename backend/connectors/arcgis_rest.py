"""Generic ArcGIS REST connector.

Many NOAA datasets discovered through InPort (notably DisMAP) are published as
ArcGIS REST Feature/Map services. This connector speaks just enough of the
ArcGIS REST protocol to describe a service's layers and run a ``/query`` against
one layer, returning plain feature dicts.

It is deliberately dataset-agnostic: callers pass a fully-qualified service or
layer URL (typically resolved from the pinned InPort registry) plus a where
clause / spatial envelope. ArcGIS error payloads are raised as ValueError so
callers can degrade gracefully.
"""

import os
from typing import Any

import httpx

HTTP_TIMEOUT_SECONDS = float(os.getenv("PELAGICSEER_HTTP_TIMEOUT_SECONDS", "300"))

# WGS84; the spatial reference our lat/lon envelopes are expressed in.
WGS84_WKID = 4326


def _request_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET a JSON document from an ArcGIS REST endpoint.

    Raises ValueError if ArcGIS returns an ``error`` payload (it answers 200
    with an error body rather than an HTTP error code).
    """
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.get(url, params=params)
        response.raise_for_status()

    payload = response.json()
    if isinstance(payload, dict) and "error" in payload:
        error = payload["error"]
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise ValueError(f"ArcGIS REST error: {message}")
    return payload


def describe_arcgis_service(service_url: str) -> dict[str, Any]:
    """Return a service's layer/table listing (id + name)."""
    payload = _request_json(service_url, {"f": "json"})
    layers = [
        {"id": layer.get("id"), "name": layer.get("name")}
        for layer in payload.get("layers", [])
    ]
    tables = [
        {"id": table.get("id"), "name": table.get("name")}
        for table in payload.get("tables", [])
    ]
    return {
        "source": "arcgis-rest",
        "service_url": service_url,
        "layers": layers,
        "tables": tables,
    }


def _envelope(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> str:
    """ArcGIS esriGeometryEnvelope JSON string (xmin/ymin/xmax/ymax)."""
    return (
        f'{{"xmin":{min_lon},"ymin":{min_lat},"xmax":{max_lon},"ymax":{max_lat},'
        f'"spatialReference":{{"wkid":{WGS84_WKID}}}}}'
    )


def query_arcgis_layer(
    layer_url: str,
    where: str = "1=1",
    out_fields: str = "*",
    envelope: tuple[float, float, float, float] | None = None,
    result_record_count: int | None = None,
    order_by: str | None = None,
    return_geometry: bool = False,
) -> dict[str, Any]:
    """Query a single ArcGIS REST layer and return its features.

    ``envelope`` is an optional ``(min_lat, min_lon, max_lat, max_lon)`` spatial
    filter in WGS84. Returns the raw ``attributes`` (and geometry when asked)
    for each feature, plus the count.
    """
    params: dict[str, Any] = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "true" if return_geometry else "false",
        "f": "json",
    }
    if envelope is not None:
        params["geometry"] = _envelope(*envelope)
        params["geometryType"] = "esriGeometryEnvelope"
        params["spatialRel"] = "esriSpatialRelIntersects"
        params["inSR"] = WGS84_WKID
    if result_record_count is not None:
        params["resultRecordCount"] = result_record_count
    if order_by is not None:
        params["orderByFields"] = order_by

    payload = _request_json(f"{layer_url}/query", params)
    raw_features = payload.get("features", [])
    features = [
        {
            "attributes": feature.get("attributes", {}),
            **({"geometry": feature.get("geometry")} if return_geometry else {}),
        }
        for feature in raw_features
    ]
    return {
        "source": "arcgis-rest",
        "layer_url": layer_url,
        "returned": len(features),
        "exceeded_transfer_limit": bool(payload.get("exceededTransferLimit", False)),
        "features": features,
    }
