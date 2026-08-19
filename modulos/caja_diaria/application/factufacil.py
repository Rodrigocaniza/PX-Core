"""Que ventas faltan cargar en FactuFácil, y cuáles ya se cargaron.

FactuFácil es un sistema externo. No hay integración oficial, así que la carga
la sigue haciendo una persona: entra, copia los datos, y los pega allá. Lo que
faltaba no era automatizar eso —no se puede— sino que la chica que atiende
supiera **cuáles** le faltan, sin tener que preguntarle a nadie ni entrar a la
consola administrativa.

La lista se deduce de las ventas que ya están en Caja. No se vuelve a cargar el
cliente, ni el sobre, ni el importe: si Caja los conoce, salen de ahí. Lo único
que se guarda es la marca de que alguien la cargó.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from ..domain.errors import InvalidCashDayError

PARA_CARGAR = "PARA_CARGAR"
CARGADA = "CARGADA"
ESTADOS = (PARA_CARGAR, CARGADA)

#: Rótulos para la pantalla. La operadora no lee guiones bajos.
ETIQUETAS = {PARA_CARGAR: "PARA CARGAR", CARGADA: "CARGADA"}

#: El orden en que FactuFácil pide los datos, heredado del contrato que dejó
#: `BC-GESTION-CENTRAL-FACTUFACIL-BANDEJA-001`. Se respeta para que copiar desde
#: Caja y copiar desde Gestión Central produzcan lo mismo, y para que el día que
#: exista una integración real las dos hablen el mismo idioma.
ORDEN_DE_COPIA = (
    ("cliente", "Cliente"),
    ("documento", "CI/RUC"),
    ("telefono", "Teléfono"),
    ("fecha", "Fecha"),
    ("sucursal", "Sucursal"),
    ("sobre", "Sobre"),
    ("vendedora", "Vendedora"),
    ("observaciones", "Observaciones"),
    ("total", "Total"),
)


def _ahora() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class FilaFactuFacil:
    """Una venta, vista desde FactuFácil.

    Todo sale de la venta salvo `estado`, `cargada_por` y `cargada_el`, que son
    lo único que esta misión agrega al mundo.
    """

    cash_entry_id: str
    fecha: str
    sucursal: str
    caja: str
    sobre: str
    cliente: str
    documento: str
    telefono: str
    vendedora: str
    total: int
    observaciones: str
    estado: str
    cargada_por: str
    cargada_el: str
    revision_venta: int
    revision_marcada: int

    @property
    def etiqueta_estado(self) -> str:
        return ETIQUETAS[self.estado]

    @property
    def editada_despues_de_cargar(self) -> bool:
        """La venta cambió después de que alguien la cargó en FactuFácil.

        No es un estado nuevo ni bloquea nada: es un aviso. Lo que se cargó allá
        ya no coincide con lo que dice Caja, y alguien tiene que mirarlo. Sin
        esto, la corrección se descubriría al cerrar el mes.
        """
        return self.estado == CARGADA and self.revision_venta != self.revision_marcada

    def texto_para_copiar(self) -> str:
        """Los datos listos para pegar, un campo por línea.

        FactuFácil se carga campo por campo en un formulario web: no hay import,
        no hay pegar-todo. Una línea por campo es lo que se puede ir copiando de
        a pedazos sin perder de vista dónde iba cada cosa.
        """
        valores = {
            "cliente": self.cliente, "documento": self.documento,
            "telefono": self.telefono, "fecha": self.fecha,
            "sucursal": self.sucursal, "sobre": self.sobre,
            "vendedora": self.vendedora, "observaciones": self.observaciones,
            "total": f"{self.total:,}".replace(",", "."),
        }
        return "\n".join(f"{rotulo}: {valores[clave]}" for clave, rotulo in ORDEN_DE_COPIA)


#: Una venta está para cargar si es una venta de verdad y nadie la marcó.
#:
#: - `status='ACTIVE'`: una anulada no se factura. Si se anula después de
#:   cargarla, sale de las dos listas y su historia queda igual.
#: - `outflow_type=''`: un gasto y una entrega a administración pasan por
#:   `cash_entries` y no son ventas. No tienen cliente ni sobre que facturar.
#: - `total > 0`: sin importe no hay nada que facturar. Es la línea que separa
#:   un borrador de una venta, y es la única regla acá que es una política y no
#:   un hecho del modelo. Está escrita a propósito en un solo lugar.
_POLITICA_ES_VENTA_FACTURABLE = (
    "e.status = 'ACTIVE' AND COALESCE(e.outflow_type,'') = '' AND COALESCE(e.total,0) > 0"
)

_SELECT = f"""
    SELECT
        e.id                              AS cash_entry_id,
        d.business_date                   AS fecha,
        COALESCE(b.branch, d.unit)        AS sucursal,
        d.unit                            AS caja,
        COALESCE(e.envelope,'')           AS sobre,
        COALESCE(e.description,'')        AS cliente,
        COALESCE(e.customer_document,'')  AS documento,
        COALESCE(e.customer_phone,'')     AS telefono,
        COALESCE(e.saleswoman,'')         AS vendedora,
        COALESCE(e.total,0)               AS total,
        COALESCE(e.observations,'')       AS observaciones,
        COALESCE(e.revision,0)            AS revision_venta,
        COALESCE(f.status,'{PARA_CARGAR}') AS estado,
        COALESCE(f.loaded_by,'')          AS cargada_por,
        COALESCE(f.loaded_at,'')          AS cargada_el,
        COALESCE(f.entry_revision,0)      AS revision_marcada
    FROM cash_entries e
    JOIN cash_days d ON d.id = e.cash_day_id
    LEFT JOIN cash_register_branches b ON b.cash_register = d.unit
    LEFT JOIN factufacil_loads f ON f.cash_entry_id = e.id
    WHERE {_POLITICA_ES_VENTA_FACTURABLE}
