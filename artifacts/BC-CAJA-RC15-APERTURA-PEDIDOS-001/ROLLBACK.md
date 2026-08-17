# ROLLBACK — BC Caja 1.0.0-rc.15

Rollback verificable y sin pérdida de datos. **Todo lo necesario ya está en su lugar
antes de instalar.**

## Punto de retorno

| Qué | Dónde |
| --- | --- |
| Base productiva | `%LOCALAPPDATA%\BC\Caja\Backups\bc-caja-pre-1.0.0-rc.15-20260817-161651-884812.sqlite3` |
| sha256 del backup | `3e9a6d405e24a462ef7de2750ddcd2a8356a1f6089ce4eab8bdaa591c7a4854d` (idéntico al original, verificado) |
| Aplicación instalada hoy | `%LOCALAPPDATA%\Programs\BC-Caja-Pilot` — **BC Caja 1.0.0-rc.11** |
| Paquete de esa versión | `releases/BC-CAJA-1.0.0-rc.11-win64.zip` |

## Por qué el rollback necesita el backup

La base productiva tiene **14 migraciones** aplicadas. rc.15 aplica la **015**
(`015_admin_counts_notifications.sql`, del administrador con arqueos por correo), que
**no tiene migración inversa**. Volver a rc.11 con la base ya migrada no está soportado:
el rollback restaura el archivo de base completo desde el backup.

## Procedimiento (transaccional)

1. Cerrar BC Caja.
2. Renombrar `%LOCALAPPDATA%\Programs\BC-Caja-Pilot` a `BC-Caja-Pilot.failed-rc15`
   (no borrar: es evidencia).
3. Restaurar la instalación anterior: descomprimir `BC-CAJA-1.0.0-rc.11-win64.zip` en
   `%LOCALAPPDATA%\Programs\BC-Caja-Pilot`.
4. Restaurar la base: copiar el backup sobre `%LOCALAPPDATA%\BC\Caja\bc_caja.sqlite3`.
5. Verificar sha256 de la base restaurada contra el del backup.
6. Abrir BC Caja y confirmar que el pie dice `BC Caja 1.0.0-rc.11`.

## Qué se pierde al hacer rollback

Todo lo cargado **después** de la instalación de rc.15. Por eso la instalación conviene
hacerla con la caja del día cerrada o antes de abrirla.

## Instalación transaccional de rc.15

1. Backup previo — **ya hecho y verificado**.
2. Cerrar BC Caja.
3. Renombrar la instalación actual a `BC-Caja-Pilot.previous-rc11` (queda como evidencia,
   igual que las anteriores `previous-rcN`).
4. Descomprimir `releases/BC-CAJA-1.0.0-rc.15-win64.zip` en
   `%LOCALAPPDATA%\Programs\BC-Caja-Pilot`.
5. Primer arranque: aplica la migración 015 sobre la base real.
6. Verificar pie `BC Caja 1.0.0-rc.15` y que los datos del día siguen ahí.
7. Si algo falla en cualquier paso: ejecutar el rollback de arriba.
