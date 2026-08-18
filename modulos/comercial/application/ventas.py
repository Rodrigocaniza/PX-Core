"""El puente entre la venta de BC Caja y el inventario.

Este módulo **no** reescribe la venta. La línea sigue siendo la fila de
`sale_items` que la Óptica usa desde la migración 006, con su armazón y su
cristal; lo único que se agrega es qué artículo canónico hay detrás de cada
componente, y qué consecuencia tiene eso sobre el stock.

Dos cosas quedan explícitamente separadas:

* el **hecho económico** de la venta, que es la entrada de Caja y no cambia;
* el **efecto de inventario**, que es un movimiento del ledger.

Una salida `VENTA` mueve una unidad y no mueve un guaraní. No suma a los
totales, no toca el arqueo y no aparece dos veces en ningún lado.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .stock_ledger import StockInsuficiente
from ..domain.eventos import DomainEvent, EventProcessingState
from ..domain.models import Destination, StockMovement, StockMovementKind


class VentasError(ValueError):
    """Base de los rechazos de la integración venta → inventario."""


class SucursalNoResoluble(VentasError):
    """No se sabe de qué local sale la mercadería.

    Elegir uno sacaría stock del local equivocado, y eso no se nota hasta que
    alguien busca físicamente algo que el sistema dice tener.
    """


class VentaIntegradaNoEditable(VentasError):
    """La venta ya movió stock; esa parte es historia."""


class AnulacionSinResponsable(VentasError):
    """Nadie firmó la anulación.

    Una venta anulada devuelve mercadería al depósito. Sin un responsable, el
    stock aparece y no hay a quién preguntarle por qué.
    """


class AnulacionSinMotivo(VentasError):
    """La anulación no dice por qué."""


#: Tipo del hecho. Se nombra una sola vez, igual que `PURCHASE_CONFIRMED`.
EVENTO_VENTA_COMPLETADA = "SALE_COMPLETED"
#: El hecho compensatorio. Es un hecho nuevo, no la negación del anterior: el
#: `SALE_COMPLETED` original sigue estando y sigue siendo verdad.
EVENTO_VENTA_ANULADA = "SALE_VOIDED"
ORIGEN_CAJA = "CAJA"
DOCUMENTO_VENTA = "VENTA"
#: Motivo canónico de la devolución al stock, sembrado por la migración 027.
MOTIVO_VENTA_ANULADA = "VENTA_ANULADA"


@dataclass(frozen=True)
class FaltanteDeStock:
    """Lo que la venta pide y el depósito no tiene."""

    article_id: str
    article_name: str
    destination: Destination
    disponible: int
    pedido: int

    @property
    def faltan(self) -> int:
        return self.pedido - self.disponible


@dataclass(frozen=True)
class PlanDeBackfillDeVentas:
    """El resultado de mirar las ventas viejas. Nunca escribió nada."""

    lineas_totales: int
    lineas_sin_articulo: int
    lineas_con_articulo: int
    movimientos_a_crear: int
    aplicable: bool
    motivo: str


def planificar_backfill_de_ventas(database_path: str | Path) -> PlanDeBackfillDeVentas:
    """Qué hacer con las ventas anteriores a esta arquitectura. Nada.

    Una línea vieja dice «Armazon/org uvx» y un código de proveedor. Eso no
    identifica un artículo del catálogo: identifica lo que alguien escribió esa
    tarde. Elegir un artículo por parecido sería inventarlo, y encima cambiaría
    el stock de hoy con una inferencia sobre el pasado.
    """
    conexion = sqlite3.connect(str(database_path))
    conexion.row_factory = sqlite3.Row
    try:
        fila = conexion.execute(
            "SELECT COUNT(*) AS total,"
            " SUM(CASE WHEN article_id IS NULL THEN 1 ELSE 0 END) AS sin_articulo"
            " FROM sale_items"
        ).fetchone()
    finally:
        conexion.close()

    total = int(fila["total"] or 0)
    sin_articulo = int(fila["sin_articulo"] or 0)
    return PlanDeBackfillDeVentas(
        lineas_totales=total,
        lineas_sin_articulo=sin_articulo,
        lineas_con_articulo=total - sin_articulo,
        movimientos_a_crear=0,
        aplicable=False,
        motivo=(
            f"{sin_articulo} de {total} líneas de venta no apuntan a un artículo del "
            "catálogo. Qué se vendió en ellas es un dato NO ATRIBUIBLE: el texto y el "
            "código de proveedor no identifican un artículo canónico. No se crea "
            "ningún movimiento y el stock de hoy no se toca con inferencias sobre "
            "el pasado."),
    )


class VentasLedgerIntegrator:
    """Deriva el efecto de inventario de una venta, dentro de su transacción.

    Nunca abre ni cierra una transacción propia. La recibe: si la venta no
    queda guardada, el stock tampoco, y al revés. Una segunda transacción
    independiente es exactamente la forma de terminar con la venta escrita y el
    stock no.
    """

    def __init__(self, catalog, ledger) -> None:
        self._catalogo = catalog
        self._ledger = ledger

    # -- consulta previa, para que la UI no sorprenda ----------------------

    def faltantes_de_stock(self, entry, *, unidad: str) -> tuple[FaltanteDeStock, ...]:
        """Qué le faltaría al depósito si esta venta se guardara ahora.

        Rechazar al guardar es correcto pero tardío: para cuando la operadora
        se entera, ya cargó toda la venta. Esto deja preguntarlo antes.
        """
        destino = self._destino_opcional(unidad)
        if destino is None:
            return ()
        pedido: dict[str, int] = {}
        for _, article_id in self._lineas_con_stock(entry):
            pedido[article_id] = pedido.get(article_id, 0) + 1

        faltantes = []
        for article_id, cantidad in pedido.items():
            disponible = self._ledger.stock(article_id, destino)
            if disponible < cantidad:
                articulo = self._catalogo.get_article(article_id)
                faltantes.append(FaltanteDeStock(
                    article_id=article_id,
                    article_name=articulo.name if articulo else "",
                    destination=destino,
                    disponible=disponible,
                    pedido=cantidad))
        return tuple(faltantes)

    # -- guardia de edición -------------------------------------------------

    def verificar_editable(
        self, connection: sqlite3.Connection, cash_day, integradas: set[str]
    ) -> None:
        """Lo que ya movió stock no se reescribe; lo demás sí.

        Se comprueba antes de escribir nada, para que el rechazo llegue como un
        mensaje entendible y no como una violación de constraint a mitad del
        guardado. Los triggers siguen estando debajo para cualquier otro
        escritor.
        """
        for entry in cash_day.entries:
            if entry.id not in integradas:
                continue
            # Anular ya no está prohibido: tiene su propio circuito, que devuelve
            # la mercadería antes de que la entrada cambie de estado. Lo que
            # sigue prohibido —también para una venta anulada— es reescribir las
            # líneas, porque el movimiento que sacó la unidad apunta a ellas.
            if self._huella(entry) != self._huella_guardada(connection, entry.id):
                raise VentaIntegradaNoEditable(
                    f"la venta «{entry.description}» ya movió stock: sus líneas no se "
                    "cambian. La corrección es un movimiento compensatorio, no una "
                    "edición")

    @staticmethod
    def _huella(entry) -> tuple:
        """Lo de la línea que decide el inventario. El resto puede cambiar."""
        return tuple(
            (position, item.id, item.article_id, item.lens_article_id)
            for position, item in enumerate(entry.items))

    @staticmethod
    def _huella_guardada(connection: sqlite3.Connection, entry_id: str) -> tuple:
        return tuple(
            (fila[0], fila[1], fila[2], fila[3])
            for fila in connection.execute(
                "SELECT position, id, article_id, lens_article_id FROM sale_items"
                " WHERE cash_entry_id = ? ORDER BY position", (entry_id,)))

    # -- anulación compensatoria -------------------------------------------

    def compensar_anulaciones_en(
        self,
        connection: sqlite3.Connection,
        cash_day,
        integradas: set[str],
        *,
        actor: str = "",
    ) -> None:
        """Devuelve al depósito la mercadería de las ventas recién anuladas.

        Corre **antes** de que la entrada cambie de estado, y no por prolijidad:
        el trigger de la 027 exige que la compensación ya esté registrada para
        dejar pasar el `VOIDED`. Si la devolución falla, la anulación no ocurre;
        si la anulación falla, la devolución tampoco. Son la misma transacción,
        la del guardado de Caja, y por eso no se abre ninguna acá.

        Nada de esto reescribe el pasado. La venta, su `SALE_COMPLETED` y sus
        movimientos `VENTA` quedan exactamente como estaban.
        """
        for entry in cash_day.entries:
            if entry.id not in integradas:
                continue
            if str(getattr(entry.status, "value", entry.status)) != "VOIDED":
                continue
            if self._anulacion_ya_registrada(connection, entry.id):
                # Guardar el mismo día dos veces no devuelve el stock dos veces.
                continue
            self._compensar_entrada(connection, cash_day, entry, actor=actor)

    def _compensar_entrada(
        self, connection: sqlite3.Connection, cash_day, entry, *, actor: str
    ) -> None:
        motivo = str(getattr(entry, "void_reason", "") or "").strip()
        if not motivo:
            raise AnulacionSinMotivo(
                f"la anulación de «{entry.description}» no declara motivo, y esa "
                "anulación devuelve mercadería al depósito")
        responsable = self._responsable(actor, cash_day, entry)

        integracion = connection.execute(
            "SELECT event_id, destination FROM sale_stock_integrations"
            " WHERE cash_entry_id = ?", (entry.id,)).fetchone()
        if integracion is None:
            # No debería ocurrir: `integradas` sale de esa misma tabla.
            raise VentasError(
                f"la venta «{entry.description}» figura integrada pero no tiene "
                "registro de integración")
        sale_event_id, destino_guardado = integracion[0], integracion[1]

        # Lo que se devuelve es lo que esta venta sacó, leído del ledger. No se
        # vuelve a derivar del catálogo: si la naturaleza de un artículo cambió
        # desde la venta, derivarla de nuevo devolvería una cantidad distinta de
        # la que salió, o inventaría stock de un servicio.
        movimientos = connection.execute(
            "SELECT id, article_id, destination, quantity, document_line_id, note"
            " FROM stock_movements WHERE document_kind = ? AND document_id = ?"
            " AND kind = ? ORDER BY rowid",
            (DOCUMENTO_VENTA, entry.id, StockMovementKind.VENTA.value)).fetchall()

        momento = datetime.now(timezone.utc).replace(microsecond=0)
        evento = DomainEvent(
            event_type=EVENTO_VENTA_ANULADA,
            source=ORIGEN_CAJA,
            entity_type="SALE",
            entity_id=entry.id,
            destination=destino_guardado,
            actor=responsable,
            occurred_at=momento,
            idempotency_key=f"{DOCUMENTO_VENTA}:{entry.id}:ANULACION",
            payload=self._payload_de_anulacion(
                cash_day, entry, motivo, responsable, sale_event_id, movimientos),
            processing_state=EventProcessingState.PENDIENTE,
        )
        # El hecho primero, igual que en la venta: una anulación es durable
        # aunque el ledger no tenga nada que devolver.
        void_event_id = self._ledger.asegurar_evento_en(connection, evento)

        for fila in movimientos:
            self._ledger.registrar_en(
                connection,
                StockMovement(
                    article_id=fila[1],
                    destination=Destination(fila[2]),
                    kind=StockMovementKind.AJUSTE_POSITIVO,
                    quantity=abs(int(fila[3])),
                    actor=responsable,
                    occurred_at=momento,
                    # La misma clave que usa `StockLedgerService.compensar`: un
                    # movimiento se compensa una vez, la haya disparado la
                    # anulación o una corrección manual del ledger.
                    idempotency_key=f"compensa:{fila[0]}",
                    reason_code=MOTIVO_VENTA_ANULADA,
                    note=motivo,
                    document_kind=DOCUMENTO_VENTA,
                    document_id=entry.id,
                    document_line_id=fila[4],
                    compensates_id=fila[0],
                ),
                evento=evento)

        self._ledger.marcar_evento_procesado_en(connection, void_event_id, momento)
        connection.execute(
            "INSERT INTO sale_void_compensations(cash_entry_id, sale_event_id,"
            " void_event_id, destination, reason_code, note, movement_count,"
            " voided_at, voided_by) VALUES (?,?,?,?,?,?,?,?,?)",
            (entry.id, sale_event_id, void_event_id, destino_guardado,
             MOTIVO_VENTA_ANULADA, motivo,
             self._compensaciones_registradas(connection, entry.id),
             momento.isoformat(), responsable))

    @staticmethod
    def _anulacion_ya_registrada(
        connection: sqlite3.Connection, entry_id: str
    ) -> bool:
        """Vive en la base y no en memoria: reabrir la ventana o recuperarse de
        un corte tiene que encontrar que esta venta ya devolvió su mercadería."""
        return connection.execute(
            "SELECT 1 FROM sale_void_compensations WHERE cash_entry_id = ?",
            (entry_id,)).fetchone() is not None

    @staticmethod
    def _compensaciones_registradas(
        connection: sqlite3.Connection, entry_id: str
    ) -> int:
        """Cuántas devoluciones tiene esta venta, contadas en el ledger.

        Se cuenta en vez de acumularse en un contador propio porque el trigger
        de la 027 verifica exactamente esta cuenta: declarar otra cosa sería
        declarar un efecto que no ocurrió.
        """
        return int(connection.execute(
            "SELECT COUNT(*) FROM stock_movements WHERE document_kind = ?"
            " AND document_id = ? AND compensates_id IS NOT NULL",
            (DOCUMENTO_VENTA, entry_id)).fetchone()[0])

    @staticmethod
    def _responsable(actor: str, cash_day, entry) -> str:
        """Quién firma la devolución de la mercadería.

        Se prefiere quien ejecutó la anulación; si el llamador no lo pasó, se
        cae a quien abrió la caja y después a la vendedora de la línea. Si no
        hay ninguno, la anulación se rechaza: stock que vuelve sin responsable
        es stock aparecido.
        """
        for candidato in (actor, getattr(cash_day, "opened_by", ""),
                          getattr(entry, "saleswoman", "")):
            limpio = str(candidato or "").strip()
            if limpio:
                return limpio
        raise AnulacionSinResponsable(
            f"la anulación de «{entry.description}» devuelve mercadería al depósito "
            "y no tiene responsable declarado")

    @staticmethod
    def _payload_de_anulacion(
        cash_day, entry, motivo: str, responsable: str, sale_event_id: str,
        movimientos,
    ) -> dict:
        """Lo mínimo para reconstruir la anulación sin volver a consultar nada."""
        return {
            "cash_day_id": cash_day.id,
            "business_date": cash_day.business_date.isoformat(),
            "unit": cash_day.unit,
            "entry_description": entry.description,
            "sale_event_id": sale_event_id,
            "void_reason": motivo,
            "voided_by": responsable,
            "compensated_movements": [
                {
                    "movement_id": fila[0],
                    "article_id": fila[1],
                    "destination": fila[2],
                    "quantity": abs(int(fila[3])),
                    "sale_item_id": fila[4],
                }
                for fila in movimientos
            ],
        }

    # -- integración --------------------------------------------------------

    def integrar_en(
        self, connection: sqlite3.Connection, cash_day, integradas: set[str]
    ) -> None:
        """Emite `SALE_COMPLETED` y sus efectos para las ventas nuevas del día."""
        for entry in cash_day.entries:
            if entry.id in integradas:
                continue
            if str(getattr(entry.status, "value", entry.status)) == "VOIDED":
                # Anular es lo contrario de vender. No descuenta nada.
                continue
            if not any(item.articulos_vinculados for item in entry.items):
                # Sin artículo canónico no hay nada que derivar. Es el caso de
                # todo lo que ya existe, y por eso instalar esto no cambia el
                # comportamiento de una caja que todavía no vincula artículos.
                continue
            self._integrar_entrada(connection, cash_day, entry)

    def _integrar_entrada(
        self, connection: sqlite3.Connection, cash_day, entry
    ) -> None:
        lineas_con_stock = self._lineas_con_stock(entry)
        destino = (self._destino(cash_day.unit) if lineas_con_stock
                   else self._destino_opcional(cash_day.unit))

        # El trigger del ledger ya impide el stock negativo, pero llegar hasta
        # ahi devuelve una violacion de constraint a mitad del guardado. Esto
        # comprueba primero, sobre la MISMA conexion —y por lo tanto viendo lo
        # que esta transaccion ya escribio—, para que el rechazo sea legible.
        self._verificar_stock(connection, entry, lineas_con_stock, destino)

        momento = datetime.now(timezone.utc).replace(microsecond=0)
        actor = (entry.saleswoman or cash_day.opened_by or "caja").strip() or "caja"

        evento = DomainEvent(
            event_type=EVENTO_VENTA_COMPLETADA,
            source=ORIGEN_CAJA,
            entity_type="SALE",
            entity_id=entry.id,
            destination=destino,
            actor=actor,
            occurred_at=momento,
            idempotency_key=f"{DOCUMENTO_VENTA}:{entry.id}",
            payload=self._payload(cash_day, entry),
            processing_state=EventProcessingState.PENDIENTE,
        )
        # El hecho primero: una venta de puros servicios se completa igual y su
        # SALE_COMPLETED tiene que quedar registrado aunque no mueva una unidad.
        event_id = self._ledger.asegurar_evento_en(connection, evento)

        movimientos = 0
        for item, article_id in lineas_con_stock:
            self._ledger.registrar_en(
                connection,
                StockMovement(
                    article_id=article_id,
                    destination=destino,
                    kind=StockMovementKind.VENTA,
                    quantity=1,
                    actor=actor,
                    occurred_at=momento,
                    idempotency_key=f"{DOCUMENTO_VENTA}:{entry.id}:{item.id}",
                    document_kind=DOCUMENTO_VENTA,
                    document_id=entry.id,
                    document_line_id=item.id,
                    note=item.description,
                ),
                evento=evento)
            movimientos += 1

        self._ledger.marcar_evento_procesado_en(connection, event_id, momento)
        connection.execute(
            "INSERT INTO sale_stock_integrations(cash_entry_id, event_id, destination,"
            " movement_count, integrated_at, integrated_by) VALUES (?,?,?,?,?,?)",
            (entry.id, event_id, destino.value if destino else None, movimientos,
             momento.isoformat(), actor))

    # -- reglas -------------------------------------------------------------

    def _lineas_con_stock(self, entry) -> list[tuple[object, str]]:
        """Las líneas que van a mover inventario, y con qué artículo.

        La decisión sale de la naturaleza del artículo en el catálogo. Ni la
        descripción, ni el código, ni el laboratorio, ni el tipo escrito a mano
        entran en esto: si lo hicieran, un texto mal tipeado movería stock.

        El componente del cristal no aparece nunca: es trabajo bajo pedido por
        naturaleza, y esa naturaleza ya lo excluye sin ningún caso especial.
        """
        lineas = []
        for item in entry.items:
            for article_id in item.articulos_vinculados:
                articulo = self._catalogo.get_article(article_id)
                if articulo is None:
                    raise VentasError(
                        f"la línea «{item.description}» apunta a un artículo que no "
                        f"existe en el catálogo: {article_id}")
                if articulo.tracks_stock:
                    lineas.append((item, article_id))
        return lineas

    def _verificar_stock(
        self, connection: sqlite3.Connection, entry, lineas_con_stock, destino
    ) -> None:
        pedido: dict[str, int] = {}
        for _, article_id in lineas_con_stock:
            pedido[article_id] = pedido.get(article_id, 0) + 1
        for article_id, cantidad in pedido.items():
            disponible = self._stock_en(connection, article_id, destino)
            if disponible < cantidad:
                articulo = self._catalogo.get_article(article_id)
                nombre = articulo.name if articulo else article_id
                raise StockInsuficiente(
                    f"«{nombre}» tiene {disponible} en {destino.value} y la venta "
                    f"«{entry.description}» pide {cantidad}. Una venta no puede dejar "
                    "el stock en negativo: la excepción es administrativa y auditada, "
                    "no una forma de seguir vendiendo")

    @staticmethod
    def _stock_en(
        connection: sqlite3.Connection, article_id: str, destino: Destination
    ) -> int:
        """El stock visto DESDE esta transacción.

        Preguntarlo por otra conexión devolvería lo que había antes de empezar,
        que en una venta de dos líneas del mismo artículo daría el visto bueno
        a las dos.
        """
        fila = connection.execute(
            "SELECT quantity FROM stock_actual WHERE article_id = ? AND destination = ?",
            (article_id, destino.value)).fetchone()
        return int(fila[0]) if fila and fila[0] is not None else 0

    def _mueve_stock(self, item) -> bool:
        """Si esta línea va a descontar algo. Derivado del catálogo, nunca del
        texto que la operadora escribió."""
        for article_id in item.articulos_vinculados:
            articulo = self._catalogo.get_article(article_id)
            if articulo is not None and articulo.tracks_stock:
                return True
        return False

    def _destino(self, unidad: str) -> Destination:
        destino = self._destino_opcional(unidad)
        if destino is None:
            raise SucursalNoResoluble(
                f"la caja «{unidad}» no está vinculada a ninguna sucursal, así que no "
                "se sabe de qué local sale la mercadería. Vincularla es una acción "
                "administrativa; adivinarla sacaría stock del local equivocado")
        return destino

    def _destino_opcional(self, unidad: str) -> Destination | None:
        """La sucursal de la caja, según el vínculo administrativo que ya existe.

        Se reusa `cash_register_branches`, que la 018 y la 020 dejaron como el
        vínculo canónico caja → sucursal. La operadora no elige de dónde sale el
        stock: sale de donde está parada.
        """
        branch = self._catalogo.branch_of_register(unidad)
        if not branch:
            return None
        try:
            return Destination(branch)
        except ValueError:
            return None

    def _payload(self, cash_day, entry) -> dict:
        """Lo mínimo para reconstruir el hecho y para que otros lo deriven.

        FactuFácil, Trabajos, revisión, Gestión Central y estadísticas van a
        colgar de este mismo hecho. Que su payload ya los contemple no es
        implementarlos: es no tener que volver a migrar cuando se implementen.
        """
        return {
            "cash_day_id": cash_day.id,
            "business_date": cash_day.business_date.isoformat(),
            "unit": cash_day.unit,
            "entry_description": entry.description,
            "saleswoman": entry.saleswoman,
            "customer_document": entry.customer_document,
            "total": entry.total,
            "lines": [
                {
                    "sale_item_id": item.id,
                    "position": position,
                    "description": item.description,
                    "article_id": item.article_id,
                    "lens_article_id": item.lens_article_id,
                    "frame_price": item.frame_price,
                    "lens_price": item.lens_price,
                    "laboratory": item.laboratory,
                    "tracks_stock": self._mueve_stock(item),
                }
                for position, item in enumerate(entry.items)
            ],
        }


class VentasService:
    """Lo que la UI necesita para vincular artículos y avisar a tiempo."""

    def __init__(self, catalog, ledger, integrator: VentasLedgerIntegrator) -> None:
        self._catalogo = catalog
        self._ledger = ledger
        self._integrador = integrator

    def articulos_vendibles(self, texto: str = "") -> Sequence:
        """Artículos activos para elegir en una línea de venta."""
        buscado = (texto or "").strip().lower()
        articulos = self._catalogo.list_articles(only_active=True)
        if not buscado:
            return articulos
        return [a for a in articulos
                if buscado in a.name.lower() or buscado in a.sku.lower()]

    def stock_disponible(self, article_id: str, unidad: str) -> int | None:
        """Lo que hay en el local de esta caja, o `None` si no mueve stock.

        `None` no es cero: un servicio no tiene stock, no tiene stock cero.
        Mostrarlo como cero haría pensar que falta algo.
        """
        articulo = self._catalogo.get_article(article_id)
        if articulo is None or not articulo.tracks_stock:
            return None
        destino = self._integrador._destino_opcional(unidad)
        if destino is None:
            return None
        return self._ledger.stock(article_id, destino)

    def faltantes_de_stock(self, entry, *, unidad: str) -> tuple[FaltanteDeStock, ...]:
        return self._integrador.faltantes_de_stock(entry, unidad=unidad)
