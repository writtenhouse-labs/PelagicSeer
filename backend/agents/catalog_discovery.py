"""CatalogDiscoveryAgent.

Drives the InPort harvester with the per-dimension keyword sets from the pinned
registry, then keeps only the catalog items that expose a distribution
PelagicSeer can actually consume (ERDDAP / ArcGIS REST / THREDDS / API). The
result is a registry-shaped dict — ``{dimension: [entries]}`` plus collected
errors — suitable for reviewing and pasting into ``inport_registry`` to refresh
the pinned item IDs.

This is the discovery step described in docs/noaa_data_sources.md: "find what
catalogs are needed and update the list of item IDs once they are identified."
It is deliberately kept out of the request path (it is slow and hits InPort
repeatedly); ``/advice`` reads the pinned registry instead.
"""

from typing import Any

import httpx

from connectors.inport import harvest_inport_catalog
from connectors.inport_registry import DIMENSION_KEYWORDS

# Connector classifications that map to a connector PelagicSeer can query.
SUPPORTED_CONNECTORS = frozenset({"erddap", "arcgis_rest", "thredds", "api_endpoint"})


def _supported_distributions(distributions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "url": dist.get("url"),
            "connector": dist.get("connector"),
            "classification": dist.get("classification"),
        }
        for dist in distributions
        if dist.get("connector") in SUPPORTED_CONNECTORS
    ]


def discover_catalog(
    dimension_keywords: dict[str, list[str]] | None = None,
    per_keyword_limit: int = 5,
    max_items_per_dimension: int = 10,
) -> dict[str, Any]:
    """Harvest InPort per dimension and keep items with a usable connector.

    Returns ``{"catalog": {dimension: [entries]}, "errors": [...], ...}`` where
    each kept entry carries its catalog item ID, title, matched keywords, and
    the subset of distributions that classify into a supported connector. Items
    that only expose human-facing/unknown URLs are dropped.
    """
    keyword_map = dimension_keywords or DIMENSION_KEYWORDS
    catalog: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, Any]] = []

    for dimension, keywords in keyword_map.items():
        try:
            harvest = harvest_inport_catalog(
                keywords=keywords,
                per_keyword_limit=per_keyword_limit,
                max_items=max_items_per_dimension,
            )
        except (httpx.HTTPError, ValueError) as exc:
            errors.append({"dimension": dimension, "error": str(exc)})
            catalog[dimension] = []
            continue

        errors.extend({"dimension": dimension, **err} for err in harvest.get("errors", []))

        entries: list[dict[str, Any]] = []
        for item in harvest.get("catalog", {}).values():
            supported = _supported_distributions(item.get("distributions", []))
            if not supported:
                continue
            entries.append(
                {
                    "catalog_item_id": item.get("catalog_item_id"),
                    "title": item.get("title"),
                    "item_url": item.get("item_url"),
                    "matched_keywords": item.get("matched_keywords", []),
                    "connectors": sorted({dist["connector"] for dist in supported}),
                    "distributions": supported,
                }
            )
        catalog[dimension] = entries

    item_count = sum(len(entries) for entries in catalog.values())
    return {
        "source": "inport-discovery",
        "dimensions": list(keyword_map),
        "item_count": item_count,
        "catalog": catalog,
        "errors": errors,
    }
