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
        lambda latitude, longitude: dict(_FULL_CONDITIONS),
    )
    monkeypatch.setattr(
        "api.main.collect_signals",
        lambda species, latitude, longitude: dict(_NO_SIGNALS),
    )

    response = client.post(
        "/advice",
        json={
            "city": "San Diego",
            "state": "CA",
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
        lambda latitude, longitude: dict(partial),
    )
    monkeypatch.setattr(
        "api.main.collect_signals",
        lambda species, latitude, longitude: dict(_NO_SIGNALS),
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
        lambda latitude, longitude: {
            "sea_surface_temp_f": 71.0,
            "dataset": "jplMURSST41",
            "observed_time": "2026-06-04T09:00:00Z",
        },
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

    request = AdviceRequest(city="San Diego", state="CA", species="tuna", target_depth_ft=250)
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
    }

    # No environmental data, so the base score of 50 isolates the signal factors:
    # species present (+10), depth match (+5), recent effort (+8), in season (+5),
    # and recent effort overlapping known habitat (+7).
    result = build_fishing_advice(request, conditions={}, signals=signals)

    assert result["score"] == 85
    assert result["label"] == "excellent"
    assert set(result["signals_considered"]["used"]) == {
        "species_presence",
        "fishing_activity",
        "target_species_activity",
    }


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

    signals = sc.collect_signals("tuna", 32.7157, -117.1611, today=date(2026, 6, 8))

    assert days_requested == [30, 365]
    assert signals["target_species_activity"]["available"] is True
    assert signals["target_species_activity"]["likely_recent_target_activity"] is True
    assert signals["target_species_activity"]["gfw_species_specific"] is False


def test_signal_factors_omitted_without_signals() -> None:
    from agents.orchestrator import build_fishing_advice
    from api.schemas import AdviceRequest

    request = AdviceRequest(city="San Diego", state="CA", species="tuna")
    result = build_fishing_advice(request, conditions=dict(_FULL_CONDITIONS))

    # Backward compatible: no signals passed -> no signal section, env score only.
    assert "signals_considered" not in result
    assert result["score"] == 100


def test_resolve_scientific_name() -> None:
    from agents.signal_collector import resolve_common_name, resolve_scientific_name

    assert resolve_scientific_name("Yellowfin Tuna") == ("Thunnus albacares", True)
    assert resolve_scientific_name("tuna") == ("Thunnus", True)
    assert resolve_scientific_name("Atlantic Herring") == ("Clupea harengus", True)
    assert resolve_common_name("Thunnus albacares") == "Yellowfin Tuna"
    assert resolve_common_name("Clupea harengus") == "Atlantic Herring"
    # Unmapped input falls back to the raw string, flagged unresolved.
    assert resolve_scientific_name("Gadus ogac") == ("Gadus ogac", False)
