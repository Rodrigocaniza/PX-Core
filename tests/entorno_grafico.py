"""Distinguir «no hay pantalla» de «hay pantalla y algo salió mal».

Vivía dentro de `tests/caja_diaria/test_arranque_ventana_principal.py`, donde
se escribió después de que un `except Exception` suelto convirtiera una falla
real en un salteo. Un salteo se lee como verde: la prueba que existía para que
la ventana no dejara de abrir dejó de correr sin avisar, y así fue como ese
fallo llegó hasta la Óptica.

Está acá arriba porque las pruebas de UI de Gestión Central necesitan la misma
guarda, y copiarla habría sido copiar también el próximo arreglo que reciba.
"""

from __future__ import annotations

#: Lo que dice Tcl cuando el intérprete gráfico directamente no existe.
_PISTAS = (
    "no display name", "display name", "couldn't connect",
    "can't find a usable", "no $display",
)


def sin_pantalla(error: BaseException) -> bool:
    """`True` sólo si el intérprete gráfico no existe, y no si existe y falló."""
    motivo = str(error).lower()
    return any(pista in motivo for pista in _PISTAS)
