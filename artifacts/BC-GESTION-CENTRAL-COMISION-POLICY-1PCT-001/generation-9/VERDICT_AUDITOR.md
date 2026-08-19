# Verdict — Auditor, generación 9
Runner: AUDITOR-IND-COMISION-POLICY-1PCT-009
Snapshot: f284b6c5fc2d0f31ffce7567146cce9371e9502a
Veredicto: PASS

## Ataques ejecutados

Todo el trabajo se hizo con scripts propios en `…\scratchpad\aud9` (`harness.py`, `t01`–`t09`), sobre bases sqlite temporales, importando el módulo con `sys.path.insert` al worktree. No se modificó ningún archivo del repositorio ni se hizo ningún commit: `git status --porcelain` → **0 líneas**; `git rev-parse HEAD` → `f284b6c5…`. Regresión completa: `python -m pytest -q` → **444 passed in 41.26s** (dos corridas, misma cifra).

**0. El arnés arranca de BASES MIGRADAS, no frescas.** Mi propio verdict de la generación 8 dice que el fuzz desde bases frescas no puede encontrar defectos que sólo existen en bases migradas, y esta vez el punto de partida es el ataque. `legacy_base()` construye por SQL plano una instalación de piloto anterior a la generación 9 —borra `commission_period_rate_events`, `central_audit`, `commission_policies` y `commission_policy_versions`— y luego abre la base con `CentralRepository`, de modo que **el paso 0 de cada corrida ya es el resultado de la migración oficial**. Cinco formas de base legada:

| Forma | Contenido |
|---|---|
| `pilot_legacy` | comisiones pagadas y política legada `GENERAL@700` con etiqueta retirada |
| `scoped` | **la forma que destapó `AB1-g8`**: políticas por `VENDEDORA@700` y por `LOCAL@500`, tres meses, hechos vivos con tasas distintas |
| `orphan_pins` | pines heredados sin hecho vivo, `REVERTIDA` con tasa, venta anulada, convenio legado, `commission_rated_periods` de la generación 5, períodos fuera de vigencia |
| `discrepant_paid` | dos `PAGADA` vivas del mismo mes a 700 y 100 bp, discrepancia perpetua |
| `fulldate` | base de procedencia externa con `period` en fecha completa (`2026-08-15`) |

**1. Invariante propio, en las tres direcciones, desde el paso 0 y después de cada paso.** Escribí mi propio SQL de vitalidad y de último evento —no importo `LIVE_OFFICIAL_FACT_SQL` ni `resolve_period_rate`, para no validar el código contra sí mismo— y clasifico `PINNED_SIN_HECHO_VIVO`, `HECHO_VIVO_SIN_PIN` y `PIN_INCOHERENTE_CON_HECHOS_VIVOS`. **Verifiqué el detector antes de usarlo**: sobre tres bases legadas construidas para violar cada dirección, el detector las señala las tres antes de abrir, y las tres desaparecen al abrir (`UNPINNED@100`, `PINNED@100`, `PINNED@100` respectivamente). Añadí un cuarto invariante estructural: el libro nunca repite `PINNED` sin `UNPINNED` intermedio ni escribe `UNPINNED` sin pin previo.

**2. Fuzz encadenado desde bases migradas: 220 semillas × 60 pasos = 13.200 pasos. Cero fallos.** Diez operaciones (`register_sale`, `recalculate` global y por período, `review`, `approve`, `mark_paid`, `revert`, `observe`, `void_sale`, `set_general_rate` con `{0, 100, 250, 700, 10000}` bp y tres vigencias, y **reapertura de la base** —que vuelve a correr la migración—). Después de **cada** paso: las tres direcciones del invariante, la buena formación del libro, y **que ningún `commission_amount` de una liquidación con `paid_at` cambie de valor**. Ni una violación, ni un importe pagado movido.

**3. Concurrencia (`threading.Barrier`, WAL, conexiones independientes).**

| Escenario | Rondas | Resultado |
|---|---|---|
| A — dos `revert` simultáneos que sueltan el último hecho vivo del mismo mes | 15 | invariante y libro limpios; un solo `UNPINNED` |
| B — **refijación concurrente**: mes ambiguo `{700,100,100}`, dos hilos retiran hechos distintos, uno de ellos provoca `UNPINNED`+`PINNED` en la misma transacción | 15 | sin secuencia nueva; nunca dos `PINNED` seguidos |
| E — apertura de la base ‖ `revert` ‖ `void_sale`, 9 hilos, 6 meses | 25 | **0 errores sqlite**; invariante limpio |
| F — martillo de 200 `BEGIN IMMEDIATE` contra 120 aperturas de `CentralRepository` | 1 | **0 aperturas fallidas**; ni un `database is locked`, ni un `BUSY_SNAPSHOT` |
| Concurrencia `set_general_rate` ‖ `approve`+`mark_paid` ×2 ‖ `recalculate` | 20 | 0 errores sqlite; **ninguna `PAGADA` cobra distinto del pin de su período** |

