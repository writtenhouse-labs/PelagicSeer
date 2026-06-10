"""NOAA InPort metadata connector.

InPort is NOAA Fisheries' public metadata repository. This connector reads the
official InPort XML export for a catalog item, extracts distribution/access
URLs, classifies each URL by the kind of downstream connector PelagicSeer can
use, and returns a compact registry-friendly summary.
"""

import os
import re
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx


INPORT_BASE_URL = "https://www.fisheries.noaa.gov/inport"
HTTP_TIMEOUT_SECONDS = float(os.getenv("PELAGICSEER_HTTP_TIMEOUT_SECONDS", "300"))
URL_PATTERN = re.compile(r"https?://[^\s<>\"]+")
INPORT_ITEM_LINK_PATTERN = re.compile(
    r"<a[^>]+href=[\"'](?P<href>(?:https://www\.fisheries\.noaa\.gov)?/inport/item/(?P<id>\d+)[^\"']*)[\"'][^>]*>"
    r"(?P<title>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
DEFAULT_HARVEST_KEYWORDS = (
    "tuna",
    "yellowfin",
    "pelagic",
    "longline",
    "observer",
    "fisheries",
    "survey",
    "tagging",
    "catch",
    "conditions",
    "surface temperature",
)

CONNECTOR_TYPES = {
    "ERDDAP": "erddap",
    "ArcGIS REST": "arcgis_rest",
    "THREDDS": "thredds",
    "CSV Download": "csv_download",
    "ZIP Download": "zip_download",
    "API Endpoint": "api_endpoint",
    "Unknown": "unknown",
}


def classify_distribution_url(url: str) -> str:
    """Classify a distribution URL by the connector PelagicSeer should use."""
    parsed = urlparse(url)
    lowered = url.lower()
    path = parsed.path.lower()

    if "/erddap/" in lowered or "erddap" in parsed.netloc.lower():
        return "ERDDAP"
    if "/arcgis/rest/services" in lowered or path.endswith(("/mapserver", "/featureserver", "/imageserver")):
        return "ArcGIS REST"
    if "thredds" in lowered or "/dodsC/" in url or "/dods/" in lowered:
        return "THREDDS"
    if path.endswith(".csv") or "format=csv" in lowered or "f=csv" in lowered:
        return "CSV Download"
    if path.endswith(".zip") or "format=zip" in lowered:
        return "ZIP Download"
    if (
        "/api/" in lowered
        or path.endswith((".json", ".geojson", ".xml"))
        or "f=json" in lowered
        or parsed.query
    ):
        return "API Endpoint"
    return "Unknown"


def _fetch_text(url: str, params: dict[str, Any] | None = None) -> str:
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.text


def _clean_html_text(value: str) -> str:
    text = HTML_TAG_PATTERN.sub(" ", value)
    return " ".join(unescape(text).split())


def _find_description(root: ElementTree.Element) -> str | None:
    for path in (
        "./item-identification/abstract",
        "./item-identification/description",
        "./data-set-description/abstract",
        "./data-set-description/purpose",
    ):
        value = _text(root.find(path))
        if value:
            return value
    return None


def fetch_inport_xml(catalog_item_id: int | str) -> str:
    """Fetch the official InPort XML export for a public catalog item."""
    return _fetch_text(f"{INPORT_BASE_URL}/item/{catalog_item_id}/inport-xml")


def _text(element: ElementTree.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None


def _section(root: ElementTree.Element, name: str) -> ElementTree.Element | None:
    return root.find(name)


def _extract_url_records_from_url_section(section: ElementTree.Element) -> list[dict[str, str | None]]:
    records: list[dict[str, str | None]] = []
    for url_element in section.findall(".//url"):
        url = _text(url_element.find("url"))
        if not url:
            continue
        records.append(
            {
                "url": url,
                "name": _text(url_element.find("name")),
                "url_type": _text(url_element.find("url-type")),
                "description": _text(url_element.find("description")),
                "source_section": "urls",
            }
        )
    return records


def _extract_url_records_from_distribution_section(
    section: ElementTree.Element,
) -> list[dict[str, str | None]]:
    records: list[dict[str, str | None]] = []
    for distribution in section.findall(".//distribution"):
        name = _text(distribution.find(".//name")) or _text(distribution.find(".//title"))
        description = _text(distribution.find(".//description"))
        url_type = _text(distribution.find(".//url-type")) or _text(distribution.find(".//function"))
        for text_value in distribution.itertext():
            for url in URL_PATTERN.findall(text_value):
                records.append(
                    {
                        "url": url.rstrip(".,;)"),
                        "name": name,
                        "url_type": url_type,
                        "description": description,
                        "source_section": "distribution-info",
                    }
                )
    return records


def _dedupe_url_records(records: list[dict[str, str | None]]) -> list[dict[str, str | None]]:
    seen: set[str] = set()
    deduped: list[dict[str, str | None]] = []
    for record in records:
        url = record["url"]
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(record)
    return deduped


def parse_inport_metadata(xml_text: str) -> dict[str, Any]:
    """Parse InPort XML into metadata and classified distribution URLs."""
    root = ElementTree.fromstring(xml_text)
    identification = _section(root, "item-identification")
    catalog_details = _section(root, "catalog-details")

    records: list[dict[str, str | None]] = []
    distribution_info = _section(root, "distribution-info")
    if distribution_info is not None:
        records.extend(_extract_url_records_from_distribution_section(distribution_info))
    urls = _section(root, "urls")
    if urls is not None:
        records.extend(_extract_url_records_from_url_section(urls))

    distributions = []
    for record in _dedupe_url_records(records):
        classification = classify_distribution_url(record["url"] or "")
        distributions.append(
            {
                **record,
                "classification": classification,
                "connector": CONNECTOR_TYPES[classification],
            }
        )

    return {
        "source": "inport",
        "catalog_item_id": _text(identification.find("catalog-item-id")) if identification is not None else None,
        "title": _text(identification.find("title")) if identification is not None else None,
        "description": _find_description(root),
        "catalog_item_type": _text(identification.find("catalog-item-type")) if identification is not None else None,
        "guid": _text(catalog_details.find("guid")) if catalog_details is not None else None,
        "owner_organization": _text(catalog_details.find("owner-organization")) if catalog_details is not None else None,
        "distribution_count": len(distributions),
        "distributions": distributions,
    }


def inspect_inport_item(catalog_item_id: int | str) -> dict[str, Any]:
    """Fetch, parse, classify, and register distribution connectors for an item."""
    return parse_inport_metadata(fetch_inport_xml(catalog_item_id))


def parse_inport_search_results(html_text: str, keyword: str, limit: int = 10) -> list[dict[str, str]]:
    """Parse InPort search HTML into catalog item hits."""
    if limit <= 0:
        return []

    hits: list[dict[str, str]] = []
    seen: set[str] = set()

    for match in INPORT_ITEM_LINK_PATTERN.finditer(html_text):
        catalog_item_id = match.group("id")
        if catalog_item_id in seen:
            continue
        seen.add(catalog_item_id)
        title = _clean_html_text(match.group("title"))
        href = match.group("href")
        hits.append(
            {
                "catalog_item_id": catalog_item_id,
                "title": title,
                "search_keyword": keyword,
                "item_url": urljoin("https://www.fisheries.noaa.gov", href),
            }
        )
        if len(hits) >= limit:
            break

    return hits


def search_inport(keyword: str, limit: int = 10) -> list[dict[str, str]]:
    """Search InPort by keyword and return catalog item hits."""
    html_text = _fetch_text(f"{INPORT_BASE_URL}/q", params={"keywords": keyword})
    return parse_inport_search_results(html_text, keyword=keyword, limit=limit)


def harvest_inport_catalog(
    keywords: list[str] | tuple[str, ...] = DEFAULT_HARVEST_KEYWORDS,
    per_keyword_limit: int = 5,
    max_items: int = 50,
) -> dict[str, Any]:
    """Build an agent-friendly InPort catalog keyed by catalog item ID."""
    keyword_list = [keyword for keyword in keywords if keyword.strip()]
    if max_items <= 0 or per_keyword_limit <= 0:
        return {
            "source": "inport",
            "keywords": keyword_list,
            "item_count": 0,
            "catalog": {},
            "errors": [],
        }

    catalog: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []

    for keyword in keyword_list:
        search_keyword = keyword.strip()
        try:
            hits = search_inport(search_keyword, limit=per_keyword_limit)
        except httpx.HTTPError as exc:
            errors.append({"keyword": search_keyword, "error": str(exc)})
            continue

        for hit in hits:
            catalog_item_id = hit["catalog_item_id"]
            if catalog_item_id in catalog:
                if search_keyword not in catalog[catalog_item_id]["matched_keywords"]:
                    catalog[catalog_item_id]["matched_keywords"].append(search_keyword)
                continue
            if len(catalog) >= max_items:
                break

            try:
                metadata = inspect_inport_item(catalog_item_id)
            except httpx.HTTPError as exc:
                errors.append({"catalog_item_id": catalog_item_id, "keyword": search_keyword, "error": str(exc)})
                continue

            distributions = metadata.get("distributions", [])
            distribution_urls = [item["url"] for item in distributions if item.get("url")]
            catalog[catalog_item_id] = {
                "catalog_item_id": catalog_item_id,
                "title": metadata.get("title") or hit.get("title"),
                "description": metadata.get("description"),
                "item_url": hit["item_url"],
                "matched_keywords": [search_keyword],
                "primary_distribution_url": distribution_urls[0] if distribution_urls else None,
                "distribution_urls": distribution_urls,
                "distributions": distributions,
            }
        if len(catalog) >= max_items:
            break

    return {
        "source": "inport",
        "keywords": keyword_list,
        "item_count": len(catalog),
        "catalog": catalog,
        "errors": errors,
    }
