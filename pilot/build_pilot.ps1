param(
    [string]$OutputDirectory = "dist"
)

$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent $PSScriptRoot
Push-Location $repository
try {
    # `trusted_issuers.json` no es codigo, asi que PyInstaller no lo lleva solo.
    # Sin el, un BC congelado no puede verificar ninguna licencia y toda
    # instalacion enrolada queda en DENY. Ver ADR-0004.
    python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name BC-Caja `
        --distpath $OutputDirectory `
        --additional-hooks-dir "tools/pyinstaller_hooks" `
        --collect-all customtkinter `
        --add-data "modulos/caja_diaria/infrastructure/migrations;modulos/caja_diaria/infrastructure/migrations" `
        --add-data "modulos/seguridad/trusted_issuers.json;modulos/seguridad" `
        bc_caja.py
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller finalizó con código $LASTEXITCODE"
    }

    # Verificacion dura del paquete: si falta algo de esto, el ejecutable
    # arranca y falla recien en la Optica. Preferimos que falle el build.
    $internal = Join-Path $OutputDirectory "BC-Caja/_internal"
    $obligatorios = @(
        "modulos/seguridad/trusted_issuers.json",
        "modulos/caja_diaria/infrastructure/migrations/033_security_v1.sql",
        "cryptography/hazmat/bindings/_rust.pyd"
    )
    foreach ($relativo in $obligatorios) {
        $ruta = Join-Path $internal $relativo
        if (-not (Test-Path -LiteralPath $ruta)) {
            throw "el paquete no incluye $relativo"
        }
    }
    Write-Output "BC_CAJA_PACKAGE_CONTENTS_OK"

    # Segundo ejecutable, de consola: la herramienta de seguridad. Va en el
    # mismo paquete porque la Optica no tiene Python instalado, y sin esto el
    # instructivo pediria algo que en esa PC no se puede hacer. Es de consola y
    # no --windowed porque su salida —el installation_id, la frase de
    # recuperacion, el veredicto— hay que poder leerla.
    # El emisor NO se empaqueta: vive en la maquina de administracion.
    $package = Join-Path $OutputDirectory "BC-Caja"
    python -m PyInstaller `
        --noconfirm `
        --console `
        --name BC-Seguridad `
        --distpath $OutputDirectory `
        --add-data "modulos/caja_diaria/infrastructure/migrations;modulos/caja_diaria/infrastructure/migrations" `
        --add-data "modulos/seguridad/trusted_issuers.json;modulos/seguridad" `
        tools/bc_security.py
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller finalizó con código $LASTEXITCODE al construir BC-Seguridad"
    }
    $seguridad = Join-Path $OutputDirectory "BC-Seguridad"
    if (-not (Test-Path -LiteralPath (Join-Path $seguridad "_internal/modulos/seguridad/trusted_issuers.json"))) {
        throw "BC-Seguridad no incluye el almacen de confianza"
    }
    Copy-Item -LiteralPath $seguridad -Destination (Join-Path $package "Seguridad") -Recurse -Force
    Remove-Item -LiteralPath $seguridad -Recurse -Force
    Write-Output "BC_SEGURIDAD_PACKAGE_OK"

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
    # PyInstaller deja abierto un instante `_internal/base_library.zip` al
    # terminar y la compresion falla por acceso denegado. Es transitorio: se
    # reintenta en vez de dar el build por perdido.
    $intentos = 0
    while ($true) {
        $intentos++
        try {
            Compress-Archive `
                -Path $package `
                -DestinationPath $zipPath `
                -CompressionLevel Optimal `
                -Force
            break
        }
        catch {
            if ($intentos -ge 5) { throw }
            Write-Output "Empaquetado bloqueado, reintento $intentos de 5..."
            Start-Sleep -Seconds 6
        }
    }
    Write-Output "BC_CAJA_BUILD_OK version=$version zip=$zipPath"
}
finally {
    Pop-Location
}
