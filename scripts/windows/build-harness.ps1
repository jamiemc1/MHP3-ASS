<#
.SYNOPSIS
    Build the C++/CLI harness in harness/ (Release, Win32).

.DESCRIPTION
    The harness compiles the original sources from legacy/ unchanged and
    records their behaviour as JSON fixtures for the Python port.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\windows\build-harness.ps1
#>
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$project = Join-Path $repoRoot "harness\Harness.vcxproj"

$vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
$msbuild = & $vswhere -latest -products * `
    -requires Microsoft.VisualStudio.Component.VC.CLI.Support `
    -find "MSBuild\**\Bin\MSBuild.exe" | Select-Object -First 1
if (-not $msbuild) {
    throw "No Visual Studio install with C++/CLI support found. See docs/windows-setup.md."
}

& $msbuild $project /p:Configuration=Release /p:Platform=Win32 /m /nologo /verbosity:minimal
if ($LASTEXITCODE -ne 0) {
    throw "MSBuild failed with exit code $LASTEXITCODE"
}

Write-Output "Built: $(Join-Path $repoRoot 'harness\Release\Harness.exe')"
