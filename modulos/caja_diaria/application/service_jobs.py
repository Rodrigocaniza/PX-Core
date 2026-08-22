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
from datetime import date, datetime, time, timezone
from typing import Sequence

from ..domain.errors import InvalidCashDayError
from ..domain.models import BUSINESS_TIMEZONE, parse_business_date, utc_now
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
        """Las personas activas, del catálogo real. Sin lista cableada.

        Ordena por el nombre que se ve y no por la columna `display_name`, igual
        que `personas_para_comision`: quien no tenga uno cargado se muestra por
        su usuario, y ordenar por la columna cruda lo mandaba al principio por
        ser NULL, a un lugar que no se corresponde con nada de lo que está en
        pantalla.

        Hoy `create_user` no deja que eso pase —si el nombre visible viene vacío
        lo reemplaza por el usuario—, así que por la puerta de entrada normal la
        lista salía bien igual. Se unifica porque la fila puede llegar por otro
        lado (SQL directo, una importación, una migración futura) y porque tener
        dos consultas que dicen lo mismo de dos maneras es cómo empiezan las
        pantallas que no coinciden entre sí.
        """
        with self.repository._connection() as connection:
            filas = connection.execute(
                "SELECT COALESCE(NULLIF(TRIM(display_name), ''), username) AS visible"
                " FROM admin_users WHERE active = 1"
                " ORDER BY visible COLLATE NOCASE").fetchall()
        return [fila["visible"] for fila in filas]

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
        actualizado, asientos, auditorias = self._consecuencias_de_comision(
            actualizado, anterior=anterior, actor=quien, occurred_at=cuando,
            reason=reason)
        # El trabajo, sus asientos y su bitácora van juntos: la comisión cuelga
        # de un hecho de esta misma historia, y guardarlos por separado dejaría
        # una ventana en la que el trabajo dice haber devengado y la comisión no
        # existe. La auditoría entra por la misma puerta y por lo mismo: la
        # línea que dice «este trabajo no devengó porque no hay política» es la
        # única huella de esa omisión, y escribirla después es no escribirla.
        return self.repository.save_service_job(
            actualizado, commissions=asientos, audits=auditorias)

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

    # -- comisión: quién puede tocarla --------------------------------------

    def _administradora(self, *, token: str | None, actor: str | None) -> str:
        """Quién está cambiando la política. Rol, no sólo sesión.

        Es más estricto que `_actor`, y la asimetría es a propósito. Recibir un
        trabajo es operativo y lo hace quien está atendiendo; decidir cuánto
        cobra alguien por trabajo es una decisión sobre plata, y esa pide el
        rol. Con `admin_ops` conectado el token no es opcional: dejar un camino
        que acepte un nombre suelto sería dejar la política sin puerta, y
        esconder la pestaña no cierra una puerta.
        """
        if self.admin_ops is not None:
            if not token:
                raise InvalidCashDayError(
                    "Administrar la comisión de composturas pide una sesión "
                    "administrativa.")
            return self.admin_ops.require_admin(token).username
        nombre = str(actor or "").strip()
        if not nombre:
            raise InvalidCashDayError("No hay operación anónima: falta el actor.")
        return nombre

    def _persona_de_politica(self, user_id: str, *, exigir_activa: bool) -> dict:
        """La persona real del catálogo, o el motivo por el que no sirve.

        Se pide el identificador y no el nombre: cambiar cómo se escribe
        «Dirección» no puede mover una tarifa de lugar.
        """
        with self.repository._connection() as connection:
            fila = connection.execute(
                "SELECT id, display_name, username, active FROM admin_users"
                " WHERE id = ?", (str(user_id or ""),)).fetchone()
        if fila is None:
            raise InvalidCashDayError(
                "Esa persona no está en el catálogo. Cargala en Administración "
                "antes de definirle una comisión.")
        if exigir_activa and not fila["active"]:
            raise InvalidCashDayError(
                f"{fila['display_name'] or fila['username']} está inactiva: no se "
                f"le puede definir una comisión nueva.")
        return dict(fila)

    @staticmethod
    def _tipo_de_politica(job_type: str | None) -> str:
        """El tipo al que aplica la regla. Vacío es «cualquier tipo».

        No reusa `_tipo_valido` porque ahí el vacío significa lo contrario: al
        dar de alta un trabajo, no decir el tipo quiere decir compostura, y en
        una política quiere decir todos. Un mismo default para dos preguntas
        distintas es como se cuela una regla que nadie escribió.
        """
        return str(job_type or "").strip().upper()

    @staticmethod
    def _instante_de_vigencia(value: date | datetime | str | None) -> str:
        """Desde cuándo rige, siempre en UTC.

        Todo lo que se compara con esto -otra vigencia, el momento del devengo-
        se guarda igual, y por eso alcanza con comparar los textos. Mezclar
        husos rompería justo el orden: `-03:00` y `+00:00` del mismo instante
        son dos textos que se ordenan al revés del tiempo.

        Una fecha suelta se toma desde el arranque de ese día en la hora de la
        Óptica -no en la del reloj de la máquina- que es lo que alguien quiere
        decir cuando escribe «desde el 1». Es la misma zona del negocio que ya
        decide de qué día es una venta; usar la del sistema haría que la misma
        fecha significara cosas distintas en dos computadoras.
        """
        if value is None:
            return utc_now().isoformat()
        if isinstance(value, str):
            texto = value.strip()
            if not texto:
                return utc_now().isoformat()
            value = (parse_business_date(texto) if len(texto) <= 10
                     else datetime.fromisoformat(texto))
        if isinstance(value, datetime):
            momento = value
        else:
            momento = datetime.combine(value, time.min, tzinfo=BUSINESS_TIMEZONE)
        if momento.tzinfo is None:
            momento = momento.replace(tzinfo=BUSINESS_TIMEZONE)
        return momento.astimezone(timezone.utc).replace(microsecond=0).isoformat()

    # -- comisión: la política ----------------------------------------------

    def definir_comision(
        self, *, user_id: str, amount: int, branch: str = "", job_type: str = "",
        effective_from: date | datetime | str | None = None, reason: str = "",
        token: str | None = None, updated_by: str | None = None,
    ) -> dict:
        """Define o cambia cuánto cobra una persona por trabajo.

        Nada viene sembrado: ni las personas ni los montos. Que el responsable
        con comisión cobre 5.000 y quien dirige la óptica no cobre nada son dos
        configuraciones que se cargan una vez sobre personas reales, y ninguna
        de las dos está escrita en este código.

        Cambiar no pisa: agrega una versión. Los trabajos que ya devengaron
        conservan su importe y ahora también la versión que lo explicaba, así
        que subir una tarifa no reescribe agosto.
        """
        quien = self._administradora(token=token, actor=updated_by)
        if int(amount) < 0:
            raise InvalidCashDayError("Una comisión no puede ser negativa.")
        persona = self._persona_de_politica(user_id, exigir_activa=True)
        sucursal = normalizar_sucursal(branch) if branch else ""
        tipo = self._tipo_de_politica(job_type)
        if tipo:
            self._tipo_valido(tipo)
        anterior = self.repository.service_commission_policy_history(
            user_id=user_id, branch=sucursal, job_type=tipo)
        # El motivo se exige al cambiar y no al cargar por primera vez. La
        # primera carga se explica sola -antes no había nada-; un cambio de
        # importe es lo que después alguien va a preguntar por qué se hizo.
        if anterior and not str(reason or "").strip():
            raise InvalidCashDayError(
                "Cambiar una comisión pide un motivo: queda en la historia.")
        return self.repository.record_service_commission_policy(
            user_id=user_id, amount=int(amount), branch=sucursal, job_type=tipo,
            active=True, effective_from=self._instante_de_vigencia(effective_from),
            reason=str(reason or "").strip(), created_by=quien,
            audit=dict(
                actor=quien,
                action=("COMMISSION_POLICY_UPDATED" if anterior
                        else "COMMISSION_POLICY_CREATED"),
                target_type="commission_policy", result="SUCCESS",
                details={"persona": persona["display_name"] or persona["username"],
                         "user_id": user_id, "sucursal": sucursal or "TODAS",
                         "tipo": tipo or "TODOS", "motivo": reason}),
        )

    def desactivar_comision(
        self, *, user_id: str, reason: str, branch: str = "", job_type: str = "",
        effective_from: date | datetime | str | None = None,
        token: str | None = None, updated_by: str | None = None,
    ) -> dict:
        """Apaga una política sin borrarla.

        Queda la fila que dice que estuvo activa, cuándo se apagó, quién y por
        qué. Borrarla dejaría a los devengos viejos explicados por una regla que
        la base ya no tiene.
        """
        return self._cambiar_vigencia(
            user_id=user_id, activa=False, reason=reason, branch=branch,
            job_type=job_type, effective_from=effective_from, token=token,
            updated_by=updated_by)

    def activar_comision(
        self, *, user_id: str, reason: str, branch: str = "", job_type: str = "",
        amount: int | None = None,
        effective_from: date | datetime | str | None = None,
        token: str | None = None, updated_by: str | None = None,
    ) -> dict:
        return self._cambiar_vigencia(
            user_id=user_id, activa=True, reason=reason, branch=branch,
            job_type=job_type, amount=amount, effective_from=effective_from,
            token=token, updated_by=updated_by)

    def _cambiar_vigencia(
        self, *, user_id: str, activa: bool, reason: str, branch: str,
        job_type: str, amount: int | None = None,
        effective_from: date | datetime | str | None = None,
        token: str | None = None, updated_by: str | None = None,
    ) -> dict:
        quien = self._administradora(token=token, actor=updated_by)
        if not str(reason or "").strip():
            raise InvalidCashDayError(
                "Activar o desactivar una comisión pide un motivo.")
        sucursal = normalizar_sucursal(branch) if branch else ""
        tipo = self._tipo_de_politica(job_type)
        versiones = self.repository.service_commission_policy_history(
            user_id=user_id, branch=sucursal, job_type=tipo)
        if not versiones:
            raise InvalidCashDayError(
                "No hay ninguna política cargada para ese alcance.")
        # Activar o desactivar no es un cambio de importe: se arrastra el que
        # había. Pedirlo de nuevo obligaría a la administradora a recordarlo, y
        # tipearlo mal convertiría una baja en un aumento silencioso.
        persona = self._persona_de_politica(user_id, exigir_activa=False)
        monto = int(versiones[0]["amount"] if amount is None else amount)
        return self.repository.record_service_commission_policy(
            user_id=user_id, amount=monto, branch=sucursal, job_type=tipo,
            active=activa, effective_from=self._instante_de_vigencia(effective_from),
            reason=str(reason).strip(), created_by=quien,
            audit=dict(
                actor=quien,
                action=("COMMISSION_POLICY_ACTIVATED" if activa
                        else "COMMISSION_POLICY_DEACTIVATED"),
                target_type="commission_policy", result="SUCCESS",
                details={"persona": persona["display_name"] or persona["username"],
                         "user_id": user_id, "sucursal": sucursal or "TODAS",
                         "tipo": tipo or "TODOS", "motivo": reason}),
        )

    def politicas_de_comision(self, *, token: str | None = None,
                              user_id: str | None = None) -> Sequence[dict]:
        """La política vigente de cada alcance, con el nombre de la persona.

        Es una consulta administrativa sensible -dice cuánto cobra cada una- y
        por eso pide el rol igual que cambiarla.
        """
        self._administradora(token=token, actor="consulta")
        nombres = self._nombres_de_personas()
        filas = []
        for fila in self.repository.list_service_commission_policy(user_id=user_id):
            item = dict(fila)
            item["display_name"] = nombres.get(fila["user_id"], fila["user_id"])
            filas.append(item)
        return filas

    def historial_de_comision(self, *, user_id: str, token: str | None = None,
                              branch: str | None = None,
                              job_type: str | None = None) -> Sequence[dict]:
        self._administradora(token=token, actor="consulta")
        return self.repository.service_commission_policy_history(
            user_id=user_id,
            branch=(normalizar_sucursal(branch) if branch else None),
            job_type=(self._tipo_de_politica(job_type) if job_type is not None else None))

    def _nombres_de_personas(self) -> dict:
        with self.repository._connection() as connection:
            return {fila["id"]: (fila["display_name"] or fila["username"])
                    for fila in connection.execute(
                        "SELECT id, display_name, username FROM admin_users")}

    def personas_para_comision(self) -> Sequence[dict]:
        """Las personas activas, para elegir en el panel. Sin lista cableada.

        Se ordena por el nombre que se ve y no por la columna `display_name`:
        quien no tiene uno cargado se muestra por su usuario, y ordenar por la
        columna cruda lo mandaba al principio de la lista por ser NULL, en un
        lugar que no se corresponde con nada de lo que está en pantalla.
        """
        with self.repository._connection() as connection:
            return [dict(id=fila["id"], display_name=fila["visible"])
                    for fila in connection.execute(
                        "SELECT id, COALESCE(NULLIF(TRIM(display_name), ''), username)"
                        " AS visible FROM admin_users WHERE active = 1"
                        " ORDER BY visible COLLATE NOCASE")]

    # -- comisión: lo devengado ---------------------------------------------

    def politica_vigente_de(self, *, user_id: str | None, job_type: str,
                            branch: str = "", at: datetime | None = None) -> dict | None:
        return self.repository.service_commission_policy_vigente(
            user_id=user_id, branch=branch, job_type=job_type,
            at=self._instante_de_vigencia(at))

    def comision_de(self, *, user_id: str | None, job_type: str,
                    branch: str = "", at: datetime | None = None) -> int:
        """Cuánto le corresponde. Cero cuando no hay política.

        Devuelve un número porque casi todas las preguntas son «cuánto», pero
        cero es ambiguo -no hay política, o la política dice cero- y por eso el
        devengo usa `politica_vigente_de`, que distingue las dos.
        """
        politica = self.politica_vigente_de(
            user_id=user_id, job_type=job_type, branch=branch, at=at)
        return int(politica["amount"]) if politica else 0

    def comisiones_del_trabajo(self, job_id: str) -> Sequence[dict]:
        return self.repository.list_service_commissions(job_id=job_id)

    def saldo_de_comisiones(self) -> Sequence[dict]:
        return self.repository.service_commission_balance()

    def _consecuencias_de_comision(
        self, trabajo: ServiceJob, *, anterior: JobStatus, actor: str,
        occurred_at: datetime, reason: str,
    ) -> tuple[ServiceJob, list[dict], list[dict]]:
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
        return trabajo, [], []

    def _devengar(self, trabajo: ServiceJob, *, actor: str,
                  occurred_at: datetime) -> tuple[ServiceJob, list[dict], list[dict]]:
        """La consecuencia económica de haber terminado el trabajo.

        La política se resuelve al momento del devengo y la versión que aplicó
        queda pegada al asiento. Eso es lo que hace que subir la tarifa mañana
        no cambie lo de hoy: lo de hoy no se recalcula, se lee.

        Sin política no se inventa nada. No hay comisión por defecto, y tampoco
        se anota una deuda de cero: se anota que este trabajo no devengó y por
        qué, que es distinto y es lo que alguien tiene que poder ver.
        """
        base = dict(target_type="service_job", target_id=trabajo.id, actor=actor)
        contexto = {"trabajo": trabajo.reference,
                    "responsable": trabajo.responsible or "SIN ASIGNAR",
                    "user_id": trabajo.responsible_user_id,
                    "sucursal": trabajo.branch, "tipo": trabajo.job_type}
        politica = self.politica_vigente_de(
            user_id=trabajo.responsible_user_id, job_type=trabajo.job_type,
            branch=trabajo.branch, at=occurred_at)
        if politica is None:
            return trabajo, [], [dict(base, action="COMMISSION_SKIPPED",
                                      result="SIN_POLITICA", details=contexto)]
        monto = int(politica["amount"])
        if monto <= 0:
            return trabajo, [], [dict(
                base, action="COMMISSION_SKIPPED", result="IMPORTE_CERO",
                details=dict(contexto, politica=politica["id"]))]
        hecho = JobHistoryEntry(
            event_type=JobEvent.COMMISSION_ACCRUED, actor=actor,
            occurred_at=occurred_at,
            detail={"beneficiario": trabajo.responsible, "importe": monto,
                    "tipo": trabajo.job_type, "politica": politica["id"]},
        )
        asiento = dict(
            job_id=trabajo.id, event_id=hecho.id,
            user_id=trabajo.responsible_user_id, beneficiary=trabajo.responsible,
            job_type=trabajo.job_type, kind="DEVENGO", amount=monto,
            policy_id=politica["id"],
            note=f"Trabajo {trabajo.reference} {ETIQUETA_ESTADO[JobStatus.READY]}")
        auditoria = dict(base, action="COMMISSION_ACCRUED", result="SUCCESS",
                         details=dict(contexto, importe=monto,
                                      politica=politica["id"],
                                      evento=hecho.id))
        return trabajo._con_hecho(hecho), [asiento], [auditoria]

    def _compensar_todo(self, trabajo: ServiceJob, *, actor: str,
                        occurred_at: datetime, reason: str,
                        ) -> tuple[ServiceJob, list[dict], list[dict]]:
        """Anular un trabajo deshace su consecuencia económica.

        No borra el devengo: asienta su contrario. Así el histórico sigue
        diciendo que se devengó y que después se compensó, que es lo que pasó.

        La compensación hereda la política del devengo que revierte, no la
        vigente hoy: revierte aquel hecho, no el precio actual.
        """
        asientos = self.repository.list_service_commissions(job_id=trabajo.id)
        devengos = [item for item in asientos if item["kind"] == "DEVENGO"]
        compensados = {item["compensates_id"] for item in asientos
                       if item["kind"] == "COMPENSACION"}
        actualizado, asientos, auditorias = trabajo, [], []
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
                policy_id=devengo.get("policy_id"),
                note=f"Trabajo {trabajo.reference} anulado: {reason}"))
            auditorias.append(dict(
                actor=actor, action="COMMISSION_COMPENSATED",
                target_type="service_job", target_id=trabajo.id, result="SUCCESS",
                details={"trabajo": trabajo.reference,
                         "beneficiario": devengo["beneficiary"],
                         "importe": -int(devengo["amount"]),
                         "compensa": devengo["id"], "motivo": reason}))
        return actualizado, asientos, auditorias

    # -- comisión: el reporte -----------------------------------------------

    def reporte_de_comisiones(
        self, *, token: str | None = None, date_from: date | str | None = None,
        date_to: date | str | None = None, branch: str | None = None,
        responsible: str | None = None, user_id: str | None = None,
        estado: str | None = None,
    ) -> dict:
        """Cuánto generó cada persona, y por qué. Devengado, compensado y neto.

        No mezcla el 1% comercial y no podría: esa comisión no vive en esta base
        -es de BC Gestión, sobre ventas, en otro archivo y con otra regla- así
        que acá no hay ni siquiera una tabla de dónde traerla por accidente.

        Los totales se suman sobre las mismas filas que se muestran, no con una
        consulta aparte. Un total que no cuadra con lo que está arriba es peor
        que no tener total.
        """
        self._administradora(token=token, actor="consulta")
        if responsible and not user_id:
            _, user_id = self._usuario_por_nombre(responsible, exigir_activa=False)
        if estado and estado not in ("DEVENGADA", "COMPENSADA"):
            raise InvalidCashDayError(f"Estado desconocido: {estado!r}.")
        desde = self._fecha(date_from)
        hasta = self._fecha(date_to)
        sucursal = normalizar_sucursal(branch) if branch else None
        filas = self.repository.service_commission_report_rows(
            date_from=desde, date_to=hasta, branch=sucursal, user_id=user_id,
            estado=estado)
        sin_politica = self.repository.service_jobs_sin_comision(
            date_from=desde, date_to=hasta, branch=sucursal)
        return {
            "filas": filas,
            "sin_politica": sin_politica,
            "totales": {
                "trabajos": len(filas),
                "bruto": sum(int(fila["accrued_amount"]) for fila in filas),
                "compensado": sum(int(fila["compensated_amount"]) for fila in filas),
                "neto": sum(int(fila["net_amount"]) for fila in filas),
                "sin_politica": len(sin_politica),
            },
        }

    @staticmethod
    def _fecha(value: date | str | None) -> str | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return parse_business_date(value).isoformat()

    def comision_del_trabajo(self, job_id: str) -> dict:
        """Lo que hay que poder ver parado sobre una compostura.

        Si generó comisión, quién, cuánto, con qué política, en qué estado y si
        hubo compensación. No pide rol: es la consecuencia del propio trabajo
        que la operadora tiene delante, no el sueldo de las demás.
        """
        trabajo = self._cargar(job_id)
        asientos = self.repository.list_service_commissions(job_id=job_id)
        devengos = [item for item in asientos if item["kind"] == "DEVENGO"]
        compensaciones = {item["compensates_id"]: item for item in asientos
                          if item["kind"] == "COMPENSACION"}
        detalle = []
        for devengo in devengos:
            compensacion = compensaciones.get(devengo["id"])
            detalle.append({
                "id": devengo["id"],
                "beneficiario": devengo["beneficiary"],
                "user_id": devengo["user_id"],
                "importe": int(devengo["amount"]),
                "compensado": int(compensacion["amount"]) if compensacion else 0,
                "neto": int(devengo["amount"]) + (
                    int(compensacion["amount"]) if compensacion else 0),
                "estado": "COMPENSADA" if compensacion else "DEVENGADA",
                "motivo_compensacion": compensacion["note"] if compensacion else "",
                "politica": self.repository.service_commission_policy_version(
                    devengo.get("policy_id")),
                "evento": devengo["event_id"],
                "fecha": devengo["created_at"],
            })
        return {
            "trabajo": trabajo.reference,
            "job_id": trabajo.id,
            "responsable": trabajo.responsible or "SIN ASIGNAR",
            "genero_comision": bool(detalle),
            "asientos": detalle,
            "neto": sum(item["neto"] for item in detalle),
        }

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
