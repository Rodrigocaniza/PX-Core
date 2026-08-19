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
    4. Con `core.autocrlf=true` y sin `.gitattributes`, un checkout limpio reescribe todos los
    ficheros del paquete que hoy llevan LF y sus hashes dejan de coincidir; sólo se salvan los que
    ya traen CRLF en el worktree —`COMMISSION_RULES.md`, los tres `PROMPT_*.txt` y las dos
    herramientas de `tools/`— y el PNG, que es binario. **El recuento exacto vive en un solo sitio,
    `ARTIFACT_CONSISTENCY.md`, y se recalcula en cada generación que toque el paquete**: repetirlo
    aquí lo dejó desfasado en la 5, en la 6 y en la 7, y abrió `L4-g6` y `L4-g7`. El propio
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
25. **Una venta con fecha futura mal tipeada. CERRADO en la generación 6.** AUDITOR-004 O1 y
    QA-004 O4 lo describieron como una congelación de la publicación: la guarda usaba `MAX(period)`
    global. Esa forma quedó cerrada en la generación 5, que retiró la guarda. La generación 5 lo
    empeoró por otra vía —la fecha errónea fijaba ese mes para siempre, `AB2-g5`— y **la generación
    6 lo cierra por la raíz**: un cálculo provisional ya no fija nada, de modo que un tipeo que
    nadie aprueba deja el mes corregible. La forma que quedó abierta entonces —`AB1-g6`: un tipeo
    que **sí** se aprueba y después se anula— la cierra la generación 7 con el boundary de salida,
    y `AB1-g7` cierra en la 8 el caso en que una comisión legada del piloto lo inhibía. **Este
    hallazgo queda cerrado**, sujeto a los verdicts de la generación 8.
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
    exportado, con la marca `pinned` de si su tasa ya quedó fijada, y la política vigente al
    exportar viaja aparte en `current_policy`. Rotular un período con la tasa global declararía
    oficial ahí un porcentaje que en ese mes no rige. Cualquier consumidor del contrato 2 debe
    adaptarse; dentro del piloto no hay ninguno.
29. **La cabecera de la pantalla rotula la política del período en curso**, no la última publicada,
    e indica cuándo el período está fijado. Ningún importe cambia; sí cambia el texto que el
    operador lee. La desactualización de `VISUAL_EVIDENCE.md` que este hallazgo registraba **quedó
    corregida en la generación 6**: el documento y su captura se regeneraron. El rótulo real hoy es
    « · fijada al aprobarse o pagarse» o « · todavía sin tasa fijada: el período sigue siendo
    corregible»; la segunda redacción cambió en la generación 7, porque la anterior afirmaba que
    nadie había aprobado y eso es falso en una base con evidencia discrepante.
    Lo que sigue abierto es la prueba de interfaz: comprueba subcadenas, así que no habría detectado
    por sí sola el desfase.

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

## Safe Pause — reanudada

La misión quedó en `SAFE_PAUSED` en `998037f924cdeb0c88565cc4618a85f9a0c92477`, con Safe Pause
registrada en `e87be30f8cde4752644bd0a0250a1ab22846a422`. **Se reanudó en PC Casa**, no en la PC de
la Óptica: el estado canónico —branch, HEAD, lease, artifacts— manda sobre el host que el plan
anticipaba. El Mission Lease se readquirió antes de tocar una sola línea. Safe Closure sigue
`PENDING` hasta los tres verdicts de la generación 6.

## Generación 6 — qué se hizo

Remediación mínima de los cuatro bloqueantes abiertos, sin rediseñar el módulo y sin UI nueva más
allá del rótulo que el propio contrato exige.

**Código.**

- `comisiones.py`: `RATING_BOUNDARY_STATES` (`APROBADA`, `PAGADA`) y `PROVISIONAL_STATES`
  (`ELEGIBLE`, `CALCULADA`, `REVISADA`) explícitos, para que la frontera económica sea un
  predicado con nombre y no una condición repartida.
