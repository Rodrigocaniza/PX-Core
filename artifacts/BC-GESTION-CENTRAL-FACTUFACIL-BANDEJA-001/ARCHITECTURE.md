# Arquitectura y flujo FactuFácil

## Flujo operativo

1. Leti, Ana o Dayana abre la bandeja FactuFácil desde Gestión Central.
2. Filtra ventas `PARA_CARGAR`, abre una fila y copia datos en el orden del formulario externo.
3. Observaciones/receta se muestra completa, preserva saltos y puede copiarse con una acción.
4. La operadora realiza la carga manual fuera del sistema; Gestión Central no abre ni controla FactuFácil.
5. Registra responsable y número de comprobante; la venta pasa a `CARGADO` una sola vez.
6. Una corrección posterior que cambie contenido cargado pasa a `OBSERVADO` y conserva versiones/historial.
7. Una marcación errónea se revierte únicamente con motivo y queda `REVERTIDO`; puede volver a prepararse explícitamente.

## Arquitectura local-first

- Proyección SQLite durable separada de la revisión de ventas.
- Identidad estable SHA-256 de sucursal + venta fuente + sobre; unicidad adicional de sucursal/sobre cuando existe.
- Payload canónico versionado y hash; historial append-only.
- Servicio de aplicación desacoplado de Tk y de cualquier proveedor externo.
- `FactuFacilExportPort` define exportación estructurada futura; el adaptador actual solo produce datos locales para portapapeles.
- Sin HTTP, navegador, credenciales, secretos ni automatización externa.

## Estados

`PARA_CARGAR → EN_PROCESO → CARGADO`; edición posterior cargada → `OBSERVADO`; `CARGADO|OBSERVADO → REVERTIDO`; `REVERTIDO|OBSERVADO → PARA_CARGAR` mediante preparación explícita.

## Permisos

- `ADMIN_CENTRAL` y `SUPERVISOR`: lectura, preparación, carga y reversión.
- `AUDITOR`: lectura e historial, sin mutaciones.
- `OPERADOR_LOCAL`: sin acceso a bandeja central.

## Aceptación y exclusiones

Filtros, copia ordenada, receta multilínea íntegra, carga no duplicable, reversión motivada, observación por cambio, reapertura, múltiples sucursales, integración con revisión central y UI 1920×1080. No se automatiza FactuFácil, no se usan ventas reales y no se implementan comisiones.
