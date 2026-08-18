# ROLLBACK — BC Caja 1.0.0-rc.31 → 1.0.0-rc.30

**Hoy no hay nada que revertir: rc.31 no se instaló.** Este procedimiento queda listo para
usarse en la máquina de la Óptica si la instalación de `INSTALL_READINESS.md` sale mal.

Depende de dos cosas que ese runbook crea antes de tocar nada, y no funciona sin ellas:

- `%LOCALAPPDATA%\BC\Caja\bc-caja-pre-1.0.0-rc.31-<stamp>.sqlite3` — backup de la base con
  hash verificado contra el original;
- `%LOCALAPPDATA%\Programs\BC-Caja-Pilot.rollback-rc30-<stamp>` — copia entera de rc.30.

## Volver a rc.30

```powershell
$P = "$env:LOCALAPPDATA\Programs\BC-Caja-Pilot"
$D = "$env:LOCALAPPDATA\BC\Caja"
$S = "<el stamp que usó la instalación>"

# 1. Cerrar el programa
Get-Process BC-Caja -ErrorAction SilentlyContinue | Stop-Process -Force

# 2. Apartar rc.31, sin borrarla: si el problema era de datos hay que poder mirarla
Move-Item $P "$P.failed-rc31-$S"

# 3. Restituir rc.30
Copy-Item "$P.rollback-rc30-$S" $P -Recurse
Get-Content "$P\VERSION.txt" -TotalCount 1        # debe decir: BC Caja 1.0.0-rc.30

# 4. Restituir la base SOLO si rc.31 llegó a escribir
#    Comparar primero; si el hash coincide con el backup, no tocar nada.
(Get-FileHash "$D\bc_caja.sqlite3").Hash -eq (Get-FileHash "$D\bc-caja-pre-1.0.0-rc.31-$S.sqlite3").Hash
Copy-Item "$D\bc_caja.sqlite3" "$D\bc-caja-post-rc31-descartada-$S.sqlite3"
Copy-Item "$D\bc-caja-pre-1.0.0-rc.31-$S.sqlite3" "$D\bc_caja.sqlite3" -Force

# 5. Verificar que rc.30 abre sobre la base restituida
Start-Process "$P\BC-Caja.exe"
```

El paso 4 conserva la base que dejó rc.31 antes de pisarla. Si el problema fue de datos,
descartarla sin copia sería perder la única evidencia de qué pasó.

## Por qué rc.31 no agrega riesgo de esquema

No trae migraciones nuevas: rc.30 y rc.31 comparten las 21 (001-021). El rollback es de
binario, no de esquema, así que rc.30 vuelve a abrir la misma base sin conversión inversa.
El paso 4 existe por los datos que rc.31 pudiera haber escrito en uso normal, no por el
esquema.

## Estado actual de los rollbacks disponibles

En el equipo de desarrollo: `BC-Caja-Pilot.rollback-rc26-20260816h` y 10 anteriores. En la
máquina de la Óptica hay que verificarlos in situ; este equipo no puede afirmarlo.
