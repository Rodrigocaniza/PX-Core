# Verdict — Auditor, generación 10
Runner: AUDITOR-IND-COMISION-POLICY-1PCT-010
Snapshot: bdc4f53fb8b3095ead16fbeadcc3d23ca6f2f2d8
Veredicto: PASS

## Ataques ejecutados

Todo el trabajo se hizo con scripts propios en `…\scratchpad\aud10` (`harness.py`, `fuzz.py`, `t01`–`t10`), sobre bases sqlite temporales, importando el módulo con `sys.path.insert` al worktree. No se modificó ningún archivo del repositorio ni se hizo ningún commit: `git status --porcelain` → **0 líneas**. Regresión completa: `python -m pytest -q` → **453 passed** (dos corridas, misma cifra).

**0. El arnés sigue arrancando de BASES MIGRADAS.** `bare_schema()` construye el esquema y borra el rastro de política, de modo que el paso 0 de cada corrida es el resultado de la migración oficial sobre una instalación de piloto. Cinco formas: `pilot`, `scoped` (**la que destapó `AB1-g8`**: `VENDEDORA@900` + `LOCAL@700`), `orphan` (pin heredado sin hecho vivo, `REVERTIDA` con tasa, venta anulada, `commission_rated_periods` de la generación 5), `discrepant` (dos `PAGADA` vivas a 700 y 100 bp) y `fulldate` (clave de período en fecha completa).

**1. Detector verificado antes de usarse.** SQL propio de vitalidad y de último evento —`JOIN` sobre `MAX(id)`, no importo `LIVE_OFFICIAL_FACT_SQL` ni `resolve_period_rate`—. Sobre cuatro bases construidas para violar cada dirección, el detector señala las cuatro antes de abrir y las cuatro desaparecen al abrir. Direcciones: `PINNED_SIN_HECHO_VIVO`, `HECHO_VIVO_SIN_PIN`, `PIN_INCOHERENTE_CON_HECHOS_VIVOS`, más `PIN_DISTINTO_DE_HECHO_UNICO`, buena formación del libro y clave escrita sin normalizar.

**2. Fuzz encadenado desde bases migradas: 220 semillas × 60 pasos = 13.200 pasos. Cero fallos.** Catorce operaciones ponderadas hacia la cadena real, incluida la **reapertura de la base**. Tras **cada** paso: las tres direcciones, la buena formación del libro y **que ningún `commission_amount` con `paid_at` cambie de valor**. Ni una violación, ni un importe pagado movido.

**3. Concurrencia sobre la superficie nueva.** 20 rondas de 6 hilos con `threading.Barrier` y conexiones independientes: `recalculate` global ‖ `recalculate` por período ‖ dos `revert` que sueltan hechos del mismo mes ‖ `set_general_rate` ‖ apertura de la base. **0 errores de bloqueo sqlite, 0 violaciones del invariante.**

**4. Reproducción de `AB1-g8` con el escenario exacto.** Paso 0: `SEED_SKIPPED{rates_bp:[700,900]}`, libro vacío, invariante limpio. Publicar 10000 bp, registrar venta, recalcular, aprobar: el libro queda en `PINNED@700` —nunca en `PINNED@10000`— y la venta nueva de 10.000.000 Gs liquida **700.000 Gs**. Los 29.700.000 Gs de sobrepago de la generación 8 siguen en 0.

**5. Aritmética, floats y estructura.** Cero `float(` y cero `round(`. Tabla exacta verificada. Cero `UPDATE`/`DELETE` sobre el libro; un solo `INSERT`; **una sola** aparición de `ORDER BY id DESC LIMIT 1` y **cero** `JOIN` sobre `MAX(id)`.

**6. La migración no escribe `commission_entries`.** Hash de la tabla idéntico tras cinco reaperturas. 2 eventos antes, 2 después; 4 filas de auditoría antes, 4 después.

## Verificación de que cerrar O2, O3, O4, O5, O7 y L3-g9 no abrió nada

**L3-g9 — probado por dos vías independientes.**

