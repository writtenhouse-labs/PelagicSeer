from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


_FULL_CONDITIONS = {
    "source": "noaa-live",
    "sea_surface_temp_f": 72.4,
    "wind_speed_kts": 9.0,
    "wave_height_ft": 2.1,
    "barometric_pressure_mb": 1016.2,
    "current_speed_kts": 0.8,
}

# Signals with both sources unavailable: contributes no scored factors, so the
# environmental score/confidence are unchanged. Lets /advice tests stay offline.
_NO_SIGNALS = {
    "species_input": "tuna",
    "scientific_name": "Thunnus",
    "name_resolved": True,
    "species_presence": {"available": False},
    "fishing_activity": {"available": False},
    "sources": [],
}


def test_advice_returns_live_conditions_and_recommendation(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.main.collect_conditions_with_fallback",
        lambda latitude, longitude: dict(_FULL_CONDITIONS),
    )
    monkeypatch.setattr(
        "api.main.collect_signals",
        lambda species, latitude, longitude: dict(_NO_SIGNALS),
    )

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
    assert body["conditions"]["source"] == "noaa-live"
    assert body["recommendation"]["score"] == 100
    assert body["recommendation"]["label"] == "excellent"
    assert body["recommendation"]["confidence"] == "high"
    assert body["recommendation"]["reasons"]


def test_advice_degrades_when_data_is_missing(monkeypatch) -> None:
    partial = {"source": "noaa-live", "sea_surface_temp_f": 72.4}
    monkeypatch.setattr(
        "api.main.collect_conditions_with_fallback",
        lambda latitude, longitude: dict(partial),
    )
    monkeypatch.setattr(
        "api.main.collect_signals",
        lambda species, latitude, longitude: dict(_NO_SIGNALS),
    )

    response = client.post(
        "/advice",
        json={"latitude": 32.7157, "longitude": -117.1611, "species": "tuna"},
    )

    assert response.status_code == 200
    recommendation = response.json()["recommendation"]
    assert recommendation["confidence"] == "low"
    assert set(recommendation["data_completeness"]["missing"]) == {
        "wind_speed_kts",
        "wave_height_ft",
        "current_speed_kts",
        "barometric_pressure_mb",
    }


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


def test_noaa_capabilities() -> None:
    response = client.get("/noaa/capabilities")

    assert response.status_code == 200
    sources = response.json()["sources"]
    assert {source["id"] for source in sources} >= {"coops", "ndbc", "erddap", "dismap"}


def test_latest_coops_observation(monkeypatch) -> None:
    def fake_latest_observation(station: str, product: str, units: str) -> dict:
        return {
            "source": "noaa-coops",
            "station": station,
            "product": product,
            "units": units,
            "observation": {"t": "2026-06-05 18:00", "v": "68.9"},
        }

    monkeypatch.setattr("api.main.get_latest_coops_observation", fake_latest_observation)

    response = client.get(
        "/noaa/coops/latest",
        params={"station": "9414290", "product": "water_temperature"},
    )

    assert response.status_code == 200
    assert response.json()["source"] == "noaa-coops"
    assert response.json()["station"] == "9414290"


def test_collector_normalizes_and_records_provenance(monkeypatch) -> None:
    from agents import environment_collector as ec

    monkeypatch.setattr(
        ec,
        "get_erddap_sst",
        lambda latitude, longitude: {
            "sea_surface_temp_f": 71.0,
            "dataset": "jplMURSST41",
            "observed_time": "2026-06-04T09:00:00Z",
        },
    )
    monkeypatch.setattr(
        ec,
        "find_nearest_ndbc_station",
        lambda latitude, longitude: {"station": "46086", "name": "SAN CLEMENTE BASIN", "distance_nm": 12.3},
    )
    monkeypatch.setattr(
        ec,
        "get_latest_ndbc_observation",
        lambda station: {"observation": {"WVHT": "0.9", "WSPD": "5.0", "PRES": "1015.0", "WTMP": "20.0"}},
    )

    conditions = ec.collect_conditions(32.7157, -117.1611)

    # ERDDAP wins for SST; NDBC supplies the rest, converted to english units.
    assert conditions["sea_surface_temp_f"] == 71.0
    assert conditions["provenance"]["sea_surface_temp_f"] == "noaa-erddap"
    assert conditions["wave_height_ft"] == 3.0  # 0.9 m
    assert conditions["wind_speed_kts"] == 9.7  # 5.0 m/s
    assert conditions["barometric_pressure_mb"] == 1015.0
    assert conditions["missing"] == ["current_speed_kts"]


