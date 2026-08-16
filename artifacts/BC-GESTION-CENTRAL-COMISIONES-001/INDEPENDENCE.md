# Independencia de revisores

Autorizada expresamente por el propietario del repositorio. Cada generación se revisó en tres
subagentes separados, con identidad de rol exclusiva, contexto propio, prompt específico por rol,
evaluación concurrente sobre el mismo snapshot inmutable y **sin compartir razonamiento ni
conclusiones**. Ninguno conoció el verdict de los otros antes de emitir el propio.

## Estado de este snapshot

**Generación 10. Pendiente de revisión independiente.** Los verdicts de generación 10 no existen
todavía; cuando se emitan quedarán en un directorio propio. Ningún documento de este paquete debe
leerse como si esa revisión ya hubiera ocurrido.

## Generación 1 — snapshot `c24b4f19c66dc685d1679ed266eb887f2dbfe773`

| Runner | Rol | Verdict |
|---|---|---|
| `LIBRARIAN-IND-COMISIONES-001` | LIBRARIAN | PASS |
| `QA-IND-COMISIONES-001` | QA | **FAIL** — Q1 |
| `AUDITOR-IND-COMISIONES-001` | AUDITOR | **FAIL** — A1, A2, A3 |

Invalidada. Evidencia íntegra en `generation-1/`.

- **Q1** — `_month()` no validaba la fecha; `"2099-4-10"` producía el período `"2099-4-"` y la
  comisión desaparecía de todos los reportes sin error. Corregido con `date.fromisoformat`.
- **A1/A2** — `observe()` + `revert()` llevaban una liquidación `PAGADA` a `REVERTIDA`, liberando
  el índice de unicidad y habilitando doble pago. Corregido con el invariante `_was_paid`.
- **A3** — afirmaciones de artifacts no respaldadas por el código.

## Generación 2 — snapshot `5ba11bdbdbaaa826f16510fb07d08ffdbce17097`

| Runner | Rol | Verdict |
|---|---|---|
| `LIBRARIAN-IND-COMISIONES-002` | LIBRARIAN | **FAIL** — B1, B2, B3 |
| `QA-IND-COMISIONES-002` | QA | **FAIL** — base congelada en REVISADA |
| `AUDITOR-IND-COMISIONES-002` | AUDITOR | **FAIL** — B1, B2 |

Invalidada. Evidencia íntegra en `generation-2/`.

Los tres confirmaron que **Q1 y A1/A2 quedaron efectivamente cerrados** y que la corrección no
introdujo regresiones. Los FAIL fueron por defectos distintos:

- **Bloqueante financiero nuevo (QA)** — una corrección de origen sobre una liquidación en estado
  `REVISADA` reescribía el total sin recalcular la base ni el descuento; como `REVISADA` no es
  recalculable y va directo a `APROBADA → PAGADA`, se liquidaban comisiones incorrectas en ambos
  sentidos y el 5% del convenio podía omitirse por completo. Defecto **preexistente** de la
  generación 1 que su QA no había encontrado. Corregido con `REVIEWED_STATES`: toda corrección de
  origen sobre algo ya revisado produce `OBSERVADA`, y antes de la revisión se recalcula la base
  completa, nunca sólo el total.
- **Bloqueantes documentales (Librarian y Auditor)** — `INDEPENDENCE.md`, `HANDOFF.md` y
  `SUMMARY.md` describían en pasado una revisión de generación 2 que aún no había ocurrido y
  remitían a un `generation-2/` inexistente; y el ZIP transportaba un `ARTIFACT_CONSISTENCY.md`
  obsoleto de la generación 1 que se auto-certificaba «PASS» con cifras de la generación
  invalidada, en un archivo excluido del manifest y por tanto invisible a la verificación de
  integridad. Ambos eran errores de la ejecución implementadora, no del producto. Corregidos:
  el paquete se documenta antes de empaquetarse, el manifest cubre ahora
  `ARTIFACT_CONSISTENCY.md`, y este documento no describe ninguna revisión no ocurrida.

## Generación 3 — snapshot `4c4cf54215fd9e080b5793931524bf1e3e1cda61`

