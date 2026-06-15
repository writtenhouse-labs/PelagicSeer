from datetime import date

import httpx
from fastapi import FastAPI
from fastapi import HTTPException

from agents.catalog_discovery import discover_catalog
from agents.environment_collector import collect_climate_anomaly, collect_conditions_with_fallback
from agents.orchestrator import build_fishing_advice
from agents.signal_collector import (
    collect_area_species,
    collect_signals,
    collect_survey_distribution,
    resolve_common_name,
    resolve_scientific_name,
)
from agents.temporal_router import resolve_temporal_plan
from api.schemas import AdviceRequest
from connectors.bathymetry import get_bathymetry_context
from connectors.fao import (
    get_fishstat_dataset_info,
    get_fishstat_species_summary,
    list_fishstat_datasets,
    query_fishstat_data,
)
from connectors.gfw import get_fishing_effort
from connectors.inport import DEFAULT_HARVEST_KEYWORDS, harvest_inport_catalog, inspect_inport_item
from connectors.mrip import get_mrip_recreational_prior
from connectors.dismap import get_dismap_distribution
from connectors.gfw import get_fishing_effort
from connectors.inport import DEFAULT_HARVEST_KEYWORDS, harvest_inport_catalog, inspect_inport_item
from connectors.inport_registry import build_registry_payload
from connectors.obis import OCEAN_BOUNDS, get_species_ocean_map, get_species_occurrences
from connectors.noaa_coops import get_latest_coops_observation
from connectors.noaa_ncei import (
    get_ncei_datasets,
    get_ncei_station_summary,
    get_ncei_temperature_anomaly,
)
from connectors.noaa_ndbc import get_latest_ndbc_observation
from connectors.nws import get_nws_forecast
from services.location_resolver import TOO_FAR_MESSAGE, resolve_location

app = FastAPI(title="PelagicSeer API")


