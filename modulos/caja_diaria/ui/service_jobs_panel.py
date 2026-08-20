"""La pestaña «Composturas» de BC Caja.

Una lista y seis botones. La operadora entra veinte veces por día a hacer dos
cosas: anotar un trabajo que acaba de entrar, y encontrar los que están listos
para que alguien los retire. Por eso la vista que abre por defecto es
«Listos para entregar» y no una hoja en blanco con todo.

Vive en su propio módulo y no adentro de `CajaDiaria.py` por la misma razón que
FactuFácil: esa pantalla ya tiene seis mil líneas.

Nada de lo que hay acá calcula reglas. El estado siguiente, si una transición es
válida, si exige motivo y si devenga comisión lo decide el servicio; la pantalla
pregunta y muestra. Cuando una acción no se puede, no se esconde el botón: se
dice por qué.
"""

from __future__ import annotations

from datetime import date

import customtkinter as ctk
from tkinter import ttk, messagebox, simpledialog

from ..application.service_jobs import (
    ETIQUETA_VISTA,
    VISTAS,
    VISTA_ENTREGADOS,
    VISTA_EN_TALLER,
    VISTA_LISTOS,
    VISTA_PENDIENTES,
    VISTA_TODOS,
)
from ..domain.errors import CashDayError
from ..domain.service_jobs import ETIQUETA_ESTADO, JobStatus

AZUL = "#0F5FB9"
VERDE = "#1B7F4B"
AMBAR = "#B45309"
ROJO = "#A32626"
GRIS = "#5B6B7F"
BORDE = "#D6E1EE"

#: Las columnas, en el orden en que se lee una fila del mostrador: primero el
#: número que se le canta al cliente, después de quién es y cómo llamarlo, y
#: recién al final quién lo hace y en qué anda.
COLUMNAS = (
    ("numero", "N°", 80, "w"),
    ("cliente", "Cliente", 200, "w"),
    ("telefono", "Teléfono", 110, "w"),
    ("trabajo", "Trabajo", 260, "w"),
    ("tipo", "Tipo", 110, "w"),
    ("responsable", "Responsable", 130, "w"),
    ("estado", "Estado", 110, "w"),
    ("fecha", "Recibido", 95, "center"),
    ("prevista", "Prevista", 95, "center"),
    ("cobro", "Cobro", 120, "w"),
)

#: Mismos colores de estado que Pedidos. Que «LISTO» sea del mismo azul en las
#: dos pantallas no es cosmética: es lo que permite leerlas sin releerlas.
COLOR_ESTADO = {
    "RECIBIDO": ("#FFF1CC", "#8A4B08"),
    "EN_TALLER": ("#EDE7F6", "#4A2E86"),
    "LISTO": ("#DCEEFF", "#174A7E"),
    "ENTREGADO": ("#DDF5E8", "#17633A"),
    "ANULADO": ("#FDECEC", "#A32626"),
}


