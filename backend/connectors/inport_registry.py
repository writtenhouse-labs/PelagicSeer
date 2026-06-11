"""Pinned NOAA InPort catalog registry.

The CatalogDiscoveryAgent searches InPort for the data dimensions PelagicSeer
cares about and classifies each item's distribution URLs by connector type.
Re-running discovery on every request would be slow and would hammer InPort, so
the *curated* result is pinned here: a small, reviewed set of catalog item IDs
per dimension, plus the keyword sets discovery uses.

Update flow: run ``agents.catalog_discovery.discover_catalog`` (or the
``GET /catalog/discover`` endpoint), review the hits, and paste the keepers into
``PINNED_CATALOG`` below. Collectors read endpoints from here rather than
hardcoding dataset IDs. See [[branch-layout]] for where this work lives.
"""

from typing import Any

# Keyword sets discovery uses per dimension. Tuned to surface queryable
# (ERDDAP / ArcGIS REST / THREDDS / API) datasets rather than documents.
DIMENSION_KEYWORDS: dict[str, list[str]] = {
    "sea_surface_temperature": [
        "sea surface temperature",
        "GOES sea surface temperature",
        "MUR sea surface temperature",
    ],
    "ocean_color": ["chlorophyll", "ocean color"],
    "currents": ["surface currents", "ocean currents", "tides and currents"],
    "species_distribution": [
        "DisMAP",
        "species distribution",
        "bottom trawl survey",
    ],
    "climate": ["climate normals", "ocean climate"],
}

# Curated catalog item IDs confirmed via InPort discovery on 2026-06-10. Each
# entry records what discovery found; ``connector`` is the PelagicSeer connector
# that can consume it ("portal"/"unknown" means human-facing only, kept for
# provenance). Extend after reviewing a fresh discovery run.
PINNED_CATALOG: dict[str, list[dict[str, Any]]] = {
    "species_distribution": [
        {
            "catalog_item_id": "66799",
            "title": "NOAA Distribution Mapping and Analysis Portal (DisMAP)",
            "connector": "arcgis_rest",
            "url": "https://apps-st.fisheries.noaa.gov/dismap",
            "notes": "ArcGIS REST feature services resolved via connectors.dismap",
        },
        {
            "catalog_item_id": "79330",
            "title": "DisMAP Survey Info CURRENT",
            "connector": "arcgis_rest",
            "url": "https://apps-st.fisheries.noaa.gov/dismap/index.html",
        },
    ],
    "sea_surface_temperature": [
        {
            "catalog_item_id": "36960",
            "title": "OW NOAA GOES-POES Sea Surface Temperature",
            "connector": "unknown",
            "url": "https://apps-st.fisheries.noaa.gov",
        },
        {
            "catalog_item_id": "78409",
            "title": "Physical Oceanographic (Water Temperature and Conductivity) Data",
            "connector": "unknown",
            "url": "https://www.fisheries.noaa.gov/inport/item/78409",
        },
    ],
}

# The DisMAP ArcGIS REST org base resolved out-of-band (InPort lists only the
# portal). Mirrors connectors.dismap.DISMAP_REST_BASE for documentation.
DISMAP_REST_BASE = "https://services2.arcgis.com/C8EMgrsFcRFL6LrL/arcgis/rest/services"


def dimensions() -> list[str]:
    """All dimensions the registry tracks."""
    return list(DIMENSION_KEYWORDS)


def entries_for_dimension(dimension: str) -> list[dict[str, Any]]:
    """Pinned catalog entries for a dimension (empty if none pinned yet)."""
    return list(PINNED_CATALOG.get(dimension, []))


def entries_for_connector(connector: str) -> list[dict[str, Any]]:
    """Pinned entries across all dimensions whose connector matches."""
    matches: list[dict[str, Any]] = []
    for dimension, entries in PINNED_CATALOG.items():
        for entry in entries:
            if entry.get("connector") == connector:
                matches.append({**entry, "dimension": dimension})
    return matches


def build_registry_payload() -> dict[str, Any]:
    """Registry view for the API: keywords + pinned catalog, no network."""
    return {
        "source": "inport-registry",
        "dimension_keywords": DIMENSION_KEYWORDS,
        "pinned_catalog": PINNED_CATALOG,
        "dismap_rest_base": DISMAP_REST_BASE,
        "item_count": sum(len(entries) for entries in PINNED_CATALOG.values()),
    }
