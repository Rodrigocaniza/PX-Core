"""La sección «Comisiones de composturas» del panel de administración.

Cinco preguntas y nada más, que son las que el administrador hace de verdad:
a quién, cuánto, desde cuándo, cuánto generó y por qué. No es un módulo
contable: no liquida, no paga, no arma recibos. Esas son otras preguntas y hoy
no tienen respuesta en el negocio, así que inventarles pantalla sería inventar
un flujo que nadie usa.

Vive en su propio módulo y no adentro de `CajaDiaria.py` por la misma razón que
Composturas y FactuFácil: esa pantalla ya tiene seis mil líneas.

Nada de lo que hay acá autoriza nada. La pantalla no decide quién puede cambiar
una tarifa: se lo pregunta al servicio en cada llamada, con el token de la
sesión. Esconder la pestaña no impide llamar al método, así que la pestaña no
es la protección: es apenas la puerta por la que se entra.
"""

from __future__ import annotations

from datetime import date

import customtkinter as ctk
from tkinter import ttk, messagebox

from ..domain.errors import CashDayError
from ..domain.service_jobs import SUCURSALES

AZUL = "#0F5FB9"
VERDE = "#1B7F4B"
AMBAR = "#B45309"
GRIS = "#5B6B7F"
BORDE = "#D6E1EE"

TODAS = "Todas"

#: La política, leída como se la piensa: de quién es, dónde y para qué aplica,
#: cuánto, desde cuándo y si está prendida.
COLUMNAS_POLITICA = (
    ("persona", "Persona", 200, "w"),
    ("sucursal", "Sucursal", 110, "w"),
    ("tipo", "Tipo de trabajo", 140, "w"),
    ("importe", "Por trabajo", 120, "e"),
    ("desde", "Rige desde", 110, "center"),
    ("estado", "Estado", 100, "w"),
    ("actor", "Definida por", 130, "w"),
)

#: El reporte. El importe original, lo que se compensó y el neto van juntos y
#: en ese orden: leer el neto sin ver de dónde salió es lo que hace que después
#: nadie pueda explicar un número.
COLUMNAS_REPORTE = (
    ("fecha", "Fecha", 95, "center"),
    ("trabajo", "N°", 80, "w"),
    ("cliente", "Cliente", 180, "w"),
    ("responsable", "Responsable", 140, "w"),
    ("sucursal", "Sucursal", 100, "w"),
    ("bruto", "Devengado", 110, "e"),
    ("compensado", "Compensado", 110, "e"),
    ("neto", "Neto", 110, "e"),
    ("estado", "Estado", 110, "w"),
)


def _guaranies(valor) -> str:
    return f"{int(valor):,}".replace(",", ".")


def _dia(iso: str | None) -> str:
    """La fecha de un instante ISO, sin la hora. La hora no aporta nada acá."""
    return str(iso or "")[:10]


