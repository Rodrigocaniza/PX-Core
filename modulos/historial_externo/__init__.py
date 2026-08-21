"""BC Historial: proceso visual separado y lectura canónica de BC Caja.

La UI de Caja sólo lanza el proceso. La consulta vive detrás de un contrato
independiente y el adaptador SQLite abre la base real en modo de solo lectura.
"""

from .launcher import (
    HistorialNoDisponible,
    abrir_historial,
    comando_historial,
    construir_argumentos,
    hay_datos_de_cliente,
    ruta_ejecutable,
)
from .history import HistoryEvent, HistoryQuery, PersonHistory
from .sqlite_reader import SQLiteHistoryReader

__all__ = [
    "HistorialNoDisponible",
    "abrir_historial",
    "comando_historial",
    "construir_argumentos",
    "hay_datos_de_cliente",
    "ruta_ejecutable",
    "HistoryEvent",
    "HistoryQuery",
    "PersonHistory",
    "SQLiteHistoryReader",
]
