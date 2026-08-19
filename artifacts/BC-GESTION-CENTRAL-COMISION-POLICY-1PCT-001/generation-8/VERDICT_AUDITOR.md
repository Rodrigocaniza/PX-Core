# Verdict — Auditor, generación 8
Runner: AUDITOR-IND-COMISION-POLICY-1PCT-008
Snapshot: cf4fb258703e266148d7bb7332b79ffdddce926c
Veredicto: FAIL

## Ataques ejecutados

Todo el trabajo se hizo con scripts propios en `…\scratchpad\aud8`, sobre bases sqlite temporales, importando el módulo con `sys.path.insert` al worktree. No modifiqué ningún archivo del repositorio ni hice ningún commit.

Regresión completa del repositorio: `python -m pytest -q` → **431 passed in 40.01s**.

**1. El arnés arranca de bases MIGRADAS, como pedía el encargo (`common.py::legacy_db`).** Construyo la base legada por SQL plano —ventas y liquidaciones a mano, con la etiqueta del piloto, con o sin `paid_at`, con `voided`, con `period` de diez caracteres, con políticas por alcance `VENDEDORA`/`LOCAL`— y **después** instancio `CentralRepository`, que es la migración oficial. El invariante de simetría corre en las **tres** direcciones (`PINNED_SIN_HECHO_VIVO`, `HECHO_VIVO_SIN_PIN`, `PIN_INCOHERENTE_CON_HECHOS_VIVOS`) **desde el paso 0** de cada corrida, y el predicado que usa el arnés es el literal `comision_policy.LIVE_OFFICIAL_FACT_SQL` importado del propio módulo, para no reescribirlo yo mismo.

**2. Once formas de base migrada, simetría en el paso 0 (`t01_step0.py`).**

| Base legada | Libro tras migrar | Violación en el paso 0 |
|---|---|---|
| piloto con comisión **pagada legada** @300 | vacío | **ninguna** ← `AB1-g7` cerrado |
| `PAGADA` canónica @500 | `PINNED@500` BACKFILL | ninguna |
| **evidencia discrepante canónica** `APROBADA`@100 + `PAGADA`@500 | vacío (`SEED_SKIPPED / EVIDENCIA_DISCREPANTE`) | **`HECHO_VIVO_SIN_PIN`** |
| `APROBADA` canónica @900 | `PINNED@900` | ninguna |
| `APROBADA` canónica con venta anulada | vacío | ninguna |
| sólo `REVERTIDA` | vacío | ninguna |
| sólo `CALCULADA` | vacío | ninguna |
| período fuera de vigencia (`2026-07`) @700 | `PINNED@700` | ninguna |
| convenio legado pagado @300 | vacío | ninguna |
| `period` de 10 caracteres (`2099-04-04`) @900 | `PINNED@900` bajo `2099-04` | ninguna ← obs. 2 de la g7 cerrada |
| discrepante mixta legada@300 + canónica@100 | `PINNED@100` | ninguna |

**3. Fuzz encadenado desde bases migradas (`t05_fuzz.py`).** Nueve formas de base migrada × 12 semillas × 80 pasos = **108 corridas, 8.640 pasos**. Once operaciones públicas, períodos `{2099-04, 2099-05, 2099-06, 2026-07}`, importes `{3, 50, 100000, 999999, 1234567, 10000000}`, tasas `{0, 100, 250, 900, 2000, 10000}`, ambos tipos de venta. La simetría en las tres direcciones se comprueba tras **cada** paso. **Ocho de las nueve formas: 0 fallos en 96 corridas. La forma «evidencia discrepante»: falla en 12 de 12 corridas, en el paso 0.**

**4. Concurrencia real (`t06_conc.py`, `t12_conc_disc.py`), `threading.Barrier`, 27 escenarios sobre tres formas de base migrada × 30 rondas = 810 rondas y ~1.770 operaciones concurrentes**, más 4 escenarios × 25 rondas sobre base discrepante.