- `comisiones.py`: `_pin_rated_period`, invocado **sólo** desde `approve()` y `mark_paid()`, dentro
  de la misma transacción que registra el hecho económico: no hay ventana en la que uno exista sin
  el otro. `INSERT OR IGNORE` por período y asiento `COMMISSION_PERIOD_RATE_PINNED` únicamente
  cuando la fila es nueva.
- `comisiones.py`: `recalculate()` **ya no escribe** `commission_rated_periods`. Ésa es la línea que
  cierra `AB2-g5` por la raíz.
- `comisiones.py`: `_policy_disclaimer` propio para un período sin tasa en vigor (`QB2-g5`).
- `repository.py`: `_backfill_rated_periods` reescrito. Siembra sólo desde `APROBADA`/`PAGADA` con
  política canónica y venta no anulada; no desempata evidencia discrepante; no escribe una sola vez
  sobre `commission_entries`; asienta `COMMISSION_PERIOD_RATE_SEEDED` y
  `COMMISSION_PERIOD_RATE_SEED_SKIPPED`. Cierra `AB1-g5`.
- `repository.py`: `_audit_seed_once`, para que la auditoría de la migración no se repita en cada
  apertura de la base.
- `comisiones_ui.py`: la cabecera y el KPI rotulan la ausencia de tasa en vigor en vez de caer a la
  política global (`QB1-g5`), y distinguen una tasa ya fijada de una todavía provisional.

**Pruebas.** 24 dirigidas nuevas en `tests/gestion_central/test_comision_rate_boundary.py` y 2 de
interfaz. 23 casos de la generación 5 reescritos al contrato nuevo y 2 parametrizaciones retiradas
—`CALCULADA` y `REVISADA` dejaron de ser estados protegidos **a propósito**—. Regresión
**395/395**, suite del módulo **195**.

**Documentos.** Se corrigieron las dos afirmaciones que la generación 5 conservó demostradas falsas
a propósito: la de `MIGRATION.md` / `ARCHITECTURE_DELTA.md` sobre lo que la siembra fija, y la
lectura implícita de que la fecha errónea quedaba resuelta. `VISUAL_EVIDENCE.md` y su captura se
regeneraron (`L6-g5`).

**Lo que no se hizo, y por qué.** No se abrió el flujo de corrección explícita de un período ya
fijado: sigue sin existir y sigue siendo otra decisión, no un cambio de política. No se tocó
`comision_policy.py`: la aritmética `Decimal` y el único `HALF_UP` canónico siguen intactos desde la
generación 3.

## Generación 6 — resultado: INVALIDADA

| Runner | Verdict | Bloqueantes |
|---|---|---|
| Librarian | **FAIL** | `L1-g6` … `L5-g6`, documentales, **cerrados en este commit de registro** |
| QA | **PASS** | ninguno |
| Auditor | **FAIL** | `AB1-g6`, económico, **abierto** |

Lo que sí quedó cerrado y verificado por los tres: `AB1-g5`, `AB2-g5`, `QB1-g5` y `QB2-g5`. El
Auditor reprodujo los dos escenarios económicos exactos de la generación 5 y midió que los 400.000 Gs
de diferencia desaparecen en ambos.

### `AB1-g6` — el boundary de salida

La generación 6 movió el boundary de **entrada** de `CALCULADA` a `APROBADA`. No tocó el de
**salida**: la evidencia se crea con un hecho económico y **no se retira cuando ese hecho se
retira**. `commission_rated_periods` tiene dos `INSERT` y ningún `UPDATE` ni `DELETE` en todo el
sistema.

Cuatro rutas públicas independientes dejan el mes fijado con **cero hechos económicos vivos**:
revertir la aprobación, `void_sale`, `revert_payment` de un cobro rechazado, y `observe` + `revert`.
Ninguna es exótica: `revert_payment` es simplemente lo que pasa cuando un cheque rebota después de
aprobada la comisión. En ese momento no salió un guaraní, no hay nada que proteger, y el mes queda
inmovilizado para siempre. Daño medido: **9.900.000 Gs de sobrepago por cada venta de 10.000.000 Gs**
del mes, sin techo.

