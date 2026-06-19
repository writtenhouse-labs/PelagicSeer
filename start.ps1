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
$RunDir = Join-Path $Root ".run"
$StatePath = Join-Path $RunDir "processes.json"

function Get-PortConflicts {
  param(
    [int]$Port,
    [string]$ServiceName
  )

  $Listeners = @(
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
      Sort-Object OwningProcess -Unique
  )
  $ProcessSnapshot = @(Get-CimInstance Win32_Process)

  foreach ($Listener in $Listeners) {
    $Owner = $ProcessSnapshot | Where-Object { $_.ProcessId -eq $Listener.OwningProcess }
    $ApplicationName = $null
    $CurrentProcess = $Owner
    for ($Depth = 0; $CurrentProcess -and $Depth -lt 6; $Depth++) {
      if ($CurrentProcess.CommandLine -like "*\GardenProject\*") {
        $ApplicationName = "GardenProject"
        break
      }
      if ($CurrentProcess.CommandLine -like "*\PelagicSeer\*") {
        $ApplicationName = "PelagicSeer"
        break
      }
      $ParentId = $CurrentProcess.ParentProcessId
      $CurrentProcess = $ProcessSnapshot | Where-Object { $_.ProcessId -eq $ParentId }
    }
    if (-not $ApplicationName) {
      $ApplicationName = if ($Owner.Name) { $Owner.Name } else { "an unknown application" }
    }

    [pscustomobject]@{
      Service = $ServiceName
      Port = $Port
      Application = $ApplicationName
      ProcessId = $Listener.OwningProcess
    }
  }
}

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

if (Test-Path $StatePath) {
  $TrackedState = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
  $ProcessSnapshot = @(Get-CimInstance Win32_Process)
  $RunningProcesses = @(
    $TrackedState.processes | ForEach-Object {
      $TrackedProcess = $ProcessSnapshot | Where-Object { $_.ProcessId -eq [int]$_.id }
      if ($TrackedProcess -and $TrackedProcess.CommandLine -like "*$Root*") {
        $TrackedProcess
      }
    }
  )
  if ($RunningProcesses.Count -gt 0) {
    throw "PelagicSeer is already running. Use .\stop.ps1 before starting it again."
  }
  Remove-Item -LiteralPath $StatePath -Force
}

$PortConflicts = @(
  Get-PortConflicts -Port $ApiPort -ServiceName "API"
  Get-PortConflicts -Port $FrontendPort -ServiceName "frontend"
)
if ($PortConflicts.Count -gt 0) {
  Write-Host ""
  Write-Host "PelagicSeer cannot start because another application is using a required port:" -ForegroundColor Yellow
  foreach ($Conflict in $PortConflicts) {
    Write-Host "  $($Conflict.Service) port $($Conflict.Port): $($Conflict.Application) (PID $($Conflict.ProcessId))"
  }
  Write-Host ""
  Write-Host "Stop the conflicting application or choose different ports, for example:"
  Write-Host "  .\start.ps1 -ApiPort 8001 -FrontendPort 8502"
  exit 1
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
streamlit run app.py --server.address 127.0.0.1 --server.port $FrontendPort --server.headless true --server.fileWatcherType none --server.websocketPingInterval 30 --browser.gatherUsageStats false
"@

Write-Host "Starting PelagicSeer API at $ApiBaseUrl"
$BackendProcess = Start-Process powershell -WindowStyle Hidden -PassThru -ArgumentList @(
  "-NoExit",
  "-ExecutionPolicy",
  "Bypass",
  "-Command",
  $BackendCommand
)

Start-Sleep -Seconds 2

Write-Host "Starting PelagicSeer frontend at http://localhost:$FrontendPort"
$FrontendProcess = Start-Process powershell -WindowStyle Hidden -PassThru -ArgumentList @(
  "-NoExit",
  "-ExecutionPolicy",
  "Bypass",
  "-Command",
  $FrontendCommand
)

New-Item -ItemType Directory -Path $RunDir -Force | Out-Null
@{
  project = "PelagicSeer"
  root = $Root
  startedAt = (Get-Date).ToUniversalTime().ToString("o")
  processes = @(
    @{ name = "api"; id = $BackendProcess.Id }
    @{ name = "frontend"; id = $FrontendProcess.Id }
  )
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $StatePath -Encoding UTF8

Write-Host ""
Write-Host "PelagicSeer is starting."
Write-Host "API:      $ApiBaseUrl"
Write-Host "Frontend: http://localhost:$FrontendPort"
Write-Host "Stop:     .\stop.ps1"
Write-Host ""
Write-Host "Use -Install if you want to refresh dependencies:"
Write-Host "  .\start.ps1 -Install"
