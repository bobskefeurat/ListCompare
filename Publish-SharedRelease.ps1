[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$ReleaseRoot = "",
    [string]$ZipPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$releaseDirEnvVar = "LISTCOMPARE_RELEASE_DIR"
$sharedSyncConfigName = "shared_sync_config.json"
$defaultArchiveName = "ListCompare-windows.zip"

function Resolve-ExistingDirectory {
    param(
        [string]$PathText,
        [string]$Label
    )

    if ($PathText -eq "") {
        return ""
    }
    if (-not (Test-Path $PathText -PathType Container)) {
        throw "$Label not found: $PathText"
    }
    return (Resolve-Path $PathText).Path
}

function Resolve-ExistingFile {
    param(
        [string]$PathText,
        [string]$Label
    )

    if (-not (Test-Path $PathText -PathType Leaf)) {
        throw "$Label not found: $PathText"
    }
    return (Resolve-Path $PathText).Path
}

function Resolve-SharedReleaseRoot {
    param([string]$RequestedReleaseRoot)

    $resolvedRequested = Resolve-ExistingDirectory -PathText $RequestedReleaseRoot -Label "Release directory"
    if ($resolvedRequested -ne "") {
        return $resolvedRequested
    }

    $envReleaseRoot = Resolve-ExistingDirectory -PathText ([string][Environment]::GetEnvironmentVariable($releaseDirEnvVar)) -Label "Release directory from environment"
    if ($envReleaseRoot -ne "") {
        return $envReleaseRoot
    }

    $baseLocalAppData = [string]$env:LOCALAPPDATA
    if ($baseLocalAppData -ne "") {
        $configPath = Join-Path $baseLocalAppData "ListCompare\$sharedSyncConfigName"
        if (Test-Path $configPath -PathType Leaf) {
            $rawConfig = Get-Content $configPath -Raw | ConvertFrom-Json
            $sharedFolder = [string]$rawConfig.shared_folder
            if ($sharedFolder -ne "") {
                $candidate = Join-Path $sharedFolder "releases"
                if (Test-Path $candidate -PathType Container) {
                    return (Resolve-Path $candidate).Path
                }
            }
        }
    }

    throw "Could not resolve a shared release folder. Pass -ReleaseRoot or set $releaseDirEnvVar."
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$normalizedVersion = $Version.Trim()
if ($normalizedVersion -eq "") {
    throw "Version can not be blank."
}

$resolvedReleaseRoot = Resolve-SharedReleaseRoot -RequestedReleaseRoot $ReleaseRoot

$resolvedZipPath = $ZipPath.Trim()
if ($resolvedZipPath -eq "") {
    $resolvedZipPath = Join-Path $projectRoot "dist\$defaultArchiveName"
}
$resolvedZipPath = Resolve-ExistingFile -PathText $resolvedZipPath -Label "Release archive"

$targetArchiveName = "ListCompare-windows-$normalizedVersion.zip"
$targetArchivePath = Join-Path $resolvedReleaseRoot $targetArchiveName
$latestManifestPath = Join-Path $resolvedReleaseRoot "latest.json"

Copy-Item $resolvedZipPath $targetArchivePath -Force

$manifest = [ordered]@{
    version = $normalizedVersion
    zip = $targetArchiveName
    published_at = (Get-Date).ToString("o")
}
$manifest | ConvertTo-Json | Set-Content -Path $latestManifestPath -Encoding utf8

Write-Host "Published archive:" $targetArchivePath
Write-Host "Updated manifest:" $latestManifestPath
