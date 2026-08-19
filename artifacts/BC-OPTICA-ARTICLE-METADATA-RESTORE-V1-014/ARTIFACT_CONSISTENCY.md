# Artifact Consistency — BC-OPTICA-ARTICLE-METADATA-RESTORE-V1-014

Cada cifra de los artefactos contra la fuente de la que sale.

| Afirmación | Dónde está | De dónde sale | Verificado |
|---|---|---|---|
| base Git `7d17cce` | MANIFEST, WORKFLOW | `git rev-parse feature/bc-optica-delivery-service-v1-011` | PASS |
| `main` sigue en `7db56a0` | MANIFEST | `git log main` | PASS |
| los cinco afectados, y sólo ésos | MANIFEST, SUMMARY | `BARRIDO_DEL_DANO.txt`, campo por campo sobre 3.554 artículos | PASS |
| categorías y marcas restauradas | MANIFEST, SUMMARY | `bc-caja-prerecuento-20260819-142306.sqlite3`, leídas de la base | PASS |
| sha256 de la fuente `71580fc8…` | MANIFEST | `sha256` del archivo | PASS |
| base antes `ff6b2b6a…` | MANIFEST | pre-guard; coincide con el cierre de V1-011 | PASS |
| base después `ffafb5c6…` | MANIFEST | `APLICACION_PRODUCTIVA.txt` | PASS |
| backup `2a100d55…` | MANIFEST | tomado por la API de backup y comparado por contenido | PASS |
| 10 campos tocados, 10 esperados | MANIFEST | `APLICACION_PRODUCTIVA.txt` | PASS |
| stock 6.166 / 2.260 / 8.426 sin cambios | MANIFEST, SUMMARY | radiografía antes y después | PASS |
| 4.441 movimientos sin cambios | MANIFEST, SUMMARY | ídem | PASS |
| Caja 12 entradas, 6.400.000, 10 líneas | MANIFEST, SUMMARY | `VERIFICACION_POST.txt` | PASS |
| notas idénticas al carácter | SUMMARY | `VERIFICACION_POST.txt`, comparación contra el backup previo | PASS |
| `000010` en 100 / 10 y estimado | MANIFEST | `stock_actual` y la nota completa en `VERIFICACION_POST.txt` | PASS |
| los cuatro sin movimientos ni fila | MANIFEST | `VERIFICACION_POST.txt` | PASS |
| ningún centinela se volvió stock | MANIFEST | `VERIFICACION_POST.txt` | PASS |
| V1-008/010/011/013 intactas | MANIFEST | `VERIFICACION_POST.txt` | PASS |
| bitácora: sólo `ARTICLE_METADATA_RESTORED` nueva | MANIFEST | conteo por acción antes y después | PASS |
| `EDITA_ARTICULO` 772 → 777 | MANIFEST | ídem, las cinco del propio guardado | PASS |
| 14 pruebas dirigidas | MANIFEST | `PRUEBAS_DIRIGIDAS.txt` | PASS |
| suite completa 981 | MANIFEST | `python -m pytest tests/` | PASS |
| idempotencia | MANIFEST | `IDEMPOTENCIA.txt` | PASS |
| smoke de la UI | MANIFEST | `SMOKE_UI.txt` | PASS |
| rollback no usado | MANIFEST | ninguna corrida terminó en falla | PASS |

## Números que corregí en el camino

Tres asserts míos estaban mal escritos, no los datos:

- esperaba `PHYSICAL_COUNT_CONFIRMED > 0`, y en producción son cero: V1-009 quedó
  en pausa segura y `000010` se registró como estimación, no como conteo. Pasé a
  comparar la bitácora contra su propio estado previo en vez de contra números
  que supuse.
- esperaba 3.583 movimientos de `INVENTARIO_INICIAL`; son 3.629 porque V1-010
  agregó altas con el mismo `reason_code`. Pasé a comparar contra producción: el
  invariante es que no se movió, no que valga tal cifra.
- comparaba un `sqlite3.Row` contra una tupla, que nunca da igual aunque los
  valores coincidan.

Los tres se corrigieron antes de tocar producción, y ninguno cambió el plan.

## HUMAN_GATE

No corresponde. La orden autoriza aplicar si el dry-run demuestra que el cambio
se limita a los metadatos perdidos, y lo demuestra: diez campos, los diez
esperados, cero inesperados, con stock y movimientos idénticos.
