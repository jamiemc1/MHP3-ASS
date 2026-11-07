<#
.SYNOPSIS
    Build the original C++/CLI application in legacy/ without modifying it.

.DESCRIPTION
    The 2017-era project targets the v141 toolset and the Windows 8.1 SDK.
    MSBuild property overrides retarget it to the toolchain VS 2022 ships,
    so no file under legacy/ is touched.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\windows\build-legacy.ps1
#>
param(
    [ValidateSet("Release", "Debug")]
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$solution = Join-Path $repoRoot "legacy\Athena's ASS MHP3rd.sln"

$vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
$msbuild = & $vswhere -latest -products * `
    -requires Microsoft.VisualStudio.Component.VC.CLI.Support `
    -find "MSBuild\**\Bin\MSBuild.exe" | Select-Object -First 1
if (-not $msbuild) {
    throw "No Visual Studio install with C++/CLI support found. See docs/windows-setup.md."
}

& $msbuild $solution `
    /p:Configuration=$Configuration `
    /p:Platform=Win32 `
    /p:PlatformToolset=v143 `
    /p:WindowsTargetPlatformVersion=10.0 `
    /p:TargetFrameworkVersion=v4.8 `
    /m /nologo /verbosity:minimal
if ($LASTEXITCODE -ne 0) {
    throw "MSBuild failed with exit code $LASTEXITCODE"
}

$exe = Join-Path $repoRoot "legacy\$Configuration\Athena's ASS MHP3rd.exe"
Write-Output "Built: $exe"
Write-Output "Run it from legacy\Run so it finds its Data folder."