class PanelComposturas(ctk.CTkFrame):
    """Construye la pestaña y la mantiene al día.

    Recibe el servicio ya armado y dos funciones: `actor`, que dice quién está
    operando ahora -y se consulta cada vez, porque la operadora puede cambiar
    sin cerrar la ventana-, y `sucursal`, que dice de qué caja es esta pantalla.
    Ninguna de las dos se pregunta en un formulario: ya están resueltas.
    """

    def __init__(self, master, servicio, *, actor, sucursal=None, perfil=None):
        super().__init__(master, fg_color="transparent")
        self._servicio = servicio
        self._actor = actor if callable(actor) else (lambda: str(actor or ""))
        self._sucursal = sucursal if callable(sucursal) else (lambda: sucursal)
        self._filas: dict[str, object] = {}
        tamano = (perfil or {}).get("fuente_label", 12)
        self._fuente = ctk.CTkFont(size=tamano)
        self._fuente_negrita = ctk.CTkFont(size=tamano, weight="bold")
        self.pack(fill="both", expand=True)
        self._construir_cabecera()
        self._construir_vistas()
        self._construir_tabla()
        self._construir_acciones()
        self.refrescar()

    # -- construcción -------------------------------------------------------

    def _construir_cabecera(self):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(barra, text="Composturas y trabajos de taller",
                     font=self._fuente_negrita, text_color=AZUL).pack(side="left")
        self._resumen = ctk.CTkLabel(barra, text="", font=self._fuente,
                                     text_color=GRIS)
        self._resumen.pack(side="left", padx=(14, 0))
        ctk.CTkButton(barra, text="+ Nuevo trabajo", width=150, height=30,
                      fg_color=AZUL, font=self._fuente_negrita,
                      command=self.nuevo_trabajo).pack(side="right")

    def _construir_vistas(self):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", padx=10, pady=(0, 6))
        # Arranca en LISTOS: es la pregunta que el mostrador hace todo el día.
        self._vista = ctk.StringVar(value=VISTA_LISTOS)
        self._botones_vista = {}
        for vista in VISTAS:
            boton = ctk.CTkButton(
                barra, text=ETIQUETA_VISTA[vista], width=140, height=28,
                font=self._fuente, command=lambda v=vista: self._cambiar_vista(v))
            boton.pack(side="left", padx=(0, 6))
            self._botones_vista[vista] = boton
        self._solo_mi_sucursal = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(barra, text="Solo mi sucursal", variable=self._solo_mi_sucursal,
                        font=self._fuente, command=self.refrescar,
                        width=20).pack(side="right")

    def _construir_tabla(self):
        marco = ctk.CTkFrame(self, fg_color="#FFFFFF")
        marco.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        marco.grid_rowconfigure(0, weight=1)
        marco.grid_columnconfigure(0, weight=1)
        self._tabla = ttk.Treeview(
            marco, columns=tuple(c for c, _t, _a, _al in COLUMNAS),
            show="headings", style="Caja.Treeview")
        for clave, titulo, ancho, anchor in COLUMNAS:
            self._tabla.heading(clave, text=titulo, anchor=anchor)
            self._tabla.column(clave, width=ancho, minwidth=ancho, anchor=anchor,
                               stretch=clave == "trabajo")
        for estado, (fondo, texto) in COLOR_ESTADO.items():
            self._tabla.tag_configure(f"estado_{estado}", background=fondo,
                                      foreground=texto)
        scroll = ttk.Scrollbar(marco, orient="vertical", command=self._tabla.yview)
        self._tabla.configure(yscrollcommand=scroll.set)
        self._tabla.grid(row=0, column=0, sticky="nsew", padx=(5, 0), pady=5)
        scroll.grid(row=0, column=1, sticky="ns", padx=(0, 5), pady=5)
        self._tabla.bind("<<TreeviewSelect>>", lambda _e: self._ajustar_acciones())
        self._vacio = ctk.CTkLabel(marco, text="", font=self._fuente,
                                   text_color=GRIS)

    def _construir_acciones(self):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", padx=10, pady=(0, 10))
        self._acciones = {}
        for clave, texto, color, comando in (
            ("taller", "Enviar a taller", AMBAR, self.enviar_a_taller),
            ("listo", "Marcar listo", VERDE, self.marcar_listo),
            ("entregar", "Entregar", AZUL, self.entregar),
            ("responsable", "Responsable", GRIS, self.cambiar_responsable),
            ("historial", "Ver historial", GRIS, self.ver_historial),
            ("anular", "Anular", ROJO, self.anular),
        ):
            boton = ctk.CTkButton(barra, text=texto, width=140, height=32,
                                  fg_color=color, font=self._fuente_negrita,
                                  command=comando, state="disabled")
            boton.pack(side="left", padx=(0, 6))
            self._acciones[clave] = boton
        self._aviso = ctk.CTkLabel(barra, text="", font=self._fuente, text_color=GRIS)
        self._aviso.pack(side="left", padx=(12, 0))

    # -- estado de la pantalla ---------------------------------------------

    def _cambiar_vista(self, vista):
        self._vista.set(vista)
        self.refrescar()

    def _sucursal_activa(self):
        return self._sucursal() if self._solo_mi_sucursal.get() else None

    def refrescar(self):
        for vista, boton in self._botones_vista.items():
            activo = vista == self._vista.get()
            boton.configure(fg_color=AZUL if activo else "#FFFFFF",
                            text_color="#FFFFFF" if activo else AZUL,
                            border_width=0 if activo else 1, border_color=BORDE)
        for item in self._tabla.get_children():
            self._tabla.delete(item)
        self._filas.clear()
        try:
            filas = self._servicio.tablero(vista=self._vista.get(),
                                           branch=self._sucursal_activa())
            resumen = self._servicio.resumen(branch=self._sucursal_activa())
        except CashDayError as error:
            self._avisar(str(error), ROJO)
            return
        for fila in filas:
            self._filas[fila.id] = fila
            self._tabla.insert(
                "", "end", iid=fila.id, tags=(f"estado_{fila.job.status.value}",),
                values=(fila.reference, fila.customer, fila.phone or "—",
                        fila.work, fila.job_type.capitalize(), fila.responsible,
                        fila.status_label, fila.received_label,
                        fila.promised_label or "—", fila.charge_label or "—"))
        self._resumen.configure(text=(
            f"{resumen['RECIBIDO']} recibidos · {resumen['EN_TALLER']} en taller · "
            f"{resumen['LISTO']} listos · {resumen['ENTREGADO']} entregados"))
        if filas:
            self._vacio.place_forget()
        else:
            self._vacio.configure(
                text=f"No hay trabajos en «{ETIQUETA_VISTA[self._vista.get()]}».")
            self._vacio.place(relx=0.5, rely=0.5, anchor="center")
        self._ajustar_acciones()

    def _seleccion(self):
        elegidos = self._tabla.selection()
        return self._filas.get(elegidos[0]) if elegidos else None

    def _ajustar_acciones(self):
        """Habilita solo lo que el trabajo elegido admite de verdad.

        El permitido sale de `allowed_transitions()`, que es el dominio: si un
        día cambia una regla, la pantalla la sigue sola y no queda ofreciendo un
        botón que después falla.
        """
        fila = self._seleccion()
        if fila is None:
            for boton in self._acciones.values():
                boton.configure(state="disabled")
            self._avisar("", GRIS)
            return
        permitidos = set(fila.job.allowed_transitions())
        self._acciones["taller"].configure(
            state="normal" if JobStatus.IN_WORKSHOP in permitidos else "disabled")
        self._acciones["listo"].configure(
            state="normal" if JobStatus.READY in permitidos else "disabled")
        self._acciones["entregar"].configure(
            state="normal" if JobStatus.DELIVERED in permitidos else "disabled")
        self._acciones["anular"].configure(
            state="normal" if JobStatus.VOIDED in permitidos else "disabled")
        self._acciones["responsable"].configure(
            state="disabled" if fila.job.status is JobStatus.VOIDED else "normal")
        self._acciones["historial"].configure(state="normal")
        # Enviar a taller desde LISTO o ENTREGADO no es enviar: es reabrir, y
        # eso se dice antes de apretar, no después.
        if fila.job.status in (JobStatus.READY, JobStatus.DELIVERED):
            self._acciones["taller"].configure(text="Reabrir")
        else:
            self._acciones["taller"].configure(text="Enviar a taller")
        self._avisar(f"{fila.reference} · {fila.customer} · {fila.status_label}", GRIS)

    def _avisar(self, texto, color):
        self._aviso.configure(text=texto, text_color=color)

    # -- acciones -----------------------------------------------------------

    def nuevo_trabajo(self):
        dialogo = DialogoNuevoTrabajo(self, self._servicio, actor=self._actor(),
                                      sucursal=self._sucursal(), fuente=self._fuente)
        self.wait_window(dialogo)
        if dialogo.creado is not None:
            self._vista.set(VISTA_PENDIENTES)
            self.refrescar()
            self._avisar(f"Trabajo {dialogo.creado.reference} registrado.", VERDE)

    def _ejecutar(self, accion, *args, **kwargs):
        fila = self._seleccion()
        if fila is None:
            return
        try:
            accion(fila.id, *args, actor=self._actor(), **kwargs)
        except CashDayError as error:
            messagebox.showwarning("No se puede", str(error), parent=self)
            return
        self.refrescar()

    def enviar_a_taller(self):
        fila = self._seleccion()
        if fila is None:
            return
        if fila.job.status in (JobStatus.READY, JobStatus.DELIVERED):
            motivo = simpledialog.askstring(
                "Reabrir trabajo",
                f"{fila.reference} está {fila.status_label}. ¿Por qué vuelve al taller?",
                parent=self)
            if not motivo:
                return
            self._ejecutar(self._servicio.reabrir, reason=motivo)
            return
        self._ejecutar(self._servicio.enviar_a_taller)

    def marcar_listo(self):
        self._ejecutar(self._servicio.marcar_listo)

    def entregar(self):
        self._ejecutar(self._servicio.entregar)

    def anular(self):
        fila = self._seleccion()
        if fila is None:
            return
        motivo = simpledialog.askstring(
            "Anular trabajo", f"¿Por qué se anula {fila.reference}?", parent=self)
        if not motivo:
            return
        self._ejecutar(self._servicio.anular, reason=motivo)

    def cambiar_responsable(self):
        fila = self._seleccion()
        if fila is None:
            return
        dialogo = DialogoResponsable(self, self._servicio, referencia=fila.reference,
                                     actual=fila.job.responsible, fuente=self._fuente)
        self.wait_window(dialogo)
        if dialogo.elegido:
            self._ejecutar(self._servicio.asignar_responsable, dialogo.elegido)

    def ver_historial(self):
        fila = self._seleccion()
        if fila is None:
            return
        lineas = []
        for hecho in self._servicio.historial(fila.id):
            cuando = hecho.occurred_at.astimezone().strftime("%d/%m/%Y %H:%M")
            paso = ""
            if hecho.from_status and hecho.to_status:
                paso = (f"  {ETIQUETA_ESTADO[hecho.from_status]} → "
                        f"{ETIQUETA_ESTADO[hecho.to_status]}")
            motivo = f"\n      Motivo: {hecho.reason}" if hecho.reason else ""
            lineas.append(f"{cuando}  {hecho.event_type.value}{paso}"
                          f"\n      Por: {hecho.actor}{motivo}")
        lineas.extend(self._lineas_de_comision(fila.id))
        messagebox.showinfo(f"Historial de {fila.reference}",
                            "\n\n".join(lineas) or "Sin hechos registrados.",
                            parent=self)

    def _lineas_de_comision(self, job_id):
        """V1-021: qué comisión salió de este trabajo, y por qué ese importe.

        Va acá y no en un botón aparte porque es una consecuencia de este
        trabajo, no un tema nuevo: quien abre el historial está preguntando
        justamente qué pasó con esta compostura. No pide rol -es la comisión de
        este trabajo, no el sueldo de las demás- y por eso no muestra ni totales
        ni lo de otras personas.
        """
        try:
            resumen = self._servicio.comision_del_trabajo(job_id)
        except Exception:
            # El historial operativo es lo que se vino a ver. Si la parte
            # económica falla, se muestra lo que sí se pudo leer en vez de
            # dejar la pantalla sin nada.
            return []
        if not resumen["genero_comision"]:
            return ["COMISIÓN\n      No generó comisión de compostura."]
        lineas = ["COMISIÓN"]
        for asiento in resumen["asientos"]:
            politica = asiento["politica"]
            origen = ("política sin registrar" if not politica else
                      f"política de {politica['amount']:,}".replace(",", ".")
                      + f" vigente desde {str(politica['effective_from'])[:10]}")
            lineas.append(
                f"      {asiento['beneficiario']}: {asiento['importe']:,}"
                .replace(",", ".")
                + f"  ({asiento['estado']})\n      Por: {origen}"
                + (f"\n      Compensada: {asiento['compensado']:,}"
                   .replace(",", ".") + f" — {asiento['motivo_compensacion']}"
                   if asiento["compensado"] else ""))
        lineas.append(f"      NETO: {resumen['neto']:,}".replace(",", "."))
        return ["\n".join(lineas)]


