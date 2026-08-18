# ROLLBACK — BC Caja 1.0.0-rc.31 → 1.0.0-rc.30

> **Revisión 18-08-2026 — rc.31 YA ESTÁ INSTALADA en la PC de la Óptica.**
> Este procedimiento pasó de hipotético a ejecutable: sus dos insumos existen en disco y
> están verificados. El rollback **no** se ejecutó y hoy no hace falta —rc.31 no escribió
> una sola vez en la base durante la validación—, pero si aparece un problema en uso
> normal, esto es lo que hay que correr.
>
> La versión anterior de este documento fue escrita antes de la instalación, con el stamp
> sin resolver y el nombre del backup equivocado (`bc-caja-pre-…` en la carpeta `Caja`,
> cuando el real es `bc-caja-preinstall-…` dentro de `Caja\Backups`). Tal como estaba, el
> paso 4 habría fallado por archivo inexistente justo cuando más importa. Queda corregido
> con las rutas reales.

## Los insumos, ya creados y verificados

| Qué | Dónde | Verificado |
| --- | --- | --- |
| Backup de la base preinstall | `%LOCALAPPDATA%\BC\Caja\Backups\bc-caja-preinstall-1.0.0-rc.31-20260818-123848.sqlite3` | sha256 `1c4fcc40…98ec`, idéntico al original |
| Copia entera de rc.30 | `%LOCALAPPDATA%\Programs\BC-Caja-Pilot.rollback-rc30-20260818-123848` | `VERSION.txt` rc.30, exe `a38262a5…adc2`, 1136 archivos |
| Segunda copia de rc.30 | `%LOCALAPPDATA%\Programs\BC-Caja-Pilot.replaced-rc30-20260818-123848` | la instalación original apartada, no borrada |

Hay **dos** copias independientes de rc.30. Si una se corrompiera, la otra sirve igual.

Stamp de la operación: `20260818-123848`.

## Volver a rc.30

```powershell
$P = "$env:LOCALAPPDATA\Programs\BC-Caja-Pilot"
$D = "$env:LOCALAPPDATA\BC\Caja"
$S = "20260818-123848"
$BK = "$D\Backups\bc-caja-preinstall-1.0.0-rc.31-$S.sqlite3"

# 0. Confirmar que los insumos están antes de tocar nada
Test-Path $BK                                     # debe dar True
Test-Path "$P.rollback-rc30-$S"                   # debe dar True

# 1. Cerrar el programa
Get-Process BC-Caja -ErrorAction SilentlyContinue | Stop-Process -Force

# 2. Apartar rc.31, sin borrarla: si el problema era de datos hay que poder mirarla
Move-Item $P "$P.failed-rc31-$S"

# 3. Restituir rc.30
Copy-Item "$P.rollback-rc30-$S" $P -Recurse
Get-Content "$P\VERSION.txt" -TotalCount 1        # debe decir: BC Caja 1.0.0-rc.30
(Get-FileHash "$P\BC-Caja.exe").Hash.ToLower()
# debe ser a38262a540ef59ea6be02ccb6a2db20242dfd791c11c79bc79c1cbadac52adc2

# 4. Restituir la base SOLO si rc.31 llegó a escribir.
#    Comparar primero; si el hash coincide con el backup, no tocar nada.
(Get-FileHash "$D\bc_caja.sqlite3").Hash -eq (Get-FileHash $BK).Hash
Copy-Item "$D\bc_caja.sqlite3" "$D\Backups\bc-caja-post-rc31-descartada-$S.sqlite3"
Copy-Item $BK "$D\bc_caja.sqlite3" -Force

# 5. Verificar que rc.30 abre sobre la base restituida
Start-Process "$P\BC-Caja.exe"
```

El paso 4 conserva la base que dejó rc.31 antes de pisarla. Si el problema fue de datos,
descartarla sin copia sería perder la única evidencia de qué pasó.

Al momento de la validación post-install, esa comparación daba `True`: la base tenía el
mismo sha256 que el backup, así que el paso 4 no habría restituido nada. Si más adelante da
`False`, es porque hubo uso real de por medio y ahí sí corresponde restituir.

## Por qué rc.31 no agrega riesgo de esquema

No trae migraciones nuevas: rc.30 y rc.31 comparten las 21 (001-021), y la validación
post-install lo confirmó contra la base productiva. El rollback es de binario, no de
esquema, así que rc.30 vuelve a abrir la misma base sin conversión inversa. El paso 4
existe por los datos que rc.31 pudiera escribir en uso normal, no por el esquema.

## Estado de los rollbacks disponibles

En la PC de la Óptica, verificados in situ el 18-08-2026: las dos copias de rc.30 de la
tabla de arriba, más la serie previa `BC-Caja-Pilot.previous-rc5` … `previous-rc15`.

En el equipo de desarrollo, que es otra máquina y está en la serie rc.27:
`BC-Caja-Pilot.rollback-rc26-20260816h` y 10 anteriores. No aplican acá.