| Escenario (por cada forma: `PAGADA` canónica sembrada / `PAGADA` legada / `APROBADA` canónica sembrada) | Rondas | Estados malos |
|---|---|---|
| A `revert` (soltar) ‖ `approve` (fijar), mismo período | 30 ×3 | 0 |
| B `void_sale` ‖ `mark_paid` | 30 ×3 | 0 |
| C dos `revert` simultáneos del mismo período | 30 ×3 | 0 |
| D `revert` ‖ `set_general_rate` | 30 ×3 | 0 |
| E `revert` ‖ `recalculate` | 30 ×3 | 0 |
| F `revert_payment` ‖ `approve` | 30 ×3 | 0 |
| G 4 hilos `revert` ‖ `approve` ‖ `void_sale` ‖ `recalculate` | 30 ×3 | 0 |
| H sobre pagada: `observe` ‖ `void_sale` ‖ `recalculate` | 30 ×3 | 0 |
| I `approve` ‖ `set_general_rate` | 30 ×3 | 0 |
| A/B/G y `revert` ‖ `mark_paid` ‖ `publish` sobre base **discrepante** | 25 ×4 | **`PIN_INCOHERENTE` en 74 de 100 rondas** |

Ni un `OperationalError`, ni un `database is locked`, ni un pin duplicado, ni una `APROBADA`/`PAGADA` sobre venta anulada, en ninguna forma. **Haber pasado la conexión del llamador a `decide()` y a las guardas de pago no abrió ninguna ventana de coherencia nueva.** Las violaciones sobre base discrepante no las produce la concurrencia: están ya en el paso 0 y la concurrencia sólo las hace visibles antes.

**5. Secuencias largas fijar/soltar/refijar sobre base migrada (`t09_long.py`).** Ocho ciclos con tasas `100, 900, 0, 2500, 10000, 350, 100, 5000` sobre dos formas de base migrada. **16 eventos alternando `PINNED`/`UNPINNED` sin excepción en las dos**, 0 violaciones de simetría, y el mes de la base migrada nunca se toca.

**6. La pregunta estructural: ¿queda alguna regla escrita dos veces?**

- **`LIVE_OFFICIAL_FACT_SQL` y `PERIOD_MATCH_SQL` son ahora el único predicado de vitalidad, y ningún lado le añade nada.** El único añadido es `e.period IS NOT NULL`, que es inocuo. **`AB1-g7` está cerrado en la raíz, no parcheado.**
- **`record_period_rate_event` es el único escritor.** `grep` sobre `modulos/`: **un solo `INSERT`, cero `UPDATE`, cero `DELETE`**. La siembra **sí** pasa por él.
- **Pero la regla que decide *qué tasa tiene un período* sigue escrita dos veces, y ahí está el bloqueante.** La siembra la resuelve con «si la evidencia viva discrepa, no elijo» (`repository.py:365-372`); el código en caliente con «la fija el primero que apruebe, y la sostiene *cualquier* hecho vivo, lleve la tasa que lleve». Es la misma pregunta contestada por dos reglas distintas: exactamente la forma de `AB1-g6` y `AB1-g7`, movida una vez más de columna.
- **Tercer sitio del predicado, en Python.** `comisiones.py:796` repite a mano la mitad de `LIVE_OFFICIAL_FACT_SQL` y **omite la cláusula de venta anulada**. Hoy no es explotable porque `_reject_voided_sale` la cubre por otra vía, pero es una cuarta copia parcial.

**7. Migración: idempotencia, no invención, no toca dinero (`t11_mig.py`).** Cinco reaperturas sobre una base con evidencia discrepante y una `CALCULADA`: **SHA-256 de `commission_entries` idéntico las cinco veces**, 0 eventos, **0 `UNPINNED`**, exactamente 1 asiento `SEED_SKIPPED`, sin duplicar.

**8. Aritmética y estructura.** `git diff 41131a6 HEAD -- comision_policy.py`: los únicos cambios de esta generación son las constantes `LIVE_OFFICIAL_FACT_SQL` y `PERIOD_MATCH_SQL` y sus comentarios. **Ni una línea de aritmética cambió.** Cero `float(` y cero `round(`; el único `ROUND_HALF_UP` sigue en `quantize_guarani` con `prec = 60`.

**9. La observación 1 de la generación 7 está cerrada (`t10_recalc.py`).** `recalculate` converge en **una sola pasada** sobre base migrada.

## Reproducción de AB1-g7 y de las cuatro rutas de AB1-g6 sobre base migrada

**`AB1-g7` está CERRADO.** Base del piloto con una única comisión ya pagada @300 bajo etiqueta `SINTETICA_PENDIENTE_APROBACION`:

```
tras migrar: POLITICA_HISTORICA_PREVIA  rate 300  importe 30.000  paid_at 2099-05-10  (intacto)
pin sembrado: []        hechos vivos 2099-04: []      simetria paso 0: sin violaciones
```

Y las **cuatro rutas de `AB1-g6` sobre esa base migrada**:

