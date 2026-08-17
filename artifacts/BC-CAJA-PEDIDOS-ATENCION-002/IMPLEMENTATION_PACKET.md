# IMPLEMENTATION_PACKET — BC-CAJA-PEDIDOS-ATENCION-002

Port del slice de Pedidos a la línea canónica real.

**Baseline verificada: `origin/main` `098a9fb` = BC Caja 1.0.0-rc.14**
(225 pruebas + 4 subpruebas verdes en `tests` antes de tocar nada).

**Origen de referencia (no de merge):** `feature/bc-caja-rc12-pedidos-atencion-001` `41ee4ce`,
construido sobre rc.11 `098b150`. Se reutiliza como referencia; **no se mergeó**.

## Contrato funcional (lo que se conserva del slice viejo)

1. Consulta canónica `Requieren atención` = no entregados con entrega `<=` hoy.
2. Pedidos se puebla al abrir la ventana, nunca es una hoja vacía.
3. Contador del aviso y navegación sobre **exactamente** el mismo conjunto.
4. Agrupación `ATRASADOS · n` / `PARA HOY · n`, en orden de urgencia.
5. Fallback a `PRÓXIMOS` cuando no hay nada urgente.
6. Columna `Última novedad` (fecha · estado · responsable · motivo), en una sola consulta.
7. Máximo 3 acciones principales y 3 filtros.
8. `Corregir estado`: selector `readonly` derivado de `ORDER_TRANSITIONS`; sin estado libre.
9. Observación y responsable obligatorios en toda corrección.
10. Teléfono visible; WhatsApp por doble clic, sin botón nuevo.

## Invariantes (no negociables)

- **I1.** Todo lo canónico posterior a rc.11 queda intacto: arqueo (rc.12), administrador
  protegido y arqueos por correo (rc.13), recuperación de notificaciones (rc.14), outbox de
  sincronización y piloto de Gestión Central.
- **I2.** Reglas económicas de Caja sin cambios.
- **I3.** Sin migraciones nuevas: 15, última `015_admin_counts_notifications.sql`.
  El slice usa `order_status_revisions` (014) tal como ya existe.
- **I4.** Laboratorio en la grilla **fuera de alcance**: vive en `SaleItem`, no en `Order`,
  y exige un join contra `sale_items`.
- **I5.** No se toca la rama ni el worktree de `BC-CAJA-APERTURA-CAJA-001`.
- **I6.** No se toca `main`, no hay force-push.

## Archivos en alcance

| Archivo | Cómo se portó |
| --- | --- |
| `domain/models.py`, `application/ports.py`, `infrastructure/sqlite_repository.py` | Idénticos al slice viejo: `main` no los había tocado desde rc.11 (hash verificado) |
| `application/services.py` | Port manual: `main` tocó `record_cash_count`; se agregan `ATTENTION_*`, el filtro y `order_attention_groups` |
| `ui/controller.py` | Port manual: `main` tocó identidad canónica y salidas; se agregan los tres métodos de Pedidos |
| `CajaDiaria.py` | Port manual del bloque de Pedidos sobre la UI rc.14 |
| `tests/caja_diaria/test_pedidos_atencion_002.py` | Nuevo (del viejo `test_rc12_pedidos_atencion.py`, con el esquema actualizado a 15) |
| `test_operator_fixes_003.py`, `test_rc10_operative_polish.py`, `test_rc5_operational_ux.py` | Aserciones de contrato adaptadas a la nueva grilla |
| `tools/capture_caja_pedidos_atencion.py` | Nuevo: captura + contrato fail-closed |

## Tests

Focalizados: `test_pedidos_atencion_002`, `test_orders_v1`, `test_rc10_operative_polish`,
`test_rc5_operational_ux`, `test_operator_fixes_003`, `test_rc11_compact_tables`.
Regresión al cierre: `tests` completo.

## Definition of Done

- [x] Baseline rc.14 verificada antes de tocar nada.
- [x] Focalizados en verde.
- [x] `tests` completo en verde, sin perder ninguna de las 225 de baseline.
- [x] Evidencia visual automatizada 1920×1080 y 1366×768 + diálogo, hasheada.
- [x] MANIFEST + SUMMARY + ARTIFACT_CONSISTENCY + WORKFLOW.
- [x] Commit protegido en rama propia y push. `main` intacto.
- [x] NEXT_ACTION persistido.
- [ ] HUMAN_GATE-PEDIDOS-002 — pendiente, nuevo, sin reutilizar el viejo.