La justificación de la decisión de propietario —«un tipeo que será anulado nunca alcanza `APROBADA`
ni `PAGADA`, así que no puede fijar un mes»— **es falsa contra el código**: un tipeo que sí llega a
`APROBADA` y después se anula fija el mes igual de para siempre que en la generación 5.

## Generación 7 — qué se hizo

Cierra `AB1-g6` con la decisión de propietario: **el período permanece fijado mientras exista al
menos un hecho económico oficial vivo que lo justifique**. Si no queda ninguno, se suelta.

**El cambio de fondo es de representación.** La generación 5 guardaba el *estado* de la fijación
en `commission_rated_periods`, una fila por período. Un estado de una sola fila no puede expresar
que una fijación se retiró sin borrarla, y borrarla habría perdido el rastro. La generación 7 lo
convierte en un **libro append-only**, `commission_period_rate_events`, con dos eventos: `PINNED`
y `UNPINNED`. El estado vigente de un período es su último evento; nada se actualiza y nada se
borra; refijar es un evento más. La tabla vieja queda congelada, sin leer ni escribir, y sin
borrar.

**El boundary de salida está en un solo sitio.** `_reconcile_period_pin` se invoca desde
`_set_status`, que es por donde pasa **toda** transición de estado. Las cuatro rutas que el Auditor
enumeró —revertir la aprobación, `void_sale`, la reversa de un cobro rechazado y `observe` seguido
de `revert`— quedan cubiertas por construcción, no una por una, y cualquier ruta futura que mueva
un estado queda cubierta también. Escribir el libro es competencia de un único método,
`_record_period_rate_event`, con tres llamadores.

**Una `PAGADA` viva nunca suelta.** `_live_official_facts` cuenta `paid_at`, así que el dinero
consolidado sostiene su mes aunque después se observe la liquidación o se anule la venta: observar
no devuelve una transferencia.

**Migrar y operar ahora coinciden.** Ambos lados usan el mismo predicado, y el SQL de los dos se
arma desde `BOUNDARY_SQL_IN`, derivado de `RATING_BOUNDARY_STATES`, que se mudó a
`comision_policy.py` porque es donde viven las constantes que el repositorio y el cálculo comparten.
Que la constante existiera sin gobernar nada fue una observación del Librarian.

**Observaciones de la generación 6 atendidas.** La 1 del Auditor —una venta anulada de una base
legada llegaba al pago— con una guarda en `review`/`approve`/`mark_paid`. La 2 —`INSERT OR IGNORE`
tragaba violaciones `NOT NULL`— desaparece: el libro usa `INSERT` normal y la idempotencia sale de
consultar el último evento. La 1 de QA —el rótulo afirmaba que nadie había aprobado, falso en una
base legada discrepante— reescribiendo pantalla y export para describir la ausencia de fijación.
La 4 de QA se deja como está a propósito: el export usa punto decimal porque es contrato de datos,
la pantalla coma porque es texto en español.

**Lo que no se hizo.** No se abrió el flujo de corrección explícita de un período fijado **que sí
tiene** un hecho vivo detrás: sigue sin existir y sigue siendo otra decisión. `comision_policy.py`
sólo gana el boundary compartido: la aritmética `Decimal` y el único `HALF_UP` siguen intactos
desde la generación 3.

## Generación 7 — resultado: INVALIDADA

| Runner | Verdict | Bloqueantes |
|---|---|---|
| Librarian | **FAIL** | `L1-g7` … `L5-g7`; `L1-g7` es de código |
| QA | **PASS** | ninguno |
| Auditor | **FAIL** | `AB1-g7`, económico |

`AB1-g6` quedó **cerrado y verificado por los tres** en sus cuatro rutas: el Auditor midió los
29.700.000 Gs de sobrepago desapareciendo, y QA lo confirmó con su propia matriz temporal.

### `AB1-g7` — el predicado escrito dos veces

