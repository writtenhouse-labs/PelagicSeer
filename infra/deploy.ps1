param(
  [string]$Project = "pelagicseer-dev",
  [string]$Region = "us-central1",
  [string]$Gcloud = "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$ApiUrl = "https://pelagicseer-api-542566523617.us-central1.run.app"

if (-not (Test-Path $Gcloud)) {
  throw "gcloud was not found at $Gcloud"
}

Write-Host "Deploying PelagicSeer API..."
& $Gcloud run deploy pelagicseer-api `
  --project $Project `
  --region $Region `
  --source $BackendDir `
  --timeout 120 `
  --update-env-vars "PYTHONPATH=/workspace,PELAGICSEER_HTTP_TIMEOUT_SECONDS=15,PELAGICSEER_FAO_HTTP_TIMEOUT_SECONDS=60,PELAGICSEER_ERDDAP_TIMEOUT_SECONDS=20,PELAGICSEER_INCLUDE_FAO_IN_ADVICE=false" `
  --quiet

Write-Host "Deploying PelagicSeer frontend..."
& $Gcloud run deploy pelagicseer-frontend `
  --project $Project `
  --region $Region `
  --source $FrontendDir `
  --timeout 3600 `
  --session-affinity `
  --min 1 `
  --max 3 `
  --concurrency 10 `
  --update-env-vars "PELAGICSEER_API_BASE_URL=$ApiUrl,PELAGICSEER_ADVICE_TIMEOUT_SECONDS=110,PELAGICSEER_MAPPER_TIMEOUT_SECONDS=30,PELAGICSEER_FAO_TIMEOUT_SECONDS=60" `
  --remove-env-vars "PELAGICSEER_API_TIMEOUT_SECONDS" `
  --quiet

Write-Host "PelagicSeer deployment complete."
