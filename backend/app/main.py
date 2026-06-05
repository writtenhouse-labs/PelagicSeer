from fastapi import FastAPI

from app.models.request import AdviceRequest
from app.services.advisor import build_fishing_advice
from app.services.noaa_client import get_mock_conditions

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
