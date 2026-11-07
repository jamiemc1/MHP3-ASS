<#
.SYNOPSIS
    Regenerate the golden fixtures from the legacy code via the harness.

.DESCRIPTION
    Writes committed fixtures to tests\golden\ and, when a save file is
    present, save-derived fixtures to the gitignored tests\savefile\golden\.
    Build the harness first (scripts\windows\build-harness.ps1).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\windows\generate-goldens.ps1
#>
param(
    # The language the GUI defaults to on first run, and the one goldens use
    # wherever names matter (charm names, imported charm lists).
    [string]$Language = "English (TeamHGG)"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$harness = Join-Path $repoRoot "harness\Release\Harness.exe"
if (-not (Test-Path $harness)) {
    throw "Harness not built. Run scripts\windows\build-harness.ps1 first."
}

function Invoke-Harness {
    & $harness @args
    if ($LASTEXITCODE -ne 0) {
        throw "Harness failed (exit $LASTEXITCODE): $args"
    }
}

$dataDir = Join-Path $repoRoot "tests\golden\data"
$namesDir = Join-Path $dataDir "names"
New-Item -ItemType Directory -Force -Path $namesDir | Out-Null

Invoke-Harness dump-data --out (Join-Path $dataDir "game-data.json.gz")
# Charm names come from ability names, so use the language the GUI runs in.
Invoke-Harness dump-charms --lang $Language --out (Join-Path $dataDir "charm-database.json.gz")

$languagesDir = Join-Path $repoRoot "legacy\Run\Data\Languages"
# PowerShell variable names are case-insensitive: don't reuse $Language here.
foreach ($languageDir in Get-ChildItem -Directory $languagesDir) {
    Invoke-Harness dump-data --names-only --lang $languageDir.Name `
        --out (Join-Path $namesDir "$($languageDir.Name).json.gz")
}

function Invoke-Searches([string]$corpusDir, [string]$outDir) {
    if (-not (Test-Path $corpusDir)) {
        return
    }
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    foreach ($query in Get-ChildItem -File -Filter "*.json" $corpusDir) {
        Invoke-Harness search $query.FullName --out (Join-Path $outDir $query.BaseName)
    }
}

Invoke-Searches (Join-Path $repoRoot "tests\corpus") (Join-Path $repoRoot "tests\golden\search")
# Queries built from a personal charm list stay out of git with their results.
Invoke-Searches (Join-Path $repoRoot "tests\savefile\corpus") (Join-Path $repoRoot "tests\savefile\golden\search")

$save = Join-Path $repoRoot "tests\savefile\MHP3RD.BIN"
if (Test-Path $save) {
    $saveGoldenDir = Join-Path $repoRoot "tests\savefile\golden"
    New-Item -ItemType Directory -Force -Path $saveGoldenDir | Out-Null
    Invoke-Harness decrypt-save $save --lang $Language --out (Join-Path $saveGoldenDir "save.json")
}
else {
    Write-Output "No tests\savefile\MHP3RD.BIN: skipped save fixtures."
}
