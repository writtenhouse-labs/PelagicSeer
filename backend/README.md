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
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Endpoints

- `GET /health`
- `POST /advice`

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
