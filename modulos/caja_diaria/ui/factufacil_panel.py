"""La pestaña «FactuFácil» de BC Caja.

Dos listas y tres botones. Nada más, a propósito: quien la usa está atendiendo
un mostrador, no administrando un sistema. Lo que necesita saber es cuáles le
faltan cargar; lo que necesita hacer es copiar los datos, cargarlos allá, y
decir que ya está.

Vive en su propio módulo y no adentro de `CajaDiaria.py` porque esa pantalla ya
tiene cinco mil líneas, y porque así la pestaña se puede leer entera de una vez.
"""

from __future__ import annotations

from datetime import date, timedelta

import customtkinter as ctk
from tkinter import ttk, messagebox

from ..application.factufacil import CARGADA, ETIQUETAS, PARA_CARGAR

AZUL = "#0F5FB9"
VERDE = "#1B7F4B"
AMBAR = "#B45309"
GRIS = "#5B6B7F"
BORDE = "#D6E1EE"

#: Lo que se ve, en el orden en que se lee una fila: primero cuándo y dónde,
#: después de quién es, y al final cuánto. El estado va primero de todos porque
#: es lo único que cambia y lo que se busca con la vista.
COLUMNAS = (
    ("estado", "Estado", 120),
    ("fecha", "Fecha", 95),
    ("sucursal", "Sucursal", 100),
    ("sobre", "Sobre", 80),
    ("cliente", "Cliente", 220),
    ("documento", "CI/RUC", 110),
    ("telefono", "Teléfono", 110),
    ("vendedora", "Vendedora", 110),
    ("total", "Total", 110),
    ("cargada_por", "Cargó", 110),
)


def guaranies(valor: int) -> str:
    return f"{int(valor or 0):,}".replace(",", ".")


