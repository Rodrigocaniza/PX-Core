# Flujo operativo, alcance y aceptación

## Flujo de Sol

1. Sol abre BC Gestión Central y ve las cuatro unidades con datos sintéticos.
2. Elige `Desde` y `Hasta` (máximo 366 días) y compara días, ventas, salidas, diferencias, sincronización y alertas.
3. Entra en una unidad y revisa el detalle diario: ventas/sobres, salidas, arqueo, sincronización e integridad.
4. Abre Revisión de ventas y valida cada campo del cierre importado, incluidas receta/observaciones y estado explícito de PDF/FactuFácil cuando la fuente no lo provee.
5. Gestiona una alerta por `PENDIENTE → VISTO → CORREGIDO → VERIFICADO`, o la descarta desde PENDIENTE/VISTO.
6. Deja una indicación para una sucursal o PC. El mensaje queda local y `PENDING`; esta misión no lo entrega.

## Criterios de aceptación

- Selector de fechas validado y agregado por unidad, con detalle diario navegable.
- Estados `SINCRONIZADO`, `ATRASADO`, `INCOMPLETO` y `CONFLICTO` visibles.
- Máquina de estados de alertas persistente, autorizada y auditada.
- Mensajes idempotentes por unidad/PC en outbox local, sin red.
- Revisión existente campo por campo preservada; fuente BC Caja siempre de solo lectura.
- Navegación y controles operables en 1920×1080 y mínimo 1180×680.
- Datos de prueba sintéticos, efímeros y reproducibles.

## Exclusiones

- Sin conexión ni reglas de FactuFácil o comisiones; solo puntos de extensión y estado no disponible.
- Sin escritura a BC Caja, BC Finanzas, correo, Telegram o producción.
- Sin merge a `main` ni instalación productiva.

