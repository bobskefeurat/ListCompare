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

$outputDir = Join-Path $projectRoot "build\\api-docs"
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

& $resolvedPythonExe -m pdoc -o $outputDir listcompare
if ($LASTEXITCODE -ne 0) {
    throw "API documentation build failed with exit code $LASTEXITCODE"
}

$indexPath = Join-Path $outputDir "index.html"
Write-Host "API docs:" $indexPath
