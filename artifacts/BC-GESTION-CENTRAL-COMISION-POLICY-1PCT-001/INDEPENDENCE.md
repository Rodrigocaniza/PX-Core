# Independencia de revisores

Autorizada expresamente por el propietario del repositorio. Cada generación se revisa en tres
runners separados, con identidad de rol exclusiva, contexto propio, prompt específico por rol,
evaluación concurrente sobre el mismo snapshot inmutable y **sin compartir razonamiento ni
conclusiones**. Ninguno conoce el verdict de los otros antes de emitir el propio.

Los tres corrieron en paralelo sobre `578bf8b7205c857f9032581744f1e5818dab99fa` con el worktree
limpio, y ninguno modificó el árbol: QA y el Auditor escribieron sus escenarios propios en un
directorio temporal fuera del repositorio.

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

Los diez bloqueantes se corrigieron y sólo ellos. Sus veinte observaciones no bloqueantes quedaron
registradas, no corregidas.

## Generación 3

Pendiente de revisión sobre el snapshot que publica esta corrección.
