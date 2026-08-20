"""Servicio de trabajos operativos: composturas y trabajos de taller.

Orquesta el dominio de `domain.service_jobs` contra el repositorio SQLite y la
sesión de operadora de V1-019B. No envía correo, no toca importes de caja y no
mueve una sola unidad de inventario: lo último no es una promesa del código sino
una consecuencia de que este módulo no importe nada del núcleo comercial.

Quién hace qué queda derivado de la sesión, no preguntado de nuevo: la operadora
que está en la caja es quien recibe, y la sucursal la decide la caja.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Sequence

from ..domain.errors import InvalidCashDayError
from ..domain.models import parse_business_date, utc_now
from ..domain.service_jobs import (
    ESTADOS_ABIERTOS,
    ESTADO_DE_DEVENGO,
    ETIQUETA_ESTADO,
    JobEvent,
    JobHistoryEntry,
    JobStatus,
    ServiceJob,
    normalizar_sucursal,
    siguiente_referencia,
)


#: Vistas del tablero. Son las preguntas que el mostrador hace de verdad, y
#: `LISTOS` está primero porque es la que se hace veinte veces por día: quién
#: puede venir a retirar.
VISTA_LISTOS = "LISTOS"
VISTA_PENDIENTES = "PENDIENTES"
VISTA_EN_TALLER = "EN_TALLER"
VISTA_ENTREGADOS = "ENTREGADOS"
VISTA_ANULADOS = "ANULADOS"
VISTA_TODOS = "TODOS"

VISTAS = (VISTA_LISTOS, VISTA_PENDIENTES, VISTA_EN_TALLER, VISTA_ENTREGADOS,
          VISTA_ANULADOS, VISTA_TODOS)

ETIQUETA_VISTA = {
    VISTA_LISTOS: "Listos para entregar",
    VISTA_PENDIENTES: "Pendientes",
    VISTA_EN_TALLER: "En taller",
    VISTA_ENTREGADOS: "Entregados",
    VISTA_ANULADOS: "Anulados",
    VISTA_TODOS: "Todos",
}

_ESTADOS_DE_VISTA = {
    VISTA_LISTOS: (JobStatus.READY,),
    VISTA_PENDIENTES: ESTADOS_ABIERTOS,
    VISTA_EN_TALLER: (JobStatus.IN_WORKSHOP,),
    VISTA_ENTREGADOS: (JobStatus.DELIVERED,),
    VISTA_ANULADOS: (JobStatus.VOIDED,),
    VISTA_TODOS: tuple(JobStatus),
}


@dataclass(frozen=True)
class JobRow:
    """Una fila del tablero, ya legible. La UI no calcula nada."""

    job: ServiceJob

    @property
    def id(self) -> str:
        return self.job.id

    @property
    def reference(self) -> str:
        return self.job.reference

    @property
    def customer(self) -> str:
        return self.job.customer_name

    @property
    def phone(self) -> str:
        return self.job.customer_phone

    @property
    def work(self) -> str:
        return self.job.description

    @property
    def job_type(self) -> str:
        return self.job.job_type

    @property
    def responsible(self) -> str:
        return self.job.responsible or "SIN ASIGNAR"

    @property
    def status_label(self) -> str:
        return ETIQUETA_ESTADO[self.job.status]

    @property
    def branch(self) -> str:
        return self.job.branch

    @property
    def received_label(self) -> str:
        return self.job.received_at.astimezone().strftime("%d/%m/%Y")

    @property
    def promised_label(self) -> str:
        return self.job.promised_date.strftime("%d/%m/%Y") if self.job.promised_date else ""

    @property
    def charge_label(self) -> str:
        """El eje económico, dicho aparte del operativo.

        Vacío cuando el trabajo no tiene importe: no todo trabajo se cobra, y
        poner «Gs. 0» donde no hubo cobro sería inventar un hecho económico.
        """
        if self.job.cash_entry_id:
            return f"COBRADO {self.job.charged_amount:,}".replace(",", ".") \
                if self.job.charged_amount else "COBRADO"
        if self.job.charged_amount:
            return f"A COBRAR {self.job.charged_amount:,}".replace(",", ".")
        return ""

    @property
    def acciones(self) -> tuple[str, ...]:
        return tuple(ETIQUETA_ESTADO[estado] for estado in self.job.allowed_transitions())


class ServiceJobsService:
    """Los trabajos operativos de la óptica.

    `admin_ops` es opcional: sin él, el servicio sigue funcionando con actor y
    sucursal explícitos, que es lo que necesitan las pruebas. Con él, la caja no
    vuelve a preguntar quién es ni dónde está: ya lo sabe por la sesión.
    """

    def __init__(self, repository, admin_ops=None) -> None:
        self.repository = repository
        self.admin_ops = admin_ops

    # -- identidad y sucursal ----------------------------------------------

    def _actor(self, *, token: str | None, actor: str | None) -> str:
        """Quién está haciendo esto.

        Con sesión, sale de la sesión y no se puede falsear desde la pantalla.
        Sin sesión hay que decirlo explícitamente: lo que no existe es la
        operación anónima.
        """
        if token and self.admin_ops is not None:
            return self.admin_ops.require_operator(token).display_name
        nombre = str(actor or "").strip()
        if not nombre:
            raise InvalidCashDayError("No hay operación anónima: falta el actor.")
        return nombre

    def _branch(self, *, token: str | None, host_branch: str | None,
                branch: str | None) -> str:
        """La sucursal efectiva.

        La determina la caja, no la persona. Cuando hay sesión se delega en
        `effective_branch`, que ya es la autoridad canónica sobre eso desde
        V1-019B; acá no se re-decide nada ni se corrige en silencio.
        """
        if token and self.admin_ops is not None:
            return normalizar_sucursal(
                self.admin_ops.effective_branch(token, host_branch)["branch"])
        return normalizar_sucursal(branch or host_branch)

    def _usuario_por_nombre(self, nombre: str, *,
                            exigir_activa: bool = True) -> tuple[str, str | None]:
        """Resuelve el responsable contra el catálogo real de personas.

        No hay una segunda lista de responsables: son las personas de
        `admin_users`, las mismas que la 030 dejó como única. Si el nombre no
        está ahí, se rechaza; inventarlo sería volver a tener dos listas.

        `exigir_activa` se apaga para buscar y para filtrar: que alguien ya no
        trabaje en la óptica no borra los trabajos que hizo, y no poder mirarlos
        sería perder historia legítima por una regla de alta.
        """
        nombre = str(nombre or "").strip()
        if not nombre:
            return "", None
        with self.repository._connection() as connection:
            fila = connection.execute(
                "SELECT id, display_name, username, active FROM admin_users"
                " WHERE display_name = ? COLLATE NOCASE"
                "    OR username = ? COLLATE NOCASE",
                (nombre, nombre)).fetchone()
        if fila is None:
            raise InvalidCashDayError(
                f"{nombre} no está en el catálogo de personas. Cargala en "
                f"Administración antes de asignarle un trabajo.")
        if exigir_activa and not fila["active"]:
            raise InvalidCashDayError(
                f"{fila['display_name'] or fila['username']} está inactiva y no "
                f"puede quedar como responsable de un trabajo nuevo.")
        return (fila["display_name"] or fila["username"]), fila["id"]

    def responsables_disponibles(self) -> Sequence[str]:
        """Las personas activas, del catálogo real. Sin lista cableada."""
        with self.repository._connection() as connection:
            filas = connection.execute(
                "SELECT display_name, username FROM admin_users WHERE active = 1"
                " ORDER BY display_name COLLATE NOCASE").fetchall()
        return [(fila["display_name"] or fila["username"]) for fila in filas]

    def tipos_de_trabajo(self) -> Sequence[dict]:
        return self.repository.service_job_types()

    def _tipo_valido(self, job_type: str | None) -> str:
        """El tipo, contra el catálogo. Vacío significa compostura.

        Compostura es el default porque es lo que entra por el mostrador nueve
        de cada diez veces, no porque sea el primero de la lista.
        """
        codigo = str(job_type or "").strip().upper() or "COMPOSTURA"
        if codigo not in {tipo["code"] for tipo in self.repository.service_job_types()}:
            raise InvalidCashDayError(f"Tipo de trabajo desconocido: {job_type!r}.")
        return codigo

    # -- alta ---------------------------------------------------------------

    def crear_trabajo(
        self, *, customer_name: str, description: str, job_type: str = "COMPOSTURA",
        customer_phone: str = "", observations: str = "", responsible: str = "",
        promised_date: date | str | None = None, charged_amount: int | None = None,
        order_id: str | None = None, token: str | None = None,
        actor: str | None = None, host_branch: str | None = None,
        branch: str | None = None, occurred_at: datetime | None = None,
    ) -> ServiceJob:
        """Registra un trabajo que entra por el mostrador.

        Pide lo mínimo que un mostrador puede dar sin frenar la atención:
        cliente, qué hay que hacer, y nada más. El teléfono es opcional porque
        exigirlo haría que la operadora invente uno.
        """
        quien = self._actor(token=token, actor=actor)
        sucursal = self._branch(token=token, host_branch=host_branch, branch=branch)
        cuando = occurred_at or utc_now()
        codigo = self._tipo_valido(job_type)
        nombre_responsable, responsable_id = self._usuario_por_nombre(responsible)
        trabajo = ServiceJob(
            reference=siguiente_referencia(self.repository.service_job_references()),
            branch=sucursal, customer_name=customer_name,
            customer_phone=customer_phone, job_type=codigo, description=description,
            observations=observations, received_by=quien,
            responsible=nombre_responsable, responsible_user_id=responsable_id,
            promised_date=parse_business_date(promised_date) if promised_date else None,
            charged_amount=charged_amount, order_id=order_id,
            received_at=cuando, created_at=cuando, updated_at=cuando,
        ).registrar_creacion(actor=quien, occurred_at=cuando)
        return self.repository.save_service_job(trabajo)

    # -- responsable --------------------------------------------------------

    def asignar_responsable(self, job_id: str, responsible: str, *,
                            token: str | None = None, actor: str | None = None,
                            occurred_at: datetime | None = None) -> ServiceJob:
        quien = self._actor(token=token, actor=actor)
        trabajo = self._cargar(job_id)
        nombre, user_id = self._usuario_por_nombre(responsible)
        if not nombre:
            raise InvalidCashDayError("El responsable necesita un nombre.")
        actualizado = trabajo.asignar_responsable(
            nombre, actor=quien, user_id=user_id, occurred_at=occurred_at or utc_now())
        return self.repository.save_service_job(actualizado)

    # -- estados ------------------------------------------------------------

    def enviar_a_taller(self, job_id: str, **kwargs) -> ServiceJob:
        return self.cambiar_estado(job_id, JobStatus.IN_WORKSHOP, **kwargs)

    def marcar_listo(self, job_id: str, **kwargs) -> ServiceJob:
        return self.cambiar_estado(job_id, JobStatus.READY, **kwargs)

    def entregar(self, job_id: str, **kwargs) -> ServiceJob:
        return self.cambiar_estado(job_id, JobStatus.DELIVERED, **kwargs)

    def anular(self, job_id: str, *, reason: str, **kwargs) -> ServiceJob:
        return self.cambiar_estado(job_id, JobStatus.VOIDED, reason=reason, **kwargs)

    def reabrir(self, job_id: str, *, reason: str, **kwargs) -> ServiceJob:
        return self.cambiar_estado(job_id, JobStatus.IN_WORKSHOP, reason=reason, **kwargs)

    def cambiar_estado(
        self, job_id: str, destino: JobStatus | str, *, reason: str = "",
        delivered_by: str = "", token: str | None = None, actor: str | None = None,
        occurred_at: datetime | None = None,
    ) -> ServiceJob:
        """Mueve el trabajo y deja las consecuencias que correspondan.

        La consecuencia económica está acá y no en el dominio a propósito: el
        dominio decide si la transición es válida, y este servicio decide si esa
        transición devenga o compensa. Mezclarlas haría que construir un trabajo
        en memoria pagara comisiones.
        """
        quien = self._actor(token=token, actor=actor)
        trabajo = self._cargar(job_id)
        cuando = occurred_at or utc_now()
        anterior = trabajo.status
        actualizado = trabajo.transicionar(
            destino, actor=quien, reason=reason, delivered_by=delivered_by,
            occurred_at=cuando)
        actualizado, asientos = self._consecuencias_de_comision(
            actualizado, anterior=anterior, actor=quien, occurred_at=cuando,
            reason=reason)
        # El trabajo y sus asientos van juntos: la comisión cuelga de un hecho
        # de esta misma historia, y guardarlos por separado dejaría una ventana
        # en la que el trabajo dice haber devengado y la comisión no existe.
        return self.repository.save_service_job(actualizado, commissions=asientos)

    # -- cobro --------------------------------------------------------------

    def vincular_cobro(self, job_id: str, cash_entry_id: str, *, amount: int | None = None,
                       token: str | None = None, actor: str | None = None,
                       occurred_at: datetime | None = None) -> ServiceJob:
        """Deja dicho qué venta cobró este trabajo.

        No crea el movimiento de caja: el dinero entra por el circuito normal de
        venta y acá solo queda la referencia. Por eso el importe no se suma a
        ningún total de este módulo.
        """
        quien = self._actor(token=token, actor=actor)
        trabajo = self._cargar(job_id)
        actualizado = trabajo.vincular_cobro(
            cash_entry_id, actor=quien, amount=amount,
            occurred_at=occurred_at or utc_now())
        return self.repository.save_service_job(actualizado)

    def actualizar_datos(self, job_id: str, *, token: str | None = None,
                         actor: str | None = None, occurred_at: datetime | None = None,
                         **campos) -> ServiceJob:
        quien = self._actor(token=token, actor=actor)
        trabajo = self._cargar(job_id)
        if "promised_date" in campos and campos["promised_date"]:
            campos["promised_date"] = parse_business_date(campos["promised_date"])
        if campos.get("job_type"):
            # Se valida acá y no se deja llegar a la clave foránea: el error de
            # la base diría «FOREIGN KEY constraint failed», que no le sirve a
            # nadie que esté mirando un mostrador.
            campos["job_type"] = self._tipo_valido(campos["job_type"])
        actualizado = trabajo.actualizar_datos(
            actor=quien, occurred_at=occurred_at or utc_now(), **campos)
        return self.repository.save_service_job(actualizado)

    # -- comisión -----------------------------------------------------------

    def definir_comision(self, *, user_id: str, amount: int, job_type: str = "",
                         updated_by: str) -> None:
        """Carga la política de comisión de una persona.

        Nada viene sembrado: los montos y las personas son decisiones de la
        Óptica y se cargan una vez. Quien no tiene política no comisiona.
        """
        if int(amount) < 0:
            raise InvalidCashDayError("Una comisión no puede ser negativa.")
        self.repository.set_service_commission_policy(
            user_id=user_id, amount=int(amount), job_type=job_type,
            updated_by=updated_by)

    def comision_de(self, *, user_id: str | None, job_type: str) -> int:
        return self.repository.service_commission_amount(
            user_id=user_id, job_type=job_type)

    def comisiones_del_trabajo(self, job_id: str) -> Sequence[dict]:
        return self.repository.list_service_commissions(job_id=job_id)

    def saldo_de_comisiones(self) -> Sequence[dict]:
        return self.repository.service_commission_balance()

    def _consecuencias_de_comision(
        self, trabajo: ServiceJob, *, anterior: JobStatus, actor: str,
        occurred_at: datetime, reason: str,
    ) -> tuple[ServiceJob, list[dict]]:
        """Devenga al llegar al estado de devengo, compensa al anular.

        El devengo cuelga de un hecho propio -`COMISION_DEVENGADA`- y no del
        cambio de estado, así que la historia dice por separado que el trabajo
        quedó listo y que eso generó una comisión. La no-duplicación la sostiene
        el `event_id` único del asiento, no la memoria de quien llama.

        Rehacer un trabajo devenga de nuevo, y está bien: si volvió al taller y
        se hizo otra vez, se hizo otra vez. Lo que no puede pasar -y no pasa- es
        que el mismo hecho pague dos veces.
        """
        if trabajo.status is ESTADO_DE_DEVENGO and anterior is not ESTADO_DE_DEVENGO:
            return self._devengar(trabajo, actor=actor, occurred_at=occurred_at)
        if trabajo.status is JobStatus.VOIDED:
            return self._compensar_todo(
                trabajo, actor=actor, occurred_at=occurred_at, reason=reason)
        return trabajo, []

    def _devengar(self, trabajo: ServiceJob, *, actor: str,
                  occurred_at: datetime) -> tuple[ServiceJob, list[dict]]:
        monto = self.comision_de(user_id=trabajo.responsible_user_id,
                                 job_type=trabajo.job_type)
        if monto <= 0:
            return trabajo, []
        hecho = JobHistoryEntry(
            event_type=JobEvent.COMMISSION_ACCRUED, actor=actor,
            occurred_at=occurred_at,
            detail={"beneficiario": trabajo.responsible, "importe": monto,
                    "tipo": trabajo.job_type},
        )
        asiento = dict(
            job_id=trabajo.id, event_id=hecho.id,
            user_id=trabajo.responsible_user_id, beneficiary=trabajo.responsible,
            job_type=trabajo.job_type, kind="DEVENGO", amount=monto,
            note=f"Trabajo {trabajo.reference} {ETIQUETA_ESTADO[JobStatus.READY]}")
        return trabajo._con_hecho(hecho), [asiento]

    def _compensar_todo(self, trabajo: ServiceJob, *, actor: str,
                        occurred_at: datetime, reason: str,
                        ) -> tuple[ServiceJob, list[dict]]:
        """Anular un trabajo deshace su consecuencia económica.

        No borra el devengo: asienta su contrario. Así el histórico sigue
        diciendo que se devengó y que después se compensó, que es lo que pasó.
        """
        asientos = self.repository.list_service_commissions(job_id=trabajo.id)
        devengos = [item for item in asientos if item["kind"] == "DEVENGO"]
        compensados = {item["compensates_id"] for item in asientos
                       if item["kind"] == "COMPENSACION"}
        actualizado, asientos = trabajo, []
        for devengo in devengos:
            if devengo["id"] in compensados:
                continue
            hecho = JobHistoryEntry(
                event_type=JobEvent.COMMISSION_COMPENSATED, actor=actor,
                occurred_at=occurred_at, reason=reason,
                detail={"beneficiario": devengo["beneficiary"],
                        "importe": -int(devengo["amount"]),
                        "compensa": devengo["id"]},
            )
            actualizado = actualizado._con_hecho(hecho)
            asientos.append(dict(
                job_id=trabajo.id, event_id=hecho.id,
                user_id=devengo["user_id"], beneficiary=devengo["beneficiary"],
                job_type=devengo["job_type"], kind="COMPENSACION",
                amount=-int(devengo["amount"]), compensates_id=devengo["id"],
                note=f"Trabajo {trabajo.reference} anulado: {reason}"))
        return actualizado, asientos

    # -- lecturas -----------------------------------------------------------

    def _cargar(self, job_id: str) -> ServiceJob:
        trabajo = self.repository.get_service_job(job_id)
        if trabajo is None:
            raise InvalidCashDayError(f"No existe el trabajo {job_id}.")
        return trabajo

    def obtener(self, job_id: str) -> ServiceJob:
        return self._cargar(job_id)

    def historial(self, job_id: str) -> Sequence[JobHistoryEntry]:
        return self._cargar(job_id).history

    def tablero(
        self, *, vista: str = VISTA_PENDIENTES, branch: str | None = None,
        responsible: str | None = None, received_from: date | None = None,
        received_to: date | None = None,
    ) -> Sequence[JobRow]:
        """Lo que la pantalla muestra, ya filtrado y ordenado."""
        if vista not in VISTAS:
            raise InvalidCashDayError(f"Vista desconocida: {vista!r}.")
        responsable_id = None
        if responsible:
            _, responsable_id = self._usuario_por_nombre(
                responsible, exigir_activa=False)
        trabajos = self.repository.list_service_jobs(
            branch=normalizar_sucursal(branch) if branch else None,
            status=[estado.value for estado in _ESTADOS_DE_VISTA[vista]],
            responsible_user_id=responsable_id,
            received_from=received_from, received_to=received_to,
        )
        return [JobRow(job=trabajo) for trabajo in trabajos]

    def resumen(self, *, branch: str | None = None) -> dict:
        """Cuántos hay en cada estado. Para el encabezado, no un dashboard."""
        conteo = {estado.value: 0 for estado in JobStatus}
        for trabajo in self.repository.list_service_jobs(
                branch=normalizar_sucursal(branch) if branch else None):
            conteo[trabajo.status.value] += 1
        return conteo
