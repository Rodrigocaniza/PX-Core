# HUMAN_GATE — BC Historial en PC/P2

Ejecutar únicamente en los hosts físicos autorizados de la Óptica. No usar
Telegram y no reutilizar ni reemplazar el installation binding de Seguridad BC.

1. Verificar que el checkout sea `feature/bc-historial-multisucursal-v1-001`
   y contenga el commit de implementación `2cd88689863a1153445f6194294bbef866935ff1`.
2. Verificar SHA-256 del ZIP contra `MANIFEST.json` antes de abrirlo.
3. En cada host, identificar explícitamente la sucursal real de la instalación.
4. Con una sesión real de operadora, comprobar que una búsqueda sólo devuelve
   ventas/trabajos de su sucursal, incluso si el mismo CI/RUC existe en la otra.
5. Con Admin real, comprobar consulta de Asunción y Pilar.
6. Con Visor Federado provisto por Seguridad BC, comprobar ambas sucursales y
   confirmar que no existe ninguna acción de escritura.
7. Probar CI/RUC exacto, nombre, teléfono y sobre/trabajo; confirmar fecha,
   sucursal, tipo, sobre, estado, importe y detalle.
8. Intentar búsqueda vacía, rol no autorizado, sesión vencida y registro sin
   sucursal; todos deben fallar cerrados o quedar excluidos.
9. Confirmar que la base productiva no cambia (tamaño/hash/mtime según el
   procedimiento local autorizado) y que el lector abre `mode=ro/query_only`.
10. Registrar evidencia real separada por host, actor, rol, sucursal, fecha,
    commit y resultado. No marcar despliegue completo si falta uno de los hosts.

Resultado esperado: PC y P2 validados físicamente con Admin global, operadora
local y Visor Federado global/read-only. Ante cualquier discrepancia, detener y
devolver el hallazgo sin fabricar evidencia.
