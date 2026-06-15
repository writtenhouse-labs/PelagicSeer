import httpx

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _raise_offline(*args, **kwargs):
    """Stand-in for a connector that is unavailable, to keep unit tests offline."""
    raise ValueError("offline in test")


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
    "fao_fishstat_context": {"available": False},
    "bathymetry_context": {"available": False},
    "mrip_recreational_prior": {"available": False},
    "sources": [],
}


def test_advice_returns_live_conditions_and_recommendation(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.main.resolve_location",
        lambda city, state: {
            "city": city,
            "state": state,
            "latitude": 32.7157,
            "longitude": -117.1611,
            "ocean_distance_miles": 4.2,
            "too_far_from_ocean": False,
        },
    )
    monkeypatch.setattr(
        "api.main.collect_conditions_with_fallback",
        lambda latitude, longitude, plan=None: dict(_FULL_CONDITIONS),
    )
    monkeypatch.setattr(
        "api.main.collect_signals",
        lambda species, latitude, longitude, plan=None: dict(_NO_SIGNALS),
    )
    monkeypatch.setattr(
        "api.main.collect_area_species",
        lambda latitude, longitude, plan=None: {"available": False},
    )
    monkeypatch.setattr(
        "api.main.collect_survey_distribution",
        lambda species, latitude, longitude: {"available": False},
    )

    response = client.post(
        "/advice",
        json={
            "city": "San Diego",
            "state": "CA",
            "species": "tuna",
            "target_depth_ft": 20,
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


def test_advice_uses_working_noaa_station_coordinates_for_ocean_connectors(monkeypatch) -> None:
    station_latitude = 32.867
    station_longitude = -117.257
    calls = {}
    conditions = {
        **_FULL_CONDITIONS,
        "sources": [
            {
                "id": "noaa-ndbc",
                "status": "ok",
                "station": "SDBC1",
                "station_name": "San Diego, CA",
                "latitude": station_latitude,
                "longitude": station_longitude,
                "distance_nm": 4.1,
            }
        ],
        "missing": [],
    }

    monkeypatch.setattr(
        "api.main.resolve_location",
        lambda city, state: {
            "city": city,
            "state": state,
            "latitude": 32.7157,
            "longitude": -117.1611,
            "ocean_distance_miles": 4.2,
            "too_far_from_ocean": False,
            "nearest_ocean_station": {
                "station": "DEAD1",
                "latitude": 32.71,
                "longitude": -117.16,
            },
        },
    )
    monkeypatch.setattr(
        "api.main.collect_conditions_with_fallback",
        lambda latitude, longitude, plan=None: dict(conditions),
    )

    def fake_collect_signals(species, latitude, longitude, plan=None):
        calls["signals"] = (latitude, longitude)
        return dict(_NO_SIGNALS)

    def fake_collect_area_species(latitude, longitude, plan=None):
        calls["area_species"] = (latitude, longitude)
        return {"available": False}

    def fake_collect_survey_distribution(species, latitude, longitude):
        calls["survey_distribution"] = (latitude, longitude)
        return {"available": False}

    monkeypatch.setattr("api.main.collect_signals", fake_collect_signals)
    monkeypatch.setattr("api.main.collect_area_species", fake_collect_area_species)
    monkeypatch.setattr("api.main.collect_survey_distribution", fake_collect_survey_distribution)

    response = client.post(
        "/advice",
        json={"city": "San Diego", "state": "CA", "species": "tuna"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_location"]["latitude"] == station_latitude
    assert body["analysis_location"]["longitude"] == station_longitude
    assert body["analysis_location"]["station"] == "SDBC1"
    assert calls["signals"] == (station_latitude, station_longitude)
    assert calls["area_species"] == (station_latitude, station_longitude)
    assert calls["survey_distribution"] == (station_latitude, station_longitude)


def test_advice_degrades_when_data_is_missing(monkeypatch) -> None:
    partial = {"source": "noaa-live", "sea_surface_temp_f": 72.4}
    monkeypatch.setattr(
        "api.main.resolve_location",
        lambda city, state: {
            "city": city,
            "state": state,
            "latitude": 32.7157,
            "longitude": -117.1611,
            "ocean_distance_miles": 4.2,
            "too_far_from_ocean": False,
        },
    )
    monkeypatch.setattr(
        "api.main.collect_conditions_with_fallback",
        lambda latitude, longitude, plan=None: dict(partial),
    )
    monkeypatch.setattr(
        "api.main.collect_signals",
        lambda species, latitude, longitude, plan=None: dict(_NO_SIGNALS),
    )
    monkeypatch.setattr(
        "api.main.collect_area_species",
        lambda latitude, longitude, plan=None: {"available": False},
    )
    monkeypatch.setattr(
        "api.main.collect_survey_distribution",
        lambda species, latitude, longitude: {"available": False},
    )

    response = client.post(
        "/advice",
        json={"city": "San Diego", "state": "CA", "species": "tuna"},
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


def test_advice_validates_location() -> None:
    response = client.post(
        "/advice",
        json={
            "city": "",
            "state": "CA",
            "species": "tuna",
        },
    )

    assert response.status_code == 422


def test_advice_returns_too_far_message(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.main.resolve_location",
        lambda city, state: {
            "city": city,
            "state": state,
            "latitude": 33.4484,
            "longitude": -112.074,
            "ocean_distance_miles": 320.0,
            "too_far_from_ocean": True,
        },
    )

    response = client.post(
        "/advice",
        json={"city": "Phoenix", "state": "AZ", "species": "tuna"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation"]["summary"] == "You're too far from the Ocean to fish silly"
    assert body["conditions"] == {}


def test_noaa_capabilities() -> None:
    response = client.get("/noaa/capabilities")

    assert response.status_code == 200
    sources = response.json()["sources"]
    assert {source["id"] for source in sources} >= {
        "coops",
        "ndbc",
        "erddap",
        "dismap",
        "inport",
    }


def test_fao_fishstat_lists_configured_datasets() -> None:
    from connectors.fao import list_fishstat_datasets

    result = list_fishstat_datasets()

    assert result["source"] == "fao-fishstat"
    dataset_ids = {dataset["id"] for dataset in result["datasets"]}
    assert dataset_ids >= {"global_production", "capture", "aquaculture"}
    assert result["datasets"][0]["expected_fields"]


def test_fao_fishstat_extracts_collection_metadata() -> None:
    from connectors.fao import _extract_collection_page_metadata

    html = """
<html>
  <head>
    <link rel="canonical" href="https://www.fao.org/fishery/collection/capture/en">
    <title>Capture production | FAO</title>
    <meta name="description" content="Capture statistics by species and area.">
  </head>
</html>
"""
    fallback = {
        "name": "Capture Production",
        "collection_url": "https://www.fao.org/fishery/collection/capture/en",
        "description": "Fallback description.",
    }

    metadata = _extract_collection_page_metadata(html, fallback)

    assert metadata["canonical_url"] == "https://www.fao.org/fishery/collection/capture/en"
    assert metadata["page_title"] == "Capture production | FAO"
    assert metadata["page_description"] == "Capture statistics by species and area."


def test_fao_fishstat_rejects_unknown_dataset() -> None:
    from connectors.fao import get_fishstat_dataset_info

    try:
        get_fishstat_dataset_info("not-a-dataset")
    except ValueError as exc:
        assert "Unknown FAO FishStat dataset" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_fao_fishstat_datasets_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.main.list_fishstat_datasets",
        lambda: {
            "source": "fao-fishstat",
            "datasets": [{"id": "capture", "name": "Capture Production"}],
        },
    )

    response = client.get("/fao/fishstat/datasets")

    assert response.status_code == 200
    assert response.json()["datasets"][0]["id"] == "capture"


def test_fao_fishstat_dataset_info_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.main.get_fishstat_dataset_info",
        lambda dataset: {
            "source": "fao-fishstat",
            "dataset": dataset,
            "collection_url": "https://www.fao.org/fishery/collection/capture/en",
            "expected_fields": ["species", "year", "value"],
        },
    )

    response = client.get("/fao/fishstat/datasets/capture")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "fao-fishstat"
    assert body["dataset"] == "capture"
    assert body["expected_fields"] == ["species", "year", "value"]


def test_fao_fishstat_query_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.main.query_fishstat_data",
        lambda dataset, limit: {
            "source": "fao-fishstat",
            "dataset": dataset,
            "response": {"headers": ["year", "value"], "values": [[2024, 12.5]][:limit]},
        },
    )

    response = client.get("/fao/fishstat/query", params={"dataset": "capture", "limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["dataset"] == "capture"
    assert body["response"]["values"] == [[2024, 12.5]]


def test_fao_fishstat_species_summary_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.main.get_fishstat_species_summary",
        lambda species, scientific_name, dataset, limit: {
            "source": "fao-fishstat",
            "dataset": dataset,
            "species_query": species,
            "scientific_name": scientific_name,
            "available": True,
            "record_count": 2,
            "returned": limit,
            "year_range": {"min": 2023, "max": 2024},
            "measures": ["tonnes"],
            "records": [],
        },
    )

    response = client.get(
        "/fao/fishstat/species-summary",
        params={
            "species": "yellowfin tuna",
            "scientific_name": "Thunnus albacares",
            "limit": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "fao-fishstat"
    assert body["species_query"] == "yellowfin tuna"
    assert body["scientific_name"] == "Thunnus albacares"
    assert body["year_range"] == {"min": 2023, "max": 2024}


def test_fao_fishstat_species_summary_parses_positional_payload(monkeypatch) -> None:
    from connectors import fao

    monkeypatch.setattr(
        fao,
        "query_fishstat_data",
        lambda **kwargs: {
            "source": "fao-fishstat",
            "dataset": kwargs["dataset"],
            "response": {
                "headers": ["species", "year", "country", "value", "measure"],
                "values": [
                    ["Yellowfin tuna", 2024, "United States of America", 123.4, "tonnes"],
                    ["Yellowfin tuna", 2023, "Mexico", 50.0, "tonnes"],
                ],
            },
        },
    )

    summary = fao.get_fishstat_species_summary(
        species="yellowfin tuna",
        scientific_name="Thunnus albacares",
    )

    assert summary["available"] is True
    assert summary["record_count"] == 2
    assert summary["year_range"] == {"min": 2023, "max": 2024}
    assert summary["total_reported_value"] == 173.4
    assert summary["records"][0]["country"] == "United States of America"


def test_fao_fishstat_species_summary_uses_package_fallback_when_table_api_is_unavailable(
    monkeypatch,
) -> None:
    from connectors import fao

    def fake_query(**kwargs):
        raise ValueError("FAO FishStat table API did not return JSON")

    monkeypatch.setattr(fao, "query_fishstat_data", fake_query)
    monkeypatch.setattr(
        fao,
        "_fishstat_package_species_summary",
        lambda species, scientific_name, dataset, limit, detail: {
            "source": "fao-fishstat",
            "access": "fishstat-package",
            "dataset": dataset,
            "species_query": species,
            "scientific_name": scientific_name,
            "available": True,
            "record_count": 1,
            "returned": 1,
            "year_range": {"min": 2024, "max": 2024},
            "total_reported_value": 123.4,
            "measures": ["t"],
            "records": [{"species": "Yellowfin tuna", "year": 2024, "value": 123.4}],
            "detail": detail,
        },
    )

    summary = fao.get_fishstat_species_summary(
        species="yellowfin tuna",
        scientific_name="Thunnus albacares",
    )

    assert summary["available"] is True
    assert summary["access"] == "fishstat-package"
    assert summary["record_count"] == 1
    assert "package fallback" in summary["detail"]


def test_fao_fishstat_species_summary_degrades_when_all_sources_are_unavailable(
    monkeypatch,
) -> None:
    from connectors import fao

    def fake_query(**kwargs):
        raise ValueError("FAO FishStat table API did not return JSON")

    def fake_fallback(**kwargs):
        raise httpx.HTTPStatusError(
            "401 Unauthorized",
            request=httpx.Request("GET", "https://example.test/species/json"),
            response=httpx.Response(401),
        )

    monkeypatch.setattr(fao, "query_fishstat_data", fake_query)
    monkeypatch.setattr(fao, "_fishstat_package_species_summary", fake_fallback)

    summary = fao.get_fishstat_species_summary(
        species="yellowfin tuna",
        scientific_name="Thunnus albacares",
    )

    assert summary["available"] is False
    assert summary["record_count"] == 0
    assert summary["records"] == []
    assert "Table API error" in summary["detail"]
    assert "Package fallback error" in summary["detail"]


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
        lambda latitude, longitude, target_date=None: {
            "sea_surface_temp_f": 71.0,
            "dataset": "jplMURSST41",
            "observed_time": "2026-06-04T09:00:00Z",
        },
    )
    # Chlorophyll and CO-OPS unavailable here so the test stays offline and the
    # canonical fields come only from ERDDAP SST + NDBC.
    monkeypatch.setattr(
        ec,
        "get_erddap_chlorophyll",
        _raise_offline,
    )
    monkeypatch.setattr(
        ec,
        "find_nearest_coops_stations",
        lambda latitude, longitude, station_type="waterlevels", limit=5: [],
    )
    monkeypatch.setattr(
        ec,
        "find_nearest_ndbc_stations",
        lambda latitude, longitude: [
            {"station": "46086", "name": "SAN CLEMENTE BASIN", "distance_nm": 12.3}
        ],
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


def test_collector_tries_next_ndbc_station_when_realtime_feed_is_missing(
    monkeypatch,
) -> None:
    from agents import environment_collector as ec

    monkeypatch.setattr(
        ec,
        "get_erddap_sst",
        lambda latitude, longitude, target_date=None: {
            "sea_surface_temp_f": 71.0,
            "dataset": "jplMURSST41",
            "observed_time": "2026-06-04T09:00:00Z",
        },
    )
    monkeypatch.setattr(ec, "get_erddap_chlorophyll", _raise_offline)
    monkeypatch.setattr(
        ec,
        "find_nearest_coops_stations",
        lambda latitude, longitude, station_type="waterlevels", limit=5: [],
    )
    monkeypatch.setattr(
        ec,
        "find_nearest_ndbc_stations",
        lambda latitude, longitude: [
            {"station": "BAD1", "name": "Missing realtime", "distance_nm": 1.0},
            {"station": "GOOD1", "name": "Working realtime", "distance_nm": 5.0},
        ],
    )

    def fake_latest_ndbc(station: str) -> dict:
        if station == "BAD1":
            raise ValueError("404 Not Found")
        return {"observation": {"WVHT": "1.0", "WSPD": "4.0"}}

    monkeypatch.setattr(ec, "get_latest_ndbc_observation", fake_latest_ndbc)

    conditions = ec.collect_conditions(32.7157, -117.1611)

    ndbc_source = next(source for source in conditions["sources"] if source["id"] == "noaa-ndbc")
    assert ndbc_source["status"] == "ok"
    assert ndbc_source["station"] == "GOOD1"
    assert conditions["wave_height_ft"] == 3.3


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


def test_bathymetry_context_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.main.get_bathymetry_context",
        lambda latitude, longitude: {
            "source": "noaa-ncei-etopo",
            "available": True,
            "latitude": latitude,
            "longitude": longitude,
            "depth_ft": 1450.0,
            "nearby_relief_ft": 300.0,
            "structure": "strong_depth_break",
        },
    )

    response = client.get("/bathymetry/context", params={"latitude": 32.7, "longitude": -117.8})

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "noaa-ncei-etopo"
    assert body["structure"] == "strong_depth_break"


def test_mrip_recreational_prior_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.main.get_mrip_recreational_prior",
        lambda species, latitude, longitude, target_date: {
            "source": "noaa-mrip",
            "available": True,
            "species": species,
            "region": {"id": "atlantic", "label": "Atlantic coast"},
            "in_season": True,
        },
    )

    response = client.get(
        "/mrip/recreational-prior",
        params={"species": "tuna", "latitude": 35.0, "longitude": -75.0, "target_date": "2026-07-01"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "noaa-mrip"
    assert body["region"]["id"] == "atlantic"


def test_bathymetry_context_classifies_depth_break(monkeypatch) -> None:
    from connectors import bathymetry

    samples = {
        (32.7, -117.8): -400.0,
        (32.75, -117.8): -650.0,
        (32.65, -117.8): -380.0,
        (32.7, -117.75): -390.0,
        (32.7, -117.85): -700.0,
    }
    monkeypatch.setattr(
        bathymetry,
        "_sample_elevation",
        lambda latitude, longitude: samples[(round(latitude, 2), round(longitude, 2))],
    )

    context = bathymetry.get_bathymetry_context(32.7, -117.8, sample_offset_deg=0.05)

    assert context["available"] is True
    assert context["depth_m"] == 400.0
    assert context["nearby_relief_m"] == 320.0
    assert context["structure"] == "strong_depth_break"


def test_mrip_prior_reports_out_of_coverage() -> None:
    from connectors.mrip import get_mrip_recreational_prior

    prior = get_mrip_recreational_prior(
        species="yellowfin tuna",
        latitude=32.7,
        longitude=-117.1,
    )

    assert prior["available"] is False
    assert "outside" in prior["detail"]


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


def test_inport_classifies_distribution_urls() -> None:
    from connectors.inport import classify_distribution_url

    assert classify_distribution_url("https://example.gov/erddap/griddap/dataset.csv") == "ERDDAP"
    assert (
        classify_distribution_url("https://example.gov/arcgis/rest/services/fish/MapServer")
        == "ArcGIS REST"
    )
    assert classify_distribution_url("https://example.gov/thredds/catalog/data/catalog.xml") == "THREDDS"
    assert classify_distribution_url("https://example.gov/downloads/data.csv") == "CSV Download"
    assert classify_distribution_url("https://example.gov/downloads/data.zip") == "ZIP Download"
    assert classify_distribution_url("https://example.gov/api/v1/datasets/123") == "API Endpoint"
    assert classify_distribution_url("https://example.gov/dataset") == "Unknown"


def test_inport_parses_metadata_and_registers_connectors() -> None:
    from connectors.inport import parse_inport_metadata

    xml = """<?xml version="1.0" encoding="UTF-8"?>
<inport-metadata>
  <item-identification>
    <catalog-item-id>123</catalog-item-id>
    <title>Example InPort Dataset</title>
    <abstract>Useful dataset description.</abstract>
    <catalog-item-type>Data Set</catalog-item-type>
  </item-identification>
  <distribution-info>
    <distribution>
      <name>ERDDAP Access</name>
      <description>Access via https://coastwatch.noaa.gov/erddap/griddap/example.html</description>
    </distribution>
    <distribution>
      <name>ArcGIS Access</name>
      <description>Service at https://example.gov/arcgis/rest/services/fish/FeatureServer</description>
    </distribution>
    <distribution>
      <name>THREDDS Access</name>
      <description>Catalog https://example.gov/thredds/catalog/model/catalog.xml</description>
    </distribution>
  </distribution-info>
  <urls>
    <url>
      <url>https://example.gov/data/latest.csv</url>
      <name>CSV data</name>
      <url-type>Download</url-type>
      <description>Download CSV</description>
    </url>
    <url>
      <url>https://example.gov/data/archive.zip</url>
      <name>ZIP data</name>
      <url-type>Download</url-type>
      <description>Download ZIP</description>
    </url>
    <url>
      <url>https://example.gov/api/v1/query?f=json</url>
      <name>API</name>
      <url-type>API</url-type>
      <description>API endpoint</description>
    </url>
    <url>
      <url>https://example.gov/readme</url>
      <name>Readme</name>
      <url-type>Online Resource</url-type>
      <description>Landing page</description>
    </url>
  </urls>
  <catalog-details>
    <guid>gov.noaa.nmfs.inport:123</guid>
    <owner-organization>Test Org</owner-organization>
  </catalog-details>
</inport-metadata>"""

    metadata = parse_inport_metadata(xml)

    assert metadata["catalog_item_id"] == "123"
    assert metadata["title"] == "Example InPort Dataset"
    assert metadata["description"] == "Useful dataset description."
    assert metadata["distribution_count"] == 7
    assert {item["classification"] for item in metadata["distributions"]} == {
        "ERDDAP",
        "ArcGIS REST",
        "THREDDS",
        "CSV Download",
        "ZIP Download",
        "API Endpoint",
        "Unknown",
    }
    assert {item["connector"] for item in metadata["distributions"]} >= {
        "erddap",
        "arcgis_rest",
        "thredds",
    }


def test_inport_parses_search_results() -> None:
    from connectors.inport import parse_inport_search_results

    html = """
<html>
  <body>
    <a href="/inport/item/123">Yellowfin Tuna Survey</a>
    <a href="/inport/item/456?tab=summary"><span>Longline Observer Data</span></a>
    <a href="/inport/item/123">Duplicate Tuna Survey</a>
  </body>
</html>
"""

    hits = parse_inport_search_results(html, keyword="tuna", limit=10)

    assert hits == [
        {
            "catalog_item_id": "123",
            "title": "Yellowfin Tuna Survey",
            "search_keyword": "tuna",
            "item_url": "https://www.fisheries.noaa.gov/inport/item/123",
        },
        {
            "catalog_item_id": "456",
            "title": "Longline Observer Data",
            "search_keyword": "tuna",
            "item_url": "https://www.fisheries.noaa.gov/inport/item/456?tab=summary",
        },
    ]


def test_inport_harvest_catalog_builds_agent_dictionary(monkeypatch) -> None:
    from connectors import inport

    def fake_search(keyword: str, limit: int) -> list[dict[str, str]]:
        return [
            {
                "catalog_item_id": "123",
                "title": f"{keyword} title",
                "search_keyword": keyword,
                "item_url": "https://www.fisheries.noaa.gov/inport/item/123",
            }
        ]

    def fake_inspect(catalog_item_id: str) -> dict:
        return {
            "catalog_item_id": catalog_item_id,
            "title": "NOAA Pelagic Longline Observer Program",
            "description": "Observer data for pelagic longline fisheries.",
            "distributions": [
                {
                    "url": "https://example.gov/erddap/tabledap/observer.csv",
                    "classification": "ERDDAP",
                    "connector": "erddap",
                }
            ],
        }

    monkeypatch.setattr(inport, "search_inport", fake_search)
    monkeypatch.setattr(inport, "inspect_inport_item", fake_inspect)

    harvest = inport.harvest_inport_catalog(keywords=["tuna", "observer"], per_keyword_limit=2)

    assert harvest["item_count"] == 1
    assert harvest["catalog"]["123"]["title"] == "NOAA Pelagic Longline Observer Program"
    assert harvest["catalog"]["123"]["description"] == "Observer data for pelagic longline fisheries."
    assert harvest["catalog"]["123"]["matched_keywords"] == ["tuna", "observer"]
    assert harvest["catalog"]["123"]["primary_distribution_url"] == (
        "https://example.gov/erddap/tabledap/observer.csv"
    )
    assert harvest["catalog"]["123"]["distribution_urls"] == [
        "https://example.gov/erddap/tabledap/observer.csv"
    ]


def test_inport_distribution_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.main.inspect_inport_item",
        lambda catalog_item_id: {
            "source": "inport",
            "catalog_item_id": str(catalog_item_id),
            "title": "Example",
            "distribution_count": 1,
            "distributions": [
                {
                    "url": "https://example.gov/data.csv",
                    "classification": "CSV Download",
                    "connector": "csv_download",
                }
            ],
        },
    )

    response = client.get("/inport/items/123/distributions")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "inport"
    assert body["distributions"][0]["connector"] == "csv_download"


def test_inport_harvest_endpoint(monkeypatch) -> None:
    def fake_harvest(keywords: list[str], per_keyword_limit: int, max_items: int) -> dict:
        return {
            "source": "inport",
            "keywords": keywords,
            "item_count": 1,
            "catalog": {
                "123": {
                    "catalog_item_id": "123",
                    "title": "Example",
                    "description": "Example metadata",
                    "distribution_urls": ["https://example.gov/data.csv"],
                }
            },
            "errors": [],
        }

    monkeypatch.setattr("api.main.harvest_inport_catalog", fake_harvest)

    response = client.get(
        "/inport/harvest",
        params={"keywords": "tuna, surface temperature", "per_keyword_limit": 2, "max_items": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["keywords"] == ["tuna", "surface temperature"]
    assert body["catalog"]["123"]["distribution_urls"] == ["https://example.gov/data.csv"]


def test_obis_ocean_map_endpoint(monkeypatch) -> None:
    def fake_ocean_map(
        scientificname: str,
        ocean: str | None,
        size: int,
        startdate: str | None,
        enddate: str | None,
        search_rank: str,
    ) -> dict:
        return {
            "source": "obis",
            "scientificname": scientificname,
            "search_rank": search_rank,
            "ocean": ocean,
            "search_area": ocean or "All oceans",
            "total": 10,
            "returned": 2,
            "point_count": 1,
            "date_range": {"start": startdate, "end": enddate},
            "year_range": {"min": 2020, "max": 2024},
            "points": [
                {
                    "latitude": 12.3,
                    "longitude": -45.6,
                    "occurrences": 2,
                    "radius_m": 100000,
                    "scientific_name": scientificname,
                }
            ],
        }

    monkeypatch.setattr("api.main.get_species_ocean_map", fake_ocean_map)

    response = client.get(
        "/obis/ocean-map",
        params={
            "species": "yellowfin tuna",
            "search_rank": "Species",
            "size": 500,
            "startdate": "2026-06-03",
            "enddate": "2026-06-10",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scientificname"] == "Thunnus albacares"
    assert body["name_resolved"] is True
    assert body["common_name"] == "Yellowfin Tuna"
    assert body["search_rank"] == "Species"
    assert body["search_area"] == "All oceans"
    assert body["date_range"] == {"start": "2026-06-03", "end": "2026-06-10"}
    assert body["points"][0]["occurrences"] == 2
    assert "Atlantic Ocean" in body["available_oceans"]


def test_obis_ocean_map_accepts_family_search(monkeypatch) -> None:
    def fake_ocean_map(
        scientificname: str,
        ocean: str | None,
        size: int,
        startdate: str | None,
        enddate: str | None,
        search_rank: str,
    ) -> dict:
        return {
            "source": "obis",
            "scientificname": scientificname,
            "search_rank": search_rank,
            "ocean": ocean,
            "search_area": "All oceans",
            "total": 4,
            "returned": 1,
            "point_count": 1,
            "date_range": {"start": startdate, "end": enddate},
            "year_range": {"min": 2025, "max": 2025},
            "points": [],
        }

    monkeypatch.setattr("api.main.get_species_ocean_map", fake_ocean_map)

    response = client.get(
        "/obis/ocean-map",
        params={
            "species": "Clupeidae",
            "search_rank": "Family",
            "startdate": "2026-06-03",
            "enddate": "2026-06-10",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scientificname"] == "Clupeidae"
    assert body["search_rank"] == "Family"
    assert body["name_resolved"] is False
    assert body["common_name"] is None


def test_advisor_scores_signals() -> None:
    from agents.orchestrator import build_fishing_advice
    from api.schemas import AdviceRequest

    request = AdviceRequest(city="San Diego", state="CA", species="tuna", target_depth_ft=20)
    signals = {
        "scientific_name": "Thunnus albacares",
        "name_resolved": True,
        "species_presence": {
            "available": True,
            "total": 5,
            "depth_range_m": {"min": 0.0, "max": 300.0},
        },
        "fishing_activity": {
            "available": True,
            "recent_hours": 20.0,
            "total_hours": 200.0,
            "in_season": True,
        },
        "target_species_activity": {
            "available": True,
            "likely_recent_target_activity": True,
            "species_occurrences_nearby": 5,
            "recent_fishing_hours_nearby": 20.0,
            "gfw_species_specific": False,
        },
        "fao_fishstat_context": {
            "available": True,
            "record_count": 2,
            "year_range": {"min": 2023, "max": 2024},
            "measures": ["tonnes"],
        },
        "bathymetry_context": {
            "available": True,
            "depth_ft": 260.0,
            "nearby_relief_ft": 450.0,
            "structure": "strong_depth_break",
        },
        "mrip_recreational_prior": {
            "available": True,
            "region": {"id": "atlantic", "label": "Atlantic coast"},
            "in_season": True,
        },
    }

    # No environmental data, so the base score of 50 isolates the signal factors:
    # species present (+10), depth match (+5), recent effort (+8), in season (+5),
    # recent effort overlapping known habitat (+7), FAO global context (+3),
    # bathymetry depth/structure (+10), and MRIP seasonality (+4).
    result = build_fishing_advice(request, conditions={}, signals=signals)

    assert result["score"] == 96
    assert result["label"] == "excellent"
    assert set(result["signals_considered"]["used"]) == {
        "species_presence",
        "fishing_activity",
        "target_species_activity",
        "fao_fishstat_context",
        "bathymetry_context",
        "mrip_recreational_prior",
    }
    assert any("FAO FishStat" in reason for reason in result["reasons"])
    assert any("bathymetric relief" in reason for reason in result["reasons"])
    assert any("MRIP recreational catch" in reason for reason in result["reasons"])


def test_collect_signals_combines_gfw_recent_effort_with_species_presence(
    monkeypatch,
) -> None:
    from datetime import date

    from agents import signal_collector as sc

    monkeypatch.setattr(
        sc,
        "get_species_occurrences",
        lambda scientific_name, latitude, longitude, buffer_deg: {
            "total": 3,
            "returned": 3,
            "depth_range_m": {"min": 0.0, "max": 200.0},
            "year_range": {"min": 2024, "max": 2026},
        },
    )
    days_requested: list[int] = []

    def fake_effort(latitude: float, longitude: float, days: int, today: date) -> dict:
        days_requested.append(days)
        if days == 30:
            return {"total_apparent_fishing_hours": 12.5, "by_month": {"2026-06": 12.5}}
        return {
            "total_apparent_fishing_hours": 90.0,
            "by_month": {"2026-04": 25.0, "2026-05": 50.0, "2026-06": 12.5},
        }

    monkeypatch.setattr(sc, "get_fishing_effort", fake_effort)
    monkeypatch.setattr(
        sc,
        "get_fishstat_species_summary",
        lambda species, scientific_name, dataset: {
            "available": True,
            "record_count": 2,
            "year_range": {"min": 2023, "max": 2024},
            "measures": ["tonnes"],
        },
    )
    monkeypatch.setattr(
        sc,
        "get_bathymetry_context",
        lambda latitude, longitude: {
            "available": True,
            "depth_ft": 260.0,
            "nearby_relief_ft": 450.0,
            "structure": "strong_depth_break",
        },
    )
    monkeypatch.setattr(
        sc,
        "get_mrip_recreational_prior",
        lambda species, latitude, longitude, target_date: {
            "available": True,
            "region": {"id": "atlantic", "label": "Atlantic coast"},
            "in_season": True,
        },
    )

    signals = sc.collect_signals("tuna", 32.7157, -117.1611, today=date(2026, 6, 8))

    assert days_requested == [30, 365]
    assert signals["target_species_activity"]["available"] is True
    assert signals["target_species_activity"]["likely_recent_target_activity"] is True
    assert signals["target_species_activity"]["gfw_species_specific"] is False
    assert signals["fao_fishstat_context"]["available"] is False
    assert signals["bathymetry_context"]["available"] is True
    assert signals["mrip_recreational_prior"]["available"] is True
    assert any(
        source["id"] == "fao-fishstat" and source["status"] == "skipped"
        for source in signals["sources"]
    )
    assert {source["id"] for source in signals["sources"]} >= {
        "obis",
        "global-fishing-watch",
        "fao-fishstat",
        "noaa-ncei-etopo",
        "noaa-mrip",
    }


def test_signal_factors_omitted_without_signals() -> None:
    from agents.orchestrator import build_fishing_advice
    from api.schemas import AdviceRequest

    request = AdviceRequest(city="San Diego", state="CA", species="tuna")
    result = build_fishing_advice(request, conditions=dict(_FULL_CONDITIONS))

    # Backward compatible: no signals passed -> no signal section, env score only.
    assert "signals_considered" not in result
    assert result["score"] == 100


def test_temporal_router_classifies_windows() -> None:
    from datetime import date

    from agents.temporal_router import resolve_temporal_plan

    today = date(2026, 6, 10)

    live = resolve_temporal_plan(date(2026, 6, 8), date(2026, 6, 12), today=today)
    assert live.mode == "live"
    assert live.includes_today is True
    assert live.target_date == today

    historical = resolve_temporal_plan(date(2026, 5, 1), date(2026, 5, 31), today=today)
    assert historical.mode == "historical"
    assert historical.target_date == date(2026, 5, 31)
    assert historical.days_span == 31

    forecast = resolve_temporal_plan(date(2026, 7, 1), date(2026, 7, 5), today=today)
    assert forecast.mode == "forecast"
    assert forecast.target_date == date(2026, 7, 1)  # soonest forecastable day


def test_advisor_caps_confidence_for_future_window() -> None:
    from datetime import date

    from agents.orchestrator import build_fishing_advice
    from agents.temporal_router import resolve_temporal_plan
    from api.schemas import AdviceRequest

    request = AdviceRequest(city="San Diego", state="CA", species="tuna")
    plan = resolve_temporal_plan(date(2026, 7, 1), date(2026, 7, 5), today=date(2026, 6, 10))

    # Full conditions would normally yield high confidence; a future window caps it.
    result = build_fishing_advice(request, conditions=dict(_FULL_CONDITIONS), plan=plan)

    assert result["temporal_mode"] == "forecast"
    assert result["confidence"] == "medium"


def test_advisor_scores_chlorophyll_when_present() -> None:
    from agents.orchestrator import build_fishing_advice
    from api.schemas import AdviceRequest

    request = AdviceRequest(city="San Diego", state="CA", species="tuna")
    conditions = dict(_FULL_CONDITIONS)
    conditions["chlorophyll_mg_m3"] = 0.5  # productive water -> +8, but capped at 100

    result = build_fishing_advice(request, conditions=conditions)
    assert any("productive water" in reason for reason in result["reasons"])


def test_collect_area_species_annotates_common_names(monkeypatch) -> None:
    from agents import signal_collector as sc

    monkeypatch.setattr(
        sc,
        "get_area_species",
        lambda latitude, longitude, buffer_deg, startdate, enddate, limit: {
            "source": "obis",
            "total_species": 2,
            "species": [
                {"scientific_name": "Thunnus albacares", "records": 120, "taxon_rank": "Species"},
                {"scientific_name": "Coryphaena hippurus", "records": 40, "taxon_rank": "Species"},
            ],
        },
    )

    result = sc.collect_area_species(32.7157, -117.1611)

    assert result["available"] is True
    assert result["species"][0]["common_name"] == "Yellowfin Tuna"
    assert result["species"][1]["common_name"] in {"Mahi-Mahi", "Dorado", "Mahi"}


def test_species_in_area_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.main.collect_area_species",
        lambda latitude, longitude, plan=None, buffer_deg=2.0, limit=25: {
            "available": True,
            "total_species": 1,
            "species": [{"scientific_name": "Thunnus albacares", "records": 9, "common_name": "Yellowfin Tuna"}],
        },
    )

    response = client.get(
        "/species/in-area",
        params={"latitude": 32.7, "longitude": -117.1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["species"][0]["common_name"] == "Yellowfin Tuna"


def test_resolve_scientific_name() -> None:
    from agents.signal_collector import resolve_common_name, resolve_scientific_name

    assert resolve_scientific_name("Yellowfin Tuna") == ("Thunnus albacares", True)
    assert resolve_scientific_name("tuna") == ("Thunnus", True)
    assert resolve_scientific_name("Atlantic Herring") == ("Clupea harengus", True)
    assert resolve_common_name("Thunnus albacares") == "Yellowfin Tuna"
    assert resolve_common_name("Clupea harengus") == "Atlantic Herring"
    # Unmapped input falls back to the raw string, flagged unresolved.
    assert resolve_scientific_name("Gadus ogac") == ("Gadus ogac", False)


def test_arcgis_query_builds_params_and_extracts_features(monkeypatch) -> None:
    from connectors import arcgis_rest

    captured: dict = {}

    def fake_request_json(url, params):
        captured["url"] = url
        captured["params"] = params
        return {
            "features": [
                {"attributes": {"Species": "Sebastes", "WTCPUE": 3.2}, "geometry": {"x": 1, "y": 2}}
            ],
            "exceededTransferLimit": False,
        }

    monkeypatch.setattr(arcgis_rest, "_request_json", fake_request_json)

    result = arcgis_rest.query_arcgis_layer(
        "https://example.gov/arcgis/rest/services/Demo/FeatureServer/1",
        where="Species = 'Sebastes'",
        out_fields="Species,WTCPUE",
        envelope=(32.0, -118.0, 33.0, -117.0),
        result_record_count=50,
        order_by="Year DESC",
    )

    assert captured["url"].endswith("/FeatureServer/1/query")
    assert captured["params"]["where"] == "Species = 'Sebastes'"
    assert captured["params"]["geometryType"] == "esriGeometryEnvelope"
    assert captured["params"]["resultRecordCount"] == 50
    assert result["returned"] == 1
    assert result["features"][0]["attributes"]["WTCPUE"] == 3.2
    # returnGeometry defaulted to false, so geometry is dropped.
    assert "geometry" not in result["features"][0]


def test_arcgis_query_raises_on_error_payload(monkeypatch) -> None:
    import pytest

    from connectors import arcgis_rest

    monkeypatch.setattr(
        arcgis_rest,
        "_request_json",
        lambda url, params: (_ for _ in ()).throw(ValueError("ArcGIS REST error: bad where")),
    )
    with pytest.raises(ValueError):
        arcgis_rest.query_arcgis_layer("https://example.gov/x/FeatureServer/0")


def test_dismap_region_for_point() -> None:
    from connectors.dismap import region_for_point

    assert region_for_point(32.7, -117.16)[0] == "WC"  # San Diego
    assert region_for_point(27.5, -90.0)[0] == "GMEX"  # Gulf of Mexico
    assert region_for_point(0.0, -30.0) is None  # mid-Atlantic: no survey region


def test_dismap_distribution_summarizes(monkeypatch) -> None:
    from connectors import dismap

    monkeypatch.setattr(
        dismap,
        "query_arcgis_layer",
        lambda layer_url, where, out_fields, result_record_count, order_by: {
            "returned": 2,
            "features": [
                {"attributes": {"CommonName": "Lingcod", "WTCPUE": 4.0, "Year": 2022, "Depth": 80.0, "Latitude": 47.1, "Longitude": -124.5}},
                {"attributes": {"CommonName": "Lingcod", "WTCPUE": 0.0, "Year": 2020, "Depth": 60.0, "Latitude": 46.9, "Longitude": -124.2}},
            ],
        },
    )

    result = dismap.get_dismap_distribution("Ophiodon elongatus", 47.0, -124.4)

    assert result["region"] == "WC"
    assert result["common_name"] == "Lingcod"
    assert result["present_samples"] == 1  # only the WTCPUE>0 sample counts
    assert result["wtcpue"] == {"min": 4.0, "max": 4.0, "mean": 4.0}
    assert result["year_range"] == {"min": 2020, "max": 2022}


def test_collect_survey_distribution_degrades_outside_region() -> None:
    from agents.signal_collector import collect_survey_distribution

    # Mid-ocean point is covered by no DisMAP region, so this degrades offline
    # (region resolution fails before any network call).
    result = collect_survey_distribution("lingcod", 0.0, -30.0)
    assert result["available"] is False
    assert "DisMAP" in result["detail"]


def test_catalog_discovery_keeps_only_supported_connectors(monkeypatch) -> None:
    from agents import catalog_discovery as cd

    def fake_harvest(keywords, per_keyword_limit, max_items):
        return {
            "catalog": {
                "1": {
                    "catalog_item_id": "1",
                    "title": "Queryable ERDDAP dataset",
                    "item_url": "https://inport/item/1",
                    "matched_keywords": keywords,
                    "distributions": [
                        {"url": "https://x/erddap/griddap/d.json", "connector": "erddap", "classification": "ERDDAP"}
                    ],
                },
                "2": {
                    "catalog_item_id": "2",
                    "title": "Portal-only item",
                    "item_url": "https://inport/item/2",
                    "matched_keywords": keywords,
                    "distributions": [
                        {"url": "https://x/landing", "connector": "unknown", "classification": "Unknown"}
                    ],
                },
            },
            "errors": [],
        }

    monkeypatch.setattr(cd, "harvest_inport_catalog", fake_harvest)

    result = cd.discover_catalog(
        dimension_keywords={"sea_surface_temperature": ["sst"]},
        per_keyword_limit=2,
        max_items_per_dimension=5,
    )

    entries = result["catalog"]["sea_surface_temperature"]
    assert [entry["catalog_item_id"] for entry in entries] == ["1"]
    assert entries[0]["connectors"] == ["erddap"]
    assert result["item_count"] == 1


def test_catalog_registry_endpoint() -> None:
    response = client.get("/catalog/registry")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "inport-registry"
    assert "species_distribution" in body["dimension_keywords"]
    # DisMAP (66799) is pinned under species distribution.
    ids = {entry["catalog_item_id"] for entry in body["pinned_catalog"]["species_distribution"]}
    assert "66799" in ids


def test_catalog_discover_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.main.discover_catalog",
        lambda per_keyword_limit, max_items_per_dimension: {
            "source": "inport-discovery",
            "item_count": 1,
            "catalog": {"species_distribution": [{"catalog_item_id": "66799"}]},
            "errors": [],
        },
    )

    response = client.get("/catalog/discover")

    assert response.status_code == 200
    assert response.json()["item_count"] == 1


def test_dismap_distribution_endpoint(monkeypatch) -> None:
    def fake_distribution(scientificname, latitude, longitude, region=None) -> dict:
        return {
            "source": "noaa-dismap",
            "scientificname": scientificname,
            "region": "WC",
            "present_samples": 5,
            "points": [],
        }

    monkeypatch.setattr("api.main.get_dismap_distribution", fake_distribution)

    response = client.get(
        "/dismap/distribution",
        params={"species": "lingcod", "latitude": 47.0, "longitude": -124.4},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "noaa-dismap"
    assert body["species_input"] == "lingcod"
    # Common name resolved to scientific name before querying DisMAP.
    assert body["scientificname"] == "Ophiodon elongatus"


# --- Phase 5: NWS forecast + NCEI anomaly ---------------------------------

_NWS_FORECAST_PAYLOAD = {
    "properties": {
        "periods": [
            {
                "name": "Today",
                "startTime": "2026-07-01T06:00:00-07:00",
                "isDaytime": True,
                "temperature": 68,
                "temperatureUnit": "F",
                "windSpeed": "5 to 10 mph",
                "windDirection": "NW",
                "shortForecast": "Sunny",
            },
            {
                "name": "Tonight",
                "startTime": "2026-07-01T18:00:00-07:00",
                "isDaytime": False,
                "temperature": 58,
                "temperatureUnit": "F",
                "windSpeed": "5 mph",
                "windDirection": "W",
                "shortForecast": "Clear",
            },
        ]
    }
}


def test_nws_forecast_selects_daytime_period(monkeypatch) -> None:
    from datetime import date

    from connectors import nws

    def fake_get(url, params=None):
        if url.endswith("/points/47.0000,-124.5000"):
            return {"properties": {"forecast": "https://api.weather.gov/x/forecast", "gridId": "SEW"}}
        return _NWS_FORECAST_PAYLOAD

    monkeypatch.setattr(nws, "_get", fake_get)

    result = nws.get_nws_forecast(47.0, -124.5, target_date=date(2026, 7, 1))

    assert result["source"] == "nws-forecast"
    assert result["forecast_office"] == "SEW"
    assert result["is_daytime"] is True
    assert result["air_temp_f"] == 68
    # "5 to 10 mph" -> high end 10 mph -> ~8.7 kts.
    assert result["wind_speed_kts"] == 8.7
    assert result["short_forecast"] == "Sunny"


def test_nws_marine_wave_converts_meters(monkeypatch) -> None:
    from datetime import date

    from connectors import nws

    def fake_get(url, params=None):
        if "/points/" in url:
            return {"properties": {
                "forecast": "https://api.weather.gov/x/forecast",
                "forecastGridData": "https://api.weather.gov/x/grid",
            }}
        return {"properties": {"waveHeight": {"uom": "wmoUnit:m", "values": [
            {"validTime": "2026-07-01T18:00:00+00:00/PT6H", "value": 1.5},
        ]}}}

    monkeypatch.setattr(nws, "_get", fake_get)

    result = nws.get_nws_marine_wave(47.0, -124.5, target_date=date(2026, 7, 1))
    assert result["wave_height_ft"] == 4.9  # 1.5 m


def test_nws_raises_outside_coverage(monkeypatch) -> None:
    import pytest

    from connectors import nws

    monkeypatch.setattr(nws, "_get", lambda url, params=None: {"properties": {}})
    with pytest.raises(ValueError):
        nws.get_nws_forecast(0.0, 0.0)


def test_collector_uses_nws_forecast_in_forecast_mode(monkeypatch) -> None:
    from datetime import date

    from agents import environment_collector as ec
    from agents.temporal_router import resolve_temporal_plan

    monkeypatch.setattr(
        ec, "get_erddap_sst",
        lambda latitude, longitude, target_date=None: {"sea_surface_temp_f": 60.0, "dataset": "jplMURSST41"},
    )
    monkeypatch.setattr(ec, "get_erddap_chlorophyll", _raise_offline)
    monkeypatch.setattr(
        ec, "find_nearest_coops_stations",
        lambda latitude, longitude, station_type="waterlevels", limit=5: [],
    )
    monkeypatch.setattr(ec, "find_nearest_ndbc_stations", _raise_offline)
    monkeypatch.setattr(
        ec, "get_nws_forecast",
        lambda latitude, longitude, target_date=None: {
            "wind_speed_kts": 12.0,
            "air_temp_f": 66,
            "short_forecast": "Breezy",
            "forecast_office": "SEW",
            "forecast_time": "2026-07-01T06:00:00-07:00",
        },
    )
    monkeypatch.setattr(
        ec, "get_nws_marine_wave",
        lambda latitude, longitude, target_date=None: {"wave_height_ft": 5.2, "valid_time": "x"},
    )

    plan = resolve_temporal_plan(date(2026, 7, 1), date(2026, 7, 5), today=date(2026, 6, 10))
    conditions = ec.collect_conditions(47.0, -124.5, plan=plan)

    assert conditions["wind_speed_kts"] == 12.0
    assert conditions["provenance"]["wind_speed_kts"] == "nws-forecast"
    assert conditions["wave_height_ft"] == 5.2
    assert conditions["air_temp_f"] == 66
    assert conditions["weather_forecast"] == "Breezy"


def test_advisor_forecast_note_credits_nws() -> None:
    from datetime import date

    from agents.orchestrator import build_fishing_advice
    from agents.temporal_router import resolve_temporal_plan
    from api.schemas import AdviceRequest

    request = AdviceRequest(city="Westport", state="WA", species="tuna")
    conditions = dict(_FULL_CONDITIONS)
    conditions["provenance"] = {"wind_speed_kts": "nws-forecast"}
    plan = resolve_temporal_plan(date(2026, 7, 1), date(2026, 7, 5), today=date(2026, 6, 10))

    result = build_fishing_advice(request, conditions=conditions, plan=plan)

    assert result["temporal_mode"] == "forecast"
    assert result["confidence"] == "medium"  # capped for a future window
    assert any("NWS forecast" in reason for reason in result["reasons"])


def test_ncei_temperature_anomaly_computes(monkeypatch) -> None:
    from datetime import date

    from connectors import noaa_ncei

    def fake_get(path, params):
        if path == "stations":
            return {"results": [{
                "id": "GHCND:TEST", "name": "Test Station",
                "latitude": 47.0, "longitude": -124.5,
                "mindate": "2000-01-01", "maxdate": "2026-06-30",
            }]}
        # /data: warmer in the current (target) year than the baseline years.
        warm = params["startdate"].startswith("2026")
        tmax, tmin = (66, 46) if warm else (60, 40)
        return {"results": [{"datatype": "TMAX", "value": tmax}, {"datatype": "TMIN", "value": tmin}]}

    monkeypatch.setattr(noaa_ncei, "_get", fake_get)
    monkeypatch.setenv("NOAA_NCDC_TOKEN", "test-token")

    result = noaa_ncei.get_ncei_temperature_anomaly(
        47.0, -124.5, target_date=date(2026, 6, 10), baseline_years=3, today=date(2026, 6, 10)
    )

    assert result["current_mean_f"] == 56.0  # (66+46)/2
    assert result["baseline_mean_f"] == 50.0  # (60+40)/2
    assert result["anomaly_f"] == 6.0
    assert result["baseline_years"] == [2023, 2024, 2025]


def test_nws_forecast_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.main.get_nws_forecast",
        lambda latitude, longitude, target_date=None: {
            "source": "nws-forecast", "wind_speed_kts": 9.0, "short_forecast": "Sunny",
        },
    )

    response = client.get("/nws/forecast", params={"latitude": 47.0, "longitude": -124.5})

    assert response.status_code == 200
    assert response.json()["source"] == "nws-forecast"


def test_ncei_anomaly_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.main.get_ncei_temperature_anomaly",
        lambda latitude, longitude, target_date=None, baseline_years=5: {
            "source": "noaa-ncei", "anomaly_f": 2.3, "current_mean_f": 60.0, "baseline_mean_f": 57.7,
        },
    )

    response = client.get("/noaa/ncei/anomaly", params={"latitude": 47.0, "longitude": -124.5})

    assert response.status_code == 200
    assert response.json()["anomaly_f"] == 2.3
