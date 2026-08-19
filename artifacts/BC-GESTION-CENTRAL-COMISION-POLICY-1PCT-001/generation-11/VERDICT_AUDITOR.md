# Verdict — Auditor, generación 11
Runner: AUDITOR-IND-COMISION-POLICY-1PCT-011
Snapshot: 75d7f1b6d0ff090abe9f1c063388c38b3f2f4ab0
Veredicto: PASS

## Ataques ejecutados

Todo en scripts propios en `…\scratchpad\aud11` (`harness.py`, `t01`–`t09`), bases sqlite temporales, módulo importado con `sys.path.insert` al worktree. No se tocó el repositorio: `git status --porcelain` → **0 líneas**, `HEAD` sin mover. Regresión: `python -m pytest -q` → **456 passed**, dos corridas, misma cifra.

**0. Arnés desde BASES MIGRADAS.** `bare()` crea el esquema y le arranca todo rastro de política canónica, de modo que el paso 0 de cada corrida es el resultado de la migración oficial sobre una instalación de piloto. Cinco formas: `pilot`, `scoped` (`VENDEDORA@900` + `LOCAL@700`, la que destapó `AB1-g8`), `orphan` (pin heredado sin hecho vivo, `REVERTIDA` con tasa, venta anulada, `commission_rated_periods` de la generación 5), `discrepant` (dos `PAGADA` canónicas vivas a 700 y 100 bp) y `fulldate` (clave de período en fecha completa). Las ventas legadas llevan el `identity_key` real del módulo, así que `_apply_source_update` las alcanza de verdad.

**1. Detector verificado ANTES de usarse.** SQL propio de vitalidad y de último evento —`JOIN` sobre `MAX(id)`, sin importar `LIVE_OFFICIAL_FACT_SQL` ni `resolve_period_rate`— y aritmética propia (`Decimal`, `HALF_UP`, reimplementada). Sobre cuatro bases construidas para violar cada dirección, el detector señala las cuatro antes de abrir y tres desaparecen al abrir; la cuarta (clave cruda en el libro) persiste **por diseño**: el libro es append-only y no se reescribe, y el módulo no la lee. Direcciones: `PINNED_SIN_HECHO_VIVO`, `HECHO_VIVO_SIN_PIN`, `PIN_INCOHERENTE_CON_HECHOS_VIVOS`, más `PIN_DISTINTO_DE_HECHO_UNICO`, buena formación y clave cruda nueva. **Paso 0 limpio en las cinco formas migradas.**

**2. Fuzz encadenado desde bases migradas: 240 semillas × 60 pasos = 13.862 pasos ejecutados. Cero fallos.** Trece operaciones ponderadas hacia la cadena real, incluida la reapertura de la base y la corrección de origen. Tras **cada** paso: las tres direcciones, buena formación del libro, **que ningún `commission_amount` con `paid_at` cambie de valor**, y **5.872 comprobaciones de que todo importe pagado sigue siendo `tasa × base`**. Ni una violación.

**3. Concurrencia sobre la cadena de pago con la guarda nueva.** 25 rondas × 6 hilos con `threading.Barrier` y conexiones independientes: dos `mark_paid` de la misma liquidación ‖ `revert` ‖ `recalculate` ‖ `set_general_rate` ‖ apertura de la base. **0 errores no-`ValueError`, 0 bloqueos sqlite, 0 violaciones, 0 liquidaciones pagadas dos veces.**

**4. Migración.** Idempotente y sin mover dinero: tras cinco reaperturas de cada una de las cinco formas, las columnas monetarias, el libro completo y el recuento de auditoría son idénticos.

**5. Aritmética y estructura.** Cero `float(` y cero `round(` en los tres módulos. Un solo `ROUND_HALF_UP`, donde estaba. Un solo `INSERT` sobre `commission_period_rate_events` y **cero** `UPDATE`/`DELETE`. `_migrate_commission_policy` toca `commission_entries` sólo para reemplazar la etiqueta de política retirada, nunca un importe.

## La guarda aritmética: que cierra el agujero y que no rechaza nada legítimo

