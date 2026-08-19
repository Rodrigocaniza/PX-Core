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
