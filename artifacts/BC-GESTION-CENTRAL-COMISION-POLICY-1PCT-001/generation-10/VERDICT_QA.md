# Verdict — QA, generación 10
Runner: QA-IND-COMISION-POLICY-1PCT-010
Snapshot: bdc4f53fb8b3095ead16fbeadcc3d23ca6f2f2d8
Veredicto: PASS

## Escenarios propios ejecutados

Todos escritos por mí en el scratchpad de sesión (`escenarios.py`, `ui_check.py`, `conflicto.py`, `conflicto2.py`), con bases sqlite temporales e `sys.path` apuntando al worktree. El repo quedó sin modificar (`git status` vacío, HEAD intacto).

Método adicional de independencia: además de comprobar cada punto del contrato contra el snapshot de la generación 10, extraje el árbol `modulos/` de la generación 9 (`f284b6c`) a un directorio aparte y **ejecuté el mismo script de escenarios contra los dos árboles**, comparando las salidas serializadas. Es la forma directa de verificar el eje «nada cambió de comportamiento» sin depender de lo que afirme el paquete.

- S1 — Economía base. Venta común 400.000 cancelada → 1%, base 400.000, comisión 4.000. Convenio 500.000 → descuento 25.000, base 475.000, comisión 4.750. Ningún evento de tasa escrito.
- S2 — `PAGADA` viva al 7% en base migrada del piloto (políticas por vendedora 7% y por local 5%, que la migración retira). El mes 2099-01 queda fijado a 700 bp por `MIGRACION`; el importe pagado sigue en 700.000 antes y después de operar sobre el mes; una venta nueva del mismo mes cobra 7% (1.000.000 → 70.000), no 1%.
- S3 — 1% prospectivo. Mes 2099-02, sin tasa histórica viva que preservar: `pinned=false`, tasa 100 bp, venta de 2.000.000 → 20.000. Sin eventos.
- S4 — Boundary. `ELEGIBLE`, `CALCULADA` y `REVISADA` no escriben nada en el libro; `APROBADA` escribe `PINNED`; `PAGADA` posterior no reescribe ni duplica.
- S5 — Pin sostenido. Dos `APROBADA` a la misma tasa: revertir la primera no mueve el libro; revertir la última escribe `UNPINNED`.
- S6 — Pin sin respaldo. Libro legado con `PINNED` 900 y único hecho vivo al 7%: al abrir la base se corrige con `UNPINNED`(900) y después `PINNED`(700), y `policy_for_period` devuelve 7%.
- S7 — Evidencia discrepante. Mes con `APROBADA` 7% y `APROBADA` 5% vivas: no se forma pin, se asienta `SEED_SKIPPED` con `rates_bp=[500,700]`, y aprobar una liquidación nueva no fija por sí mismo.
- S8 — Secuencia completa: aprobar → `PINNED`; revertir → `UNPINNED`; aprobar y pagar otra → `PINNED`. Anular la venta de la `PAGADA` no suelta el mes y no toca su importe.
- S9 — **Eje nuevo (rutas que ahora reconcilian).** Siete sub-casos comparando el libro antes/después: corrección de origen sobre mes sin fijar; corrección de origen sobre mes fijado por otra liquidación; recálculo repetido; recálculo sobre mes fijado; promoción a elegible por cobro final sobre mes sin fijar; promoción a elegible sobre mes ya fijado; anulación de venta con liquidación sólo calculada. **En los siete el libro quedó exactamente igual: cero `PINNED` y cero `UNPINNED` espurios**, y los importes aprobados/pagados intactos.
- S10 — Rechazo por política desfasada: «la política del período cambió desde el cálculo (1,00% v1 → 3,00% v2)». En un segundo caso donde antes el mensaje habría sido el vacío `(v1 → v1)`, ahora dice `(9,00% v1 → 1,00% v1)`.
- S11 — Rotulado en los cuatro puntos de la secuencia sobre `report`, `export_summary` (contract_version 3), `policy` y `policy_disclaimer`. El texto distingue fijada de provisional y nunca emite `None`.
- S12 — Rotulado y export sobre la base migrada del piloto en 2099-01 (7% fijado), 2099-02 (1% provisional), 2099-03 (discrepante) y 2099-05 (corregido a 7%).
- S13 — Reapertura de la base migrada cinco veces: libro idéntico, un solo asiento de conflicto.
- S14 — Publicación con una fila legada de fecha completa (`2099-07-15`) en el libro: los períodos protegidos declarados son `["2099-03"]`, sin el mes fantasma.
- S15 — Abrir la base aplica la misma regla que las transiciones (libro en caliente == libro tras reabrir).
- S16 — **Rotulado de pantalla 1920×1080** con `CommissionsPanel` real (tkinter) en los cuatro puntos de la secuencia, más un mes sin tasa en vigor y sobre la base migrada con la `PAGADA` al 7%.
- S17 — Conflicto en caliente: un tercer hecho vivo a otra tasa asienta un segundo conflicto distinto (`[500,700,900]`, actor real) sin duplicar el primero.
- S18 — **Mutación de la guarda estructural:** retiré la reconciliación de `_promote_to_eligible` en una copia del árbol fuera del repo y el test estructural falla nombrando la función.
- S19 — Comparación generación 9 vs generación 10 sobre los quince escenarios instrumentados: **trece salen idénticas carácter a carácter**. Las dos únicas diferencias son las esperadas: el mensaje de política desfasada ahora nombra la tasa, y los períodos protegidos ya no incluyen el mes fantasma.
- S20 — `python -m pytest -q`: **453 passed**.

