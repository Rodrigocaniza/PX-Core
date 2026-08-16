# Librarian independiente — Generación 8

- RUNNER_ID: `LIBRARIAN-IND-COMISIONES-008`
- SNAPSHOT_COMMIT: `c4f6ee64717ca43becc5986985040ff57d6ee9f2`
- SNAPSHOT_TREE: `6e6bc6a0c66f41ff050e0c256ef3a3493b4eaf6b`
- TIMESTAMP_UTC: 2026-08-16T02:04:11Z
- MANIFEST: 47 OK / 0 FAILED · ZIP: 48 miembros, 48 byte-idénticos, 0 mismatches

## VERDICT: FAIL

### Los cuatro bloqueantes de la generación 7: los cuatro CERRADOS

B1 (ítem de backlog falso) cerrado y reescrito con veracidad; B2 (backlogs distintos) cerrado, hoy
26 = 26 con conjunto idéntico; B3 (contradicción numérica) cerrado, catorce/ocho en los tres
documentos; B4 (referencia que omitía una generación) cerrado.

- EVIDENCE_PRESERVATION: OK. Veintiún verdicts (7 PASS / 14 FAIL); los tres `SELF_REVIEW_*`
  verificados por blob contra `c24b4f19`.
- Cifras verificadas por ejecución: 302/302, 47 dominio + 4 UI = 51, 302 = 251 + 51.
- Las nueve reglas económicas citan símbolos y pruebas que existen; cero citas rotas.

### BLOQUEANTE — reincidencia de la clase B1

`HANDOFF.md` ítem 17 y su gemelo en `WORKFLOW.json` declaraban abierto: «`ARCHITECTURE.md` no
documenta `_reverse_agreement_settlement`». Falso contra este snapshot: `ARCHITECTURE.md` lo
documenta de forma explícita y detallada. Agravante: **el propio commit de esta generación añadió
esa documentación** mientras dejaba el ítem del backlog declarándola ausente. Como ambos backlogs
son idénticos, los dos transportaban la misma afirmación falsa.

## Observaciones no bloqueantes

- `ARCHITECTURE.md` sostiene que `paid_amount` «nunca se asigna por fuera del libro» y tres
  párrafos más abajo admite la escritura directa en el alta. El invariante de resultado se sostiene
  y el ítem 20 lo registra, pero la frase absoluta convive con su propia excepción.
- El conteo «catorce» no incorpora el bloqueante de QA de la generación 7; es defendible si se lee
  como cierre incompleto del de la generación 6, pero la convención no está explicitada.
- `test_expenses_and_administration_deliveries_never_enter_the_ledger` son dos `pytest.raises`
  sobre el constructor: nunca construye un gasto ni toca el libro. El nombre promete más que la
  prueba. Igual para la prueba citada por la regla 8, que cubre sólo la mitad `REVERTIDA`.
- Los ítems 14 y 15 del backlog comparten raíz y figuran como hallazgos independientes.
