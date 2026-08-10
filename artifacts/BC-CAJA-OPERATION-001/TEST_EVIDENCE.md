# Test Evidence

Comandos:

```text
python -m unittest discover -s tests -p "test_*.py" -v
python -m compileall -q CajaDiaria.py interfaz.py modulos/caja_diaria tests/caja_diaria
```

Resultado fresco:

- 46 tests ejecutados;
- 46 PASS;
- 0 failures;
- 0 errors.

Cobertura nueva:

- edición y anulación lógica;
- totales excluyen anulados;
- historial y revisión append-only;
- migración de DB 001 a 002 sin pérdida;
- cierre bloquea edición/anulación;
- backup válido y consultable;
- ruta configurada estable;
- separación database/Backups/Logs;
- base explícita de tests no toca ruta productiva;
- E2E de dos días con dos restarts completos.

No se creó `bc_caja.sqlite3` dentro del repo ni se usaron datos reales.
