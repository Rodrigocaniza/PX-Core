# BC-CAJA-RC12-PEDIDOS-ATENCION-001

Slice mínimo de Pedidos bajo la filosofía **"qué requiere atención ahora"**, sobre la
baseline canónica real **BC Caja 1.0.0-rc.11** (`098b150`).

## Qué cambia

| Antes (rc.11) | Ahora (rc.12) |
| --- | --- |
| La grilla arrancaba vacía hasta tocar un filtro | Pedidos se puebla al abrir |
| Filtros `Hoy / Atrasados / Próximos / Todos` | `Requieren atención` (por defecto) / `Próximos` / `Todos` |
| Lista plana | Agrupada: `ATRASADOS · n` y `PARA HOY · n` |
| Sin resumen | Una línea que dice por dónde empezar |
| 9 columnas (con CI/RUC y Origen) | 8 columnas: entra `Última novedad`, salen CI/RUC y Origen |
| 3 botones `Marcar pendiente / listo / entregado` | 3 acciones: `Marcar listo`, `Marcar entregado`, `Corregir estado` |
| Motivo libre sólo al revertir ENTREGADO | Toda corrección: estado de lista cerrada + observación obligatoria |
| El aviso `⚠ Trabajos N` contaba atrasados pero abría `Hoy` | El aviso cuenta y abre exactamente `Requieren atención` |
| Sin acceso a WhatsApp | Doble clic sobre el teléfono abre WhatsApp, sin botón nuevo |

## Consulta canónica

`Requieren atención` = pedidos **no entregados** con `fecha de entrega <= hoy`.

Los grupos se devuelven siempre en orden de urgencia (`Atrasados`, `Para hoy`,
`Próximos`). Cuando no hay nada atrasado ni para hoy, la vista muestra `Próximos`
en lugar de una hoja vacía.

## Corregir estado (lista cerrada)

`ORDER_TRANSITIONS` en `domain/models.py` pasa a ser la única fuente de verdad de las
transiciones. El diálogo deriva su selector `readonly` de ahí, así que no existe forma
de tipear un estado libre. La observación y el responsable son obligatorios y quedan en
`order_status_revisions` (migración 014, sin cambios de esquema).

Retrocesos permitidos, sin tocar el dominio: `LISTO → PENDIENTE` y `ENTREGADO → PENDIENTE`.

## Alcance deliberadamente excluido

- **Laboratorio en la grilla**: hoy vive en `SaleItem`, no en `Order`. Mostrarlo exige un
  join contra `sale_items` y es un slice propio.
- Apertura de Caja, DatePicker compartido y FactuFácil: siguen en la cola, sin mezclar.
- **Reglas económicas de Caja: intactas.** Ningún cambio en montos, descuentos ni totales.

## Validación

- 206 pruebas + 4 subpruebas (188 de baseline + 18 nuevas). Suite completa en verde.
- Esquema estable en 14 migraciones.
- Evidencia visual **automática** revisada: `pedidos-atencion-1920x1080.png`,
  `pedidos-atencion-1366x768.png`, `corregir-estado-1920x1080.png`.
- Evidencia visual **real en la Óptica**: pendiente — ver `HUMAN_GATE.md`.