El boundary de salida estaba bien puesto. Lo que no estaba unificado era **qué cuenta como hecho
vivo**: la siembra exigía política canónica y la reconciliación no. `BOUNDARY_SQL_IN` había
unificado la lista de estados —la parte que ya coincidía— y dejó divergente la que decide.

La consecuencia es que **toda comisión ya pagada del piloto**, que la migración deja por diseño y
para siempre con `POLITICA_HISTORICA_PREVIA`, era invisible para sembrar y a la vez un hecho vivo
para retener. Su mes no podía soltarse jamás, y `AB1-g6` reaparecía completo por sus cuatro rutas,
con la misma cifra: 9.900.000 Gs de sobrepago por venta de 10.000.000 Gs.

## Generación 8 — qué se hizo

**No hizo falta una decisión de propietario, y conviene decir por qué.** El Auditor planteó dos
opciones —que la liquidación legada cuente como hecho vivo, o que no cuente— pero el módulo ya había
respondido en todas partes menos en esa línea: el reporte excluye `POLITICA_HISTORICA_PREVIA` de
`commission_amount` y la cuenta en `non_official_amount`, el desglose escribe «no es pagable con
este importe», y la migración nunca sembró desde ella. La regla del propietario dice «hecho
económico **oficial** vivo». `_live_official_facts` era el único sitio que no aplicaba el
calificativo: es un defecto contra el vocabulario del propio paquete, no una bifurcación.

**Código.**

- `comision_policy.LIVE_OFFICIAL_FACT_SQL` y `PERIOD_MATCH_SQL`: **un solo SQL** para los dos
  lados. No dos textos equivalentes —eso falló en la 6 y en la 7— sino uno.
- `CentralRepository.record_period_rate_event`: **un solo `INSERT`** sobre el libro en todo el
  código. Vive en el repositorio porque la migración también escribe y no puede importar
  `comisiones` sin ciclo; tenerlo en el servicio dejaba una segunda ruta, que era `L1-g7`.
- El `UNPINNED` nombra la liquidación que dejó de sostener el período (`entry_id`, `sale_id`).
- La migración reevalúa un período cuyo último evento es `UNPINNED` si hay evidencia viva.
- `decide()` y las guardas de la cadena de pago resuelven **dentro** de la transacción del
  llamador: `recalculate` converge en una pasada y no deja un rechazo intermedio sin explicación.
- `substr(period,1,7)` en los dos lados, y la última división en coma flotante del módulo retirada.

**Pruebas.** 13 dirigidas nuevas en `test_comision_legacy_facts.py`. Cuatro de ellas fallan contra
el predicado de la generación 7 y pasan contra el de la 8: se comprobó explícitamente, porque una
prueba que pasa en los dos sentidos no demuestra nada. Regresión **431/431**, módulo **231**.

**Observaciones de la generación 7 atendidas.** Del Auditor: 1 (`decide` fuera de la transacción),
2 (período por prefijo contra exacto), 4 (redacción del invariante 12), 6 (la última división
flotante) y 7 (`_reject_voided_sale` abría conexión propia). De QA: 2 (la migración no reevaluaba
un período suelto) y 5 (el `UNPINNED` no nombraba el hecho). Del Librarian: las cuatro
documentales, 3 a 6.

**Observaciones que quedan abiertas, y por qué.** La 3 del Auditor —evidencia discrepante deja
períodos sin pin— pierde casi todo su filo al cerrarse `AB1-g7`, y elegir por el propietario sigue
sin ser aceptable. La 5 —`recalculate` evalúa liquidaciones de ventas anuladas— es trabajo
desperdiciado, no dinero. La 1 de QA —export contradictorio en una base legada fuera de vigencia—
no la produce ninguna ruta pública. La 3 —`observe` por sí solo suelta— es correcta bajo la regla y
queda documentada. La 4 —punto decimal en el export, coma en pantalla— es deliberada.

## Generación 8 — resultado: INVALIDADA

| Runner | Verdict | Bloqueantes |
|---|---|---|
| Librarian | **FAIL** | `L1-g8`, `L2-g8` |
| QA | **PASS** | ninguno |
| Auditor | **FAIL** | `AB1-g8`, económico |

