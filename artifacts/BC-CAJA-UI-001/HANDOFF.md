# Handoff — BC-CAJA-UI-001

La UI legacy ya consume Core services y SQLite mediante controller/composition root.

Siguiente misión preparada: `BC-CAJA-OPERATION-001`.

Antes de piloto:

- resolver o mantener bloqueado el arrastre;
- validar workbook real;
- definir backup/recovery;
- exponer historial y correcciones controladas;
- probar con datos sintéticos o copia explícitamente autorizada.

No crear datos productivos, no borrar TXT y no conectar BC Gestión desde este handoff.

Toda continuidad permanece limitada a PX-Core / BC Caja.
