"""Qué hacer con el stock de lo que ya pasó. Respuesta corta: nada.

Las líneas de venta que existen en producción no apuntan a un artículo del
catálogo —el catálogo no existía cuando se escribieron— y no hay forma de
deducir cuál era. Un backfill tendría que elegir un artículo por cada línea, y
esa elección sería inventada.

Un inventario que arranca en cero y se explica es más útil que uno que arranca
con un número que nadie puede justificar. Así que esto planifica y no escribe:
mira la evidencia, dice qué encontró y por qué no es aplicable. El mismo ciclo
del importador del slice 1.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PlanDeBackfill:
    """El resultado de mirar la evidencia. Nunca escribió nada."""

    lineas_totales: int
    lineas_sin_articulo: int
    lineas_con_articulo: int
    movimientos_a_crear: int
    aplicable: bool
    motivo: str
    detalle: tuple[str, ...] = field(default_factory=tuple)


def planificar_backfill_historico(database_path: str | Path) -> PlanDeBackfill:
    """Calcula el plan de backfill del ledger. No escribe.

    Falla cerrado: si hay una sola línea sin artículo atribuible, el plan
    completo queda no aplicable. Cargar el stock de las líneas que sí se pueden
    atribuir y dejar afuera el resto daría un inventario parcial que se ve
    igual que uno completo, y ese es el peor de los dos mundos.
    """
    conexion = sqlite3.connect(str(database_path))
    conexion.row_factory = sqlite3.Row
    try:
        totales = conexion.execute(
            "SELECT COUNT(*) AS total,"
            " SUM(CASE WHEN article_id IS NULL THEN 1 ELSE 0 END) AS sin_articulo"
            " FROM sale_items"
        ).fetchone()
    finally:
        conexion.close()

    lineas = int(totales["total"] or 0)
    sin_articulo = int(totales["sin_articulo"] or 0)
    con_articulo = lineas - sin_articulo

    if lineas == 0:
        return PlanDeBackfill(
            lineas_totales=0, lineas_sin_articulo=0, lineas_con_articulo=0,
            movimientos_a_crear=0, aplicable=False,
            motivo="No hay ventas históricas: no hay nada que atribuir, y el "
                   "stock histórico queda como dato no atribuible.",
            detalle=("el ledger arranca vacío y se llena hacia adelante",))

    if sin_articulo:
        return PlanDeBackfill(
            lineas_totales=lineas, lineas_sin_articulo=sin_articulo,
            lineas_con_articulo=con_articulo, movimientos_a_crear=0,
            aplicable=False,
            motivo=f"{sin_articulo} de {lineas} líneas de venta no tienen artículo "
                   "del catálogo. Qué se vendió en ellas es un dato NO ATRIBUIBLE: "
                   "elegir un artículo sería inventarlo.",
            detalle=(
                "no se crea ningún movimiento de stock",
                "las líneas históricas siguen funcionando con article_id NULL",
                "el ledger arranca vacío y se llena hacia adelante",
            ))

    return PlanDeBackfill(
        lineas_totales=lineas, lineas_sin_articulo=0, lineas_con_articulo=con_articulo,
        movimientos_a_crear=0, aplicable=False,
        motivo="Todas las líneas tienen artículo, pero falta la otra mitad del "
               "dato: sin las entradas que las abastecieron, generar sólo las "
               "salidas dejaría todo el inventario en negativo. El origen de "
               "esas entradas es un dato PENDIENTE hasta que exista Compras.",
        detalle=("no se crea ningún movimiento de stock",))