**No rechaza nada legítimo. 1.726 liquidaciones recorridas por el camino público completo, 1.726 pagadas, cero rechazos.** Para cada una de **once tasas** —0, 1, 7, 50, 100, 250, 500, 700, 999, 3.333 y 10.000 bp— y las **dos clases** de venta, sobre base migrada: publicar la tasa → registrar → `recalculate` → `review` → `approve` → `mark_paid`. Los totales se eligieron para cubrir todos los restos módulo 100 y, sobre todo, **el medio guaraní exacto**: para cada tasa se resolvió la base que hace `base × tasa / 10.000 = k + ½`, más los totales que dejan el descuento del convenio en medio guaraní exacto (10, 30, 50, 110, 1.010). Cada importe pagado se contrastó contra mi propio `HALF_UP` independiente: **cero discrepancias, cero falsos rechazos**.

Y once casos legítimos más, construidos como filas que **llegan migradas** y por tanto no pasan por `recalculate`, con el mes fijado por una `PAGADA` canónica viva a la tasa histórica: 7% (700.000), 5% (500.000), convenio al 7% (665.000 sobre base 9.500.000), convenio al 5% de 999.999 (47.500), medio guaraní exacto al 1% de 1.050 (11), al 7% de 50 (4) y al 5% de 10 (1), **tasa 0** (0), **base 0** (0), base 1 que redondea a 0, y 100% (7.777.777). **Los once se pagan. Ningún falso rechazo.** El cobro de comisiones reales no queda bloqueado.

**Cierra el escenario de los 8.900.000 Gs, con mi reproducción exacta.** Fila de procedencia externa en base migrada: `commissionable_base=10.000.000`, `rate_bp=100`, `policy_version=1`, `policy_status=CANONICA_APROBADA`, `commission_amount=9.000.000`, donde lo oficial son 100.000. `review` → **RECHAZA**, con el mensaje que nombra las tres cifras. `approve` y `mark_paid` quedan fuera de alcance porque el estado sigue en `CALCULADA`. Estado final `CALCULADA`, `paid_at=None`, **libro de tasas vacío**: el mes ni siquiera queda fijado. Variantes: 1 Gs de más, 1 Gs de menos, importe negativo y traza inventada con importe de 9.000.000 → **todas rechazadas**.

**Pero cierra la mitad reportada, no el escenario.** La guarda comprueba el importe contra la **base almacenada**; nadie comprueba la base almacenada contra la venta. Movida la invención una columna a la izquierda —`gross_amount=10.000.000`, `commissionable_base=900.000.000`, `commission_amount=9.000.000` a 100 bp, aritméticamente coherente— las tres puertas se abren, **se pagan 9.000.000 Gs, 8.900.000 Gs de sobrepago exactos**, y el mes queda `PINNED@100`: el libro afirma el 1% mientras el importe pagado es el 90%. Es el mismo perfil de alcanzabilidad que `O8-g10` (sólo fila externa; `recalculate` previo lo repara: verificado, paga 100.000), y por eso no lo cuento como bloqueante, con el mismo criterio con que no se contó `O8-g10`. Queda como `O15-g11`.

## Bloqueantes

Ninguno.

## Observaciones no bloqueantes

**O1 (heredada, abierta a propósito).** Un mes con una `PAGADA` viva al 7% cobra el 7% a las ventas posteriores. Decisión del propietario, tomada y escrita. **No la cuento como bloqueante.**

**O15-g11 — el sexto disfraz existe, es el quinto a medio cerrar, y cuesta la misma cifra.** La pregunta «¿este importe es el oficial de hoy?» sigue contestándose en dos sitios con dos criterios. `recalculate` compara **diez** campos y **re-deriva `gross_amount`, `agreement_discount` y `commissionable_base` desde `commission_sales`**. `_require_current_policy` compara ahora tasa, versión, `policy_status` y —esto es lo nuevo— el importe contra la base almacenada; pero **nunca re-deriva la base ni el bruto desde la venta**. Su criterio sigue siendo un subconjunto estricto del de `recalculate`. Consecuencias medidas: base inflada ×90 → **8.900.000 Gs de sobrepago**, la cifra íntegra de `O8-g10`; convenio sin su descuento del 5% → 100.000 en vez de 95.000, sobrepago acotado al 5% de la comisión; y el desglose de esa fila muestra «Descuento de convenio (5%): 0» sin objetar nada. El invariante `gross_amount = commissionable_base + agreement_discount` no lo comprueba nadie. La corrección natural es una línea al lado de la que se añadió: recomputar `commissionable_base(sale_kind, total)` desde la venta y exigir que coincida. **Dejo por escrito, otra vez, que la generación 11 corrigió la mitad que ya estaba reportada y no la mitad contigua** —es literalmente lo que ocurrió en `AB1-g6`, `AB1-g7` y `AB1-g8`—, para que el propietario pueda discrepar con datos delante.

