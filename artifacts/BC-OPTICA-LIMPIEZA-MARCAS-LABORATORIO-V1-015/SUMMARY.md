# BC-OPTICA-LIMPIEZA-MARCAS-LABORATORIO-V1-015

Treinta y un artículos tienen un laboratorio escrito donde va la marca. Queda
resuelto, probado y listo — pero **no aplicado**: esto se hizo en Casa, y la base
de la Óptica no viaja.

## De dónde sale el problema

En las planillas de la Óptica la columna «Marca» de un cristal trae el
laboratorio. No era un error de tipeo: era el único lugar donde ese dato podía
estar. Así entró al catálogo en V1-008, y así seguía hasta hoy.

La migración 028 le dio al laboratorio su propio campo. Desde entonces la marca
dejó de ser el único sitio posible, y recién por eso se puede sacar sin perder
nada.

## Los 31, clasificados

| clase | artículos | qué se hace |
|---|---|---|
| `LABORATORY_IN_BRAND_CONFIRMED` | **28** | la marca queda en blanco |
| `CORRECTED_SOURCE_HAS_REAL_BRAND` | **2** | toman «Óptica Puppilent\`s» |
| `AMBIGUOUS` | **1** | no se toca: espera una decisión |
| `VALID_BRAND` | 0 | — |
| `NO_ACTION` | 0 | — |

Los 28 son cristales, todos `TRABAJO_BAJO_PEDIDO`, todos con «Laboratorio
Optilab» o «Laboratorio Servi Optical» de marca. La fuente corregida del 19/08
sigue poniendo el laboratorio en esa columna, así que no hay marca real que
rescatar en ningún lado: va a blanco, no a un fabricante inventado. Su
laboratorio ya vive en `default_laboratory_id` desde V1-012 y ahí se queda.

Los 2 son de *Compostura* —`2000065 Adaptacion de cristal` y `2000070 Hilo`— y
son el caso contrario: la fuente corregida **sí** trae una marca real. Las 21
filas de Compostura pasaron a «Óptica Puppilent\`s», y para `2000070` está
verificado en las dos sucursales. Poner blanco ahí sería tirar un dato que el
dueño ya corrigió.

El ambiguo es `2000212 ST Fotocromatico`. El brief lo trata como cristal; en
producción es un `PRODUCTO_STOCKEABLE` de *Armazones* con «Laboratorio Optilab»
de marca. Un armazón sí tiene marca real, sólo que ésta no lo es, y desde Casa no
hay cómo saber cuál. Va al HUMAN_GATE.

## Lo que no se hizo, y por qué

**No se limpió por parecido.** La lista de marcas que nombran un laboratorio
tiene exactamente dos entradas y está escrita a mano. Una regla del tipo «toda
marca que se parezca a un laboratorio» se habría llevado puesta «Optica San
Cayetano» —doce artículos, y es una óptica, no un laboratorio—. Hay una guarda
que denuncia cualquier marca-laboratorio nueva sin tocarla: ampliar el alcance es
una decisión, no un efecto.

**No se creó ninguna marca.** «Óptica Puppilent\`s» ya existe: es la que V1-014
restauró en `000010 LIMPIA CRISTAL`. El conteo de marcas queda en 136, igual que
antes.

**No se tocó nada más que `brand_id`.** Ni el laboratorio por defecto, ni la
naturaleza, ni el stock, ni un movimiento, ni una línea de venta, ni las notas,
ni el precio. Se usa `actualizar_articulo` —la operación parcial de V1-014— con
un solo campo nombrado. Es exactamente lo que faltaba cuando V1-010 borró
categoría y marca de cinco artículos sin querer.

## Cómo se probó, sin producción delante

Se reconstruyó una copia local del catálogo desde `catalogo_canonico.csv` —el
mismo archivo que se importó en la Óptica— más los 24 laboratorios por defecto
copiados uno por uno de la salida real de V1-012. Sobre esa copia:

- el dry-run encuentra los 31 y los clasifica 28 / 2 / 1;
- aplicado, cambian 30 `brand_id` y ningún otro campo de ningún artículo;
- marcas 136, laboratorios 3, artículos con default 24: los tres sin cambio;
- `integrity_check` ok, FK 0, negativos 0, huérfanos 0, efectos sin hecho 0;
- una segunda corrida no cambia nada.

**Esto no es validación contra producción.** La copia no tiene movimientos, ni
ventas, ni caja, ni las 767 bajas de V1-010/V1-013: tiene la forma del catálogo,
que es lo que la misión toca. Que el conteo de marcas dé 136 —el mismo número que
V1-012 midió en la Óptica— es una señal de que la copia es fiel, no una prueba de
que la base real vaya a comportarse igual. Eso se comprueba allá.

Un detalle honesto: en la copia `2000070 Hilo` figura como `PRODUCTO_STOCKEABLE`,
porque el CSV canónico es anterior a la corrección de naturaleza de V1-010. En
producción es `SERVICIO_NO_STOCKEABLE`. La herramienta no nombra ese campo, así
que no lo puede cambiar, y hay una prueba dirigida que lo fija con la naturaleza
productiva.

## Pruebas

24 dirigidas nuevas, verdes. Cubren la clasificación caso por caso y —la mitad
que más importa— que cambiar la marca no arrastre categoría, naturaleza, notas,
costo, precio, `default_laboratory_id`, proveedor, unidad ni ningún otro campo.
La última vende un cristal de los que se limpian, con su laboratorio escrito en
la línea, y comprueba que vaciar la marca no reescribe esa venta de agosto.

Commercial Core entero: 345 verdes, ninguna roja. El repo: 1025 verdes y 2 rojas
en `tests/gestion_central/test_ui_interactions.py`, clasificadas
`PREEXISTING_OUT_OF_SCOPE` — ya estaban rojas en `a0bd4da`, y la misión no
modifica ni un archivo de producción. La evidencia de la reproducción está en
`PRUEBAS_PREEXISTENTES.txt`. No se declara regresión verde total del repo: no lo
es.

## Estado

`READY_FOR_PRODUCTIVE_APPLY_AT_OPTICA`. La herramienta, el plan, el backup, las
guardas, el rollback y los post-checks están listos. Al volver a la Óptica se
corre primero sin `--confirmar`, se compara el plan contra `DRY_RUN.txt`, y recién
entonces se confirma.
