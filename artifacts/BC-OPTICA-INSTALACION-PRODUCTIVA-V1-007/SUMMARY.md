# BC-OPTICA-INSTALACION-PRODUCTIVA-V1-007

**BC Caja 1.0.0-rc.32 está instalada en la Óptica, sobre la base productiva real,
con 27 migraciones y sin haber perdido ni cambiado un solo dato.**

## Qué faltaba y por qué

El slice 6 dejó rc.32 empaquetada, smokeada y con el gate 022→027 en PASS. Pero
ese gate corrió sobre la base local del piloto de PC Casa: misma forma, otros
datos. La misión 006 lo declaró explícitamente como **pendiente y bloqueante**.

Esta misión corrió el mismo gate contra la base productiva real de la Óptica —
12 entradas, 6.400.000, 10 líneas de venta, 2 días, 8 pedidos — sobre una copia
aislada, y recién con ese PASS instaló.

## El orden que se siguió

1. Estado canónico verificado, no supuesto. La rama del slice 6 **no existía en
   esta PC**; apareció con `fetch`. `5bc1540` confirmado y descendiente de
   `7db56a0`.
2. Base productiva localizada por `resolve_data_paths()`, no por ruta cableada.
3. Backup por la API de backup de SQLite, con sha256 y equivalencia verificada
   tabla por tabla. El WAL entró; una copia de archivo lo habría dejado afuera.
4. Gate 021→027 sobre copia aislada: **PASS, 0 fallas**. Cadena, integridad, FK,
   ninguna fila cambiada, circuito comercial completo con anulación
   compensatoria, rollback byte a byte, base de origen intacta.
5. Paquete rc.32 reconstruido aquí desde el mismo commit: el zip de Casa quedó
   local y no existe en esta máquina.
6. Smoke del ejecutable sobre copia de la base real, **antes** de instalar: PASS.
7. Instalación, con rc.31 conservada entera como rollback.
8. Post-instalación: el propio ejecutable aplicó 022→027, integridad ok, 0 FK,
   todos los datos productivos intactos.

## Estado final

| | antes | después |
| --- | --- | --- |
| BC Caja | 1.0.0-rc.31 | **1.0.0-rc.32** |
| migraciones | 21 (`021`) | **27 (`027`)** |
| entradas de Caja | 12 | 12 |
| dinero registrado | 6.400.000 | 6.400.000 |
| líneas de venta | 10 | 10 |
| días de caja | 2 | 2 |
| pedidos | 8 | 8 |
| artículos | — | 0 |

Lo nuevo es estructura, no datos: catálogo, ledger de inventario, event spine,
proveedores, compras, el vínculo venta↔artículo↔stock y la anulación
compensatoria. Ni un hecho de negocio inventado. El catálogo nace vacío porque
todavía no ocurrió el hecho que lo llena.

## Vuelta atrás disponible

- Base: `Backups\bc-caja-preinstall-1.0.0-rc.32-20260819-113826.sqlite3`,
  sha256 `4768ba6b…`, con rollback probado byte a byte en el gate.
- Binario: `BC-Caja-Pilot.rollback-rc31-20260819-1200`, rc.31 completa.

El binario **solo** no sirve hacia atrás: rc.31 no entiende 022–027. Hay que
volver también la base. Y en cuanto se cargue operación real sobre rc.32, volver
la base cuesta perder lo cargado.

## Lo que no se hizo, a propósito

- **Carga inicial del catálogo: no empezó.** Es misión aparte, como se pidió. El
  sistema ya tiene plantilla, importación en dos pasos, `nature` obligatoria e
  inventario inicial auditado por `INGRESO_ADMINISTRATIVO / INVENTARIO_INICIAL`;
  lo que falta es la fuente real de artículos.
- **Ninguna operación real con la operadora.** Cargar una venta de prueba sobre
  producción sería exactamente el hecho sin causa que la arquitectura prohíbe.
- **`main` sigue en `7db56a0`.** Sin merge, sin PR, sin force-push.
