[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [switch]$InstallBuildDeps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

function Resolve-PythonExe {
    param([string]$RequestedPythonExe)

    if ($RequestedPythonExe -ne "") {
        if (-not (Test-Path $RequestedPythonExe)) {
            throw "Python executable not found: $RequestedPythonExe"
        }
        return (Resolve-Path $RequestedPythonExe).Path
    }

    $pythonRoot = Join-Path $env:LOCALAPPDATA "Python"
    if (Test-Path $pythonRoot) {
        $installedPython = Get-ChildItem $pythonRoot -Directory -Filter "pythoncore-*" |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName "python.exe" } |
            Where-Object { Test-Path $_ } |
            Select-Object -First 1

        if ($installedPython) {
            return $installedPython
        }
    }

    throw "Could not find a real python.exe under %LOCALAPPDATA%\\Python. Pass -PythonExe explicitly."
}

$resolvedPythonExe = Resolve-PythonExe -RequestedPythonExe $PythonExe
Write-Host "Using Python:" $resolvedPythonExe

if ($InstallBuildDeps) {
    & $resolvedPythonExe -m pip install -r requirements.txt -r requirements-build.txt
}

& $resolvedPythonExe -m PyInstaller --noconfirm --clean listcompare.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

$releaseDir = Join-Path $projectRoot "dist\\ListCompare"
if (-not (Test-Path $releaseDir)) {
    throw "Expected release directory was not created: $releaseDir"
}

$releaseReadmePath = Join-Path $projectRoot "README-Windows.txt"
if (Test-Path $releaseReadmePath) {
    Copy-Item $releaseReadmePath -Destination (Join-Path $releaseDir "README-Windows.txt") -Force
}

$archivePath = Join-Path $projectRoot "dist\\ListCompare-windows.zip"
if (Test-Path $archivePath) {
    Remove-Item $archivePath -Force
}

Compress-Archive -Path $releaseDir -DestinationPath $archivePath -CompressionLevel Optimal

Write-Host "Release folder:" $releaseDir
Write-Host "Release archive:" $archivePath
