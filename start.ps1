param(
  [switch]$Install,
  [int]$ApiPort = 8000,
  [int]$FrontendPort = 8501,
  [int]$AdviceTimeoutSeconds = 110,
  [int]$MapperTimeoutSeconds = 30,
  [int]$FaoTimeoutSeconds = 60,
  [int]$HttpTimeoutSeconds = 15,
  [int]$ErddapTimeoutSeconds = 20
)

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$BackendVenv = Join-Path $BackendDir ".venv"
$FrontendVenv = Join-Path $FrontendDir ".venv"

function New-ProjectVenv {
  param(
    [string]$ProjectDir,
    [string]$VenvDir
  )

  if (Test-Path $VenvDir) {
    return
  }

  Write-Host "Creating virtual environment: $VenvDir"
  Push-Location $ProjectDir
  try {
    if (Get-Command py -ErrorAction SilentlyContinue) {
      py -3.10 -m venv .venv
    } else {
      python -m venv .venv
    }
  } finally {
    Pop-Location
  }
}

function Install-Requirements {
  param(
    [string]$ProjectDir,
    [string]$VenvDir
  )

  $Python = Join-Path $VenvDir "Scripts\python.exe"
  $Requirements = Join-Path $ProjectDir "requirements.txt"

  if (-not (Test-Path $Python)) {
    throw "Python executable not found in $VenvDir"
  }

  if (-not (Test-Path $Requirements)) {
    throw "requirements.txt not found in $ProjectDir"
  }

  Write-Host "Installing requirements for $ProjectDir"
  & $Python -m pip install -r $Requirements
}

New-ProjectVenv -ProjectDir $BackendDir -VenvDir $BackendVenv
New-ProjectVenv -ProjectDir $FrontendDir -VenvDir $FrontendVenv

if ($Install) {
  Install-Requirements -ProjectDir $BackendDir -VenvDir $BackendVenv
  Install-Requirements -ProjectDir $FrontendDir -VenvDir $FrontendVenv
}

$ApiBaseUrl = "http://127.0.0.1:$ApiPort"

$BackendCommand = @"
Set-Location '$BackendDir'
`$host.UI.RawUI.WindowTitle = 'PelagicSeer API'
& '.\.venv\Scripts\Activate.ps1'
`$env:PELAGICSEER_HTTP_TIMEOUT_SECONDS = '$HttpTimeoutSeconds'
`$env:PELAGICSEER_FAO_HTTP_TIMEOUT_SECONDS = '$FaoTimeoutSeconds'
`$env:PELAGICSEER_ERDDAP_TIMEOUT_SECONDS = '$ErddapTimeoutSeconds'
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port $ApiPort
"@

$FrontendCommand = @"
Set-Location '$FrontendDir'
`$host.UI.RawUI.WindowTitle = 'PelagicSeer Frontend'
& '.\.venv\Scripts\Activate.ps1'
`$env:PELAGICSEER_API_BASE_URL = '$ApiBaseUrl'
`$env:PELAGICSEER_ADVICE_TIMEOUT_SECONDS = '$AdviceTimeoutSeconds'
`$env:PELAGICSEER_MAPPER_TIMEOUT_SECONDS = '$MapperTimeoutSeconds'
`$env:PELAGICSEER_FAO_TIMEOUT_SECONDS = '$FaoTimeoutSeconds'
streamlit run app.py --server.address 127.0.0.1 --server.port $FrontendPort --server.headless true --server.fileWatcherType none --browser.gatherUsageStats false
"@

Write-Host "Starting PelagicSeer API at $ApiBaseUrl"
Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-ExecutionPolicy",
  "Bypass",
  "-Command",
  $BackendCommand
)

Start-Sleep -Seconds 2

Write-Host "Starting PelagicSeer frontend at http://localhost:$FrontendPort"
Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-ExecutionPolicy",
  "Bypass",
  "-Command",
  $FrontendCommand
)

Write-Host ""
Write-Host "PelagicSeer is starting."
Write-Host "API:      $ApiBaseUrl"
Write-Host "Frontend: http://localhost:$FrontendPort"
Write-Host ""
Write-Host "Use -Install if you want to refresh dependencies:"
Write-Host "  .\start.ps1 -Install"