class DialogoNuevoTrabajo(ctk.CTkToplevel):
    """Lo mínimo para anotar un trabajo sin frenar la atención.

    No pide sucursal ni quién recibe: las dos salen de la caja y de la sesión.
    Volver a preguntarlas sería pedirle a la operadora que confirme lo que el
    sistema ya sabe, y abrir la puerta a que se conteste distinto.
    """

    def __init__(self, master, servicio, *, actor, sucursal, fuente):
        super().__init__(master)
        self.title("Nuevo trabajo")
        self.geometry("520x520")
        self.transient(master)
        self.grab_set()
        self._servicio = servicio
        self._actor = actor
        self._sucursal = sucursal
        self.creado = None
        self._campos = {}

        ctk.CTkLabel(self, text=f"Recibe: {actor}  ·  Sucursal: {sucursal or '—'}",
                     font=fuente, text_color=GRIS).pack(anchor="w", padx=16, pady=(14, 8))

        for clave, titulo in (("customer_name", "Cliente *"),
                              ("customer_phone", "Teléfono"),
                              ("description", "Trabajo a realizar *"),
                              ("observations", "Observación")):
            ctk.CTkLabel(self, text=titulo, font=fuente).pack(anchor="w", padx=16)
            campo = ctk.CTkEntry(self, font=fuente, height=32)
            campo.pack(fill="x", padx=16, pady=(0, 8))
            self._campos[clave] = campo

        ctk.CTkLabel(self, text="Tipo de trabajo", font=fuente).pack(anchor="w", padx=16)
        tipos = servicio.tipos_de_trabajo()
        self._etiquetas = {tipo["label"]: tipo["code"] for tipo in tipos}
        self._tipo = ctk.CTkOptionMenu(
            self, values=list(self._etiquetas) or ["Compostura"], font=fuente)
        self._tipo.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(self, text="Responsable del trabajo", font=fuente).pack(
            anchor="w", padx=16)
        responsables = list(servicio.responsables_disponibles())
        # «Sin asignar» es una opción real: muchas veces se anota el trabajo y
        # recién después se decide quién lo hace.
        self._responsable = ctk.CTkOptionMenu(
            self, values=["Sin asignar"] + responsables, font=fuente)
        self._responsable.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(self, text="Fecha prevista (dd/mm/aaaa)", font=fuente).pack(
            anchor="w", padx=16)
        self._prevista = ctk.CTkEntry(self, font=fuente, height=32)
        self._prevista.pack(fill="x", padx=16, pady=(0, 12))

        self._error = ctk.CTkLabel(self, text="", font=fuente, text_color=ROJO)
        self._error.pack(anchor="w", padx=16)

        acciones = ctk.CTkFrame(self, fg_color="transparent")
        acciones.pack(fill="x", padx=16, pady=12)
        ctk.CTkButton(acciones, text="Registrar", fg_color=AZUL, font=fuente,
                      command=self._guardar).pack(side="right")
        ctk.CTkButton(acciones, text="Cancelar", fg_color=GRIS, font=fuente,
                      command=self.destroy).pack(side="right", padx=(0, 8))
        self._campos["customer_name"].focus_set()

    def _guardar(self):
        responsable = self._responsable.get()
        try:
            self.creado = self._servicio.crear_trabajo(
                customer_name=self._campos["customer_name"].get(),
                customer_phone=self._campos["customer_phone"].get(),
                description=self._campos["description"].get(),
                observations=self._campos["observations"].get(),
                job_type=self._etiquetas.get(self._tipo.get(), "COMPOSTURA"),
                responsible="" if responsable == "Sin asignar" else responsable,
                promised_date=self._prevista.get().strip() or None,
                actor=self._actor, branch=self._sucursal,
            )
        except (CashDayError, ValueError) as error:
            self._error.configure(text=str(error))
            return
        self.destroy()


