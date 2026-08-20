# Artifact Consistency — V1-020

Cada afirmación de `SUMMARY.md` y `MANIFEST.json`, contra la fuente que la
sostiene. Lo que no se pudo contrastar, se dice.

## Números y afirmaciones

| afirmación | contra qué | |
|---|---|---|
| la línea contiene V1-019A, 018, 017 y `origin/main` | `git merge-base --is-ancestor`, cuatro veces | ✔ |
| `origin/main` intacto en `7db56a0` | `git rev-parse origin/main` | ✔ |
| la comisión del 1% está en otra línea | `merge-base --is-ancestor` da falso para `mission/bc-gestion-central-comision-policy-1pct-001` | ✔ |
| `030` era la última antes de este slice | `ls migrations/` y la cadena aplicada | ✔ |
| la 031 se aplica y la cadena queda entera | `afirmar_cadena_completa_con(conexion, "031")` | ✔ |
| la 031 es estrictamente aditiva | prueba que lee el `.sql` y busca `ALTER TABLE` / `UPDATE` / `DELETE` / `DROP` al inicio de sentencia | ✔ |
| la 031 sólo escribe su catálogo | misma prueba, sobre las líneas `INSERT` | ✔ |
| ningún tipo de trabajo puede ser stockeable | `INSERT` con `stockeable=1` → `IntegrityError` | ✔ |
| cero movimientos de inventario en todos los estados | conteo de `stock_movements` después de cada paso, para los cuatro conceptos | ✔ |
| ni artículos ni `domain_events` ni `event_effects` | conteo de las tres tablas tras el ciclo completo | ✔ |
| el módulo no puede mover stock | los tres archivos no contienen `modulos.comercial`, `stock_movements` ni `inventory` | ✔ |
| nueve tablas económicas idénticas antes/después | foto de `COUNT(*)` sobre el ciclo completo con anulación | ✔ |
| Hilo/Tornillo/Plaqueta/Patillas ya eran no stockeables | `tools/conciliacion_inventario_corregido_optica.py`, `A_SERVICIO` y `NATURE_CORRECTION` de V1-010 | ✔ |
| el devengo es en `LISTO` | `ESTADO_DE_DEVENGO is JobStatus.READY`, y prueba de que entregar no vuelve a devengar | ✔ |
| la comisión no se duplica | reintento sobre el mismo `event_id` devuelve `None` y el asiento sigue siendo uno | ✔ |
| anular compensa y el saldo queda en cero | `sum(amount) == 0` y `service_commission_balance` | ✔ |
| sin política no hay comisión | responsable sin política → lista de asientos vacía | ✔ |
| no hay nombres cableados | ninguna prueba siembra política sin declarar el `user_id`; la 031 no inserta personas | ✔ |
| la sucursal la decide la caja | operadora de Asunción en caja de Pilar → trabajo en Pilar | ✔ |
| no hay operación anónima | crear sin actor y con token falso, las dos rechazadas | ✔ |
| no hay hard-delete | `DELETE` sobre `service_jobs` y sobre `service_job_events` → `IntegrityError` | ✔ |
| la historia no se reescribe | `UPDATE` sobre `service_job_events` → `IntegrityError` | ✔ |
| guardar dos veces no duplica hechos | `save_service_job` dos veces, misma cantidad de hechos | ✔ |
| el panel abre en «Listos» | `panel._vista.get() == VISTA_LISTOS` | ✔ |
| sólo se habilita lo que el trabajo admite | estado de los seis botones en tres situaciones distintas | ✔ |
| 88 dirigidas | `88 passed` | ✔ |
| suite completa 1288 verdes, 0 rojas | `1288 passed`, dos corridas | ✔ |
| once líneas de enganche en `CajaDiaria.py` | `git diff --stat`: `CajaDiaria.py \| 11 +` | ✔ |

## Lo que se afirma sin poder contrastarlo acá

| afirmación | por qué no se puede | qué se hizo |
|---|---|---|
| «Rochi cobra 5.000 y la dirección no cobra» | son personas reales que todavía no están cargadas: la 030 no se aplicó en la Óptica | no se sembró ningún nombre. La política se carga allá, contra personas reales. La prueba usa personas de prueba |
| «la 031 no rompe datos productivos» | no hay base productiva en Casa | se verificó que la migración no tiene una sola sentencia que pueda modificar una fila existente. Es lo más fuerte que se puede afirmar desde acá, y se declara así |
| el comportamiento de la pestaña con volumen real | no hay trabajos reales | las pruebas de UI corren contra el panel de verdad, no contra un doble |

## Diferencias entre lo pedido y lo entregado

**Se pidió** corregir la lógica anterior que tratara Hilo, Tornillo y Plaqueta
como artículos físicos, «si puede hacerse sin romper historia legítima».
**No se corrigió nada**, y la razón es que ya estaba corregido: V1-010 lo hizo
con su evidencia y su cierre auditado. Volver a hacerlo habría reescrito una
decisión tomada. Lo que se entregó en su lugar es la prueba de que sigue
vigente.

**Se pidió** determinar si el devengo va en `LISTO` o en `ENTREGADO` derivándolo
del flujo real. Se decidió `LISTO`, y el argumento está en `SUMMARY.md` y en el
comentario de `ESTADO_DE_DEVENGO`. Es una decisión reversible en un solo lugar
si la Óptica dice otra cosa.
