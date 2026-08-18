# Handoff

Cadena: Librarian → QA → Auditor, en tres runners independientes sobre el mismo snapshot
inmutable. Estado de revisión: `INDEPENDENCE.md`. Evidencia por generación en `generation-N/`.

## Matriz de revisión

- Política canónica, aritmética `Decimal`/`HALF_UP` y estados de política → `modulos/gestion_central/comision_policy.py`
- Resolución, recálculo, versionado, guardas y export → `modulos/gestion_central/comisiones.py`
- Esquema, columnas de traza y migración → `modulos/gestion_central/repository.py`
- Encabezado, KPI, columnas y desglose → `modulos/gestion_central/comisiones_ui.py`
- Validación de dominio y migración → `tests/gestion_central/test_comisiones.py`
- Validación de interfaz y Full HD → `tests/gestion_central/test_comisiones_ui_interactions.py`
- Contrato del porcentaje → `COMMISSION_POLICY_1PCT.md`
- Reglas económicas ya canónicas → `artifacts/BC-GESTION-CENTRAL-COMISIONES-001/COMMISSION_RULES.md`
- Arquitectura base → `artifacts/BC-GESTION-CENTRAL-COMISIONES-001/ARCHITECTURE.md`

## Hallazgos no bloqueantes abiertos

Los **treinta y siete** del handoff de BC-GESTION-CENTRAL-COMISIONES-001 siguen abiertos y sin
corregir: esta misión no los tocó por estar fuera de su alcance. Se consultan en
`artifacts/BC-GESTION-CENTRAL-COMISIONES-001/HANDOFF.md`, y `WORKFLOW.json` de esa misión registra
los mismos treinta y siete. Cuatro de ellos cambian de estado:

1. **El signo «×» delante de un importe que ya es el producto** (heredado 8, parcial). Cerrado: la
   línea de comisión del desglose ahora usa «=». El badge de piloto duplicado entre shell y panel
   sigue abierto.
2. **Ni `register_payment` ni `sync_review_sales` tienen llamador productivo** (heredado 11). Sigue
   abierto y es ahora el bloqueante funcional principal: con la política aprobada, el cableado del
   ciclo de cobros es lo único que separa a la bandeja de ser operable desde el producto.
3. **`assert "float(" not in source` es más débil que la propiedad declarada** (heredado 7). Sigue
   abierto y ahora importa más, porque el cálculo pasó a `Decimal`: la aserción no distingue un
   `Decimal` bien usado de uno mal usado.
4. **`COMMISSION_RULES.md` y `ARCHITECTURE.md` generalizan de más** (heredado 16). Sigue abierto;
   esta misión no reescribió esos documentos.

Nuevos, abiertos y **no** corregidos:

5. **La vigencia es de granularidad mensual aunque el parámetro sea una fecha completa.**
   `is_in_effect` compara `período >= effective_from[:7]`, así que una vigencia fijada al
   `2026-08-20` rige igual desde el `2026-08-01`. Está documentado, es coherente con la
   granularidad mensual del módulo, y la vigencia canónica es día 1; pero la API acepta un día que
   no se respeta.
6. **Una liquidación con importe no oficial ya pagada no tiene corrección.** `recalculate` no la
   alcanza —correctamente, porque el dinero salió— y `revert` está bloqueado. Es el mismo callejón
   que el hallazgo heredado 4 para la `OBSERVADA` pagada. Las **no** pagadas sí tienen salida.
7. **Una `OBSERVADA` legada conserva su importe no oficial indefinidamente.** No es pagable y los
   agregados la informan aparte, pero `recalculate` no la alcanza y la única salida pública,
   `revert`, no crea liquidación de reemplazo. Es el complemento del hallazgo heredado 4.
8. **`POLICY_STATUSES` se define y no se usa.** Es documentación ejecutable del conjunto de
   estados, pero ninguna guarda lo valida contra lo que se escribe en `policy_status`.
9. **El retiro de políticas por alcance es una eliminación de filas.** Queda auditada con su
   `rate_bp` previo en `central_audit`, que es suficiente para reconstruirla, pero la fila en sí
   no se conserva en `commission_policy_versions`.
10. **`set_general_rate` no ofrece una vista previa del impacto**, ni exige un permiso distinto del
    de pagar: el mismo principal publica el porcentaje y cobra con él. Con una sola política
    general y auditoría de cada publicación el riesgo es acotado, pero no hay separación de
    funciones ni segunda barrera para un 0% o un 100%.
11. **`cancelled_date` viaja siempre nulo en el contrato v2.** `ENTRY_EXPORT_FIELDS` lo declara,
    pero `list_entries` expone la fecha de la venta como `sale_cancelled_date`, así que el campo
    sale vacío en el 100% de las filas. Viene de la misión anterior y el contrato v2 lo arrastró.
