# BC Caja RC15 — UX operativa

Base canónica: `BC Caja 1.0.0-rc.14` / `42b8df26d5e055b16cc204902ec38de0d0de7355`.

Cambio limitado a layout, texto y limpieza de widgets. No modifica reglas económicas,
cálculos, servicios, migraciones, SQLite, correo, cierre ni datos.

- Observaciones/Receta ampliada y receta completa visible a 1366×768.
- Flujo visual: Cliente y comprobante → Detalle de venta → Pago → Observaciones y total.
- Limpiar junto a Guardar salida, violeta, y limpia venta más todos los campos de salida.
- Trabajos a entregar junto a Caja inicial y con ancho equivalente.
- No hay campo Usuario duplicado; la autoría proviene del responsable canónico de caja/sesión.
- Cinco movimientos mínimos, footer y Cerrar caja preservados.

Verificación: 205 pruebas PASS. Smoke GUI real 1366×768 PASS.
