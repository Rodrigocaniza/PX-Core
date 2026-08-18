# Independencia de revisores

Autorizada expresamente por el propietario del repositorio. Cada generación se revisa en tres
runners separados, con identidad de rol exclusiva, contexto propio, prompt específico por rol,
evaluación concurrente sobre el mismo snapshot inmutable y **sin compartir razonamiento ni
conclusiones**. Ninguno conoce el verdict de los otros antes de emitir el propio.

En cada generación los tres corrieron en paralelo sobre el snapshot de esa generación —
`578bf8b7205c857f9032581744f1e5818dab99fa`, `7abc30e6d33eb5dc522be7e43aa3ad3886a65b32` y
`75f5c5728cf9194b3e4c91a3b1e83c10ea1ec48a` respectivamente— con el worktree limpio, y ninguno
modificó el árbol: QA y el Auditor escribieron sus escenarios propios en un directorio temporal
fuera del repositorio.

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

## Generación 5

Pendiente. Su alcance es cerrar B1-g4 y B2-g4 sobre el snapshot que publique esa corrección. B1-g4
requiere decisión de propietario sobre en qué debe apoyarse la guarda. Los verdicts de las
generaciones 1, 2, 3 y 4 no se reutilizan.
