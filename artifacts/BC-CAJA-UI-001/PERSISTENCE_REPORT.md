# Persistence Report

Base por defecto: `Datos/bc_caja.sqlite3`.

La base se crea únicamente cuando se compone la Caja en ejecución. Los tests usan rutas temporales y no generaron datos bajo `Datos/`.

## Flujo

```text
CajaDiaria.py
  → CashDayUIController
  → CashDayService
  → CashDayRepository
  → SQLiteCashDayRepository
  → bc_caja.sqlite3
```

## Garantías

- migración `001` idempotente;
- foreign keys activas;
- unicidad por fecha/unidad;
- agregado CashDay + entries guardado en transacción;
- rollback ante fallo;
- cierre y snapshot sobreviven reinicio;
- cash count persiste denominaciones y diferencia;
- consultas por ID, fecha/unidad y rango;
- sin dependencia de una DB de desarrollo.

## Compatibilidad TXT

`Datos/caja_diaria.txt` y las funciones legacy continúan presentes. Se usan solo como evidencia/compatibilidad y para que las caracterizaciones sigan ejecutándose. Los eventos normales de UI ya no llaman `agregar_registros`, `aplicar_importacion` ni `registrar_arqueo` legacy.

No existe migración automática TXT→SQLite todavía. Si aparecen datos TXT reales, su migración debe ser explícita, respaldada y probada en OPERATION-001.