| Ruta que retira el hecho | Libro de `2099-04` | 3 ventas reales de 10.000.000 pagan | Sobrepago |
|---|---|---|---|
| `revert` de la aprobación | `PINNED@10000 → UNPINNED@10000 → PINNED@100` | 300.000 Gs | **0 Gs** |
| `void_sale` | `PINNED@10000 → UNPINNED@10000 → PINNED@100` | 300.000 Gs | **0 Gs** |
| `observe` + `revert` | `PINNED@10000 → UNPINNED@10000 → PINNED@100` | 300.000 Gs | **0 Gs** |
| `revert_payment` (cheque rechazado, con cobro real registrado) | `PINNED@10000 → UNPINNED@10000` | 300.000 Gs | **0 Gs** |

En las cuatro, el importe legado queda byte a byte intacto. **Los 29.700.000 Gs que medía la generación 7 desaparecen sobre la base del piloto pagada.**

**Las mismas cuatro rutas vuelven a pagar mal sobre otra base migrada: la de evidencia discrepante.** Es `AB1-g8`.

## Bloqueantes

### AB1-g8 — la migración se niega a desempatar evidencia discrepante y el código en caliente sí desempata: un mes migrado nace sin pin teniendo hechos vivos, y el primer pin que reciba queda clavado para siempre a la tasa equivocada

**Dónde.** Dos reglas para la misma pregunta —«¿qué tasa tiene este período?»—, cada una en un sitio:

- `repository.py:365-372`, `_backfill_period_rate_events`: si `len(rates) > 1` asienta `SEED_SKIPPED` y `continue` — el período queda **sin** pin, con hechos vivos dentro.
- `comisiones.py:834`, `_reconcile_period_pin`: `if self._live_official_facts(con, period): return False` — **cualquier** hecho vivo retiene el pin, lleve la tasa que lleve.

El predicado de vitalidad ya es uno solo, y eso está bien resuelto. Lo que sigue duplicado es la **regla de decisión**. La consecuencia es la misma de siempre: un pin que ningún hecho vivo justifica **y que nada puede retirar**.

**Por qué no es un caso de laboratorio.** La base que lo explota la produce la propia migración oficial, y la produce **por diseño**: `_migrate_commission_policy` retira las políticas por alcance `VENDEDORA` y `LOCAL` (invariante I1 del paquete). Una instalación del piloto que tenía 9 % por vendedora y 7 % por local produjo liquidaciones del **mismo mes** con `policy_status = CANONICA_APROBADA` y `rate_bp` distintos. El `SEED_SKIPPED / EVIDENCIA_DISCREPANTE` que la migración escribe **es la firma de que el sistema entró en este estado**.

**Reproducción — `t03_scoped.py`, sólo API pública sobre la base migrada, sin SQL, sin concurrencia.** Base legada: políticas de piloto `VENDEDORA:Vendedora Vieja @900` y `LOCAL:Óptica Asunción @700`, y dos liquidaciones de `2099-04`: `e-V` `APROBADA` @900 / 90.000 Gs y `e-L` `PAGADA` @700 / 70.000 Gs.

```
paso 0 (recien migrada):
   auditoria: SEED_SKIPPED {"reason":"EVIDENCIA_DISCREPANTE","rates_bp":[700,900]}
   libro de 2099-04: []            hechos vivos: [e-V@900, e-L@700]
   VIOLACION: HECHO_VIVO_SIN_PIN
1) publish 10000bp eff 2099-01-01 -> (2, True)
2) venta de 2099-04 por 10.000.000 -> recalculate/review/approve -> PINNED@10000
3) revert(entry) -> pin: PINNED@10000   <-- NO SUELTA. e-L (PAGADA@700) lo sostiene.
   VIOLACION: PIN_INCOHERENTE_CON_HECHOS_VIVOS — pin@10000 vs vivos [700]
4) publish 100bp eff 2099-01-01 -> (3, True); recalculate -> {'evaluated': 1, 'changed': 0}
   policy_for_period('2099-04') -> {'rate_bp': 10000, 'pinned': True}
5) tres ventas REALES de 10.000.000 Gs cada una, aprobadas y pagadas:
   TOTAL pagado 30.000.000 Gs | correcto al 1% 300.000 Gs | SOBREPAGO 29.700.000 Gs
   libro completo: [PINNED@10000]   <-- un solo evento, ningun UNPINNED jamas
```

**Las cuatro rutas de `AB1-g6` vuelven a fallar, todas, con la misma cifra**: `revert`, `void_sale`, `observe`+`revert` y `revert_payment` dejan `[PINNED@10000]` y 30.000.000 Gs pagados, **29.700.000 Gs de sobrepago**.

