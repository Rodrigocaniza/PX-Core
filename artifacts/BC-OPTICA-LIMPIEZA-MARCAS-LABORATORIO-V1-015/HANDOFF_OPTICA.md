# Handoff — de Casa a la Óptica

**V1-015 está lista y no está aplicada.** Todo viaja por Git: no hay nada que
copiar a mano, ni un script suelto, ni un archivo que haya que mandar aparte.

```
git fetch origin
git checkout feature/bc-optica-limpieza-marcas-laboratorio-v1-015
```

El HEAD autoritativo es el que apunte `origin/feature/bc-optica-limpieza-marcas-laboratorio-v1-015`.
No hay un SHA escrito acá a propósito: un artifact no puede contener el hash del
commit que lo contiene. Lo que sí se puede comparar —y es lo que importa— es la
**huella del plan** en `PLAN_SELLADO.json`: si el dry-run de allá da 28/2/1 sobre
los mismos 31 SKU, es el mismo plan.

---

## Lo primero, porque cambia todo lo demás

La base productiva vive sólo acá. En Casa no se tocó, no se leyó y no se simuló
contra ella: el plan se probó sobre una copia armada desde el catálogo canónico
de V1-008. **Nada de lo que sigue está validado contra producción.** Eso se
comprueba en los pasos 1 y 4.

## Qué hace esta misión, en una línea

Treinta y un artículos tienen un laboratorio escrito donde va la marca. Veintiocho
cristales quedan sin marca, dos composturas recuperan la marca real que el dueño
ya había corregido, y un armazón espera. Se toca **un solo campo**: `brand_id`.

---

## 1. Verificar el estado canónico de producción

Con BC Caja **cerrado** —dos escritores a la vez es como se traba SQLite—.

La herramienta imprime el `sha256` de la base y su radiografía al arrancar. Los
números que tienen que aparecer, de `HANDOFF_CASA.md` de V1-012:

| | |
|---|---|
| artículos / activos | 3.596 / 2.829 |
| movimientos | 4.441 |
| ASUNCION / PILAR / total | 6.166 / 2.260 / 8.426 |
| Caja | 12 entradas · 6.400.000 |
| migraciones | 28 |
| marcas / laboratorios | 136 / 3 |
| cristales con laboratorio por defecto | 24 |

Si algo de esto no coincide, **parar**: alguien operó la Óptica desde el 19/08 y
el plan hay que revisarlo antes de aplicarlo, no después.

## 2. Localizar el inventario corregido del 19/08

```
C:\Users\Striker\Downloads\Inventario P2.xls
```

Es el de PILAR, y es el que importa: **los 31 casos salen todos de PILAR**. El de
ASUNCION (`Inventario PC.xls`) sirve nada más como confirmación cruzada de
`2000070`.

Si está guardado como `.xls` viejo, `openpyxl` no lo abre: abrirlo en Excel y
guardarlo como `.xlsx`. Es lo mismo que hizo V1-010.

Si no aparece, la herramienta corre igual con la evidencia registrada en
`EVIDENCIA_FUENTE_CORREGIDA.json` y lo dice en la primera línea del informe. El
plan sale idéntico salvo por `2000212`, que sin el archivo se queda esperando.

## 3. Dry-run, con la fuente

```
python tools/limpieza_marcas_laboratorio_optica.py ^
    --fuente-corregida "C:\Users\Striker\Downloads\Inventario P2.xlsx" ^
    --salida DRY_RUN_OPTICA.txt
```

Sin `--confirmar` no escribe nada.

## 4. Comparar contra el baseline sellado

El resumen tiene que dar **28 / 2 / 1**, 30 artículos que cambian. El plan
completo, fila por fila, está en `PLAN_SELLADO.json` y en `DRY_RUN.txt`.

Tres desvíos y qué significa cada uno:

- **`2000212` sale de `AMBIGUOUS`** → mejora esperada, no desvío. El archivo le
  dio su marca real y el gate se cerró solo. Sigue.
- **Cualquier otro SKU cambia de clase, aparece o desaparece** → parar. Es drift
  de producción o de la fuente, y hay que entenderlo antes de escribir.
- **La herramienta aborta sola** → encontró una marca-laboratorio fuera de su
  lista autorizada, o una marca destino que no existe. No la fuerces: eso es una
  decisión de catálogo nueva.

