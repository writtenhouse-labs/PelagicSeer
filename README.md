# PelagicSeer

AI-powered fish intelligence platform.

## Live Development Site

Use the current development deployment at:

**[https://pelagicseer-frontend-542566523617.us-central1.run.app/](https://pelagicseer-frontend-542566523617.us-central1.run.app/)**

This is an experimental development service. Results can be incomplete, delayed,
or unavailable when an upstream public data service is slow or offline.

## AI Authorship

The PelagicSeer codebase was written by AI under human direction. Claude was
used to build the initial project framework, and OpenAI Codex wrote the majority
of the implementation, integrations, tests, deployment tooling, and
documentation.

## What PelagicSeer Does

- Combines public ocean, weather, biological, survey, fishing-effort, and
  fisheries-production data.
- Produces an explainable fishing-conditions score rather than claiming to
  predict an actual catch.
- Reports which sources returned data, which fields are missing, and how much
  confidence to place in the result.
- Provides a multi-source map for OBIS occurrence records and FAO FishStat
  production context.

PelagicSeer is an experimental decision-support tool, not a navigation,
weather-warning, fisheries-management, or catch-guarantee system.

## Data Integrations and Limitations

| Integration | Data used by PelagicSeer | Important limitations |
|---|---|---|
| [OpenStreetMap Nominatim](https://nominatim.org/release-docs/latest/api/Search/) | Converts a city and state into latitude and longitude. | Geocoding can be ambiguous, reflects mapped place data rather than marine conditions, and is subject to the public service's availability and usage policy. |
| [NOAA CoastWatch ERDDAP / NASA JPL MUR SST](https://coastwatch.pfeg.noaa.gov/erddap/info/jplMURSST41/index.html) | Daily global analyzed sea-surface temperature at approximately 0.01-degree resolution. | This is a blended satellite and in-situ analysis, not a thermometer reading at the requested fishing spot. Near-real-time values can be revised, clouds and interpolation affect source observations, and future requests use the latest observation as a proxy rather than an SST forecast. As verified on **June 18, 2026**, this SST dataset was active with coverage through **May 13, 2026**. |
| [NOAA CoastWatch ERDDAP / Aqua MODIS chlorophyll](https://coastwatch.pfeg.noaa.gov/erddap/info/erdMH1chla8day/index.html) | Eight-day chlorophyll-a composite used as a marine-productivity proxy. | The configured dataset is stale: its published coverage ends **June 14, 2022**, despite its title saying "present." Chlorophyll is not fish abundance, and cloud cover, coastal water, suspended sediment, and the eight-day averaging window can distort its usefulness. |
| [NOAA NDBC](https://www.ndbc.noaa.gov/) | Nearest working buoy or C-MAN station observations, including waves, wind, pressure, and water temperature when available. | Stations are sparse offshore, individual stations omit some measurements, feeds can be delayed or unavailable, and the nearest station may be far from the requested location. PelagicSeer tries several nearby stations but does not spatially model conditions between them. |
| [NOAA CO-OPS Tides and Currents](https://tidesandcurrents.noaa.gov/api/) | Currents, water level, and salinity from product-specific coastal stations. | Coverage is concentrated near U.S. coasts, ports, and estuaries. Different measurements often come from different stations, salinity and currents have much thinner coverage than water level, and coastal observations may not represent offshore conditions. |
| [National Weather Service API](https://www.weather.gov/documentation/services-web-api) | Forecast wind, air temperature, narrative weather, and marine-wave grid values for future date windows. | Coverage is primarily the United States and its territories. Forecast grids are not direct observations, marine-wave values are not available everywhere, forecast skill declines with lead time, and PelagicSeer has no true future SST forecast. |
| [OBIS](https://obis.org/manual/access/) | Species occurrence records, nearby species checklists, observation coordinates, dates, years, and recorded depths. | OBIS shows where a species has been recorded, not where it is now or how many fish are present. Records are opportunistic and unevenly sampled, can be old, can contain identification or coordinate errors, and absence of records is not evidence that a species is absent. Mapper results are sampled and aggregated rather than exhaustive. |
| [Global Fishing Watch](https://globalfishingwatch.org/our-apis/documentation) | AIS-derived **apparent fishing-effort hours** by location and time, used for recent activity and seasonality context. | GFW does **not** tell PelagicSeer the number, weight, or species of fish caught. Effort is inferred from vessel behavior, not verified catch. Non-AIS, poorly received, spoofed, or intentionally dark vessels can be missing, and small/recreational boats are underrepresented. The integration requires an API token. |
| [FAO FishStat](https://www.fao.org/fishery/en/statistics) | Global capture and aquaculture production records by species/item, year, country, and FAO fishing area; displayed as broad production context. | FishStat is aggregated, delayed statistical reporting, not live fishing conditions or local bite activity. FAO-area map markers use representative area centroids rather than exact catch locations. Species-name matching and reporting practices vary, and the first package download/load can be slow. It is excluded from the advice hot path by default. |
| [NOAA NCEI Climate Data Online](https://www.ncei.noaa.gov/cdo-web/webservices/v2) | Historical daily temperature summaries and a temperature-anomaly calculation for historical windows. | This connector uses the nearest qualifying **land climate station**, so it is contextual climate data rather than ocean temperature. It requires an NCEI token, station histories can be incomplete, and the anomaly is calculated from a limited local baseline rather than a full ocean climatology. |
| [NOAA NCEI ETOPO 2022](https://www.ncei.noaa.gov/products/etopo-global-relief-model) | Seafloor elevation, estimated depth, nearby relief, and a simple structure/slope proxy. | ETOPO is a global relief model, not current sonar. Its resolution cannot resolve many small reefs, wrecks, ledges, or rapidly changing seabed features. PelagicSeer's "structure" classification is derived from a few nearby samples and should not be used for navigation. |
| [NOAA Fisheries DisMAP](https://apps-st.fisheries.noaa.gov/dismap/DisMAP.html) through [ArcGIS REST](https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/) | Regional fishery-independent survey samples, biomass/catch-per-unit-effort values, depth, year, and survey distribution for matching species. | Coverage is limited to configured U.S. survey regions and is strongest for bottom-trawl, groundfish, and benthic species. It is often a poor fit for highly pelagic targets such as tuna. PelagicSeer uses a pinned **July 1, 2024** DisMAP service snapshot, and a survey observation is not a live fish-location signal. |
| [NOAA MRIP](https://www.fisheries.noaa.gov/recreational-fishing-data/marine-recreational-information-program) | A curated regional and monthly recreational-fishing seasonality prior plus links to MRIP data products. | The current connector does not query live catch estimates. It uses conservative regional bounds and a small hand-maintained species-season mapping, so unsupported species receive only general coverage context. MRIP itself is survey-based, revised, delayed, and focused on U.S. recreational fisheries. |
| [NOAA Fisheries InPort](https://www.fisheries.noaa.gov/inport/) | Catalog metadata and distribution URLs used to discover and classify potential NOAA datasets and services. | InPort is a metadata catalog, not the underlying observation feed. Records and links can be incomplete, stale, duplicated, or human-facing rather than machine-queryable. PelagicSeer uses a pinned registry for normal advice requests instead of repeatedly crawling the catalog. |

## Scoring Caveats

PelagicSeer combines signals heuristically. A higher score means the available
conditions and historical context look more favorable according to the current
rules; it does not mean fish are present or that a catch is likely. In
particular:

- GFW effort is not species-specific catch data.
- OBIS occurrences are historical records, not live detections.
- Chlorophyll is a productivity proxy, not fish abundance.
- FAO and MRIP data describe broad historical activity, not current conditions.
- Forecast windows use forecast wind and waves but latest-observation SST.
- If every live environmental source fails, the development app can fall back
  to clearly labeled mock conditions so the interface remains testable.

## Structure

- `backend/api` - FastAPI entry point and request schemas.
- `backend/agents` - deterministic data collection and recommendation orchestration.
- `backend/connectors` - external public-data clients.
- `backend/models` - fish-movement modeling experiments.
- `frontend` - Streamlit application and multi-source mapper.
- `infra` - Google Cloud Run deployment tooling.

See `docs/noaa_data_sources.md` for NOAA source options and agent ideas.

## Run Backend

```powershell
cd C:\Users\sarah\Source\Repos\PelagicSeer\backend
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn api.main:app --reload
```

## Run Frontend

```powershell
cd C:\Users\sarah\Source\Repos\PelagicSeer\frontend
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Run Everything

```powershell
cd C:\Users\sarah\Source\Repos\PelagicSeer
.\start.ps1
```

Use `.\start.ps1 -Install` to create missing virtual environments and refresh dependencies before starting.

Stop both local services with:

```powershell
.\stop.ps1
```

## Timeout Budgets

The local launcher applies interactive latency budgets suited to each interface:

- Fishing advice request: 110 seconds
- OBIS multi-source mapper request: 30 seconds
- FAO FishStat mapper request: 60 seconds
- General upstream data source request: 15 seconds
- NOAA ERDDAP request: 20 seconds
- FAO FishStat upstream request: 60 seconds

Override them with the corresponding `start.ps1` parameters or these environment
variables: `PELAGICSEER_ADVICE_TIMEOUT_SECONDS`,
`PELAGICSEER_MAPPER_TIMEOUT_SECONDS`, `PELAGICSEER_FAO_TIMEOUT_SECONDS`,
`PELAGICSEER_HTTP_TIMEOUT_SECONDS`, `PELAGICSEER_ERDDAP_TIMEOUT_SECONDS`, and
`PELAGICSEER_FAO_HTTP_TIMEOUT_SECONDS`.

Cloud Run uses a separate request timeout. The API service is deployed with a
120-second request timeout. The Streamlit frontend is deployed with a
3600-second timeout because its browser session uses a long-lived WebSocket;
this does not change the frontend's 110-second advice API timeout.
The frontend deployment also enables Cloud Run session affinity so a
reconnecting Streamlit client returns to the instance holding its session.

Deploy both services with:

```powershell
.\infra\deploy.ps1
```

## Future Vision

- Replace stale environmental datasets with actively maintained equivalents.
- Add measured validation against historical catch outcomes.
- Train and evaluate machine-learning models only after establishing reliable
  ground-truth data.
- Add personalized recommendations and a mobile application.