**Daño: 29.700.000 Gs en el escenario reproducido; 9.900.000 Gs de sobrepago por cada venta de 10.000.000 Gs del mes, sin techo.** En la dirección contraria, **9.900.000 Gs de subpago por venta**.

**No hay ninguna ruta pública de corrección (`t04_norescue.py`):** publicar a cualquier tasa, recalcular, reabrir la base tres veces, observar, revertir o anular la venta de `e-L` dejan todos el pin en 10000.

**Qué haría falta, como mínimo.** Que las dos mitades contesten la misma pregunta con la misma regla. Dos salidas coherentes, y el propietario debe elegir una:

1. **Que la reconciliación mire la tasa igual que la siembra.** Un pin se sostiene sólo mientras exista un hecho vivo **con esa tasa**; si los vivos que quedan llevan otra, el período se suelta y vuelve a resolverse. Cierra además la tercera dirección del invariante por construcción.
2. **Que la siembra no deje huecos.** Si un período migrado tiene hechos vivos discrepantes, no puede quedar simultáneamente sin pin y bloqueado.

Lo que no puede sostenerse es que la evidencia discrepante sea demasiado ambigua para *fijar* un mes y a la vez suficiente para *retenerlo* fijado a una tasa que ninguno de sus hechos lleva.

## Observaciones no bloqueantes

1. **El predicado de vitalidad tiene una tercera copia, en Python y parcial.** `comisiones.py:796` (`_pin_rated_period`) repite a mano `entry["rate_bp"] is None or entry["policy_status"] != POLICY_CANONICAL` y **omite la cláusula de venta anulada**. Hoy no es explotable, pero es la misma clase de copia parcial que costó dos generaciones.
2. **La siembra escribe su `PINNED` con `audit=False` y lo asienta aparte, con otro nombre de acción.** Tras sembrar hay 0 filas `COMMISSION_PERIOD_RATE_PINNED` en `central_audit`. Un consumidor que cuente fijaciones por la auditoría no ve las de la migración. El escritor es uno; el **formato del asiento** sigue siendo dos.
3. **`decide()` sólo está a medias dentro de la transacción del llamador.** `pinned_for(con)` resuelve con la conexión del llamador, pero `catalogue()`, `current()` e `in_force_for()` siguen abriendo la suya. No lo pude explotar, pero la firma promete más de lo que cumple.
4. **`recalculate` sobre una base migrada reprecia hacia arriba una `APROBADA` legada sin aviso adicional.** Está documentado y asentado en `replaced`, y la guarda de pago impide cobrarlo sin re-aprobación, pero es la operación que **consume** la evidencia discrepante.
5. **`recalculate` sigue evaluando liquidaciones cuya venta está anulada.** Sin efecto económico, pero consume trabajo.
6. **La única división por flotante del paquete sigue en `comisiones.py`**, dentro de la etiqueta de texto del desglose de convenio.
7. **Un período fijado por un pago consolidado conserva su tasa para siempre, aunque la política oficial cambie después.** Es la regla declarada y no la cuestiono, pero sobre bases migradas su alcance es mayor de lo que se lee: una `PAGADA` canónica @700 sembrada por la migración fija su mes al 7 % de forma permanente. Merece estar dicho explícitamente en `MIGRATION.md`, porque es dinero.

## Superficie que mi auditoría NO cubrió

- **No auditó la interfaz gráfica ejecutándose** ni verificó las capturas de `screenshots/`.
- **No verifiqué el `MANIFEST.sha256` ni el contenido del `.zip`**; es trabajo del Librarian.
- **Mi fuzz cubre nueve formas de base migrada, no todas.** Encontré `AB1-g8` en la novena; no seguí ramificando. Quedan sin explorar: convenios legados con períodos fuera de vigencia, bases con más de dos hechos discrepantes en el mismo mes, y bases con `commission_payments` legados a mano.
- **No probé `period` con formatos distintos de `AAAA-MM` y `AAAA-MM-DD`.**
- **No probé corrupción del fichero sqlite, fallos de disco a mitad de transacción, ni relojes que retroceden.**
- **No audité `sync_review_sales` ni el resto de gestión central fuera de comisiones.**
- **No medí rendimiento** ni probé con volúmenes grandes del libro append-only.
- **Mi concurrencia usa hilos sobre un mismo fichero local con WAL.** No probé procesos separados.