Presté atención específica a que `migrate()` **no** corre bajo `BEGIN IMMEDIATE` sino en transacción diferida, y a que ahora escribe (`UNPINNED`) donde antes sólo sembraba: no logré producir con ello ni un error de bloqueo ni un pisado. El `busy_timeout` por defecto de 5 s del módulo `sqlite3` y el hecho de que `_migrate_commission_policy` ejecute DML antes que las lecturas de reconciliación cubren la ventana.

**4. Secuencias largas fijar/soltar/refijar con tasas distintas.** 400 operaciones aleatorias (`revert`, `observe`, `void_sale`, `mark_paid`, `recalculate`, reapertura) sobre un mes con seis hechos a `{100,250,700,100,250,700}`; y las 13.200 del fuzz, que incluyen refijaciones reales a otra tasa. Invariante y libro limpios en todos los pasos.

**5. Estructura: ¿queda una cuarta copia?** `grep` regex sobre `comisiones.py`, `repository.py`, `comision_policy.py` y `comisiones_ui.py`:

- `UPDATE`/`DELETE` sobre `commission_period_rate_events`: **cero**. Un solo `INSERT`, en `record_period_rate_event`.
- Lista literal `'APROBADA','PAGADA'` fuera de `BOUNDARY_SQL_IN`: **cero**.
- `policy_status='CANONICA_APROBADA'` en SQL fuera de `LIVE_OFFICIAL_FACT_SQL`: **cero**.
- `paid_at IS NOT NULL` y `COALESCE(s.voided…)` en SQL: **una sola aparición cada uno, en `comision_policy.py`**.
- `LIVE_OFFICIAL_FACT_SQL`, `PERIOD_MATCH_SQL`, `BOUNDARY_SQL_IN` y `RATING_BOUNDARY_STATES` siguen importados en `comisiones.py` pero **ya no se usan**: el módulo delega entero en el repositorio. No queda ninguna copia parcial del predicado ni de la decisión.
- La decisión (`resolve_period_rate`) tiene un solo llamador de verdad, `reconcile_period_rate`, y éste un solo escritor.

Lo que **sí** sigue escrito más de una vez es la pregunta *«¿qué dice el libro hoy?»* (tres formulaciones) y la *normalización de la clave de período* al leer el libro (una mitad normaliza, la otra no). Ninguna de las dos mueve dinero hoy; van como observaciones, porque son la forma residual del patrón.

**6. Aritmética y ausencia de floats.** Cero `float(` y cero `round(` en los cuatro ficheros; `ROUND_HALF_UP` y el único `quantize` siguen sólo en `comision_policy.py`, con `prec=60`. Tabla verificada exacta: `50×1%→1`, `150×1%→2`, `49×1%→0`, `1.234.567×1%→12.346`, `999.999×5%→50.000`, `2.500.000.000.000×1%→25.000.000.000`, `1×100%→1`.

**7. La migración no escribe `commission_entries`.** Hash SHA-256 de la tabla completa **idéntico tras cinco reaperturas** de una base viva con `PAGADA@700`, `CALCULADA@100`, `REVERTIDA@900` y un pin heredado huérfano. La reconciliación de apertura escribió lo correcto —`UNPINNED` del pin de `2026-05` que ya nada sostenía, `PINNED@700` en `2026-08`— y **no volvió a escribir nada** en las cuatro reaperturas siguientes: 3 eventos antes, 3 eventos después. Auditoría sin duplicar: una sola fila `SEED_SKIPPED` por período tras cuatro reaperturas.

**8. Propiedades de `resolve_period_rate` en aislamiento.** Vacío → `None`. Tasas distintas → `AMBIGUOUS`. Un pago gana a una aprobación aunque sea más nuevo. **Estable ante el orden de lectura**: la misma lista permutada devuelve el mismo hecho.

## Reproducción de AB1-g8 y de las rutas de AB1-g6 sobre base migrada discrepante

**AB1-g8 — CERRADO. Los 29.700.000 Gs desaparecen.** Escenario exacto del verdict de la generación 8 (`t09_ab1g8_exact.py`): políticas de piloto `VENDEDORA:Vendedora Vieja@900` y `LOCAL:Optica Asuncion@700`, liquidaciones `e-V APROBADA@900` y `e-L PAGADA@700` del mismo mes `2099-04`, base **migrada** por el código de la generación 9. Corrido por las cuatro rutas de retirada del hecho:

```
paso 0: SEED_SKIPPED {"entries":["e-V","e-L"],"rates_bp":[700,900],"reason":"EVIDENCIA_DISCREPANTE"}
        libro=[]   inv=[]        <-- la 8 daba aqui HECHO_VIVO_SIN_PIN
1) publish 10000bp eff 2099-01-01
2) venta de 2099-04 por 10.000.000 -> recalculate/review/approve
   libro = PINNED@700            <-- la 8 daba PINNED@10000
3) revert / void_sale / observe+revert / revert_payment
   libro = PINNED@700   inv=[]   <-- la 8 daba PIN_INCOHERENTE (pin@10000 vs vivos [700])
4) publish 100bp; policy_for_period(2099-04) -> rate_bp 700
5) tres ventas REALES de 10.000.000 Gs: pagan 2.100.000 Gs
   libro completo: [PINNED@700 origin=COMMISSION_POLICY_REPAIRED]
   importe de e-L intacto: 70.000 Gs @700
```

El pin al 100 % **ya no llega a existir**: `recalculate` repara `e-V` —que llevaba una tasa que ninguna política vigente sostiene—, con lo que el mes deja de ser ambiguo y se fija a los 700 bp que su `PAGADA` viva sí lleva; a partir de ahí `_require_current_policy` **rechaza aprobar la liquidación del tipeo a 10000 bp**. Los **29.700.000 Gs de sobrepago de la generación 8 caen a 0**. El importe de `e-L` no se tocó, y `resolve_period_rate` decidió una sola vez para las dos mitades.

Queda un residuo de 1.800.000 Gs en ese escenario, pero **no es el bloqueante**: es el mes al 7 % gobernando ventas nuevas, que es la semántica que el propietario decidió. Va cuantificado en las observaciones.

**Las cuatro rutas de AB1-g6 sobre base migrada discrepante — CERRADAS, con daño 0** (`t05_g6routes.py`). Base migrada con el piloto `VENDEDORA@700` + `LOCAL@500` de `2026-08` vivo; se ataca `2026-09`, publicando 10000 bp, aprobando y retirando el hecho por cada ruta:

| Ruta que retira el hecho | Pin antes | Pin después | Venta real de 2026-09 paga | Daño |
|---|---|---|---|---|
| `revert` de la aprobación | `PINNED@10000` | **`UNPINNED@10000`** | 100.000 Gs | **0 Gs** |
| `void_sale` (regla aprobada 8) | `PINNED@10000` | **`UNPINNED@10000`** | 100.000 Gs | **0 Gs** |
| `revert_payment` (cheque rechazado) | `PINNED@10000` | **`UNPINNED@10000`** | 100.000 Gs | **0 Gs** |
| `observe` + `revert` | `PINNED@10000` | **`UNPINNED@10000`** | 100.000 Gs | **0 Gs** |

Las cuatro sueltan, las cuatro dejan las tres direcciones del invariante limpias y el libro bien formado, y las cuatro hacen que la venta real posterior cobre sus 100.000 Gs oficiales en vez de 10.000.000. Los 9.900.000 Gs por venta de `AB1-g6` y los 29.700.000 Gs de `AB1-g8` no se reproducen por ninguna ruta.

**Semántica nueva — verificada, y verificada como inocua para el dinero ya pagado.** En las 13.200 transiciones del fuzz, en las 400 de la secuencia larga y en los cinco escenarios dirigidos, **ningún `commission_amount` de una liquidación con `paid_at` cambió jamás de valor**. `recalculate` cuelga `paid_at IS NULL` del `WHERE` entero y `_apply_source_update` manda a `OBSERVADA` todo lo revisado, aprobado o pagado. **No encontré ninguna ruta —pública, por combinación ni por concurrencia— por la que un importe pagado cambie de valor.** Un mes con dos `PAGADA` vivas a tasas distintas nunca se fija (discrepancia perpetua, correctamente asentada) y las ventas nuevas de ese mes cobran el 1 % canónico.

## Bloqueantes

Ninguno.

## Observaciones no bloqueantes

