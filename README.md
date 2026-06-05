# PelagicSeer

AI-powered fish intelligence platform.

## MVP
- NOAA weather integration
- Marine forecast analysis
- Species reporting
- Safety scoring

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

## Future Vision
- Historical catch prediction
- Machine learning models
- Personalized fishing recommendations
- Mobile application
