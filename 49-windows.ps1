# Windows counterpart of the stage 49 controller.
# Calls 49-1-windows.ps1, 49-2-windows.ps1, and later Windows sub-stages in order.
# Offline-first. Does not call stage 9.
param(
    [string]$Verb = "--dry-run"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Show-Usage {
    Write-Output "Usage: powershell -File 49-windows.ps1 [--dry-run|--status|--verify|--install|--configure|--refresh|--repair|--help]"
    Write-Output "Windows entry for the same contract groups as 49.sh."
    Write-Output "Default is --dry-run. No packages and no network. Stage 9 is not called."
}

$known = @(
    "--dry-run", "--status", "--verify", "--install",
    "--configure", "--refresh", "--repair", "--help", "-h"
)
if ($Verb -eq "--help" -or $Verb -eq "-h") {
    Show-Usage
    exit 0
}
if ($known -notcontains $Verb) {
    Write-Error "49-windows: unknown argument: $Verb"
    exit 2
}

Write-Output "49-windows 9-Ball controller verb=$Verb offline=1 network=none jet_stage_9=untouched platform=windows"
$found = $false
foreach ($n in 1..30) {
    $stage = Join-Path $Root ("49-{0}-windows.ps1" -f $n)
    if (Test-Path $stage) {
        $found = $true
        & powershell -NoProfile -File $stage $Verb
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}
if (-not $found) {
    Write-Error "49-windows: no sub-stages were present"
    exit 1
}
exit 0
