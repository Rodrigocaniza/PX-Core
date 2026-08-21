"""Puente hacia BC Historial (integracion V1, por proceso externo).

BC Caja no lee el historico: lanza BC Historial como aplicacion aparte, ya
prefiltrada por el cliente en pantalla. Ver `docs/HISTORIAL_EXTERNO.md`.
"""

from .launcher import (
    HistorialNoDisponible,
    abrir_historial,
    construir_argumentos,
    hay_datos_de_cliente,
    ruta_ejecutable,
)

__all__ = [
    "HistorialNoDisponible",
    "abrir_historial",
    "construir_argumentos",
    "hay_datos_de_cliente",
    "ruta_ejecutable",
]
