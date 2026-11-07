<#
.SYNOPSIS
    Archive the original GUI's results after each search.

.DESCRIPTION
    After a search finishes, the GUI saves every solution, the options and the
    chosen skills to legacy\Run\settings.cfg, and the next search overwrites
    it. Run this script beside the GUI and press Enter after each search: it
    copies settings.cfg and the current Data\mycharms.txt into
    tests\savefile\gui-captures\<number>\ (gitignored: results can depend on
    personal charms) and prints the solution count to check against the
    GUI's "Solutions found".

    Don't touch the Options menu between a search finishing and pressing
    Enter: each toggle re-saves settings.cfg with the new options beside the
    old search's solutions (OptionsChanged, Form1.h:1218-1223), and the
    capture would no longer describe the search that produced them.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\windows\capture-gui-searches.ps1
#>
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$runDir = Join-Path $repoRoot "legacy\Run"
$settings = Join-Path $runDir "settings.cfg"
$mycharms = Join-Path $runDir "Data\mycharms.txt"
$capturesDir = Join-Path $repoRoot "tests\savefile\gui-captures"
New-Item -ItemType Directory -Force -Path $capturesDir | Out-Null

# settings.cfg version 2: 14 option lines and 24 skill lines precede the solutions
# (src/mhp3ass/settings_cfg.py). The count printed here is only a quick check.
$headerLines = 38

# Number after the highest existing capture, so gaps and non-numeric folders never lead to an overwrite.
$numbered = @(Get-ChildItem -Directory $capturesDir | Where-Object { $_.Name -match '^\d+$' } | ForEach-Object { [int]$_.Name })
$next = 1 + ($numbered | Measure-Object -Maximum).Maximum
Write-Output "Captures go to $capturesDir"
Write-Output "Press Enter after each search has finished (progress bar full). Type q then Enter to stop."
Write-Output "Don't change the Options menu before capturing: it re-saves settings.cfg with the new options."

while ($true) {
    $answer = Read-Host "Search $next done? [Enter = capture, q = quit]"
    if ($answer -eq "q") {
        break
    }
    if (-not (Test-Path $settings)) {
        Write-Output "No settings.cfg yet: run a search in the GUI first."
        continue
    }
    $target = Join-Path $capturesDir ("{0:D2}" -f $next)
    if (Test-Path $target) {
        throw "Capture $target already exists; refusing to overwrite it"
    }
    New-Item -ItemType Directory -Path $target | Out-Null
    Copy-Item $settings (Join-Path $target "settings.cfg")
    # Absent until the GUI first saves a charm list; only my-charms and Auto-Guard searches read it.
    if (Test-Path $mycharms) {
        Copy-Item $mycharms (Join-Path $target "mycharms.txt")
    }

    $lines = @(Get-Content (Join-Path $target "settings.cfg"))
    $solutions = [Math]::Max(0, $lines.Count - $headerLines)
    Write-Output ("Captured {0:D2}: {1} solutions" -f $next, $solutions)
    $next++
}
