# BC-CAJA-PEDIDOS-ATENCION-002 — Pedidos, qué requiere atención ahora

Port del slice de Pedidos a la línea canónica real: **`origin/main` `098a9fb` = BC Caja
1.0.0-rc.14**. Reemplaza a `BC-CAJA-RC12-PEDIDOS-ATENCION-001`, que había quedado colgado
de rc.11 y no integraba.

## Qué cambia respecto de rc.14

| rc.14 | Ahora |
| --- | --- |
| La grilla arrancaba vacía hasta tocar un filtro | Pedidos se puebla al abrir la ventana |
| Filtros `Hoy / Atrasados / Próximos / Todos` | `Requieren atención` (por defecto) / `Próximos` / `Todos` |
| Lista plana | Agrupada: `ATRASADOS · n` y `PARA HOY · n`, en orden de urgencia |
| Sin resumen | Una línea que dice por dónde empezar |
| 9 columnas (con CI/RUC y Origen) | 8 columnas: entra `Última novedad`, salen CI/RUC y Origen |
| 3 botones `Marcar pendiente / listo / entregado` | 3 acciones: `Marcar listo`, `Marcar entregado`, `Corregir estado` |
| Motivo libre sólo al revertir ENTREGADO | Toda corrección: estado de lista cerrada + observación obligatoria |
| El aviso `⚠ Trabajos N` contaba atrasados pero abría `Hoy` | El aviso cuenta y abre exactamente `Requieren atención` |
| Sin acceso a WhatsApp | Doble clic sobre el teléfono abre WhatsApp, sin botón nuevo |

`Requieren atención` = pedidos **no entregados** con `fecha de entrega <= hoy`.
`ORDER_TRANSITIONS` en `domain/models.py` es la única fuente de verdad de las transiciones;
el selector `readonly` del diálogo se deriva de ahí, así que no existe forma de tipear un
estado libre. La corrección queda en `order_status_revisions` (migración 014, ya existente).

## Diferencias respecto del slice viejo (rc.12-pedidos)

1. **Base distinta:** rc.14 en vez de rc.11. Todo lo canónico posterior queda intacto —
   arqueo, administrador protegido, arqueos por correo, recuperación de notificaciones,
   outbox de sincronización y piloto de Gestión Central.
2. **No hubo merge.** Los tres archivos que `main` no había tocado desde rc.11
   (`domain/models.py`, `application/ports.py`, `infrastructure/sqlite_repository.py`) se
   portaron byte a byte — sus sha256 coinciden con los del MANIFEST viejo. `services.py`,
   `ui/controller.py` y `CajaDiaria.py` se reescribieron a mano sobre rc.14, respetando los
   cambios que `main` había hecho en esas mismas funciones.
3. **Esquema:** el test de contrato pasó de exigir 14 migraciones a exigir 15, conservando
   la 014 que este slice necesita. El port **no agrega migraciones**.
4. **Evidencia visual endurecida:** la captura dejó de ser sólo una foto. Ahora verifica el
   contrato y aborta si no se cumple, incluida la comprobación de que los controles de
   rc.14 (`Arqueo`, `Administrador`) siguen presentes.
5. **Nombres:** `test_pedidos_atencion_002.py` y `capture_caja_pedidos_atencion.py` — el
   prefijo `rc12` quedó tomado por el arqueo canónico.
6. **HUMAN_GATE nuevo.** El viejo no se reutiliza ni se hereda su estado.

## Validación

**Automática:** 243 pruebas + 4 subpruebas en `tests` (225 de baseline + 18 nuevas).
Baseline de `main` medida antes de tocar nada: 225 + 4.

**Visual automatizada:** `tools/capture_caja_pedidos_atencion.py` levanta la UI real con un
día sembrado (3 atrasados, 2 para hoy, 1 próximo) y **falla si el contrato no se cumple**:

1. las 8 columnas de `ORDER_COLUMN_SPECS`;
2. la grilla arranca con un encabezado de grupo y trae `ATRASADOS` y `PARA HOY`;
3. la línea de resumen dice por dónde empezar;
4. exactamente 3 acciones y 3 filtros, sin `Marcar pendiente`;
5. `Arqueo` y `Administrador` de rc.14 siguen ahí;
6. el texto del aviso coincide con el conjunto que abre, y la grilla muestra esa cantidad;
7. con `--dialogo`: el selector es `readonly` y sus valores salen del dominio.

Tres capturas: grilla a 1920×1080 y 1366×768 (8 columnas sin scroll horizontal) y el
diálogo `Corregir estado`.

**Humana:** pendiente. Ver `HUMAN_GATE.md`. No se reutilizó ningún PASS anterior.

## Fuera de alcance

- **Laboratorio en la grilla:** vive en `SaleItem`, no en `Order`; exige join contra
  `sale_items` y es su propio slice.
- `BC-CAJA-APERTURA-CAJA-001`: rama y worktree intactos, esperando su propio gate.