**O16-g11 — «¿ya movió dinero?» tiene tres textos, y el reporte usa el más pobre.** `_was_paid` dice `status == 'PAGADA' or paid_at`; `LIVE_OFFICIAL_FACT_SQL` dice `paid_at IS NOT NULL OR boundary`; el KPI del reporte dice sólo `status == 'PAGADA'`. Reproducido: comisión pagada de 100.000 Gs y luego venta anulada → la liquidación queda `OBSERVADA` con `paid_at` puesto, `revert` la sigue rechazando por pagada, y `paid_amount` del reporte **pasa de 100.000 a 0**. El dinero salió y el mes deja de contarlo como pagado. No mueve dinero, pero descuadra el informe mensual con el que se concilia.

**O17-g11 — la traza de política de una fila externa entra al libro de tasas sin filtrarse.** Confirmada la variante que la generación 10 anotó y que la 11 no cerró: una fila con `policy_code='INVENTADO'` y `policy_scope='VENDEDORA'` pero tasa y versión correctas pasa la guarda y `approve` escribe `PINNED … 'INVENTADO','VENDEDORA'` en `commission_period_rate_events`, **resucitando en el libro el alcance por vendedora que la misión abolió**. La guarda compara `(rate_bp, policy_version)`; `policy_code` y `policy_scope` no los mira nadie.

**O11-g10 sigue en pie, mejorada.** `period_key()` existe y se usa 7 veces, pero la regla de la clave de período sigue escrita a mano 13 veces (`comision_policy.py` 6, `repository.py` 4, `comisiones.py` 2, `comisiones_ui.py` 1). Hoy todas normalizan el argumento —inocuas—; la que normalizaba el dato era `O3` y está cerrada.

**Cerrar O9 a O14 no abrió nada; las seis verificadas una por una.** `O9`: base con fijación heredada de la generación 5 **y** fila de libro con clave cruda → el `SEED_SKIPPED{SIN_HECHO_ECONOMICO_VIVO}` vuelve a escribirse, y sigue siendo uno solo tras cuatro reaperturas. `O10`: `list_entries` y `recalculate` dan el mismo resultado con `'2026-05'` y con `'2026-05-15'`. `O12`: la prueba estructural camina el árbol sintáctico, cubre `INSERT`, y sus 11 casos pasan, incluidos los tres que antes se colaban. `O13`: tres hechos vivos a `{100,700}`; al revertir uno, las tasas siguen siendo `{100,700}` pero los hechos cambian y **se asienta un segundo conflicto** —la deduplicación es por hechos y por igualdad de JSON, sin `LIKE`—. `O14`: el import duplicado ya no está. `O11` queda informativa arriba.

**Ningún importe pagado cambió de valor** en los 13.862 pasos del fuzz, en las 25 rondas de concurrencia, en las 25 reaperturas de migración ni en ninguno de los escenarios dirigidos.

## Superficie que mi auditoría NO cubrió

- **La capa de interfaz.** `comisiones_ui.py` sólo entró por `grep`.
- **Concurrencia entre procesos.** Toda la mía es multi-hilo dentro de un proceso, 25 rondas de 6 hilos.
- **Fallo de máquina.** No probé corte de energía ni `kill -9` en medio de la transacción `UNPINNED`+`PINNED`.
- **Escala.** La reconciliación de apertura recorre todos los períodos en cada arranque; no medí el coste sobre una base con años de historia.
- **El alcance de O15-g11.** Verifiqué que `recalculate`, `_apply_source_update`, `_promote_to_eligible` y `_create_entry` derivan siempre la base desde la venta, y que un `recalculate` previo repara la base inflada. No puedo demostrar que no exista una ruta pública que deje la base desalineada con la venta mientras la tasa y el importe siguen puestos.
- **El séptimo disfraz.** Encontré el sexto por lectura y construcción a mano, como los tres anteriores; mi fuzz tampoco lo habría encontrado, porque parte de bases que el sistema sabe producir. Puedo afirmar que vitalidad, decisión, escritura y lectura del libro tienen hoy un solo texto cada una. **«Cuál es el importe oficial» todavía tiene dos.**
- **El resto del paquete.** No audité `service.py`, `models.py`, las exportaciones más allá de los campos de política, ni verifiqué `TEST_EVIDENCE.md`, `MANIFEST.sha256` ni el `.zip`.
- **La decisión del propietario en sí.** `O1` es donde esa distinción cuesta dinero.
