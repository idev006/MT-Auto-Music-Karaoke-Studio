[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$logRoot = Join-Path $env:LOCALAPPDATA 'MT\MediaStudio\logs'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$logPath = Join-Path $logRoot 'install.log'
function Write-InstallLog([string]$Message) {
    Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format o) $Message" -Encoding UTF8
}
Write-InstallLog 'Installation started.'

if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'MT Karaoke Studio requires 64-bit Windows.'
}
$packageRoot = Split-Path -Parent $PSScriptRoot
$payload = Join-Path $packageRoot 'payload'
$executable = Join-Path $payload 'MT-Karaoke-Studio.exe'

if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Installer payload is incomplete: $executable"
}
$baseModelRoot = Join-Path $payload 'models\faster-whisper\models--Systran--faster-whisper-base\snapshots'
$baseModelSnapshot = Get-ChildItem -LiteralPath $baseModelRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object {
        (Test-Path -LiteralPath (Join-Path $_.FullName 'config.json') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $_.FullName 'model.bin') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $_.FullName 'tokenizer.json') -PathType Leaf)
    } |
    Select-Object -First 1
if (-not $baseModelSnapshot) {
    throw 'Installer payload is incomplete: Faster Whisper base model files are missing.'
}

$defaultRoot = Join-Path $env:LOCALAPPDATA 'Programs\MT-Karaoke-Studio'
$installRoot = if ($env:MT_KARAOKE_INSTALL_ROOT) {
    [System.IO.Path]::GetFullPath($env:MT_KARAOKE_INSTALL_ROOT)
} else {
    [System.IO.Path]::GetFullPath($defaultRoot)
}
$parent = Split-Path -Parent $installRoot
$staging = "$installRoot.installing-$PID"
$backup = "$installRoot.previous-$PID"
$payloadBytes = (Get-ChildItem -LiteralPath $payload -Recurse -File | Measure-Object Length -Sum).Sum
$driveRoot = [System.IO.Path]::GetPathRoot($installRoot)
$availableBytes = [System.IO.DriveInfo]::new($driveRoot).AvailableFreeSpace
$requiredBytes = [int64]($payloadBytes * 1.25)
if ($availableBytes -lt $requiredBytes) {
    throw "Insufficient disk space. Required: $requiredBytes bytes; available: $availableBytes bytes."
}

New-Item -ItemType Directory -Path $parent -Force | Out-Null
if (Test-Path -LiteralPath $staging) {
    Remove-Item -LiteralPath $staging -Recurse -Force
}

try {
    Copy-Item -LiteralPath $payload -Destination $staging -Recurse
    $portableFlag = Join-Path $staging 'portable.flag'
    if (Test-Path -LiteralPath $portableFlag) {
        Remove-Item -LiteralPath $portableFlag -Force
    }
    if (-not (Test-Path -LiteralPath (Join-Path $staging 'MT-Karaoke-Studio.exe'))) {
        throw 'Staged executable validation failed.'
    }

    if (Test-Path -LiteralPath $installRoot) {
        Move-Item -LiteralPath $installRoot -Destination $backup
        $existingModels = Join-Path $backup 'models'
        if (Test-Path -LiteralPath $existingModels -PathType Container) {
            $stagedModels = Join-Path $staging 'models'
            New-Item -ItemType Directory -Path $stagedModels -Force | Out-Null
            $existingWhisper = Join-Path $existingModels 'faster-whisper'
            $stagedWhisper = Join-Path $stagedModels 'faster-whisper'
            New-Item -ItemType Directory -Path $stagedWhisper -Force | Out-Null
            if (Test-Path -LiteralPath $existingWhisper) {
                Get-ChildItem -LiteralPath $existingWhisper -Force | ForEach-Object {
                    $destination = Join-Path $stagedWhisper $_.Name
                    if (-not (Test-Path -LiteralPath $destination)) {
                        Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse
                    }
                }
            }
        }
    }
    Move-Item -LiteralPath $staging -Destination $installRoot
    if (-not $env:MT_KARAOKE_SKIP_SMOKE_TEST) {
        $smoke = Start-Process `
            -FilePath (Join-Path $installRoot 'MT-Karaoke-Studio.exe') `
            -ArgumentList '--smoke-test' `
            -WorkingDirectory $installRoot `
            -WindowStyle Hidden `
            -Wait `
            -PassThru
        if ($smoke.ExitCode -ne 0) {
            throw "Installed application smoke test failed with exit code $($smoke.ExitCode)."
        }
    }
    $manifest = @{
        schema_version = 1
        installed_at = (Get-Date).ToString('o')
        install_root = $installRoot
        payload_bytes = $payloadBytes
        model_root = (Join-Path $installRoot 'models\faster-whisper')
    } | ConvertTo-Json
    Set-Content -LiteralPath (Join-Path $installRoot 'install-manifest.json') -Value $manifest -Encoding UTF8
    if (Test-Path -LiteralPath $backup) {
        Remove-Item -LiteralPath $backup -Recurse -Force
    }
    Write-InstallLog "Installation completed at $installRoot."
} catch {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    if (Test-Path -LiteralPath $backup) {
        if (Test-Path -LiteralPath $installRoot) {
            $installedModels = Join-Path $installRoot 'models'
            if (Test-Path -LiteralPath $installedModels) {
                $backupModels = Join-Path $backup 'models'
                if (Test-Path -LiteralPath $backupModels) {
                    Remove-Item -LiteralPath $backupModels -Recurse -Force
                }
                Move-Item -LiteralPath $installedModels -Destination $backupModels
            }
            Remove-Item -LiteralPath $installRoot -Recurse -Force
        }
        Move-Item -LiteralPath $backup -Destination $installRoot
    }
    Write-InstallLog "Installation failed: $($_.Exception.Message)"
    throw
}

Write-Host "MT Karaoke Studio installed at: $installRoot"
