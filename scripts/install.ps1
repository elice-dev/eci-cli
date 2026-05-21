<#
.SYNOPSIS
    Install script for the ECI (Elice Cloud Infrastructure) CLI on Windows.

.DESCRIPTION
    Usage:
      powershell -c "irm https://raw.githubusercontent.com/elice-dev/eci-cli/main/scripts/install.ps1 | iex"

    Environment variables:
      VERSION       Specific version to install (e.g., "0.1.0"). Defaults to latest.
      INSTALL_DIR   Directory to install the bundle into. Defaults to
                    $env:LOCALAPPDATA\eci-cli.
#>

$ErrorActionPreference = 'Stop'

$BinaryName  = 'eci'
$BinaryExe   = 'eci.exe'
$GithubRepo  = 'elice-dev/eci-cli'
$ReleaseBase = "https://github.com/$GithubRepo/releases/download"
$GithubApi   = "https://api.github.com/repos/$GithubRepo"


function Get-Arch {
    $machine = if ($env:PROCESSOR_ARCHITEW6432) {
        $env:PROCESSOR_ARCHITEW6432
    } else {
        $env:PROCESSOR_ARCHITECTURE
    }
    switch ($machine) {
        'AMD64' { return 'x86_64' }
        'ARM64' { return 'arm64' }
        default { throw "unsupported architecture: $machine" }
    }
}

function Get-InstallRoot {
    if ($env:INSTALL_DIR) { return $env:INSTALL_DIR }
    return (Join-Path $env:LOCALAPPDATA 'eci-cli')
}

function Get-Version {
    if ($env:VERSION) { return $env:VERSION }
    $headers = @{ 'User-Agent' = 'eci-cli-installer' }
    try {
        $resp = Invoke-RestMethod -Uri "$GithubApi/releases/latest" -Headers $headers
    } catch {
        throw "could not determine latest version. Set VERSION explicitly."
    }
    return ($resp.tag_name -replace '^v','')
}

function Test-Checksum {
    param([string]$File, [string]$Expected)
    $actual = (Get-FileHash -Path $File -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $Expected.ToLower()) {
        throw "checksum mismatch.`n  expected: $Expected`n  actual:   $actual"
    }
}

function Get-ExistingVersion {
    param([string]$ExePath)
    if (-not (Test-Path $ExePath)) { return $null }
    try {
        $out = & $ExePath --version 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        return (($out -split '\s+') | Select-Object -Last 1)
    } catch {
        return $null
    }
}


function Install-EciCli {
    $os       = 'windows'
    $arch     = Get-Arch
    $rootDir  = Get-InstallRoot
    $version  = Get-Version
    $exePath  = Join-Path $rootDir $BinaryExe

    $tmpdir = Join-Path ([System.IO.Path]::GetTempPath()) "eci-install-$([guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Path $tmpdir -Force | Out-Null

    try {
        $existing = Get-ExistingVersion -ExePath $exePath

        $action = if (-not $existing) {
            "install $version"
        } elseif ($existing -ne $version) {
            "upgrade $existing -> $version"
        } else {
            "reinstall $version"
        }

        Write-Host ""
        Write-Host "  ECI CLI installer"
        Write-Host "  Action:    $action"
        Write-Host "  Platform:  $os $arch"
        Write-Host "  Source:    GitHub Releases (v$version)"
        Write-Host "  Bundle:    $rootDir"
        Write-Host "  Launcher:  $exePath"
        Write-Host ""

        $asset     = "$BinaryName-$os-$arch-$version.zip"
        $assetUrl  = "$ReleaseBase/v$version/$asset"
        $sumsUrl   = "$ReleaseBase/v$version/checksums.txt"
        $assetPath = Join-Path $tmpdir $asset
        $sumsPath  = Join-Path $tmpdir 'checksums.txt'

        Write-Host "Downloading..."
        $oldProg = $ProgressPreference
        $ProgressPreference = 'SilentlyContinue'
        try {
            Invoke-WebRequest -Uri $assetUrl -OutFile $assetPath -UseBasicParsing
            Invoke-WebRequest -Uri $sumsUrl  -OutFile $sumsPath  -UseBasicParsing
        } finally {
            $ProgressPreference = $oldProg
        }

        Write-Host -NoNewline "Verifying...  "
        $line = Get-Content $sumsPath | Where-Object { $_ -match [regex]::Escape($asset) } | Select-Object -First 1
        if (-not $line) { throw "checksum not found for $asset in checksums.txt" }
        $expected = ($line -split '\s+')[0]
        Test-Checksum -File $assetPath -Expected $expected
        Write-Host "OK"

        Write-Host -NoNewline "Extracting... "
        Expand-Archive -Path $assetPath -DestinationPath $tmpdir -Force
        Write-Host "OK"

        $bundleSrc = Join-Path $tmpdir "$BinaryName-$os-$arch-$version"
        if (-not (Test-Path $bundleSrc)) {
            $bundleSrc = (Get-ChildItem $tmpdir -Directory | Select-Object -First 1).FullName
            if (-not $bundleSrc) { throw "extracted bundle directory not found" }
        }

        if (Test-Path $rootDir) {
            Remove-Item -Recurse -Force $rootDir
        }
        New-Item -ItemType Directory -Path (Split-Path $rootDir -Parent) -Force | Out-Null
        Move-Item -Path $bundleSrc -Destination $rootDir

        Write-Host ""
        Write-Host "Installed $BinaryName to $exePath"

        $userPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
        # @() forces array — a single-element pipe output otherwise unwraps to a string.
        $paths = @(if ($userPath) { $userPath -split ';' | Where-Object { $_ } } else { @() })

        if ($paths -notcontains $rootDir) {
            $newPath = ($paths + $rootDir) -join ';'
            [Environment]::SetEnvironmentVariable('PATH', $newPath, 'User')
            Write-Host ""
            Write-Host "Added $rootDir to PATH (User scope)"
        } else {
            Write-Host ""
            Write-Host "PATH already includes $rootDir."
        }

        # Registry update doesn't refresh this session's $env:PATH — mirror it.
        $sessionPaths = @(($env:PATH -split ';') | Where-Object { $_ })
        if ($sessionPaths -notcontains $rootDir) {
            $env:PATH = "$env:PATH;$rootDir"
        }

        Write-Host ""
        Write-Host "Run '$BinaryName --help' to get started."
    }
    finally {
        if (Test-Path $tmpdir) {
            Remove-Item -Recurse -Force $tmpdir -ErrorAction SilentlyContinue
        }
    }
}


Install-EciCli