| Runner | Rol | Verdict |
|---|---|---|
| `LIBRARIAN-IND-COMISIONES-003` | LIBRARIAN | PASS |
| `QA-IND-COMISIONES-003` | QA | **FAIL** — dos bloqueantes en el libro de cobros |
| `AUDITOR-IND-COMISIONES-003` | AUDITOR | PASS |

Invalidada. Evidencia íntegra en `generation-3/`.

Librarian y Auditor confirmaron cerrados los tres bloqueantes financieros anteriores y los dos
documentales. El Auditor verificó por ejecución 8 rutas del invariante del dinero pagado y la
imposibilidad de doble pago. El QA encontró dos defectos nuevos en el libro de cobros:

- **Recobro tras reversión rechazado en silencio.** La clave de idempotencia de `register_payment`
  se derivaba del contenido y el chequeo no excluía los cobros ya reversados. Tras una reversión
  motivada, volver a cargar el mismo recibo real devolvía `(None, False)` sin excepción ni asiento:
  la venta quedaba con saldo fantasma y la vendedora nunca cobraba su comisión (subpago del 100%).
- **Dos cobros parciales legítimos idénticos se colapsaban en uno**, dejando un saldo fantasma.

Corregidos haciendo la idempotencia explícita y del llamador, separando la identidad interna del
cobro (`idempotency_key`) de la clave del llamador (`client_key`), y excluyendo los cobros
reversados del chequeo de duplicados.

## Generación 4 — snapshot `88a3f74e0d507f20917ef5d650dd92a3e56e8202`

| Runner | Rol | Verdict |
|---|---|---|
| `LIBRARIAN-IND-COMISIONES-004` | LIBRARIAN | PASS |
| `QA-IND-COMISIONES-004` | QA | **FAIL** — dos defectos en la conciliación de origen |
| `AUDITOR-IND-COMISIONES-004` | AUDITOR | **FAIL** — contrato afirmado no cumplido y `paid_amount` negativo |

Invalidada. Evidencia íntegra en `generation-4/`.

Los tres confirmaron cerrados los cinco bloqueantes anteriores; QA verificó además que el contrato
nuevo de idempotencia no abrió ninguna vía de doble conteo, y ambos confirmaron que la migración
aditiva no pierde datos. Los cuatro defectos nuevos tenían **una sola raíz**: `paid_amount` se
asignaba por fuera del libro append-only.

- **Cobro posterior del origen descartado en silencio.** `_apply_source_update` ignoraba
  `initial_paid`: una venta ingerida con saldo y cobrada después quedaba atrapada para siempre en
  `PENDIENTE_SALDO`, informando éxito. Subpago del 100% por la vía de ingesta documentada.
- **`paid_amount` negativo** por corrección a convenio sin guarda, con el reporte informando como
  cobrado un dinero ya revertido.
- **`revert_payment` sin guarda de tipo**, dejando dinero declarado como cobrado sin asiento.
- **El contrato de idempotencia no cumplía lo que `ARCHITECTURE.md` afirmaba**: el chequeo de saldo
  precedía al de reintento, y el caso roto era el más frecuente.

Corregidos de raíz en la generación 5: el libro es ahora la única fuente de verdad de
`paid_amount`, el convenio liquida mediante una fila `CONVENIO` del propio libro, toda diferencia
declarada por el origen se asienta como una fila más, y el reintento se reconoce antes de validar
importes.

## Generación 5 — snapshot `0f735f714aab454f714a9af45beb7bda13c301cc`

| Runner | Rol | Verdict |
|---|---|---|
| `LIBRARIAN-IND-COMISIONES-005` | LIBRARIAN | **FAIL** — hallazgo declarado abierto que el snapshot ya cerraba |
| `QA-IND-COMISIONES-005` | QA | **FAIL** — tres defectos con una raíz |
| `AUDITOR-IND-COMISIONES-005` | AUDITOR | **FAIL** — comisión sin cobro y documento contradicho |

Invalidada. Evidencia íntegra en `generation-5/`.

Los tres confirmaron cerrados los **nueve** bloqueantes financieros anteriores, y QA verificó el
invariante del libro en 360 puntos de control sin un solo desvío. Pero la corrección estructural de
la generación 5 **introdujo un defecto propio**: la fila `CONVENIO` del libro sobrevivía a la
conversión de la venta a común. QA y Auditor lo encontraron de forma independiente.

