# VERDICT — LIBRARIAN (revisión independiente de veracidad documental)

| Campo | Valor |
|---|---|
| Runner | `LIBRARIAN-IND-COMISION-POLICY-1PCT-005` |
| Rol | LIBRARIAN (independiente) |
| Misión | `BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001` |
| Generación | 5 |
| Snapshot revisado | `2ac9f5c93ec99ed506133310ee6cd19f6779b971` (verificado con `git rev-parse HEAD`) |
| Base de la misión | `e7732603d9eb098867a272598e6d30803a4f1ac3` (verificada) |
| Árbol al empezar / al terminar | limpio / limpio (`git status --porcelain` sin salida en ambos extremos) |
| Temporales | `…\scratchpad\lib-gen5` (fuera del repositorio) |
| Modificaciones al repositorio | ninguna. Sin `add`, `commit`, `checkout`, `push` |
| Fecha UTC | 2026-08-18T02:30:43Z |
| **VEREDICTO** | **FAIL** — 6 bloqueantes |

---

## 1. Cierre de B1-g4 y B2-g4 (verificado por mi cuenta, contra el código)

**B1-g4 — CERRADO.** La protección dejó de ser un predicado sobre el estado actual.
`CanonicalCommissionPolicy.decide()` consulta `pinned_for(period)` —fila de `commission_rated_periods`— **antes** que el catálogo, y devuelve la tasa fijada. La tabla se declara con `period TEXT PRIMARY KEY` y se escribe con `INSERT OR IGNORE`; no hay `UPDATE` ni `DELETE` sobre ella en ninguna ruta. Ejecuté la matriz y la fuga literal del Auditor:

```
python -m pytest -q tests/gestion_central/test_comisiones.py \
  -k "far_future or no_public_transition or observing_a_paid"
16 passed, 98 deselected in 1.85s
```

`set_general_rate` ya no consulta estados: `grep` sólo devuelve la **definición** de `SETTLED_STATES` (ya sin usos) y ningún `MAX(period)`; la única consulta de máximo es `MAX(effective_from)`. La restricción del propietario —no usar `MAX(period)` global— se cumple.

**B2-g4 — CERRADO.** `_apply_source_update` escribe el mismo bloque `replaced`, con el mismo nombre y los mismos tres campos que `recalculate`, condicionado a que hubiera tasa o importe previos.

Ambos cierres son reales. **El FAIL de este verdict no los revierte**: es documental, y todos los bloqueantes que siguen son afirmaciones del paquete demostrablemente falsas contra el código o contra el artefacto en **este** snapshot.

---

## 2. Verificaciones ejecutadas

### 2.1 Cifras (todas ejecutadas, ninguna estimada)

| Cifra declarada | Resultado |
|---|---|
| Regresión **371** | `371 tests collected` ✅. En ejecución: `369 passed, 2 errors` — los 2 son `TclError` de Tk al correr la suite completa en esta sesión; aislados pasan. No es un fallo del código de la misión ✅ |
| Suite del módulo **171** | `171` ✅ |
| **120** entre los dos ficheros de comisiones | 114 + 6 ✅ |
| **114** / **6** | `114` / `6` ✅ |
| **94** funciones en `test_comisiones.py` | `94`; base `e773260` → `47`; 47+48−1 = 94 ✅ |
| **13** funciones nuevas de la gen 5 | AST-diff `5652e46` vs HEAD: 81 → 94 = **+13** neto (15 nombres nuevos − 2 renombrados) ✅ |
| **26** casos nuevos (345 → 371) | conteo AST sobre `5652e46` = **88**; 114 − 88 = 26; 371 − 26 = **345** ✅ |
| **69** añadidos (67 dominio + 2 interfaz) | 114−47=67, 6−4=2 ✅ |
| **14** transiciones | 14 tuplas en `TRANSITIONS`; composición 4 `observe` + 3 `revert` + 3 `void_sale` + 4 correcciones/cobro ✅ |
| **29** hallazgos | `WORKFLOW` 29, `HANDOFF` 29 ✅ (pero ver bloqueante 3: **el contenido del 23 y del 25 no coincide con la realidad**) |
| **36** manifest / **37** ZIP | 36 entradas, **36/36 hash OK**; ZIP 37 miembros, **37 byte-idénticos, 0 mismatch** ✅ |
| **12** verdicts | 12 presentes en el ZIP y en el manifest; `generation-5/` vacío ✅ |
| `contract_version` **3** | `3`, con `policy` = política **del período** (incluye `pinned`) y `current_policy` aparte ✅ |
| **18 de 36** con CRLF | **18** exactos: **15 de 22** `.md`, **1 de 2** `.json`, **2 de 8** `.py` ✅ **en `ARTIFACT_CONSISTENCY.md` y `HANDOFF.md`** (ver bloqueante 3 para `WORKFLOW.json`) |
| Captura | 93.307 bytes, 1920×1080, RGB, `4c616c0c…5019e` ✅ |
| Consistencia | `PAQUETE CONSISTENTE` ✅ |

