# BC-CAJA-VISUAL-CLEAN-RC4-001

BC Caja 1.0.0-rc.4 presenta el estado ABIERTO en español, reordena Cliente,
Detalle de venta y Pago según el contrato operativo, incorpora selector de
calendario y convierte el panel lateral del borrador en Observaciones
multilínea persistente. Total de la venta y Saldo cliente son indicadores
calculados visualmente diferenciados.

Limpiar vacía la venta completa, la lista multiproducto y todos los campos de
Salida de caja —incluido Usuario—, elimina selecciones e identificadores y
cancela ambos modos de edición sin alterar registros persistidos.

## Evidencia

- Regresión: 160 passed.
- Smoke visual/funcional: PASS a 1366x768.
- EXE instalado self-check: exit 0.
- SQLite: integrity_check=ok; 12 migraciones aplicadas.
- Backup previo: `C:\Users\Usuario\AppData\Local\BC\Caja\Backups\bc-caja-pre-1.0.0-rc.4-20260813-235938-485238.sqlite3`.
- Backup SHA-256: `e4bc427d60177f53d37578b11b511f1cad80a6123efda985f094c463943fec50`.
- Base externa: `C:\Users\Usuario\AppData\Local\BC\Caja\bc_caja.sqlite3`.
- Instalación: `C:\Users\Usuario\AppData\Local\Programs\BC-Caja-Pilot`.
- rc.3 preservada: `C:\Users\Usuario\AppData\Local\Programs\BC-Caja-Pilot.previous-rc3`.
- Aplicación rc.4 abierta y operativa.