`AB1-g7` quedó cerrado **en la raíz** y verificado por los tres: sobre la base del piloto con una
comisión ya pagada, las cuatro rutas de `AB1-g6` dan 0 Gs de sobrepago.

### `AB1-g8` — la regla de decisión, escrita dos veces

La generación 8 unificó el **predicado de vitalidad** —qué cuenta como hecho vivo—. Lo que seguía
duplicado era la **regla de decisión**: qué tasa tiene el período. La siembra exigía coherencia y se
abstenía ante tasas distintas; la reconciliación no miraba la tasa en absoluto y retenía el pin con
cualquier hecho vivo.

La base que lo explota la produce la migración oficial **por diseño**: retirar las políticas por
vendedora y por local deja liquidaciones del mismo mes a tasas distintas. Ese mes nacía sin pin
teniendo hechos vivos, y el primer pin que recibía quedaba clavado a una tasa que ninguno de sus
hechos llevaba. 29.700.000 Gs en el escenario reproducido, sin ruta pública de corrección.

## Generación 9 — qué se hizo

**Decisión de propietario confirmada.** Una `PAGADA` viva conserva **la tasa económica real con la
que fue pagada**, aunque difiera del 1% vigente: si un mes tiene un pago vivo al 7%, queda fijado al
7%. Ese pago no se reinterpreta como 1%, su importe no se toca, y la política vigente no se fuerza
retroactivamente sobre hechos económicos anteriores. **El 1% es prospectivo**: rige los meses nuevos
o no consolidados, los que no tienen una tasa oficial histórica viva que preservar.

**Una sola función decide.** `comision_policy.resolve_period_rate` contesta «¿qué tasa tiene este
período?» a partir de sus hechos vivos, su estado económico oficial, la tasa de cada hecho y la
coherencia entre ellos. `CentralRepository.reconcile_period_rate` la aplica: fijar, soltar y refijar
dejan de ser tres operaciones con tres criterios y pasan a ser la diferencia entre lo que el libro
dice y lo que la regla dice. La invocan por igual `_set_status` —toda transición— y la apertura de
la base. No queda ningún texto equivalente que pueda separarse.

**Por qué importaba tanto.** `AB1-g6`, `AB1-g7` y `AB1-g8` son el mismo defecto tres veces: la misma
regla en dos sitios, y cada corrección unificando la mitad que ya coincidía. La 6 unificó el
boundary de entrada, la 7 la lista de estados, la 8 el predicado de vitalidad. La 9 extrae la
**decisión** entera, que es lo que quedaba.

**Pruebas.** 13 dirigidas nuevas en `test_comision_rate_coherence.py`, incluida la base con políticas
por alcance del Auditor. La que encierra el estado final de la generación 8 —libro al 100% con un
solo hecho vivo al 7%— se verificó contra la regla anterior: da 10000 y ahora da 700. Regresión
**444/444**, módulo **244**.

**Observaciones de la generación 8 atendidas.** Del Auditor: 1 (la tercera copia parcial del
predicado, que desaparece con `_pin_rated_period`), 2 (la siembra asentaba con otro nombre y sin
auditar) y 6 (la última división flotante). Del Librarian: las seis. De QA: 1 (un `PINNED` heredado
sin hecho vivo sobrevivía a la apertura) y 4 (el aviso pedía recalcular liquidaciones ya pagadas).

**Lo que queda abierto y por qué.** La 3 del Auditor —`decide()` resuelve el pin dentro de la
transacción pero el catálogo abre conexión propia— no es explotable: `BEGIN IMMEDIATE` serializa a
los escritores. La 4 y la 5 son trabajo desperdiciado, no dinero. La 2 de QA —dos pasadas de
`recalculate` cuando la reparación suelta el propio período— tampoco mueve dinero mal. La 3 de QA
—el KPI «Pagado» suma lo legado que «Comisión oficial» excluye— es defendible: el dinero salió.

## Generación 9 — resultado: INVALIDADA por el Librarian

