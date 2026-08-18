# INSTALL_READINESS — BC Caja 1.0.0-rc.31

**El paquete está listo y verificado. La instalación NO se ejecutó, y no por permisos:
este equipo no tiene instalada rc.30.**

## Por qué no se instaló

El gate pasó y rc.31 se empaquetó. El paso siguiente era el backup preinstall de rc.30 y
la instalación transaccional sobre ella. Al verificar el destino real
—`%LOCALAPPDATA%\Programs\BC-Caja-Pilot`— apareció otra cosa:

| Comprobación | Esperado (canónico) | Encontrado en este equipo |
| --- | --- | --- |
| `VERSION.txt` de la instalación vigente | `BC Caja 1.0.0-rc.30` | `BC Caja 1.0.0-rc.27` |
| Fecha del `BC-Caja.exe` instalado | 17-08 (build rc.30) | 16-08-2026 22:41 |
| Backup preinstall de rc.30 | `bc-caja-pre-1.0.0-rc.30-*.sqlite3` | no existe; la serie corta en rc.15 |
| Carpeta de rollback de rc.30 | `BC-Caja-Pilot.previous-rc15` / `rollback-rc27-*` | no existen; la última es `rollback-rc26-20260816h` |
| Paquete rc.28 / rc.29 / rc.30 en disco | presente | ninguno |

Es decir: **la instalación productiva de rc.30 vive en otra máquina, la de la Óptica.**
Este equipo es el de desarrollo y quedó en una instalación de la serie rc.27.

Instalar rc.31 acá sería instalar sobre rc.27, saltando el tramo rc.28→rc.30 que nunca se
ensayó en esta máquina, y dejar asentado como "instalación productiva validada" algo que
no lo es. No se hizo, y no se declara hecho.

## Lo que sí quedó verificado del paquete

| | |
| --- | --- |
| Versión | `1.0.0-rc.31` (en `VERSION.txt` del paquete, no en el nombre del script) |
| Zip | `releases/BC-CAJA-1.0.0-rc.31-win64.zip`, 34 111 433 bytes |
| sha256 del zip | `95e9148a2c712ccb6622f2fb89cc0dcc4e7547c002308ba532988217f95c2948` |
| sha256 del exe | `62e8f1d87206b31b428892dc60266dde3394ef30a8b530b41f53563fe892152f` |
| Contenido | `BC-Caja.exe`, `VERSION.txt`, `INSTALACION.txt`, `GUIA_RAPIDA.txt` |
| Migraciones embebidas | 21 |
| Suite | 682 passed |
| Smoke del binario | arranca en directorio de datos aislado, crea esquema en 021, `integrity ok`, `foreign_key_check 0`, outbox 0, sin `startup-error.log` |
| DB local | `sha256` sin cambios antes y después del smoke |

## Runbook para ejecutar en la máquina de la Óptica

Requiere que ahí la instalación vigente sea efectivamente rc.30. **Verificarlo primero: si
`VERSION.txt` no dice rc.30, detenerse y reportar.**

```powershell
$P = "$env:LOCALAPPDATA\Programs\BC-Caja-Pilot"
$D = "$env:LOCALAPPDATA\BC\Caja"
$S = Get-Date -Format "yyyyMMdd-HHmmss"

# 0. Verificar el punto de partida y que no haya nadie usando el programa
Get-Content "$P\VERSION.txt" -TotalCount 1        # debe decir: BC Caja 1.0.0-rc.30
Get-Process BC-Caja -ErrorAction SilentlyContinue # debe estar vacío

# 1. Backup preinstall de la base, con hash verificado
Copy-Item "$D\bc_caja.sqlite3" "$D\bc-caja-pre-1.0.0-rc.31-$S.sqlite3"
(Get-FileHash "$D\bc_caja.sqlite3").Hash -eq (Get-FileHash "$D\bc-caja-pre-1.0.0-rc.31-$S.sqlite3").Hash

# 2. Rollback: apartar rc.30 entera, sin borrarla
Copy-Item $P "$P.rollback-rc30-$S" -Recurse
Get-Content "$P.rollback-rc30-$S\VERSION.txt" -TotalCount 1

# 3. Instalar rc.31
Expand-Archive "<ruta>\BC-CAJA-1.0.0-rc.31-win64.zip" "$env:TEMP\rc31-$S" -Force
(Get-FileHash "$env:TEMP\rc31-$S\BC-Caja\BC-Caja.exe").Hash.ToLower()
# debe ser 62e8f1d87206b31b428892dc60266dde3394ef30a8b530b41f53563fe892152f
Move-Item $P "$P.replaced-rc30-$S"
Move-Item "$env:TEMP\rc31-$S\BC-Caja" $P
Get-Content "$P\VERSION.txt" -TotalCount 1        # debe decir: BC Caja 1.0.0-rc.31
```

Si cualquier paso falla, ejecutar `ROLLBACK.md` antes de seguir.

## Validación post-install (los 10 puntos, en la máquina de la Óptica)

`integrity_check` · `foreign_key_check` · 21 migraciones sin agregar ninguna ·
datos y montos sin cambios contra el backup del paso 1 · Pedidos · Seguimiento ·
Historial · Arqueo · Administrador · correo y outbox sin envíos.