### 2.2 La representación declarada es la que usa el código

- Una fila por período: `period TEXT PRIMARY KEY`. ✅
- Append-only: sólo `INSERT OR IGNORE` en dos sitios; ningún `UPDATE`/`DELETE` fuera del *helper* de pruebas. ✅
- `decide()` resuelve por la fila antes que por el catálogo. ✅
- La siembra sólo cubre tarifaciones canónicas: `rate_bp IS NOT NULL AND policy_status = 'CANONICA_APROBADA'`. ✅
- `set_general_rate` ya no bloquea; la publicación asienta `protected_periods` y `protected_periods_count`. ✅

### 2.3 Otras comprobaciones del protocolo

Base exacta en los tres documentos ✅. `SINTETICA_PENDIENTE_APROBACION` sólo en `RETIRED_POLICY_STATUSES` ✅. *Code spans* balanceados ✅. Ninguna regla canónica anterior redocumentada contradiciéndola ✅. Verdicts 1-4 sin retocar, incluida la nota del Librarian de la generación 4 ✅. `INDEPENDENCE.md` cuenta bien la generación 4: **14** = 7 + 4 + 3 ✅. Cinco ficheros tocados fuera de `artifacts/` y `comision_policy.py` intacto ✅.

---

## 3. Bloqueantes

### L1-g5 — `TEST_EVIDENCE.md` afirma una aserción que no existe y una ruta que no está cerrada

> «…es exactamente lo que B1 **prohíbe desde ahora**. Conserva su intención intacta … y **gana** una aserción: que la ruta pública está cerrada (`pytest.raises(..., "ya fue liquidado")`).»

```
$ grep -rn "ya fue liquidado" tests/ modulos/ --include=*.py
(sin resultados)
```

La prueba fue reescrita en la generación 5: la aserción de excepción desapareció y la deriva se reconstruye borrando la evidencia con `clear_rated_periods`. Y la ruta pública **no** está cerrada: publicar ya no se rechaza por período liquidado. Es una reliquia literal de la guarda por estado, en el documento que describe las pruebas.

### L2-g5 — `TEST_EVIDENCE.md` declara «cuatro pruebas» y enumera seis

La enumeración que sigue son tres viñetas con **dos** nombres cada una = **seis**, y seis es el número real: cuatro modificadas conservando el nombre más dos renombradas y reescritas. Las dos renombradas no pueden contarse como nuevas sin romper la cifra **13**. El documento se contradice consigo mismo en la misma frase. Es el mismo género de recuento que produjo G2-L1, G2-L2, G3-L1 y G3-L2.

### L3-g5 — `WORKFLOW.json`, hallazgo 23: «21 de 33 ficheros con CRLF»

`HANDOFF.md` y `ARTIFACT_CONSISTENCY.md` dicen, correctamente, **18 de 36**. El manifest de este snapshot tiene 36 entradas, no 33. La cifra de `WORKFLOW.json` es la de la generación 4 y hoy es falsa por los dos lados. Además desmiente la afirmación de que «`HANDOFF.md` y `WORKFLOW.json` comparten los mismos 29 hallazgos»: comparten los identificadores, no el contenido.

### L4-g5 — El hallazgo 25 describe como abierta una guarda que ya no existe

> «…**la guarda usa `MAX(period)` global**…», bajo el epígrafe «abiertos y no corregidos».

No existe ningún `MAX(period)` en el código, y el propio paquete demuestra lo contrario en `TEST_EVIDENCE.md` § «Hallazgo 25: sin frontera global por `MAX(period)`», con su prueba en verde. El paquete declara abierto y no corregido un hallazgo que su propia sección de pruebas presenta como imposible. Segunda reliquia, y ésta infla el backlog de 29.

