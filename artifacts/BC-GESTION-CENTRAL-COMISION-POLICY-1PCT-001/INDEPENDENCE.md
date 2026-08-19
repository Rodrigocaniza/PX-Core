# Independencia de revisores

Autorizada expresamente por el propietario del repositorio. Cada generación se revisa en tres
runners separados, con identidad de rol exclusiva, contexto propio, prompt específico por rol,
evaluación concurrente sobre el mismo snapshot inmutable y **sin compartir razonamiento ni
conclusiones**. Ninguno conoce el verdict de los otros antes de emitir el propio.

En cada generación los tres corrieron en paralelo sobre el snapshot de esa generación —`578bf8b`,
`7abc30e`, `75f5c57` y `5652e46` respectivamente, y el de la generación 5 queda fijado en su commit
de registro— con el worktree limpio, y ninguno modificó el árbol: QA y el Auditor escribieron sus
escenarios propios en un directorio temporal fuera del repositorio. Cada sección de más abajo lleva
el snapshot completo.

## Generación 1 — snapshot `578bf8b7205c857f9032581744f1e5818dab99fa`

| Runner | Rol | Verdict |
|---|---|---|
| `LIBRARIAN-IND-COMISION-POLICY-1PCT-001` | LIBRARIAN | **FAIL** — L1, L2, L3 |
| `QA-IND-COMISION-POLICY-1PCT-001` | QA | PASS |
| `AUDITOR-IND-COMISION-POLICY-1PCT-001` | AUDITOR | **FAIL** — A1, A2 |

Evidencia íntegra y sin retocar en `generation-1/`.

La independencia se pagó sola. Los dos revisores que fallaron encontraron defectos que la
autorrevisión no vio, y **no se solapan entre sí**: el Librarian encontró tres afirmaciones falsas
del paquete contra el código; el Auditor encontró una fuga económica real —una liquidación migrada
era pagable al porcentaje ya retirado, hasta siete veces el oficial, por el flujo normal de la
pantalla— y además demostró que el remedio manual que el propio paquete documentaba destruía la
comisión en lugar de corregirla. QA, que pasó, había ejercitado la guarda de pago sólo por su
literal —ausencia de importe— y por eso no llegó al mismo sitio; su observación 7 rozaba el asunto
sin cruzarlo.

Los cinco bloqueantes se corrigieron y sólo ellos. Las **veintitrés** observaciones no bloqueantes
de los tres verdicts —ocho del Librarian, siete de QA y ocho del Auditor— quedaron registradas, no
corregidas, según el protocolo.

## Generación 2 — snapshot `7abc30e6d33eb5dc522be7e43aa3ad3886a65b32`

| Runner | Rol | Verdict |
|---|---|---|
| `LIBRARIAN-IND-COMISION-POLICY-1PCT-002` | LIBRARIAN | **FAIL** — L1, L2, L3, L4 |
| `QA-IND-COMISION-POLICY-1PCT-002` | QA | **FAIL** — Q1, Q2, Q3 |
| `AUDITOR-IND-COMISION-POLICY-1PCT-002` | AUDITOR | **FAIL** — A1, A2, A3 |

Evidencia íntegra y sin retocar en `generation-2/`.

Los tres confirmaron por su cuenta el cierre de la fuga de la generación 1 y los tres encontraron
que la corrección era **insuficiente contra su propio enunciado**, cada uno por un flanco distinto:

- QA y el Auditor coincidieron, sin verse, en que la reparación cubría una sola de las dos etiquetas
  retiradas y dejaba varada la liquidación **sin porcentaje** —que era el estado por defecto del
  piloto anterior, porque nunca sembró política—. Ambos lo reconstruyeron ejecutando el código
  pre-misión en vez de fabricar el estado por SQL.
- El Auditor encontró la deriva de versión: la guarda comprobaba el sello grabado al calcular y no
  la política en vigor, así que publicar una versión nueva y pagar después liquidaba al porcentaje
  anterior. Ruta pública, sin base legada.
- QA encontró el mismo daño por el flujo soportado: programar la vigencia del mes siguiente y pulsar
  «Recalcular» destruía la comisión ya calculada del mes en curso, porque el historial de versiones
  se escribía y nunca se leía para calcular.
- El Librarian encontró cuatro afirmaciones falsas, tres de ellas **introducidas por la propia
  corrección** de la generación 1 —incluido un conteo erróneo del mismo tipo que él había marcado
  antes— y una prueba que ya no ejercitaba el caso por el que existía, porque el arreglo la había
  vuelto inalcanzable.

