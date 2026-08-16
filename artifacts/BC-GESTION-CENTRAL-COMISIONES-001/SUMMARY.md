# Resumen

Bandeja y reporte mensual de comisiones por vendedora y local para BC Gestión Central,
local-first y sobre datos sintéticos.

Distingue con claridad ventas todavía no comisionables, ventas ya elegibles, convenios,
correcciones y reversiones, total informativo vendido, base comisionable y comisión calculada.

- La venta común comisiona sólo al quedar totalmente cancelada, en el período de esa cancelación.
- Los cobros parciales se muestran como información y nunca generan comisión pagable.
- El convenio es venta finalizada para comisión, con base = total − 5% aplicada exactamente una vez, y sin crear saldo cliente.
- Ocho estados con transiciones auditadas: `PENDIENTE_SALDO`, `ELEGIBLE`, `CALCULADA`, `REVISADA`, `APROBADA`, `PAGADA`, `OBSERVADA`, `REVERTIDA`. No se paga sin revisión y aprobación previas.
- Una liquidación que alguna vez movió dinero nunca alcanza `REVERTIDA`, ni pasando por `OBSERVADA`: toda corrección posterior al pago produce `OBSERVADA`, y el índice de unicidad sigue impidiendo un segundo pago de la misma venta.
- El período de liquidación sólo puede derivarse de una fecha ISO real: una fecha mal formada se rechaza en el borde en vez de generar un mes inexistente.
- Importes enteros de guaraníes; porcentajes en puntos básicos; sin floats monetarios.

El porcentaje de comisión **no** se inventó: la base comisionable siempre se calcula y se muestra,
y el porcentaje queda como configuración sintética separada, marcada
`SINTETICA_PENDIENTE_APROBACION`. Es la única configuración pendiente de aprobación.

No integra nómina, BC-Finanzas, bancos ni liquidaciones contables externas. No modifica las
reglas de BC Caja. No contiene credenciales nuevas ni datos de clientes.

Base exacta: `eb6d082de4004d166379ffaae2b8f106fac10df1`.

Este snapshot es la **generación 7 y está pendiente de revisión independiente**. Las generaciones
1 a 6 fueron revisadas por runners independientes y las seis resultaron invalidadas: catorce
bloqueantes financieros reales, todos corregidos y cubiertos por pruebas. Tres de ellos fueron
introducidos por una corrección anterior. Detalle y verdicts en `INDEPENDENCE.md` y en los
directorios `generation-1/` a `generation-6/`.
