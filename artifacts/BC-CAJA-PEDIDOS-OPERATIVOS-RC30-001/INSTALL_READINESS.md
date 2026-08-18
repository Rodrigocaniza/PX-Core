# INSTALL_READINESS — BC Caja 1.0.0-rc.31

> **EJECUTADO el 18-08-2026 en la PC de la Optica, stamp `20260818-123848`.**
> Este runbook se corrio entero y rc.31 quedo instalada y validada. Lo que sigue queda
> como registro historico: la tabla "Encontrado en este equipo" describe el equipo de
> desarrollo, que estaba en rc.27 y no era el destino. El resultado real esta en
> `INSTALL_EVIDENCE.md`.

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

## Confirmado por el operador

rc.30 **sí** fue instalada y validada en la máquina de la Óptica. Este equipo es el de
casa y quedó en rc.27. La tabla de arriba no describe un release perdido: describe que
este equipo no es el destino.

## El zip se recupera solo: no hace falta transporte físico

Los zips de RC están gitignoreados por convención —viaja el hash en el `MANIFEST`, no el
binario—, así que clonar la rama no lo trae. Y reconstruirlo allá **no** sirve para
verificar contra estos hashes: PyInstaller no produce binarios reproducibles byte a byte,
así que un rebuild daría otro `sha256` y el runbook fallaría con todo en orden.

El artefacto exacto quedó publicado como release asset de un repositorio **privado**,
fuera del historial Git:

| | |
| --- | --- |
| Repositorio | `Rodrigocaniza/PX-Core-releases` (privado) |
| Tag | `bc-caja-1.0.0-rc.31` |
| Asset | `BC-CAJA-1.0.0-rc.31-win64.zip` |
| sha256 | `95e9148a2c712ccb6622f2fb89cc0dcc4e7547c002308ba532988217f95c2948` |

**Round-trip verificado desde la PC de casa:** subido y vuelto a descargar, el zip vuelve
con el mismo `sha256` y los mismos 34 111 433 bytes; el `BC-Caja.exe` dentro conserva
`62e8f1d8…` y su `VERSION.txt` dice rc.31.

### Recuperarlo en la Óptica

Requiere `gh` autenticado con acceso al repo privado. Verificarlo primero:

```powershell
gh auth status          # si falla: gh auth login
gh release view bc-caja-1.0.0-rc.31 --repo Rodrigocaniza/PX-Core-releases
```

```powershell
$Z = "$env:TEMP\rc31"
gh release download bc-caja-1.0.0-rc.31 `
  --repo Rodrigocaniza/PX-Core-releases `
  --pattern "BC-CAJA-1.0.0-rc.31-win64.zip" --dir $Z

# No instalar nada si esto no da True
(Get-FileHash "$Z\BC-CAJA-1.0.0-rc.31-win64.zip").Hash.ToLower() -eq `
  "95e9148a2c712ccb6622f2fb89cc0dcc4e7547c002308ba532988217f95c2948"
```

Si `gh` no estuviera disponible allá, el mismo asset se baja desde la web del repositorio
privado con la cuenta del dueño; el paso de verificación de hash es el mismo y no es
opcional. Recién ahí sigue el runbook, con `<ruta>` = `$Z\BC-CAJA-1.0.0-rc.31-win64.zip`.

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