## 5. `2000212 ST Fotocromatico` — la única ambigüedad

Armazón, `PRODUCTO_STOCKEABLE`, marca «Laboratorio Optilab», sin laboratorio por
defecto a propósito.

La herramienta ya hace lo correcto sola, y conviene saber qué es «lo correcto»
para reconocerlo:

- si la fuente le da una **marca real inequívoca** para el mismo código → la usa,
  y el gate se cierra sin que nadie decida nada;
- si la celda «Marca» viene **vacía**, o repite un laboratorio → lo deja **sin
  cambio**. Una celda en blanco dice «no sé», no «no tiene marca»;
- **no** lo recategoriza como cristal;
- **no** lo limpia a blanco por criterio propio.

Y lo más importante: **no frena a los otros 30.** Está probado
(`test_el_ambiguo_no_frena_a_los_demas`).

Si al final sigue sin resolverse, queda como estaba y se decide en otro momento.
Eso no impide cerrar la misión.

## 6. Aplicar

```
python tools/limpieza_marcas_laboratorio_optica.py ^
    --fuente-corregida "C:\Users\Striker\Downloads\Inventario P2.xlsx" ^
    --confirmar --salida APLICACION_PRODUCTIVA.txt
```

Antes de escribir una sola fila:

- **backup verificable** en `...\BC\Caja\Backups\bc-caja-premarcas-<fecha>.sqlite3`,
  y comprueba que el backup tenga el mismo contenido que la base. Si eso falla,
  no escribe;
- **pre-guards**: cada marca destino tiene que existir y estar activa —no se crea
  ninguna marca—, todos los casos tienen que conservar su categoría, y ninguna
  marca-laboratorio puede estar fuera de la lista autorizada.

## 7. Post-check integral

Lo corre sola y lo imprime. Todo tiene que decir `OK`:

- sólo cambió `brand_id`, y sólo en los artículos del plan — se compara artículo
  por artículo, campo por campo, antes contra después;
- artículos 3.596 · activos 2.829;
- movimientos 4.441 · ASUNCION 6.166 · PILAR 2.260;
- Caja 12 entradas · 6.400.000;
- `sale_items` y los laboratorios de las líneas históricas, sin cambio;
- marcas 136 · laboratorios 3 · artículos con laboratorio por defecto 24;
- `integrity_check` ok · FK 0 · negativos 0 · huérfanos 0 · efectos sin hecho 0;
- idempotencia: una segunda corrida no cambiaría nada.

Después, un vistazo en *Comercial*: `2000060 Organico UVX` sin marca y **con** su
laboratorio sugerido; `2000070 Hilo` con marca «Óptica Puppilent\`s`»,
`SERVICIO_NO_STOCKEABLE` y fuera del stock.

## 8. Rollback

Cerrar todo y copiar `bc-caja-premarcas-<fecha>.sqlite3` sobre
`bc_caja.sqlite3`. El backup se toma antes de la primera escritura: revierte la
misión entera.

Si la herramienta abortó por una guarda, no hace falta: sale antes de escribir.

---

## Lo que NO hay que hacer acá

- **No unificar «Óptica Puppilent\`s» con «Optica Puppilents».** Son la misma
  óptica escrita de dos maneras, siete artículos y uno. Es un finding aparte y
  tocaría artículos fuera de estos 31.
- **No resolver los pendientes de V1-012** —los 7 códigos ausentes, el par
  `2000078`/`2000219`, los 6 cristales sin laboratorio, los tres teléfonos—. Se
  leyeron como evidencia y siguen abiertos.
- **No tocar `tests/gestion_central/test_ui_interactions.py`.** Sus dos fallos son
  anteriores a esta misión y ajenos a su alcance.

## Un aviso, por si sirve para lo que venga después

Cinco de los seis cristales sin laboratorio por defecto —`2000127`, `2000210`,
`2000211`, `2000219`, `2000227`— tienen hoy «Laboratorio Optilab» de marca, y
esta misión les borra ese dato. Como **pista** de a qué laboratorio van, se pierde
al aplicar. Si se va a usar, hay que leerla antes, o después del backup
`bc-caja-premarcas`, que la conserva. No es un blocker: es algo que conviene saber
antes y no descubrir después.
