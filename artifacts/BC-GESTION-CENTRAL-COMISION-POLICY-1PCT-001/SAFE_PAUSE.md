# Safe Pause — Auto-Resume

> **El estado canónico manda sobre este documento.** Si algo de aquí no coincide con `git`,
> `WORKFLOW.json` o `MISSION_LEASE.json`, gana el estado real. Este resumen existe para no
> reconstruir contexto, no para sustituirlo.
>
> Esta advertencia no es decorativa: la Safe Pause anterior anticipaba que la misión seguiría desde
> la PC de la Óptica y siguió desde PC Casa, y el encargo de esta pausa daba por vivo un estado
> —«GEN9, no abrir GEN10»— que ya había sido superado por dos generaciones. **Verificá el HEAD antes
> de creerle a nadie, incluido este fichero.**

## Identidad

| | |
|---|---|
| **Misión** | `BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001` |
| **Generación en revisión** | **11 — INVALIDATED** (snapshot `75d7f1b6d0ff090abe9f1c063388c38b3f2f4ab0`) |
| **Generación siguiente** | **12 — sin abrir**, sin snapshot |
| **Branch** | `mission/bc-gestion-central-comision-policy-1pct-001` |
| **Remoto** | `origin` — publicada y sincronizada |
| **Working tree** | limpio |
| **Worktree** | `.worktrees/gc-comision-policy-1pct-001` (PC Casa) |
| **Safe Pause** | `SAFE_PAUSED` |
| **Safe Closure** | `PENDING` |
| **Mission Lease** | `RELEASED_FOR_SAFE_PAUSE` — **readquirir antes de tocar nada** |

Base de la misión: `e7732603d9eb098867a272598e6d30803a4f1ac3`.

## Dónde se cortó

El único runner en vuelo —`AUDITOR-IND-COMISION-POLICY-1PCT-011`— **terminó antes de pausar**, y su
verdict quedó registrado. Después de eso no se inició ningún fuzz, ningún runner, ninguna
remediación y ninguna generación. No se modificó ninguna regla económica.

## Estado de la generación 11

| Runner | Verdict | Bloqueantes |
|---|---|---|
| Librarian | **FAIL** | `L1-g11` |
| QA | **PASS** | ninguno |
| Auditor | **PASS** | ninguno |

**Tercer `PASS` consecutivo del Auditor** (generaciones 9, 10 y 11) y cuarto de QA. La generación
queda invalidada por un único bloqueante, y no es económico.

### Pruebas que ya pasaron

- Regresión completa **456/456**, verificada dos veces por el Auditor y una por el Librarian.
- Suite del módulo **256/256**.
- Casos de comisiones: **205** = 112 + 8 + 24 + 23 + 14 + 13 + 11.
- **Auditor:** 13.862 pasos de fuzz desde bases migradas, 5.872 comprobaciones de `importe = tasa ×
  base`, 25 rondas × 6 hilos de concurrencia sobre la cadena de pago, 25 reaperturas de migración.
  **1.726 liquidaciones legítimas** por el camino público completo, once tasas × dos clases de
  venta, con el medio guaraní exacto resuelto para cada tasa: **cero falsos rechazos**.
- **QA:** diferencial contra el árbol de la generación 10 —trece de quince escenarios idénticos
  carácter a carácter— más **506 liquidaciones** producidas por el sistema, cero rechazos.

> **Aviso para quien retome.** Las pruebas de interfaz usan Tk y **se pisan si dos corridas de
> `pytest` comparten el display**: durante esta pausa una corrida dio `454 passed, 2 errors` en
> `test_delivery_ui_interactions.py` y la siguiente, en serie, dio `456 passed` sin tocar una línea.
> No es una regresión. El Librarian de la generación 10 ya lo había anotado (su observación 7).
> Corré la suite en serie antes de leer un fallo de interfaz como un defecto.

### Lo que no se llegó a hacer

- No se abrió la generación 12.
- No se corrigió `L1-g11`.
- No se tocó ninguno de los tres hallazgos económicos nuevos.
- No se relanzó ningún runner después del Auditor.

## Bloqueante abierto

**`L1-g11` — la cobertura declarada de la guarda estructural es más ancha que la real.**

El invariante 10 afirma que la prueba estructural «falla si una función que escribe
`commission_entries` no reconcilia». El Librarian inyectó cuatro escritores en el módulo real —SQL
izado a una constante de módulo, armado por concatenación, con el nombre de tabla interpolado, y
`DELETE`— y **las cuatro pruebas estructurales pasaron**.

El ejemplo importa porque es el estilo del propio paquete: izar SQL a constantes de módulo es lo que
este módulo practica —`LIVE_OFFICIAL_FACT_SQL`, `PERIOD_MATCH_SQL`, `BOUNDARY_SQL_IN`,
`PERIOD_KEY_SQL`— y la generación 11 acaba de añadir `period_key` con el mismo criterio.

**Es la tercera vez que se sobre-afirma la cobertura de una guarda** (`L3-g9`, `L2-g10`, `L1-g11`).
Una prueba estática no puede decidir en general si una función escribe una tabla, porque el SQL
puede construirse en tiempo de ejecución. La corrección correcta **no es un cuarto intento de
universalidad**: es acotar la afirmación al alcance real de la guarda **y** extenderla donde es
barato —constantes de módulo, concatenaciones simples, `DELETE` y `REPLACE INTO`—.

## Hallazgos económicos nuevos — **no absorbidos**

Están en `ECONOMIC_FINDINGS_OPEN.md`, priorizados y separados por decisión del propietario. Resumen:

| | ID | Daño | Alcanzable por ruta pública |
|---|---|---|---|
| **P1** | `O15-g11` | **8.900.000 Gs** de sobrepago: la guarda de pago no re-deriva `commissionable_base` ni `gross_amount` desde la venta | no |
| **P2** | `O17-g11` | una traza de política inventada entra al libro append-only y resucita el alcance por vendedora | no |
| **P3** | `O16-g11` | el KPI `paid_amount` usa `status` y no `paid_at`: una pagada luego observada o anulada desaparece del pagado | **sí** |

`O1` **no** está en esa lista: es la decisión de propietario de la generación 9 —un mes con una
`PAGADA` viva al 7% cobra el 7% a las ventas posteriores, 600.000 Gs por venta de 10.000.000—.
Merece confirmación explícita antes de producción, pero no es un defecto.

## Cómo retomar

```
git fetch origin
git -C .worktrees/gc-comision-policy-1pct-001 status --porcelain   # debe estar vacío
git -C .worktrees/gc-comision-policy-1pct-001 rev-parse HEAD       # comparar con el estado real
```

Después: **readquirir el Mission Lease**, leer `ECONOMIC_FINDINGS_OPEN.md`, y decidir con el
propietario el orden de P1/P2/P3 respecto de `L1-g11` **antes** de escribir código. P1 mueve dinero;
`L1-g11` no.

## Artifacts

Los **treinta y tres** verdicts viven íntegros en `generation-1/` … `generation-11/`, tres por
generación, ninguno retocado. `MANIFEST.sha256` y el ZIP verifican en el worktree donde se generan
(hallazgo abierto 23: `core.autocrlf=true` sin `.gitattributes`).

## Lo que no se toca

BC-Core. Telegram. Commercial Core Slices 1–6. `BC-OPTICA-INSTALACION-PRODUCTIVA-V1-007`. La
instalación productiva de Caja. `main`. Sin PR, sin merge, sin force-push.
`BC-GESTION-CENTRAL-SOBRES-FACTURA-V1` sigue sin abrirse.
