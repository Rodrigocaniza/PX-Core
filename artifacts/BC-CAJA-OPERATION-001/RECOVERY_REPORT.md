# Recovery Report

## Garantías implementadas

- cada operación UI confirmada termina en commit SQLite;
- el agregado se guarda con `BEGIN IMMEDIATE` y rollback ante error;
- `journal_mode=WAL` para base en archivo;
- `synchronous=FULL`;
- foreign keys y constraints activos;
- `PRAGMA quick_check` en composition root;
- migraciones versionadas y envueltas en transacción;
- migración 001→002 probada con datos preexistentes;
- backup consistente vía API `sqlite3.backup()` después del cierre;
- retención liviana de 30 backups;
- fallo de backup no revierte ni oculta el cierre ya persistido: se muestra advertencia.

## Cobertura de reinicio

Tests destruyen controller/repository y crean instancias nuevas sobre el mismo archivo. Caja, movimientos, estados, anulaciones, totales y snapshot se recuperan sin memoria compartida.

## Límite MVP

No hay restore automático ni reparación destructiva. Ante `quick_check` fallido, el arranque se detiene con error SQLite; la recuperación desde backup debe ser un procedimiento controlado antes del piloto.