Los diez bloqueantes se corrigieron y sólo ellos. Sus **diecisiete** observaciones no bloqueantes
—seis del Librarian, cinco de QA y seis del Auditor— quedaron registradas, no corregidas.

## Generación 3 — snapshot `75f5c5728cf9194b3e4c91a3b1e83c10ea1ec48a`

| Runner | Rol | Verdict |
|---|---|---|
| `LIBRARIAN-IND-COMISION-POLICY-1PCT-003` | LIBRARIAN | **FAIL** — L1, L2 |
| `QA-IND-COMISION-POLICY-1PCT-003` | QA | PASS |
| `AUDITOR-IND-COMISION-POLICY-1PCT-003` | AUDITOR | **FAIL** — B1, B2 |

Evidencia íntegra y sin retocar en `generation-3/`.

Los tres verificaron por su cuenta el cierre de los quince bloqueantes de las generaciones 1 y 2, y
los tres coincidieron en que están cerrados. QA lo hizo por ejecución, reconstruyendo con sus
propios escenarios los tres casos que él mismo había roto en la generación 2, y pasó. El Auditor
reprodujo los diez invariantes económicos del enunciado y **los diez pasan**, incluida la
concurrencia real sobre `mark_paid`, `set_general_rate`, `register_payment` y `recalculate`.

Los dos FAIL no revierten nada de lo anterior; abren frente nuevo:

- El Auditor encontró la **fuga inversa** de la que cerró en las generaciones 1 y 2. Allí se pagaba
  a una política ya superada; aquí se paga a una política que **no regía cuando se generó la
  comisión**: la guarda de `set_general_rate` rechaza una vigencia *anterior* a la última publicada
  pero acepta una **igual**, de modo que un período ya calculado, revisado y aprobado se re-tarifa
  al alza —4.000.000 Gs donde el 1% eran 100.000— o a cero, y se paga. Es exactamente lo que el
  código dice que «el versionado existe para impedir».
- El mismo Auditor encontró que la promesa de reparación sin destrucción es falsa en dos sub-casos:
  el período anterior a la vigencia no tiene salida por ninguna ruta pública, y el importe anulado
  no queda asentado cuando la liquidación no estaba en `REVISADA` ni `APROBADA`.
- El Librarian encontró dos recuentos falsos, **ambos desactualizados por la corrección de esta
  misma generación** y ambos del mismo tipo que G2-L1 y G2-L2: los miembros del ZIP y las
  observaciones de la generación 2 en este mismo documento. Se corrigen en el commit de registro,
  y su cierre queda sujeto a la reverificación del Librarian sobre el snapshot de la generación 4.

QA, que pasó, había rozado el asunto de B1 por el flanco de las vigencias a mitad de mes (su
observación O1) sin cruzar hasta la vigencia igual, y por eso no llegó al mismo sitio que el
Auditor. Las **diecisiete** observaciones no bloqueantes de los tres verdicts —seis del Librarian,
cuatro de QA y siete del Auditor— quedan registradas, no corregidas.

## Generación 4 — snapshot `5652e46ce7127060ed50d96e464e732809351550`

| Runner | Rol | Verdict |
|---|---|---|
| `LIBRARIAN-IND-COMISION-POLICY-1PCT-004` | LIBRARIAN | PASS |
| `QA-IND-COMISION-POLICY-1PCT-004` | QA | PASS |
| `AUDITOR-IND-COMISION-POLICY-1PCT-004` | AUDITOR | **FAIL** — B1-g4, B2-g4 |

Evidencia íntegra y sin retocar en `generation-4/`.

Es la primera generación con dos PASS, y la que mejor muestra para qué sirve la independencia. Los
tres reverificaron por su cuenta el cierre de los cuatro bloqueantes de la generación 3 y los tres
lo confirmaron: el Librarian ejecutando el exploit del Auditor en vez de leer el diff, QA con 203
comprobaciones propias, el Auditor con 161.000 casos de aritmética, 1.200 operaciones de fuzz y 80
rondas de concurrencia. Los diez invariantes económicos pasan. La guarda nueva no introdujo
regresión alguna.

Y aun así el Auditor volvió a encontrar dinero mal pagado, por cuarta generación consecutiva, en la
superficie que los otros dos no exploraron:

- **B1-g4.** La guarda decide si un período «ya fue liquidado» mirando el **estado actual** de las
  entradas. `observe()` sobre una liquidación pagada —operación pública, normal y explícitamente
  permitida—, `void_sale()` sobre una venta ya cobrada, `revert()`, o incluso una corrección
  cosmética de origen, sacan la entrada de `SETTLED_STATES` y devuelven la fuga entera: **400.000 Gs
  pagados por un período donde el 1% eran 40.000**, o el mes completo anulado a cero. La afirmación
  de que «no tiene ruta pública, ni directa ni indirecta» es falsa.