*Vía diferencial.* Reconstruí la generación 9 desactivando **exactamente** las reconciliaciones nuevas, por nombre de acción (`COMMISSION_RECALCULATED`, `SOURCE_UPDATED`, `SALE_CANCELLED`), dejando vivas las de la 9. Sobre cada estado alcanzado por el fuzz (60 semillas × 20 pasos, cinco formas de base legada) copié la base y corrí la misma operación en las dos versiones, comparando el hash de `commission_entries`, el libro completo y el valor devuelto. **4.952 comparaciones, 0 diferencias.** De ellas, 120 escribieron el libro: las escribieron **las dos** versiones, idénticamente.

*Vía instrumentación.* Envolví `reconcile_period_rate` y conté llamadas y escrituras por origen durante las 13.200 transiciones. Los tres sitios nuevos suman **1.177 llamadas** (`COMMISSION_RECALCULATED` 871, `SALE_CANCELLED` 171, `SOURCE_UPDATED` 135) y **0 escrituras**.

*Y qué pasa si alguna vez sí escriben.* Desalineé el libro a mano y comparé lo que escribe la reconciliación de apertura con lo que escribe `recalculate`: escriben **la misma reparación**; sólo cambian `origin` y `actor`. La conclusión es estructural: los cuatro sitios llaman a la misma función de decisión, así que añadir llamadas sólo puede añadir reparaciones idénticas.

**O2 — la lectura unificada no alteró ninguna decisión.** Reimplementé las **tres** formulaciones de la generación 9 y las comparé con la única de la 10 sobre ocho libros × cinco períodos × tres vigencias. `last_period_rate_event`: **0 diferencias**. `pinned_periods_from`: seis diferencias, **todas y sólo** en libros con clave cruda, y todas en la dirección correcta.

**O3 — la normalización no cambió a qué período pertenece nada.** Diferencial de la apertura completa sobre siete bases: `commission_entries` idéntico en las siete, libro idéntico en las siete. Verificado además que la publicación ya no declara el mes fantasma. Única diferencia: una nota de auditoría que se pierde (ver observaciones).

**O4 y O5 — cerradas, y verificadas juntas.** Base con tres hechos vivos a 700/100/250 bp: la apertura asienta `SEED_SKIPPED{[100,250,700]}` a nombre de `MIGRACION`. Al revertir en caliente el de 250 bp, el conflicto pasa a `{100,700}` y **se asienta una segunda fila**, a nombre de `sol`.

**O7 — cerrada.** `list_entries(period='2026-08')` devuelve las dos filas de clave cruda y `recalculate(period='2026-08')` las evalúa y corrige.

**Ninguna `PAGADA` cambió de importe** en las 13.200 transiciones del fuzz, en las 4.952 comparaciones diferenciales, en las 20 rondas de concurrencia ni en los escenarios dirigidos.

## Bloqueantes

Ninguno.

## Observaciones no bloqueantes

**O1 (heredada, abierta a propósito).** Un mes con una `PAGADA` viva al 7 % cobra el 7 % a las ventas registradas después: la venta nueva de 10.000.000 Gs liquida 700.000 Gs en vez de 100.000. Es la decisión del propietario, tomada y escrita. **No la cuento como bloqueante.**

**O8-g10 — el quinto disfraz del patrón existe, y esta vez toca dinero: «¿el importe de esta liquidación es el oficial de hoy?» se contesta en dos sitios con dos criterios distintos.** `recalculate` compara **diez** campos. `_require_current_policy` —la guarda de `review`, `approve` y `mark_paid`— compara **sólo** `(rate_bp, policy_version)`, más que `policy_status` sea canónico y que ni la tasa ni el importe sean nulos. **Nunca compara el importe con `commission_for(base, rate)`.** Construí una base cuya liquidación lleva la tasa y la versión que `decide()` dará hoy, y un `commission_amount` de 9.000.000 Gs sobre una base de 10.000.000: `review` → `approve` → `mark_paid` **pasan las tres**, se pagan 9.000.000 Gs —**8.900.000 Gs de sobrepago**— y el mes queda fijado a 100 bp, de modo que el libro afirma que el mes está al 1 % mientras el importe pagado es del 90 %. Variantes verificadas: `gross_amount` divergente también pasa; y una traza inventada pasa igual y **entra al libro de tasas**, resucitando un alcance por vendedora que la misión abolió. El propio docstring de la guarda dice «*No alcanza con que haya un importe, ni con que lleve el sello `CANONICA_APROBADA`*»: como está escrita, sí alcanza. **No la declaro bloqueante** por tres razones que dejo por escrito para que el propietario pueda discrepar: (1) no es alcanzable por ninguna ruta pública —`recalculate` y `_apply_source_update` escriben siempre el importe con `commission_for`, y un `recalculate` previo lo repara—; (2) no es alcanzable desde ninguna base que este sistema pueda producir, sólo desde una fila incoherente de procedencia externa; (3) **no la abrió la generación 10**. Pero es el mismo patrón que costó `AB1-g6`, `AB1-g7` y `AB1-g8`, y es el primero de la serie que la guarda no cubre.