12. **El chequeo de consistencia trata la generación en curso como revisada.** Calcula
    `reviewed = max(generation)` sin mirar `status`, de modo que su regla de «no anticipar la
    revisión en curso» queda inerte justo para la generación que se está revisando.
13. **Una corrección de origen sobre una `OBSERVADA` con importe no oficial lo borra sin
    registrarlo.** `_apply_source_update` no la considera un estado revisado, así que entra por la
    rama de recálculo y anula `rate_bp` y `commission_amount`; el asiento `SOURCE_UPDATED` guarda
    la base nueva pero no el importe reemplazado, a diferencia de `COMMISSION_POLICY_REPAIRED`.
14. **La nota de una `SIN_POLITICA_APLICADA` ya pagada invita a recalcular** aunque `recalculate`
    jamás la alcanzará. La rama `POLITICA_HISTORICA_PREVIA` sí distingue si movió dinero; esta no.

Aportados por las observaciones no bloqueantes de la generación 3, abiertos y **no** corregidos:

15. **Una vigencia que no es día 1 de mes se publica como una fecha y se aplica desde el día 1.**
    QA-003 O1: `set_general_rate` acepta cualquier `effective_from` válido, pero `is_in_effect`
    compara prefijos `AAAA-MM`. Publicar «3% desde 2026-08-20» re-tarifa a 30.000 una venta del 5 de
    agosto ya aprobada y le quita el aval. Agrava el hallazgo 5, que sólo describía la granularidad.
16. **El resumen por vendedora no expone la columna de importe no oficial.** QA-003 O3: `report()`
    calcula `non_official_amount` por vendedora pero `SUMMARY_COLUMNS` no lo muestra, así que el
    dato queda sólo en el banner global.
17. **`mark_paid` no lleva la guarda `_reject_paid`.** AUDITOR-003 O2: confía sólo en la máquina de
    estados. No hay ruta pública que lo explote —se verificó—, pero es una asimetría de defensa en
    profundidad frente al blindaje explícito que sí tiene `recalculate`.
18. **`set_general_rate` quedaría sin guarda de retroceso si `commission_policy_versions` estuviese
    vacía.** AUDITOR-003 O3: `latest` se deriva sólo de esa tabla. No se encontró ruta pública que
    produzca ese estado; queda como endurecimiento.
19. **`recalculate` abre una conexión por entrada dentro del `BEGIN IMMEDIATE`.** AUDITOR-003 O7:
    correcto en WAL y sin bloqueos en las pruebas de concurrencia, pero escala mal por período.
    Rendimiento, no corrección.
20. **El checker de consistencia no inspecciona el ZIP ni cuenta las observaciones de los
    verdicts.** LIBRARIAN-003 obs 1: es justo donde sobrevivieron L1 y L2, y
    `ARTIFACT_CONSISTENCY.md` presenta su veredicto como respaldo de un bloque de afirmaciones más
    amplio que su alcance real.
21. **El párrafo de cabecera de `INDEPENDENCE.md` citaba sólo el snapshot de la generación 1.**
    LIBRARIAN-003 obs 3. Corregido en el commit de registro de la generación 3; queda anotado para
    que el Librarian lo reverifique.
22. **`MIGRATION.md` paso 1 atribuye `commission_policy_versions` a `_add_missing_columns`.**
    LIBRARIAN-003 obs 5: la crea el `CREATE TABLE IF NOT EXISTS` de `migrate()`. El efecto descrito
    es correcto; la atribución no.

Detectado en la generación 4 sobre el propio paquete:

23. **`MANIFEST.sha256` sólo verifica en el worktree donde se genera.** Detectado en la generación
    4. Con `core.autocrlf=true` y sin `.gitattributes`, un checkout limpio devuelve 20 de los 40
    ficheros con CRLF —18 de los 26 `.md` y dos `.py`— y sus hashes dejan de
    coincidir; el propio
    manifest llega con CRLF y `sha256sum -c` no puede analizarlo. Es heredado de cómo se construyó
    el paquete desde la generación 1, no lo introduce esta generación. El ZIP sí conserva los bytes
    exactos. Corrección propuesta, fuera del alcance de B1/B2: fijar `-text` para el paquete con un
    `.gitattributes` acotado, y recalcular el manifest sobre esos bytes.

Aportados por las observaciones no bloqueantes de la generación 4, abiertos y **no**
corregidos:

24. **En la rama de reparación, `replaced` se asienta con nulos.** QA-004 O3: cuando la liquidación
    no tenía importe ni porcentaje que retirar, el bloque se escribe igual con `rate_bp: None` y
    `commission_amount: None`. Registra un dato cierto, pero es ruido: un lector del historial ve un
    `replaced` donde no hubo retiro de valor.