- **B2-g4.** La garantía de que «todo importe retirado queda asentado» sólo se cumple dentro de
  `recalculate`. `_apply_source_update` anula `rate_bp` y `commission_amount` y escribe
  `SOURCE_UPDATED` sin el bloque `replaced`: un importe heredado de una base migrada, que no tiene
  asiento previo, desaparece del sistema por una corrección de sobre.

QA había rozado B1-g4 por el flanco de `revert` —su observación O2, con la misma reproducción— y
decidió no elevarlo a bloqueante porque exige una acción destructiva y auditada y no alcanza dinero
pagado. El Auditor cruzó donde QA no: `observe()` sobre una **PAGADA**, que no es destructiva, no
requiere permiso especial y sí alcanza dinero pagado. La diferencia entre una observación y un
bloqueante estuvo en un solo estado de la máquina.

El Librarian, que dio por ciertos los invariantes 5 y 7 en sus puntos 6 y 12, dejó anotado en su
propio verdict qué superficie no cubrió, sin retocar el PASS. Las **catorce** observaciones no
bloqueantes de los tres verdicts —siete del Librarian, cuatro de QA y tres del Auditor— quedan
registradas, no corregidas.

## Generación 5 — snapshot `2ac9f5c93ec99ed506133310ee6cd19f6779b971`

| Runner | Rol | Verdict |
|---|---|---|
| `LIBRARIAN-IND-COMISION-POLICY-1PCT-005` | LIBRARIAN | **FAIL** — L1-g5 … L6-g5 |
| `QA-IND-COMISION-POLICY-1PCT-005` | QA | **FAIL** — QB1-g5, QB2-g5 |
| `AUDITOR-IND-COMISION-POLICY-1PCT-005` | AUDITOR | **FAIL** — AB1-g5, AB2-g5 |

Evidencia íntegra y sin retocar en `generation-5/`.

**Los tres coinciden en que el diseño es correcto y en que B1-g4 y B2-g4 están cerrados de verdad**,
cada uno por su cuenta: QA con una matriz propia de 18 transiciones y 7 cadenas encadenadas, el
Librarian ejecutando la matriz y comprobando que ninguna sentencia escribe `UPDATE` o `DELETE` sobre
la evidencia, el Auditor con 10 transiciones, 30 semillas × 120 pasos de fuzz histórico y
concurrencia real. Los diez invariantes pasan sobre bases frescas. Nadie encontró una transición que
devuelva un período tarifado al catálogo.

Y aun así los tres fallan, cada uno en una capa distinta, y ninguno se solapa con otro:

- **El Auditor**, en la capa que el diseño no cubrió: **cuándo se graba la evidencia**. Un pin es
  definitivo, así que grabarlo mal es peor que una guarda floja. Encontró dos formas de grabarlo mal,
  ambas con dinero mal pagado. `AB1-g5`: la siembra de la migración fija el período con la tasa de la
  liquidación más antigua, aunque esté `REVERTIDA` y su venta anulada, y aunque el mes se haya pagado
  dos veces a otra tasa; la migración baja una `APROBADA` de 500.000 a 100.000 Gs y le borra el aval,
  sin una sola fila de auditoría. `AB2-g5`: un tipeo de fecha fija un mes lejano para siempre, y el
  pin sobrevive a la corrección de origen y a la anulación que el propio sistema registra.
- **QA**, en la capa del rótulo: en un período donde no rige ninguna tasa, la pantalla declara oficial
  la tasa global publicada y el export emite «Comisión oficial None%». Es el error que la misión
  corrige desde la generación 2, sobreviviendo en las dos superficies que la gente lee.
- **El Librarian**, en la capa documental: seis afirmaciones falsas, todas por no actualizar la
  documentación al retirar la guarda por estado, incluida una que declaraba abierto un hallazgo que
  el propio paquete demuestra imposible, y otra que justificaba no regenerar la captura con un rótulo
  que ya cambió.

La observación del Auditor que ordena la misión entera: «es la quinta generación consecutiva en que
la fuga aparece en el mismo sitio conceptual: la afirmación de que un importe es oficial se apoya en
algo que no verifica que lo sea. Antes era la etiqueta; ahora es la primera fila escrita.»

Los seis bloqueantes documentales se cierran en el commit de registro. Las **diecisiete**
observaciones no bloqueantes de los tres verdicts —siete del Librarian, cuatro de QA y seis del
Auditor— quedan registradas, no corregidas.

## Generación 6 — snapshot `a5d6955828850b322c7ea00f5b46e3b5e7f3d7e4`

