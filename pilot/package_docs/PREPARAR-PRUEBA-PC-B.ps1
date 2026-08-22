param(
    [string]$Base = "$env:LOCALAPPDATA\BC\Caja\bc_caja.sqlite3",
    [string]$Salida = "$env:USERPROFILE\Desktop\BC-PC-B-REAL"
)

$ErrorActionPreference = "Stop"
$package = $PSScriptRoot
$securityExe = Join-Path $package "Seguridad\BC-Seguridad.exe"
$securityRoot = Join-Path $env:LOCALAPPDATA "BC\Security"
$required = @("installation.json", "installation.secret", "license.bclic")

if (Get-Process -Name "BC-Caja" -ErrorAction SilentlyContinue) {
    throw "ABORT: BC-Caja esta abierto. Cerrarlo antes de copiar la base."
}
if (-not (Test-Path -LiteralPath $securityExe -PathType Leaf)) {
    throw "ABORT: falta Seguridad\BC-Seguridad.exe"
}
if (-not (Test-Path -LiteralPath $Base -PathType Leaf)) {
    throw "ABORT: no existe la base $Base"
}
foreach ($name in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $securityRoot $name) -PathType Leaf)) {
        throw "ABORT: falta BC\Security\$name; PC-A no esta lista"
    }
}
$wal = "$Base-wal"
if ((Test-Path -LiteralPath $wal) -and (Get-Item -LiteralPath $wal).Length -gt 0) {
    throw "ABORT: existe WAL no vacio. Abrir y cerrar BC limpiamente antes de reintentar."
}
$journal = "$Base-journal"
if ((Test-Path -LiteralPath $journal) -and (Get-Item -LiteralPath $journal).Length -gt 0) {
    throw "ABORT: existe journal no vacio. Abrir y cerrar BC limpiamente antes de reintentar."
}

$allow = & $securityExe verificar --base $Base 2>&1
if ($LASTEXITCODE -ne 0 -or -not (($allow -join "`n").StartsWith("ALLOW / OK"))) {
    throw "ABORT: PC-A no dio ALLOW / OK. Resultado: $($allow -join ' ')"
}
$bcx1 = & $securityExe verificar-bcx1 --base $Base 2>&1
if ($LASTEXITCODE -ne 0 -or -not (($bcx1 -join "`n").StartsWith("BCX1_OK "))) {
    throw "ABORT: la base de PC-A no dio BCX1_OK. Resultado: $($bcx1 -join ' ')"
}

$work = "$Salida.work"
if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force }
if (Test-Path -LiteralPath "$Salida.zip") { Remove-Item -LiteralPath "$Salida.zip" -Force }
New-Item -ItemType Directory -Path "$work\BC-Caja", "$work\Clon\LocalAppData\BC\Security", "$work\Clon\Datos" -Force | Out-Null
Copy-Item -Path "$package\*" -Destination "$work\BC-Caja" -Recurse -Force
foreach ($name in $required) {
    Copy-Item -LiteralPath (Join-Path $securityRoot $name) -Destination "$work\Clon\LocalAppData\BC\Security\$name" -Force
}
Copy-Item -LiteralPath $Base -Destination "$work\Clon\Datos\bc_caja.sqlite3" -Force
Copy-Item -LiteralPath "$package\EJECUTAR-PRUEBA-PC-B.ps1" -Destination "$work\EJECUTAR-PRUEBA-PC-B.ps1" -Force
$copiedBase = "$work\Clon\Datos\bc_caja.sqlite3"
$copiedCheck = & $securityExe verificar-bcx1 --base $copiedBase 2>&1
if ($LASTEXITCODE -ne 0 -or -not (($copiedCheck -join "`n").StartsWith("BCX1_OK "))) {
    throw "ABORT: la copia SQLite no es integra/protegida: $($copiedCheck -join ' ')"
}

$files = Get-ChildItem -LiteralPath $work -Recurse -File | Where-Object { $_.Name -ne "MANIFEST-PC-B.json" } | ForEach-Object {
    [ordered]@{
        path = $_.FullName.Substring($work.Length + 1).Replace("\", "/")
        bytes = $_.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
    }
}
$manifest = [ordered]@{
    format = "bc.pc-b-clone.v1"
    created_utc = [DateTime]::UtcNow.ToString("o")
    source_check = "ALLOW / OK"
    source_data_check = ($bcx1 -join " ")
    copied_data_check = ($copiedCheck -join " ")
    files = @($files)
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$work\MANIFEST-PC-B.json" -Encoding UTF8
Compress-Archive -Path "$work\*" -DestinationPath "$Salida.zip" -CompressionLevel Optimal -Force
$zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath "$Salida.zip").Hash.ToLowerInvariant()
Write-Output "BUNDLE_PC_B_OK ruta=$Salida.zip sha256=$zipHash"
