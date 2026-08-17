# PREFLIGHT rc.11 → rc.15

Ejecutado antes de tocar la instalación real. **Fail-closed.**

## 1. Precheck canónico — PASS

| Verificación | Resultado |
| --- | --- |
| Ruta instalada | `%LOCALAPPDATA%\Programs\BC-Caja-Pilot` |
| Versión instalada | **BC Caja 1.0.0-rc.11** |
| Base productiva | `%LOCALAPPDATA%\BC\Caja\bc_caja.sqlite3`, 180.224 bytes |
| `integrity_check` | ok |
| `foreign_key_check` | 0 violaciones |
| Migraciones aplicadas | 14 (última `014`), sin `015` |
| Caja de **hoy** abierta | no — se puede instalar |
| Procesos BC Caja | ninguno corriendo |
| Backup disponible | sí, `bc-caja-pre-1.0.0-rc.15-20260817-161651-884812.sqlite3` |
| Espacio libre | 100,4 GB |
| Permisos de escritura | instalación y datos, OK |
| Configuración SMTP | **ninguna** — rc.13 arranca con el correo sin configurar |
| Datos reales | 2 días, 12 movimientos, 8 pedidos, 10 ítems de venta |

**Aviso registrado:** los días **12/08 y 13/08 quedaron `OPEN`**. Con rc.15 el histórico es
sólo lectura, así que **esos dos días ya no se pueden cerrar desde la UI**. No bloquea la
instalación —son días viejos sin arqueo— pero hay que decidir qué se hace con ellos.

## 2. Validación sobre clon productivo — PASS

Copia de la base real en un directorio aislado; migración por el flujo soportado
(`build_cash_day_controller`), sin tocar SQLite a mano y **sin enviar ningún correo**.

| Verificación | Resultado |
| --- | --- |
| Migración `015` aplicada | sí — 15 migraciones |
| `integrity_check` / `foreign_key_check` post-migración | ok / 0 |
| `cash_days`, `cash_entries`, `orders`, `sale_items` | 2, 12, 8, 10 → **idénticos** |
| **Reglas económicas** | sumas `total`/`cash`/`expenses` idénticas: `(6.400.000, 2.200.000, 250.000)` |
| Cajas iniciales | idénticas |
| Apertura rc.15 | abre hoy, `opened_at` con zona horaria, responsable canónico |
| Historial | día 12/08 legible con sus 5 movimientos |
| Arqueo (rc.12) | registra e es idempotente al reabrir |
| Administrador (rc.13) | crea admin inicial, autentica y **rechaza clave incorrecta** |
| Correo | `enabled: false`, sin destinatario → **NOT_CONFIGURED** |
| Cierre con arqueo | cierra; contado 1.300.000 = esperado 1.300.000 |
| Outbox | **0 correos enviados** sin configuración |
| Pedidos | 3 grupos; el aviso coincide con la consulta; 8 pedidos reales preservados |
| Historial auditado | revisión `PENDIENTE → LISTO` con responsable y motivo |
| Lista cerrada | `LISTO → (PENDIENTE, ENTREGADO)` |
| Integridad final | ok / 0 |

**Resultado: `rc.11 → rc.15` válida sobre datos productivos reales.**