class PanelFactuFacil(ctk.CTkFrame):
    """Construye la pestaña y la mantiene al día.

    Recibe el servicio ya armado: no abre bases ni sabe dónde viven. Y recibe
    `copiar`, porque copiar al portapapeles lo hace la ventana raíz de Tk y no
    un frame suelto.
    """

    def __init__(self, master, servicio, *, actor: str, perfil=None, copiar=None):
        super().__init__(master, fg_color="transparent")
        self._servicio = servicio
        self._actor = actor or ""
        self._copiar = copiar
        fuente = (perfil or {}).get("fuente_label", 11)
        self._fuente = fuente
        self._estado = ctk.StringVar(value=PARA_CARGAR)
        self._seleccion = None
        self._filas = {}

        self._construir_cabecera(fuente)
        self._construir_filtros(fuente)
        self._construir_tabla(fuente)
        self._construir_observaciones(fuente)
        self._construir_acciones(fuente)
        self.refrescar()

    # -- construcción ------------------------------------------------------

    def _construir_cabecera(self, fuente):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", pady=(0, 6))
        self._chips = {}
        for estado, color in ((PARA_CARGAR, AMBAR), (CARGADA, VERDE)):
            chip = ctk.CTkButton(
                barra, text=ETIQUETAS[estado], height=34, width=190,
                corner_radius=17, fg_color="#FFFFFF", text_color=color,
                hover_color="#EAF3FF", border_width=2, border_color=BORDE,
                font=ctk.CTkFont(size=fuente + 2, weight="bold"),
                command=lambda valor=estado: self._cambiar_estado(valor))
            chip.pack(side="left", padx=(0, 8))
            self._chips[estado] = (chip, color)
        self._aviso = ctk.CTkLabel(
            barra, text="", anchor="e", text_color=GRIS,
            font=ctk.CTkFont(size=fuente + 1, weight="bold"))
        self._aviso.pack(side="right", padx=8)

    def _construir_filtros(self, fuente):
        barra = ctk.CTkFrame(self, fg_color="#F5F8FC", corner_radius=6)
        barra.pack(fill="x", pady=(0, 6))
        self._entradas = {}
        for clave, etiqueta, ancho in (
            ("desde", "Desde", 110), ("hasta", "Hasta", 110),
            ("sucursal", "Sucursal", 120), ("sobre", "Sobre", 90),
            ("cliente", "Cliente", 180), ("vendedora", "Vendedora", 120),
        ):
            ctk.CTkLabel(barra, text=etiqueta, text_color=GRIS,
                         font=ctk.CTkFont(size=fuente, weight="bold")
                         ).pack(side="left", padx=(10, 4), pady=7)
            campo = ctk.CTkEntry(barra, width=ancho, height=28,
                                 font=ctk.CTkFont(size=fuente))
            campo.pack(side="left", pady=7)
            campo.bind("<Return>", lambda _evento: self.refrescar())
            self._entradas[clave] = campo
        ctk.CTkButton(barra, text="Limpiar", width=90, height=28,
                      fg_color="#FFFFFF", text_color=GRIS, border_width=1,
                      border_color=BORDE, hover_color="#EAF3FF",
                      font=ctk.CTkFont(size=fuente, weight="bold"),
                      command=self._limpiar_filtros).pack(side="right", padx=(4, 10))
        ctk.CTkButton(barra, text="Buscar", width=90, height=28,
                      fg_color=AZUL, hover_color="#0F5FC7",
                      font=ctk.CTkFont(size=fuente, weight="bold"),
                      command=self.refrescar).pack(side="right", padx=4)
        # Un atajo que resuelve el caso de todos los días: lo de hoy.
        ctk.CTkButton(barra, text="Hoy", width=70, height=28,
                      fg_color="#FFFFFF", text_color=AZUL, border_width=1,
                      border_color=BORDE, hover_color="#EAF3FF",
                      font=ctk.CTkFont(size=fuente, weight="bold"),
                      command=self._filtrar_hoy).pack(side="right", padx=4)

    def _construir_tabla(self, fuente):
        marco = ctk.CTkFrame(self, fg_color="#FFFFFF", corner_radius=6)
        marco.pack(fill="both", expand=True)
        estilo = ttk.Style()
        estilo.configure("FactuFacil.Treeview", rowheight=fuente + 18,
                         font=("Segoe UI", fuente), background="#FFFFFF",
                         fieldbackground="#FFFFFF")
        estilo.configure("FactuFacil.Treeview.Heading",
                         font=("Segoe UI", fuente, "bold"))
        self.tabla = ttk.Treeview(
            marco, columns=[clave for clave, _, _ in COLUMNAS], show="headings",
            style="FactuFacil.Treeview", selectmode="browse")
        for clave, titulo, ancho in COLUMNAS:
            self.tabla.heading(clave, text=titulo)
            self.tabla.column(clave, width=ancho, anchor="e" if clave == "total" else "w")
        barra = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y", pady=6)
        self.tabla.pack(fill="both", expand=True, padx=6, pady=6)
        self.tabla.tag_configure(PARA_CARGAR, foreground="#7A4B00")
        self.tabla.tag_configure(CARGADA, foreground="#1B5E3A")
        self.tabla.tag_configure("editada", background="#FFF6E5")
        self.tabla.bind("<<TreeviewSelect>>", self._al_seleccionar)

    def _construir_observaciones(self, fuente):
        """La receta se lee entera o no sirve de nada.

        En la grilla no entra: son dos renglones de graduación por ojo. Va acá
        abajo, completa, y cambia al elegir una fila.
        """
        marco = ctk.CTkFrame(self, fg_color="#F8FAFD", corner_radius=6)
        marco.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(marco, text="Observaciones / receta", text_color=GRIS,
                     font=ctk.CTkFont(size=fuente, weight="bold")
                     ).pack(anchor="w", padx=10, pady=(6, 0))
        self.observaciones = ctk.CTkTextbox(
            marco, height=fuente * 5, fg_color="#FFFFFF", wrap="word",
            font=ctk.CTkFont(size=fuente + 1))
        self.observaciones.pack(fill="x", padx=10, pady=(2, 8))
        self.observaciones.configure(state="disabled")

    def _construir_acciones(self, fuente):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", pady=(8, 0))
        self.boton_copiar = ctk.CTkButton(
            barra, text="Copiar datos", width=170, height=40,
            fg_color="#FFFFFF", text_color=AZUL, border_width=2,
            border_color=BORDE, hover_color="#EAF3FF",
            font=ctk.CTkFont(size=fuente + 3, weight="bold"),
            command=self.copiar_seleccion)
        self.boton_copiar.pack(side="left", padx=(0, 10))
        self.boton_marcar = ctk.CTkButton(
            barra, text="Marcar como cargada", width=240, height=40,
            fg_color=VERDE, hover_color="#166B3F",
            font=ctk.CTkFont(size=fuente + 3, weight="bold"),
            command=self.marcar_seleccion)
        self.boton_marcar.pack(side="left", padx=(0, 10))
        self.boton_revertir = ctk.CTkButton(
            barra, text="Volver a Para cargar", width=210, height=40,
            fg_color="#FFFFFF", text_color=AMBAR, border_width=2,
            border_color="#F0D3A8", hover_color="#FFF6E5",
            font=ctk.CTkFont(size=fuente + 3, weight="bold"),
            command=self.revertir_seleccion)
        self.boton_revertir.pack(side="left")
        self.mensaje = ctk.CTkLabel(
            barra, text="", anchor="w", text_color=VERDE,
            font=ctk.CTkFont(size=fuente + 2, weight="bold"))
        self.mensaje.pack(side="left", padx=14)

    # -- estado y datos ----------------------------------------------------

    def _filtros(self) -> dict:
        return {clave: campo.get().strip() or None
                for clave, campo in self._entradas.items()}

    def _limpiar_filtros(self):
        for campo in self._entradas.values():
            campo.delete(0, "end")
        self.refrescar()

    def _filtrar_hoy(self):
        hoy = date.today().isoformat()
        for clave, valor in (("desde", hoy), ("hasta", hoy)):
            self._entradas[clave].delete(0, "end")
            self._entradas[clave].insert(0, valor)
        self.refrescar()

    def _cambiar_estado(self, estado):
        self._estado.set(estado)
        self.refrescar()

    def refrescar(self):
        estado = self._estado.get()
        filtros = self._filtros()
        filas = self._servicio.listar(estado=estado, **filtros)
        conteos = self._servicio.conteos(**filtros)
        for valor, (chip, color) in self._chips.items():
            activo = valor == estado
            chip.configure(
                text=f"{ETIQUETAS[valor]}  ({conteos[valor]})",
                fg_color=color if activo else "#FFFFFF",
                text_color="#FFFFFF" if activo else color,
                border_color=color if activo else BORDE)
        self.tabla.delete(*self.tabla.get_children())
        self._filas = {fila.cash_entry_id: fila for fila in filas}
        for fila in filas:
            etiquetas = [fila.estado]
            if fila.editada_despues_de_cargar:
                etiquetas.append("editada")
            self.tabla.insert(
                "", "end", iid=fila.cash_entry_id, tags=tuple(etiquetas),
                values=(fila.etiqueta_estado, fila.fecha, fila.sucursal, fila.sobre,
                        fila.cliente, fila.documento, fila.telefono, fila.vendedora,
                        guaranies(fila.total), fila.cargada_por))
        editadas = sum(1 for fila in filas if fila.editada_despues_de_cargar)
        self._aviso.configure(
            text=(f"{editadas} se editaron después de cargarse" if editadas else ""),
            text_color=AMBAR if editadas else GRIS)
        self._seleccion = None
        self._mostrar_observaciones("")
        self._ajustar_botones()

    def _al_seleccionar(self, _evento=None):
        seleccion = self.tabla.selection()
        self._seleccion = seleccion[0] if seleccion else None
        fila = self._filas.get(self._seleccion)
        self._mostrar_observaciones(fila.observaciones if fila else "")
        self._ajustar_botones()

    def _mostrar_observaciones(self, texto):
        self.observaciones.configure(state="normal")
        self.observaciones.delete("1.0", "end")
        self.observaciones.insert("1.0", texto or "—")
        self.observaciones.configure(state="disabled")

    def _ajustar_botones(self):
        fila = self._filas.get(self._seleccion)
        hay = fila is not None
        self.boton_copiar.configure(state="normal" if hay else "disabled")
        self.boton_marcar.configure(
            state="normal" if hay and fila.estado == PARA_CARGAR else "disabled")
        self.boton_revertir.configure(
            state="normal" if hay and fila.estado == CARGADA else "disabled")

    # -- acciones ----------------------------------------------------------

    def copiar_seleccion(self):
        fila = self._filas.get(self._seleccion)
        if fila is None:
            return
        texto = fila.texto_para_copiar()
        if self._copiar is not None:
            self._copiar(texto)
        self._avisar("Datos copiados. Pegalos en FactuFácil.", VERDE)

    def marcar_seleccion(self):
        fila = self._filas.get(self._seleccion)
        if fila is None:
            return
        cambio = self._servicio.marcar_cargada(fila.cash_entry_id, actor=self._actor)
        self.refrescar()
        self._avisar(
            f"Sobre {fila.sobre} marcado como cargado." if cambio
            else f"El sobre {fila.sobre} ya estaba cargado.", VERDE if cambio else GRIS)

    def revertir_seleccion(self):
        fila = self._filas.get(self._seleccion)
        if fila is None:
            return
        dialogo = ctk.CTkInputDialog(
            title="Volver a Para cargar",
            text=f"¿Por qué vuelve el sobre {fila.sobre}?")
        motivo = (dialogo.get_input() or "").strip()
        if not motivo:
            # Cancelar y no escribir el motivo son lo mismo: no se revierte.
            self._avisar("Sin motivo no se revierte.", AMBAR)
            return
        try:
            self._servicio.revertir(fila.cash_entry_id, actor=self._actor, motivo=motivo)
        except Exception as error:  # noqa: BLE001 - la operadora lee el porqué
            messagebox.showwarning("FactuFácil", str(error))
            return
        self.refrescar()
        self._avisar(f"Sobre {fila.sobre} vuelve a Para cargar.", AMBAR)

    def _avisar(self, texto, color):
        self.mensaje.configure(text=texto, text_color=color)
        self.after(6000, lambda: self.mensaje.configure(text=""))


def construir_panel_factufacil(master, servicio, *, actor, perfil=None, copiar=None):
    panel = PanelFactuFacil(master, servicio, actor=actor, perfil=perfil, copiar=copiar)
    panel.pack(fill="both", expand=True, padx=10, pady=8)
    return panel
