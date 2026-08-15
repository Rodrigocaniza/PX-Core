# Resumen

Bandeja y reporte mensual de comisiones por vendedora y local para BC Gestión Central,
local-first y sobre datos sintéticos.

Distingue con claridad ventas todavía no comisionables, ventas ya elegibles, convenios,
correcciones y reversiones, total informativo vendido, base comisionable y comisión calculada.

- La venta común comisiona sólo al quedar totalmente cancelada, en el período de esa cancelación.
- Los cobros parciales se muestran como información y nunca generan comisión pagable.
- El convenio es venta finalizada para comisión, con base = total − 5% aplicada exactamente una vez, y sin crear saldo cliente.
- Ocho estados con transiciones auditadas: `PENDIENTE_SALDO`, `ELEGIBLE`, `CALCULADA`, `REVISADA`, `APROBADA`, `PAGADA`, `OBSERVADA`, `REVERTIDA`. No se paga sin revisión y aprobación previas.
- Una liquidación pagada nunca se modifica en silencio: toda corrección posterior produce `OBSERVADA`.
- Importes enteros de guaraníes; porcentajes en puntos básicos; sin floats monetarios.

El porcentaje de comisión **no** se inventó: la base comisionable siempre se calcula y se muestra,
y el porcentaje queda como configuración sintética separada, marcada
`SINTETICA_PENDIENTE_APROBACION`. Es la única configuración pendiente de aprobación.

No integra nómina, BC-Finanzas, bancos ni liquidaciones contables externas. No modifica las
reglas de BC Caja. No contiene credenciales nuevas ni datos de clientes.

Base exacta: `eb6d082de4004d166379ffaae2b8f106fac10df1`.
Estado del workflow: `HUMAN_GATE_PENDING` (revisores independientes no disponibles).
