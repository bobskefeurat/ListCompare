function Get-PythonVersionFromDirectoryName {
    param([string]$DirectoryName)

    $match = [regex]::Match(
        [string]$DirectoryName,
        '^pythoncore-(?<version>\d+(?:\.\d+)*)(?:-.+)?$',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )
    if (-not $match.Success) {
        return $null
    }

    try {
        return [version]$match.Groups['version'].Value
    }
    catch {
        return $null
    }
}

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
            ForEach-Object {
                [pscustomobject]@{
                    DirectoryName = $_.Name
                    DirectoryPath = $_.FullName
                    PythonExe = Join-Path $_.FullName "python.exe"
                    Version = Get-PythonVersionFromDirectoryName -DirectoryName $_.Name
                }
            } |
            Where-Object { Test-Path $_.PythonExe } |
            Sort-Object `
                @{ Expression = { $_.Version -ne $null }; Descending = $true }, `
                @{ Expression = { if ($_.Version -ne $null) { $_.Version } else { [version]'0.0' } }; Descending = $true }, `
                @{ Expression = { $_.DirectoryName }; Descending = $true } |
            Select-Object -First 1

        if ($installedPython) {
            return $installedPython.PythonExe
        }
    }

    throw "Could not find a real python.exe under %LOCALAPPDATA%\\Python. Pass -PythonExe explicitly."
}
