# UI → Core Mapping

| WIDGET / EVENTO | COMPORTAMIENTO LEGACY | SERVICE / CONTROLLER NUEVO |
|---|---|---|
| Menú `Caja diaria (Óptica)` | Abre `CajaDiaria.abrir_caja_diaria(self)` | Misma llamada; controller se compone por defecto |
| Fecha + Unidad | Datos de una línea TXT | `open_or_load_day()` / `get_by_date_and_unit()` |
| Caja inicial | Solo fila especial del Excel | `CashDayService.open_day()`; requerida al crear |
| Botón `Abrir / Consultar Caja` | No existía | Recupera SQLite o abre una Caja nueva |
| Campos manuales | Alta TXT inmediata | `add_manual_entry()` → `add_entry()` → repository |
| Botón `Guardar registro` | `agregar_registros()` TXT | Escritura transaccional SQLite y refresh de totales |
| Estado/totales bajo formulario | No existía en carga manual | `CashDay.totals()`; muestra OPEN/CLOSED y acumulados |
| Botón `Cerrar Caja` | Cálculo efímero sin estado | `close_day()`; snapshot persistido y bloqueo |
| Elegir/analizar Excel | Parser legacy | Se conserva como preview provisional |
| Botón `Importar` | `aplicar_importacion()` TXT | `import_legacy_analysis()` → Core/SQLite |
| Errores del Excel | Avisos no bloqueantes | Errores bloquean importación; no se guarda parcialmente por error de parsing |
| Arqueo | `registrar_arqueo()` TXT | `record_cash_count()` → `cash_counts` SQLite |
| Consulta tras reinicio | Relectura TXT técnica | Controller/service reconstruye agregado desde SQLite |
| Edición/eliminación | Sin UI; eliminación completa de día | Core lo soporta por ID en OPEN; UI aún no lo expone |
| Historial | Sin pantalla | Puerto/query existe; queda para OPERATION-001 |

La UI no accede al repositorio ni a SQLite directamente.
