from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_advice_returns_mock_conditions_and_recommendation() -> None:
    response = client.post(
        "/advice",
        json={
            "latitude": 32.7157,
            "longitude": -117.1611,
            "species": "tuna",
            "target_depth_ft": 250,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["species"] == "tuna"
    assert body["conditions"]["source"] == "mock-noaa"
    assert body["recommendation"]["score"] == 100
    assert body["recommendation"]["label"] == "excellent"
    assert body["recommendation"]["reasons"]


def test_advice_validates_coordinates() -> None:
    response = client.post(
        "/advice",
        json={
            "latitude": 120,
            "longitude": -117.1611,
            "species": "tuna",
        },
    )

    assert response.status_code == 422
