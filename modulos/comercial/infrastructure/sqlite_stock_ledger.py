"""Persistencia del ledger de inventario y del Event Spine.

Vive en la misma base que Caja y depende de su cadena de migraciones: la 023 es
la que crea estas tablas. Igual que el repositorio de catálogos, no aplica
migraciones por su cuenta — hay una sola cadena y un solo dueño,
`SQLiteCashDayRepository`.

Las reglas duras (append-only, stock negativo, naturaleza del artículo, motivo
válido) están en la base como triggers, no acá. Este módulo escribe y lee; si
intentara además ser el guardián, cualquier otro escritor las esquivaría.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence

from ..domain.eventos import DomainEvent, EventEffect, EventProcessingState
from ..domain.models import Destination, StockMovement, StockMovementKind


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(momento: datetime | None) -> str | None:
    return momento.isoformat() if momento is not None else None


def _momento(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto) if texto else None


class SQLiteStockLedgerRepository:
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
    def _escritura(self) -> Iterator[sqlite3.Connection]:
        """Transacción de escritura exclusiva.

        `BEGIN IMMEDIATE` toma el lock de escritura desde el principio: sin eso,
        dos cajas descontando la última unidad al mismo tiempo podrían leer
        stock 1 las dos. Con esto, la segunda espera, y cuando entra el trigger
        ya ve el movimiento de la primera.
        """
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

    def registrar(
        self,
        movimiento: StockMovement,
        *,
        evento: DomainEvent | None = None,
        efecto: str = "STOCK_MOVEMENT",
    ) -> StockMovement:
        """Graba el hecho y su efecto en su propia transacción.

        Si la clave de idempotencia ya está, devuelve lo que ya había: el mismo
        hecho no descuenta dos veces.
        """
        with self._escritura() as connection:
            return self.registrar_en(connection, movimiento, evento=evento,
                                     efecto=efecto)

    def transaccion(self):
        """Transacción de escritura para quien necesite abarcar más que el ledger.

        Confirmar una compra tiene que grabar la factura, el hecho y todos los
        movimientos, o ninguna de las tres cosas. Media factura confirmada sería
        peor que ninguna, porque el stock parcial se ve igual que el correcto.
        """
        return self._escritura()

    def registrar_en(
        self,
        connection: sqlite3.Connection,
        movimiento: StockMovement,
        *,
        evento: DomainEvent | None = None,
        efecto: str = "STOCK_MOVEMENT",
    ) -> StockMovement:
        """Lo mismo, dentro de una transacción que abrió otro.

        No abre ni cierra nada: el dueño de la transacción decide si al final
        todo esto queda o no queda.
        """
        existente = self._buscar_por_clave(connection, movimiento.idempotency_key)
        if existente is not None:
            return existente

        registrado = _ahora()
        event_id = None
        if evento is not None:
            event_id = self.asegurar_evento_en(connection, evento)

        connection.execute(
            """
            INSERT INTO stock_movements(
                id, event_id, article_id, destination, kind, quantity,
                occurred_at, recorded_at, actor, reason_code, note,
                supplier_id, document_kind, document_id, document_line_id,
                document_number, compensates_id, negative_override,
                idempotency_key)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                movimiento.id,
                event_id,
                movimiento.article_id,
                movimiento.destination.value,
                movimiento.kind.value,
                movimiento.signed_quantity,
                _iso(movimiento.occurred_at),
                _iso(registrado),
                movimiento.actor,
                movimiento.reason_code,
                movimiento.note,
                movimiento.supplier_id,
                movimiento.document_kind,
                movimiento.document_id,
                movimiento.document_line_id,
                movimiento.document_number,
                movimiento.compensates_id,
                1 if movimiento.negative_override else 0,
                movimiento.idempotency_key,
            ),
        )

        if event_id is not None:
            connection.execute(
                """
                INSERT OR IGNORE INTO event_effects(
                    event_id, effect_kind, effect_table, effect_id, created_at)
                VALUES (?,?,?,?,?)
                """,
                (event_id, efecto, "stock_movements", movimiento.id,
                 _iso(registrado)),
            )
            self.marcar_evento_procesado_en(connection, event_id, registrado)

        return self._buscar_por_id(connection, movimiento.id)

    @staticmethod
    def marcar_evento_procesado_en(
        connection: sqlite3.Connection, event_id: str, momento: datetime
    ) -> None:
        """Avanzar el estado es lo único que un hecho registrado admite, y el
        trigger `domain_events_inmutable` se encarga de que siga siendo así."""
        connection.execute(
            "UPDATE domain_events SET processing_state = ?, processed_at = ?"
            " WHERE event_id = ?",
            (EventProcessingState.PROCESADO.value, _iso(momento), event_id),
        )

    def asegurar_evento_en(
        self, connection: sqlite3.Connection, evento: DomainEvent
    ) -> str:
        """Devuelve el `event_id` del hecho, registrándolo si es la primera vez.

        La clave de idempotencia manda sobre el id: si el mismo hecho llega con
        un id nuevo, sigue siendo el mismo hecho.

        Es público porque un hecho puede ser durable sin producir stock: una
        factura de puros servicios se confirma igual, y su `PURCHASE_CONFIRMED`
        tiene que quedar registrado aunque no haya un solo movimiento que lo
        arrastre a la base.
        """
        fila = connection.execute(
            "SELECT event_id FROM domain_events WHERE idempotency_key = ?",
            (evento.idempotency_key,),
        ).fetchone()
        if fila is not None:
            return fila["event_id"]

        registrado = _ahora()
        connection.execute(
            """
            INSERT INTO domain_events(
                event_id, event_type, source, entity_type, entity_id, destination,
                actor, occurred_at, recorded_at, payload, processing_state,
                processed_at, failure_reason, idempotency_key)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                evento.event_id,
                evento.event_type,
                evento.source,
                evento.entity_type,
                evento.entity_id,
                evento.destination.value if evento.destination is not None else None,
                evento.actor,
                _iso(evento.occurred_at),
                _iso(registrado),
                evento.payload_json,
                evento.processing_state.value,
                _iso(evento.processed_at),
                evento.failure_reason,
                evento.idempotency_key,
            ),
        )
        return evento.event_id

    # -- lectura ------------------------------------------------------------

    def obtener(self, movimiento_id: str) -> StockMovement | None:
        with self._connection() as connection:
            return self._buscar_por_id(connection, movimiento_id)

    def por_clave(self, idempotency_key: str) -> StockMovement | None:
        with self._connection() as connection:
            return self._buscar_por_clave(connection, idempotency_key)

    def movimientos(
        self,
        *,
        article_id: str | None = None,
        destination: Destination | str | None = None,
    ) -> list[StockMovement]:
        condiciones: list[str] = []
        parametros: list[object] = []
        if article_id:
            condiciones.append("article_id = ?")
            parametros.append(article_id)
        if destination is not None:
            condiciones.append("destination = ?")
            parametros.append(Destination(destination).value)
        donde = f" WHERE {' AND '.join(condiciones)}" if condiciones else ""
        with self._connection() as connection:
            filas = connection.execute(
                f"SELECT * FROM stock_movements{donde} ORDER BY recorded_at, rowid",
                parametros,
            ).fetchall()
        return [_a_movimiento(fila) for fila in filas]

    def movimientos_de_documento(
        self, document_kind: str, document_id: str
    ) -> list[StockMovement]:
        with self._connection() as connection:
            filas = connection.execute(
                "SELECT * FROM stock_movements WHERE document_kind = ?"
                " AND document_id = ? ORDER BY recorded_at, rowid",
                (document_kind, document_id),
            ).fetchall()
        return [_a_movimiento(fila) for fila in filas]

    def compensacion_de(self, movimiento_id: str) -> StockMovement | None:
        with self._connection() as connection:
            fila = connection.execute(
                "SELECT * FROM stock_movements WHERE compensates_id = ?",
                (movimiento_id,),
            ).fetchone()
        return _a_movimiento(fila) if fila else None

    def stock(self, article_id: str, destination: Destination | str) -> int:
        with self._connection() as connection:
            fila = connection.execute(
                "SELECT quantity FROM stock_actual WHERE article_id = ?"
                " AND destination = ?",
                (article_id, Destination(destination).value),
            ).fetchone()
        return int(fila["quantity"]) if fila and fila["quantity"] is not None else 0

    def stock_por_destino(self, article_id: str) -> dict[Destination, int]:
        with self._connection() as connection:
            filas = connection.execute(
                "SELECT destination, quantity FROM stock_actual WHERE article_id = ?",
                (article_id,),
            ).fetchall()
        return {Destination(f["destination"]): int(f["quantity"]) for f in filas}

    def evento(self, event_id: str) -> DomainEvent | None:
        with self._connection() as connection:
            fila = connection.execute(
                "SELECT * FROM domain_events WHERE event_id = ?", (event_id,)
            ).fetchone()
        return _a_evento(fila) if fila else None

    def evento_por_clave(self, idempotency_key: str) -> DomainEvent | None:
        with self._connection() as connection:
            fila = connection.execute(
                "SELECT * FROM domain_events WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        return _a_evento(fila) if fila else None

    def eventos_pendientes(self) -> Sequence[DomainEvent]:
        with self._connection() as connection:
            filas = connection.execute(
                "SELECT * FROM domain_events WHERE processing_state = ?"
                " ORDER BY occurred_at",
                (EventProcessingState.PENDIENTE.value,),
            ).fetchall()
        return [_a_evento(fila) for fila in filas]

    def efectos_de(self, event_id: str) -> list[EventEffect]:
        with self._connection() as connection:
            filas = connection.execute(
                "SELECT * FROM event_effects WHERE event_id = ?"
                " ORDER BY created_at, effect_id",
                (event_id,),
            ).fetchall()
        return [
            EventEffect(
                event_id=fila["event_id"],
                effect_kind=fila["effect_kind"],
                effect_table=fila["effect_table"],
                effect_id=fila["effect_id"],
                created_at=_momento(fila["created_at"]),
            )
            for fila in filas
        ]

    # -- internos -----------------------------------------------------------

    @staticmethod
    def _buscar_por_id(
        connection: sqlite3.Connection, movimiento_id: str
    ) -> StockMovement | None:
        fila = connection.execute(
            "SELECT * FROM stock_movements WHERE id = ?", (movimiento_id,)
        ).fetchone()
        return _a_movimiento(fila) if fila else None

    @staticmethod
    def _buscar_por_clave(
        connection: sqlite3.Connection, idempotency_key: str
    ) -> StockMovement | None:
        fila = connection.execute(
            "SELECT * FROM stock_movements WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        return _a_movimiento(fila) if fila else None


def _a_movimiento(fila: sqlite3.Row) -> StockMovement:
    """La cantidad se guarda con signo; el dominio la declara positiva."""
    return StockMovement(
        id=fila["id"],
        event_id=fila["event_id"],
        article_id=fila["article_id"],
        destination=Destination(fila["destination"]),
        kind=StockMovementKind(fila["kind"]),
        quantity=abs(int(fila["quantity"])),
        occurred_at=_momento(fila["occurred_at"]),
        recorded_at=_momento(fila["recorded_at"]),
        actor=fila["actor"],
        reason_code=fila["reason_code"],
        note=fila["note"],
        supplier_id=fila["supplier_id"],
        document_kind=fila["document_kind"],
        document_id=fila["document_id"],
        document_line_id=fila["document_line_id"],
        document_number=fila["document_number"],
        compensates_id=fila["compensates_id"],
        negative_override=bool(fila["negative_override"]),
        idempotency_key=fila["idempotency_key"],
    )


def _a_evento(fila: sqlite3.Row) -> DomainEvent:
    return DomainEvent(
        event_id=fila["event_id"],
        event_type=fila["event_type"],
        source=fila["source"],
        entity_type=fila["entity_type"],
        entity_id=fila["entity_id"],
        destination=fila["destination"],
        actor=fila["actor"],
        occurred_at=_momento(fila["occurred_at"]),
        recorded_at=_momento(fila["recorded_at"]),
        payload=json.loads(fila["payload"]),
        processing_state=EventProcessingState(fila["processing_state"]),
        processed_at=_momento(fila["processed_at"]),
        failure_reason=fila["failure_reason"],
        idempotency_key=fila["idempotency_key"],
    )