def test_gfw_effort_endpoint(monkeypatch) -> None:
    def fake_effort(latitude: float, longitude: float, days: int) -> dict:
        return {
            "source": "global-fishing-watch",
            "total_apparent_fishing_hours": 142.5,
            "groups": [{"flag": "USA", "hours": 142.5}],
        }

    monkeypatch.setattr("api.main.get_fishing_effort", fake_effort)

    response = client.get("/gfw/effort", params={"latitude": 32.7, "longitude": -117.1})

    assert response.status_code == 200
    assert response.json()["source"] == "global-fishing-watch"
    assert response.json()["total_apparent_fishing_hours"] == 142.5


def test_gfw_effort_requires_token(monkeypatch) -> None:
    monkeypatch.delenv("GFW_API_TOKEN", raising=False)

    response = client.get("/gfw/effort", params={"latitude": 32.7, "longitude": -117.1})

    assert response.status_code == 400


def test_ncei_station_summary_endpoint(monkeypatch) -> None:
    def fake_summary(latitude: float, longitude: float, days: int) -> dict:
        return {
            "source": "noaa-ncei",
            "dataset": "GHCND",
            "station": {"station_id": "GHCND:USW00023188", "distance_km": 4.2},
            "record_count": 2,
            "observations": [{"date": "2026-05-01T00:00:00", "datatype": "TMAX", "value": 68}],
        }

    monkeypatch.setattr("api.main.get_ncei_station_summary", fake_summary)

    response = client.get(
        "/noaa/ncei/station-summary", params={"latitude": 32.7, "longitude": -117.1}
    )

    assert response.status_code == 200
    assert response.json()["source"] == "noaa-ncei"
    assert response.json()["station"]["station_id"] == "GHCND:USW00023188"


def test_ncei_requires_token(monkeypatch) -> None:
    monkeypatch.delenv("NOAA_NCDC_TOKEN", raising=False)

    response = client.get("/noaa/ncei/datasets")

    assert response.status_code == 400


def test_obis_occurrences_endpoint(monkeypatch) -> None:
    def fake_occurrences(scientificname, latitude, longitude, buffer_deg) -> dict:
        return {
            "source": "obis",
            "scientificname": scientificname,
            "total": 1234,
            "returned": 1,
            "depth_range_m": {"min": 5.0, "max": 220.0},
            "occurrences": [{"scientific_name": scientificname, "depth_m": 50.0, "year": 2021}],
        }

    monkeypatch.setattr("api.main.get_species_occurrences", fake_occurrences)

    response = client.get(
        "/obis/occurrences",
        params={"scientificname": "Thunnus albacares", "latitude": 32.7, "longitude": -117.1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "obis"
    assert body["total"] == 1234


def test_advisor_scores_signals() -> None:
    from agents.orchestrator import build_fishing_advice
    from api.schemas import AdviceRequest

    request = AdviceRequest(
        latitude=32.7, longitude=-117.1, species="tuna", target_depth_ft=250
    )
    signals = {
        "scientific_name": "Thunnus albacares",
        "name_resolved": True,
        "species_presence": {
            "available": True,
            "total": 5,
            "depth_range_m": {"min": 0.0, "max": 300.0},
        },
        "fishing_activity": {"available": True, "total_hours": 200.0, "in_season": True},
    }

    # No environmental data, so the base score of 50 isolates the signal factors:
    # species present (+10), depth match (+5), high effort (+10), in season (+5).
    result = build_fishing_advice(request, conditions={}, signals=signals)

    assert result["score"] == 80
    assert result["label"] == "excellent"
    assert set(result["signals_considered"]["used"]) == {
        "species_presence",
        "fishing_activity",
    }


def test_signal_factors_omitted_without_signals() -> None:
    from agents.orchestrator import build_fishing_advice
    from api.schemas import AdviceRequest

    request = AdviceRequest(latitude=32.7, longitude=-117.1, species="tuna")
    result = build_fishing_advice(request, conditions=dict(_FULL_CONDITIONS))

    # Backward compatible: no signals passed -> no signal section, env score only.
    assert "signals_considered" not in result
    assert result["score"] == 100


def test_resolve_scientific_name() -> None:
    from agents.signal_collector import resolve_scientific_name

    assert resolve_scientific_name("Yellowfin Tuna") == ("Thunnus albacares", True)
    assert resolve_scientific_name("tuna") == ("Thunnus", True)
    # Unmapped input falls back to the raw string, flagged unresolved.
    assert resolve_scientific_name("Gadus ogac") == ("Gadus ogac", False)