25. **Una venta con fecha futura mal tipeada.** AUDITOR-004 O1 y QA-004 O4 lo describieron como una
    congelación de la publicación: la guarda usaba `MAX(period)` global. **Esa forma quedó cerrada en
    la generación 5**, que retiró la guarda; ya no existe ningún `MAX(period)` en el código y la
    publicación no se congela. Pero el problema de fondo **sigue abierto y empeoró**: ahora la fecha
    errónea fija ese mes para siempre y lo hace pagar mal en silencio. Está registrado como el
    bloqueante económico `AB2-g5`.
26. **Observar una liquidación pagada retira su importe del KPI `paid_amount`.** AUDITOR-004 O2:
    `report()` lo calcula sobre `status == "PAGADA"`, de modo que dinero que efectivamente salió deja
    de verse en el reporte del período. Es además lo que vuelve invisible en pantalla la fuga B1-g4.
27. **`SUMMARY.md` y `WORKFLOW.json` declaran de dos formas la comisión de la venta con saldo.**
    LIBRARIAN-004 obs 6: la tabla dice «0 (no pagable)» y `verified_examples` dice `null`. El código
    escribe `None` y el KPI agrega 0, así que ninguna es falsa; el mismo caso verificado se declara
    dos veces distinto. Abierta desde la generación 1.

## Generación 4 — qué se hizo

Los dos bloqueantes económicos del Auditor, y **sólo** ellos.

- **B1, cerrado por decisión del propietario: opción (a), endurecer la guarda.** La regla canónica
  queda: una tasa publicada gobierna hacia adelante; un período ya liquidado no se re-tarifa por
  `set_general_rate`; no se modifica retroactivamente una liquidación calculada, revisada, aprobada
  o pagada. `set_general_rate` rechaza ahora toda vigencia cuyo mes no sea posterior al último
  período con liquidaciones en `CALCULADA`, `REVISADA`, `APROBADA` o `PAGADA` —lo que incluye la
  vigencia *igual*, que era la puerta abierta—. La guarda va **después** del corto-circuito de
  idempotencia, para que republicar lo idéntico siga sin crear versión.
- **B2, cerrado.** `recalculate` escribe `replaced` en toda rama que anule o reemplace un importe o
  un porcentaje previo, no sólo al reparar una `REVISADA` o una `APROBADA`.
  `COMMISSION_POLICY_1PCT.md` deja de prometer reparación donde el período es anterior a la
  vigencia, y dice en su lugar lo que sí está garantizado: que el importe retirado queda asentado.

**Fuera de alcance, por decisión explícita:** el flujo separado de corrección/ajuste auditado para
una tasa mal publicada sobre un período ya liquidado. No se implementa en esta generación. Hasta
que exista, un período liquidado con una tasa equivocada no tiene corrección por ruta pública, y un
importe heredado de un período anterior a la vigencia tampoco: ambos quedan asentados, no
recuperables.

Aportados por la generación 5, abiertos y **no** corregidos:

28. **El export sube a `contract_version: 3`.** El bloque `policy` pasa a ser el del período
    exportado, con la marca `pinned` de si quedó fijado al tarifarse, y la política vigente al
    exportar viaja aparte en `current_policy`. Rotular un período con la tasa global declararía
    oficial ahí un porcentaje que en ese mes no rige. Cualquier consumidor del contrato 2 debe
    adaptarse; dentro del piloto no hay ninguno.
29. **La cabecera de la pantalla rotula la política del período en curso**, no la última publicada,
    e indica cuándo el período está fijado. Ningún importe cambia; sí cambia el texto que el
    operador lee. **`VISUAL_EVIDENCE.md` quedó desactualizado**: el capturador tarifa el período, de
    modo que la cabecera real ahora incluye « · fijada al tarifarse» y la captura de la generación 3
    ya no coincide. La prueba de interfaz sólo comprueba subcadenas y no lo detecta. Debe
    regenerarse en la generación 6.

## Generación 4 — resultado: INVALIDADA

Librarian **PASS**, QA **PASS**, Auditor **FAIL**. Los tres confirmaron que los cuatro bloqueantes
de la generación 3 están cerrados y que los diez invariantes económicos pasan; la guarda nueva no
introdujo regresión. Pero el Auditor encontró que **ninguno de los dos cierres era suficiente**:

- **B1-g4 (abierto).** La guarda decide si un período «ya fue liquidado» mirando el **estado
  actual** de las entradas. `observe()` sobre una liquidación pagada —operación pública, permitida y
  no destructiva—, `void_sale()` sobre una venta ya cobrada, `revert()` o una corrección cosmética
  de origen sacan la entrada de `SETTLED_STATES` y devuelven la fuga entera: **400.000 Gs pagados
  por un período donde el 1% eran 40.000**, o el mes completo anulado a cero. Cierre propuesto:
  apoyar la guarda en evidencia de tarifación (`paid_at`, `rate_bp` o el historial) en lugar del
  estado actual.
