# VERDICT_LIBRARIAN — BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001 (generación 2)

| | |
|---|---|
| **Runner** | LIBRARIAN-IND-COMISION-POLICY-1PCT-002 (independiente; sin contacto con QA ni Auditor) |
| **Rol** | Revisor independiente de veracidad documental |
| **Snapshot** | `7abc30e6d33eb5dc522be7e43aa3ad3886a65b32` — árbol limpio antes y después de ejecutar la suite |
| **Base declarada** | `e7732603d9eb098867a272598e6d30803a4f1ac3` |
| **Timestamp UTC** | 2026-08-16T04:00:34Z |
| **Ficheros modificados por mí** | ninguno |

---

## Cierre de bloqueantes de la generación 1

| ID | Origen | Veredicto de cierre |
|---|---|---|
| **L1** | LIBRARIAN | **CERRADO** |
| **L2** | LIBRARIAN | **NO CERRADO — parcial** (ver bloqueante L2) |
| **L3** | LIBRARIAN | **CERRADO** |
| **A1** | AUDITOR | **CERRADO en el código; su evidencia documental es falsa** (ver bloqueante L3) |
| **A2** | AUDITOR | **CERRADO** |

**L1.** `HANDOFF.md` dice ahora «Los **treinta y siete**». Verificado: el handoff anterior tiene 37
ítems numerados y su `WORKFLOW.json` tiene `len == 37`. Cerrado.

**L2.** Parcial. `COMMISSION_RULES.md` recibe una anotación en su encabezado y **su cuerpo no se
retocó** —verificado byte a byte contra `e7732603` con `difflib`: 8 líneas añadidas, 0 eliminadas, 0
modificadas—. La regla 5 y la sección «Configuración pendiente de aprobación» están correctamente
declaradas superadas. Falta: la anotación no cubre la fórmula de redondeo, que el propio L2 citaba y
que `COMMISSION_POLICY_1PCT.md` declara superada. Ver bloqueante L2.

**L3.** `MIGRATION.md` distingue ahora las tres columnas `NOT NULL` con `DEFAULT` de las cuatro
anulables sin `DEFAULT`. Exacto contra `repository.py::_add_missing_columns`. Cerrado.

**A1.** El invariante 2 fue reformulado y la reformulación es **verdadera** contra el código. El
defecto conceptual está cerrado. Lo que no es cierto es la prueba que se cita como verificación: ver
bloqueante L3.

**A2.** **Cerrado, y reproducido por mí sin reusar una sola aserción del paquete.** Sobre base legada
al 7% (33.250 Gs contra 4.750 oficiales): `mark_paid` sobre `APROBADA` legada, `approve` sobre
`REVISADA` legada y `review` sobre `CALCULADA` legada, los tres → `ValueError: la liquidación no
lleva la política oficial vigente (POLITICA_HISTORICA_PREVIA)`. La reparación por `recalculate`:
`{'evaluated': 1, 'changed': 1}` → `CALCULADA`, 4.750, `reviewed_by=None`, `approved_by=None`,
historial `COMMISSION_POLICY_REPAIRED` con el importe reemplazado; segundo pase `changed: 0`. La
legada `PAGADA` no se toca. El desglose rotula «Comisión con política anterior (no pagable)».

---

## Verificaciones

**1. Base, padre y merge.** `git rev-parse 7abc30e^` → **`578bf8b`**. `git merge-base e7732603
7abc30e` → `e7732603`: la base declarada es **ancestro pero NO padre directo** (es el abuelo).
`git merge-base --is-ancestor 7abc30e main` → falso: **sin merge a `main`**. Ver bloqueante L4.

**2. Alcance del diff.** `e7732603..7abc30e` → **28 rutas**: 20 del paquete, `COMMISSION_RULES.md`
(sólo la anotación declarada), 4 de `modulos/gestion_central/`, 2 de `tests/`, 2 de `tools/`. El
diff `578bf8b..7abc30e` toca sólo `comisiones.py` y `test_comisiones.py` además de los documentos:
**los cinco bloqueantes y sólo ellos**.

**3. Conteos de pruebas.** 323 regresión ✓ (323 passed in 29,05 s); 123 módulo ✓; 67 y 5 ✓; 51 base
✓; 302 línea base ✓; 47→65 con +19/−1 y dos parametrizadas → 67 casos ✓; 4→5 interfaz ✓; «19
funciones, 21 casos» ✓; «+21 neto: 20 dominio y 1 interfaz» ✓.

**4. «Pruebas preexistentes actualizadas» (7).** La lista coincide **exactamente** con el conjunto
de funciones modificadas. «Todas las demás siguen intactas» es cierto.

**5. Nombres de prueba citados.** Los 30 existen, salvo la citada como eliminada. Excepción: el
ítem 18, ver bloqueante L3.

**6. Ejemplos numéricos.** Todos verificados contra el código: 400.000→4.000; 500.000→25.000/
475.000/4.750; 333.333→3.167; 1.234.567→12.346; bordes 50→1, 150→2, 49→0; agregado de la captura
4.345.000→43.450. Migración desde base legada de tres alcances → una sola fila `GENERAL`.

**7. MANIFEST.sha256.** **26/26 OK, 0 FAILED.** El paquete tiene 20 archivos; quedan fuera
exactamente `MANIFEST.sha256` y el ZIP.

**8. ZIP.** **27 miembros, 0 mismatch, 0 faltantes**, todos byte-idénticos.

