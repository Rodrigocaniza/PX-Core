$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$manifestPath = Join-Path $root "MANIFEST-PC-B.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "ABORT: falta MANIFEST-PC-B.json"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach ($entry in $manifest.files) {
    $path = Join-Path $root ($entry.path.Replace("/", "\"))
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "ABORT: falta $($entry.path)" }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
    if ($hash -ne $entry.sha256) { throw "ABORT: hash distinto en $($entry.path)" }
}

$env:LOCALAPPDATA = (Resolve-Path (Join-Path $root "Clon\LocalAppData")).Path
$exe = Join-Path $root "BC-Caja\Seguridad\BC-Seguridad.exe"
$base = Join-Path $root "Clon\Datos\bc_caja.sqlite3"
$deny = & $exe verificar --base $base 2>&1
$denyCode = $LASTEXITCODE
if ($denyCode -ne 2 -or -not (($deny -join "`n").StartsWith("DENY / MAQUINA_DISTINTA"))) {
    throw "ABORT: se esperaba DENY / MAQUINA_DISTINTA exit 2; recibido exit $denyCode: $($deny -join ' ')"
}
$bcx1 = & $exe verificar-bcx1 --base $base 2>&1
if ($LASTEXITCODE -ne 0 -or -not (($bcx1 -join "`n").StartsWith("BCX1_OK "))) {
    throw "ABORT: la SQLite copiada no dio BCX1_OK: $($bcx1 -join ' ')"
}
Write-Output "PC_B_REAL_OK DENY_MAQUINA_DISTINTA exit=2 $($bcx1 -join ' ')"
