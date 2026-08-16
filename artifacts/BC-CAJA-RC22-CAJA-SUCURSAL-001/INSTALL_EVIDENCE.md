# Install Evidence — BC Caja 1.0.0-rc.22

## Precheck

| Comprobación | Resultado |
|---|---|
| Instancias activas | 0 |
| Versión instalada | `1.0.0-rc.21` |
| `integrity_check` | ok |
| Esquema | 001–018 |
| SHA256 ZIP | `3820A9F730B7AC06C3008B8F299AA7F5933509105784D37F64F5CB65278B7B1C` |
| SHA256 EXE | `D5B64332A4A2DCF0EFB87EC3A3CD48C32304EBEC3B4AEBC53ECE0D3DEF484695` |

## Backup y rollback

- Data root → `%LOCALAPPDATA%\BC\Caja-RC22-preinstall-20260816c` (33 archivos).
- rc.21 → `BC-Caja-Pilot.rollback-rc21-20260816c`.
- Preservados: rollbacks de rc.20, rc.17, rc.16 y rc.15.

## Instalación

Reemplazo transaccional con staging validado, carpeta vigente apartada en
lugar de borrada y restauración inmediata ante fallo. Solo la carpeta del
programa.

## Post-install

| Comprobación | Resultado |
|---|---|
| Versión | `BC Caja 1.0.0-rc.22` |
| Arranque | abre y sostiene la ventana |
| Migraciones | 001–018 |
| `integrity_check` | ok |
| Datos | **ninguna diferencia** contra el precheck |
| Binding caja→sucursal | `PC → ASUNCION`, `PILAR → PILAR` (`P2` sin asignar) |
| Económico | `cash_entries` 8, `sale_items` 2, cierres 3, outbox 1, `mail_history` 5 — sin cambios |
| Escenario TEST | 15 pedidos PILAR, 0 en circuito, 3 laboratorios |
| Correos / cierres nuevos | 0 / 0 |
| Rollback usado | NO |

El escenario TEST queda en su punto inicial, listo para la prueba manual.

## Límite conocido, sin cambios

La GUI del ejecutable congelado no es conducible por automatización: los
controles de CustomTkinter se dibujan sobre canvas. La vista por sucursal y
las alertas quedan verificadas por la suite y por los smokes sobre el mismo
commit empaquetado.
