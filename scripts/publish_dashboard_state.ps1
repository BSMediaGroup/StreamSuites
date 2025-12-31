# ======================================================================
# StreamSuites — Local Dashboard State Publisher
# Mirrors GitHub Action behavior
# ======================================================================

# Resolve paths
$RuntimeRoot   = Resolve-Path ".."
$DashboardRoot = Resolve-Path "..\..\StreamSuites-Dashboard"

$Source = Join-Path $RuntimeRoot "runtime\exports"
$Dest   = Join-Path $DashboardRoot "docs\shared\state"

if (!(Test-Path $Source)) {
    Write-Error "Runtime exports not found: $Source"
    exit 1
}

if (!(Test-Path $Dest)) {
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
}

Write-Host "Syncing runtime snapshots → dashboard..."
robocopy $Source $Dest /MIR /NFL /NDL /NJH /NJS /NC /NS

Write-Host "Dashboard state sync complete."
