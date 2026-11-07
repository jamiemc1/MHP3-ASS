<#
.SYNOPSIS
    Launch the original application, building it first if needed.

.DESCRIPTION
    The application loads Data\... relative to its working directory, so it
    must start from legacy\Run.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\windows\run-gui.ps1
#>
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$exe = Join-Path $repoRoot "legacy\Release\Athena's ASS MHP3rd.exe"
if (-not (Test-Path $exe)) {
    & (Join-Path $PSScriptRoot "build-legacy.ps1")
}

Start-Process -FilePath $exe -WorkingDirectory (Join-Path $repoRoot "legacy\Run")