- Una venta convertida de convenio a común quedaba liquidada con dinero jamás cobrado, y podía
  llegar a `PAGADA` con comisión sobre cero cobros reales. El asiento era irreversible y el cobro
  real posterior se rechazaba: la venta quedaba permanentemente incobrable.
- Tras una reversa rutinaria, el residuo producía 400.000 Gs. de subfacturación al cliente.
- El KPI de portada «Cobros parciales» informaba como cobrado dinero ya revertido.

Corregidos en la generación 6 sin inventar ninguna regla: cuando la venta deja de ser convenio, la
liquidación por convenio **se revierte en el libro**, que es exactamente lo que `COMMISSION_RULES.md`
ya documentaba; y el KPI excluye los cobros revertidos.

## Generación 6 — snapshot `aed7bb2e4b370aeaa884008efab31dec16a965b2`

| Runner | Rol | Verdict |
|---|---|---|
| `LIBRARIAN-IND-COMISIONES-006` | LIBRARIAN | PASS |
| `QA-IND-COMISIONES-006` | QA | **FAIL** — el convenio no podía corregirse a la baja |
| `AUDITOR-IND-COMISIONES-006` | AUDITOR | PASS |

Invalidada. Evidencia íntegra en `generation-6/`.

Librarian y Auditor dieron PASS: el backlog volvió a ser veraz y los doce bloqueantes financieros
anteriores quedaron cerrados, con el invariante del libro resistiendo 7.184 controles de QA y 120
secuencias de fuzz del Auditor sin un solo desvío. El QA encontró un defecto acotado: como la
liquidación por convenio sólo se revertía cuando la venta *dejaba* de ser convenio, corregir a la
baja el total de un convenio se rechazaba para siempre con un mensaje que invocaba un cobro
inexistente, dejando 95.000 Gs. de base sobrevaluada por venta afectada. Agravante: la excepción no
capturada **truncaba el lote de sincronización** y salteaba en silencio las filas posteriores.

Corregido en la generación 7: toda corrección sobre un convenio re-expresa su liquidación —se
revierte la anterior y se asienta la nueva por el total corregido—, y `sync_review_sales` cuenta la
fila rechazada en `rejected` y continúa con el resto del lote.

## Generación 7 — snapshot `cfc43718d85fdbb260f0f6d2663eb025991643eb`

| Runner | Rol | Verdict |
|---|---|---|
| `LIBRARIAN-IND-COMISIONES-007` | LIBRARIAN | **FAIL** — cuatro inconsistencias del paquete |
| `QA-IND-COMISIONES-007` | QA | **FAIL** — la guarda del lote no cubría el parseo |
| `AUDITOR-IND-COMISIONES-007` | AUDITOR | PASS, sin bloqueantes |

Invalidada. Evidencia íntegra en `generation-7/`.

El Auditor dio PASS sin bloqueantes tras 134 comprobaciones adversariales propias, y QA sometió el
libro a 2.240 pasos de fuzz con trece invariantes duros sin encontrar una grieta: **el núcleo
económico quedó verificado de forma exhaustiva por dos revisores independientes**.

- **QA** — la corrección de la generación 7 dejó el parseo y la construcción de la fila fuera del
  `try`, de modo que un `ValueError` nacido ahí seguía truncando el lote y borrando en silencio
  ventas aplicables. Lo reprodujo con el `ReviewService` real. Corregido cubriendo todo el cuerpo
  del bucle, sin degradar `AccessDenied`, que debe seguir cortando la sincronización.
- **Librarian** — cuatro inconsistencias del propio paquete: un hallazgo declarado abierto que el
  código ya cerraba, los backlogs de `HANDOFF.md` y `WORKFLOW.json` sin coincidir pese a una
  autocertificación en contrario, una contradicción numérica en el conteo de bloqueantes, y una
  referencia que omitía una generación ya revisada. Todas corregidas.

## Generación 8 — snapshot `c4f6ee64717ca43becc5986985040ff57d6ee9f2`

| Runner | Rol | Verdict |
|---|---|---|
| `LIBRARIAN-IND-COMISIONES-008` | LIBRARIAN | **FAIL** — un ítem de backlog que el snapshot ya cerraba |
| `QA-IND-COMISIONES-008` | QA | **PASS** |
| `AUDITOR-IND-COMISIONES-008` | AUDITOR | **PASS** |

