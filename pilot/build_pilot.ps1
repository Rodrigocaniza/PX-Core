param(
    [string]$OutputDirectory = "dist"
)

$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent $PSScriptRoot
Push-Location $repository
try {
    python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name BC-Caja `
        --distpath $OutputDirectory `
        --additional-hooks-dir "tools/pyinstaller_hooks" `
        --collect-all customtkinter `
        --add-data "modulos/caja_diaria/infrastructure/migrations;modulos/caja_diaria/infrastructure/migrations" `
        bc_caja.py
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller finalizó con código $LASTEXITCODE"
    }

    $package = Join-Path $OutputDirectory "BC-Caja"
    Copy-Item -LiteralPath `
        "pilot/package_docs/INSTALACION.txt", `
        "pilot/package_docs/GUIA_RAPIDA.txt", `
        "pilot/package_docs/VERSION.txt" `
        -Destination $package -Force

    # La version sale de VERSION.txt, no del nombre del script: cablearla
    # producia paquetes mal etiquetados al cambiar de release.
    $versionLine = (Get-Content "pilot/package_docs/VERSION.txt" -Encoding utf8)[0]
    if ($versionLine -notmatch 'BC Caja\s+(?<version>\S+)') {
        throw "No se pudo determinar la version desde pilot/package_docs/VERSION.txt"
    }
    $version = $Matches['version']

    $releaseDirectory = Join-Path $repository "releases"
    New-Item -ItemType Directory -Force -Path $releaseDirectory | Out-Null
    $zipPath = Join-Path $releaseDirectory "BC-CAJA-$version-win64.zip"
    Compress-Archive `
        -Path $package `
        -DestinationPath $zipPath `
        -CompressionLevel Optimal `
        -Force
    Write-Output "BC_CAJA_BUILD_OK version=$version zip=$zipPath"
}
finally {
    Pop-Location
}
