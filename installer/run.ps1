[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ApplicationArguments)

$ErrorActionPreference = 'Stop'
$defaultRoot = Join-Path $env:LOCALAPPDATA 'Programs\MT-Karaoke-Studio'
$installRoot = if ($env:MT_KARAOKE_INSTALL_ROOT) {
    [System.IO.Path]::GetFullPath($env:MT_KARAOKE_INSTALL_ROOT)
} else {
    [System.IO.Path]::GetFullPath($defaultRoot)
}
$executable = Join-Path $installRoot 'MT-Karaoke-Studio.exe'

if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $developmentExecutable = Join-Path $projectRoot '.venv\Scripts\mt-karaoke-ui.exe'
    if (Test-Path -LiteralPath $developmentExecutable -PathType Leaf) {
        $executable = $developmentExecutable
        $installRoot = $projectRoot
    } else {
        Write-Host 'MT Karaoke Studio is not installed. Run install.bat first.' -ForegroundColor Red
        exit 1
    }
}

$startParameters = @{
    FilePath = $executable
    WorkingDirectory = $installRoot
}
if ($ApplicationArguments.Count -gt 0) {
    $startParameters.ArgumentList = $ApplicationArguments
}
Start-Process @startParameters
