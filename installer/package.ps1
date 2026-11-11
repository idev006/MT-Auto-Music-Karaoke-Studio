[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$AppDist)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$releaseRoot = Join-Path $projectRoot 'release'
$packageName = 'MT-Karaoke-Studio-Installer'
$packageRoot = Join-Path $releaseRoot $packageName
$zipPath = Join-Path $releaseRoot "$packageName.zip"

if (-not (Test-Path -LiteralPath (Join-Path $AppDist 'MT-Karaoke-Studio.exe'))) {
    throw "Application distribution is incomplete: $AppDist"
}
New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
if (Test-Path -LiteralPath $packageRoot) {
    Remove-Item -LiteralPath $packageRoot -Recurse -Force
}
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null
Copy-Item -LiteralPath $AppDist -Destination (Join-Path $packageRoot 'payload') -Recurse
$baseModel = Join-Path $projectRoot 'models\faster-whisper\models--Systran--faster-whisper-base'
if (-not (Test-Path -LiteralPath $baseModel -PathType Container)) {
    throw "Required offline base model is missing: $baseModel"
}
$validSnapshot = Get-ChildItem -LiteralPath (Join-Path $baseModel 'snapshots') -Directory -ErrorAction SilentlyContinue |
    Where-Object {
        (Test-Path -LiteralPath (Join-Path $_.FullName 'config.json') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $_.FullName 'model.bin') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $_.FullName 'tokenizer.json') -PathType Leaf)
    } |
    Select-Object -First 1
if (-not $validSnapshot) {
    throw "Required offline base model is incomplete: $baseModel"
}
$payloadModels = Join-Path $packageRoot 'payload\models\faster-whisper'
New-Item -ItemType Directory -Path $payloadModels -Force | Out-Null
Copy-Item -LiteralPath $baseModel -Destination $payloadModels -Recurse
New-Item -ItemType Directory -Path (Join-Path $packageRoot 'installer') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'install.ps1') -Destination (Join-Path $packageRoot 'installer\install.ps1')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'run.ps1') -Destination (Join-Path $packageRoot 'installer\run.ps1')
Copy-Item -LiteralPath (Join-Path $projectRoot 'install.bat') -Destination $packageRoot
Copy-Item -LiteralPath (Join-Path $projectRoot 'run.bat') -Destination $packageRoot
Compress-Archive -Path (Join-Path $packageRoot '*') -DestinationPath $zipPath -CompressionLevel Optimal
Remove-Item -LiteralPath $packageRoot -Recurse -Force
$distRoot = Split-Path -Parent ([System.IO.Path]::GetFullPath($AppDist))
if ((Split-Path -Leaf $distRoot) -eq 'dist') {
    Remove-Item -LiteralPath $distRoot -Recurse -Force
}
$buildRoot = Join-Path $projectRoot 'build'
if (Test-Path -LiteralPath $buildRoot) {
    Remove-Item -LiteralPath $buildRoot -Recurse -Force
}
Write-Host "Installer ZIP created at: $zipPath"