Invalidada. Evidencia íntegra en `generation-8/`.

**Los dos revisores técnicos emitieron PASS.** QA cerró los quince bloqueantes financieros
históricos con escenarios propios, reprodujo el hueco del parseo sobre el `ReviewService` real y
corrió 1.920 pasos de fuzz con trece invariantes duros sin una grieta en el dinero. El Auditor
atacó por ejecución las tres únicas rutas a `REVERTIDA` con liquidaciones pagadas, verificó la
imposibilidad de doble pago en la API y en el motor, y confirmó la migración aditiva sobre el
esquema anterior.

El único bloqueante fue documental: el ítem 17 del backlog declaraba que `ARCHITECTURE.md` no
documentaba `_reverse_agreement_settlement`, cuando el propio commit de la generación 8 había
añadido esa documentación. El Auditor lo señaló de forma independiente como observación. Retirado
en la generación 9, junto con la incorporación al backlog de todas las observaciones de ambos
revisores.

## Generación 9 — snapshot `114aee84745aa82293509f4d76be3c0bac381827`

| Runner | Rol | Verdict |
|---|---|---|
| `LIBRARIAN-IND-COMISIONES-009` | LIBRARIAN | **FAIL** — dos inconsistencias documentales |
| `QA-IND-COMISIONES-009` | QA | **PASS** |
| `AUDITOR-IND-COMISIONES-009` | AUDITOR | **PASS** |

Invalidada. Evidencia íntegra en `generation-9/`.

**Segunda generación consecutiva con QA y Auditor en PASS.** QA demostró que el cambio era inerte
comparando los AST de `comisiones.py` antes y después —idénticos— y acumuló unas 132.000 aserciones
propias con 8.800 pasos de fuzz en cinco semillas, sin una sola falla. El Auditor atacó seis rutas a
`REVERTIDA` y corrió 600 pasos de fuzz con siete invariantes duros, sin violaciones, y declaró: «no
encontré una sola afirmación falsa contra el código». El Librarian confirmó además, por primera vez,
que **el backlog es veraz: los treinta ítems contrastados uno por uno contra el código, con cita de
línea, y los treinta abiertos**.

Sus dos bloqueantes fueron de bookkeeping documental y ambos reincidencias: `HANDOFF.md` seguía
citando el rango de generaciones hasta la 7 cuando la 8 ya estaba revisada, e `INDEPENDENCE.md` se
contradecía a sí mismo en el conteo de bloqueantes financieros. Corregidos en la generación 10, y
—para cortar la reincidencia de raíz— se añadió `tools/check_mission_package_consistency.py`, que
verifica rangos, conteos únicos, backlogs idénticos, ausencia de anticipación de la revisión en
curso y code spans balanceados, y que se ejecuta antes de publicar cada snapshot.

## Valor demostrado de la independencia

Quince defectos financieros reales y diez de veracidad documental fueron detectados por revisores
independientes después de que la autorrevisión los declarara correctos, y con la regresión completa
en verde en todas las generaciones. Tres de ellos fueron **introducidos por una corrección
anterior**, lo que es en sí mismo un argumento a favor de revisar cada generación desde cero. Habrían movido dinero mal: comisión perdida por período
corrupto, doble pago habilitado, comisión liquidada sobre una base congelada, comisión nunca
generada tras una reversión, comisión atrapada para siempre tras un cobro posterior, y
`paid_amount` negativo.

Ninguna suite verde sustituye a una revisión independiente: **todas** las generaciones revisadas
tenían el 100% de sus pruebas en verde en el momento de ser revisadas.

El patrón de los hallazgos también es informativo: tras la generación 2, los defectos dejaron de
aparecer en las reglas económicas —que se mantuvieron correctas— y se concentraron en la
conciliación entre un origen con forma de snapshot y un libro con forma de eventos. Por eso la
corrección de la generación 5 es estructural y no otro parche puntual.

Las observaciones no bloqueantes de todas las generaciones revisadas quedan registradas sin corregir, según
el protocolo de corregir únicamente bloqueantes. Ver `HANDOFF.md`.