**O1 — Un mes con una `PAGADA` legada al 5 % o al 7 % cobra esa tasa también a las ventas registradas después, sin ninguna ruta de liberación. Cuantificado: 400.000 Gs por venta de 10.000.000 Gs en un mes al 5 %, 600.000 Gs en uno al 7 %; 1.200.000 Gs y 1.800.000 Gs respectivamente en las reproducciones de tres ventas.** Es la consecuencia directa —y honestamente documentada— de la decisión del propietario. No la declaro bloqueante porque está decidida y escrita. La señalo porque la justificación escrita es *«no reescribir historia»* y el efecto observable va en la otra dirección: la historia gobierna dinero futuro. Una `PAGADA` viva no se suelta por ninguna vía, de modo que **un solo pago legado de agosto fija agosto al 7 % para siempre**, y `set_general_rate(100, 2026-08-01)`, `recalculate` y reabrir la base tres veces lo dejan intacto (verificado). Merece una confirmación explícita antes de producción.

**O2 — La pregunta «¿qué dice el libro hoy?» está escrita en tres sitios.** `comisiones.py:124 _last_period_rate_event` y `repository.py:374` contienen **el mismo texto SQL** duplicado literalmente, y `comisiones.py:132 _pinned_periods_from` lo formula por tercera vez con un `JOIN` sobre `MAX(id)`. Hoy las tres coinciden. Pero la decisión se unificó en `resolve_period_rate` y la escritura en `record_period_rate_event`, mientras que **la lectura del estado actual quedó fuera de esa unificación**: es el único sitio donde una corrección futura puede volver a tocar una mitad y no la otra.

**O3 — La normalización de la clave de período sólo se aplica a una de las dos mitades del `UNION` de la reconciliación de apertura.** Una fila de libro legada con clave en fecha completa —`2026-08-15`— sobrevive intacta a toda reapertura. **Es económicamente inerte** —`pinned_for` y `decide()` normalizan a `[:7]`— **pero contamina la auditoría**: la publicación siguiente asienta `"protected_periods": ["2026-08","2026-08-15"]`, es decir, declara protegido un período que no existe.

**O4 — `_audit_seed_once` deduplica por `action`+`target`, así que la segunda discrepancia distinta de un mismo período es silenciosa.** La guarda es correcta para su propósito original pero `reconcile_period_rate` la usa también en caliente, donde el conflicto sí es un hecho nuevo cada vez.

**O5 — Un conflicto detectado en caliente se asienta a nombre de `MIGRACION`.** `_audit_seed_once` fija `actor="MIGRACION"` en duro, ignorando el `actor` que `reconcile_period_rate` recibió.

**O6 — `recalculate` puede necesitar dos pasadas para converger sobre un mes migrado ambiguo.** Reparar una liquidación puede deshacer la ambigüedad del mes y fijarlo, con lo que las liquidaciones evaluadas después ven el pin y las evaluadas antes no. **No hay divergencia final ni pago incorrecto**: `_require_current_policy` rechaza aprobar la versión desactualizada y la segunda pasada converge.

**O7 — `recalculate` y `list_entries` filtran el período con `period=?` literal, no con `PERIOD_KEY_SQL`.** Sobre una base de procedencia externa con `period` en fecha completa, `recalculate(period='2026-08')` no alcanza esas filas. Es un filtro, no la decisión, y `recalculate()` sin período sí las alcanza.

## Superficie que mi auditoría NO cubrió

- **La capa de interfaz.** Sólo entró por `grep` estructural. No ejecuté ni una interacción de pantalla.
- **Concurrencia entre procesos.** Toda mi concurrencia es multi-hilo dentro de un proceso. El punto que más me preocupaba —que `migrate()` corre en transacción **diferida** y ahora escribe— no produjo un solo error, pero un `BUSY_SNAPSHOT` entre procesos con timings distintos no queda descartado por mi evidencia.
- **Fallo de máquina.** No probé corte de energía ni `kill -9` en medio de la transacción `UNPINNED`+`PINNED`. La atomicidad de la refijación la deduzco de que ambos eventos van en la misma transacción, no de haberla interrumpido.
- **Escala.** La reconciliación de apertura ahora recorre **todos** los períodos de la base en cada arranque. No medí el coste de abrir una base con años de historia.
- **El resto del paquete.** No audité `service.py`, `models.py`, el reporte mensual ni las exportaciones más allá de los campos que toca la política; no verifiqué las cifras de `TEST_EVIDENCE.md` ni el `.zip`.
- **La decisión del propietario en sí.** Verifiqué que el código hace lo que la documentación dice; **no** puedo verificar que sea lo que el propietario quiso. O1 es precisamente el punto donde esa distinción cuesta dinero.
- **Un quinto disfraz del patrón.** Encontré cuatro parejas de textos que responden preguntas relacionadas (O2, O3, O7) y ninguna mueve dinero hoy. No puedo afirmar que no exista una quinta: las tres anteriores se encontraron leyendo, no fuzzeando, y mi fuzz tampoco habría encontrado O3 —lo encontré construyendo a mano la base que lo expone.