class PanelComisiones(ctk.CTkFrame):
    """Política arriba, lo generado abajo.

    Están en la misma pantalla y no en dos pestañas porque son la misma
    conversación: se define una tarifa para mirar qué produjo, y se mira lo que
    produjo para decidir si la tarifa sigue estando bien. Separarlas obligaría a
    ir y volver para responder una sola pregunta.
    """

    def __init__(self, master, servicio, *, token, ventana=None):
        super().__init__(master, fg_color="transparent")
        self.servicio = servicio
        self.token = token
        self.ventana = ventana or master
        self._politicas: dict[str, dict] = {}
        self._personas: list[dict] = []
        self._construir()
        self.refrescar()

    # -- armado -------------------------------------------------------------

    def _construir(self) -> None:
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(barra, text="Comisión por compostura", text_color=AZUL,
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        self.aviso = ctk.CTkLabel(barra, text="", text_color=VERDE,
                                  font=ctk.CTkFont(size=12, weight="bold"))
        self.aviso.pack(side="right", padx=8)

        ctk.CTkLabel(
            self, justify="left", text_color=GRIS, anchor="w",
            text=("Es un importe fijo por trabajo hecho, y no tiene nada que ver "
                  "con la comisión del 1% sobre ventas: son dos cosas distintas "
                  "y se calculan aparte."),
        ).pack(fill="x", padx=14, pady=(0, 6))

        self.tabla = ttk.Treeview(
            self, columns=[clave for clave, *_ in COLUMNAS_POLITICA],
            show="headings", selectmode="browse", height=7)
        for clave, titulo, ancho, anclaje in COLUMNAS_POLITICA:
            self.tabla.heading(clave, text=titulo)
            self.tabla.column(clave, width=ancho, anchor=anclaje)
        self.tabla.pack(fill="x", padx=12, pady=4)
        self.tabla.tag_configure("inactiva", foreground="#8A97A6")

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(fill="x", padx=12, pady=(2, 10))
        ctk.CTkButton(botones, text="Nueva política",
                      command=self._nueva).pack(side="left")
        for texto, accion, color in (
                ("Editar", self._editar, AZUL),
                ("Activar / desactivar", self._alternar, AMBAR),
                ("Ver historial", self._historial, AZUL)):
            ctk.CTkButton(botones, text=texto, command=accion, fg_color="#FFFFFF",
                          text_color=color, border_width=1, border_color=BORDE,
                          hover_color="#EAF3FF").pack(side="left", padx=8)

        self._construir_reporte()

    def _construir_reporte(self) -> None:
        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.pack(fill="x", padx=12, pady=(6, 2))
        ctk.CTkLabel(cabecera, text="Lo que se generó", text_color=AZUL,
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        filtros = ctk.CTkFrame(self, fg_color="transparent")
        filtros.pack(fill="x", padx=12, pady=2)
        self.filtros = {}
        hoy = date.today()
        for clave, etiqueta, valor in (
                ("desde", "Desde", hoy.replace(day=1).strftime("%d/%m/%Y")),
                ("hasta", "Hasta", hoy.strftime("%d/%m/%Y"))):
            ctk.CTkLabel(filtros, text=etiqueta, text_color=GRIS).pack(side="left", padx=(0, 4))
            campo = ctk.CTkEntry(filtros, width=100)
            campo.insert(0, valor)
            campo.pack(side="left", padx=(0, 10))
            self.filtros[clave] = campo
        ctk.CTkLabel(filtros, text="Sucursal", text_color=GRIS).pack(side="left", padx=(0, 4))
        self.filtro_sucursal = ctk.CTkComboBox(
            filtros, width=120, values=[TODAS, *SUCURSALES])
        self.filtro_sucursal.set(TODAS)
        self.filtro_sucursal.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(filtros, text="Responsable", text_color=GRIS).pack(side="left", padx=(0, 4))
        self.filtro_persona = ctk.CTkComboBox(filtros, width=150, values=[TODAS])
        self.filtro_persona.set(TODAS)
        self.filtro_persona.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(filtros, text="Estado", text_color=GRIS).pack(side="left", padx=(0, 4))
        self.filtro_estado = ctk.CTkComboBox(
            filtros, width=130, values=[TODAS, "Devengadas", "Compensadas"])
        self.filtro_estado.set(TODAS)
        self.filtro_estado.pack(side="left", padx=(0, 10))
        ctk.CTkButton(filtros, text="Consultar", width=110,
                      command=self.consultar).pack(side="left")

        self.reporte = ttk.Treeview(
            self, columns=[clave for clave, *_ in COLUMNAS_REPORTE],
            show="headings", selectmode="browse", height=8)
        for clave, titulo, ancho, anclaje in COLUMNAS_REPORTE:
            self.reporte.heading(clave, text=titulo)
            self.reporte.column(clave, width=ancho, anchor=anclaje)
        self.reporte.pack(fill="both", expand=True, padx=12, pady=6)
        self.reporte.tag_configure("compensada", foreground="#A32626")

        self.totales = ctk.CTkLabel(
            self, text="", anchor="w", text_color=AZUL,
            font=ctk.CTkFont(size=13, weight="bold"))
        self.totales.pack(fill="x", padx=14, pady=(0, 2))
        self.pendiente = ctk.CTkLabel(self, text="", anchor="w", text_color=AMBAR)
        self.pendiente.pack(fill="x", padx=14, pady=(0, 10))

    # -- utilidades ---------------------------------------------------------

    def _decir(self, texto: str, color: str = VERDE) -> None:
        self.aviso.configure(text=texto, text_color=color)
        self.after(6000, lambda: self.aviso.configure(text=""))

    def _fallar(self, error: Exception) -> None:
        messagebox.showerror("Comisiones", str(error), parent=self.ventana)

    def _elegida(self) -> dict | None:
        seleccion = self.tabla.selection()
        return self._politicas.get(seleccion[0]) if seleccion else None

    # -- política -----------------------------------------------------------

    def refrescar(self, mensaje: str = "") -> None:
        self.tabla.delete(*self.tabla.get_children())
        self._politicas = {}
        try:
            self._personas = list(self.servicio.personas_para_comision())
            politicas = self.servicio.politicas_de_comision(token=self.token)
        except Exception as exc:
            self._fallar(exc)
            return
        nombres = [persona["display_name"] for persona in self._personas]
        self.filtro_persona.configure(values=[TODAS, *nombres])
        for politica in politicas:
            self._politicas[politica["id"]] = politica
            self.tabla.insert(
                "", "end", iid=politica["id"],
                tags=() if politica["active"] else ("inactiva",),
                values=(politica["display_name"],
                        politica["branch"] or TODAS,
                        politica["job_type"] or "Todos",
                        _guaranies(politica["amount"]),
                        _dia(politica["effective_from"]),
                        "Activa" if politica["active"] else "Inactiva",
                        politica["created_by"]))
        if mensaje:
            self._decir(mensaje)

    def _formulario(self, titulo: str, politica: dict | None = None) -> None:
        """Alta y edición comparten formulario: son los mismos campos.

        Editar no modifica la fila elegida -no se puede, es append-only-: carga
        sus valores y guarda una versión nueva. La pantalla lo dice, para que
        nadie crea que corrigió un error y en realidad dejó los dos.
        """
        dialogo = ctk.CTkToplevel(self.ventana)
        dialogo.title(titulo)
        dialogo.geometry("430x470")
        dialogo.transient(self.ventana)
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=titulo, font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=AZUL).pack(anchor="w", padx=18, pady=(16, 8))

        ctk.CTkLabel(dialogo, text="Persona", anchor="w").pack(fill="x", padx=18, pady=(6, 0))
        persona = ctk.CTkComboBox(
            dialogo, width=360,
            values=[item["display_name"] for item in self._personas] or ["(sin personas)"])
        persona.pack(padx=18)
        ctk.CTkLabel(dialogo, text="Sucursal (vacío = todas)", anchor="w").pack(
            fill="x", padx=18, pady=(6, 0))
        sucursal = ctk.CTkComboBox(dialogo, width=360, values=[TODAS, *SUCURSALES])
        sucursal.set(TODAS)
        sucursal.pack(padx=18)
        ctk.CTkLabel(dialogo, text="Tipo de trabajo (vacío = todos)", anchor="w").pack(
            fill="x", padx=18, pady=(6, 0))
        tipos = [TODAS] + [tipo["code"] for tipo in self.servicio.tipos_de_trabajo()]
        tipo = ctk.CTkComboBox(dialogo, width=360, values=tipos)
        tipo.set(TODAS)
        tipo.pack(padx=18)
        ctk.CTkLabel(dialogo, text="Importe por trabajo (Gs.)", anchor="w").pack(
            fill="x", padx=18, pady=(6, 0))
        importe = ctk.CTkEntry(dialogo, width=360)
        importe.pack(padx=18)
        ctk.CTkLabel(dialogo, text="Rige desde (dd/mm/aaaa, vacío = hoy)", anchor="w").pack(
            fill="x", padx=18, pady=(6, 0))
        desde = ctk.CTkEntry(dialogo, width=360)
        desde.pack(padx=18)
        ctk.CTkLabel(dialogo, text="Motivo del cambio", anchor="w").pack(
            fill="x", padx=18, pady=(6, 0))
        motivo = ctk.CTkEntry(dialogo, width=360)
        motivo.pack(padx=18)
        ctk.CTkLabel(
            dialogo, justify="left", anchor="w", text_color=GRIS,
            text=("Los trabajos ya terminados conservan la tarifa que tenían.\n"
                  "Cambiar acá no reescribe lo que ya se devengó."),
        ).pack(fill="x", padx=18, pady=(10, 0))

        if politica is not None:
            persona.set(politica["display_name"])
            persona.configure(state="disabled")
            sucursal.set(politica["branch"] or TODAS)
            sucursal.configure(state="disabled")
            tipo.set(politica["job_type"] or TODAS)
            tipo.configure(state="disabled")
            importe.insert(0, str(politica["amount"]))
        elif self._personas:
            persona.set(self._personas[0]["display_name"])

        def guardar():
            elegida = next((item for item in self._personas
                            if item["display_name"] == persona.get()), None)
            if elegida is None:
                self._fallar(CashDayError("Elegí una persona del catálogo."))
                return
            try:
                monto = int(str(importe.get()).strip().replace(".", "") or 0)
            except ValueError:
                self._fallar(CashDayError("El importe tiene que ser un número."))
                return
            try:
                self.servicio.definir_comision(
                    token=self.token, user_id=elegida["id"], amount=monto,
                    branch="" if sucursal.get() == TODAS else sucursal.get(),
                    job_type="" if tipo.get() == TODAS else tipo.get(),
                    effective_from=desde.get().strip() or None,
                    reason=motivo.get().strip())
            except Exception as exc:
                self._fallar(exc)
                return
            dialogo.destroy()
            self.refrescar(f"{elegida['display_name']}: {_guaranies(monto)} por trabajo.")

        acciones = ctk.CTkFrame(dialogo, fg_color="transparent")
        acciones.pack(fill="x", padx=18, pady=16, side="bottom")
        ctk.CTkButton(acciones, text="Guardar", command=guardar).pack(side="left")
        ctk.CTkButton(acciones, text="Cancelar", fg_color="#6B7280",
                      command=dialogo.destroy).pack(side="left", padx=8)

    def _nueva(self) -> None:
        self._formulario("Nueva política de comisión")

    def _editar(self) -> None:
        politica = self._elegida()
        if politica is None:
            self._decir("Elegí una fila.", AMBAR)
            return
        self._formulario(f"Editar · {politica['display_name']}", politica)

    def _alternar(self) -> None:
        politica = self._elegida()
        if politica is None:
            self._decir("Elegí una fila.", AMBAR)
            return
        activa = bool(politica["active"])
        motivo = _pedir_motivo(
            self.ventana,
            "Desactivar comisión" if activa else "Activar comisión",
            f"¿Por qué se {'desactiva' if activa else 'activa'} la comisión de "
            f"{politica['display_name']}?")
        if not motivo:
            return
        try:
            accion = (self.servicio.desactivar_comision if activa
                      else self.servicio.activar_comision)
            accion(token=self.token, user_id=politica["user_id"],
                   branch=politica["branch"], job_type=politica["job_type"],
                   reason=motivo)
        except Exception as exc:
            self._fallar(exc)
            return
        self.refrescar(
            f"{politica['display_name']}: comisión "
            f"{'desactivada' if activa else 'activada'}.")

    def _historial(self) -> None:
        politica = self._elegida()
        if politica is None:
            self._decir("Elegí una fila.", AMBAR)
            return
        try:
            versiones = self.servicio.historial_de_comision(
                token=self.token, user_id=politica["user_id"],
                branch=politica["branch"] or None, job_type=politica["job_type"])
        except Exception as exc:
            self._fallar(exc)
            return
        ventana = ctk.CTkToplevel(self.ventana)
        ventana.title(f"Historial · {politica['display_name']}")
        ventana.geometry("720x420")
        ventana.transient(self.ventana)
        ctk.CTkLabel(ventana, text=f"Historial de comisión · {politica['display_name']}",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color=AZUL).pack(
                         anchor="w", padx=16, pady=(14, 8))
        tabla = ttk.Treeview(
            ventana, columns=("desde", "importe", "antes", "estado", "actor", "motivo"),
            show="headings", selectmode="browse")
        for clave, titulo, ancho, anclaje in (
                ("desde", "Rige desde", 100, "center"),
                ("importe", "Importe", 100, "e"),
                ("antes", "Anterior", 100, "e"),
                ("estado", "Estado", 90, "w"),
                ("actor", "Quién", 110, "w"),
                ("motivo", "Motivo", 200, "w")):
            tabla.heading(clave, text=titulo)
            tabla.column(clave, width=ancho, anchor=anclaje)
        tabla.pack(fill="both", expand=True, padx=16, pady=8)
        for version in versiones:
            tabla.insert("", "end", values=(
                _dia(version["effective_from"]), _guaranies(version["amount"]),
                _guaranies(version["previous_amount"])
                if version["previous_amount"] is not None else "—",
                "Activa" if version["active"] else "Inactiva",
                version["created_by"], version["reason"] or "—"))
        ctk.CTkLabel(ventana, anchor="w", text_color=GRIS, justify="left",
                     text=("Ninguna versión se borra ni se reescribe: cambiar una "
                           "tarifa agrega una fila.")).pack(
                               fill="x", padx=18, pady=(0, 12))

    # -- reporte ------------------------------------------------------------

    def consultar(self) -> None:
        estado = {"Devengadas": "DEVENGADA", "Compensadas": "COMPENSADA"}.get(
            self.filtro_estado.get())
        persona = next((item for item in self._personas
                        if item["display_name"] == self.filtro_persona.get()), None)
        try:
            reporte = self.servicio.reporte_de_comisiones(
                token=self.token,
                date_from=self.filtros["desde"].get().strip() or None,
                date_to=self.filtros["hasta"].get().strip() or None,
                branch=None if self.filtro_sucursal.get() == TODAS
                else self.filtro_sucursal.get(),
                user_id=persona["id"] if persona else None,
                estado=estado)
        except Exception as exc:
            self._fallar(exc)
            return
        self.reporte.delete(*self.reporte.get_children())
        for fila in reporte["filas"]:
            compensada = fila["estado"] == "COMPENSADA"
            self.reporte.insert(
                "", "end", tags=("compensada",) if compensada else (),
                values=(_dia(fila["accrued_at"]), fila["reference"], fila["customer"],
                        fila["beneficiary"], fila["branch"],
                        _guaranies(fila["accrued_amount"]),
                        _guaranies(fila["compensated_amount"]) if compensada else "—",
                        _guaranies(fila["net_amount"]), fila["estado"]))
        totales = reporte["totales"]
        self.totales.configure(
            text=(f"{totales['trabajos']} trabajos   ·   "
                  f"Devengado {_guaranies(totales['bruto'])}   ·   "
                  f"Compensado {_guaranies(totales['compensado'])}   ·   "
                  f"NETO {_guaranies(totales['neto'])}"))
        # Lo que no devengó es parte de la respuesta, no una nota al pie: un
        # trabajo terminado sin comisión puede ser una decision o un olvido, y
        # la unica forma de que sea una decision es que alguien lo vea.
        self.pendiente.configure(
            text=("" if not totales["sin_politica"] else
                  f"{totales['sin_politica']} trabajo(s) terminados no devengaron: "
                  f"su responsable no tiene política cargada, o es de cero."))


def _pedir_motivo(parent, titulo: str, pregunta: str) -> str:
    """Un motivo escrito, o nada. Sin motivo no se cambia una política."""
    dialogo = ctk.CTkInputDialog(text=pregunta, title=titulo)
    return str(dialogo.get_input() or "").strip()


def construir_panel_comisiones(master, servicio, *, token, ventana=None):
    panel = PanelComisiones(master, servicio, token=token, ventana=ventana)
    panel.pack(fill="both", expand=True)
    return panel
