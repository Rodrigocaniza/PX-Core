# Veredicto — HUMAN_GATE-RC15-INSTALADA-001

**PASS.** Registrado el 2026-08-17 sobre **rc.15 ya instalada y corriendo con los datos
reales de la Óptica**.

## Alcance del PASS

Los 11 puntos del gate:

1. El pie muestra `BC Caja 1.0.0-rc.15`.
2. Apertura con fecha de hoy no tipeable; `ABRIR CAJA DE HOY` no pregunta fecha ni hora.
3. `Caja inicial` destacada y estado con la hora real de apertura.
4. `Arqueo` accesible (rc.12).
5. `Administrador` accesible (rc.13).
6. Pedidos abre en `Requieren atención` con los pedidos reales agrupados.
7. **Contraste corregido:** acción disponible sólida, no disponible claramente apagada, con
   el motivo al pasar el mouse.
8. `Historial` muestra los movimientos existentes.
9. `Consultar otro día` carga el histórico en sólo lectura.
10. Cierre con arqueo, sin intentar enviar correo (correo deshabilitado).
11. Regresión 1366×768: 8 columnas sin scroll horizontal y contraste mantenido.

## Cadena de validación que respalda este PASS

| Etapa | Resultado |
| --- | --- |
| Gates de origen | `HUMAN_GATE-APERTURA-CAJA-001` PASS · `HUMAN_GATE-PEDIDOS-002` PASS |
| Preflight canónico sobre producción | PASS |
| Migración rc.11 → rc.15 sobre clon de la base real | PASS |
| Pruebas | 258 + 4 subpruebas |
| Evidencia visual fail-closed | 9 capturas, 1920×1080 y 1366×768 |
| Instalación transaccional | OK, con backup preinstall y rc.11 preservada |
| Verificación post-install sobre la base productiva | PASS |

## Estado tras el PASS

**rc.15 queda como versión instalada y validada.** Rollback disponible y verificado
(`ROLLBACK.md`) mientras se conserven el backup preinstall y `BC-Caja-Pilot.previous-rc11`.

Queda pendiente, fuera de este gate: los días **12/08 y 13/08** siguen `OPEN` y con el
histórico en sólo lectura ya no se pueden cerrar desde la pantalla.
