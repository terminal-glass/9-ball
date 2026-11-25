# Windows counterpart of 49-5. Same five pieces as 49-5.sh.
# Offline-first. Does not call stage 9.
param([string]$Verb = "--dry-run")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
Write-Output "49-5-windows platform=windows"
$python = $null
foreach ($name in @("python", "python3")) {
    if (Get-Command $name -ErrorAction SilentlyContinue) { $python = $name; break }
}
if (-not $python) { Write-Error "49-5-windows: Python 3 is required and was not found"; exit 1 }
& $python -m osamp.stage 49-5 $Verb
exit $LASTEXITCODE
