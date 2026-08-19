# Artifact Consistency — BC-OPTICA-LABORATORIO-POR-DEFECTO-V1-012

Cada cifra de los artefactos contra la fuente de la que sale.

| Afirmación | Dónde está | De dónde sale | Verificado |
|---|---|---|---|
| base Git `c838f10` | MANIFEST, WORKFLOW | `git rev-parse` sobre el tip de V1-014 | PASS |
| `origin/main` sigue en `7db56a0` | MANIFEST | `git log origin/main` | PASS |
| estado productivo declarado por el dueño | WORKFLOW | radiografía previa: 3.596 / 2.829 / 4.441, ASU 6.166, PIL 2.260 | PASS |
| sha256 antes `ffafb5c6…` | MANIFEST | pre-guard; coincide con el cierre de V1-014 | PASS |
| sha256 después `a335805e…` | MANIFEST | `APLICACION_PRODUCTIVA.txt` | PASS |
| backup `cebf6b56…` | MANIFEST | `Get-FileHash` del archivo | PASS |
| `laboratories` estaba vacía | MANIFEST, SUMMARY | consulta previa: 0 filas | PASS |
| el catálogo es el de la migración 003 | MANIFEST, SUMMARY | `sqlite_master`; la tabla la crea `003_laboratory.sql` | PASS |
| 3 laboratorios, uno por nombre | MANIFEST | `VERIFICACION_POST.txt` | PASS |
| 24 asignaciones: 16 / 7 / 1 | MANIFEST, SUMMARY | `VERIFICACION_POST.txt`, listadas una por una | PASS |
| los 24 son `TRABAJO_BAJO_PEDIDO` | MANIFEST | `VERIFICACION_POST.txt` | PASS |
| 7 códigos del brief no existen | MANIFEST, SUMMARY, GATE | `CATALOGO_CONTRA_PRODUCCION.txt`, y ausentes también en dos backups | PASS |
| 5 nombres distintos con el mismo código | MANIFEST, SUMMARY | `CATALOGO_CONTRA_PRODUCCION.txt` | PASS |
| `2000212` es `PRODUCTO_STOCKEABLE` en Armazones | MANIFEST, SUMMARY | `VERIFICACION_POST.txt` | PASS |
| `2000212` sin laboratorio | MANIFEST, SUMMARY | `VERIFICACION_POST.txt` | PASS |
| 6 cristales activos sin default | MANIFEST, GATE | consulta sobre producción | PASS |
| `2000219` tiene el nombre exacto de `2000078` | SUMMARY, GATE | consulta por nombre | PASS |
| marcas de esos 6: 5 Optilab, 1 FENIX | GATE | consulta sobre producción | PASS |
| Hilo en la fuente original dice Optilab | MANIFEST, SUMMARY | `P2 - Inventario.xlsx`, fila 854 | PASS |
| Hilo en las corregidas dice «Óptica Puppilent\`s» | MANIFEST, SUMMARY, GATE | `Inventario P2.xls` fila 734 y `Inventario PC.xls` fila 1672 | PASS |
| las 21 filas de Compostura corregidas a Puppilent\`s | SUMMARY, GATE | agrupación por categoría del P2 corregido | PASS |
| 20 cristales con laboratorio como marca | MANIFEST, GATE | consulta sobre producción | PASS |
| migración aditiva y no inventa datos | MANIFEST | `MIGRACION_028.txt`: 0 artículos con laboratorio tras migrar | PASS |
| rc.32 intacta, todo preservado | MANIFEST | `MIGRACION_028.txt`, 13 contadores iguales | PASS |
| stock y movimientos sin cambios | MANIFEST, SUMMARY | radiografía antes y después | PASS |
| único campo cambiado en `articles` | MANIFEST, SUMMARY | `VERIFICACION_POST.txt`, diff contra el backup previo | PASS |
| 10 líneas de venta idénticas al carácter | MANIFEST, SUMMARY | `VERIFICACION_POST.txt` | PASS |
| bitácora: sólo las dos acciones nuevas | MANIFEST | conteo por acción antes y después | PASS |
| 22 dirigidas | MANIFEST | `PRUEBAS_DIRIGIDAS.txt` | PASS |
| suite completa 1.003 | MANIFEST | `python -m pytest tests/` | PASS |
| idempotencia | MANIFEST | `IDEMPOTENCIA.txt`, y una corrida `--confirmar` repetida deja el mismo sha256 | PASS |
| circuito de venta | MANIFEST, SUMMARY | `CIRCUITO_DE_VENTA.txt` | PASS |
| smoke de UI | MANIFEST | `SMOKE_UI.txt` | PASS |
| rollback no usado | MANIFEST | ninguna corrida terminó en falla | PASS |

## Números que corregí en el camino

Dos asserts míos, no los datos:

- esperaba que ningún laboratorio existiera como marca. «Laboratorio Optilab» ya
  era marca de 23 artículos **antes** de esta misión — es justamente el arrastre
  que la misión encontró. El invariante correcto es que el conteo no cambie, no
  que sea cero.
- la herramienta leía `default_laboratory_id` antes de que la 028 hubiera
  corrido. Ahora aplica la migración ella misma, así no depende de que alguien
  haya abierto la app antes.

Ambos se corrigieron sobre copia, antes de tocar producción.

## Una nota sobre la evidencia de la migración

`MIGRACION_028.txt` corre sobre `bc-caja-premetadatos-20260819-170642.sqlite3` y
no sobre el backup de esta misión. El motivo es que la herramienta migra primero
y respalda después, así que su propio backup ya tiene 28 migraciones y no sirve
para probar el upgrade. El que se usa es la última foto productiva real con 27.

## HUMAN_GATE

Abierto y **no bloqueante**. Está en `HUMAN_GATE.md`: los 7 códigos ausentes, el
par `2000078`/`2000219`, los 6 cristales sin default, las marcas que son
laboratorios —incluido `2000070 Hilo`— y los teléfonos que faltan.