def _analysis_location_from_conditions(location: dict, conditions: dict) -> dict:
    """Choose the working NOAA station coordinate for ocean data lookups."""
    preferred_source_ids = (
        "noaa-ndbc",
        "noaa-coops:water_level",
        "noaa-coops:currents",
        "noaa-coops:salinity",
    )
    sources = conditions.get("sources", [])
    if isinstance(sources, list):
        for source_id in preferred_source_ids:
            for source in sources:
                if not isinstance(source, dict):
                    continue
                if source.get("id") != source_id or source.get("status") != "ok":
                    continue
                latitude = source.get("latitude")
                longitude = source.get("longitude")
                if latitude is None or longitude is None:
                    continue
                return {
                    "latitude": latitude,
                    "longitude": longitude,
                    "source": source_id,
                    "station": source.get("station"),
                    "station_name": source.get("station_name"),
                    "distance_nm": source.get("distance_nm"),
                    "basis": "nearest working NOAA station used by live conditions",
                }

    nearest_station = location.get("nearest_ocean_station") or {}
    if nearest_station.get("latitude") is not None and nearest_station.get("longitude") is not None:
        return {
            "latitude": nearest_station["latitude"],
            "longitude": nearest_station["longitude"],
            "source": "nearest_ocean_station",
            "station": nearest_station.get("station"),
            "station_name": nearest_station.get("name"),
            "distance_nm": nearest_station.get("distance_nm"),
            "basis": "nearest active NOAA station fallback",
        }

    return {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "source": "geocoded_location",
        "basis": "geocoded city/state fallback",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/advice")
def advice(request: AdviceRequest) -> dict:
    try:
        location = resolve_location(request.city, request.state)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    latitude = location["latitude"]
    longitude = location["longitude"]

    today = date.today()
    plan = resolve_temporal_plan(
        request.start_date or today,
        request.end_date or today,
        today=today,
    )

    if location["too_far_from_ocean"]:
        return {
            "location": location,
            "species": request.species,
            "date_range": plan.as_dict(),
            "conditions": {},
            "signals": {},
            "area_species": {"available": False},
            "survey_distribution": {"available": False},
            "climate_anomaly": {"available": False},
            "recommendation": {
                "score": 0,
                "label": "too_far",
                "summary": TOO_FAR_MESSAGE,
                "reasons": [
                    f"{request.city}, {request.state} is about "
                    f"{location['ocean_distance_miles']} miles from the nearest ocean station."
                ],
                "confidence": "high",
                "data_completeness": {"available": [], "missing": []},
            },
        }

    conditions = collect_conditions_with_fallback(latitude, longitude, plan=plan)
    analysis_location = _analysis_location_from_conditions(location, conditions)
    analysis_latitude = analysis_location["latitude"]
    analysis_longitude = analysis_location["longitude"]

    signals = collect_signals(request.species, analysis_latitude, analysis_longitude, plan=plan)
    area_species = collect_area_species(analysis_latitude, analysis_longitude, plan=plan)
    survey_distribution = collect_survey_distribution(
        request.species, analysis_latitude, analysis_longitude
    )
    # The climate anomaly is historical-window context and is token-gated +
    # multi-call, so it is only fetched for past windows (kept off the hot path).
    climate_anomaly = (
        collect_climate_anomaly(analysis_latitude, analysis_longitude, plan=plan)
        if plan.mode == "historical"
        else {"available": False}
    )
    recommendation = build_fishing_advice(request, conditions, signals, plan=plan)

    return {
        "location": location,
        "analysis_location": analysis_location,
        "species": request.species,
        "date_range": plan.as_dict(),
        "conditions": conditions,
        "signals": signals,
        "area_species": area_species,
        "survey_distribution": survey_distribution,
        "climate_anomaly": climate_anomaly,
        "recommendation": recommendation,
    }


@app.get("/species/in-area")
def species_in_area(
    latitude: float,
    longitude: float,
    buffer_deg: float = 2.0,
    startdate: date | None = None,
    enddate: date | None = None,
    limit: int = 25,
) -> dict:
    """List the species recorded near a lat/lon (OBIS checklist), optionally
    restricted to a date window."""
    try:
        if (startdate is None) != (enddate is None):
            raise ValueError("startdate and enddate must be provided together")
        if startdate and enddate and startdate > enddate:
            raise ValueError("startdate cannot be after enddate")
        plan = (
            resolve_temporal_plan(startdate, enddate)
            if startdate and enddate
            else None
        )
        return collect_area_species(latitude, longitude, plan=plan, buffer_deg=buffer_deg, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/dismap/distribution")
def dismap_distribution(
    species: str,
    latitude: float,
    longitude: float,
    region: str | None = None,
) -> dict:
    """NOAA DisMAP survey distribution (biomass) for a species near a point.

    The species name is resolved to a scientific name first; the covering
    survey region is inferred from the point unless ``region`` is given.
    """
    try:
        scientific_name, _ = resolve_scientific_name(species)
        result = get_dismap_distribution(scientific_name, latitude, longitude, region=region)
        result["species_input"] = species
        return result
    except ValueError as exc:
        # No covering region or an ArcGIS error.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/nws/forecast")
def nws_forecast(
    latitude: float,
    longitude: float,
    target_date: date | None = None,
) -> dict:
    """NWS wind/temperature/narrative forecast for a point (U.S. coverage only)."""
    try:
        return get_nws_forecast(latitude, longitude, target_date=target_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/noaa/ncei/anomaly")
def ncei_anomaly(
    latitude: float,
    longitude: float,
    target_date: date | None = None,
    baseline_years: int = 5,
) -> dict:
    """Temperature anomaly for a point/date vs. recent local climatology (GHCND)."""
    try:
        return get_ncei_temperature_anomaly(
            latitude, longitude, target_date=target_date, baseline_years=baseline_years
        )
    except ValueError as exc:
        # Missing token or no data both surface as a 400 with the reason.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/catalog/registry")
def catalog_registry() -> dict:
    """Return the pinned InPort catalog registry (no network)."""
    return build_registry_payload()


@app.get("/catalog/discover")
def catalog_discover(
    per_keyword_limit: int = 5,
    max_items_per_dimension: int = 10,
) -> dict:
    """Run the CatalogDiscoveryAgent: harvest InPort per dimension and keep
    items exposing a connector PelagicSeer can consume. Slow (hits InPort)."""
    try:
        return discover_catalog(
            per_keyword_limit=per_keyword_limit,
            max_items_per_dimension=max_items_per_dimension,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/noaa/capabilities")
def noaa_capabilities() -> dict:
    return {
        "sources": [
            {
                "id": "coops",
                "name": "NOAA CO-OPS Tides and Currents",
                "best_for": [
                    "water temperature",
                    "currents",
                    "tide predictions",
                    "water levels",
                    "wind",
                    "barometric pressure",
                    "salinity",
                    "visibility",
                ],
            },
            {
                "id": "ndbc",
                "name": "NOAA National Data Buoy Center",
                "best_for": [
                    "wave height",
                    "wave period",
                    "wind",
                    "sea surface temperature",
                    "air temperature",
                    "pressure",
                ],
            },
            {
                "id": "erddap",
                "name": "NOAA CoastWatch ERDDAP",
                "best_for": [
                    "gridded satellite sea surface temperature",
                    "chlorophyll",
                    "ocean color",
                    "large-area environmental rasters",
                ],
            },
            {
                "id": "dismap",
                "name": "NOAA Fisheries DisMAP",
                "best_for": [
                    "fish and invertebrate survey distributions",
                    "species distribution indicators",
                    "historical biomass surfaces",
                ],
            },
            {
                "id": "nws",
                "name": "NOAA National Weather Service forecast",
                "best_for": [
                    "wind forecast",
                    "coastal wave height forecast",
                    "air temperature forecast",
                    "weather narrative for future windows",
                ],
            },
            {
                "id": "inport",
                "name": "NOAA Fisheries InPort",
                "best_for": [
                    "NOAA Fisheries and NOS metadata discovery",
                    "distribution URL extraction",
                    "downstream connector classification",
                    "dataset access links",
                ],
            },
        ]
    }


@app.get("/fao/fishstat/datasets")
def fao_fishstat_datasets() -> dict:
    return list_fishstat_datasets()


@app.get("/fao/fishstat/datasets/{dataset}")
def fao_fishstat_dataset_info(dataset: str) -> dict:
    try:
        return get_fishstat_dataset_info(dataset=dataset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/fao/fishstat/query")
def fao_fishstat_query(dataset: str = "global_production", limit: int = 25) -> dict:
    try:
        return query_fishstat_data(dataset=dataset, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/fao/fishstat/species-summary")
def fao_fishstat_species_summary(
    species: str,
    scientific_name: str | None = None,
    dataset: str = "global_production",
    limit: int = 10,
) -> dict:
    try:
        return get_fishstat_species_summary(
            species=species,
            scientific_name=scientific_name,
            dataset=dataset,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/noaa/coops/latest")
def latest_coops_observation(
    station: str,
    product: str = "water_temperature",
    units: str = "english",
) -> dict:
    try:
        return get_latest_coops_observation(station=station, product=product, units=units)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/noaa/ndbc/latest/{station}")
def latest_ndbc_observation(station: str) -> dict:
    try:
        return get_latest_ndbc_observation(station=station)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/gfw/effort")
def fishing_effort(latitude: float, longitude: float, days: int = 30) -> dict:
    try:
        return get_fishing_effort(latitude=latitude, longitude=longitude, days=days)
    except ValueError as exc:
        # Missing token or no coverage for the requested box/window.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/bathymetry/context")
def bathymetry_context(latitude: float, longitude: float) -> dict:
    try:
        return get_bathymetry_context(latitude=latitude, longitude=longitude)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/mrip/recreational-prior")
def mrip_recreational_prior(
    species: str,
    latitude: float,
    longitude: float,
    target_date: date | None = None,
) -> dict:
    try:
        return get_mrip_recreational_prior(
            species=species,
            latitude=latitude,
            longitude=longitude,
            target_date=target_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/obis/occurrences")
def obis_occurrences(
    scientificname: str,
    latitude: float,
    longitude: float,
    buffer_deg: float = 1.0,
) -> dict:
    try:
        return get_species_occurrences(
            scientificname=scientificname,
            latitude=latitude,
            longitude=longitude,
            buffer_deg=buffer_deg,
        )
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/obis/ocean-map")
def obis_ocean_map(
    species: str,
    ocean: str | None = None,
    size: int = 1000,
    startdate: date | None = None,
    enddate: date | None = None,
    search_rank: str = "Species",
) -> dict:
    try:
        normalized_rank = search_rank.title()
        if normalized_rank not in {"Species", "Genus", "Family"}:
            raise ValueError("search_rank must be Species, Genus, or Family")
        scientific_name, name_resolved = (
            resolve_scientific_name(species)
            if normalized_rank == "Species"
            else (species.strip(), False)
        )
        if (startdate is None) != (enddate is None):
            raise ValueError("startdate and enddate must be provided together")
        if startdate and enddate and startdate > enddate:
            raise ValueError("startdate cannot be after enddate")
        result = get_species_ocean_map(
            scientificname=scientific_name,
            ocean=ocean,
            size=size,
            startdate=startdate.isoformat() if startdate else None,
            enddate=enddate.isoformat() if enddate else None,
            search_rank=normalized_rank,
        )
        result["species_input"] = species
        result["name_resolved"] = name_resolved
        result["common_name"] = (
            resolve_common_name(scientific_name) if normalized_rank == "Species" else None
        )
        result["available_oceans"] = list(OCEAN_BOUNDS)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/noaa/ncei/datasets")
def ncei_datasets(limit: int = 25) -> dict:
    try:
        return get_ncei_datasets(limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/inport/items/{catalog_item_id}/distributions")
def inport_item_distributions(catalog_item_id: int) -> dict:
    try:
        return inspect_inport_item(catalog_item_id)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/inport/harvest")
def inport_harvest(
    keywords: str | None = None,
    per_keyword_limit: int = 5,
    max_items: int = 50,
) -> dict:
    try:
        keyword_list = (
            [keyword.strip() for keyword in keywords.split(",") if keyword.strip()]
            if keywords
            else list(DEFAULT_HARVEST_KEYWORDS)
        )
        return harvest_inport_catalog(
            keywords=keyword_list,
            per_keyword_limit=per_keyword_limit,
            max_items=max_items,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/noaa/ncei/station-summary")
def ncei_station_summary(latitude: float, longitude: float, days: int = 30) -> dict:
    try:
        return get_ncei_station_summary(latitude=latitude, longitude=longitude, days=days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
