# BC Caja 1.0.0-rc.24 — Versión consolidada

Única versión de las Misiones 1, 2 y 3. No se construyó ninguna intermedia.

## Build

```
BC_CAJA_BUILD_OK version=1.0.0-rc.24
zip=releases/BC-CAJA-1.0.0-rc.24-win64.zip   (34.666.716 bytes)
```

Producido con `pilot/build_pilot.ps1`, que toma la versión de
`pilot/package_docs/VERSION.txt` en vez de cablearla.

El binario queda **local y no se exporta al remoto**, siguiendo la convención
vigente desde rc.20 (ver `.gitignore`).

## Contenido verificado del paquete

| Comprobación | Resultado |
|---|---|
| `BC-Caja.exe` | presente |
| `VERSION.txt` en el paquete | `BC Caja 1.0.0-rc.24` |
| `INSTALACION.txt` · `GUIA_RAPIDA.txt` | presentes |
| Migraciones empaquetadas | hasta `020_branch_bindings_canonicas.sql` |

## Arranque real del ejecutable empaquetado

Lanzado con `BC_CAJA_DATA_DIR` a un directorio temporal, **sin instalar**:

```
EXE_VIVO                 (la ventana abre y se mantiene)
MIGRACIONES: 018, 019, 020
BINDINGS:    P2→PILAR · PC→ASUNCION · PILAR→PILAR
```

El esquema se migra solo hasta 020 y los tres vínculos canónicos quedan
sembrados exactamente como los declaró la operación. Los datos siguen fuera
del ejecutable.

## Estado

| | |
|---|---|
| Regresión | 497 PASS / 0 FAIL |
| Smoke GUI 1920×1080 | PASS |
| Smoke GUI 1366×768 | PASS |
| Producción | sigue en **rc.23** |
| Instalación | **no realizada** — HUMAN_GATE |

## HUMAN_GATE — instalación y prueba manual

La versión consolidada está lista. **No se instaló nada.** Falta la decisión
de instalar `releases/BC-CAJA-1.0.0-rc.24-win64.zip` y la prueba manual con
los mismos 15 TEST sobre la aplicación instalada.

Al instalar, la migración 020 vincula `PC`, `P2` y `PILAR` a su sucursal. Es
lo que hace aparecer la alerta principal, así que conviene confirmar sobre la
instalación real que cada caja muestra la alerta de **su** local y no la de
la otra sucursal.
