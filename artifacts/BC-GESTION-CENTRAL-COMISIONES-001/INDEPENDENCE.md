# Independencia de revisores

Autorizada expresamente por el propietario del repositorio. Cada generación se revisó en tres
subagentes separados, con identidad de rol exclusiva, contexto propio, prompt específico por rol,
evaluación concurrente sobre el mismo snapshot inmutable y **sin compartir razonamiento ni
conclusiones**. Ninguno conoció el verdict de los otros antes de emitir el propio.

## Estado de este snapshot

**Generación 3. Pendiente de revisión independiente.** Los verdicts de generación 3 no existen
todavía; cuando se emitan quedarán en `generation-3/`. Ningún documento de este paquete debe
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

## Valor demostrado de la independencia

Tres defectos financieros reales y dos defectos de veracidad documental fueron detectados por
revisores independientes después de que la autorrevisión de la ejecución implementadora los
declarara correctos. Dos de ellos habrían movido dinero mal.

Las observaciones no bloqueantes de las tres generaciones quedan registradas sin corregir, según
el protocolo de corregir únicamente bloqueantes. Ver `HANDOFF.md`.
