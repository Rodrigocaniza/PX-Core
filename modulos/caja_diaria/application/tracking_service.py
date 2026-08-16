"""Servicio del circuito de seguimiento Pilar / laboratorios.

Orquesta el dominio de `domain.tracking` contra el repositorio SQLite local.
No envia correo, no toca importes y no requiere red: la operacion completa
funciona sin internet, igual que el resto de BC Caja.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable, Mapping, Sequence

from ..domain.errors import InvalidCashDayError
from ..domain.models import BUSINESS_TIMEZONE, parse_business_date
from ..domain.tracking import (
    DEFAULT_EXPECTED_TIME,
    SUCURSAL_PROCESO_POR_DEFECTO,
    normalizar_sucursal,
    ContactChannel,
    ContactRecord,
    Laboratory,
    PilarShipment,
    TrackedWork,
    TrackingStatus,
    shipment_progress,
    group_overdue_by_laboratory,
    operational_summary,
    overdue_alert,
    parse_expected_time,
    reception_progress,
)

TRACKING_SETTING_KEY = "tracking"

#: Rotulos legibles del circuito. El enum guarda el valor canonico con guiones
#: bajos; la operadora lee la etapa fisica en castellano.
ETIQUETAS_ESTADO = {
    TrackingStatus.SENT_FROM_PILAR: "ENVIADO DESDE PILAR",
    TrackingStatus.RECEIVED_IN_ASUNCION: "RECIBIDO EN ASUNCIÓN",
    TrackingStatus.IN_LABORATORY: "EN LABORATORIO",
    TrackingStatus.RECEIVED_FROM_LABORATORY: "RECIBIDO DEL LABORATORIO",
    TrackingStatus.SENT_TO_PILAR: "ENVIADO A PILAR",
    TrackingStatus.RECEIVED_IN_PILAR: "RECIBIDO EN PILAR",
    TrackingStatus.CLOSED: "CERRADO",
}

#: Los seis estados que la tabla debe poder mostrar. `CERRADO` queda fuera:
#: el circuito operativo termina al confirmarse la recepcion en Pilar.
ESTADOS_VISIBLES = (
    TrackingStatus.SENT_FROM_PILAR,
    TrackingStatus.RECEIVED_IN_ASUNCION,
    TrackingStatus.IN_LABORATORY,
    TrackingStatus.RECEIVED_FROM_LABORATORY,
    TrackingStatus.SENT_TO_PILAR,
    TrackingStatus.RECEIVED_IN_PILAR,
)

#: Un trabajo esta activo mientras no completo el circuito. `RECIBIDO EN
#: PILAR` lo completa; `CERRADO` es el archivado posterior.
ESTADOS_COMPLETADOS = (TrackingStatus.RECEIVED_IN_PILAR, TrackingStatus.CLOSED)

SCOPE_ACTIVOS = "ACTIVOS"
SCOPE_COMPLETADOS = "COMPLETADOS"
SCOPE_TODOS = "TODOS"

ALERTA_ATRASADO = "ATRASADO"
ALERTA_CONFIRMADO = "CONFIRMADO PARA MAÑANA"
SIN_LABORATORIO = "SIN ASIGNAR"


@dataclass(frozen=True)
class BoardRow:
    """Fila lista para la grilla: el laboratorio ya viene resuelto.

    La operadora ve linea y WhatsApp en la misma fila; no tiene que preguntar
    de que laboratorio se trata ni entrar a otra pantalla a buscar el numero.
    """

    work: TrackedWork
    laboratory: Laboratory | None
    overdue: bool

    @property
    def envelope(self) -> str:
        return self.work.envelope

    @property
    def customer_name(self) -> str:
        return self.work.customer_name

    @property
    def status_label(self) -> str:
        if self.overdue:
            return "ATRASADO"
        if self.work.confirmed_for_next_day and self.work.status is TrackingStatus.IN_LABORATORY:
            return "CONFIRMADO_PARA_MAÑANA"
        return self.work.status.value

    # -- presentacion del circuito ----------------------------------------

    @property
    def physical_status(self) -> str:
        """Etapa fisica real. Nunca la borra una condicion derivada."""
        return ETIQUETAS_ESTADO[self.work.status]

    @property
    def alert(self) -> str:
        """Condicion derivada que acompaña a la etapa, si la hay."""
        if self.overdue:
            return ALERTA_ATRASADO
        if self.work.confirmed_for_next_day and self.work.status is TrackingStatus.IN_LABORATORY:
            return ALERTA_CONFIRMADO
        return ""

    @property
    def status_display(self) -> str:
        """`ATRASADO · EN LABORATORIO`: la alerta antepone, no reemplaza."""
        if self.alert:
            return f"{self.alert} · {self.physical_status}"
        return self.physical_status

    @property
    def responsible_branch(self) -> str | None:
        return self.work.responsible_branch

    @property
    def work_type(self) -> str:
        """Tipo de trabajo, tomado de la observacion del pedido de origen."""
        observacion = (self.work.observations or "").strip()
        return observacion.splitlines()[0] if observacion else ""

    @property
    def laboratory_name(self) -> str:
        """`SIN ASIGNAR` mientras el trabajo no salio a ningun laboratorio."""
        return self.laboratory.name if self.laboratory is not None else SIN_LABORATORIO

    @property
    def phone_line(self) -> str:
        return self.laboratory.phone_line if self.laboratory else ""

    @property
    def whatsapp(self) -> str:
        return self.laboratory.whatsapp if self.laboratory else ""

    @property
    def expected_label(self) -> str:
        if self.work.expected_date is None:
            return ""
        fecha = self.work.expected_date.strftime("%d-%m")
        hora = (self.work.expected_time or DEFAULT_EXPECTED_TIME).strftime("%H:%M")
        return f"{fecha} {hora}"

    @property
    def last_news(self) -> str:
        return self.work.last_news()


class TrackingService:
    def __init__(self, repository) -> None:
        self.repository = repository

    # -- configuracion -----------------------------------------------------

    def settings(self) -> dict:
        with self.repository._connection() as connection:
            row = connection.execute(
                "SELECT value_json FROM app_settings WHERE key = ?", (TRACKING_SETTING_KEY,),
            ).fetchone()
        return json.loads(row["value_json"]) if row else {}

    def default_expected_time(self) -> time:
        """Hora esperada por defecto, configurable y nunca cableada."""
        configurado = self.settings().get("default_expected_time")
        try:
            return parse_expected_time(configurado) or DEFAULT_EXPECTED_TIME
        except InvalidCashDayError:
            return DEFAULT_EXPECTED_TIME

    # -- laboratorios ------------------------------------------------------

    def save_laboratory(
        self, *, name: str, phone_line: str = "", whatsapp: str = "",
        active: bool = True, laboratory_id: str | None = None,
    ) -> Laboratory:
        datos = dict(name=name, phone_line=phone_line, whatsapp=whatsapp, active=active)
        if laboratory_id:
            datos["id"] = laboratory_id
        return self.repository.save_laboratory(Laboratory(**datos))

    def list_laboratories(self, *, only_active: bool = False) -> Sequence[Laboratory]:
        return self.repository.list_laboratories(only_active=only_active)

    def laboratory_catalog(self) -> dict[str, Laboratory]:
        return {lab.id: lab for lab in self.repository.list_laboratories()}

    def update_laboratory(
        self, laboratory_id: str, *, name: str | None = None,
        phone_line: str | None = None, whatsapp: str | None = None,
        active: bool | None = None,
    ) -> Laboratory:
        actual = self.repository.get_laboratory(laboratory_id)
        if actual is None:
            raise InvalidCashDayError(f"laboratorio inexistente: {laboratory_id}")
        return self.repository.save_laboratory(Laboratory(
            id=actual.id,
            name=actual.name if name is None else name,
            phone_line=actual.phone_line if phone_line is None else phone_line,
            whatsapp=actual.whatsapp if whatsapp is None else whatsapp,
            active=actual.active if active is None else active,
            created_at=actual.created_at,
        ))

    def set_laboratory_active(self, laboratory_id: str, active: bool) -> Laboratory:
        """Alta y baja logica: nunca se borra fisicamente.

        Un laboratorio con historial debe seguir existiendo para que los
        trabajos pasados conserven a quien se les envio; desactivarlo solo lo
        retira de las opciones de envio nuevo.
        """
        return self.update_laboratory(laboratory_id, active=active)

    def laboratory_has_history(self, laboratory_id: str) -> bool:
        return self.repository.laboratory_has_history(laboratory_id)

    def selectable_laboratories(self) -> Sequence[Laboratory]:
        """Opciones validas para un envio nuevo: solo laboratorios activos."""
        return self.repository.list_laboratories(only_active=True)

    # -- vinculo caja -> sucursal ------------------------------------------

    def branch_of_register(self, cash_register: str) -> str | None:
        """Sucursal de la caja. None si nadie la asigno: no se adivina."""
        return self.repository.branch_of_register(cash_register)

    def bind_register_to_branch(
        self, cash_register: str, branch: str, *, assigned_by: str, reason: str = "",
    ) -> None:
        self.repository.bind_register_to_branch(
            cash_register, branch, assigned_by=assigned_by, reason=reason)

    def list_register_branches(self):
        return self.repository.list_register_branches()

    def pending_actions_for_branch(
        self, branch: str, *, now: datetime | None = None,
    ) -> dict:
        """Que tiene pendiente este local, y nada mas.

        Se calcula por sucursal responsable de la proxima accion, no por la
        mera existencia del trabajo: el mismo trabajo alerta en Asuncion
        mientras esta en laboratorio y en Pilar recien cuando va en camino.
        """
        objetivo = normalizar_sucursal(branch)
        momento = now or datetime.now(BUSINESS_TIMEZONE)
        works = [
            w for w in self.list_works()
            if w.responsible_branch == objetivo and w.status not in ESTADOS_COMPLETADOS
        ]
        por_recibir_consulta = sum(
            1 for w in works if w.status is TrackingStatus.SENT_FROM_PILAR)
        por_enviar_lab = sum(
            1 for w in works if w.status is TrackingStatus.RECEIVED_IN_ASUNCION)
        en_lab = sum(1 for w in works if w.status is TrackingStatus.IN_LABORATORY)
        atrasados = sum(1 for w in works if w.is_overdue(momento))
        por_encomendar = sum(
            1 for w in works if w.status is TrackingStatus.RECEIVED_FROM_LABORATORY)
        por_recibir_encomienda = sum(
            1 for w in works if w.status is TrackingStatus.SENT_TO_PILAR)
        alertas = []
        if atrasados:
            alertas.append({
                "clave": "atrasados", "cantidad": atrasados, "filtro": "Atrasados",
                "texto": f"{atrasados} atrasado{'' if atrasados == 1 else 's'}"
                         " — contactar laboratorios"})
        if por_recibir_consulta:
            alertas.append({
                "clave": "por_recibir", "cantidad": por_recibir_consulta,
                "filtro": "Por recibir",
                "texto": f"{por_recibir_consulta} por recibir desde Pilar"})
        if por_enviar_lab:
            alertas.append({
                "clave": "por_enviar_lab", "cantidad": por_enviar_lab,
                "filtro": "Recibidos en Asunción",
                "texto": f"{por_enviar_lab} pendiente{'' if por_enviar_lab == 1 else 's'}"
                         " de enviar a laboratorio"})
        if por_encomendar:
            alertas.append({
                "clave": "por_encomendar", "cantidad": por_encomendar,
                "filtro": "Listos p/ Pilar",
                "texto": f"{por_encomendar} listo{'' if por_encomendar == 1 else 's'}"
                         " para enviar a Pilar"})
        if por_recibir_encomienda:
            alertas.append({
                "clave": "por_recibir_encomienda", "cantidad": por_recibir_encomienda,
                "filtro": "En tránsito",
                "texto": f"{por_recibir_encomienda} encomienda(s) por recibir en "
                         f"{objetivo.title()}"})
        return {
            "branch": objetivo, "total": len(works), "alertas": alertas,
            "atrasados": atrasados, "en_laboratorio": en_lab,
        }

    # -- alta de lote desde Pilar ------------------------------------------

    #: La consulta puede terminar un dia y el lote armarse al siguiente, asi
    #: que la ventana por defecto cubre hoy y los dos dias previos. No cambia
    #: el criterio: sigue siendo la fecha de creacion del pedido.
    DEFAULT_CANDIDATE_DAYS = 3

    def default_candidate_range(self, today: date | str | None = None) -> tuple[date, date]:
        fin = parse_business_date(today or date.today())
        return fin - timedelta(days=self.DEFAULT_CANDIDATE_DAYS - 1), fin

    def shipment_candidates(
        self, *, branch: str = "Pilar", consultation_date: date | str | None = None,
        end_date: date | str | None = None,
    ) -> Sequence:
        """Trabajos ya cargados en Caja que todavia no salieron en un envio.

        No se pide recargar nada: los candidatos son los pedidos existentes de
        la sucursal, y los ya seguidos quedan excluidos en la propia consulta.

        Sin fechas explicitas se usa la ventana por defecto de tres dias, de
        modo que la consulta del viernes siga visible el sabado sin tocar el
        selector. Con fechas explicitas manda lo que eligio la operadora.
        """
        if consultation_date in (None, "") and end_date in (None, ""):
            return self.repository.list_shipment_candidates(
                branch=branch, start_date=self.default_candidate_range()[0],
                end_date=self.default_candidate_range()[1],
            )
        inicio = parse_business_date(consultation_date or date.today())
        fin = parse_business_date(end_date) if end_date not in (None, "") else inicio
        if fin < inicio:
            inicio, fin = fin, inicio
        return self.repository.list_shipment_candidates(
            branch=branch, start_date=inicio, end_date=fin,
        )

    def create_pilar_shipment(
        self, order_ids: Sequence[str], *, operator: str,
        consultation_date: date | str | None = None,
        shipped_on: date | str | None = None, branch: str = "Pilar", note: str = "",
    ) -> dict:
        """Crea el lote y marca sus trabajos ENVIADO_DESDE_PILAR de una vez."""
        seleccion = [str(order_id) for order_id in order_ids if str(order_id or "").strip()]
        if not seleccion:
            raise InvalidCashDayError("seleccioná al menos un trabajo para el envío")
        ya_enviados = self.repository.list_tracked_works_for_orders(seleccion)
        if ya_enviados:
            sobres = ", ".join(sorted(work.envelope for work in ya_enviados))
            raise InvalidCashDayError(
                f"estos trabajos ya salieron en un envío anterior: {sobres}"
            )
        # La elegibilidad se resuelve sobre los pedidos elegidos, no volviendo
        # a filtrar por fecha. La operadora ya los selecciono de una busqueda
        # que puede abarcar un rango; re-derivar por un unico dia hacia fallar
        # el envio con "ya no estan disponibles" aunque estuvieran a la vista.
        catalogo = {
            pedido.id: pedido for pedido in self.repository.list_orders_by_ids(seleccion)
        }
        faltantes = [order_id for order_id in seleccion if order_id not in catalogo]
        if faltantes:
            raise InvalidCashDayError(
                f"{len(faltantes)} trabajo(s) ya no existen y no pueden enviarse"
            )
        ajenos = sorted(
            pedido.envelope for pedido in catalogo.values()
            if pedido.branch.casefold() != branch.strip().casefold()
        )
        if ajenos:
            raise InvalidCashDayError(
                f"estos trabajos no son de {branch}: {', '.join(ajenos)}"
            )
        # Sin fecha explicita, la consulta se deduce del propio lote.
        consulta = (
            parse_business_date(consultation_date) if consultation_date not in (None, "")
            else max(pedido.created_at.date() for pedido in catalogo.values())
        )
        envio = self.repository.save_pilar_shipment(PilarShipment(
            shipped_on=shipped_on or consulta, operator=operator,
            consultation_date=consulta, origin_branch=branch, note=note,
        ))
        trabajos = []
        for order_id in seleccion:
            pedido = catalogo[order_id]
            trabajos.append(self.repository.save_tracked_work(TrackedWork(
                envelope=pedido.envelope, customer_name=pedido.customer_name,
                observations=pedido.observations, order_id=pedido.id,
                cash_entry_id=pedido.cash_entry_id, shipment_id=envio.id,
                consultation_date=consulta, created_by=operator,
                origin_branch=branch,
            )))
        return {"shipment": envio, "works": trabajos, "count": len(trabajos)}

    def shipment_detail(self, shipment_id: str) -> dict:
        envio = self.repository.get_pilar_shipment(shipment_id)
        if envio is None:
            raise InvalidCashDayError(f"envío inexistente: {shipment_id}")
        trabajos = [
            work for work in self.repository.list_tracked_works()
            if work.shipment_id == shipment_id
        ]
        return {"shipment": envio, "works": trabajos, **shipment_progress(trabajos)}

    def work_detail(self, work_id: str, *, now: datetime | None = None) -> dict:
        """Ficha completa del trabajo: identidad, plazo, contacto e historial."""
        work = self._load(work_id)
        laboratorio = (
            self.repository.get_laboratory(work.laboratory_id)
            if work.laboratory_id else None
        )
        fila = BoardRow(
            work=work, laboratory=laboratorio,
            overdue=work.is_overdue(now or datetime.now(BUSINESS_TIMEZONE)),
        )
        return {
            "envelope": fila.envelope,
            "customer_name": fila.customer_name,
            "work_type": fila.work_type,
            "status": fila.status_display,
            "physical_status": fila.physical_status,
            "alert": fila.alert,
            "laboratory": fila.laboratory_name,
            "phone_line": fila.phone_line,
            "whatsapp": fila.whatsapp,
            "expected": fila.expected_label,
            "last_news": fila.last_news,
            "contacts": work.contacts,
            "transitions": work.transitions,
            "order_id": work.order_id,
            "shipment_id": work.shipment_id,
            "created_by": work.created_by,
            "observations": work.observations,
        }

    def list_shipments(self, *, limit: int = 50) -> Sequence[PilarShipment]:
        return self.repository.list_pilar_shipments(limit=limit)

    # -- alta directa (sin pedido previo) ----------------------------------

    def register_pilar_batch(
        self, works: Iterable[Mapping], *, consultation_date: date | str,
        created_by: str, origin_branch: str = "PILAR",
    ) -> list[TrackedWork]:
        """Nidia carga la consulta del viernes y la marca enviada desde Pilar."""
        consulta = parse_business_date(consultation_date)
        registrados = []
        for datos in works:
            work = TrackedWork(
                envelope=str(datos.get("envelope", "")),
                customer_name=str(datos.get("customer_name", "")),
                observations=str(datos.get("observations", "")),
                order_id=datos.get("order_id"),
                cash_entry_id=datos.get("cash_entry_id"),
                consultation_date=consulta, created_by=created_by,
                origin_branch=origin_branch,
            )
            registrados.append(self.repository.save_tracked_work(work))
        return registrados

    # -- transiciones ------------------------------------------------------

    def _load(self, work_id: str) -> TrackedWork:
        work = self.repository.get_tracked_work(work_id)
        if work is None:
            raise InvalidCashDayError(f"trabajo inexistente: {work_id}")
        return work

    def _advance(
        self, work_id: str, status: TrackingStatus, *, responsible: str, note: str = "",
    ) -> TrackedWork:
        actualizado = self._load(work_id).transition_to(
            status, responsible=responsible, note=note,
        )
        return self.repository.save_tracked_work(actualizado)

    def receive_in_asuncion(self, work_id: str, *, responsible: str, note: str = "") -> TrackedWork:
        return self._advance(
            work_id, TrackingStatus.RECEIVED_IN_ASUNCION, responsible=responsible, note=note,
        )

    def receive_batch_in_asuncion(
        self, work_ids: Iterable[str], *, responsible: str,
    ) -> list[TrackedWork]:
        return [self.receive_in_asuncion(work_id, responsible=responsible) for work_id in work_ids]

    def send_to_laboratory(
        self, work_id: str, laboratory_id: str, *, expected_date: date | str,
        expected_time: time | str | None = None, responsible: str, note: str = "",
    ) -> TrackedWork:
        if self.repository.get_laboratory(laboratory_id) is None:
            raise InvalidCashDayError(f"laboratorio inexistente: {laboratory_id}")
        actualizado = self._load(work_id).send_to_laboratory(
            laboratory_id, expected_date=expected_date,
            expected_time=expected_time or self.default_expected_time(),
            responsible=responsible, note=note,
        )
        return self.repository.save_tracked_work(actualizado)

    def receive_from_laboratory(
        self, work_id: str, *, responsible: str, note: str = "",
    ) -> TrackedWork:
        return self._advance(
            work_id, TrackingStatus.RECEIVED_FROM_LABORATORY, responsible=responsible, note=note,
        )

    def send_batch_to_pilar(
        self, work_ids: Iterable[str], *, responsible: str, note: str = "",
    ) -> list[TrackedWork]:
        """La encomienda viaja como lote, pero cada trabajo conserva su traza."""
        return [
            self._advance(work_id, TrackingStatus.SENT_TO_PILAR, responsible=responsible, note=note)
            for work_id in work_ids
        ]

    def receive_in_pilar(self, work_id: str, *, responsible: str, note: str = "") -> TrackedWork:
        return self._advance(
            work_id, TrackingStatus.RECEIVED_IN_PILAR, responsible=responsible, note=note,
        )

    def close_work(self, work_id: str, *, responsible: str, note: str = "") -> TrackedWork:
        return self._advance(work_id, TrackingStatus.CLOSED, responsible=responsible, note=note)

    # -- contactos ---------------------------------------------------------

    def register_contact(
        self, work_id: str, *, operator: str, channel: ContactChannel | str = ContactChannel.CALL,
        result: str = "", next_expected_date: date | str | None = None,
        next_expected_time: time | str | None = None,
        recorded_at: datetime | None = None,
    ) -> TrackedWork:
        contacto = ContactRecord(
            operator=operator, channel=channel, result=result,
            next_expected_date=next_expected_date,
            next_expected_time=next_expected_time,
            **({"recorded_at": recorded_at} if recorded_at else {}),
        )
        return self.repository.save_tracked_work(self._load(work_id).register_contact(contacto))

    def confirm_for_next_day(
        self, work_id: str, *, operator: str, next_expected_date: date | str,
        next_expected_time: time | str | None = None,
        channel: ContactChannel | str = ContactChannel.CALL, result: str = "",
        recorded_at: datetime | None = None,
    ) -> TrackedWork:
        """Azucar sobre `register_contact`: confirmar es registrar la novedad."""
        return self.register_contact(
            work_id, operator=operator, channel=channel,
            result=result or "Confirmado para el dia siguiente",
            next_expected_date=next_expected_date,
            next_expected_time=next_expected_time or self.default_expected_time(),
            recorded_at=recorded_at,
        )

    def contact_history(self, work_id: str) -> Sequence[ContactRecord]:
        return self._load(work_id).contacts

    # -- vistas ------------------------------------------------------------

    def list_works(
        self, *, consultation_date: date | str | None = None, status: str | None = None,
        laboratory_id: str | None = None,
    ) -> Sequence[TrackedWork]:
        return self.repository.list_tracked_works(
            consultation_date=parse_business_date(consultation_date)
            if consultation_date not in (None, "") else None,
            status=status or None, laboratory_id=laboratory_id or None,
        )

    def board(
        self, *, consultation_date: date | str | None = None, status: str | None = None,
        laboratory_id: str | None = None, only_overdue: bool = False,
        origin_branch: str | None = None, responsible_branch: str | None = None,
        scope: str = SCOPE_ACTIVOS, now: datetime | None = None,
    ) -> dict:
        """Todo lo que la pantalla necesita, resuelto en una sola consulta.

        Por defecto devuelve los trabajos **activos**: la operadora entra a la
        pestaña para saber que tiene pendiente, no para revisar lo terminado.
        Los completados siguen consultables con `scope=COMPLETADOS`.
        """
        momento = now or datetime.now(BUSINESS_TIMEZONE)
        works = list(self.list_works(
            consultation_date=consultation_date, status=status, laboratory_id=laboratory_id,
        ))
        if origin_branch:
            works = [work for work in works if work.origin_branch == normalizar_sucursal(origin_branch)]
        if responsible_branch:
            # Vista operativa local: solo lo que este local tiene que resolver.
            objetivo = normalizar_sucursal(responsible_branch)
            works = [w for w in works if w.responsible_branch == objetivo]
        if scope == SCOPE_ACTIVOS:
            works = [w for w in works if w.status not in ESTADOS_COMPLETADOS]
        elif scope == SCOPE_COMPLETADOS:
            works = [w for w in works if w.status in ESTADOS_COMPLETADOS]
        catalogo = self.laboratory_catalog()
        filas = [
            BoardRow(
                work=work, laboratory=catalogo.get(work.laboratory_id),
                overdue=work.is_overdue(momento),
            )
            for work in works
        ]
        if only_overdue:
            filas = [fila for fila in filas if fila.overdue]
        # Las excepciones primero: atrasado, luego lo que vence antes.
        filas.sort(key=lambda fila: (
            0 if fila.overdue else 1,
            fila.work.deadline or datetime.max.replace(tzinfo=BUSINESS_TIMEZONE),
            fila.work.envelope,
        ))
        return {
            "rows": filas,
            "summary": operational_summary(works, momento),
            "reception": reception_progress(works),
            "overdue_groups": group_overdue_by_laboratory(works, catalogo, momento),
            "alert": overdue_alert(works, momento),
        }
