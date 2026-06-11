# PelagicSeer Backend

Simple FastAPI service for local fishing advice experiments.

## Setup

```powershell
cd C:\Users\sarah\Source\Repos\PelagicSeer\backend
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run Locally

```powershell
uvicorn api.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Endpoints

- `GET /health`
- `POST /advice` — pulls conditions (ERDDAP satellite SST + chlorophyll, nearest NDBC buoy, nearest CO-OPS currents/water-level/salinity stations), species presence + fishing effort, a list of species recorded in the area, and DisMAP survey distribution for the target species, then scores everything and reports confidence based on how much real data was available. Falls back to mock data only if every source fails. Accepts an optional `start_date`/`end_date` window: a window including today runs live; a past window queries archives and adds an NCEI climate anomaly; a future window pulls the NWS wind/wave forecast for the window start (SST stays a latest-observation proxy) and caps confidence.
- `GET /species/in-area?latitude=32.7&longitude=-117.1` — lists the species recorded near a point (OBIS checklist), ranked by record count, optionally restricted with `startdate`/`enddate`.
- `GET /dismap/distribution?species=lingcod&latitude=47&longitude=-124.5` — NOAA DisMAP survey biomass (WTCPUE) distribution for a species; the covering survey region is inferred from the point (mostly U.S. groundfish surveys, so pelagic targets degrade gracefully).
- `GET /catalog/registry` — the pinned InPort catalog registry: per-dimension search keywords and curated catalog item IDs (no network).
- `GET /catalog/discover` — runs the CatalogDiscoveryAgent: harvests InPort per dimension and keeps items exposing an ERDDAP/ArcGIS-REST/THREDDS/API connector. Slow (hits InPort).
- `GET /noaa/capabilities`
- `GET /noaa/coops/latest?station=9414290&product=water_level`
- `GET /noaa/ndbc/latest/{station}`
- `GET /gfw/effort?latitude=32.7&longitude=-117.1&days=30` — recent apparent fishing effort near a point from Global Fishing Watch.
- `GET /obis/occurrences?scientificname=Thunnus%20albacares&latitude=32.7&longitude=-117.1` — marine species occurrence records near a point from OBIS (no token).
- `GET /inport/items/{catalog_item_id}/distributions` — reads NOAA InPort metadata, extracts distribution URLs, classifies each URL, and reports the matching PelagicSeer connector type.
- `GET /inport/harvest` — searches NOAA InPort for PelagicSeer keywords, inspects each item, and returns an agent-friendly catalog keyed by InPort item ID.
- `GET /noaa/ncei/datasets` — list NCEI/CDO datasets (handy token check).
- `GET /noaa/ncei/station-summary?latitude=32.7&longitude=-117.1&days=30` — recent daily summaries from the nearest *active* NCEI station.
- `GET /noaa/ncei/anomaly?latitude=47&longitude=-124.5` — mean-temperature anomaly for a point/date vs. the same time of year over the preceding years at the nearest GHCND station (token-gated).
- `GET /nws/forecast?latitude=47&longitude=-124.5` — NWS wind/temperature/narrative forecast for a point, optionally for a `target_date` (U.S. coverage only); the forecast source behind the temporal router's future-window mode.

## API tokens

Tokens are read from environment variables so they never land in source control.
Set them persistently at User scope (survives reboots and new processes):

```powershell
# Global Fishing Watch — https://globalfishingwatch.org/our-apis/tokens
[Environment]::SetEnvironmentVariable('GFW_API_TOKEN', 'your-gfw-token', 'User')

# NOAA NCEI / NCDC Climate Data Online — https://www.ncdc.noaa.gov/cdo-web/token
[Environment]::SetEnvironmentVariable('NOAA_NCDC_TOKEN', 'your-noaa-token', 'User')
```

CO-OPS, NDBC, ERDDAP, and OBIS are open APIs and need no token.

Example request:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/advice `
  -ContentType "application/json" `
  -Body '{"latitude":32.7157,"longitude":-117.1611,"species":"tuna","target_depth_ft":250}'
```

## Test

```powershell
pytest
```
