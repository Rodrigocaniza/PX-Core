# BC-OPTICA-CARGA-INICIAL-CATALOGO-V1-008

**Los dos inventarios reales están entendidos, limpios, normalizados y
simulados. Producción no fue tocada: sigue con 0 artículos y 0 movimientos.**

## Base canónica elegida

`a7b685c`, tip de `feature/bc-optica-instalacion-productiva-v1-007`.

No se salió de `origin/main`. `main` está en `7db56a0` = rc.31 con 21
migraciones, y **producción está por delante**: corre rc.32 con 27 migraciones
desde la rama del slice 6. Crear esta misión desde `main` habría borrado las
seis migraciones comerciales que la Óptica ya usa — no habría existido ni la
tabla `articles`. La cadena verificada es
`7db56a0 → ed0dbba → 54f5f06 → ecc0c7b → b580e50 → a8443a3 → 5bc1540 → a7b685c`.

## Lo que resultó de mirar los archivos

**Las 8.459 filas de PC eran 2.586 artículos.** 5.871 filas vienen vacías.
Coincide con los «unos 2.000 de Asunción» que ya decía la documentación.

**Los 837.403 «unidades» de Pilar no eran unidades.** Ocho filas de `Compostura`
declaran ~99.900 cada una: es el centinela con que un sistema viejo modela un
servicio que no se agota. Once filas concentran 818.867 de las 837.403. No se
corrigió a mano: cuando la naturaleza es la correcta, un servicio no puede
llevar stock y el número desaparece solo. Pilar entra con **2.897**.

**El código no identifica al mismo artículo en las dos sucursales.** De 107
códigos de armazón compartidos, uno solo describe el mismo marco. `104627` es un
rojo fijo en Asunción y un dorado flex en Pilar. Tratarlo como SKU global habría
pegado dos marcos distintos en un artículo y sumado stock sobre algo inexistente.
Sólo son globales los códigos de barras de fabricante y el catálogo interno
compartido; el resto lleva prefijo de sucursal.

**Las sucursales no hubo que suponerlas.** `cash_register_branches`, sembrada por
las migraciones 018 y 020, ya dice `PC → ASUNCION` y `P2 → PILAR`. Los 8 pedidos
reales de esta instalación están en `PC`. `PC → ASUNCION` dejó de ser hipótesis.

## Naturaleza

13 categorías directas a `PRODUCTO_STOCKEABLE`. `Cristales` a
`TRABAJO_BAJO_PEDIDO`, justificada: la «marca» es el laboratorio que los fabrica
y el stock declarado son centinelas.

Dos quedan en `REQUIRES_POLICY_DECISION` y no se adivinaron: `Compostura`, que
mezcla servicios, cristales y repuestos en una sola categoría, y las 4 filas sin
categoría de Asunción, que parecen armazones — pero deducir la naturaleza del
texto es exactamente lo que el sistema prohíbe.

## Dry-run — PASS, 0 fallas

Sobre copia consistente de la base productiva, con el mecanismo real de dos
pasos, sin ningún atajo:

- catálogo: 3.529 altas, 0 rechazos, plan aplicable entero
- tras aplicarlo: 3.529 artículos y **0 movimientos** — catálogo no es stock
- inventario inicial: 3.579 movimientos `INGRESO_ADMINISTRATIVO` /
  `INVENTARIO_INICIAL`, 8.705 unidades a Asunción y 2.897 a Pilar
- cada movimiento con actor, motivo, explicación escrita, documento de origen y
  **la fecha del recuento, no la de hoy**: 2026-08-03 y 2026-08-10
- idempotencia: reaplicar el archivo se rechaza por sha256; repetir el recuento
  devuelve la misma corrida; 0 movimientos duplicados
- `integrity_check` ok, 0 violaciones de FK, 0 stock negativo, 0 huérfanos, 0
  efectos sin hecho
- Caja intacta: 12 entradas, 6.400.000, 10 líneas
- la base productiva quedó con el mismo sha256: nunca se abrió para escribir

## Lo que falta y por qué se para acá

Tres decisiones humanas, resumidas por reglas y no por registros: cómo se abre
`Compostura` (21 filas, tres grupos ya listados), si las 4 filas sin categoría
son armazones, y si los 2.860 limpia-cristales de Asunción son reales.

Están en `HUMAN_GATE.md` con el texto listo para responder. **No se carga nada
sobre producción hasta que estén respondidas.**