**O9-g10 — cerrar O3 se llevó por delante una nota de auditoría.** `known` ahora se normaliza, así que una fila de libro con clave cruda hace que su mes cuente como «ya conocido» y se **suprima** el `SEED_SKIPPED{SIN_HECHO_ECONOMICO_VIVO}` que la generación 9 sí escribía. No mueve dinero, pero es exactamente la forma del patrón.

**O10-g10 — el argumento de `recalculate(period=)` y `list_entries(period=)` pasó a exigir `AAAA-MM`.** El filtro es ahora `substr(period,1,7)=?` contra el valor almacenado; el **argumento** no se normaliza. El efecto práctico es nulo, pero la asimetría entre normalizar el dato y no normalizar el argumento es la que produjo O3.

**O11-g10 — la regla de la clave de período sigue escrita nueve veces.** `PERIOD_KEY_SQL` en SQL y `[:7]` en ocho sitios de Python. Hoy todas normalizan el **argumento** —idempotentes e inocuas—; O3 era la única que normalizaba el **dato**.

**O12-g10 — la garantía estructural nueva cubre `UPDATE`, no `INSERT`.** `_create_entry` escribe `status` con un `INSERT` y no reconcilia; hoy es correcto, pero una ruta futura que inserte una `APROBADA` no la detendría nada. Además el `zip(escriben, nombres)` empareja cuerpos en orden de fichero con nombres ordenados alfabéticamente.

**O13-g10 — `_audit_conflict_once` deduplica por conjunto de tasas, no por conjunto de hechos.** Dos conflictos con las mismas tasas pero distintas liquidaciones se asientan una sola vez. Menor: hace un `LIKE` sin índice sobre `central_audit` en cada reconciliación de un mes ambiguo.

**O14-g10 — `comisiones.py` importa `CentralRepository` dos veces, en líneas consecutivas.** Inocuo; ruido introducido por esta generación.

**O6-g9 sigue en pie.** El diferencial demuestra que `recalculate` se comporta exactamente igual que en la 9.

## Superficie que mi auditoría NO cubrió

- **La capa de interfaz.** Sólo entró por `grep` y por la lectura del llamador de `recalculate`.
- **Concurrencia entre procesos.** Toda mi concurrencia es multi-hilo dentro de un proceso, 20 rondas de 6 hilos.
- **Fallo de máquina.** No probé corte de energía ni `kill -9` en medio de la transacción `UNPINNED`+`PINNED`.
- **Escala.** La reconciliación de apertura recorre todos los períodos en cada arranque y `pinned_periods_from` hace una consulta por período. No medí el coste sobre una base con años de historia.
- **El alcance de O8-g10.** Verifiqué que no hay ruta pública ni base producible por el sistema que lo alcance, revisando los cuatro escritores de `commission_amount` y los tres de `gross_amount`. No puedo demostrar que no exista un cuarto camino.
- **El resto del paquete.** No audité `service.py`, `models.py`, el reporte mensual ni las exportaciones más allá de los campos de política; no verifiqué las cifras de `TEST_EVIDENCE.md`, el `MANIFEST.sha256` ni el `.zip`.
- **La decisión del propietario en sí.** O1 es donde esa distinción cuesta dinero.
- **Un sexto disfraz.** Encontré el quinto (O8-g10) leyendo y construyendo a mano, no fuzzeando. Mi fuzz tampoco lo habría encontrado. Puedo afirmar que las cuatro preguntas centrales —vitalidad, decisión, escritura y ahora lectura del libro— tienen hoy un solo texto cada una.
