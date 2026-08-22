"""Ventana de BC Comunicaciones.

Tres columnas fijas pensadas para 1366x768: buscador y categorías a la
izquierda, lista de plantillas al centro, y a la derecha el panel de trabajo,
que alterna entre preparar un mensaje, editar una plantilla y ver los mensajes
copiados recientemente.

Toda la lógica vive en `CommunicationsUIController`; acá sólo se dibuja y se
enrutan eventos.
"""

from __future__ import annotations

from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..config import resolve_data_paths
from ..domain.models import Template
from .controller import CommunicationsUIController, friendly_error
from .theme import (
    COLOR_AMBAR,
    COLOR_BORDE,
    COLOR_FONDO,
    COLOR_PANEL,
    COLOR_PANEL_SECUNDARIO,
    COLOR_PRIMARIO,
    COLOR_PRIMARIO_HOVER,
    COLOR_ROJO,
    COLOR_ROJO_HOVER,
    COLOR_TEXTO,
    COLOR_TEXTO_SUAVE,
    COLOR_VERDE,
    COLOR_VERDE_HOVER,
)

VENTANA_ANCHO = 1366
VENTANA_ALTO = 768
ANCHO_COLUMNA_IZQUIERDA = 244
ANCHO_COLUMNA_CENTRO = 352

ATAJOS = "F2 nueva · F3 buscar · F4 recientes · F9 respaldo · F10 restaurar · Ctrl+Enter copiar · Esc volver"

ALTO_DATOS_MINIMO = 104
ALTO_DATOS_MAXIMO = 186
ALTO_FILA_DATOS = 68


