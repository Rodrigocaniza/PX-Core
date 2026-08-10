# Test Evidence — BC-CAJA-UI-001

Comando canónico repo-scoped:

```text
python -m unittest discover -s tests -p "test_*.py" -v
python -m compileall -q CajaDiaria.py modulos/caja_diaria tests/caja_diaria
```

Resultado fresco antes de artifacts:

- 39 tests ejecutados;
- 39 PASS;
- 0 failures;
- 0 errors;
- compilación correcta.

Cobertura funcional agregada:

- controller inyectable;
- base nueva en ruta temporal;
- apertura o recuperación por fecha/unidad;
- caja inicial obligatoria solo en primera apertura;
- alta manual y traducción completa de campos;
- persistencia y reload con una instancia nueva;
- totales después de reload;
- cierre persistido y bloqueo posterior;
- importación legacy hacia SQLite;
- entrada inválida no crea la Caja;
- error SQLite no expone traceback/SQL;
- import de `interfaz.py` y entry point disponibles sin arrancar GUI.

No se ejecutaron tests frágiles de píxeles ni se creó una base productiva.