### L5-g5 — `COMMISSION_POLICY_1PCT.md` invoca «la guarda de período liquidado» como razón vigente

> «…publicar una vigencia que alcance ese período **está prohibido por la guarda de período liquidado**.»

Esa guarda fue retirada en esta misma generación. El documento lo dice él mismo veinte líneas antes. La conclusión sigue siendo cierta, pero **por otro motivo**: la guarda de retroceso. La razón declarada es falsa contra el código y contradice el mismo documento. Tercera reliquia.

### L6-g5 — `HANDOFF.md` afirma que el rótulo de la captura «coincide»; no coincide

Reproduje el escenario exacto del capturador contra este código:

```
pinned: True
Comisión oficial 1,00% de la base · COMISION_GENERAL_1PCT v1 · vigente desde 2026-08-01 · fijada al tarifarse · redondeo HALF_UP a Gs. enteros
```

El `recalculate` del capturador tarifa `2099-04`, de modo que `pinned` es **True** y la interfaz inserta « · fijada al tarifarse». `VISUAL_EVIDENCE.md` transcribe el encabezado **sin** ese fragmento; la prueba de interfaz sólo comprueba subcadenas, así que no cubre la diferencia. La frase de `HANDOFF.md` existe precisamente para justificar no regenerar la captura, y es falsa.

---

## 4. Observaciones no bloqueantes

1. **«Publicar siempre es posible» es absoluto y no lo es.** Publicar una vigencia hacia atrás se rechaza. El sentido pretendido —ya no se bloquea por período liquidado— es correcto y `COMMISSION_POLICY_1PCT.md` lo enuncia con precisión; por eso no lo elevo.
2. **La matriz no es el producto completo, aunque el texto lo sugiere.** Faltan al menos `void_sale` desde `REVISADA` y `revert` desde `OBSERVADA`, ambas legales. Sin consecuencia económica, pero la afirmación de exhaustividad es más ancha que la matriz.
3. **`WORKFLOW.policy_decision_b1` se conserva sin marca de superado.** Su regla ya no describe el código; los bloqueantes `B1`/`B2` sí llevan `SUCEDIDO_POR_…`, este bloque no.
4. **Reliquias en las cadenas de documentación del código** (no son afirmaciones del paquete): dos comentarios en `test_comisiones.py` siguen hablando de la prohibición retirada.
5. **`SETTLED_STATES` queda definida y sin ningún uso.** Una constante muerta con ese nombre invita a reintroducir la guarda derribada.
6. **Carryovers ya registrados**, sin cambio: hallazgos 3, 22 y 27.
7. **Los 2 errores `TclError`** de la corrida completa son de entorno (Tk), no del código: los dos tests pasan aislados.

---

## 5. VEREDICTO

# **FAIL**

El diseño de la generación 5 es sólido y lo verifiqué por mi cuenta: la evidencia durable existe, es append-only, `decide()` la consulta primero, la siembra está correctamente acotada a lo canónico, `set_general_rate` dejó de bloquear, no hay `MAX(period)` global, y B1-g4 y B2-g4 están cerrados de verdad. Las trece cifras principales son exactas y ejecutadas, el manifest verifica 36/36, el ZIP es byte-idéntico en sus 37 miembros, y el recuento de CRLF es correcto en los dos documentos que lo enuncian con detalle.

Lo que falla es lo que esta generación tenía que arrastrar consigo: **la documentación no se actualizó al retirar la guarda por estado**. Sobreviven tres reliquias que describen esa guarda como vigente (L1-g5, L4-g5, L5-g5), una de ellas en el propio backlog de hallazgos abiertos; un recuento de pruebas que se contradice dentro de la misma frase (L2-g5); una cifra de CRLF congelada en la generación anterior dentro de un `WORKFLOW.json` que el paquete declara idéntico al `HANDOFF.md` (L3-g5); y una justificación falsa para no regenerar la captura, cuando el rótulo de pantalla sí cambió (L6-g5).

Ninguno de los seis toca dinero. Los seis son afirmaciones del paquete demostrablemente falsas contra el código o contra el artefacto en este snapshot, con el comando que lo demuestra en cada caso, y cuatro de ellos caen exactamente en la superficie que el encargo de esta generación pedía revisar.
