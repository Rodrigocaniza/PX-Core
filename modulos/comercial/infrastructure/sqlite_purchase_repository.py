"""Persistencia de las compras.

Vive en la misma base que Caja y el resto del núcleo comercial, y depende de su
cadena de migraciones: la 024 es la que crea estas tablas. No aplica migraciones
por su cuenta — hay una sola cadena y un solo dueño, `SQLiteCashDayRepository`.

Las reglas que tienen que valer para cualquier escritor —no repartir lo que no
mueve stock, no repartir más de lo comprado, no reescribir una compra
confirmada, no contradecir el vencimiento derivado— están en la base como
triggers, no acá.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence

from ..domain.compras import (
    Distribution,
    Purchase,
    PurchaseCondition,
    PurchaseLine,
    PurchaseStatus,
)
from ..domain.models import Destination


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(momento: datetime | date | None) -> str | None:
    return momento.isoformat() if momento is not None else None


def _momento(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto) if texto else None


def _fecha(texto: str | None) -> date | None:
    return date.fromisoformat(texto) if texto else None


class SQLitePurchaseRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._memory_connection: sqlite3.Connection | None = None
        if str(database_path) == ":memory:":
            self._memory_connection = self._new_connection()

    def _new_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._memory_connection or self._new_connection()
        try:
            yield connection
        finally:
            if self._memory_connection is None:
                connection.close()

    @contextmanager
    def escritura(self) -> Iterator[sqlite3.Connection]:
        """Transacción de escritura exclusiva, para el que la necesite entera."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            else:
                connection.execute("COMMIT")

    def close(self) -> None:
        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None

    # -- escritura ----------------------------------------------------------

    def guardar_borrador(self, compra: Purchase) -> Purchase:
        """Graba la factura completa —cabecera, líneas y reparto— o nada.

        Las tres cosas son un solo hecho de carga: una cabecera sin sus líneas
        no es una factura, es un formulario a medias.
        """
        with self.escritura() as connection:
            self._insertar_compra(connection, compra)
        return self.obtener(compra.id)

    def _insertar_compra(
        self, connection: sqlite3.Connection, compra: Purchase
    ) -> None:
        ahora = _iso(_ahora())
        connection.execute(
            """
            INSERT INTO purchases(
                id, supplier_id, document_date, document_number, stamped_number,
                condition, receipt_reference, credit_days, due_date,
                document_total, status, notes, created_by, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (compra.id, compra.supplier_id, _iso(compra.document_date),
             compra.document_number, compra.stamped_number, compra.condition.value,
             compra.receipt_reference, compra.credit_days, _iso(compra.due_date),
             compra.document_total, PurchaseStatus.BORRADOR.value, compra.notes,
             compra.created_by, ahora, ahora),
        )
        for linea in compra.lines:
            connection.execute(
                """
                INSERT INTO purchase_lines(
                    id, purchase_id, line_number, article_id, description,
                    quantity, unit_cost, notes, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (linea.id, compra.id, linea.line_number, linea.article_id,
                 linea.description, linea.quantity, linea.unit_cost, linea.notes,
                 ahora, ahora),
            )
            for distribucion in linea.distributions:
                connection.execute(
                    """
                    INSERT INTO purchase_line_distributions(
                        id, purchase_line_id, destination, quantity, created_at)
                    VALUES (?,?,?,?,?)
                    """,
                    (f"{linea.id}:{distribucion.destination.value}", linea.id,
                     distribucion.destination.value, distribucion.quantity, ahora),
                )

    @staticmethod
    def marcar_confirmada_en(
        connection: sqlite3.Connection,
        purchase_id: str,
        *,
        actor: str,
        event_id: str,
        momento: datetime,
    ) -> None:
        """La transición BORRADOR -> CONFIRMADA, dentro de la transacción ajena.

        Los triggers dejan pasar esta sola: miran el estado viejo, así que lo
        que queda prohibido es tocar lo que ya está confirmado.
        """
        connection.execute(
            "UPDATE purchases SET status = ?, confirmed_by = ?, confirmed_at = ?,"
            " event_id = ?, updated_at = ? WHERE id = ? AND status = ?",
            (PurchaseStatus.CONFIRMADA.value, actor, _iso(momento), event_id,
             _iso(momento), purchase_id, PurchaseStatus.BORRADOR.value),
        )

    # -- lectura ------------------------------------------------------------

    def obtener(self, purchase_id: str) -> Purchase | None:
        with self._connection() as connection:
            return self._leer(connection, purchase_id)

    def obtener_en(
        self, connection: sqlite3.Connection, purchase_id: str
    ) -> Purchase | None:
        return self._leer(connection, purchase_id)

    def por_documento(
        self, supplier_id: str, document_number: str
    ) -> Purchase | None:
        with self._connection() as connection:
            fila = connection.execute(
                "SELECT id FROM purchases WHERE supplier_id = ? AND document_number = ?",
                (supplier_id, document_number),
            ).fetchone()
            return self._leer(connection, fila["id"]) if fila else None

    def listar(self, *, supplier_id: str | None = None) -> Sequence[Purchase]:
        condicion = " WHERE supplier_id = ?" if supplier_id else ""
        parametros = (supplier_id,) if supplier_id else ()
        with self._connection() as connection:
            filas = connection.execute(
                f"SELECT id FROM purchases{condicion} ORDER BY document_date, rowid",
                parametros,
            ).fetchall()
            return [self._leer(connection, fila["id"]) for fila in filas]

    def _leer(
        self, connection: sqlite3.Connection, purchase_id: str
    ) -> Purchase | None:
        fila = connection.execute(
            "SELECT * FROM purchases WHERE id = ?", (purchase_id,)
        ).fetchone()
        if fila is None:
            return None

        lineas = []
        for fila_linea in connection.execute(
            "SELECT * FROM purchase_lines WHERE purchase_id = ? ORDER BY line_number",
            (purchase_id,),
        ).fetchall():
            repartos = connection.execute(
                "SELECT destination, quantity FROM purchase_line_distributions"
                " WHERE purchase_line_id = ? ORDER BY destination",
                (fila_linea["id"],),
            ).fetchall()
            lineas.append(PurchaseLine(
                id=fila_linea["id"],
                article_id=fila_linea["article_id"],
                line_number=fila_linea["line_number"],
                quantity=fila_linea["quantity"],
                unit_cost=fila_linea["unit_cost"],
                description=fila_linea["description"],
                notes=fila_linea["notes"],
                distributions=tuple(
                    Distribution(destination=Destination(r["destination"]),
                                 quantity=r["quantity"])
                    for r in repartos),
            ))

        return Purchase(
            id=fila["id"],
            supplier_id=fila["supplier_id"],
            document_date=_fecha(fila["document_date"]),
            document_number=fila["document_number"],
            stamped_number=fila["stamped_number"],
            condition=PurchaseCondition(fila["condition"]),
            receipt_reference=fila["receipt_reference"],
            credit_days=fila["credit_days"],
            document_total=fila["document_total"],
            status=PurchaseStatus(fila["status"]),
            notes=fila["notes"],
            created_by=fila["created_by"],
            created_at=_momento(fila["created_at"]),
            updated_at=_momento(fila["updated_at"]),
            confirmed_by=fila["confirmed_by"],
            confirmed_at=_momento(fila["confirmed_at"]),
            event_id=fila["event_id"],
            lines=tuple(lineas),
        )

    def origen_de_movimiento(self, movement_id: str) -> sqlite3.Row | None:
        """De una unidad en el depósito hasta la factura que la trajo.

        La vista `stock_origen_compra` de la 024 resuelve el camino entero, así
        que la pregunta se contesta con una consulta y no leyendo código.
        """
        with self._connection() as connection:
            return connection.execute(
                "SELECT * FROM stock_origen_compra WHERE movement_id = ?",
                (movement_id,),
            ).fetchone()
