from fastapi import FastAPI

from agents.orchestrator import build_fishing_advice
from api.schemas import AdviceRequest
from connectors.noaa_erddap import get_mock_conditions

app = FastAPI(title="PelagicSeer API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/advice")
def advice(request: AdviceRequest) -> dict:
    conditions = get_mock_conditions(request.latitude, request.longitude)
    recommendation = build_fishing_advice(request, conditions)

    return {
        "location": {
            "latitude": request.latitude,
            "longitude": request.longitude,
        },
        "species": request.species,
        "conditions": conditions,
        "recommendation": recommendation,
    }