| Runner | Verdict | Bloqueantes |
|---|---|---|
| Librarian | **FAIL** | `L1-g9`, `L2-g9`, `L3-g9` |
| QA | **PASS** | ninguno |
| Auditor | **PASS** | **ninguno — el primero de la misión** |

`AB1-g8` cerrado. El Auditor corrió 13.200 pasos de fuzz **desde bases migradas**, con el invariante
en tres direcciones tras cada paso y un detector que verificó antes de usar; cinco escenarios de
concurrencia incluida la refijación concurrente; y reprodujo `AB1-g8` y las cuatro rutas de
`AB1-g6` sobre base discrepante, todas con daño **0 Gs**. Ningún importe pagado cambió de valor en
ninguna de las 13.600 transiciones.

Los tres bloqueantes del Librarian son afirmaciones falsas, ninguna económica. El más serio es
`L3-g9`: el invariante 10 apoyaba su garantía «por construcción» en `_set_status` como único punto
de paso, y hay **tres `UPDATE` directos más** que escriben estado. La prueba de que no era cierto
estaba en el propio código: `recalculate` tenía que reconciliar por su cuenta.

## Generación 10 — qué se hizo

**`L3-g9`, por los dos lados.** Los cuatro sitios que escriben `commission_entries.status`
—`_set_status`, `recalculate`, `_apply_source_update` y la promoción a elegible— reconcilian ahora
su período, y una **prueba estructural** comprueba que ninguna función que escriba estado se olvide
de hacerlo. La garantía deja de ser una afirmación y pasa a estar sostenida por una guarda que falla
si alguien la rompe mañana.

**`L1-g9` y `L2-g9`.** La tabla de reglas de `MIGRATION.md` describía la siembra que ya no existe;
sus seis filas se reescribieron. `HANDOFF.md` citaba un rótulo retirado en la generación 7.

**Las observaciones estructurales del Auditor.** La lectura del libro estaba escrita tres veces
—dos con el mismo SQL copiado— y ahora es una sola, en el repositorio (O2). La clave del período se
normaliza también al leer el libro, así que no quedan períodos fantasma en la auditoría (O3). Un
conflicto nuevo del mismo mes sí se asienta, porque la huella incluye las tasas (O4). Un conflicto
provocado en caliente se asienta a nombre de quien lo provocó y no de la migración (O5). `recalculate`
y `list_entries` filtran el período con la clave normalizada (O7). Y de QA: el rechazo por política
desfasada nombra la tasa y no sólo la versión.

**Lo que queda abierto, y por qué.** La observación **O1 del Auditor** es la consecuencia de la
decisión de propietario de la generación 9, tomada y escrita: un mes con una `PAGADA` viva al 7%
cobra el 7% también a las ventas registradas después. Cuantificada: **600.000 Gs por venta de
10.000.000 Gs**. El Auditor la señala porque la justificación escrita es «no reescribir historia» y
el efecto observable es que la historia gobierna dinero futuro. No es un defecto del código: es la
regla funcionando. Queda anotada para que el propietario la confirme antes de producción.

Las observaciones 3 y 4 de QA —el código de política se sigue llamando `COMISION_GENERAL_1PCT`
cuando la tasa fijada es histórica, y el pin hereda el `scope` del hecho legado— son de vocabulario:
al admitir tasas distintas del 1%, el nombre del contrato se quedó corto. No mueven dinero y su
corrección toca el identificador canónico de la política, que es una decisión aparte.

## Siguiente paso propuesto

**Generación 10 publicada y pendiente de los tres verdicts independientes.** No se reutiliza ningún
verdict de las generaciones 1 a 9. Con 3×PASS: Artifact Consistency, Safe Closure y liberación del
lease.

Sólo después de la Safe Closure vuelve a la cola el cableado de `register_payment` y
`sync_review_sales` desde el producto (heredado 11), que sigue siendo lo único que impide que el
ciclo cobro → elegibilidad → 1% → aprobación → pago sea alcanzable sin el capturador sintético.
