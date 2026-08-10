# Handoff — BC-CAJA-CORE-001

Resultado: foundation implementada y suite verde en PX-Core.

Siguiente paso mínimo recomendado: una misión `BC-CAJA-EXCEL-001` para extraer/adaptar el importer legacy hacia el nuevo dominio con preview atómico y errores explícitos. Debe mantener `PENDING_REAL_WORKBOOK_VALIDATION` hasta poder comparar `Agosto PC 2026.xlsx`.

No conectar todavía la UI directamente al repositorio: la UI debe consumir `CashDayService` mediante el composition root.

No implementar arrastre ni reapertura hasta resolver sus gates de negocio.

No se autoriza desde este handoff ningún commit/push ni trabajo sobre otros repositorios.

Archivos canónicos de revisión:

- `modulos/caja_diaria/domain/`
- `modulos/caja_diaria/application/`
- `modulos/caja_diaria/infrastructure/`
- `modulos/caja_diaria/bootstrap.py`
- `tests/caja_diaria/`
- `artifacts/BC-CAJA-CORE-001/SUMMARY.md`
