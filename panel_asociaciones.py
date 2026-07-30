"""Panel integrado de Planillas de Asociaciones."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from shutil import copy2
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
import Asociaciones

COLOR_FONDO = ("#F4F7FB", "#0B1220")
COLOR_PANEL = ("#FFFFFF", "#131D2E")
COLOR_PANEL_SECUNDARIO = ("#EAF0F7", "#1A2639")
COLOR_BORDE = ("#DCE4EE", "#26354A")
COLOR_TEXTO = ("#182230", "#F4F7FB")
COLOR_TEXTO_SUAVE = ("#617084", "#9CAFC5")
COLOR_PRIMARIO = "#246BFD"
COLOR_VERDE = "#18A874"
COLOR_ROJO = "#E25555"
COLOR_NARANJA = "#E99A35"


def _monto(valor):
    return f"Gs. {int(valor):,}".replace(",", ".")


class PanelAsociaciones(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLOR_FONDO, corner_radius=0)
        self.config_id = None
        self.planilla_id = None
        self.detalle_id = None
        self.vista_actual = "inicio"
        self._orden_tablas = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._crear_encabezado()
        self.cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self.cuerpo.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.cuerpo.grid_columnconfigure(0, weight=1)
        self.cuerpo.grid_rowconfigure(0, weight=1)
        self.winfo_toplevel().bind("<Escape>", self._navegar_atras_escape)
        self.mostrar_inicio()

    def _navegar_atras_escape(self, _evento=None):
        """Retrocede una vista; desde el inicio vuelve al panel general."""
        if self.vista_actual == "detalle":
            self._mostrar_local()
        elif self.vista_actual in ("local", "config"):
            self.mostrar_inicio()
        else:
            ventana = self.winfo_toplevel()
            if hasattr(ventana, "mostrar_inicio"):
                ventana.mostrar_inicio()
        return "break"

    @staticmethod
    def _valor_ordenable(valor, tipo):
        texto = str(valor or "").strip()
        if tipo == "numero":
            limpio = (
                texto.replace("Gs.", "")
                .replace(".", "")
                .replace(",", "")
                .replace(" ", "")
            )
            try:
                return int(limpio)
            except ValueError:
                return 0
        if tipo == "periodo":
            try:
                mes, anio = texto.split("-")
                return int(anio), int(mes)
            except (ValueError, AttributeError):
                return 0, 0
        if tipo == "cuota":
            try:
                partes = texto.replace("-", "/").split("/")
                actual = int(partes[0])
                total = int(partes[1]) if len(partes) > 1 else actual
                return actual, total
            except (ValueError, IndexError):
                return 0, 0
        return texto.casefold()

    def _configurar_orden(self, tabla, columnas):
        """Activa orden ascendente/descendente al tocar cada encabezado."""
        tabla._columnas_orden = columnas
        self._orden_tablas[str(tabla)] = {
            "columna": None,
            "descendente": False,
            "titulos": {clave: titulo for clave, titulo, _ancho, _tipo in columnas},
            "tipos": {clave: tipo for clave, _titulo, _ancho, tipo in columnas},
        }
        for clave, titulo, _ancho, tipo in columnas:
            tabla.heading(
                clave,
                text=f"{titulo} ↕",
                command=lambda c=clave, t=tipo: self._ordenar_tabla(tabla, c, t),
            )

    def _ordenar_tabla(self, tabla, columna, tipo):
        estado = self._orden_tablas[str(tabla)]
        descendente = (
            not estado["descendente"]
            if estado["columna"] == columna
            else False
        )
        filas = list(tabla.get_children(""))
        filas.sort(
            key=lambda item: self._valor_ordenable(
                tabla.set(item, columna), tipo
            ),
            reverse=descendente,
        )
        for posicion, item in enumerate(filas):
            tabla.move(item, "", posicion)

        estado["columna"] = columna
        estado["descendente"] = descendente
        for clave, titulo in estado["titulos"].items():
            indicador = ""
            if clave == columna:
                indicador = " ▼" if descendente else " ▲"
            else:
                indicador = " ↕"
            tabla.heading(
                clave,
                text=titulo + indicador,
                command=lambda c=clave, t=estado["tipos"][clave]: (
                    self._ordenar_tabla(tabla, c, t)
                ),
            )

    def _crear_encabezado(self):
        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.grid(row=0, column=0, sticky="ew", padx=22, pady=(16, 12))
        cab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            cab, text="Planillas de Asociaciones",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=COLOR_TEXTO, anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            cab,
            text="Configuración por asociación, importación mensual y exportación.",
            font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXTO_SUAVE, anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(3, 0))

    def _limpiar_cuerpo(self):
        for hijo in self.cuerpo.winfo_children():
            hijo.destroy()

    def _boton(self, master, texto, comando, color=COLOR_PRIMARIO, ancho=140):
        return ctk.CTkButton(
            master, text=texto, command=comando, width=ancho, height=38,
            corner_radius=9, fg_color=color,
            hover_color=color, font=ctk.CTkFont(size=12, weight="bold"),
        )

    def _campo(self, master, texto, fila, columna, columnspan=1):
        ctk.CTkLabel(
            master, text=texto, text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
        ).grid(row=fila, column=columna, columnspan=columnspan,
               sticky="ew", padx=8, pady=(6, 3))
        entrada = ctk.CTkEntry(
            master, height=38, fg_color=COLOR_PANEL_SECUNDARIO,
            border_color=COLOR_BORDE, text_color=COLOR_TEXTO,
        )
        entrada.grid(row=fila + 1, column=columna, columnspan=columnspan,
                     sticky="ew", padx=8, pady=(0, 7))
        return entrada

    # ------------------------------------------------------------------
    # INICIO: ASOCIACIONES Y LOCALES
    # ------------------------------------------------------------------
    def mostrar_inicio(self):
        self.vista_actual = "inicio"
        self._limpiar_cuerpo()

        marco = ctk.CTkFrame(
            self.cuerpo, fg_color=COLOR_PANEL, corner_radius=14,
            border_width=1, border_color=COLOR_BORDE,
        )
        marco.grid(row=0, column=0, sticky="nsew")
        marco.grid_columnconfigure(0, weight=2)
        marco.grid_columnconfigure(1, weight=3)
        marco.grid_rowconfigure(1, weight=1)


        # Dashboard
        dash = ctk.CTkFrame(marco, fg_color="transparent")
        dash.grid(row=3, column=0, columnspan=4, sticky="ew", padx=12, pady=(6,2))
        for i in range(5):
            dash.grid_columnconfigure(i, weight=1)

        def _card(col, titulo):
            card = ctk.CTkFrame(
                dash,
                fg_color=COLOR_PANEL_SECUNDARIO,
                corner_radius=10,
                border_width=1,
                border_color=COLOR_BORDE,
            )
            card.grid(row=0, column=col, sticky="ew", padx=4)
            ctk.CTkLabel(
                card,
                text=titulo,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
            ).pack(pady=(8,2))
            lbl = ctk.CTkLabel(
                card,
                text="-",
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color=COLOR_TEXTO,
            )
            lbl.pack(pady=(0,8))
            return lbl

        self.lbl_dash_planillas=_card(0,"Planillas")
        self.lbl_dash_registros=_card(1,"Registros")
        self.lbl_dash_subtotal=_card(2,"Cuotas del mes")
        self.lbl_dash_saldo=_card(3,"Saldo pendiente")
        self.lbl_dash_pendientes=_card(4,"Pendientes de finalizar")
        acciones = ctk.CTkFrame(marco, fg_color="transparent")
        acciones.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=12)
        self._boton(acciones, "Nueva asociación/local", self.nueva_config, COLOR_VERDE, 180).pack(side="left", padx=4)
        self._boton(acciones, "Modificar", self.modificar_config, COLOR_NARANJA, 120).pack(side="left", padx=4)
        self._boton(acciones, "Eliminar", self.eliminar_config, COLOR_ROJO, 110).pack(side="left", padx=4)
        self._boton(acciones, "Abrir local", self.abrir_local, COLOR_PRIMARIO, 130).pack(side="left", padx=4)

        izquierda = ctk.CTkFrame(marco, fg_color=COLOR_PANEL_SECUNDARIO, corner_radius=12)
        izquierda.grid(row=1, column=0, sticky="nsew", padx=(14, 7), pady=(0, 14))
        izquierda.grid_columnconfigure(0, weight=1)
        izquierda.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            izquierda, text="Asociaciones y locales",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXTO, anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=12)

        self.tree_config = ttk.Treeview(izquierda, show="tree", selectmode="browse")
        self.tree_config.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.tree_config.bind("<Double-1>", lambda _e: self.abrir_local())
        self.tree_config.bind("<<AbrirConTeclado>>", lambda _e: self.abrir_local())
        self.tree_config.bind("<Return>", lambda _e: self.abrir_local())
        self.tree_config.bind("<<TreeviewSelect>>", lambda _e: self._actualizar_resumen())

        derecha = ctk.CTkFrame(marco, fg_color="transparent")
        derecha.grid(row=1, column=1, sticky="nsew", padx=(7, 14), pady=(0, 14))
        derecha.grid_columnconfigure((0, 1, 2), weight=1)
        derecha.grid_rowconfigure(2, weight=1)

        self.lbl_resumen = ctk.CTkLabel(
            derecha, text="Seleccioná un local para ver su información.",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXTO, anchor="w", justify="left",
        )
        self.lbl_resumen.grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=(4, 12))

        stats = self._estadisticas()
        for col, (titulo, valor) in enumerate((
            ("Asociaciones", stats["asociaciones"]),
            ("Locales", stats["locales"]),
            ("Planillas del mes", stats["mes"]),
        )):
            tarjeta = ctk.CTkFrame(
                derecha, fg_color=COLOR_PANEL_SECUNDARIO,
                corner_radius=12, border_width=1, border_color=COLOR_BORDE,
            )
            tarjeta.grid(row=1, column=col, sticky="nsew", padx=6, pady=4)
            ctk.CTkLabel(
                tarjeta, text=titulo, text_color=COLOR_TEXTO_SUAVE,
                font=ctk.CTkFont(size=12, weight="bold"),
            ).pack(padx=12, pady=(12, 3))
            ctk.CTkLabel(
                tarjeta, text=str(valor), text_color=COLOR_TEXTO,
                font=ctk.CTkFont(size=24, weight="bold"),
            ).pack(padx=12, pady=(0, 12))

        self._cargar_arbol()
        self._actualizar_dashboard_inicio()
        self.after_idle(self._enfocar_primer_local)

    def _actualizar_dashboard_inicio(self):
        resumen = Asociaciones.resumen_dashboard()
        self.lbl_dash_planillas.configure(text=str(resumen["planillas"]))
        self.lbl_dash_registros.configure(text=str(resumen["registros"]))
        self.lbl_dash_subtotal.configure(text=_monto(resumen["cuotas_mes"]))
        self.lbl_dash_saldo.configure(text=_monto(resumen["saldo_pendiente"]))
        self.lbl_dash_pendientes.configure(text=str(resumen["pendientes"]))

    def _enfocar_primer_local(self):
        """Selecciona el primer local para comenzar con flechas y Enter."""
        asociaciones = self.tree_config.get_children("")
        if not asociaciones:
            self.tree_config.focus_set()
            return
        locales = self.tree_config.get_children(asociaciones[0])
        destino = locales[0] if locales else asociaciones[0]
        self.tree_config.selection_set(destino)
        self.tree_config.focus(destino)
        self.tree_config.focus_set()
        self.tree_config.see(destino)

    def _estadisticas(self):
        configs = Asociaciones.listar_configuraciones()
        asociaciones = {c["asociacion"] for c in configs}
        periodo = datetime.now().strftime("%m-%Y")
        return {
            "asociaciones": len(asociaciones),
            "locales": len(configs),
            "mes": len(Asociaciones.listar_planillas(periodo=periodo)),
        }

    def _cargar_arbol(self):
        self.tree_config.delete(*self.tree_config.get_children())
        agrupadas = {}
        for config in Asociaciones.listar_configuraciones():
            agrupadas.setdefault(config["asociacion"], []).append(config)

        for asociacion in sorted(agrupadas):
            padre = self.tree_config.insert("", "end", text=f"📁 {asociacion}", open=True)
            for config in sorted(agrupadas[asociacion], key=lambda x: x["local"]):
                self.tree_config.insert(
                    padre, "end", iid=config["id"],
                    text=f"   🏢 {config['local']}",
                )

    def _config_seleccionada(self):
        seleccion = self.tree_config.selection()
        if not seleccion:
            return None
        return Asociaciones.obtener_configuracion(seleccion[0])

    def _actualizar_resumen(self):
        config = self._config_seleccionada()
        if not config:
            self.lbl_resumen.configure(text="Seleccioná un local para ver su información.")
            return
        cantidad = len(Asociaciones.listar_planillas(config_id=config["id"]))
        regla = config["tipo_descuento"]
        if config["porcentaje"]:
            regla += f" · {config['porcentaje']}%"
        self.lbl_resumen.configure(
            text=(
                f"{config['asociacion']}\n"
                f"{config['local']}\n"
                f"Descuento: {regla}\n"
                f"Categorías: {', '.join(config['categorias'])}\n"
                f"Planillas registradas: {cantidad}"
            )
        )

    # ------------------------------------------------------------------
    # CONFIGURACIÓN
    # ------------------------------------------------------------------
    def nueva_config(self):
        self.config_id = None
        self._mostrar_form_config()

    def modificar_config(self):
        config = self._config_seleccionada()
        if not config:
            messagebox.showwarning("Asociación", "Seleccioná un local.", parent=self)
            return
        self.config_id = config["id"]
        self._mostrar_form_config(config)

    def _mostrar_form_config(self, config=None):
        self.vista_actual = "config"
        self._limpiar_cuerpo()
        form = ctk.CTkFrame(
            self.cuerpo, fg_color=COLOR_PANEL, corner_radius=14,
            border_width=1, border_color=COLOR_BORDE,
        )
        form.grid(row=0, column=0, sticky="nsew")
        for col in range(4):
            form.grid_columnconfigure(col, weight=1)

        ctk.CTkLabel(
            form, text="Configurar asociación y local",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLOR_TEXTO,
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(16, 8))

        self.c_asociacion = self._campo(form, "Asociación", 1, 0, 2)
        self.c_local = self._campo(form, "Local", 1, 2, 2)
        self.c_titulo = self._campo(form, "Título del encabezado", 3, 0, 2)
        self.c_liquidacion = self._campo(form, "Texto de liquidación", 3, 2, 2)
        self.c_logo = self._campo(form, "Logo", 5, 0, 3)
        self._boton(form, "Elegir imagen", self.elegir_logo, COLOR_PRIMARIO, 130).grid(
            row=6, column=3, sticky="ew", padx=8, pady=(0, 7)
        )

        ctk.CTkLabel(
            form, text="Regla de descuento",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_TEXTO,
        ).grid(row=7, column=0, sticky="w", padx=8, pady=(6, 3))
        self.c_tipo = ctk.CTkOptionMenu(
            form, values=list(Asociaciones.TIPOS_DESCUENTO),
            height=38, fg_color=COLOR_PRIMARIO,
        )
        self.c_tipo.grid(row=8, column=0, sticky="ew", padx=8, pady=(0, 7))
        self.c_porcentaje = self._campo(form, "Porcentaje", 7, 1)
        self.c_categorias = self._campo(form, "Categorías separadas por coma", 7, 2, 2)

        botones = ctk.CTkFrame(form, fg_color="transparent")
        botones.grid(row=9, column=0, columnspan=4, sticky="ew", padx=12, pady=16)
        self._boton(botones, "Guardar", self.guardar_config, COLOR_VERDE).pack(side="left", padx=4)
        self._boton(botones, "Cancelar", self.mostrar_inicio, COLOR_NARANJA).pack(side="left", padx=4)

        if config:
            datos = (
                (self.c_asociacion, config["asociacion"]),
                (self.c_local, config["local"]),
                (self.c_titulo, config["titulo"]),
                (self.c_liquidacion, config["texto_liquidacion"]),
                (self.c_logo, config.get("logo", "")),
                (self.c_porcentaje, str(config["porcentaje"])),
                (self.c_categorias, ", ".join(config["categorias"])),
            )
            for campo, valor in datos:
                campo.insert(0, valor)
            self.c_tipo.set(config["tipo_descuento"])
        else:
            self.c_tipo.set("SIN_DESCUENTO")
            self.c_porcentaje.insert(0, "0")
            self.c_categorias.insert(0, "Funcionarios, Jubilados")

    def elegir_logo(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar logo",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg")],
            parent=self,
        )
        if not ruta:
            return
        Asociaciones.CARPETA_LOGOS.mkdir(parents=True, exist_ok=True)
        destino = Asociaciones.CARPETA_LOGOS / Path(ruta).name
        copy2(ruta, destino)
        self.c_logo.delete(0, "end")
        self.c_logo.insert(0, str(destino))

    def guardar_config(self):
        try:
            Asociaciones.guardar_configuracion({
                "id": self.config_id,
                "asociacion": self.c_asociacion.get(),
                "local": self.c_local.get(),
                "titulo": self.c_titulo.get(),
                "texto_liquidacion": self.c_liquidacion.get(),
                "logo": self.c_logo.get(),
                "tipo_descuento": self.c_tipo.get(),
                "porcentaje": self.c_porcentaje.get() or "0",
                "categorias": [x.strip() for x in self.c_categorias.get().split(",")],
                "permite_ajuste_manual": True,
            })
        except (ValueError, OSError) as error:
            messagebox.showerror("No se pudo guardar", str(error), parent=self)
            return
        self.mostrar_inicio()

    def eliminar_config(self):
        config = self._config_seleccionada()
        if not config:
            messagebox.showwarning("Asociación", "Seleccioná un local.", parent=self)
            return
        if not messagebox.askyesno(
            "Eliminar", f"¿Eliminar {config['asociacion']} - {config['local']}?",
            parent=self,
        ):
            return
        try:
            Asociaciones.eliminar_configuracion(config["id"])
        except ValueError as error:
            messagebox.showerror("No se pudo eliminar", str(error), parent=self)
            return
        self.mostrar_inicio()

    # ------------------------------------------------------------------
    # TRABAJO MENSUAL
    # ------------------------------------------------------------------
    def abrir_local(self):
        config = self._config_seleccionada()
        if not config:
            messagebox.showwarning("Asociación", "Seleccioná un local.", parent=self)
            return
        self.config_id = config["id"]
        self._mostrar_local()

    def _mostrar_local(self):
        self.vista_actual = "local"
        self._limpiar_cuerpo()
        config = Asociaciones.obtener_configuracion(self.config_id)
        if not config:
            self.mostrar_inicio()
            return

        marco = ctk.CTkFrame(
            self.cuerpo, fg_color=COLOR_PANEL, corner_radius=14,
            border_width=1, border_color=COLOR_BORDE,
        )
        marco.grid(row=0, column=0, sticky="nsew")
        marco.grid_columnconfigure((0, 1, 2, 3), weight=1)
        marco.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(
            marco, text=f"{config['asociacion']} · {config['local']}",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLOR_TEXTO,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(14, 4))
        self._boton(marco, "Volver", self.mostrar_inicio, COLOR_NARANJA, 100).grid(
            row=0, column=3, sticky="e", padx=16, pady=(14, 4)
        )

        ctk.CTkLabel(
            marco, text="Período MM-AAAA",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO, anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=8, pady=(6, 3))

        periodo_frame = ctk.CTkFrame(marco, fg_color="transparent")
        periodo_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 7))
        periodo_frame.grid_columnconfigure(1, weight=1)

        self._boton(
            periodo_frame, "◀", self.periodo_anterior, COLOR_NARANJA, 38
        ).grid(row=0, column=0, sticky="w", padx=(0, 6))

        self.p_periodo = ctk.CTkEntry(
            periodo_frame, height=38,
            fg_color=COLOR_PANEL_SECUNDARIO,
            border_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            justify="center",
        )
        self.p_periodo.grid(row=0, column=1, sticky="ew")
        self.p_periodo.insert(0, datetime.now().strftime("%m-%Y"))

        self._boton(
            periodo_frame, "▶", self.periodo_siguiente, COLOR_PRIMARIO, 38
        ).grid(row=0, column=2, sticky="e", padx=(6, 0))
        ctk.CTkLabel(
            marco, text="Categoría",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_TEXTO,
        ).grid(row=1, column=1, sticky="w", padx=8, pady=(6, 3))
        self.p_categoria = ctk.CTkOptionMenu(
            marco, values=config["categorias"], height=38,
            fg_color=COLOR_PRIMARIO,
        )
        self.p_categoria.grid(row=2, column=1, sticky="ew", padx=8, pady=(0, 7))
        self.p_categoria.set(config["categorias"][0])

        self.p_descuento = self._campo(marco, "Descuento manual", 1, 2)
        self.p_descuento.insert(0, "0")

        # Dashboard
        dash = ctk.CTkFrame(marco, fg_color="transparent")
        dash.grid(row=3, column=0, columnspan=4, sticky="ew", padx=12, pady=(4,8))
        for i in range(5):
            dash.grid_columnconfigure(i, weight=1)

        def _card(col, titulo):
            f=ctk.CTkFrame(dash, fg_color=COLOR_PANEL_SECUNDARIO,
                           border_width=1,border_color=COLOR_BORDE,corner_radius=10)
            f.grid(row=0,column=col,sticky="ew",padx=4)
            ctk.CTkLabel(f,text=titulo,font=ctk.CTkFont(size=11,weight="bold"),
                         text_color=COLOR_TEXTO_SUAVE).pack(pady=(8,2))
            l=ctk.CTkLabel(f,text="-",font=ctk.CTkFont(size=18,weight="bold"),
                           text_color=COLOR_TEXTO)
            l.pack(pady=(0,8))
            return l

        self.lbl_dash_planillas=_card(0,"Planillas")
        self.lbl_dash_registros=_card(1,"Registros")
        self.lbl_dash_subtotal=_card(2,"Cuotas del mes")
        self.lbl_dash_saldo=_card(3,"Saldo pendiente")
        self.lbl_dash_pendientes=_card(4,"Pendientes")

        acciones = ctk.CTkFrame(marco, fg_color="transparent")
        acciones.grid(row=5, column=0, columnspan=4, sticky="ew", padx=12, pady=10)
        self._boton(acciones, "Importar Excel", self.importar_excel, COLOR_VERDE, 140).pack(side="left", padx=4)
        self._boton(acciones, "Nueva planilla vacía", self.nueva_planilla, COLOR_PRIMARIO, 160).pack(side="left", padx=4)
        self._boton(acciones, "Generar mes siguiente", self.generar_mes_siguiente, COLOR_NARANJA, 170).pack(side="left", padx=4)
        self._boton(acciones, "Abrir", self.abrir_planilla, COLOR_PRIMARIO, 100).pack(side="left", padx=4)
        self._boton(acciones, "Exportar Excel", self.exportar_excel, COLOR_VERDE, 130).pack(side="right", padx=4)
        self._boton(acciones, "Exportar PDF", self.exportar_pdf, COLOR_ROJO, 120).pack(side="right", padx=4)

        self.tree_planillas = ttk.Treeview(
            marco, columns=("periodo", "categoria", "registros", "subtotal", "saldo", "descuento", "total"),
            show="headings", selectmode="extended",
        )
        columnas = (
            ("periodo", "Período", 100, "periodo"),
            ("categoria", "Categoría", 180, "texto"),
            ("registros", "Registros", 90, "numero"),
            ("subtotal", "Subtotal", 150, "numero"),
            ("saldo", "Saldo pendiente", 170, "numero"),
            ("descuento", "Descuento", 140, "numero"),
            ("total", "Total", 150, "numero"),
        )
        for clave, _titulo, ancho, _tipo in columnas:
            self.tree_planillas.column(clave, width=ancho, anchor="center")
        self._configurar_orden(self.tree_planillas, columnas)
        ctk.CTkLabel(
            marco,
            text="Podés seleccionar varias planillas con Ctrl o Shift.",
            text_color=COLOR_TEXTO_SUAVE,
            font=ctk.CTkFont(size=11),
            anchor="w",
        ).grid(row=6, column=0, columnspan=4, sticky="nw", padx=20, pady=(2, 0))
        self.lbl_saldo_general = ctk.CTkLabel(
            marco,
            text="Saldo pendiente total: Gs. 0",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXTO,
        )
        self.lbl_saldo_general.grid(row=6, column=0, columnspan=4, sticky="ne", padx=20, pady=(0,2))

        self.tree_planillas.grid(
            row=6, column=0, columnspan=4, sticky="nsew",
            padx=16, pady=(24, 8),
        )
        self.tree_planillas.bind("<Double-1>", lambda _e: self.abrir_planilla())
        self.tree_planillas.bind("<<AbrirConTeclado>>", lambda _e: self.abrir_planilla())
        self.tree_planillas.bind("<Return>", lambda _e: self.abrir_planilla())

        pie = ctk.CTkFrame(marco, fg_color="transparent")
        pie.grid(row=7, column=0, columnspan=4, sticky="ew", padx=12, pady=(4, 14))
        self._boton(pie, "Eliminar planilla", self.eliminar_planilla, COLOR_ROJO, 140).pack(side="left", padx=4)
        self._boton(pie, "Eliminar todo el mes", self.eliminar_mes, COLOR_ROJO, 160).pack(side="left", padx=4)

        self.refrescar_planillas()
        self.after_idle(self._enfocar_primera_planilla)

    def _enfocar_primera_planilla(self):
        filas = self.tree_planillas.get_children("")
        if filas:
            self.tree_planillas.selection_set(filas[0])
            self.tree_planillas.focus(filas[0])
            self.tree_planillas.see(filas[0])
        self.tree_planillas.focus_set()


    def _cambiar_periodo(self, delta):
        try:
            mes, anio = map(int, self.p_periodo.get().strip().split("-"))
        except Exception:
            mes = datetime.now().month
            anio = datetime.now().year
        mes += delta
        if mes < 1:
            mes = 12
            anio -= 1
        elif mes > 12:
            mes = 1
            anio += 1
        self.p_periodo.delete(0, "end")
        self.p_periodo.insert(0, f"{mes:02d}-{anio}")
        self.refrescar_planillas()

    def periodo_anterior(self):
        self._cambiar_periodo(-1)

    def periodo_siguiente(self):
        self._cambiar_periodo(1)


    def refrescar_planillas(self):
        self.tree_planillas.delete(*self.tree_planillas.get_children())
        planillas = sorted(
            Asociaciones.listar_planillas(config_id=self.config_id, periodo=self.p_periodo.get().strip()),
            key=lambda x: (x["periodo"][3:], x["periodo"][:2], x["categoria"]),
            reverse=True,
        )

        for p in planillas:
            t = Asociaciones.calcular_totales(p["id"])
            self.tree_planillas.insert(
                "", "end", iid=p["id"],
                values=(
                    p["periodo"],
                    p["categoria"],
                    t["cantidad"],
                    _monto(t["subtotal"]),
                    _monto(t["saldo_pendiente"]),
                    _monto(t["descuento"]),
                    _monto(t["total"]),
                ),
            )

        # Dashboard del período actualmente seleccionado.
        cantidad_planillas = len(planillas)
        cantidad_registros = 0
        cuotas_mes = 0
        saldo_mes = 0
        pendientes_mes = 0

        for planilla in planillas:
            totales = Asociaciones.calcular_totales(planilla["id"])
            cantidad_registros += totales["cantidad"]
            cuotas_mes += totales["subtotal"]
            saldo_mes += totales["saldo_pendiente"]
            pendientes_mes += totales["pendientes"]

        self.lbl_saldo_general.configure(
            text=f"Saldo pendiente del mes: {_monto(saldo_mes)}"
        )
        self.lbl_dash_planillas.configure(text=str(cantidad_planillas))
        self.lbl_dash_registros.configure(text=str(cantidad_registros))
        self.lbl_dash_subtotal.configure(text=_monto(cuotas_mes))
        self.lbl_dash_saldo.configure(text=_monto(saldo_mes))
        self.lbl_dash_pendientes.configure(text=str(pendientes_mes))


    def nueva_planilla(self):
        try:
            p = Asociaciones.guardar_planilla({
                "config_id": self.config_id,
                "periodo": self.p_periodo.get(),
                "categoria": self.p_categoria.get(),
                "descuento_manual": self.p_descuento.get() or "0",
            })
        except ValueError as error:
            messagebox.showerror("No se pudo crear", str(error), parent=self)
            return
        self.planilla_id = p["id"]
        self._mostrar_detalle()

    def importar_excel(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar planilla Excel",
            filetypes=[("Excel", "*.xlsx *.xlsm")],
            parent=self,
        )
        if not ruta:
            return
        reemplazar = messagebox.askyesno(
            "Importar Excel",
            "¿Reemplazar las planillas existentes de los períodos detectados?\n\n"
            "Elegí No para conservarlas y cancelar si ya existen.",
            parent=self,
        )
        try:
            resumen = Asociaciones.importar_excel(
                ruta, self.config_id, reemplazar_periodo=reemplazar
            )
        except (ValueError, OSError) as error:
            messagebox.showerror("No se pudo importar", str(error), parent=self)
            return
        messagebox.showinfo(
            "Importación completa",
            f"Planillas: {resumen['planillas']}\n"
            f"Registros: {resumen['registros']}\n"
            f"Períodos: {', '.join(resumen['periodos'])}",
            parent=self,
        )
        self._mostrar_local()

    def _planillas_seleccionadas(self):
        return list(self.tree_planillas.selection())

    def _planilla_seleccionada(self):
        seleccion = self._planillas_seleccionadas()
        return seleccion[0] if seleccion else None

    def abrir_planilla(self):
        pid = self._planilla_seleccionada()
        if not pid:
            messagebox.showwarning("Planilla", "Seleccioná una planilla.", parent=self)
            return
        self.planilla_id = pid
        self._mostrar_detalle()

    def generar_mes_siguiente(self):
        ids = self._planillas_seleccionadas()
        if not ids:
            messagebox.showwarning(
                "Planillas",
                "Seleccioná una o varias planillas para continuar.",
                parent=self,
            )
            return

        destinos = []
        for planilla_id in ids:
            origen = Asociaciones.obtener_planilla(planilla_id)
            destinos.append(
                f"• {origen['categoria']}: "
                f"{origen['periodo']} → "
                f"{Asociaciones.siguiente_periodo(origen['periodo'])}"
            )

        if not messagebox.askyesno(
            "Generar mes siguiente",
            (
                f"Se generarán {len(ids)} planilla(s):\n\n"
                + "\n".join(destinos)
                + "\n\nSe copiarán solamente las personas con saldo pendiente, "
                  "se aumentará la cuota y se descontará el nuevo pago."
            ),
            parent=self,
        ):
            return

        try:
            resultado = Asociaciones.generar_meses_siguientes(ids)
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo generar",
                str(error),
                parent=self,
            )
            return

        self.refrescar_planillas()

        nuevos_ids = [
            item["planilla"]["id"] for item in resultado["resultados"]
        ]
        for item_id in nuevos_ids:
            if self.tree_planillas.exists(item_id):
                self.tree_planillas.selection_add(item_id)
                self.tree_planillas.see(item_id)

        messagebox.showinfo(
            "Mes generado",
            (
                f"Planillas creadas: {resultado['planillas']}\n"
                f"Períodos: {', '.join(resultado['periodos'])}\n"
                f"Registros continuados: {resultado['continuados']}\n"
                f"Registros finalizados: {resultado['finalizados']}\n\n"
                "Las nuevas planillas quedaron seleccionadas. "
                "Podés abrir cualquiera para agregar funcionarios nuevos."
            ),
            parent=self,
        )

    def eliminar_planilla(self):
        pid = self._planilla_seleccionada()
        if not pid:
            messagebox.showwarning("Planilla", "Seleccioná una planilla.", parent=self)
            return
        if messagebox.askyesno(
            "Eliminar planilla", "¿Eliminar la planilla y todos sus registros?",
            parent=self,
        ):
            Asociaciones.eliminar_planilla(pid)
            self.refrescar_planillas()

    def eliminar_mes(self):
        periodo = self.p_periodo.get().strip()
        if not messagebox.askyesno(
            "Eliminar mes completo",
            f"¿Eliminar TODAS las planillas de {periodo} para este local?",
            parent=self,
        ):
            return
        try:
            cantidad = Asociaciones.eliminar_periodo(periodo, self.config_id)
        except ValueError as error:
            messagebox.showerror("Período inválido", str(error), parent=self)
            return
        messagebox.showinfo("Mes eliminado", f"Planillas eliminadas: {cantidad}", parent=self)
        self.refrescar_planillas()

    def exportar_excel(self):
        self._exportar("xlsx", Asociaciones.exportar_excel)

    def exportar_pdf(self):
        self._exportar("pdf", Asociaciones.exportar_pdf)

    def _exportar(self, extension, funcion):
        pid = self._planilla_seleccionada()
        if not pid:
            messagebox.showwarning("Planilla", "Seleccioná una planilla.", parent=self)
            return
        p = Asociaciones.obtener_planilla(pid)
        ruta = filedialog.asksaveasfilename(
            defaultextension=f".{extension}",
            filetypes=[(extension.upper(), f"*.{extension}")],
            initialfile=f"{p['periodo']}_{p['categoria']}.{extension}",
            parent=self,
        )
        if not ruta:
            return
        try:
            funcion(pid, ruta)
        except Exception as error:
            messagebox.showerror("No se pudo exportar", str(error), parent=self)
            return
        messagebox.showinfo("Exportación completa", f"Archivo guardado en:\n{ruta}", parent=self)

    # ------------------------------------------------------------------
    # DETALLE DE PLANILLA
    # ------------------------------------------------------------------
    def _mostrar_detalle(self):
        self.vista_actual = "detalle"
        self._limpiar_cuerpo()
        p = Asociaciones.obtener_planilla(self.planilla_id)
        config = Asociaciones.obtener_configuracion(p["config_id"])

        marco = ctk.CTkFrame(
            self.cuerpo, fg_color=COLOR_PANEL, corner_radius=14,
            border_width=1, border_color=COLOR_BORDE,
        )
        marco.grid(row=0, column=0, sticky="nsew")
        for col in range(6):
            marco.grid_columnconfigure(col, weight=1)
        marco.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            marco,
            text=f"{config['asociacion']} · {config['local']} · {p['periodo']} · {p['categoria']}",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=COLOR_TEXTO,
        ).grid(row=0, column=0, columnspan=5, sticky="w", padx=16, pady=(14, 8))
        self._boton(marco, "Volver", self._mostrar_local, COLOR_NARANJA, 100).grid(
            row=0, column=5, sticky="e", padx=16, pady=(14, 8)
        )

        self.d_legajo = self._campo(marco, "Legajo", 1, 0)
        self.d_nombre = self._campo(marco, "Nombre y apellido", 1, 1)
        self.d_cuota = self._campo(marco, "N.º cuota", 1, 2)
        self.d_total = self._campo(marco, "Total compra", 1, 3)
        self.d_monto = self._campo(marco, "Monto cuota", 1, 4)
        self.d_saldo = self._campo(marco, "Saldo", 1, 5)
        self.d_saldo.configure(state="disabled")

        # Para funcionarios nuevos, calcula automáticamente:
        # saldo = total de compra - primera cuota.
        for campo in (self.d_cuota, self.d_total, self.d_monto):
            campo.bind("<KeyRelease>", self._actualizar_saldo_nuevo)

        acciones = ctk.CTkFrame(marco, fg_color="transparent")
        acciones.grid(row=3, column=0, columnspan=6, sticky="ew", padx=12, pady=8)
        self._boton(acciones, "Nuevo", self.nuevo_detalle, COLOR_PRIMARIO, 90).pack(side="left", padx=4)
        self._boton(acciones, "Guardar", self.guardar_detalle, COLOR_VERDE, 100).pack(side="left", padx=4)
        self._boton(acciones, "Eliminar", self.eliminar_detalle, COLOR_ROJO, 100).pack(side="left", padx=4)

        self.tree_detalle = ttk.Treeview(
            marco,
            columns=("legajo", "nombre", "cuota", "total", "monto", "saldo"),
            show="headings", selectmode="browse",
        )
        columnas_detalle = (
            ("legajo", "Legajo", 100, "texto"),
            ("nombre", "Nombre y apellido", 300, "texto"),
            ("cuota", "Cuota", 80, "cuota"),
            ("total", "Total compra", 130, "numero"),
            ("monto", "Monto cuota", 130, "numero"),
            ("saldo", "Saldo", 130, "numero"),
        )
        for clave, _titulo, ancho, _tipo in columnas_detalle:
            self.tree_detalle.column(clave, width=ancho, anchor="center")
        self._configurar_orden(self.tree_detalle, columnas_detalle)
        self.tree_detalle.grid(row=4, column=0, columnspan=6, sticky="nsew", padx=16, pady=8)
        self.tree_detalle.bind("<<TreeviewSelect>>", self.seleccionar_detalle)

        self.lbl_totales = ctk.CTkLabel(
            marco, text="", font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXTO,
        )
        self.lbl_totales.grid(row=5, column=0, columnspan=6, sticky="e", padx=16, pady=(4, 14))
        self.refrescar_detalle()

    def _actualizar_saldo_nuevo(self, _evento=None):
        """Calcula el saldo solo al cargar una compra nueva en su primera cuota."""
        if self.detalle_id is not None:
            return

        try:
            cuota = self.d_cuota.get().strip()
            if not cuota or not Asociaciones.es_primera_cuota(cuota):
                return

            total = Asociaciones.convertir_entero(
                self.d_total.get(), "total de compra"
            )
            monto = Asociaciones.convertir_entero(
                self.d_monto.get(), "monto de cuota"
            )
        except ValueError:
            return

        self.d_saldo.configure(state="normal")
        self.d_saldo.delete(0, "end")
        self.d_saldo.insert(0, str(max(total - monto, 0)))
        self.d_saldo.configure(state="disabled")

    def nuevo_detalle(self):
        self.detalle_id = None
        for campo in (
            self.d_legajo, self.d_nombre, self.d_cuota,
            self.d_total, self.d_monto,
        ):
            campo.delete(0, "end")
        self.d_saldo.configure(state="normal")
        self.d_saldo.delete(0, "end")
        self.d_saldo.configure(state="disabled")

    def guardar_detalle(self):
        try:
            Asociaciones.guardar_detalle({
                "id": self.detalle_id,
                "planilla_id": self.planilla_id,
                "legajo": self.d_legajo.get(),
                "nombre": self.d_nombre.get(),
                "numero_cuota": self.d_cuota.get(),
                "total_compra": self.d_total.get(),
                "monto_cuota": self.d_monto.get(),
                "saldo_pendiente": self.d_saldo.get(),
            })
        except ValueError as error:
            messagebox.showerror("No se pudo guardar", str(error), parent=self)
            return
        self.nuevo_detalle()
        self.refrescar_detalle()

    def seleccionar_detalle(self, _evento=None):
        sel = self.tree_detalle.selection()
        if not sel:
            return
        self.detalle_id = sel[0]
        detalle = next(
            x for x in Asociaciones.listar_detalles(self.planilla_id)
            if x["id"] == self.detalle_id
        )
        self.nuevo_detalle()
        self.detalle_id = detalle["id"]
        for campo, valor in zip(
            (self.d_legajo, self.d_nombre, self.d_cuota, self.d_total, self.d_monto),
            (detalle["legajo"], detalle["nombre"], detalle["numero_cuota"],
             detalle["total_compra"], detalle["monto_cuota"]),
        ):
            campo.insert(0, str(valor))

        self.d_saldo.configure(state="normal")
        self.d_saldo.insert(0, str(detalle["saldo_pendiente"]))
        self.d_saldo.configure(state="disabled")

    def eliminar_detalle(self):
        if not self.detalle_id:
            messagebox.showwarning("Registro", "Seleccioná un registro.", parent=self)
            return
        if messagebox.askyesno("Eliminar", "¿Eliminar el registro?", parent=self):
            Asociaciones.eliminar_detalle(self.detalle_id)
            self.nuevo_detalle()
            self.refrescar_detalle()

    def refrescar_detalle(self):
        self.tree_detalle.delete(*self.tree_detalle.get_children())
        for d in Asociaciones.listar_detalles(self.planilla_id):
            self.tree_detalle.insert(
                "", "end", iid=d["id"],
                values=(
                    d["legajo"], d["nombre"], d["numero_cuota"],
                    _monto(d["total_compra"]), _monto(d["monto_cuota"]),
                    _monto(d["saldo_pendiente"]),
                ),
            )
        t = Asociaciones.calcular_totales(self.planilla_id)
        self.lbl_totales.configure(
            text=(
                f"Subtotal: {_monto(t['subtotal'])}   |   "
                f"Descuento: {_monto(t['descuento'])}   |   "
                f"Total: {_monto(t['total'])}   |   "
                f"Saldo pendiente: {_monto(t['saldo_pendiente'])}"
            )
        )


def crear_panel_asociaciones(master):
    return PanelAsociaciones(master)
