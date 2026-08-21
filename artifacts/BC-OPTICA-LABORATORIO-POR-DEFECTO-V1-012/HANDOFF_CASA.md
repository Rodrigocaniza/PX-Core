# Handoff — de la Óptica a Casa

**19/08/2026.** Pausa segura. Nada quedó a medias.

---

## Lo primero, porque cambia todo lo demás

**La base productiva no viaja.** Vive sólo en la PC de la Óptica, en
`C:\Users\Striker\AppData\Local\BC\Caja\bc_caja.sqlite3`. Casa es otra máquina
**con la misma ruta**, así que ese archivo allá existe pero **es otra base**.

Lo que sí viaja, y viaja completo, es el código y los artefactos: están en el
remoto, en ocho ramas.

Consecuencia práctica: desde Casa se puede leer, diseñar, escribir código y
correr pruebas. **No se puede verificar contra la base real de la Óptica ni
aplicar nada productivo.** Cualquier misión que necesite tocar producción espera
a volver acá.

## Estado productivo real (Óptica)

| | |
|---|---|
| artículos | 3.596 (2.829 activos) |
| movimientos | 4.441 |
| stock ASUNCION | 6.166 |
| stock PILAR | 2.260 |
| total | 8.426 |
| Caja histórica | 12 entradas · 6.400.000 · 10 líneas |
| migraciones | 28 |
| laboratorios | 3 |
| cristales con laboratorio por defecto | 24 (16 Optilab / 7 ServiOptica / 1 Lab Cristal) |
| `2000212 ST Fotocromatico` | sin default, a propósito |
| sha256 | `a335805eb83cce46454e36eda1fdb25a567be1ad534427af687ef0fa8b225d13` |

`integrity_check` ok · FK 0 · negativos 0 · huérfanos 0 · efectos sin hecho 0.

## Último HEAD

`feature/bc-optica-laboratorio-por-defecto-v1-012` @ **`dc1654d`**, pusheada y
sincronizada. Worktree limpio.

La cadena entera está en el remoto, y **ninguna sale de `origin/main`** (`7db56a0`,
rc.31): ramificar desde ahí perdería Commercial Core. La punta viva es `dc1654d`.

| slice | rama | HEAD |
|---|---|---|
| 007 instalación | `feature/bc-optica-instalacion-productiva-v1-007` | `a7b685c` |
| 008 carga catálogo | `…carga-inicial-catalogo-v1-008` | `f5a55b7` |
| 009 recuento | `…recuento-fisico-pendientes-v1-009` | `71dbc0d` |
| 010 conciliación | `…conciliacion-inventario-corregido-v1-010` | `09532f7` |
| 013 promo | `…promo-limpia-cristal-v1-013` | `3d03dcf` |
| 011 delivery | `…delivery-service-v1-011` | `7d17cce` |
| 014 metadatos | `…article-metadata-restore-v1-014` | `c838f10` |
| **012 laboratorios** | `…laboratorio-por-defecto-v1-012` | **`dc1654d`** |

Ojo con una trampa conocida: el **`main` local está viejo** (`d88f595`, del 30/07).
Mirar `main` a secas no dice nada; el canónico es `origin/main`.

## Migración 028

`028_default_laboratory.sql` — **aplicada en producción**. Aditiva: agrega
`articles.default_laboratory_id` (FK nulable a `laboratories`) y su índice. No
inventa datos: después de migrar, cero artículos con laboratorio. Idempotente.
`sale_items.laboratory` quedó intacto — ahí vive el laboratorio que realmente
hizo cada trabajo, y por eso cambiar un default no reescribe ventas.

El catálogo de laboratorios es el de la migración 003, el del circuito de
Seguimiento. No hay un segundo.

## Decisiones pendientes (HUMAN_GATE, no bloqueante)

Ninguna impide operar. Están completas en `HUMAN_GATE.md`.

1. **Siete códigos de cristales que no existen** en producción: `2000124`,
   `2000139`, `2000077`, `2000078`, `2000090`, `2000231`, `2000235`. ¿Son
   cristales reales que nunca entraron al catálogo, o códigos de otra planilla?
2. **`2000078` / `2000219`**: nombre idéntico («Multiblue Foto Ar»), distinto
   código. ¿Es el mismo cristal renumerado?
3. **Seis cristales activos sin laboratorio**: `2000127`, `2000210`, `2000211`,
   `2000219`, `2000227`, `2000239`.
4. **Marcas que en realidad son laboratorios**: 31 artículos. Ahora que el
   laboratorio tiene campo propio, esa marca se puede limpiar. Incluye
   `2000070 Hilo`, cuyo caso quedó documentado con evidencia de las dos fuentes.
5. **Teléfonos** de Laboratorio Optilab, ServiOptica y Laboratorio Cristal: los
   tres quedaron vacíos. El Seguimiento los necesita para reclamar trabajos.

## Reglas provisionales, verificadas contra la base

No es una promesa: se comprobó en producción, ahora mismo.

- los siete códigos **siguen sin crearse** ✓
- `2000078` y `2000219` **no se fusionaron** ✓
- los seis defaults **siguen en NULL** ✓
- las marcas-laboratorio **siguen sin limpiar** (31 artículos) ✓
- **ningún teléfono inventado** (los tres en blanco) ✓

## Blockers operativos

**Ninguno.** La Óptica puede vender hoy con todo esto puesto: elegir un cristal
llena el campo «Laboratorio» solo, y la operadora lo cambia cuando ese trabajo va
a otro lado.

## Siguiente acción recomendada

Desde Casa, sin tocar producción: **preparar `V1-015`, la limpieza de las marcas
que son laboratorios** — es la deuda más grande que quedó, tiene evidencia
completa en `MANIFEST.json` y `HUMAN_GATE.md`, y ahora que el laboratorio tiene
su lugar propio nada la retiene. Se puede dejar la herramienta escrita, probada
contra copias y en dry-run, para aplicarla al volver.

Lo que **no** conviene hacer desde Casa: nada que dependa de leer la base real de
la Óptica.

Y si aparecen los números de los tres laboratorios, se cargan en un minuto desde
el ABM de Laboratorios en la pantalla de Seguimiento.