def alto_datos(cantidad_variables: int) -> int:
    """Alto del bloque de variables: crece con los campos y nunca come el mensaje.

    Los campos se ubican de a dos por fila, así que el alto depende de las filas
    reales. Con muchas variables se topa y el bloque pasa a tener scroll propio.
    """
    filas = max(1, -(-int(cantidad_variables) // 2))
    return max(ALTO_DATOS_MINIMO, min(ALTO_DATOS_MAXIMO, 36 + filas * ALTO_FILA_DATOS))


def abrir_comunicaciones(ventana_padre, controller: CommunicationsUIController):
    """Abre la ventana de BC Comunicaciones sobre `ventana_padre`."""
    return VentanaComunicaciones(ventana_padre, controller)


class VentanaComunicaciones(ctk.CTkToplevel):
    def __init__(self, ventana_padre, controller: CommunicationsUIController) -> None:
        super().__init__(ventana_padre)
        self.controller = controller
        self.title("BC Comunicaciones — Biblioteca de mensajes")
        self.geometry(f"{VENTANA_ANCHO}x{VENTANA_ALTO}")
        self.minsize(1180, 700)
        self.configure(fg_color=COLOR_FONDO)

        self._categoria_actual: str = ""
        self._sucursal_actual: str | None = None
        self._solo_favoritas: bool = False
        self._ver_inactivas: bool = False
        self._resultados: list[Template] = []
        self._plantilla_actual: Template | None = None
        self._campos_variables: dict[str, ctk.CTkEntry] = {}
        self._botones_plantilla: dict[str, ctk.CTkButton] = {}
        self._modo: str = "preparar"
        self._borrador_original: Template | None = None
        self._temporizador_copiado: str | None = None

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._construir_barra_superior()
        self._construir_columna_izquierda()
        self._construir_columna_centro()
        self._construir_columna_derecha()
        self._construir_pie()
        self._registrar_atajos()

        self.after(60, self._primer_dibujado)

    # ------------------------------------------------------------------ construcción

    def _construir_barra_superior(self) -> None:
        barra = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=0, height=58)
        barra.grid(row=0, column=0, columnspan=3, sticky="ew")
        barra.grid_propagate(False)
        barra.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            barra, text="BC COMUNICACIONES", font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_TEXTO,
        ).grid(row=0, column=0, padx=(16, 20), pady=12, sticky="w")

        acciones = ctk.CTkFrame(barra, fg_color="transparent")
        acciones.grid(row=0, column=2, padx=(8, 16), pady=9, sticky="e")

        ctk.CTkLabel(acciones, text="Operador", text_color=COLOR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 6))
        self.entrada_operador = ctk.CTkEntry(acciones, width=132, placeholder_text="Tu nombre")
        self.entrada_operador.pack(side="left", padx=(0, 12))
        self.entrada_operador.bind("<FocusOut>", lambda _event: self._guardar_operador())

        for texto, comando, color in (
            ("Bandeja", self._abrir_bandeja, COLOR_VERDE),
            ("Nueva  F2", self._nueva_plantilla, COLOR_PRIMARIO),
            ("Recientes  F4", self._mostrar_recientes, COLOR_PANEL_SECUNDARIO[1]),
            ("Respaldo  F9", self._crear_respaldo, COLOR_PANEL_SECUNDARIO[1]),
            ("Restaurar  F10", self._restaurar_respaldo, COLOR_PANEL_SECUNDARIO[1]),
        ):
            ctk.CTkButton(
                acciones, text=texto, command=comando, height=32, width=112,
                fg_color=color, hover_color=COLOR_PRIMARIO_HOVER,
                font=ctk.CTkFont(size=12, weight="bold"),
            ).pack(side="left", padx=3)

    def _abrir_bandeja(self) -> None:
        from .inbox_app import InboxWindow
        InboxWindow(self, self.controller.inbox, self.controller.operator)

    def _construir_columna_izquierda(self) -> None:
        panel = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=0,
                             width=ANCHO_COLUMNA_IZQUIERDA, border_width=1, border_color=COLOR_BORDE)
        panel.grid(row=1, column=0, sticky="nsew")
        panel.grid_propagate(False)
        panel.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(panel, text="BUSCAR", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=COLOR_TEXTO_SUAVE).grid(row=0, column=0, padx=14, pady=(14, 4), sticky="w")

        self.entrada_busqueda = ctk.CTkEntry(
            panel, width=ANCHO_COLUMNA_IZQUIERDA - 28, height=34,
            placeholder_text="Escribí y buscá (F3)",
        )
        self.entrada_busqueda.grid(row=1, column=0, padx=14, sticky="ew")
        self.entrada_busqueda.bind("<KeyRelease>", lambda _event: self._refrescar_resultados())

        ctk.CTkLabel(panel, text="CATEGORÍAS", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=COLOR_TEXTO_SUAVE).grid(row=2, column=0, padx=14, pady=(16, 4), sticky="w")

        self.contenedor_categorias = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        self.contenedor_categorias.grid(row=3, column=0, padx=8, sticky="nsew")

        filtros = ctk.CTkFrame(panel, fg_color="transparent")
        filtros.grid(row=4, column=0, padx=14, pady=(8, 14), sticky="ew")

        ctk.CTkLabel(filtros, text="SUCURSAL", anchor="w", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=COLOR_TEXTO_SUAVE).pack(fill="x", pady=(0, 3))
        self.selector_sucursal = ctk.CTkOptionMenu(
            filtros, values=["Todas"], height=30, command=self._elegir_sucursal,
            fg_color=COLOR_PANEL_SECUNDARIO[1], button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
        )
        self.selector_sucursal.pack(fill="x", pady=(0, 6))

        self.var_favoritas = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            filtros, text="Sólo favoritas ★", variable=self.var_favoritas,
            command=self._cambiar_favoritas, font=ctk.CTkFont(size=12),
        ).pack(anchor="w", pady=3)

        self.var_inactivas = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            filtros, text="Ver desactivadas", variable=self.var_inactivas,
            command=self._cambiar_inactivas, font=ctk.CTkFont(size=12),
        ).pack(anchor="w", pady=3)

    def _construir_columna_centro(self) -> None:
        panel = ctk.CTkFrame(self, fg_color=COLOR_FONDO, corner_radius=0, width=ANCHO_COLUMNA_CENTRO)
        panel.grid(row=1, column=1, sticky="nsew")
        panel.grid_propagate(False)
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        self.etiqueta_resultados = ctk.CTkLabel(
            panel, text="PLANTILLAS", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.etiqueta_resultados.grid(row=0, column=0, padx=14, pady=(14, 6), sticky="w")

        self.lista_plantillas = ctk.CTkScrollableFrame(panel, fg_color=COLOR_PANEL, corner_radius=8)
        self.lista_plantillas.grid(row=1, column=0, padx=10, pady=(0, 12), sticky="nsew")
        self.lista_plantillas.grid_columnconfigure(0, weight=1)

    def _construir_columna_derecha(self) -> None:
        self.panel_derecho = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=0,
                                          border_width=1, border_color=COLOR_BORDE)
        self.panel_derecho.grid(row=1, column=2, sticky="nsew")
        self.panel_derecho.grid_columnconfigure(0, weight=1)
        self.panel_derecho.grid_rowconfigure(2, weight=1)

        encabezado = ctk.CTkFrame(self.panel_derecho, fg_color="transparent")
        encabezado.grid(row=0, column=0, padx=18, pady=(14, 2), sticky="ew")
        encabezado.grid_columnconfigure(0, weight=1)

        self.titulo_panel = ctk.CTkLabel(
            encabezado, text="Elegí una plantilla", anchor="w",
            font=ctk.CTkFont(size=17, weight="bold"), text_color=COLOR_TEXTO,
        )
        self.titulo_panel.grid(row=0, column=0, sticky="ew")

        self.boton_favorita = ctk.CTkButton(
            encabezado, text="☆", width=42, height=32, command=self._alternar_favorita,
            fg_color=COLOR_PANEL_SECUNDARIO[1], hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.boton_favorita.grid(row=0, column=1, padx=(8, 0))

        self.boton_editar = ctk.CTkButton(
            encabezado, text="Editar", width=78, height=32, command=self._editar_plantilla,
            fg_color=COLOR_PANEL_SECUNDARIO[1], hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.boton_editar.grid(row=0, column=2, padx=(6, 0))

        self.boton_activar = ctk.CTkButton(
            encabezado, text="Desactivar", width=94, height=32, command=self._alternar_activa,
            fg_color=COLOR_PANEL_SECUNDARIO[1], hover_color=COLOR_ROJO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.boton_activar.grid(row=0, column=3, padx=(6, 0))

        self.subtitulo_panel = ctk.CTkLabel(
            self.panel_derecho, text="", anchor="w",
            font=ctk.CTkFont(size=11), text_color=COLOR_TEXTO_SUAVE,
        )
        self.subtitulo_panel.grid(row=1, column=0, padx=18, pady=(0, 8), sticky="ew")

        self.cuerpo_panel = ctk.CTkFrame(self.panel_derecho, fg_color="transparent")
        self.cuerpo_panel.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="nsew")
        self.cuerpo_panel.grid_columnconfigure(0, weight=1)
        self.cuerpo_panel.grid_rowconfigure(0, weight=1)

    def _construir_pie(self) -> None:
        pie = ctk.CTkFrame(self, fg_color=COLOR_PANEL_SECUNDARIO, corner_radius=0, height=30)
        pie.grid(row=2, column=0, columnspan=3, sticky="ew")
        pie.grid_propagate(False)
        pie.grid_columnconfigure(0, weight=1)

        self.etiqueta_estado = ctk.CTkLabel(
            pie, text="Listo.", anchor="w", font=ctk.CTkFont(size=11), text_color=COLOR_TEXTO_SUAVE,
        )
        self.etiqueta_estado.grid(row=0, column=0, padx=14, sticky="w")

        # Los atajos viven en el pie: ahí entran completos sin recortarse.
        ctk.CTkLabel(
            pie, text=ATAJOS, font=ctk.CTkFont(size=11), text_color=COLOR_TEXTO_SUAVE,
        ).grid(row=0, column=1, padx=14)

        ctk.CTkLabel(
            pie, text=f"datos: {resolve_data_paths().root}", anchor="e",
            font=ctk.CTkFont(size=10), text_color=COLOR_TEXTO_SUAVE,
        ).grid(row=0, column=2, padx=14, sticky="e")

    def _registrar_atajos(self) -> None:
        self.bind("<F2>", lambda _event: self._nueva_plantilla())
        self.bind("<F3>", lambda _event: self._foco_busqueda())
        self.bind("<Control-f>", lambda _event: self._foco_busqueda())
        self.bind("<F4>", lambda _event: self._mostrar_recientes())
        self.bind("<F9>", lambda _event: self._crear_respaldo())
        self.bind("<F10>", lambda _event: self._restaurar_respaldo())
        self.bind("<Control-Return>", lambda _event: self._copiar_mensaje())
        self.bind("<Escape>", lambda _event: self._volver())

    # ------------------------------------------------------------------ ciclo de datos

    def _primer_dibujado(self) -> None:
        operador = self.controller.operator()
        if operador:
            self.entrada_operador.insert(0, operador)
        self.selector_sucursal.configure(values=["Todas", *self.controller.branch_options()])
        self._refrescar_categorias()
        self._refrescar_resultados()
        self._foco_busqueda()

    def _refrescar_categorias(self) -> None:
        for hijo in self.contenedor_categorias.winfo_children():
            hijo.destroy()
        for opcion in self.controller.category_options(include_inactive=self._ver_inactivas):
            activa = opcion.slug == self._categoria_actual
            ctk.CTkButton(
                self.contenedor_categorias,
                text=f"{opcion.name}   ({opcion.count})",
                anchor="w", height=32,
                fg_color=COLOR_PRIMARIO if activa else "transparent",
                hover_color=COLOR_PRIMARIO_HOVER,
                text_color="#FFFFFF" if activa else COLOR_TEXTO,
                font=ctk.CTkFont(size=12, weight="bold" if activa else "normal"),
                command=lambda slug=opcion.slug: self._elegir_categoria(slug),
            ).pack(fill="x", padx=2, pady=2)

    def _refrescar_resultados(self, *, seleccionar: str | None = None) -> None:
        consulta = self.entrada_busqueda.get()
        self._resultados = list(
            self.controller.search(
                consulta,
                category_slug=self._categoria_actual or None,
                branch=self._sucursal_actual,
                only_favorites=self._solo_favoritas,
                include_inactive=self._ver_inactivas,
            )
        )
        self.etiqueta_resultados.configure(text=f"PLANTILLAS  ({len(self._resultados)})")

        for hijo in self.lista_plantillas.winfo_children():
            hijo.destroy()
        self._botones_plantilla = {}

        if not self._resultados:
            ctk.CTkLabel(
                self.lista_plantillas,
                text=self.controller.empty_state_message(
                    consulta,
                    category_slug=self._categoria_actual or None,
                    only_favorites=self._solo_favoritas,
                ),
                justify="left", wraplength=ANCHO_COLUMNA_CENTRO - 60,
                text_color=COLOR_TEXTO_SUAVE, font=ctk.CTkFont(size=12),
            ).grid(row=0, column=0, padx=16, pady=20, sticky="w")
            return

        for fila, plantilla in enumerate(self._resultados):
            estrella = "★ " if plantilla.favorite else ""
            apagada = "" if plantilla.active else "  (desactivada)"
            boton = ctk.CTkButton(
                self.lista_plantillas,
                text=f"{estrella}{plantilla.title}{apagada}",
                anchor="w", height=38, corner_radius=6,
                fg_color="transparent", hover_color=COLOR_PANEL_SECUNDARIO[1],
                text_color=COLOR_TEXTO if plantilla.active else COLOR_TEXTO_SUAVE,
                font=ctk.CTkFont(size=13),
                command=lambda item=plantilla: self._abrir_plantilla(item.id),
            )
            boton.grid(row=fila, column=0, sticky="ew", padx=6, pady=1)
            self._botones_plantilla[plantilla.id] = boton

        objetivo = seleccionar or (self._plantilla_actual.id if self._plantilla_actual else None)
        if objetivo and objetivo in self._botones_plantilla:
            self._marcar_seleccion(objetivo)

    def _marcar_seleccion(self, template_id: str) -> None:
        for identificador, boton in self._botones_plantilla.items():
            elegido = identificador == template_id
            boton.configure(
                fg_color=COLOR_PANEL_SECUNDARIO[1] if elegido else "transparent",
                font=ctk.CTkFont(size=13, weight="bold" if elegido else "normal"),
            )

    # ------------------------------------------------------------------ filtros

    def _elegir_categoria(self, slug: str) -> None:
        self._categoria_actual = slug
        self._refrescar_categorias()
        self._refrescar_resultados()

    def _elegir_sucursal(self, value: str) -> None:
        self._sucursal_actual = None if value == "Todas" else value
        self._refrescar_resultados()

    def _cambiar_favoritas(self) -> None:
        self._solo_favoritas = bool(self.var_favoritas.get())
        self._refrescar_resultados()

    def _cambiar_inactivas(self) -> None:
        self._ver_inactivas = bool(self.var_inactivas.get())
        self._refrescar_categorias()
        self._refrescar_resultados()

    def _foco_busqueda(self) -> None:
        self.entrada_busqueda.focus_set()
        self.entrada_busqueda.select_range(0, "end")

    # ------------------------------------------------------------------ preparar mensaje

    def _cancelar_aviso_copiado(self) -> None:
        """Apaga el temporizador de la confirmación de copiado, si hay uno vivo.

        Sin esto, el temporizador de un copiado anterior borraría la confirmación
        de uno nuevo, o intentaría escribir sobre una etiqueta ya destruida al
        cambiar de plantilla.
        """
        if self._temporizador_copiado is None:
            return
        try:
            self.after_cancel(self._temporizador_copiado)
        except Exception:
            pass
        self._temporizador_copiado = None

    def _ocultar_aviso_copiado(self) -> None:
        self._temporizador_copiado = None
        try:
            self.etiqueta_copiado.configure(text="")
        except Exception:
            pass

    def _limpiar_cuerpo(self) -> None:
        self._cancelar_aviso_copiado()
        for hijo in self.cuerpo_panel.winfo_children():
            hijo.destroy()
        self._campos_variables = {}

    def _abrir_plantilla(self, template_id: str) -> None:
        if not self._confirmar_descarte():
            return
        try:
            formulario = self.controller.open_template(template_id)
        except Exception as error:  # noqa: BLE001 - traducido a mensaje de usuario
            self._avisar_error(error)
            return

        self._plantilla_actual = formulario.template
        self._modo = "preparar"
        self._borrador_original = None
        self._marcar_seleccion(template_id)
        self._dibujar_preparacion(formulario)

    def _dibujar_preparacion(self, formulario) -> None:
        plantilla = formulario.template
        self._limpiar_cuerpo()
        self.titulo_panel.configure(text=plantilla.title)
        self.subtitulo_panel.configure(
            text=f"{self.controller.library.category_name(plantilla.category_slug)}"
                 + (f"   ·   {plantilla.branch}" if plantilla.branch else "   ·   Todas las sucursales")
                 + f"   ·   usada {plantilla.usage_count} veces"
                 + ("" if plantilla.active else "   ·   DESACTIVADA")
        )
        self.boton_favorita.configure(text="★" if plantilla.favorite else "☆")
        self.boton_editar.configure(text="Editar", command=self._editar_plantilla)
        self.boton_activar.configure(text="Desactivar" if plantilla.active else "Activar")
        for boton in (self.boton_favorita, self.boton_editar, self.boton_activar):
            boton.configure(state="normal")

        contenedor = self.cuerpo_panel
        contenedor.grid_rowconfigure(0, weight=0)
        contenedor.grid_rowconfigure(1, weight=1)

        marco_datos = ctk.CTkScrollableFrame(
            contenedor, fg_color=COLOR_PANEL_SECUNDARIO, corner_radius=8,
            height=alto_datos(len(formulario.specs)),
            label_text="DATOS A COMPLETAR",
            label_font=ctk.CTkFont(size=11, weight="bold"),
        )
        marco_datos.grid(row=0, column=0, sticky="ew", padx=6, pady=(0, 8))
        marco_datos.grid_columnconfigure(1, weight=1)
        marco_datos.grid_columnconfigure(3, weight=1)

        if not formulario.specs:
            ctk.CTkLabel(
                marco_datos, text="Esta plantilla no necesita datos: ya está lista para copiar.",
                text_color=COLOR_TEXTO_SUAVE, font=ctk.CTkFont(size=12),
            ).grid(row=0, column=0, columnspan=4, padx=10, pady=10, sticky="w")
        else:
            # Dos columnas de campos para que entren sin scroll en 1366x768.
            for indice, spec in enumerate(formulario.specs):
                fila, columna = divmod(indice, 2)
                ctk.CTkLabel(
                    marco_datos, text=spec.label, anchor="w",
                    font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXTO_SUAVE,
                ).grid(row=fila * 2, column=columna * 2, padx=(10, 6), pady=(8, 0), sticky="w")
                campo = ctk.CTkEntry(
                    marco_datos, height=32, placeholder_text=spec.example or spec.label,
                )
                campo.grid(row=fila * 2 + 1, column=columna * 2, columnspan=2,
                           padx=(10, 12), pady=(0, 6), sticky="ew")
                campo.bind("<KeyRelease>", lambda _event: self._refrescar_vista_previa())
                campo.bind("<Return>", lambda _event: self._foco_siguiente_campo())
                self._campos_variables[spec.name] = campo

        marco_mensaje = ctk.CTkFrame(contenedor, fg_color="transparent")
        marco_mensaje.grid(row=1, column=0, sticky="nsew", padx=6)
        marco_mensaje.grid_columnconfigure(0, weight=1)
        marco_mensaje.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            marco_mensaje, text="MENSAJE FINAL  (podés ajustarlo antes de copiar)", anchor="w",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXTO_SUAVE,
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.caja_mensaje = ctk.CTkTextbox(
            marco_mensaje, fg_color=COLOR_PANEL_SECUNDARIO, wrap="word",
            font=ctk.CTkFont(size=13), border_width=1, border_color=COLOR_BORDE,
        )
        self.caja_mensaje.grid(row=1, column=0, sticky="nsew")
        self.caja_mensaje.bind("<KeyRelease>", lambda _event: self._refrescar_estado_copiado())

        self.etiqueta_faltantes = ctk.CTkLabel(
            marco_mensaje, text="", anchor="w", justify="left",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_AMBAR,
        )
        self.etiqueta_faltantes.grid(row=2, column=0, sticky="ew", pady=(6, 2))

        acciones = ctk.CTkFrame(marco_mensaje, fg_color="transparent")
        acciones.grid(row=3, column=0, sticky="ew", pady=(2, 6))
        acciones.grid_columnconfigure(1, weight=1)

        self.boton_copiar = ctk.CTkButton(
            acciones, text="COPIAR MENSAJE   Ctrl+Enter", height=44, width=248,
            command=self._copiar_mensaje, fg_color=COLOR_VERDE, hover_color=COLOR_VERDE_HOVER,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.boton_copiar.grid(row=0, column=0, sticky="w")

        self.etiqueta_copiado = ctk.CTkLabel(
            acciones, text="", anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_VERDE,
        )
        self.etiqueta_copiado.grid(row=0, column=1, padx=14, sticky="w")

        ctk.CTkButton(
            acciones, text="Limpiar datos", height=44, width=124, command=self._limpiar_datos,
            fg_color=COLOR_PANEL_SECUNDARIO[1], hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=2, sticky="e")

        self._texto_generado = ""
        self._refrescar_vista_previa()
        if self._campos_variables:
            next(iter(self._campos_variables.values())).focus_set()

    def _valores_actuales(self) -> dict[str, str]:
        return {nombre: campo.get() for nombre, campo in self._campos_variables.items()}

    def _texto_actual(self) -> str:
        return self.caja_mensaje.get("1.0", "end").strip()

    def _texto_editado_a_mano(self) -> bool:
        """Compara el contenido real contra lo último que generó la vista previa.

        Antes alcanzaba con apoyar una flecha o un Tab sobre el recuadro para
        congelar la vista previa: el mensaje dejaba de actualizarse mientras el
        operador seguía corrigiendo los campos, y se copiaba el texto viejo.
        """
        return self._texto_actual() != str(getattr(self, "_texto_generado", "")).strip()

    def _refrescar_vista_previa(self) -> None:
        if self._plantilla_actual is None or self._modo != "preparar":
            return
        if not self._texto_editado_a_mano():
            vista = self.controller.preview(self._plantilla_actual, self._valores_actuales())
            self.caja_mensaje.delete("1.0", "end")
            self.caja_mensaje.insert("1.0", vista.text)
            self._texto_generado = vista.text
        self._refrescar_estado_copiado()

    def _refrescar_estado_copiado(self) -> None:
        """Habilita COPIAR según el texto que realmente se va a copiar."""
        if self._plantilla_actual is None or self._modo != "preparar":
            return
        texto = self._texto_actual()
        if not texto:
            self.etiqueta_faltantes.configure(text="El mensaje está vacío.", text_color=COLOR_AMBAR)
            self.boton_copiar.configure(state="disabled")
            return
        pendientes = self.controller.pending_in_text(self._plantilla_actual, texto)
        if pendientes:
            self.etiqueta_faltantes.configure(
                text="Faltan completar: " + ", ".join(pendientes), text_color=COLOR_AMBAR,
            )
            self.boton_copiar.configure(state="disabled")
        else:
            self.etiqueta_faltantes.configure(
                text="Mensaje completo, listo para copiar.", text_color=COLOR_VERDE,
            )
            self.boton_copiar.configure(state="normal")

    def _foco_siguiente_campo(self) -> None:
        campos = list(self._campos_variables.values())
        actual = self.focus_get()
        if actual in campos:
            indice = campos.index(actual)
            if indice + 1 < len(campos):
                campos[indice + 1].focus_set()
                return
        self.caja_mensaje.focus_set()

    def _limpiar_datos(self) -> None:
        for campo in self._campos_variables.values():
            campo.delete(0, "end")
        self._cancelar_aviso_copiado()
        self.etiqueta_copiado.configure(text="")
        self.caja_mensaje.delete("1.0", "end")
        self._texto_generado = ""
        self._refrescar_vista_previa()

    def _copiar_mensaje(self) -> None:
        if self._plantilla_actual is None or self._modo != "preparar":
            return
        texto = self._texto_actual()
        # Ctrl+Enter llega acá aunque el botón esté deshabilitado: mismo criterio
        # para el atajo y para el botón, y un aviso que coincide con la pantalla.
        pendientes = self.controller.pending_in_text(self._plantilla_actual, texto) if texto else ()
        if not texto or pendientes:
            self._refrescar_estado_copiado()
            detalle = (
                "El mensaje está vacío." if not texto
                else "Faltan completar estos datos: " + ", ".join(pendientes)
            )
            self._estado(f"Faltan datos: {detalle}")
            messagebox.showwarning("Faltan datos", detalle, parent=self)
            return
        try:
            mensaje = self.controller.copy_message(
                self._plantilla_actual.id,
                self._valores_actuales(),
                final_text=texto,
                operator=self.entrada_operador.get(),
            )
        except Exception as error:  # noqa: BLE001 - traducido a mensaje de usuario
            self._avisar_error(error)
            return

        self.etiqueta_copiado.configure(text="✓ Copiado al portapapeles")
        self._estado(f"Mensaje «{mensaje.template_title}» copiado y registrado.")
        self._cancelar_aviso_copiado()
        self._temporizador_copiado = self.after(4000, self._ocultar_aviso_copiado)
        self._plantilla_actual = self.controller.library.get(self._plantilla_actual.id)
        self._refrescar_resultados(seleccionar=self._plantilla_actual.id)
        self.subtitulo_panel.configure(
            text=f"{self.controller.library.category_name(self._plantilla_actual.category_slug)}"
                 f"   ·   usada {self._plantilla_actual.usage_count} veces"
        )

    def _alternar_favorita(self) -> None:
        if self._plantilla_actual is None:
            return
        self._plantilla_actual = self.controller.toggle_favorite(self._plantilla_actual.id)
        self.boton_favorita.configure(text="★" if self._plantilla_actual.favorite else "☆")
        self._estado(
            "Agregada a favoritas." if self._plantilla_actual.favorite else "Quitada de favoritas."
        )
        self._refrescar_resultados(seleccionar=self._plantilla_actual.id)

    def _alternar_activa(self) -> None:
        if self._plantilla_actual is None:
            return
        objetivo = not self._plantilla_actual.active
        if not objetivo and not messagebox.askyesno(
            "Desactivar plantilla",
            f"«{self._plantilla_actual.title}» dejará de aparecer en la búsqueda.\n\n"
            "No se borra: podés volver a activarla cuando quieras. ¿Desactivar?",
            parent=self,
        ):
            return
        self._plantilla_actual = self.controller.set_active(self._plantilla_actual.id, objetivo)
        self.boton_activar.configure(text="Desactivar" if objetivo else "Activar")
        self._estado("Plantilla activada." if objetivo else "Plantilla desactivada.")
        self._refrescar_categorias()
        self._refrescar_resultados(seleccionar=self._plantilla_actual.id)
        self._abrir_plantilla(self._plantilla_actual.id)

    # ------------------------------------------------------------------ administración

    def _nueva_plantilla(self) -> None:
        if not self._confirmar_descarte():
            return
        self._dibujar_editor(None)

    def _editar_plantilla(self) -> None:
        if self._plantilla_actual is None:
            self._estado("Elegí primero una plantilla de la lista.")
            return
        self._dibujar_editor(self._plantilla_actual)

    def _dibujar_editor(self, plantilla: Template | None) -> None:
        self._modo = "editar"
        self._borrador_original = plantilla
        self._limpiar_cuerpo()

        self.titulo_panel.configure(text="Nueva plantilla" if plantilla is None else "Editar plantilla")
        self.subtitulo_panel.configure(
            text="Escribí las variables entre llaves dobles, por ejemplo {{cliente}} o {{fecha}}."
        )
        for boton in (self.boton_favorita, self.boton_editar, self.boton_activar):
            boton.configure(state="disabled")

        borrador = self.controller.draft_from(plantilla, default_category=self._categoria_actual)

        marco = ctk.CTkFrame(self.cuerpo_panel, fg_color="transparent")
        marco.grid(row=0, column=0, sticky="nsew", padx=6)
        marco.grid_columnconfigure(0, weight=1)
        marco.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(marco, text="TÍTULO", anchor="w", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=COLOR_TEXTO_SUAVE).grid(row=0, column=0, sticky="w")
        self.editor_titulo = ctk.CTkEntry(marco, height=34, placeholder_text="Ej.: Pedido listo para retirar")
        self.editor_titulo.grid(row=1, column=0, sticky="ew", pady=(2, 8))
        self.editor_titulo.insert(0, borrador["title"])

        fila = ctk.CTkFrame(marco, fg_color="transparent")
        fila.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        fila.grid_columnconfigure(0, weight=1)
        fila.grid_columnconfigure(1, weight=1)

        categorias = list(self.controller.library.list_categories())
        self._nombres_categoria = {categoria.name: categoria.slug for categoria in categorias}
        nombre_actual = next(
            (categoria.name for categoria in categorias if categoria.slug == borrador["category_slug"]),
            categorias[0].name if categorias else "",
        )
        izquierda = ctk.CTkFrame(fila, fg_color="transparent")
        izquierda.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        izquierda.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(izquierda, text="CATEGORÍA", anchor="w", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=COLOR_TEXTO_SUAVE).grid(row=0, column=0, sticky="w")
        self.editor_categoria = ctk.CTkOptionMenu(
            izquierda, values=list(self._nombres_categoria) or ["General"], height=34,
            fg_color=COLOR_PANEL_SECUNDARIO[1], button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
        )
        self.editor_categoria.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        if nombre_actual:
            self.editor_categoria.set(nombre_actual)

        derecha = ctk.CTkFrame(fila, fg_color="transparent")
        derecha.grid(row=0, column=1, sticky="ew")
        derecha.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(derecha, text="PALABRAS CLAVE  (para buscarla más rápido)", anchor="w",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=COLOR_TEXTO_SUAVE).grid(row=0, column=0, sticky="w")
        self.editor_claves = ctk.CTkEntry(derecha, height=34, placeholder_text="retiro listo entrega")
        self.editor_claves.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        self.editor_claves.insert(0, borrador["keywords"])

        ctk.CTkLabel(derecha, text="SUCURSAL  (vacío = todas)", anchor="w",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=COLOR_TEXTO_SUAVE).grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.editor_sucursal = ctk.CTkEntry(derecha, height=34, placeholder_text="Ej.: Casa Central")
        self.editor_sucursal.grid(row=3, column=0, sticky="ew", pady=(2, 0))
        self.editor_sucursal.insert(0, borrador["branch"])

        ctk.CTkLabel(marco, text="MENSAJE", anchor="w", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=COLOR_TEXTO_SUAVE).grid(row=3, column=0, sticky="w")
        self.editor_cuerpo = ctk.CTkTextbox(
            marco, fg_color=COLOR_PANEL_SECUNDARIO, wrap="word", font=ctk.CTkFont(size=13),
            border_width=1, border_color=COLOR_BORDE,
        )
        self.editor_cuerpo.grid(row=4, column=0, sticky="nsew", pady=(2, 6))
        marco.grid_rowconfigure(4, weight=1)
        self.editor_cuerpo.insert("1.0", borrador["body"])
        self.editor_cuerpo.bind("<KeyRelease>", lambda _event: self._refrescar_variables_detectadas())

        self.etiqueta_variables = ctk.CTkLabel(
            marco, text="", anchor="w", justify="left",
            font=ctk.CTkFont(size=11), text_color=COLOR_TEXTO_SUAVE,
        )
        self.etiqueta_variables.grid(row=5, column=0, sticky="ew", pady=(0, 4))

        acciones = ctk.CTkFrame(marco, fg_color="transparent")
        acciones.grid(row=6, column=0, sticky="ew", pady=(2, 8))

        self.var_editor_activa = ctk.BooleanVar(value=bool(borrador["active"]))
        ctk.CTkCheckBox(acciones, text="Activa", variable=self.var_editor_activa,
                        font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 16))

        ctk.CTkButton(
            acciones, text="GUARDAR", height=40, width=150, command=self._guardar_editor,
            fg_color=COLOR_VERDE, hover_color=COLOR_VERDE_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left")

        ctk.CTkButton(
            acciones, text="Cancelar", height=40, width=110, command=self._volver,
            fg_color=COLOR_PANEL_SECUNDARIO[1], hover_color=COLOR_ROJO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=8)

        self.editor_titulo.focus_set()
        self._refrescar_variables_detectadas()

    def _borrador_editor(self) -> dict:
        nombre = self.editor_categoria.get()
        return {
            "title": self.editor_titulo.get(),
            "body": self.editor_cuerpo.get("1.0", "end").strip(),
            "category_slug": self._nombres_categoria.get(nombre, nombre),
            "keywords": self.editor_claves.get(),
            "branch": self.editor_sucursal.get(),
            "active": bool(self.var_editor_activa.get()),
        }

    def _refrescar_variables_detectadas(self) -> None:
        from ..domain.models import extract_variables, humanize_variable

        detectadas = extract_variables(self.editor_cuerpo.get("1.0", "end"))
        if detectadas:
            texto = "Variables detectadas: " + ", ".join(humanize_variable(nombre) for nombre in detectadas)
        else:
            texto = "Sin variables. Escribí {{cliente}} donde quieras completar un dato al usarla."
        self.etiqueta_variables.configure(text=texto)

    def _guardar_editor(self) -> None:
        borrador = self._borrador_editor()
        problemas = self.controller.validate_draft(borrador)
        if problemas:
            messagebox.showwarning("Faltan datos", "\n".join(problemas), parent=self)
            return
        try:
            plantilla = self.controller.save_template(
                borrador,
                template_id=self._borrador_original.id if self._borrador_original else None,
            )
        except Exception as error:  # noqa: BLE001 - traducido a mensaje de usuario
            self._avisar_error(error)
            return

        self._estado(f"Plantilla «{plantilla.title}» guardada.")
        self._modo = "preparar"
        self._borrador_original = None
        self._plantilla_actual = plantilla
        self._refrescar_categorias()
        self._refrescar_resultados(seleccionar=plantilla.id)
        self._abrir_plantilla(plantilla.id)

    def _confirmar_descarte(self) -> bool:
        """Impide perder cambios sin querer al salir del editor."""
        if self._modo != "editar":
            return True
        if not self.controller.has_unsaved_changes(self._borrador_original, self._borrador_editor()):
            return True
        return messagebox.askyesno(
            "Cambios sin guardar",
            "Tenés cambios sin guardar en esta plantilla.\n\n¿Querés descartarlos?",
            parent=self,
        )

    def _volver(self) -> None:
        if not self._confirmar_descarte():
            return
        self._modo = "preparar"
        self._borrador_original = None
        if self._plantilla_actual is not None:
            self._abrir_plantilla(self._plantilla_actual.id)
        else:
            self._limpiar_cuerpo()
            self.titulo_panel.configure(text="Elegí una plantilla")
            self.subtitulo_panel.configure(text="")

    # ------------------------------------------------------------------ recientes

    def _mostrar_recientes(self) -> None:
        if not self._confirmar_descarte():
            return
        self._modo = "recientes"
        self._limpiar_cuerpo()
        self.titulo_panel.configure(text="Mensajes copiados recientemente")
        self.subtitulo_panel.configure(text="Los últimos mensajes preparados desde esta computadora. Esc para volver.")
        for boton in (self.boton_favorita, self.boton_editar, self.boton_activar):
            boton.configure(state="disabled")

        lista = ctk.CTkScrollableFrame(self.cuerpo_panel, fg_color=COLOR_PANEL_SECUNDARIO, corner_radius=8)
        lista.grid(row=0, column=0, sticky="nsew", padx=6, pady=(0, 8))
        lista.grid_columnconfigure(0, weight=1)

        recientes = list(self.controller.recent(30))
        if not recientes:
            ctk.CTkLabel(
                lista,
                text="Todavía no copiaste ningún mensaje.\n"
                     "Abrí una plantilla, completá los datos y tocá COPIAR MENSAJE.",
                justify="left", text_color=COLOR_TEXTO_SUAVE, font=ctk.CTkFont(size=12),
            ).grid(row=0, column=0, padx=16, pady=18, sticky="w")
            return

        for fila, mensaje in enumerate(recientes):
            tarjeta = ctk.CTkFrame(lista, fg_color=COLOR_PANEL, corner_radius=6)
            tarjeta.grid(row=fila, column=0, sticky="ew", padx=6, pady=3)
            tarjeta.grid_columnconfigure(0, weight=1)
            marca = mensaje.prepared_at.astimezone().strftime("%d/%m %H:%M")
            quien = f" · {mensaje.operator}" if mensaje.operator else ""
            editado = " · editado a mano" if mensaje.manually_edited else ""
            ctk.CTkLabel(
                tarjeta, text=f"{marca}{quien} · {mensaje.template_title}{editado}", anchor="w",
                font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXTO_SUAVE,
            ).grid(row=0, column=0, padx=10, pady=(6, 0), sticky="ew")
            ctk.CTkLabel(
                tarjeta, text=mensaje.summary, anchor="w", justify="left",
                font=ctk.CTkFont(size=12), text_color=COLOR_TEXTO,
            ).grid(row=1, column=0, padx=10, pady=(0, 6), sticky="ew")
            ctk.CTkButton(
                tarjeta, text="Copiar de nuevo", width=124, height=28,
                fg_color=COLOR_PANEL_SECUNDARIO[1], hover_color=COLOR_PRIMARIO_HOVER,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda texto=mensaje.final_text: self._copiar_texto_directo(texto),
            ).grid(row=0, column=1, rowspan=2, padx=10)

    def _copiar_texto_directo(self, texto: str) -> None:
        clipboard = self.controller.preparation.clipboard
        if clipboard is None:
            return
        clipboard.copy(texto)
        self._estado("Mensaje copiado nuevamente al portapapeles.")

    # ------------------------------------------------------------------ respaldo

    def _crear_respaldo(self) -> None:
        try:
            destino = self.controller.create_backup("manual")
        except Exception as error:  # noqa: BLE001 - traducido a mensaje de usuario
            self._avisar_error(error)
            return
        self._estado(f"Respaldo creado: {destino.name}")
        messagebox.showinfo(
            "Respaldo creado",
            f"Se guardó una copia de seguridad en:\n\n{destino}",
            parent=self,
        )

    def _restaurar_respaldo(self) -> None:
        # Restaurar reconstruye el panel: si hay un borrador abierto, se perdería.
        if not self._confirmar_descarte():
            return
        inicial = self.controller.list_backups()
        archivo = filedialog.askopenfilename(
            parent=self,
            title="Elegí la copia de seguridad a restaurar",
            initialdir=str(inicial[0].parent) if inicial else None,
            filetypes=[("Copias de BC Comunicaciones", "*.sqlite3"), ("Todos los archivos", "*.*")],
        )
        if not archivo:
            return
        if not messagebox.askyesno(
            "Restaurar copia",
            "Se van a reemplazar las plantillas y el historial actuales por los de la copia elegida.\n\n"
            "Antes de reemplazar, guardamos automáticamente una copia de lo que tenés ahora.\n\n"
            "¿Continuar?",
            parent=self,
        ):
            return
        try:
            resultado = self.controller.restore_backup(archivo)
        except Exception as error:  # noqa: BLE001 - traducido a mensaje de usuario
            self._avisar_error(error)
            return

        self._plantilla_actual = None
        self._modo = "preparar"
        self._limpiar_cuerpo()
        self.titulo_panel.configure(text="Elegí una plantilla")
        self.subtitulo_panel.configure(text="")
        self._refrescar_categorias()
        self._refrescar_resultados()
        self._estado(f"Restauración completa: {resultado.templates} plantillas.")
        messagebox.showinfo(
            "Restauración completa",
            f"Se restauraron {resultado.templates} plantillas y "
            f"{resultado.prepared_messages} mensajes del historial.\n\n"
            f"Tu estado anterior quedó guardado en:\n{resultado.safety_backup}",
            parent=self,
        )

    # ------------------------------------------------------------------ auxiliares

    def _guardar_operador(self) -> None:
        self.controller.set_operator(self.entrada_operador.get())

    def _estado(self, texto: str) -> None:
        self.etiqueta_estado.configure(text=texto)

    def _avisar_error(self, error: Exception) -> None:
        titulo, detalle = friendly_error(error)
        self._estado(f"{titulo}: {detalle}")
        messagebox.showwarning(titulo, detalle, parent=self)
