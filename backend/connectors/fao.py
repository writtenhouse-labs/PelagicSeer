"""FAO FishStat connector.

FishStat public collection pages do not require a token. FAO's fisheries
frontend also advertises table-query endpoints, so this connector exposes the
stable collection metadata surface and a small, configurable JSON query hook.
"""

import os
import json
import re
from functools import lru_cache
from html import unescape
from json import JSONDecodeError
from typing import Any

import httpx


FAO_FISHERY_BASE_URL = os.getenv("FAO_FISHERY_BASE_URL", "https://www.fao.org/fishery").rstrip("/")
FAO_FISHSTAT_API_BASE_URL = os.getenv("FAO_FISHSTAT_API_BASE_URL", FAO_FISHERY_BASE_URL).rstrip("/")
HTTP_TIMEOUT_SECONDS = float(os.getenv("PELAGICSEER_HTTP_TIMEOUT_SECONDS", "300"))
FISHSTAT_RUNIVERSE_BASE_URL = os.getenv(
    "FISHSTAT_RUNIVERSE_BASE_URL",
    "https://sofia-taf.r-universe.dev/fishstat/data",
).rstrip("/")

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
CANONICAL_PATTERN = re.compile(
    r"<link[^>]+rel=[\"']canonical[\"'][^>]+href=[\"'](?P<href>[^\"']+)[\"']",
    re.IGNORECASE,
)
TITLE_PATTERN = re.compile(r"<title[^>]*>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)
META_DESCRIPTION_PATTERN = re.compile(
    r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"'](?P<content>[^\"']+)[\"']",
    re.IGNORECASE,
)

FISHSTAT_DATASETS: dict[str, dict[str, Any]] = {
    "global_production": {
        "id": "global_production",
        "name": "Global Production",
        "collection_url": f"{FAO_FISHERY_BASE_URL}/collection/global_production/en",
        "statistics_timeseries": "global_production",
        "description": (
            "Global capture and aquaculture production statistics by country or area, "
            "aquatic species item, FAO major fishing area, and year."
        ),
        "expected_fields": [
            "species",
            "year",
            "area",
            "country",
            "value",
            "measure",
            "status",
            "source",
        ],
    },
    "capture": {
        "id": "capture",
        "name": "Capture Production",
        "collection_url": f"{FAO_FISHERY_BASE_URL}/collection/capture/en",
        "statistics_timeseries": "capture",
        "description": (
            "Capture production statistics by country or territory, species item, "
            "FAO major fishing area, and year."
        ),
        "expected_fields": [
            "species",
            "year",
            "area",
            "country",
            "value",
            "measure",
            "status",
        ],
    },
    "aquaculture": {
        "id": "aquaculture",
        "name": "Aquaculture Production",
        "collection_url": f"{FAO_FISHERY_BASE_URL}/collection/aquaculture/en",
        "statistics_timeseries": "aquaculture",
        "description": (
            "Aquaculture production statistics by country or territory, aquatic "
            "species item, environment, and year."
        ),
        "expected_fields": [
            "species",
            "year",
            "area",
            "country",
            "environment",
            "value",
            "measure",
            "status",
        ],
    },
}


def _clean_html_text(value: str | None) -> str | None:
    if not value:
        return None
    text = HTML_TAG_PATTERN.sub(" ", value)
    cleaned = " ".join(unescape(text).split())
    return cleaned or None


def _dataset_config(dataset: str) -> dict[str, Any]:
    key = dataset.strip().lower()
    try:
        return FISHSTAT_DATASETS[key]
    except KeyError as exc:
        available = ", ".join(sorted(FISHSTAT_DATASETS))
        raise ValueError(f"Unknown FAO FishStat dataset '{dataset}'. Available datasets: {available}") from exc


def _fetch_collection_page(url: str) -> tuple[str, str]:
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text, str(response.url)


def _extract_collection_page_metadata(html_text: str, fallback: dict[str, Any]) -> dict[str, str | None]:
    canonical_match = CANONICAL_PATTERN.search(html_text)
    title_match = TITLE_PATTERN.search(html_text)
    description_match = META_DESCRIPTION_PATTERN.search(html_text)

    return {
        "canonical_url": canonical_match.group("href") if canonical_match else fallback["collection_url"],
        "page_title": _clean_html_text(title_match.group("title")) if title_match else fallback["name"],
        "page_description": (
            _clean_html_text(description_match.group("content"))
            if description_match
            else fallback["description"]
        ),
    }


def _table_query_endpoint(timeseries: str, language: str) -> str:
    return f"{FAO_FISHSTAT_API_BASE_URL}/statistics/api/data/query/{timeseries}/{language}"


def list_fishstat_datasets() -> dict[str, Any]:
    """Return the FAO FishStat datasets configured for PelagicSeer."""
    return {
        "source": "fao-fishstat",
        "datasets": [
            {
                "id": dataset["id"],
                "name": dataset["name"],
                "collection_url": dataset["collection_url"],
                "description": dataset["description"],
                "expected_fields": dataset["expected_fields"],
            }
            for dataset in FISHSTAT_DATASETS.values()
        ],
    }


def get_fishstat_dataset_info(dataset: str = "global_production") -> dict[str, Any]:
    """Fetch public FAO FishStat collection metadata for a configured dataset."""
    config = _dataset_config(dataset)
    html_text, resolved_url = _fetch_collection_page(config["collection_url"])
    page_metadata = _extract_collection_page_metadata(html_text, config)

    return {
        "source": "fao-fishstat",
        "dataset": config["id"],
        "name": config["name"],
        "description": page_metadata["page_description"] or config["description"],
        "collection_url": config["collection_url"],
        "resolved_url": resolved_url,
        "canonical_url": page_metadata["canonical_url"],
        "page_title": page_metadata["page_title"],
        "expected_fields": config["expected_fields"],
        "table_api": {
            "endpoint": _table_query_endpoint(config["statistics_timeseries"], "en"),
            "method": "POST",
            "requires_token": False,
            "status": "configured",
            "notes": (
                "FAO collection metadata is public. If FAO serves the table API from "
                "a different host, set FAO_FISHSTAT_API_BASE_URL."
            ),
        },
    }


def query_fishstat_data(
    dataset: str = "global_production",
    rows: list[dict[str, Any]] | None = None,
    columns: list[dict[str, Any]] | None = None,
    filters: list[dict[str, Any]] | None = None,
    limit: int = 25,
    language: str = "en",
) -> dict[str, Any]:
    """Run a small FAO FishStat table query and return compact JSON results."""
    if limit <= 0:
        raise ValueError("limit must be greater than 0")

    config = _dataset_config(dataset)
    endpoint = _table_query_endpoint(config["statistics_timeseries"], language)
    body = {
        "aggregationType": "D",
        "disableSymbol": False,
        "includeNullValues": False,
        "grouped": False,
        "rows": rows or [{"field": "year", "order": "desc"}],
        "columns": columns or [],
        "filters": filters or [],
    }

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = client.post(endpoint, params={"format": "positional"}, json=body)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "json" not in content_type.lower():
        raise ValueError(
            "FAO FishStat table API did not return JSON. "
            "Set FAO_FISHSTAT_API_BASE_URL if this deployment serves tables elsewhere."
        )

    payload = response.json()
    values = payload.get("values")
    if isinstance(values, list):
        payload = {**payload, "values": values[:limit]}

    return {
        "source": "fao-fishstat",
        "dataset": config["id"],
        "endpoint": str(response.url),
        "query": body,
        "response": payload,
    }


def _header_name(header: Any) -> str:
    if isinstance(header, dict):
        value = header.get("field") or header.get("id") or header.get("name") or header.get("title")
        return str(value) if value is not None else ""
    return str(header)


def _records_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload.get("records") or payload.get("data")
    if isinstance(records, list) and all(isinstance(record, dict) for record in records):
        return records

    headers = payload.get("headers") or payload.get("columns")
    values = payload.get("values") or payload.get("rows")
    if not isinstance(headers, list) or not isinstance(values, list):
        return []

    header_names = [_header_name(header) for header in headers]
    converted: list[dict[str, Any]] = []
    for row in values:
        if isinstance(row, dict):
            converted.append(row)
        elif isinstance(row, list):
            converted.append(
                {
                    header_names[index] or f"field_{index}": value
                    for index, value in enumerate(row)
                    if index < len(header_names)
                }
            )
    return converted


def _first_present(record: dict[str, Any], candidates: tuple[str, ...]) -> Any:
    lowered = {key.lower(): value for key, value in record.items()}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def _numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return None
    return None


def _runiverse_data_url(dataset: str) -> str:
    return f"{FISHSTAT_RUNIVERSE_BASE_URL}/{dataset}/json"


@lru_cache(maxsize=1)
def _fishstat_species_lookup() -> list[dict[str, Any]]:
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = client.get(_runiverse_data_url("species"))
        response.raise_for_status()
        return response.json()


@lru_cache(maxsize=1)
def _fishstat_country_lookup() -> dict[Any, str]:
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = client.get(_runiverse_data_url("country"))
            response.raise_for_status()
            countries = response.json()
    except httpx.HTTPError:
        return {}
    return {
        item.get("country"): item.get("country_name") or item.get("name")
        for item in countries
        if isinstance(item, dict)
    }


@lru_cache(maxsize=1)
def _fishstat_area_lookup() -> dict[Any, str]:
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = client.get(_runiverse_data_url("area"))
            response.raise_for_status()
            areas = response.json()
    except httpx.HTTPError:
        return {}
    return {
        item.get("area"): item.get("area_name") or item.get("name")
        for item in areas
        if isinstance(item, dict)
    }


@lru_cache(maxsize=1)
def _fishstat_measure_lookup() -> dict[Any, str]:
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = client.get(_runiverse_data_url("measure"))
            response.raise_for_status()
            measures = response.json()
    except httpx.HTTPError:
        return {}
    return {
        item.get("measure"): item.get("unit") or item.get("measure_name") or item.get("short")
        for item in measures
        if isinstance(item, dict)
    }


def _species_match_score(record: dict[str, Any], terms: list[str]) -> int:
    species_name = str(record.get("species_name") or "").lower()
    scientific = str(record.get("scientific") or "").lower()
    searchable = f"{species_name} {scientific}"
    score = 0
    for term in terms:
        normalized = term.lower().strip()
        if not normalized:
            continue
        if normalized == scientific:
            score = max(score, 100)
        elif normalized == species_name:
            score = max(score, 95)
        elif normalized in scientific:
            score = max(score, 80)
        elif normalized in species_name:
            score = max(score, 70)
        else:
            tokens = [token for token in re.split(r"\W+", normalized) if token]
            if tokens and all(token in searchable for token in tokens):
                score = max(score, 60)
    return score


def _match_fishstat_species(species: str, scientific_name: str | None) -> list[dict[str, Any]]:
    terms = [term for term in (scientific_name, species) if term and term.strip()]
    scored = [
        (_species_match_score(record, terms), record)
        for record in _fishstat_species_lookup()
        if _species_match_score(record, terms) > 0
    ]
    scored.sort(key=lambda item: (-item[0], str(item[1].get("species_name") or "")))
    return [record for _, record in scored[:10]]


def _iter_runiverse_records(dataset: str):
    decoder = json.JSONDecoder()
    buffer = ""
    started = False
    url = _runiverse_data_url(dataset)

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            for chunk in response.iter_text():
                buffer += chunk
                while True:
                    buffer = buffer.lstrip()
                    if not started:
                        if not buffer:
                            break
                        if buffer[0] != "[":
                            raise ValueError("FishStat package JSON did not return an array")
                        buffer = buffer[1:]
                        started = True
                        continue
                    if not buffer:
                        break
                    if buffer[0] == "]":
                        return
                    if buffer[0] == ",":
                        buffer = buffer[1:]
                        continue
                    try:
                        record, index = decoder.raw_decode(buffer)
                    except JSONDecodeError:
                        break
                    if isinstance(record, dict):
                        yield record
                    buffer = buffer[index:]


def _fishstat_package_species_summary(
    species: str,
    scientific_name: str | None,
    dataset: str,
    limit: int,
    detail: str | None = None,
) -> dict[str, Any]:
    dataset_name = "production" if dataset == "global_production" else dataset
    if dataset_name not in {"production", "capture", "aquaculture"}:
        _dataset_config(dataset)

    matches = _match_fishstat_species(species, scientific_name)
    species_codes = {match["species"] for match in matches if match.get("species")}
    species_names = {
        match.get("species"): match.get("species_name") or match.get("scientific")
        for match in matches
    }
    if not species_codes:
        return {
            "source": "fao-fishstat",
            "access": "fishstat-r-universe",
            "dataset": dataset,
            "species_query": species,
            "scientific_name": scientific_name,
            "available": False,
            "record_count": 0,
            "returned": 0,
            "year_range": None,
            "total_reported_value": None,
            "measures": [],
            "records": [],
            "matched_species": [],
            "detail": "No FishStat species lookup rows matched this query.",
            "notes": "FAO FishStat is global production/capture context, not local catch or live fishing conditions.",
        }

    country_names = _fishstat_country_lookup()
    area_names = _fishstat_area_lookup()
    measure_names = _fishstat_measure_lookup()
    matched_records: list[dict[str, Any]] = []
    total_value = 0.0
    valued_records = 0
    years: list[int] = []
    measures: set[str] = set()

    for record in _iter_runiverse_records(dataset_name):
        code = record.get("species")
        if code not in species_codes:
            continue
        value = _numeric_value(record.get("value"))
        year_value = _numeric_value(record.get("year"))
        measure = record.get("measure")
        if value is not None:
            total_value += value
            valued_records += 1
        if year_value is not None:
            years.append(int(year_value))
        if measure:
            measures.add(str(measure_names.get(measure) or measure))

        matched_records.append(
            {
                "species": species_names.get(code) or code,
                "year": int(year_value) if year_value is not None else None,
                "country": country_names.get(record.get("country")) or record.get("country"),
                "fao_area": area_names.get(record.get("area")) or record.get("area"),
                "value": value,
                "measure": str(measure_names.get(measure) or measure) if measure else None,
                "source": record.get("source"),
            }
        )

    matched_records.sort(
        key=lambda item: (
            -(item["year"] or 0),
            -(item["value"] or 0),
            str(item["country"] or ""),
        )
    )

    return {
        "source": "fao-fishstat",
        "access": "fishstat-r-universe",
        "dataset": dataset,
        "species_query": species,
        "scientific_name": scientific_name,
        "available": bool(matched_records),
        "record_count": len(matched_records),
        "returned": min(len(matched_records), limit),
        "year_range": {"min": min(years), "max": max(years)} if years else None,
        "total_reported_value": round(total_value, 3) if valued_records else None,
        "measures": sorted(measures),
        "records": matched_records[:limit],
        "matched_species": matches,
        "detail": detail,
        "notes": "FAO FishStat is global production/capture context, not local catch or live fishing conditions.",
    }


def _unavailable_species_summary(
    species: str,
    scientific_name: str | None,
    dataset: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "source": "fao-fishstat",
        "dataset": dataset,
        "species_query": species,
        "scientific_name": scientific_name,
        "available": False,
        "record_count": 0,
        "returned": 0,
        "year_range": None,
        "total_reported_value": None,
        "measures": [],
        "records": [],
        "matched_species": [],
        "detail": detail,
        "notes": "FAO FishStat is global production/capture context, not local catch or live fishing conditions.",
    }


def get_fishstat_species_summary(
    species: str,
    scientific_name: str | None = None,
    dataset: str = "global_production",
    limit: int = 10,
) -> dict[str, Any]:
    """Return FAO FishStat production context for a target species.

    The FishStat query API shape can vary by FAO deployment, so parsing accepts
    both row dictionaries and positional ``headers``/``values`` responses.
    """
    search_terms = [term for term in (species, scientific_name) if term and term.strip()]
    if not search_terms:
        raise ValueError("species is required")

    filters = [
        {
            "field": "species",
            "operator": "contains",
            "value": search_terms[0],
        }
    ]
    try:
        result = query_fishstat_data(
            dataset=dataset,
            rows=[{"field": "species"}, {"field": "year", "order": "desc"}],
            columns=[],
            filters=filters,
            limit=limit,
        )
    except (httpx.HTTPError, ValueError) as exc:
        table_error = exc
        try:
            return _fishstat_package_species_summary(
                species=species,
                scientific_name=scientific_name,
                dataset=dataset,
                limit=limit,
                detail="Used FishStat package fallback because FAO's web table endpoint was unavailable.",
            )
        except (httpx.HTTPError, ValueError) as fallback_exc:
            return _unavailable_species_summary(
                species=species,
                scientific_name=scientific_name,
                dataset=dataset,
                detail=(
                    "FAO FishStat context is currently unavailable. "
                    f"Table API error: {table_error}. "
                    f"Package fallback error: {fallback_exc}."
                ),
            )

    payload = result.get("response", {})
    records = _records_from_payload(payload)

    summarized_records: list[dict[str, Any]] = []
    total_value = 0.0
    valued_records = 0
    years: list[int] = []
    measures: set[str] = set()

    for record in records[:limit]:
        value = _numeric_value(_first_present(record, ("value", "quantity", "production", "amount")))
        year_value = _numeric_value(_first_present(record, ("year", "time", "date")))
        measure = _first_present(record, ("measure", "unit", "units"))
        if value is not None:
            total_value += value
            valued_records += 1
        if year_value is not None:
            years.append(int(year_value))
        if measure:
            measures.add(str(measure))

        summarized_records.append(
            {
                "species": _first_present(record, ("species", "species_item", "item", "taxon")),
                "year": int(year_value) if year_value is not None else None,
                "country": _first_present(record, ("country", "area", "country_or_area")),
                "fao_area": _first_present(record, ("fao_area", "fishing_area", "major_fishing_area")),
                "value": value,
                "measure": str(measure) if measure is not None else None,
            }
        )

    return {
        "source": "fao-fishstat",
        "dataset": dataset,
        "species_query": species,
        "scientific_name": scientific_name,
        "available": bool(summarized_records),
        "record_count": len(records),
        "returned": len(summarized_records),
        "year_range": {"min": min(years), "max": max(years)} if years else None,
        "total_reported_value": round(total_value, 3) if valued_records else None,
        "measures": sorted(measures),
        "records": summarized_records,
        "notes": "FAO FishStat is global production/capture context, not local catch or live fishing conditions.",
    }

