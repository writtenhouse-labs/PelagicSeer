import httpx
from fastapi import FastAPI
from fastapi import HTTPException

from agents.environment_collector import collect_conditions_with_fallback
from agents.orchestrator import build_fishing_advice
from agents.signal_collector import collect_signals
from api.schemas import AdviceRequest
from connectors.gfw import get_fishing_effort
from connectors.obis import get_species_occurrences
from connectors.noaa_coops import get_latest_coops_observation
from connectors.noaa_ncei import get_ncei_datasets, get_ncei_station_summary
from connectors.noaa_ndbc import get_latest_ndbc_observation
from services.location_resolver import TOO_FAR_MESSAGE, resolve_location

app = FastAPI(title="PelagicSeer API")


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

    if location["too_far_from_ocean"]:
        return {
            "location": location,
            "species": request.species,
            "conditions": {},
            "signals": {},
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

    conditions = collect_conditions_with_fallback(latitude, longitude)
    signals = collect_signals(request.species, latitude, longitude)
    recommendation = build_fishing_advice(request, conditions, signals)

    return {
        "location": location,
        "species": request.species,
        "conditions": conditions,
        "signals": signals,
        "recommendation": recommendation,
    }


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
        ]
    }


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


@app.get("/noaa/ncei/datasets")
def ncei_datasets(limit: int = 25) -> dict:
    try:
        return get_ncei_datasets(limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/noaa/ncei/station-summary")
def ncei_station_summary(latitude: float, longitude: float, days: int = 30) -> dict:
    try:
        return get_ncei_station_summary(latitude=latitude, longitude=longitude, days=days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