| Runner | Rol | Verdict | Bloqueantes |
|---|---|---|---|
| `LIBRARIAN-IND-COMISION-POLICY-1PCT-006` | Librarian | **FAIL** | `L1-g6` … `L5-g6`, documentales |
| `QA-IND-COMISION-POLICY-1PCT-006` | QA | **PASS** | ninguno |
| `AUDITOR-IND-COMISION-POLICY-1PCT-006` | Auditor | **FAIL** | `AB1-g6`, económico |

**Resultado: INVALIDADA.** Los tres confirmaron, cada uno por su cuenta, que `AB1-g5` y `AB2-g5`
están cerrados: el Auditor reprodujo los dos escenarios exactos de la generación 5 y midió que los
400.000 Gs de diferencia desaparecen en ambos. `QB1-g5` y `QB2-g5` también quedan cerrados,
verificados por QA sobre widgets Tk reales. Lo que invalida la generación es otra cosa.

**Qué cubrió cada uno, y por dónde entró el fallo.**

- **QA** construyó una matriz propia de dos ejes —once celdas de estado × fijado— más nueve bases
  legadas a mano y mil reaperturas, y comprobó en cada celda que el dinero y el rótulo dicen lo
  mismo. No encontró ningún bloqueante. Declaró no haber ejercitado concurrencia ni el paquete
  documental: las dos superficies donde sí había fallos.
- **El Librarian** contrastó afirmación por afirmación contra el código y encontró cinco
  documentales, todos de la misma familia que los doce anteriores: **documentación que no se
  actualizó al cambiar la semántica**. Tres de ellos —`L2-g6`, `L3-g6`, `L4-g6`— son entradas del
  backlog que describían como pendiente algo que esta misma generación había hecho, o como vigente
  un daño que había eliminado. Declaró explícitamente no haber intentado romper el boundary.
- **El Auditor** encontró `AB1-g6` **leyendo el código, no fuzzeando**, y lo dijo: sus 85 corridas
  de fuzz validaban el pin contra el historial, y el historial conserva la aprobación después de
  revertirla, de modo que el defecto era invisible para su propio arnés. Es la observación más
  valiosa del ciclo: un invariante mal elegido convierte 17.000 pasos limpios en ninguna evidencia.

**La lección estructural de esta generación.** La 5 fallaba porque fijaba demasiado pronto. La 6
mueve el boundary de entrada de `CALCULADA` a `APROBADA` y eso es correcto y está verificado. Pero
no toca el boundary de **salida**: la evidencia se crea con un hecho económico y no se retira
cuando ese hecho se retira. `AB1-g6` es el mismo defecto estructural que `AB2-g5`, un estado más
adelante. Cerrarlo exige decidir si un período puede **desfijarse**, que es una decisión distinta de
la que el propietario ya tomó y que la generación 7 debe plantear antes de escribir código.

Los verdicts de las generaciones 1 a 6 **no se reutilizan** en la generación 7.

## Generación 7

**Remediada, pendiente de los tres verdicts.** Alcance ejecutado: `AB1-g6`, con la decisión de
propietario —opción (a), desfijar al retirarse el último hecho vivo— y las observaciones de la
generación 6 que pertenecen a su misma familia.

**Qué superficie debe cubrir cada rol, a la vista de lo que cada uno no cubrió antes:**

- **Auditor.** Encontró `AB1-g6` leyendo el código y dijo que su propio fuzz no podía detectarlo,
  porque validaba el pin contra el historial y el historial conserva la aprobación revertida. El
  invariante correcto ahora es **contra los hechos vivos**, no contra el historial: un período está
  fijado si y sólo si tiene al menos un `APROBADA`/`PAGADA` vivo o un `paid_at`. La superficie nueva
  es la simetría del boundary —¿existe alguna ruta que suelte un período que **sí** tiene un hecho
  vivo, o que deje fijado uno que no lo tiene?— y la concurrencia entre soltar y fijar.
- **QA.** Su matriz de once celdas dio PASS y no encontró nada, porque el defecto estaba en una
  dimensión que su matriz no tenía: el tiempo. La matriz de esta generación necesita el eje
  **secuencia**: fijar → retirar → refijar, y qué dice el rótulo en cada punto.
- **Librarian.** Cinco documentales en la generación 6, tres de ellos entradas de backlog que
  describían como pendiente algo ya hecho. Esta generación vuelve a cambiar la **semántica** de la
  fijación y además cambia la **representación**, así que toda afirmación sobre
  `commission_rated_periods` es sospechosa por defecto, y los recuentos del paquete se movieron
  otra vez.

Los verdicts de las generaciones 1 a 6 **no se reutilizan**.
