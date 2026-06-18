# PelagicSeer

AI-powered fish intelligence platform.

## MVP
- NOAA weather integration (InPort, NCEI, GFW, COOPS, ERDAP, NDBC, OBIS)
- Marine forecast analysis
- Species reporting
- Prediction scoring

## Structure
- `backend/api` - FastAPI entry point and request schemas
- `backend/agents` - recommendation orchestration and future Claude/LangChain integration
- `backend/connectors` - external data source clients
- `backend/models` - fish movement modeling experiments
- `frontend` - Streamlit SPA
- `infra` - GCP deployment configuration placeholders

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
- Historical catch prediction
- Machine learning models
- Personalized fishing recommendations
- Mobile application
