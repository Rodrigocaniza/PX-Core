# Evidencia SAFE

- `python -m pytest tests/caja_diaria/test_historial_multisucursal.py tests/caja_diaria/test_historial_externo.py tests/caja_diaria/test_historial_reader.py -q`: 57 PASS.
- `python -m pytest tests/caja_diaria -q`: 1022 PASS, 37 skip, 0 fail.
- `git diff --check`: PASS (sólo avisos informativos LF/CRLF de Windows).
- GitHub Actions `PR CI / pytest`, run `32594536940`: PASS.

Cobertura adversarial añadida: token fabricado, sujeto/rol/sucursal vacíos,
visor con claim de escritura, operadora con claim global accidental, hechos sin
sucursal, más de 200 hechos ajenos desplazando uno local y filtro SQLite antes
de `LIMIT`.
