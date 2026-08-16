# Escenario TEST — circuito Pilar → Asunción → Laboratorio → Pilar

Preparado sobre la instalación productiva `BC Caja 1.0.0-rc.21` para que el
circuito pueda probarse a mano de punta a punta.

## Método de seed elegido, y por qué

No existe en BC Caja un mecanismo de seed/demo pensado para la base instalada,
así que se descartó la opción 1. De las dos restantes se tomó **la de menor
impacto**, siguiendo la preferencia explícita de crear los trabajos sin
impacto económico productivo.

**Los quince trabajos se crearon como `orders` con `cash_entry_id` nulo**, vía
la API canónica del repositorio. El dominio lo admite: un pedido puede existir
sin venta asociada. Consecuencia: **no se creó ni una sola venta**. Sin
`cash_entries`, sin `sale_items`, sin importes, sin saldo, sin convenio, sin
salida de caja, sin arqueo, sin comisión, sin correo.

Se añadió además una **caja TEST** con unidad `PILAR`, fecha 15/08/2026,
apertura 0 y cero movimientos, cerrada, como ancla del escenario. Es inerte:
la búsqueda de candidatos no la consulta, y su contenido económico es nulo.
Ninguna caja productiva fue tocada.

La sucursal `PILAR` no existía en la base, así que todo lo TEST es
inequívocamente distinguible de lo real, que vive todo en `PC`.

## Qué se creó

| Item | Detalle |
|---|---|
| Caja TEST | `2b889860-35d5-4199-9f90-257052e84ea3` · unidad `PILAR` · 15/08/2026 · CLOSED · 0 movimientos · apertura 0 |
| Pedidos | 15, sobres `TEST-P-001` … `TEST-P-015`, clientes `Cliente Prueba 01` … `15` |
| Vendedora | `Nidia (TEST)` |
| Tipos | Cristal · Armazón + Cristal · Sol · Armazón (texto libre, como en el formulario real) |
| Creación | 15/08/2026 |
| Entrega | 22/08/2026, para no inflar el aviso de trabajos del día |
| Laboratorios | `LAB PRUEBA ALFA` (021 555 101 / 0981 555 201), `LAB PRUEBA BETA` (021 555 102 / 0982 555 202), `LAB PRUEBA GAMMA` (021 555 103 / 0983 555 203) |

Línea y WhatsApp son distintos en los tres, para ejercitar esa diferencia.
Los IDs exactos están en `TEST_DATA_MANIFEST.json`.

## Estado de partida

Los quince quedan **sin entrar al circuito**: `tracked_works` sigue en 0. El
primer estado lo produce el usuario al crear el envío. No se avanzó ningún
estado automáticamente.

## Datos reales preservados

Único delta en toda la base: `cash_days` 6→7, `laboratories` 0→3,
`orders` 2→17. Todo lo demás idéntico.

```
cash_entries 8   sale_items 2   cash_counts 3   cash_count_snapshots 1
mail_outbox 1    mail_history 5 pedidos reales PC 2   cierres PC 2
```

Cero correos, cero cierres productivos nuevos, cero ventas modificadas.
`integrity_check=ok`.

## Reversión

`tools/cleanup_escenario_test.py` borra **solo por id exacto** lo listado en el
manifiesto, nunca por patrón. Simula por defecto; requiere `--aplicar`.
Incluye una salvaguarda: si la caja TEST llegara a tener movimientos, aborta
sin borrar nada. Simulación ejecutada y correcta. **No aplicada.**

Backup previo completo: `%LOCALAPPDATA%\BC\Caja-ESCENARIO-TEST-preseed-20260816`.