- **B2-g4 (abierto).** La garantía sólo se cumple dentro de `recalculate`. `_apply_source_update`
  anula `rate_bp` y `commission_amount` y escribe `SOURCE_UPDATED` sin `replaced`: un importe
  heredado de una base migrada, que no tiene asiento previo, desaparece por una corrección de sobre.
  Cierre propuesto: replicar ahí el bloque `replaced`.

En consecuencia, el invariante 5 y el invariante 7 de `ARCHITECTURE_DELTA.md` —y sus ecos en
`COMMISSION_POLICY_1PCT.md` y `SUMMARY.md`— **están demostrados falsos y se conservan sin corregir**
hasta la generación 5, para que se arreglen con la evidencia a la vista.

## Generación 5 — qué se hizo

Los dos bloqueantes económicos, y **sólo** ellos, por decisión de propietario: no seguir parcheando
predicados sobre el estado actual, sino adoptar una invariante basada en evidencia durable.

- **Representación elegida: `commission_rated_periods`.** Una fila por período, clave primaria
  `period`, escrita con `INSERT OR IGNORE` la primera vez que se tarifa y nunca actualizada ni
  borrada. Guarda la tasa y la traza con la que ese período quedó fijado. Es la representación
  mínima que responde «este período ya tuvo una tasa aplicada» sin inferirlo del estado de ninguna
  liquidación. La migración la siembra desde las liquidaciones que ya llevan `rate_bp` **con
  política canónica**; un importe heredado no oficial no fija nada, porque fijarlo lo volvería
  incorregible.
- **B1-g4, cerrado.** `decide()` resuelve el período contra esa fila antes que contra el catálogo,
  así que `observe`, `revert`, `void_sale` y la corrección de origen ya no lo devuelven al catálogo.
  `set_general_rate` **deja de bloquear**: publicar siempre es posible y no reescribe lo tarifado.
- **B2-g4, cerrado.** `_apply_source_update` escribe el mismo bloque `replaced` que `recalculate`
  cuando la corrección retira una tasa o un importe previo.

**Por qué fijar y no bloquear.** Bloquear la publicación no puede satisfacer a la vez los dos
requisitos del encargo. Como la vigencia se resuelve por mes, una vigencia para `2027-01` gobierna
también a `2036-08`: proteger todo período tarifado obliga a bloquear `2027`, que es exactamente la
congelación que había que evitar. Fijar el período a la tasa con la que fue tarifado satisface los
dos: nada se re-tarifa y nada se congela.

**Fuera de alcance, por decisión explícita:** el flujo separado de corrección retroactiva. Hasta que
exista, la tasa de un período ya tarifado no se corrige por ruta pública.

## Decisión de propietario para la generación 6

**La tasa del período NO se fija en el primer cálculo.** Queda fijada únicamente cuando existe un
**hecho económico oficial**.

- **Boundary: `APROBADA` o `PAGADA`.**
- Los estados provisionales anteriores —`ELEGIBLE`, `CALCULADA`, `REVISADA`— siguen siendo
  **corregibles** y no fijan nada.
- **La migración no puede sembrar** desde una venta anulada, ni desde un primer cálculo arbitrario,
  ni desde evidencia ambigua.
- **Una migración nunca puede modificar silenciosamente dinero aprobado o pagado**, ni retirar una
  aprobación o un pago.

Cierra los dos bloqueantes económicos por la raíz: un tipeo que será anulado nunca alcanza
`APROBADA` ni `PAGADA`, de modo que no puede fijar un mes (`AB2-g5`); y la siembra deja de depender
del orden de creación para depender del mismo hecho económico (`AB1-g5`).

## Safe Pause

La misión queda en `SAFE_PAUSED` en el commit `998037f924cdeb0c88565cc4618a85f9a0c92477`, con la
branch publicada y sincronizada, el árbol limpio y el Mission Lease **liberado** para que otro host
lo adquiera. Safe Closure sigue `PENDING`: pausar no es cerrar. El resumen de Auto-Resume está en
`SAFE_PAUSE.md`, y el estado canónico manda sobre él.

## Siguiente paso propuesto

**Generación 5 en revisión: cerrar B1-g4 y B2-g4.** B1-g4 requiere decisión de propietario sobre en qué debe
apoyarse la guarda y con qué alcance temporal, porque la corrección obvia —proteger todo período
que alguna vez tuvo un porcentaje aplicado— congela ese mes de forma permanente, y se cruza con el
hallazgo 25. B2-g4 no tiene bifurcación.

Sólo después de la Safe Closure vuelve a la cola el cableado de `register_payment` y
`sync_review_sales` desde el producto (heredado 11), que sigue siendo lo único que impide que el
ciclo cobro → elegibilidad → 1% → aprobación → pago sea alcanzable sin el capturador sintético.