**9. Captura.** SHA-256 `a08910a9…`, **93.753 bytes**, IHDR **1920×1080**, RGB. Los tres valores son
exactos. Leí el PNG y verifiqué **todo** lo que VISUAL_EVIDENCE afirma, incluidas las tres filas por
local, el desglose de cuatro líneas y la nota de política. La advertencia de no reproducibilidad
byte a byte es correcta.

**10. Etiqueta retirada.** Una sola aparición en fuente, en `RETIRED_POLICY_STATUSES`.

**11. Contrato anterior.** Cuerpo **intacto**. Las cláusulas declaradas superadas sí lo están.
Insuficiencias: bloqueante L2 y observación 1.

**12. Code spans.** Backticks pares en los 12 `.md` del paquete, fences balanceados.

**13. Backlog.** 9 y 9, coincidentes ítem a ítem, y los nueve verdaderos contra el código.

**14. Checker.** `PAQUETE CONSISTENTE` (rc=0) para ambos paquetes.

---

## Bloqueantes

1. **L1 — Conteo falso de observaciones de la generación 1.** `INDEPENDENCE.md` afirma «Las
   **quince** observaciones no bloqueantes de los tres verdicts». Contadas sobre los verdicts que el
   propio paquete conserva: Librarian **8**, QA **7**, Auditor **8**. Total **23**, no quince.
   Quince es la suma de Librarian + QA: se omitieron íntegramente las ocho del Auditor. Es
   exactamente el defecto de clase L1 de la generación anterior, reintroducido en un documento
   **nuevo** de esta generación.

2. **L2 — La anotación de superado no cubre todo lo que el propio paquete declara superado, y
   SUMMARY se contradice con COMMISSION_POLICY_1PCT sobre cuánto es.**
   `COMMISSION_POLICY_1PCT.md` abre con «quedan superadas, y sólo ellas» y lista **tres** ítems;
   `SUMMARY.md` dice «quedan superadas **exactamente** la regla 5 y la sección… —**las dos**…» y
   remite a la lista de tres. Dos absolutos incompatibles sobre la cuestión que L2 existía para
   zanjar. Peor: la anotación añadida a `COMMISSION_RULES.md` menciona sólo dos, de modo que un
   lector deduce que el resto sigue vigente y llega a «Redondeo y enteros», que documenta
   `(importe * puntos_basicos + 5000) // 10000` como la implementación. El L2 original citaba esa
   fórmula explícitamente.

3. **L3 — La prueba citada como verificación del invariante de traza no ejercita el caso por el que
   existe.** `TEST_EVIDENCE.md` ítem 18 y el invariante 2 de `ARCHITECTURE_DELTA.md` citan
   `test_the_trace_is_complete_exactly_when_the_policy_is_the_canonical_one` «sobre los tres estados
   de política que conviven en una misma base». Reproduje el escenario exacto: tras el
   `recalculate` de la prueba los estados presentes son **`['CANONICA_APROBADA',
   'FUERA_DE_VIGENCIA']`**. No hay ninguna `POLITICA_HISTORICA_PREVIA`: la única legada es reparada
   por ese mismo `recalculate` —que es justamente el arreglo de A2—. La rama `else`, la que comprueba
   la traza vacía, es **código muerto**, y la aserción final ni siquiera exige el tercer estado. La
   mitad del invariante 2 que corresponde a A1 no la verifica la prueba que se cita para ello.

4. **L4 — `ARTIFACT_CONSISTENCY.md` afirma un parentesco que git desmiente.** «…que es el **padre
   directo del snapshot**». El padre directo de `7abc30e` es `578bf8b`; `e7732603` es su abuelo. El
   documento es **nuevo** en este commit: la afirmación era cierta para la generación 1 y se copió
   sin verificar. Agravante: `WORKFLOW.generations[1].snapshot_commit` sigue en `null`, de modo que
   lo único que el paquete dice sobre el linaje del commit revisado es incorrecto.

---

## Observaciones no bloqueantes

1. **La enumeración «reglas 1 a 4 y 6 a 8» omite la regla 9.** `COMMISSION_RULES.md` tiene nueve
   reglas; la novena, «Toda edición, anulación, reversión o recálculo conserva auditoría», sigue
   vigente pero queda sin declarar en tres documentos a la vez.

2. **La evidencia de ausencia de floats sigue sobrevalorada** (heredada, sin cambios).
   `test_no_external_provider_or_secrets_in_module` lee sólo `comisiones.py`, no `comision_policy.py`,
   que es donde vive la aritmética de la que habla la frase. Y `comisiones.py:827` sí produce un
   float para rotular el descuento.

3. **El paquete sigue sin fijar su propio snapshot.** `generations[1].snapshot_commit` es `null` y
   `evidence` apunta a `generation-2/`, que no existe. Repite la observación 3 de la generación 1.

4. **El checker trata la generación en curso como revisada.** Calcula `reviewed = max(generation)`
   sin mirar `status`, de modo que su regla de «no anticipar la revisión en curso» queda inerte.

5. **Tabla partida en `TEST_EVIDENCE.md`.** Las dos filas nuevas están separadas por una línea en
   blanco y renderizan como una segunda tabla sin encabezado. Cosmético.

6. **`SUMMARY.md` y `WORKFLOW.json` siguen discrepando sobre la venta con saldo** (observación 6 de
   la generación 1, no corregida): «0 (no pagable)» frente a `commission: null`.

---

VERDICT: FAIL
