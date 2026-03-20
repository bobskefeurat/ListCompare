[CmdletBinding()]
param(
    [string]$ReleaseRoot = "",
    [string]$RuntimeRoot = "",
    [switch]$SkipLaunch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$appExeName = "ListCompare.exe"
$installedStateName = "installed.json"
$latestManifestName = "latest.json"
$releaseDirEnvVar = "LISTCOMPARE_RELEASE_DIR"
$runtimeDirEnvVar = "LISTCOMPARE_RUNTIME_DIR"
$sharedSyncConfigName = "shared_sync_config.json"
$sharedFolderName = "ListCompareShared"
$script:ReleaseRootResolutionWarning = ""

function Test-PathSafe {
    param(
        [string]$Path,
        [System.Management.Automation.SwitchParameter]$Container,
        [System.Management.Automation.SwitchParameter]$Leaf
    )

    $pathType = $null
    if ($Container) {
        $pathType = "Container"
    }
    elseif ($Leaf) {
        $pathType = "Leaf"
    }

    try {
        if ($null -eq $pathType) {
            return (Test-Path $Path)
        }
        return (Test-Path $Path -PathType $pathType)
    }
    catch {
        return $false
    }
}

function Show-LauncherError {
    param([string]$Message)

    try {
        Add-Type -AssemblyName PresentationFramework
        [void][System.Windows.MessageBox]::Show($Message, "ListCompare")
    }
    catch {
        Write-Error $Message
    }
}

function Resolve-RequestedDirectory {
    param(
        [string]$PathText,
        [string]$Label
    )

    if ($PathText -eq "") {
        return ""
    }
    if (-not (Test-PathSafe $PathText -Container)) {
        throw "$Label not found: $PathText"
    }
    return (Resolve-Path $PathText).Path
}

function Resolve-DirectoryPathAllowMissing {
    param([string]$PathText)

    if ($PathText -eq "") {
        return ""
    }
    return [System.IO.Path]::GetFullPath($PathText)
}

function Get-ReleaseRootCandidates {
    $candidates = New-Object System.Collections.Generic.List[string]
    $seen = @{}

    function Add-Candidate {
        param([string]$CandidatePath)

        if ($CandidatePath -eq "") {
            return
        }
        if (-not (Test-PathSafe $CandidatePath -Container)) {
            return
        }
        try {
            $resolved = (Resolve-Path $CandidatePath).Path
        }
        catch {
            return
        }
        $key = $resolved.ToLowerInvariant()
        if ($seen.ContainsKey($key)) {
            return
        }
        $seen[$key] = $true
        [void]$candidates.Add($resolved)
    }

    $fileSystemRoots = Get-PSDrive -PSProvider FileSystem |
        Where-Object { $_.Root } |
        Select-Object -ExpandProperty Root
    foreach ($driveRoot in $fileSystemRoots) {
        Add-Candidate (Join-Path $driveRoot "Min enhet\$sharedFolderName\releases")
        Add-Candidate (Join-Path $driveRoot "My Drive\$sharedFolderName\releases")
        Add-Candidate (Join-Path $driveRoot "$sharedFolderName\releases")
    }

    Add-Candidate (Join-Path $HOME "Google Drive\Min enhet\$sharedFolderName\releases")
    Add-Candidate (Join-Path $HOME "Google Drive\My Drive\$sharedFolderName\releases")
    Add-Candidate (Join-Path $HOME "Google Drive\$sharedFolderName\releases")

    return @($candidates.ToArray())
}

function Get-ConfiguredSharedReleaseRoot {
    $baseLocalAppData = [string]$env:LOCALAPPDATA
    if ($baseLocalAppData -eq "") {
        return ""
    }

    $configPath = Join-Path $baseLocalAppData "ListCompare\$sharedSyncConfigName"
    if (-not (Test-PathSafe $configPath -Leaf)) {
        return ""
    }

    try {
        $rawConfig = Get-Content $configPath -Raw | ConvertFrom-Json
    }
    catch {
        $script:ReleaseRootResolutionWarning = "Could not read shared release config: $($_.Exception.Message)"
        return ""
    }
    $sharedFolder = [string]$rawConfig.shared_folder
    if ($sharedFolder -eq "") {
        return ""
    }

    $candidate = Join-Path $sharedFolder "releases"
    if (-not (Test-PathSafe $candidate -Container)) {
        return ""
    }
    return (Resolve-Path $candidate).Path
}

function Resolve-ReleaseRootPath {
    param(
        [string]$RequestedReleaseRoot,
        [switch]$AllowInstalledFallback
    )

    $resolvedRequested = Resolve-RequestedDirectory -PathText $RequestedReleaseRoot -Label "Release directory"
    if ($resolvedRequested -ne "") {
        return $resolvedRequested
    }

    $envReleaseRoot = Resolve-RequestedDirectory -PathText ([string][Environment]::GetEnvironmentVariable($releaseDirEnvVar)) -Label "Release directory from environment"
    if ($envReleaseRoot -ne "") {
        return $envReleaseRoot
    }

    $configuredReleaseRoot = Get-ConfiguredSharedReleaseRoot
    if ($configuredReleaseRoot -ne "" -and (Test-PathSafe (Join-Path $configuredReleaseRoot $latestManifestName) -Leaf)) {
        return $configuredReleaseRoot
    }

    $candidateRoots = @(Get-ReleaseRootCandidates | Where-Object {
        Test-PathSafe (Join-Path $_ $latestManifestName) -Leaf
    })
    if ($candidateRoots.Count -eq 1) {
        return $candidateRoots[0]
    }
    if ($candidateRoots.Count -gt 1) {
        if ($AllowInstalledFallback) {
            $script:ReleaseRootResolutionWarning = "Multiple release folders were found. Set $releaseDirEnvVar or pass -ReleaseRoot."
            return ""
        }
        throw "Multiple release folders were found. Set $releaseDirEnvVar or pass -ReleaseRoot."
    }
    return ""
}

function Resolve-RuntimeRootPath {
    param([string]$RequestedRuntimeRoot)

    $resolvedRequested = Resolve-DirectoryPathAllowMissing -PathText $RequestedRuntimeRoot
    if ($resolvedRequested -ne "") {
        return $resolvedRequested
    }

    $envRuntimeRoot = Resolve-DirectoryPathAllowMissing -PathText ([string][Environment]::GetEnvironmentVariable($runtimeDirEnvVar))
    if ($envRuntimeRoot -ne "") {
        return $envRuntimeRoot
    }

    $baseLocalAppData = [string]$env:LOCALAPPDATA
    if ($baseLocalAppData -eq "") {
        throw "LOCALAPPDATA is not available."
    }
    return (Join-Path $baseLocalAppData "ListCompareRuntime")
}

function Load-InstalledState {
    param([string]$InstalledStatePath)

    if (-not (Test-PathSafe $InstalledStatePath -Leaf)) {
        return @{
            version = ""
            zip = ""
        }
    }

    $rawState = Get-Content $InstalledStatePath -Raw | ConvertFrom-Json
    return @{
        version = [string]$rawState.version
        zip = [string]$rawState.zip
    }
}

function Save-InstalledState {
    param(
        [string]$InstalledStatePath,
        [string]$Version,
        [string]$ZipName
    )

    $payload = [ordered]@{
        version = $Version
        zip = $ZipName
        updated_at = (Get-Date).ToString("o")
    }
    $payload | ConvertTo-Json | Set-Content -Path $InstalledStatePath -Encoding utf8
}

function Load-LatestRelease {
    param([string]$ResolvedReleaseRoot)

    if ($ResolvedReleaseRoot -eq "") {
        return $null
    }

    $manifestPath = Join-Path $ResolvedReleaseRoot $latestManifestName
    if (-not (Test-PathSafe $manifestPath -Leaf)) {
        return $null
    }

    $rawManifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    $version = [string]$rawManifest.version
    $zipName = [string]$rawManifest.zip
    if ($version -eq "" -or $zipName -eq "") {
        throw "$latestManifestName must contain version and zip."
    }
    return @{
        version = $version
        zip = $zipName
    }
}

function Install-Release {
    param(
        [string]$ResolvedReleaseRoot,
        [string]$ResolvedRuntimeRoot,
        [hashtable]$LatestRelease
    )

    $zipPath = Join-Path $ResolvedReleaseRoot ([string]$LatestRelease.zip)
    if (-not (Test-PathSafe $zipPath -Leaf)) {
        throw "Release archive not found: $zipPath"
    }

    $stagingRoot = Join-Path $ResolvedRuntimeRoot "staging"
    $currentRoot = Join-Path $ResolvedRuntimeRoot "current"
    $backupRoot = Join-Path $ResolvedRuntimeRoot "previous"
    $installedStatePath = Join-Path $ResolvedRuntimeRoot $installedStateName

    New-Item -ItemType Directory -Path $ResolvedRuntimeRoot -Force | Out-Null
    if (Test-PathSafe $stagingRoot) {
        Remove-Item $stagingRoot -Recurse -Force
    }
    if (Test-PathSafe $backupRoot) {
        Remove-Item $backupRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null

    Expand-Archive -Path $zipPath -DestinationPath $stagingRoot -Force

    $stagedExe = Get-ChildItem -Path $stagingRoot -Filter $appExeName -Recurse -File |
        Select-Object -First 1
    if ($null -eq $stagedExe) {
        throw "Could not find $appExeName after extracting $zipPath"
    }

    $stagedAppRoot = $stagedExe.Directory.FullName
    try {
        if (Test-PathSafe $currentRoot) {
            Move-Item -Path $currentRoot -Destination $backupRoot
        }
        Move-Item -Path $stagedAppRoot -Destination $currentRoot
        Save-InstalledState -InstalledStatePath $installedStatePath -Version ([string]$LatestRelease.version) -ZipName ([string]$LatestRelease.zip)
    }
    catch {
        if ((Test-PathSafe $backupRoot) -and -not (Test-PathSafe $currentRoot)) {
            Move-Item -Path $backupRoot -Destination $currentRoot
        }
        throw
    }
    finally {
        if (Test-PathSafe $stagingRoot) {
            Remove-Item $stagingRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
        if (Test-PathSafe $backupRoot) {
            Remove-Item $backupRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-ListCompareUpdater {
    $resolvedRuntimeRoot = Resolve-RuntimeRootPath -RequestedRuntimeRoot $RuntimeRoot
    New-Item -ItemType Directory -Path $resolvedRuntimeRoot -Force | Out-Null

    $installedStatePath = Join-Path $resolvedRuntimeRoot $installedStateName
    $currentRoot = Join-Path $resolvedRuntimeRoot "current"
    $currentExePath = Join-Path $currentRoot $appExeName
    $hasRunnableLocalVersion = Test-PathSafe $currentExePath -Leaf

    $script:ReleaseRootResolutionWarning = ""
    $resolvedReleaseRoot = Resolve-ReleaseRootPath `
        -RequestedReleaseRoot $ReleaseRoot `
        -AllowInstalledFallback:$hasRunnableLocalVersion
    if ($resolvedReleaseRoot -eq "" -and $script:ReleaseRootResolutionWarning -ne "") {
        if (-not $hasRunnableLocalVersion) {
            throw $script:ReleaseRootResolutionWarning
        }
        Write-Warning $script:ReleaseRootResolutionWarning
    }

    $latestRelease = Load-LatestRelease -ResolvedReleaseRoot $resolvedReleaseRoot
    $installedState = Load-InstalledState -InstalledStatePath $installedStatePath

    $needsUpdate = $false
    if ($null -ne $latestRelease) {
        $needsUpdate = (
            (-not (Test-PathSafe $currentExePath -Leaf)) -or
            ([string]$installedState.version -ne [string]$latestRelease.version) -or
            ([string]$installedState.zip -ne [string]$latestRelease.zip)
        )
    }

    if ($needsUpdate) {
        Install-Release `
            -ResolvedReleaseRoot $resolvedReleaseRoot `
            -ResolvedRuntimeRoot $resolvedRuntimeRoot `
            -LatestRelease $latestRelease
    }

    if (-not (Test-PathSafe $currentExePath -Leaf)) {
        if ($resolvedReleaseRoot -eq "") {
            throw "No installed version was found and no release folder could be detected."
        }
        throw "No runnable local version is available. Check that $latestManifestName and the release zip exist."
    }

    if (-not $SkipLaunch) {
        Start-Process -FilePath $currentExePath | Out-Null
    }
}

if ([string][Environment]::GetEnvironmentVariable("LISTCOMPARE_UPDATER_SKIP_MAIN") -eq "1") {
    return
}

try {
    Invoke-ListCompareUpdater
}
catch {
    Show-LauncherError $_.Exception.Message
    exit 1
}