class DialogoResponsable(ctk.CTkToplevel):
    """Elige responsable del catálogo real. No hay lista escrita a mano."""

    def __init__(self, master, servicio, *, referencia, actual, fuente):
        super().__init__(master)
        self.title("Responsable del trabajo")
        self.geometry("380x210")
        self.transient(master)
        self.grab_set()
        self.elegido = None
        ctk.CTkLabel(self, text=f"Trabajo {referencia}", font=fuente).pack(
            anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(self, text=f"Ahora: {actual or 'sin asignar'}", font=fuente,
                     text_color=GRIS).pack(anchor="w", padx=16, pady=(0, 10))
        opciones = list(servicio.responsables_disponibles()) or ["Sin personas cargadas"]
        self._menu = ctk.CTkOptionMenu(self, values=opciones, font=fuente)
        self._menu.pack(fill="x", padx=16)
        acciones = ctk.CTkFrame(self, fg_color="transparent")
        acciones.pack(fill="x", padx=16, pady=16)
        ctk.CTkButton(acciones, text="Asignar", fg_color=AZUL, font=fuente,
                      command=self._elegir).pack(side="right")
        ctk.CTkButton(acciones, text="Cancelar", fg_color=GRIS, font=fuente,
                      command=self.destroy).pack(side="right", padx=(0, 8))

    def _elegir(self):
        self.elegido = self._menu.get()
        self.destroy()


def construir_panel_composturas(master, servicio, *, actor, sucursal=None, perfil=None):
    return PanelComposturas(master, servicio, actor=actor, sucursal=sucursal,
                            perfil=perfil)
