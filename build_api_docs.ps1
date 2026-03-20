[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [switch]$InstallBuildDeps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

. (Join-Path $projectRoot "build_common.ps1")

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
