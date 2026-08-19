# BC-OPTICA-RECUENTO-FISICO-PENDIENTES-V1-009

**Todo listo menos cinco números que sólo pueden salir de contar.**

## De dónde salen los cinco

No de este documento ni de un mensaje: de la base. `admin_audit_log` guarda una
fila por cada uno con acción `STOCK_INITIAL_PENDING_PHYSICAL_VERIFICATION`, y de
ahí sale todo — código, artículo, sucursal, naturaleza, la cifra que declaraba la
planilla, el archivo y la fila de donde vino. La misión anterior no dejó una nota
para acordarse: dejó una consulta.

Verificado que los cinco siguen sin movimiento en su sucursal, que ninguno estaba
ya cerrado, y que `000010 Limpia Cristal` conserva intactas sus 10 unidades de
Pilar mientras Asunción sigue sin nada.

## Lo que se preparó

Una herramienta que hace las dos mitades: `--listar` arma la planilla leyendo la
base, `--aplicar` asienta lo contado. Con backup verificable, validaciones,
verificación después de escribir y el procedimiento de vuelta atrás escrito.

Tres decisiones que valen la pena explicar:

**El hecho es el recuento de hoy.** El movimiento lleva la fecha de hoy, no la de
los XLSX de agosto, porque lo que ocurrió es que alguien contó hoy. Sigue siendo
`INGRESO_ADMINISTRATIVO` / `INVENTARIO_INICIAL`, que es lo que realmente es: la
primera vez que ese artículo tiene unidades.

**La cifra vieja no se toca.** El cierre guarda `source_reported_quantity` al
lado del conteo real, con el archivo y el corte de donde salió. Se puede
comparar; no se puede perder.

**Cero se registra, no se omite.** Si un artículo se cuenta y no hay ninguno, eso
queda como `PHYSICAL_COUNT_CONFIRMED = 0` **sin** movimiento — no se inventa un
movimiento de cero, que el modelo no necesita — y con `movimiento_creado = false`.
Es lo único que distingue «se contó y no había» de «nunca se contó».

## Dry-run — PASS, 0 fallas

Sobre copia de la base real, con cantidades de ensayo elegidas para ejercitar los
dos caminos: tres positivas y dos en cero. Los tres movimientos se crearon, los
dos ceros quedaron registrados sin unidades, Asunción no tocó Pilar, repetirlo no
escribió nada, integridad y FK limpias, Caja histórica intacta y la base
productiva con el mismo `sha256`.

Se corrigió algo de legibilidad en el camino: al reintentar un conteo ya
asentado, la herramienta lo reportaba como falla. No lo es — es no tener nada que
hacer — y ahora lo dice así.

## Backup

`bc-caja-prerecuento-20260819-142306.sqlite3`, sha256 `71580fc8…`, verificado
equivalente a la base. El paso productivo vuelve a hacer el suyo igual.

## Lo que falta

Cinco números, en `HUMAN_GATE.md`. Los que no se cuenten hoy siguen pendientes
sin bloquear nada.

---

## SAFE PAUSE — 2026-08-19

La misión queda pausada, no descartada. **Nada se escribió en producción**: sigue
con 3.554 artículos, 3.583 movimientos y el mismo `sha256` `25cd7d04…`, y los
cinco pendientes siguen abiertos.

**Por qué.** Se pidieron los cinco conteos. Llegó uno —Asunción— pero con el
marcador literal `[CANTIDAD REAL CONTADA]` en lugar del número, así que no se
aplicó nada: inventar esa cifra es exactamente lo que estas misiones existen para
evitar. Y antes de volver a pedirlo, aparecieron dos inventarios corregidos del
19 de agosto, posteriores a las planillas que usó la 008 y con columnas que
aquéllas no traían. Contar a mano contra una foto vieja sería trabajo que la
conciliación puede invalidar.

**Lo que quedó verificado y sigue sirviendo:**

- el camino parcial funciona: aplicar sólo una sucursal cierra ese pendiente y
  deja los otros abiertos, con 0 cierres y 0 movimientos. Nadie se cierra solo
- la herramienta, la planilla de conteo, el dry-run completo y el backup
  (`bc-caja-prerecuento-20260819-142306.sqlite3`, sha256 `71580fc8…`) siguen
  válidos

**Continúa en** `BC-OPTICA-CONCILIACION-INVENTARIO-CORREGIDO-V1-010`, que
reevalúa los cinco con los archivos nuevos. Uno de ellos ya se resuelve sin
contar: `2000056 Par de patillas` pasa a servicio por definición operativa del
negocio.
