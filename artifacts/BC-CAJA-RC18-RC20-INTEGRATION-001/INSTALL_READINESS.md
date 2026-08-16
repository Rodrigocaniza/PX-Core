# Install Readiness — BC-CAJA-RC18-RC20-INTEGRATION-001

## Estado actual del equipo

| Item | Valor |
|---|---|
| Versión instalada | `BC Caja 1.0.0-rc.17` |
| Ruta del programa | `%LOCALAPPDATA%\Programs\BC-Caja-Pilot` |
| Ejecutable | `BC-Caja.exe`, 8.407.716 bytes, 15/08/2026 |
| Datos | `%LOCALAPPDATA%\BC\Caja\bc_caja.sqlite3`, 270.336 bytes |
| Esquema en producción | migraciones 001–015 |
| Rollbacks disponibles | `BC-Caja-Pilot.rollback-rc16-20260815`, `...rollback-rc15-20260815` y 8 versiones previas |
| Backups | `%LOCALAPPDATA%\BC\Caja\Backups` con historial pre-instalación por versión |

## Qué cambia al instalar

- **Esquema**: 015 → 017. Agrega `laboratories`, `tracked_works`,
  `tracked_work_transitions`, `tracked_work_contacts`, `pilar_shipments` y la
  clave `tracking` en `app_settings`. **No modifica ninguna tabla existente**
  salvo agregar la columna `shipment_id` a `tracked_works`, que es nueva.
- **UI**: jerarquía del resumen de caja (RC18), pestaña Seguimiento (RC19),
  alta de lote y ABM de laboratorios (RC20).
- **Nada económico**: ningún cambio en importes, cierres, arqueos, correo ni
  convenios, verificado por diff sobre la cadena completa.

## Ensayo de migración ya realizado

Sobre una copia de la base **real** de producción, obtenida con la API de
backup de SQLite sin abrir el archivo productivo en escritura:

```
ANTES   001..015 | cash_days=6 cash_entries=8 orders=2 mail_outbox=1 counts=1
DESPUES 001..017 | cash_days=6 cash_entries=8 orders=2 mail_outbox=1 counts=1
integrity_check=ok · datos preservados=True · archivo productivo intacto=True
```

## Secuencia de instalación preparada

1. Cerrar BC Caja si está en ejecución.
2. Backup del data root completo a
   `%LOCALAPPDATA%\BC\Caja-INTEGRATION-preinstall-<fecha>`.
3. Copiar la instalación vigente a
   `%LOCALAPPDATA%\Programs\BC-Caja-Pilot.rollback-rc17-<fecha>`.
   **RC17 no se elimina.**
4. Construir el paquete desde la rama integrada (`pilot/build_pilot.ps1`).
5. Reemplazar únicamente la carpeta del programa.
6. Post-install: arranque, versión, acceso a datos existentes, UI RC18,
   pestaña Seguimiento RC19, alta de lote y ABM RC20, `integrity_check`,
   y verificación de cero correos y cero cierres nuevos.
7. Ante cualquier falla: restaurar la carpeta de rollback y el data root.

## Por qué no está ejecutada

La política canónica de BC Caja, establecida en RC17
(`SAFE_CLOSURE_READY · publication: HUMAN_GATE_REQUIRED · installation:
false`), exige autorización humana explícita para instalar. RC18, RC19 y RC20
registraron `installation: false` por el mismo motivo.

La instalación reemplaza el programa que la óptica usa en producción, así que
requiere el gate consolidado: **integración validada → instalación →
validación post-instalación**.
