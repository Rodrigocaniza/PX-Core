# Artifact Consistency — V1-015

Cada afirmación de estos artifacts, contra lo que realmente pasó. No contra lo
que se esperaba que pasara.

## Números

| afirmación | dónde | contra qué se comprobó | |
|---|---|---|---|
| 31 casos | SUMMARY, MANIFEST | conteo sobre `catalogo_canonico.csv`: 23 + 8 | ✔ |
| coincide con producción | SUMMARY | `CIERRE_CROSS_PC.txt` de V1-012 dice «31 articulos» | ✔ |
| 28 confirmados | todos | salida real del dry-run | ✔ |
| 2 con marca real | todos | salida real del dry-run | ✔ |
| 1 ambiguo | todos | salida real del dry-run | ✔ |
| 30 cambian | MANIFEST | `cambios: 30, esperados 30` en la corrida | ✔ |
| 24 laboratorios por defecto | base de prueba | copiados uno por uno de `APLICACION_PRODUCTIVA.txt` de V1-012 | ✔ |
| marcas 136 | MANIFEST | `radiografia()` sobre la copia, antes y después | ✔ |
| 24 pruebas dirigidas | SUMMARY | `24 passed` | ✔ |
| 345 en comercial, 0 rojas | SUMMARY | `345 passed` | ✔ |
| 1025 + 2 en el repo | SUMMARY | `1025 passed, 2 failed` | ✔ |
| las 2 rojas ya estaban | SUMMARY, MANIFEST | checkout limpio de `a0bd4da` y volver a correrlas: fallan igual | ✔ |
| la misión no toca producción | PRUEBAS_PREEXISTENTES | `git diff --name-only a0bd4da HEAD`: sólo la herramienta, sus pruebas y sus artifacts | ✔ |
| el plan no derivó | PLAN_SELLADO | dry-run repetido tras el cambio de código: 28/2/1 idéntico | ✔ |

## Lo que se dice que no cambia

Cada uno se comprobó comparando la radiografía antes y después sobre la copia, no
razonando sobre el código:

| invariante | valor | |
|---|---|---|
| artículos / activos | 3554 / 3554 | ✔ |
| movimientos, ASUNCION, PILAR | 0 / 0 / 0 en la copia | ✔ |
| entradas y total de Caja | 0 / 0 en la copia | ✔ |
| `sale_items` y sus laboratorios | 0 / 0 en la copia | ✔ |
| categorías | 14 | ✔ |
| marcas | 136 | ✔ |
| laboratorios | 3 | ✔ |
| artículos con laboratorio por defecto | 24 | ✔ |
| campos distintos de `brand_id` | 0 cambios inesperados | ✔ |

Los ceros de movimientos, ventas y caja son ceros **de la copia**, no de
producción: la copia se armó desde el catálogo y no tiene esa historia. Como
invariante prueban que la herramienta no los crea; no prueban que no los altere
en una base que sí los tenga. Eso lo cubren dos pruebas dirigidas, que trabajan
sobre una base con historia: `test_el_stock_y_los_movimientos_no_se_mueven` da de
alta un movimiento real antes de limpiar, y
`test_una_venta_de_agosto_no_se_reescribe_al_limpiar_la_marca` vende un cristal
—uno de los que sí se limpian— con su laboratorio escrito en la línea, y
comprueba que la línea queda igual. La confirmación final es la corrida en la
Óptica.

## Diferencias entre la copia y producción, dichas de frente

| | copia local | producción |
|---|---|---|
| artículos | 3.554 | 3.596 |
| activos | 3.554 | 2.829 |
| movimientos | 0 | 4.441 |
| Caja | vacía | 12 entradas · 6.400.000 |
| `2000070 Hilo` | `PRODUCTO_STOCKEABLE` | `SERVICIO_NO_STOCKEABLE` |

Las tres primeras son porque la copia sale del catálogo canónico y no de un
backup: no tiene las 767 bajas de V1-010/V1-013 ni la historia. La cuarta es
porque el CSV es anterior a la corrección de naturaleza de V1-010.

Ninguna afecta lo que la misión hace, porque la herramienta nombra un solo campo
y ese campo es `brand_id`. Que la naturaleza sobreviva con el valor productivo
está fijado por prueba dirigida
(`test_la_compostura_sigue_siendo_servicio_despues_de_recuperar_su_marca`), no por
la copia.

## Lo que se afirma sobre la fuente corregida

`EVIDENCIA_FUENTE_CORREGIDA.json` cita textual de dónde sale cada cosa. Dos
matices que el artifact dice y conviene repetir:

- para `2000070 Hilo`, V1-012 verificó «Óptica Puppilent\`s» en **las dos**
  sucursales, por SKU;
- para `2000065 Adaptacion de cristal` la evidencia es **de bloque**: las 21 filas
  de Compostura de la fuente corregida pasaron a esa marca. Su SKU no está
  verificado individualmente porque el `.xls` no está en esta PC.

Por eso la herramienta acepta `--fuente-corregida`: en la Óptica lee el archivo y
resuelve por SKU, y lo que salga del archivo le gana a la evidencia registrada.

## Lo que NO se afirma

- que esto esté validado contra la base de la Óptica. **No lo está.**
- que `2000212` esté resuelto. Está en el HUMAN_GATE.
- que «Laboratorio Servi Optical» y «ServiOptica» sean el mismo laboratorio. No
  hizo falta decidirlo, y no se decidió.
- que los pendientes de V1-012 estén cerrados. Se leyeron como evidencia y
  siguen abiertos.

## Sorpresa

Esperaba encontrar sólo dos marcas-laboratorio y encontré exactamente eso, pero
de paso apareció que «Óptica Puppilent\`s» convive con «Optica Puppilents» —la
misma óptica, dos grafías, ocho artículos repartidos—. No se unifica acá: tocaría
artículos fuera de los 31. Queda anotado en el HUMAN_GATE.