## Bloqueantes
Ninguno.

## Observaciones no bloqueantes

1. `modulos/gestion_central/comisiones.py` importa dos veces la misma línea (`from .repository import CentralRepository`). Es inocua, pero es ruido introducido por esta generación.
2. La fila de libro con clave sucia (`period='2099-07-15'`) deja de declararse «protegida», que es el defecto corregido, pero **la fila en sí no se normaliza ni se reconcilia nunca**: queda huérfana de forma permanente sin ruta de corrección. Hoy nadie la lee, así que no afecta al dinero ni al rótulo.
3. `_audit_conflict_once` deduplica con un `LIKE` sobre el JSON serializado. El `_` de `rates_bp` es comodín de `LIKE`, y la huella depende del formato exacto de `json.dumps`. Funciona en mis pruebas, pero es una comparación de texto sobre un serializado, no sobre un dato.
4. Recalcular un mes con evidencia discrepante lo desempata como efecto colateral: reparar la primera `APROBADA` la saca de los hechos vivos, y la reconciliación que sigue fija el mes con el superviviente. **Verifiqué que la generación 9 hace exactamente lo mismo**, así que no es regresión de la 10; pero la afirmación «mientras la evidencia discrepe no se forma pin» se sostiene sólo hasta que alguien pulsa Recalcular.
5. Confirmo que las observaciones 3 y 4 de la generación 9 siguen presentes. Quedan abiertas a propósito y no las cuento.

## Superficie que mi revisión NO cubrió

- Concurrencia real: dos procesos o dos hilos reconciliando el mismo período a la vez.
- La base del piloto real en disco: construí bases migradas sintéticas propias.
- Escritura efectiva del fichero de export desde el botón «Exportar resumen».
- Captura de pantallas y verificación visual pixel a pixel; leí los rótulos por sus widgets.
- Roles distintos de `ADMIN_CENTRAL`.
- El resto de los módulos más allá de lo que cubre `pytest -q`.
- Coherencia documental del paquete: `MANIFEST.sha256`, el `.zip`, `WORKFLOW.json` y los verdicts anteriores.
- Rendimiento de `pinned_periods_from`, que pasó de un `JOIN` único a una consulta por período.
