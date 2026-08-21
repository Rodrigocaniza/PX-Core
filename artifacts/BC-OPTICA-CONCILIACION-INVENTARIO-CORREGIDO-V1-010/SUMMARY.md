# BC-OPTICA-CONCILIACION-INVENTARIO-CORREGIDO-V1-010

**Los archivos «corregidos» no corrigieron lo que más importaba, y eso es el
hallazgo principal.**

## Lo que llegó

Dos archivos del 19 de agosto, `Inventario PC.xls` e `Inventario P2.xls`,
posteriores a las planillas del 3 y el 10 que usó la 008. Son OLE2 legacy —
`openpyxl` no los lee— así que se convirtieron a `.xlsx` con Excel en modo sólo
lectura, sobre copias; los originales quedaron con su sha256 intacto.

Traen tres columnas que las anteriores no tenían: **`Cod. Barra`, `CostoA` y
`PrecioA`**. Eso resuelve de un saque la deuda de «los artículos entraron sin
precio». Y pierden `Casilla`, `Zona` y `Observacion`, que venían vacías igual.

## Lo que no cambió, y debería haber cambiado

**Los 28 centinelas siguen ahí. 842.497 unidades declaradas.** Hilo en 99.981,
Adaptación de cristal en 99.916, Compostura Flex en 99.884.

Peor: el archivo corregido de **Asunción trae 7 centinelas que antes no tenía**.
`Composturas` no existía como categoría en el PC anterior y ahora aparece con
9.222 «unidades» de Compostura Flex. La corrección no limpió el problema: lo
propagó a la otra sucursal.

Ninguno entra al ledger.

## Lo que sí se ganó

**La 008 dejó producción limpia, y ahora se ve.** Los 30 Cristales y los 9
servicios de Compostura tienen **cero movimientos**. La regla que pedía preparar
compensaciones «si producción tiene movimientos por interpretación anterior» no
tiene nada que compensar. Haber dejado en suspenso todo lo que no era un conteo
evitó exactamente el desastre que ahora habría que deshacer.

Una sola naturaleza cambia: `2000056 Par de patillas`, de producto a servicio por
definición del negocio. Sin conteo, sin compensación, sin stock que sacar.

## Lo que el dry-run aplicaría — PASS, 0 fallas

42 artículos nuevos (de 46 registros: cuatro son el mismo SKU global en las dos
sucursales), 1.066 unidades de stock inicial, **47 unidades de ajuste positivo y
65 de negativo** con motivo `ERROR_INVENTARIO` y la fila de origen en cada nota.

Artículos 3.554 → 3.596 · Asunción 5.849 → 6.904 · Pilar 2.899 → 2.892.

Las dos corridas de la 008 quedan enteras —3.583 movimientos, 8.748 unidades,
verificado por `document_id`—, los cinco pendientes siguen registrados, Caja
intacta, invariantes limpias, idempotencia byte a byte.

## Lo que no toqué

**775 artículos desaparecieron del archivo**, 776 unidades, 641 de ellos
armazones. Los dos informes listan sólo lo que tiene stock, así que «ausente»
significa que el sistema viejo dice cero. Pero 647 armazones en 16 días son 40
por día: eso no es una óptica vendiendo, es una limpieza o un filtro distinto.
Descontarlos sería sacar stock por una ausencia que no entiendo.

**`000010 Limpia Cristal` pasó de 2.860 a 2.857.** Bajó tres en dieciséis días, y
ahora tiene precio y costo. Un centinela no se mueve; esto se mueve despacio,
como un consumible real. La pregunta dejó de ser «¿será real?» y pasó a ser
«¿confirmás 2.857?».

**`000037 LIMPIA CRISTAL OBSEQUIO` es el SKU ficticio de la regla F**, y está
confirmado: precio de venta **0** clavado en el catálogo y costo 4.740, cuatro
veces y media el del limpia-cristal real. 726 unidades de stock ficticio en el
ledger. Lo bueno es que el modelo ya sabe hacer lo correcto: `sale_items` tiene
`no_cost` y `article_id`, así que una línea puede vender el producto real a
precio cero. Hoy no lo usa nadie.

## Fuera de alcance, como slices

Laboratorio por defecto (la tabla existe pero está vacía y no hay campo en el
artículo), Delivery (no existe el concepto) y el motor promocional. Los tres
necesitan cambios de producto, no conciliación.

## Generación 2 — las tres decisiones, y tres errores que evitaron daño

Las decisiones llegaron y el plan se recalculó entero. El anterior quedó
obsoleto y no se reutilizó.

`Hilo`, `Tornillo` y `Plaqueta` se suman a `Par de patillas` como servicios: los
cuatro tenían **cero unidades**, así que no hubo nada que compensar, y sus cifras
—99.981, 99.423, 9.391, 524— quedan escritas en el artículo sólo como evidencia
de que la fuente decía eso. Ninguno necesita que nadie cuente nada.

Los 775 ausentes se retiran, pero el recálculo destapó **tres cosas que habrían
hecho daño**:

**Un código renumerado.** El archivo corregido normaliza algunos códigos de barra
a 13 dígitos con un cero adelante. `300653145470` figuraba como baja y
`0300653145470` como alta: es el mismo Opti Free Express. Busqué el patrón en los
775 y es el único caso, pero de no verlo habría retirado un artículo vivo y
creado un duplicado.

**El retiro es por artículo; la ausencia, por sucursal.** El primer intento falló
con `ArticuloEnUso`: el sistema **impide** desactivar algo que todavía tiene
stock, «porque quedaría sin nadie que lo mire». La guarda es correcta y el error
era mío. Cinco artículos faltan en una sucursal y viven en la otra; se compensa
el depósito ausente y el artículo sigue activo.

**Una fila que nunca fue artículo.** `ASU-101814`, la que la 008 rechazó por no
tener descripción. Contarla como baja habría inflado el número.

Quedan **773 ausentes reales**: 766 retirados y 5 que siguen vivos. Los 773
tenían stock, ninguno era una baja limpia, así que **primero se lleva el stock a
cero y después se retira** — nunca queda stock fantasma en un artículo inactivo.

`000010 Limpia Cristal` no recibe ningún ajuste: Asunción sigue pendiente, sin
2.860 ni 2.857 ni cero inventado, y Pilar conserva sus 10. `000037` no se toca:
va entero al slice 013.

## Estado del plan

| | antes | después |
| --- | ---: | ---: |
| artículos | 3.554 | 3.595 |
| activos | 3.554 | 2.829 |
| stock ASUNCION | 5.849 | 6.276 |
| stock PILAR | 2.899 | 2.776 |
| **total** | **8.748** | **9.052** |

41 altas · 766 retiros · 773 unidades compensadas (645 + 128) · 37 ajustes
(+47 / −34) · 4 cambios de naturaleza. **PASS, 0 fallas.**

## Generación 3 — aplicada

Autorizada y hecha. **PASS, 0 fallas, sin rollback.**

El pre-guard pasó en los diez puntos, y después la herramienta hizo algo que
vale la pena contar: **recalculó el plan entero desde los archivos y la base, y
lo comparó contra el sellado en el gate antes de escribir una sola fila**. Las
catorce cifras coincidieron. Si alguna no lo hubiera hecho, abortaba — una
autorización se da sobre un plan concreto, y adaptarlo a evidencia nueva después
del gate es ejecutar algo que nadie aprobó.

| | antes | después |
| --- | ---: | ---: |
| artículos | 3.554 | **3.595** |
| activos | 3.554 | **2.829** |
| movimientos | 3.583 | **4.438** |
| stock ASUNCION | 5.849 | **6.276** |
| stock PILAR | 2.899 | **2.776** |
| **total** | **8.748** | **9.052** |

41 altas con 1.064 unidades · 766 retiros con **773 unidades compensadas a cero
antes de desactivar** · 37 ajustes (+47 / −34) · 4 cambios de naturaleza con sus
cierres. `sha256`: `25cd7d04…` → `ae67faff…`

**Nada se borró.** Los retirados están inactivos, con su stock llevado a cero por
un movimiento nuevo y su historia entera. Verificado explícitamente: **stock
operativo en artículos retirados = 0**.

Caja histórica intacta, la carga de la V1-008 intacta (3.583 movimientos y 8.748
unidades), `000010` sin cantidad en Asunción y con sus 10 en Pilar, `000037`
esperando el slice 013, y ningún artículo de Compostura clasificado como
producto.

El replay no escribió una sola fila. Y BC Caja abre con la UI Comercial
funcionando sobre la base ya conciliada.

**Un tropiezo que quedó del lado correcto:** al validar sobre copia, el script
falló con `database is locked` — escribía desde una segunda conexión mientras el
controlador tenía la suya. Se corrigió antes de tocar producción, que es
exactamente para lo que existía la copia.

## Adenda — los limpia-cristales de Asunción

La decisión llegó cuando V1-010 ya estaba aplicada, así que no se recalculó el
plan: se agregó un hecho más sobre lo ya escrito. **100 unidades**, y el sistema
dice de sí mismo que son una estimación, no un conteo.

Eso es la parte que importa. `ESTIMATED_INITIAL_STOCK`, con `es_conteo_fisico:
false` escrito en el registro y las dos cifras que las fuentes declararon —2.860 y
2.857, ninguna aceptada— guardadas al lado. Si mañana alguien cuenta y da otra
cosa, la corrección va a ser un movimiento compensatorio y se va a poder explicar
por qué hacía falta. Si esto se hubiera registrado como conteo, esa explicación
se perdía.

ASUNCION 6.276 → **6.376** · PILAR **2.776 intacto** · total **9.152** ·
movimientos 4.438 → **4.439**. Un solo movimiento, ningún efecto colateral:
catálogo, activos, Caja y la carga de V1-008 quedaron idénticos.

**Los cinco pendientes están cerrados y no queda ninguno abierto**: cuatro porque
dejaron de ser inventario, y éste declarando que su número es aproximado.

## Lo que sigue

Tres slices, en este orden: **013** (retirar `000037` y montar la promoción sobre
el limpia-cristal real), **011** (Delivery) y **012** (laboratorio por defecto).
La V1-009 sigue pausada por una sola cantidad: los limpia-cristales de Asunción.
