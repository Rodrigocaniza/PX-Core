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

    $releaseDirectory = Join-Path $repository "releases"
    New-Item -ItemType Directory -Force -Path $releaseDirectory | Out-Null
    Compress-Archive `
        -Path $package `
        -DestinationPath (Join-Path $releaseDirectory "BC-CAJA-1.0.0-rc.12-win64.zip") `
        -CompressionLevel Optimal `
        -Force
}
finally {
    Pop-Location
}
