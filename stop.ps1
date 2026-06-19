$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$RunDir = Join-Path $Root ".run"
$StatePath = Join-Path $RunDir "processes.json"
$ProcessSnapshot = @(Get-CimInstance Win32_Process)

function Stop-ProcessTree {
  param([int]$ProcessId)

  $Children = @(
    $ProcessSnapshot | Where-Object { $_.ParentProcessId -eq $ProcessId }
  )
  foreach ($Child in $Children) {
    Stop-ProcessTree -ProcessId $Child.ProcessId
  }

  if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
  }
}

$TrackedIds = @()
if (Test-Path $StatePath) {
  try {
    $State = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    $TrackedIds = @(
      $State.processes | ForEach-Object {
        $Process = $ProcessSnapshot | Where-Object { $_.ProcessId -eq [int]$_.id }
        if ($Process -and $Process.CommandLine -like "*$Root*") {
          [int]$_.id
        }
      }
    )
  } catch {
    Write-Warning "The saved process state could not be read; searching for PelagicSeer processes instead."
  }
}

if ($TrackedIds.Count -eq 0) {
  $Candidates = @(
    $ProcessSnapshot | Where-Object {
      $_.ProcessId -ne $PID -and
      $_.CommandLine -like "*$Root*" -and
      ($_.CommandLine -match "uvicorn|streamlit")
    }
  )
  $CandidateIds = @($Candidates.ProcessId)
  $TrackedIds = @(
    $Candidates |
      Where-Object { $_.ParentProcessId -notin $CandidateIds } |
      ForEach-Object { [int]$_.ProcessId }
  )
}

if ($TrackedIds.Count -eq 0) {
  Write-Host "PelagicSeer is not running."
} else {
  foreach ($ProcessId in $TrackedIds) {
    Stop-ProcessTree -ProcessId $ProcessId
  }
  Write-Host "PelagicSeer has stopped."
}

if (Test-Path $StatePath) {
  Remove-Item -LiteralPath $StatePath -Force
}
if ((Test-Path $RunDir) -and -not (Get-ChildItem -LiteralPath $RunDir -Force)) {
  Remove-Item -LiteralPath $RunDir -Force
}
