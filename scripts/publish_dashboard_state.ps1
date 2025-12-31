# ======================================================================
# StreamSuites — Local Dashboard State Publisher
# Mirrors GitHub Action behavior
# Owner: Brainstream Media Group
# ======================================================================

# Resolve paths relative to this script location
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

$RuntimeRoot   = Resolve-Path ".."
$DashboardRoot = Resolve-Path "..\..\StreamSuites-Dashboard"

$Source = Join-Path $RuntimeRoot "runtime\exports"
$Dest   = Join-Path $DashboardRoot "docs\shared\state"

Write-Host ""
Write-Host "------------------------------------------------------------"
Write-Host "StreamSuites — Publishing Runtime State to Dashboard"
Write-Host "------------------------------------------------------------"
Write-Host "Runtime source:   $Source"
Write-Host "Dashboard target: $Dest"
Write-Host ""

if (!(Test-Path $Source)) {
    Write-Error "Runtime exports not found: $Source"
    Write-Host ""
    Write-Host "Press any key to close..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

if (!(Test-Path $Dest)) {
    Write-Host "Destination folder does not exist — creating it"
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
}

Write-Host "Syncing runtime snapshots → dashboard..."
Write-Host ""

robocopy $Source $Dest /MIR /NFL /NDL /NJH /NJS /NC /NS

Write-Host ""
Write-Host "------------------------------------------------------------"
Write-Host "Dashboard state sync complete."
Write-Host "------------------------------------------------------------"
Write-Host ""
Write-Host "Press any key to close..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