"""


class FactuFacilService:
    """Sólo lee ventas y escribe marcas. Nunca toca un importe."""

    def __init__(self, repository) -> None:
        self._repository = repository

    # -- consulta ----------------------------------------------------------

    def listar(
        self,
        *,
        estado: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        sucursal: str | None = None,
        sobre: str | None = None,
        cliente: str | None = None,
        vendedora: str | None = None,
    ) -> Sequence[FilaFactuFacil]:
        consulta, parametros = _SELECT, []
        if estado is not None:
            if estado not in ESTADOS:
                raise InvalidCashDayError(f"estado desconocido: {estado}")
            consulta += " AND COALESCE(f.status,?) = ?"
            parametros += [PARA_CARGAR, estado]
        for clausula, valor in (
            (" AND d.business_date >= ?", desde),
            (" AND d.business_date <= ?", hasta),
            (" AND UPPER(COALESCE(b.branch, d.unit)) = UPPER(?)", _limpio(sucursal)),
            (" AND COALESCE(e.envelope,'') LIKE ?", _contiene(sobre)),
            (" AND COALESCE(e.description,'') LIKE ?", _contiene(cliente)),
            (" AND COALESCE(e.saleswoman,'') LIKE ?", _contiene(vendedora)),
        ):
            if valor:
                consulta += clausula
                parametros.append(valor)
        consulta += " ORDER BY d.business_date DESC, sobre, e.created_at"
        with self._repository._connection() as conexion:
            filas = conexion.execute(consulta, parametros).fetchall()
        return tuple(FilaFactuFacil(**dict(fila)) for fila in filas)

    def obtener(self, cash_entry_id: str) -> FilaFactuFacil | None:
        with self._repository._connection() as conexion:
            fila = conexion.execute(
                _SELECT + " AND e.id = ?", (cash_entry_id,)).fetchone()
        return FilaFactuFacil(**dict(fila)) if fila else None

    def historial(self, cash_entry_id: str) -> Sequence[dict]:
        with self._repository._connection() as conexion:
            filas = conexion.execute(
                "SELECT * FROM factufacil_history WHERE cash_entry_id = ? ORDER BY id",
                (cash_entry_id,)).fetchall()
        return tuple(dict(fila) for fila in filas)

    def texto_para_copiar(self, cash_entry_id: str) -> str:
        """Leer para copiar no cambia nada: ni la marca, ni la venta."""
        fila = self.obtener(cash_entry_id)
        if fila is None:
            raise InvalidCashDayError("esa venta no está en FactuFácil")
        return fila.texto_para_copiar()

    # -- marcas ------------------------------------------------------------

    def marcar_cargada(self, cash_entry_id: str, *, actor: str) -> bool:
        """La cargó una persona en FactuFácil. Devuelve si algo cambió.

        Marcar dos veces no duplica ni pisa: la segunda devuelve `False` y deja
        el nombre y la hora de quien la cargó primero. Un doble clic no puede
        reescribir quién hizo el trabajo.
        """
        responsable = str(actor or "").strip()
        if not responsable:
            raise InvalidCashDayError("marcar una venta como cargada requiere responsable")
        return self._transicion(
            cash_entry_id, destino=CARGADA, actor=responsable,
            desde_permitidos={PARA_CARGAR}, accion="MARCADA_CARGADA", motivo="",
            repetir_es_inocuo=True)

    def revertir(self, cash_entry_id: str, *, actor: str, motivo: str) -> bool:
        """Vuelve a PARA CARGAR. Exige motivo, y no borra la historia."""
        responsable = str(actor or "").strip()
        razon = str(motivo or "").strip()
        if not responsable:
            raise InvalidCashDayError("revertir requiere responsable")
        if not razon:
            raise InvalidCashDayError("revertir requiere un motivo")
        return self._transicion(
            cash_entry_id, destino=PARA_CARGAR, actor=responsable,
            desde_permitidos={CARGADA}, accion="REVERTIDA", motivo=razon)

    def _transicion(self, cash_entry_id, *, destino, actor, desde_permitidos,
                    accion, motivo, repetir_es_inocuo: bool = False) -> bool:
        with self._repository._connection() as conexion:
            conexion.execute("BEGIN IMMEDIATE")
            try:
                venta = conexion.execute(
                    _SELECT + " AND e.id = ?", (cash_entry_id,)).fetchone()
                if venta is None:
                    raise InvalidCashDayError(
                        "esa venta no existe, está anulada o no es facturable")
                actual = venta["estado"]
                if actual == destino and repetir_es_inocuo:
                    # Marcar dos veces la misma venta es lo que pasa cuando el
                    # clic se repite o dos personas la cargan a la vez. No es un
                    # error y no puede reescribir quien la cargo primero.
                    conexion.rollback()
                    return False
                if actual not in desde_permitidos:
                    raise InvalidCashDayError(
                        f"no se puede pasar de {ETIQUETAS[actual]} a {ETIQUETAS[destino]}")
                ahora = _ahora()
                revision = int(venta["revision_venta"])
                if destino == CARGADA:
                    valores = (destino, actor, ahora, revision, ahora)
                else:
                    # Revertir no borra quién la había cargado: eso es historia y
                    # queda en `factufacil_history`. La marca vigente sí se limpia,
                    # porque ahora mismo no está cargada.
                    valores = (destino, "", "", revision, ahora)
                conexion.execute(
                    """INSERT INTO factufacil_loads(
                        cash_entry_id, status, loaded_by, loaded_at, entry_revision, updated_at
                    ) VALUES (?,?,?,?,?,?)
                    ON CONFLICT(cash_entry_id) DO UPDATE SET
                        status=excluded.status, loaded_by=excluded.loaded_by,
                        loaded_at=excluded.loaded_at,
                        entry_revision=excluded.entry_revision,
                        updated_at=excluded.updated_at""",
                    (cash_entry_id, *valores))
                conexion.execute(
                    """INSERT INTO factufacil_history(
                        cash_entry_id, from_state, to_state, actor, reason,
                        entry_revision, recorded_at
                    ) VALUES (?,?,?,?,?,?,?)""",
                    (cash_entry_id, actual, destino, actor, motivo, revision, ahora))
                conexion.execute(
                    """INSERT INTO admin_audit_log(
                        id, actor, action, target_type, target_id, result,
                        details_json, recorded_at
                    ) VALUES (?,?,?,?,?,?,?,?)""",
                    (str(uuid.uuid4()), actor, accion,
                     "CASH_ENTRY", cash_entry_id, destino,
                     json.dumps({"sobre": venta["sobre"], "motivo": motivo,
                                 "revision_venta": revision},
                                ensure_ascii=False, sort_keys=True), ahora))
                conexion.commit()
                return True
            except Exception:
                conexion.rollback()
                raise

    # -- resumen para la pantalla -----------------------------------------

    def conteos(self, **filtros) -> dict[str, int]:
        filtros.pop("estado", None)
        filas = self.listar(**filtros)
        return {
            PARA_CARGAR: sum(1 for f in filas if f.estado == PARA_CARGAR),
            CARGADA: sum(1 for f in filas if f.estado == CARGADA),
        }


def _limpio(valor: str | None) -> str | None:
    texto = str(valor or "").strip()
    return texto or None


def _contiene(valor: str | None) -> str | None:
    texto = str(valor or "").strip()
    return f"%{texto}%" if texto else None
