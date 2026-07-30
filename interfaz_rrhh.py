"""Interfaz gráfica de Recursos Humanos para BC Gestión.

Usa los mismos archivos y reglas de Funcionarios.py, Novedades.py y
Liquidaciones.py. No migra ni duplica los datos existentes.
"""

from datetime import datetime
import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

import Funcionarios
import Liquidaciones
import Novedades
from datos import guardar_datos, leer_datos


COLOR_FONDO = ("#F4F7FB", "#0B1220")
COLOR_PANEL = ("#FFFFFF", "#131D2E")
COLOR_BORDE = ("#DCE4EE", "#26354A")
COLOR_TEXTO = ("#182230", "#F4F7FB")
COLOR_TEXTO_SUAVE = ("#617084", "#9CAFC5")
COLOR_PRIMARIO = "#246BFD"
COLOR_PRIMARIO_HOVER = "#1855D6"
COLOR_VERDE = "#18A874"
COLOR_ROJO = "#E25555"
COLOR_NARANJA = "#E99A35"


def limpiar_texto(texto, nombre, obligatorio=True):
    valor = texto.strip()

    if obligatorio and not valor:
        raise ValueError(f"Completá el campo {nombre}.")

    if "|" in valor or "\n" in valor or "\r" in valor:
        raise ValueError(
            f"El campo {nombre} contiene un carácter no permitido."
        )

    return valor


def convertir_monto(texto, permitir_cero=False):
    valor = (
        texto.strip()
        .replace(".", "")
        .replace(",", "")
        .replace(" ", "")
    )

    if not valor.isdigit():
        raise ValueError("Ingresá un monto válido usando números.")

    monto = int(valor)

    if monto < 0 or (monto == 0 and not permitir_cero):
        raise ValueError("El monto debe ser mayor que cero.")

    return monto


def validar_fecha(texto, nombre="fecha"):
    valor = texto.strip()

    try:
        return datetime.strptime(valor, "%d-%m-%Y")
    except ValueError as error:
        raise ValueError(
            f"La {nombre} debe tener formato DD-MM-AAAA."
        ) from error


def validar_periodo(texto):
    valor = texto.strip()

    try:
        return datetime.strptime(valor, "%m-%Y")
    except ValueError as error:
        raise ValueError(
            "El período debe tener formato MM-AAAA."
        ) from error


def formatear_monto(monto):
    return f"{int(monto):,}".replace(",", ".")


def configurar_treeview():
    estilo = ttk.Style()

    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass

    estilo.configure(
        "BCTree.Treeview",
        rowheight=30,
        font=("Segoe UI", 10),
    )
    estilo.configure(
        "BCTree.Treeview.Heading",
        font=("Segoe UI", 10, "bold"),
    )


class VentanaRecursosHumanos(ctk.CTkFrame):
    def __init__(self, master, pestana_inicial):
        super().__init__(
            master,
            fg_color=COLOR_FONDO,
            corner_radius=0,
        )

        self.habilitar_navegacion_tab()

        self.indice_funcionario = None
        self.indice_novedad = None
        self.indice_liquidacion = None
        self.mapa_funcionarios = {}

        configurar_treeview()

        encabezado = ctk.CTkFrame(
            self,
            fg_color=COLOR_PANEL,
            corner_radius=0,
            height=72,
        )
        encabezado.pack(fill="x")
        encabezado.pack_propagate(False)

        ctk.CTkLabel(
            encabezado,
            text="Recursos Humanos",
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=23, weight="bold"),
        ).pack(side="left", padx=26)

        ctk.CTkLabel(
            encabezado,
            text="BC Inversiones EAS",
            text_color=COLOR_TEXTO_SUAVE,
            font=ctk.CTkFont(size=13),
        ).pack(side="right", padx=26)

        self.pestanas = ctk.CTkTabview(
            self,
            fg_color=COLOR_FONDO,
            segmented_button_selected_color=COLOR_PRIMARIO,
            segmented_button_selected_hover_color=COLOR_PRIMARIO_HOVER,
        )
        self.pestanas.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=(12, 18),
        )

        for nombre in [
            "Funcionarios",
            "Novedades",
            "Liquidaciones",
            "Salario mínimo",
        ]:
            self.pestanas.add(nombre)

        self.construir_funcionarios()
        self.construir_novedades()
        self.construir_liquidaciones()
        self.construir_salario_minimo()
        self.actualizar_todo()

        equivalencias = {
            "Gestión de funcionarios": "Funcionarios",
            "Novedades": "Novedades",
            "Liquidaciones": "Liquidaciones",
            "Salario mínimo": "Salario mínimo",
        }
        self.pestanas.set(
            equivalencias.get(pestana_inicial, "Funcionarios")
        )

        

    def habilitar_navegacion_tab(self):
        """Activa una navegación de teclado continua y contextual."""
        self.bind(
            "<Tab>",
            lambda evento: self.mover_foco_formulario(evento, 1),
            add="+",
        )
        self.bind(
            "<Shift-Tab>",
            lambda evento: self.mover_foco_formulario(evento, -1),
            add="+",
        )
        self.bind(
            "<ISO_Left_Tab>",
            lambda evento: self.mover_foco_formulario(evento, -1),
            add="+",
        )
        for secuencia, direccion in [
            ("<Up>", "arriba"),
            ("<Down>", "abajo"),
            ("<Left>", "izquierda"),
            ("<Right>", "derecha"),
        ]:
            self.bind(
                secuencia,
                lambda evento, sentido=direccion: (
                    self.manejar_flecha(evento, sentido)
                ),
                add="+",
            )

    def controles_editables_visibles(self):
        """Devuelve controles útiles visibles en su orden de creación."""
        controles = []
        tipos_navegables = (
            ctk.CTkEntry,
            ctk.CTkComboBox,
            ctk.CTkOptionMenu,
            ctk.CTkTabview,
            ttk.Treeview,
        )

        def recorrer(elemento):
            for hijo in elemento.winfo_children():
                if isinstance(hijo, tipos_navegables):
                    try:
                        estado = str(hijo.cget("state")).lower()
                    except (AttributeError, ValueError):
                        estado = "normal"

                    if estado != "disabled" and hijo.winfo_viewable():
                        controles.append(hijo)

                recorrer(hijo)

        recorrer(self)
        return controles

    @staticmethod
    def control_con_foco_actual(widget, controles, limite):
        """Relaciona el control interno de CustomTkinter con su campo."""
        actual = widget

        while actual is not None:
            if actual in controles:
                return actual

            if actual == limite:
                break

            actual = getattr(actual, "master", None)

        return None

    @staticmethod
    def enfocar_control(control):
        """Coloca el cursor en la parte editable real del control."""
        entrada_interna = getattr(control, "_entry", None)

        if entrada_interna is not None:
            entrada_interna.focus_set()
        else:
            control.focus_set()

    def mover_foco_formulario(self, evento, direccion):
        """Recorre los controles y vuelve al inicio al llegar al final."""
        controles = self.controles_editables_visibles()

        if not controles:
            return None

        actual = self.control_con_foco_actual(
            evento.widget,
            controles,
            self,
        )

        if actual is None:
            destino = controles[0] if direccion > 0 else controles[-1]
        else:
            indice = controles.index(actual)
            nuevo_indice = (indice + direccion) % len(controles)
            destino = controles[nuevo_indice]

        self.enfocar_control(destino)
        return "break"

    @staticmethod
    def filas_visibles_treeview(tabla, padre=""):
        """Obtiene las filas visibles de una tabla."""
        filas = []
        for item in tabla.get_children(padre):
            filas.append(item)
            if tabla.item(item, "open"):
                filas.extend(
                    VentanaRecursosHumanos.filas_visibles_treeview(
                        tabla,
                        item,
                    )
                )
        return filas

    @staticmethod
    def mover_seleccion_treeview(tabla, paso):
        """Mueve la selección una fila y hace ciclo en los extremos."""
        filas = VentanaRecursosHumanos.filas_visibles_treeview(tabla)
        if not filas:
            return

        seleccion = tabla.selection()
        actual = seleccion[0] if seleccion else None
        if actual not in filas:
            destino = filas[0] if paso > 0 else filas[-1]
        else:
            destino = filas[(filas.index(actual) + paso) % len(filas)]

        tabla.selection_set(destino)
        tabla.focus(destino)
        tabla.see(destino)
        tabla.event_generate("<<TreeviewSelect>>")

    @staticmethod
    def cambiar_opcion(control, paso):
        """Cambia una opción de ComboBox u OptionMenu."""
        try:
            valores = list(control.cget("values"))
        except (AttributeError, TypeError, ValueError):
            return False

        if not valores:
            return False

        actual = control.get()
        try:
            indice = valores.index(actual)
        except ValueError:
            indice = -1 if paso > 0 else 0

        nuevo = valores[(indice + paso) % len(valores)]
        control.set(nuevo)

        comando = getattr(control, "_command", None)
        if callable(comando):
            comando(nuevo)
        return True

    @staticmethod
    def cambiar_pestana(control, paso):
        """Cambia la pestaña activa con izquierda o derecha."""
        nombres = list(getattr(control, "_name_list", []))
        if not nombres:
            return False

        actual = control.get()
        try:
            indice = nombres.index(actual)
        except ValueError:
            indice = 0

        control.set(nombres[(indice + paso) % len(nombres)])
        return True

    def manejar_flecha(self, evento, direccion):
        """Aplica las flechas según el control que tiene el foco."""
        controles = self.controles_editables_visibles()
        actual = self.control_con_foco_actual(
            evento.widget,
            controles,
            self,
        )

        if actual is None or isinstance(actual, ctk.CTkEntry):
            return None

        if isinstance(actual, ttk.Treeview):
            if direccion in ["arriba", "abajo"]:
                # Treeview ya mueve una fila con su navegación nativa.
                return None
            if direccion == "izquierda":
                actual.xview_scroll(-1, "units")
            else:
                actual.xview_scroll(1, "units")
            return "break"

        if isinstance(actual, (ctk.CTkComboBox, ctk.CTkOptionMenu)):
            paso = -1 if direccion in ["arriba", "izquierda"] else 1
            if self.cambiar_opcion(actual, paso):
                return "break"
            return None

        if isinstance(actual, ctk.CTkTabview):
            if direccion not in ["izquierda", "derecha"]:
                return None
            paso = -1 if direccion == "izquierda" else 1
            if self.cambiar_pestana(actual, paso):
                self.after_idle(actual.focus_set)
                return "break"

        return None

    def crear_tree(self, padre, columnas, titulos, anchos):
        contenedor = ctk.CTkFrame(
            padre,
            fg_color=COLOR_PANEL,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        contenedor.pack(fill="both", expand=True)

        tree = ttk.Treeview(
            contenedor,
            columns=columnas,
            show="headings",
            style="BCTree.Treeview",
            selectmode="browse",
        )

        for columna, titulo, ancho in zip(
            columnas,
            titulos,
            anchos,
        ):
            tree.heading(columna, text=titulo)
            tree.column(
                columna,
                width=ancho,
                minwidth=70,
                anchor="w",
            )

        barra_y = ttk.Scrollbar(
            contenedor,
            orient="vertical",
            command=tree.yview,
        )
        barra_x = ttk.Scrollbar(
            contenedor,
            orient="horizontal",
            command=tree.xview,
        )
        tree.configure(
            yscrollcommand=barra_y.set,
            xscrollcommand=barra_x.set,
        )

        tree.grid(row=0, column=0, sticky="nsew")
        barra_y.grid(row=0, column=1, sticky="ns")
        barra_x.grid(row=1, column=0, sticky="ew")
        contenedor.grid_rowconfigure(0, weight=1)
        contenedor.grid_columnconfigure(0, weight=1)
        return tree

    def crear_campo(
        self,
        padre,
        fila,
        etiqueta,
        valores=None,
        ancho=240,
    ):
        ctk.CTkLabel(
            padre,
            text=etiqueta,
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(
            row=fila,
            column=0,
            sticky="w",
            padx=(0, 12),
            pady=5,
        )

        if valores is None:
            campo = ctk.CTkEntry(
                padre,
                width=ancho,
                height=34,
            )
        else:
            campo = ctk.CTkComboBox(
                padre,
                values=valores,
                width=ancho,
                height=34,
                state="readonly",
            )
            if valores:
                campo.set(valores[0])

        campo.grid(
            row=fila,
            column=1,
            sticky="ew",
            pady=5,
        )
        return campo

    # ------------------------- FUNCIONARIOS -------------------------

    def construir_funcionarios(self):
        pagina = self.pestanas.tab("Funcionarios")
        pagina.grid_columnconfigure(1, weight=1)
        pagina.grid_rowconfigure(0, weight=1)

        formulario = ctk.CTkScrollableFrame(
            pagina,
            width=380,
            fg_color=COLOR_PANEL,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        formulario.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(8, 8),
            pady=8,
        )
        formulario.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            formulario,
            text="Datos del funcionario",
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(4, 12),
        )

        self.f_nombre = self.crear_campo(
            formulario, 1, "Nombre y apellido"
        )
        self.f_cedula = self.crear_campo(
            formulario, 2, "Cédula"
        )
        self.f_ingreso = self.crear_campo(
            formulario, 3, "Fecha de ingreso"
        )
        self.f_unidad = self.crear_campo(
            formulario,
            4,
            "Unidad",
            Funcionarios.UNIDADES,
        )
        self.f_cargo = self.crear_campo(
            formulario, 5, "Cargo"
        )
        self.f_modalidad = self.crear_campo(
            formulario,
            6,
            "Modalidad",
            Funcionarios.MODALIDADES_PAGO,
        )
        self.f_tipo_sueldo = self.crear_campo(
            formulario,
            7,
            "Tipo de sueldo",
            ["Salario mínimo", "Manual"],
        )
        self.f_sueldo = self.crear_campo(
            formulario, 8, "Sueldo o jornal"
        )
        self.f_ips = self.crear_campo(
            formulario,
            9,
            "IPS",
            ["Sí", "No"],
        )
        self.f_horario = self.crear_campo(
            formulario, 10, "Horario"
        )
        self.f_observaciones = self.crear_campo(
            formulario, 11, "Observaciones"
        )

        self.f_ingreso.insert(
            0,
            datetime.now().strftime("%d-%m-%Y"),
        )
        self.f_horario.insert(0, "08:00 a 18:00")

        botones = ctk.CTkFrame(
            formulario,
            fg_color="transparent",
        )
        botones.grid(
            row=12,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(14, 6),
        )
        botones.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            botones,
            text="Guardar",
            command=self.guardar_funcionario,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkButton(
            botones,
            text="Nuevo / limpiar",
            command=self.limpiar_funcionario,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
        ).grid(row=0, column=1, sticky="ew", padx=(5, 0))

        derecha = ctk.CTkFrame(
            pagina,
            fg_color="transparent",
        )
        derecha.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(8, 8),
            pady=8,
        )
        derecha.grid_rowconfigure(1, weight=1)
        derecha.grid_columnconfigure(0, weight=1)

        filtros = ctk.CTkFrame(
            derecha,
            fg_color="transparent",
        )
        filtros.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(
            filtros,
            text="Mostrar:",
            text_color=COLOR_TEXTO_SUAVE,
        ).pack(side="left", padx=(0, 8))
        self.filtro_estado_funcionario = ctk.CTkComboBox(
            filtros,
            values=["Activos", "Inactivos", "Todos"],
            width=145,
            state="readonly",
            command=lambda _valor: self.actualizar_funcionarios(),
        )
        self.filtro_estado_funcionario.set("Activos")
        self.filtro_estado_funcionario.pack(side="left")

        ctk.CTkButton(
            filtros,
            text="Reactivar",
            width=105,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
            command=lambda: self.cambiar_estado_funcionario("Activo"),
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            filtros,
            text="Desactivar",
            width=105,
            fg_color=COLOR_NARANJA,
            hover_color="#C77B20",
            command=lambda: self.cambiar_estado_funcionario("Inactivo"),
        ).pack(side="right")

        contenedor_tree = ctk.CTkFrame(
            derecha,
            fg_color="transparent",
        )
        contenedor_tree.grid(row=1, column=0, sticky="nsew")
        self.tree_funcionarios = self.crear_tree(
            contenedor_tree,
            (
                "nombre",
                "cedula",
                "unidad",
                "cargo",
                "modalidad",
                "sueldo",
                "ips",
                "estado",
            ),
            (
                "Nombre",
                "Cédula",
                "Unidad",
                "Cargo",
                "Modalidad",
                "Sueldo/Jornal",
                "IPS",
                "Estado",
            ),
            (180, 100, 90, 140, 90, 110, 55, 75),
        )
        self.tree_funcionarios.bind(
            "<<TreeviewSelect>>",
            self.cargar_funcionario_seleccionado,
        )

    def obtener_indice_tree(self, tree):
        seleccion = tree.selection()

        if not seleccion:
            raise ValueError("Seleccioná primero un registro de la tabla.")

        return int(seleccion[0])

    def actualizar_funcionarios(self):
        for item in self.tree_funcionarios.get_children():
            self.tree_funcionarios.delete(item)

        filtro = self.filtro_estado_funcionario.get()

        for indice, linea in enumerate(
            leer_datos(Funcionarios.RUTA_FUNCIONARIOS)
        ):
            datos = Funcionarios.separar_funcionario(linea)

            if datos is None:
                continue

            if (
                filtro == "Activos"
                and datos["estado"] != "Activo"
            ):
                continue

            if (
                filtro == "Inactivos"
                and datos["estado"] != "Inactivo"
            ):
                continue

            sueldo = Funcionarios.calcular_sueldo_funcionario(datos)
            self.tree_funcionarios.insert(
                "",
                "end",
                iid=str(indice),
                values=(
                    datos["nombre"],
                    datos["cedula"],
                    datos["unidad"],
                    datos["cargo"],
                    datos["modalidad"],
                    formatear_monto(sueldo),
                    datos["ips"],
                    datos["estado"],
                ),
            )

    def limpiar_funcionario(self):
        self.indice_funcionario = None

        for campo in [
            self.f_nombre,
            self.f_cedula,
            self.f_ingreso,
            self.f_cargo,
            self.f_sueldo,
            self.f_horario,
            self.f_observaciones,
        ]:
            campo.delete(0, "end")

        self.f_ingreso.insert(
            0,
            datetime.now().strftime("%d-%m-%Y"),
        )
        self.f_horario.insert(0, "08:00 a 18:00")
        self.f_unidad.set(Funcionarios.UNIDADES[0])
        self.f_modalidad.set("Mensual")
        self.f_tipo_sueldo.set("Salario mínimo")
        self.f_ips.set("Sí")

    def cargar_funcionario_seleccionado(self, _evento=None):
        try:
            indice = self.obtener_indice_tree(
                self.tree_funcionarios
            )
        except ValueError:
            return

        lineas = leer_datos(Funcionarios.RUTA_FUNCIONARIOS)

        if indice >= len(lineas):
            return

        datos = Funcionarios.separar_funcionario(lineas[indice])

        if datos is None:
            return

        self.indice_funcionario = indice
        pares = [
            (self.f_nombre, datos["nombre"]),
            (self.f_cedula, datos["cedula"]),
            (self.f_ingreso, datos["fecha_ingreso"]),
            (self.f_cargo, datos["cargo"]),
            (self.f_sueldo, str(datos["sueldo_base"])),
            (self.f_horario, datos["horario"]),
            (self.f_observaciones, datos["observaciones"]),
        ]

        for campo, valor in pares:
            campo.delete(0, "end")
            campo.insert(0, valor)

        self.f_unidad.set(datos["unidad"])
        self.f_modalidad.set(datos["modalidad"])
        self.f_tipo_sueldo.set(datos["tipo_sueldo"])
        self.f_ips.set(datos["ips"])

    def guardar_funcionario(self):
        try:
            nombre = limpiar_texto(
                self.f_nombre.get(),
                "nombre",
            )
            cedula = limpiar_texto(
                self.f_cedula.get(),
                "cédula",
            )
            fecha_ingreso = self.f_ingreso.get().strip()
            validar_fecha(fecha_ingreso, "fecha de ingreso")
            cargo = limpiar_texto(
                self.f_cargo.get(),
                "cargo",
            )
            horario = limpiar_texto(
                self.f_horario.get(),
                "horario",
                obligatorio=False,
            ) or "No especificado"
            observaciones = limpiar_texto(
                self.f_observaciones.get(),
                "observaciones",
                obligatorio=False,
            ) or "Sin observaciones"

            modalidad = self.f_modalidad.get()
            tipo_sueldo = self.f_tipo_sueldo.get()

            if modalidad != "Mensual":
                tipo_sueldo = "Manual"

            if tipo_sueldo == "Salario mínimo":
                sueldo = Funcionarios.obtener_salario_minimo(
                    fecha_ingreso
                )
                if sueldo is None:
                    raise ValueError(
                        "No hay salario mínimo vigente para esa fecha."
                    )
            else:
                sueldo = convertir_monto(self.f_sueldo.get())

            lineas = leer_datos(Funcionarios.RUTA_FUNCIONARIOS)

            for indice, linea in enumerate(lineas):
                existente = Funcionarios.separar_funcionario(linea)
                if (
                    existente is not None
                    and existente["cedula"].lower() == cedula.lower()
                    and indice != self.indice_funcionario
                ):
                    raise ValueError(
                        "Ya existe un funcionario con esa cédula."
                    )

            estado = "Activo"
            if (
                self.indice_funcionario is not None
                and self.indice_funcionario < len(lineas)
            ):
                anterior = Funcionarios.separar_funcionario(
                    lineas[self.indice_funcionario]
                )
                if anterior is not None:
                    estado = anterior["estado"]

            datos = {
                "nombre": nombre,
                "cedula": cedula,
                "fecha_ingreso": fecha_ingreso,
                "unidad": self.f_unidad.get(),
                "cargo": cargo,
                "modalidad": modalidad,
                "tipo_sueldo": tipo_sueldo,
                "sueldo_base": sueldo,
                "ips": self.f_ips.get(),
                "horario": horario,
                "estado": estado,
                "observaciones": observaciones,
            }
            nueva_linea = Funcionarios.crear_linea_funcionario(datos)

            if self.indice_funcionario is None:
                lineas.append(nueva_linea)
                mensaje = "Funcionario registrado correctamente."
            else:
                lineas[self.indice_funcionario] = nueva_linea
                mensaje = "Funcionario modificado correctamente."

            guardar_datos(Funcionarios.RUTA_FUNCIONARIOS, lineas)
            self.limpiar_funcionario()
            self.actualizar_todo()
            messagebox.showinfo("Funcionarios", mensaje, parent=self)

        except (ValueError, IndexError) as error:
            messagebox.showerror(
                "No se pudo guardar",
                str(error),
                parent=self,
            )

    def cambiar_estado_funcionario(self, nuevo_estado):
        try:
            indice = self.obtener_indice_tree(
                self.tree_funcionarios
            )
            lineas = leer_datos(Funcionarios.RUTA_FUNCIONARIOS)
            datos = Funcionarios.separar_funcionario(lineas[indice])

            if datos is None:
                raise ValueError("El registro seleccionado no es válido.")

            if datos["estado"] == nuevo_estado:
                raise ValueError(
                    f"El funcionario ya está {nuevo_estado.lower()}."
                )

            accion = (
                "reactivar"
                if nuevo_estado == "Activo"
                else "desactivar"
            )
            if not messagebox.askyesno(
                "Confirmar",
                f"¿Querés {accion} a {datos['nombre']}?\n"
                "Su historial se conservará.",
                parent=self,
            ):
                return

            datos["estado"] = nuevo_estado
            lineas[indice] = Funcionarios.crear_linea_funcionario(
                datos
            )
            guardar_datos(Funcionarios.RUTA_FUNCIONARIOS, lineas)
            self.limpiar_funcionario()
            self.actualizar_todo()

        except (ValueError, IndexError) as error:
            messagebox.showerror(
                "Funcionarios",
                str(error),
                parent=self,
            )

    # --------------------------- NOVEDADES --------------------------

    def construir_novedades(self):
        pagina = self.pestanas.tab("Novedades")
        pagina.grid_columnconfigure(1, weight=1)
        pagina.grid_rowconfigure(0, weight=1)

        formulario = ctk.CTkScrollableFrame(
            pagina,
            width=400,
            fg_color=COLOR_PANEL,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        formulario.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(8, 8),
            pady=8,
        )
        formulario.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            formulario,
            text="Registrar o modificar novedad",
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(4, 12),
        )

        self.n_funcionario = self.crear_campo(
            formulario,
            1,
            "Funcionario",
            ["Sin funcionarios activos"],
            ancho=270,
        )
        self.n_tipo = self.crear_campo(
            formulario,
            2,
            "Tipo",
            Novedades.TIPOS_NOVEDAD,
            ancho=270,
        )
        self.n_inicio = self.crear_campo(
            formulario, 3, "Fecha de inicio", ancho=270
        )
        self.n_fin = self.crear_campo(
            formulario, 4, "Fecha de finalización", ancho=270
        )
        self.n_monto = self.crear_campo(
            formulario, 5, "Monto", ancho=270
        )
        self.n_ips = self.crear_campo(
            formulario,
            6,
            "Cubierto por IPS",
            ["No", "Sí"],
            ancho=270,
        )
        self.n_motivo = self.crear_campo(
            formulario,
            7,
            "Concepto / motivo / observación",
            ancho=270,
        )

        hoy = datetime.now().strftime("%d-%m-%Y")
        self.n_inicio.insert(0, hoy)
        self.n_fin.insert(0, hoy)
        self.n_monto.insert(0, "0")

        botones = ctk.CTkFrame(
            formulario,
            fg_color="transparent",
        )
        botones.grid(
            row=8,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(14, 6),
        )
        botones.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            botones,
            text="Guardar",
            command=self.guardar_novedad,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkButton(
            botones,
            text="Nuevo / limpiar",
            command=self.limpiar_novedad,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
        ).grid(row=0, column=1, sticky="ew", padx=(5, 0))

        derecha = ctk.CTkFrame(
            pagina,
            fg_color="transparent",
        )
        derecha.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(8, 8),
            pady=8,
        )
        derecha.grid_rowconfigure(1, weight=1)
        derecha.grid_columnconfigure(0, weight=1)

        filtros = ctk.CTkFrame(
            derecha,
            fg_color="transparent",
        )
        filtros.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(
            filtros,
            text="Período (MM-AAAA):",
            text_color=COLOR_TEXTO_SUAVE,
        ).pack(side="left", padx=(0, 8))
        self.filtro_periodo_novedad = ctk.CTkEntry(
            filtros,
            width=115,
            placeholder_text="Todos",
        )
        self.filtro_periodo_novedad.pack(side="left")
        ctk.CTkButton(
            filtros,
            text="Filtrar",
            width=80,
            command=self.actualizar_novedades,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            filtros,
            text="Eliminar",
            width=90,
            fg_color=COLOR_ROJO,
            hover_color="#BB3D3D",
            command=self.eliminar_novedad,
        ).pack(side="right")

        contenedor_tree = ctk.CTkFrame(
            derecha,
            fg_color="transparent",
        )
        contenedor_tree.grid(row=1, column=0, sticky="nsew")
        self.tree_novedades = self.crear_tree(
            contenedor_tree,
            (
                "funcionario",
                "tipo",
                "inicio",
                "fin",
                "monto",
                "ips",
                "motivo",
            ),
            (
                "Funcionario",
                "Tipo",
                "Inicio",
                "Fin",
                "Monto",
                "IPS",
                "Motivo",
            ),
            (170, 110, 95, 95, 95, 55, 210),
        )
        self.tree_novedades.bind(
            "<<TreeviewSelect>>",
            self.cargar_novedad_seleccionada,
        )

    def actualizar_lista_funcionarios(self):
        funcionarios = Novedades.obtener_funcionarios_activos()
        self.mapa_funcionarios = {
            f"{dato['cedula']} — {dato['nombre']}": dato
            for dato in funcionarios
        }
        valores = list(self.mapa_funcionarios)

        if not valores:
            valores = ["Sin funcionarios activos"]

        self.n_funcionario.configure(values=valores)
        self.l_funcionario.configure(values=valores)

        if self.n_funcionario.get() not in valores:
            self.n_funcionario.set(valores[0])

        if self.l_funcionario.get() not in valores:
            self.l_funcionario.set(valores[0])

    def limpiar_novedad(self):
        self.indice_novedad = None
        hoy = datetime.now().strftime("%d-%m-%Y")

        for campo, valor in [
            (self.n_inicio, hoy),
            (self.n_fin, hoy),
            (self.n_monto, "0"),
            (self.n_motivo, ""),
        ]:
            campo.delete(0, "end")
            campo.insert(0, valor)

        self.n_tipo.set(Novedades.TIPOS_NOVEDAD[0])
        self.n_ips.set("No")

    def actualizar_novedades(self):
        for item in self.tree_novedades.get_children():
            self.tree_novedades.delete(item)

        periodo = self.filtro_periodo_novedad.get().strip()

        if periodo:
            try:
                validar_periodo(periodo)
            except ValueError as error:
                messagebox.showerror(
                    "Filtro inválido",
                    str(error),
                    parent=self,
                )
                return

        for indice, linea in enumerate(
            leer_datos(Novedades.RUTA_NOVEDADES)
        ):
            datos = Novedades.separar_novedad(linea)

            if datos is None:
                continue

            if periodo:
                fecha = validar_fecha(datos["fecha_inicio"])
                if fecha.strftime("%m-%Y") != periodo:
                    continue

            self.tree_novedades.insert(
                "",
                "end",
                iid=str(indice),
                values=(
                    datos["nombre"],
                    datos["tipo"],
                    datos["fecha_inicio"],
                    datos["fecha_fin"],
                    formatear_monto(datos["monto"]),
                    datos["cubierto_ips"],
                    datos["motivo"],
                ),
            )

    def cargar_novedad_seleccionada(self, _evento=None):
        try:
            indice = self.obtener_indice_tree(self.tree_novedades)
        except ValueError:
            return

        lineas = leer_datos(Novedades.RUTA_NOVEDADES)
        if indice >= len(lineas):
            return

        datos = Novedades.separar_novedad(lineas[indice])
        if datos is None:
            return

        self.indice_novedad = indice
        clave = f"{datos['cedula']} — {datos['nombre']}"
        valores = list(self.mapa_funcionarios)

        if clave not in valores:
            valores.append(clave)
            self.n_funcionario.configure(values=valores)

        self.n_funcionario.set(clave)
        self.n_tipo.set(datos["tipo"])
        self.n_ips.set(datos["cubierto_ips"])

        for campo, valor in [
            (self.n_inicio, datos["fecha_inicio"]),
            (self.n_fin, datos["fecha_fin"]),
            (self.n_monto, str(datos["monto"])),
            (self.n_motivo, datos["motivo"]),
        ]:
            campo.delete(0, "end")
            campo.insert(0, valor)

    def guardar_novedad(self):
        try:
            seleccion = self.n_funcionario.get()
            funcionario = self.mapa_funcionarios.get(seleccion)

            if funcionario is None and self.indice_novedad is None:
                raise ValueError(
                    "Seleccioná un funcionario activo."
                )

            if funcionario is None:
                cedula, nombre = [
                    parte.strip()
                    for parte in seleccion.split("—", 1)
                ]
                funcionario = {
                    "cedula": cedula,
                    "nombre": nombre,
                }

            tipo = self.n_tipo.get()
            inicio_texto = self.n_inicio.get().strip()
            fin_texto = self.n_fin.get().strip()
            inicio = validar_fecha(inicio_texto, "fecha de inicio")
            fin = validar_fecha(fin_texto, "fecha de finalización")

            if tipo in ["Ausencia", "Comisión"]:
                fin = inicio
                fin_texto = inicio_texto

            if fin < inicio:
                raise ValueError(
                    "La fecha final no puede ser anterior a la inicial."
                )

            if tipo in ["Comisión", "Adelanto", "Otro descuento"]:
                monto = convertir_monto(self.n_monto.get())
            else:
                monto = 0

            cubierto = (
                self.n_ips.get()
                if tipo == "Reposo"
                else "No"
            )
            motivo = limpiar_texto(
                self.n_motivo.get(),
                (
                    "concepto de la comisión"
                    if tipo == "Comisión"
                    else "motivo"
                ),
                obligatorio=(tipo == "Comisión"),
            )
            if not motivo:
                motivo = "Sin observación"

            datos = {
                "cedula": funcionario["cedula"],
                "nombre": funcionario["nombre"],
                "tipo": tipo,
                "fecha_inicio": inicio_texto,
                "fecha_fin": fin_texto,
                "monto": monto,
                "cubierto_ips": cubierto,
                "motivo": motivo,
            }
            lineas = leer_datos(Novedades.RUTA_NOVEDADES)
            nueva = Novedades.crear_linea_novedad(datos)

            if self.indice_novedad is None:
                lineas.append(nueva)
                mensaje = "Novedad registrada correctamente."
            else:
                lineas[self.indice_novedad] = nueva
                mensaje = "Novedad modificada correctamente."

            guardar_datos(Novedades.RUTA_NOVEDADES, lineas)
            self.limpiar_novedad()
            self.actualizar_novedades()
            messagebox.showinfo("Novedades", mensaje, parent=self)

        except (ValueError, IndexError) as error:
            messagebox.showerror(
                "No se pudo guardar",
                str(error),
                parent=self,
            )

    def eliminar_novedad(self):
        try:
            indice = self.obtener_indice_tree(self.tree_novedades)
            lineas = leer_datos(Novedades.RUTA_NOVEDADES)
            datos = Novedades.separar_novedad(lineas[indice])

            if datos is None:
                raise ValueError("La novedad seleccionada no es válida.")

            if not messagebox.askyesno(
                "Eliminar novedad",
                f"¿Eliminar {datos['tipo']} de {datos['nombre']}?",
                parent=self,
            ):
                return

            del lineas[indice]
            guardar_datos(Novedades.RUTA_NOVEDADES, lineas)
            self.limpiar_novedad()
            self.actualizar_novedades()

        except (ValueError, IndexError) as error:
            messagebox.showerror(
                "Novedades",
                str(error),
                parent=self,
            )

    # ------------------------- LIQUIDACIONES ------------------------

    def construir_liquidaciones(self):
        pagina = self.pestanas.tab("Liquidaciones")
        pagina.grid_columnconfigure(0, weight=1)
        pagina.grid_rowconfigure(2, weight=1)

        controles = ctk.CTkFrame(
            pagina,
            fg_color=COLOR_PANEL,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        controles.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=8,
            pady=(8, 6),
        )

        ctk.CTkLabel(
            controles,
            text="Funcionario",
            text_color=COLOR_TEXTO_SUAVE,
        ).pack(side="left", padx=(16, 6), pady=14)
        self.l_funcionario = ctk.CTkComboBox(
            controles,
            values=["Sin funcionarios activos"],
            width=220,
            state="readonly",
        )
        self.l_funcionario.pack(side="left", pady=14)

        ctk.CTkLabel(
            controles,
            text="Período",
            text_color=COLOR_TEXTO_SUAVE,
        ).pack(side="left", padx=(16, 6), pady=14)
        self.l_periodo = ctk.CTkEntry(
            controles,
            width=105,
        )
        self.l_periodo.insert(
            0,
            datetime.now().strftime("%m-%Y"),
        )
        self.l_periodo.pack(side="left", pady=14)

        ctk.CTkLabel(
            controles,
            text="Monto base manual",
            text_color=COLOR_TEXTO_SUAVE,
        ).pack(side="left", padx=(16, 6), pady=14)
        self.l_monto_manual = ctk.CTkEntry(
            controles,
            width=135,
            placeholder_text="Diario/semanal",
        )
        self.l_monto_manual.pack(side="left", pady=14)

        ctk.CTkButton(
            controles,
            text="Calcular y guardar",
            width=150,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
            command=self.generar_liquidacion,
        ).pack(side="left", padx=14, pady=14)

        filtros = ctk.CTkFrame(
            pagina,
            fg_color="transparent",
        )
        filtros.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=8,
            pady=6,
        )
        ctk.CTkLabel(
            filtros,
            text="Consultar período:",
            text_color=COLOR_TEXTO_SUAVE,
        ).pack(side="left")
        self.filtro_periodo_liquidacion = ctk.CTkEntry(
            filtros,
            width=110,
        )
        self.filtro_periodo_liquidacion.insert(
            0,
            datetime.now().strftime("%m-%Y"),
        )
        self.filtro_periodo_liquidacion.pack(
            side="left",
            padx=8,
        )
        ctk.CTkButton(
            filtros,
            text="Filtrar",
            width=80,
            command=self.actualizar_liquidaciones,
        ).pack(side="left")

        self.total_liquidaciones = ctk.CTkLabel(
            filtros,
            text="Total neto: Gs. 0",
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.total_liquidaciones.pack(side="left", padx=18)

        ctk.CTkButton(
            filtros,
            text="Eliminar",
            width=85,
            fg_color=COLOR_ROJO,
            hover_color="#BB3D3D",
            command=self.eliminar_liquidacion,
        ).pack(side="right")
        ctk.CTkButton(
            filtros,
            text="Generar recibo",
            width=115,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            command=self.generar_recibo,
        ).pack(side="right", padx=8)
        ctk.CTkButton(
            filtros,
            text="Recalcular",
            width=100,
            fg_color=COLOR_NARANJA,
            hover_color="#C77B20",
            command=self.recalcular_liquidacion,
        ).pack(side="right")
        contenedor_tree = ctk.CTkFrame(
            pagina,
            fg_color="transparent",
        )
        contenedor_tree.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=8,
            pady=(6, 8),
        )
        self.tree_liquidaciones = self.crear_tree(
            contenedor_tree,
            (
                "nombre",
                "periodo",
                "dias",
                "bruto",
                "comisiones",
                "ausencias",
                "reposos",
                "ips",
                "adelantos",
                "otros",
                "neto",
            ),
            (
                "Funcionario",
                "Período",
                "Días",
                "Bruto",
                "Comisiones",
                "Ausencias",
                "Reposos",
                "IPS",
                "Adelantos",
                "Otros",
                "Neto",
            ),
            (170, 80, 55, 100, 100, 90, 90, 90, 90, 90, 105),
        )

        ctk.CTkLabel(
            pagina,
            text=(
                "Las liquidaciones guardadas entran como egreso en el "
                "cierre mensual. Recalcular reemplaza solamente la "
                "liquidación seleccionada usando las novedades actuales."
            ),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=3,
            column=0,
            sticky="ew",
            padx=12,
            pady=(0, 8),
        )

    def calcular_datos_liquidacion(
        self,
        funcionario,
        periodo,
        monto_base_manual=None,
    ):
        fecha_periodo = validar_periodo(periodo)
        sueldo_mensual = Funcionarios.calcular_sueldo_funcionario(
            funcionario,
            fecha_periodo,
        )
        resultado = Liquidaciones.ajustar_sueldo_por_fecha_ingreso(
            funcionario,
            fecha_periodo,
            sueldo_mensual,
        )

        if resultado is None:
            raise ValueError(
                "No se puede liquidar un período anterior al ingreso."
            )

        liquidacion_manual = (
            funcionario["modalidad"] in ("Diario", "Semanal")
        )

        if liquidacion_manual:
            if monto_base_manual is None or monto_base_manual <= 0:
                raise ValueError(
                    "Ingresá el monto base total efectivamente liquidado "
                    "para este período."
                )
            sueldo_mensual = monto_base_manual
            sueldo_bruto = monto_base_manual
            dias_liquidados = 0
        else:
            sueldo_bruto = resultado["sueldo_bruto"]
            dias_liquidados = resultado["dias_liquidados"]

        novedades = Liquidaciones.obtener_novedades_del_periodo(
            funcionario["cedula"],
            fecha_periodo,
        )
        if liquidacion_manual:
            dias_reposo = novedades["dias_reposo"]
            dias_ausencia = novedades["dias_ausencia"]
            descuento_reposos = 0
            descuento_ausencias = 0
        else:
            dias_reposo = min(
                novedades["dias_reposo"],
                dias_liquidados,
            )
            dias_disponibles = dias_liquidados - dias_reposo
            dias_ausencia = min(
                novedades["dias_ausencia"],
                dias_disponibles,
            )
            valor_dia = sueldo_mensual // 30
            descuento_reposos = valor_dia * dias_reposo
            descuento_ausencias = valor_dia * dias_ausencia

        bruto_empresa = max(
            0,
            sueldo_bruto
            - descuento_reposos
            - descuento_ausencias,
        )
        descuento_ips = Liquidaciones.calcular_descuento_ips(
            funcionario,
            bruto_empresa,
        )
        adelantos = novedades["adelantos"]
        otros = novedades["otros_descuentos"]
        comisiones = novedades["comisiones"]
        neto = max(
            0,
            bruto_empresa
            + comisiones
            - descuento_ips
            - adelantos
            - otros,
        )

        return {
            "cedula": funcionario["cedula"],
            "nombre": funcionario["nombre"],
            "periodo": periodo,
            "dias_liquidados": dias_liquidados,
            "sueldo_referencia": sueldo_mensual,
            "sueldo_bruto": sueldo_bruto,
            "descuento_ips": descuento_ips,
            "neto_cobrar": neto,
            "tipo_liquidacion": (
                "Monto manual"
                if liquidacion_manual
                else (
                    "Proporcional"
                    if resultado["es_proporcional"]
                    else "Mes completo"
                )
            ),
            "dias_ausencia": dias_ausencia,
            "dias_reposo": dias_reposo,
            "descuento_ausencias": descuento_ausencias,
            "descuento_reposos": descuento_reposos,
            "adelantos": adelantos,
            "otros_descuentos": otros,
            "comisiones": comisiones,
            "detalle_comisiones": novedades["detalle_comisiones"],
        }

    def resumen_liquidacion(self, datos):
        lineas = [
            f"Funcionario: {datos['nombre']}",
            f"Período: {datos['periodo']}",
        ]

        if datos["tipo_liquidacion"] == "Monto manual":
            lineas.append(
                "Monto base manual: "
                f"Gs. {formatear_monto(datos['sueldo_bruto'])}"
            )
        else:
            lineas.extend(
                [
                    f"Días liquidados: {datos['dias_liquidados']}",
                    "Sueldo bruto: "
                    f"Gs. {formatear_monto(datos['sueldo_bruto'])}",
                ]
            )

        lineas.extend(
            [
                (
                    "Comisiones "
                    f"({len(datos.get('detalle_comisiones', []))}): "
                    f"Gs. {formatear_monto(datos['comisiones'])}"
                ),
                f"Ausencias: {datos['dias_ausencia']} día/s",
                f"Reposos: {datos['dias_reposo']} día/s",
                f"IPS: Gs. {formatear_monto(datos['descuento_ips'])}",
                f"Adelantos: Gs. {formatear_monto(datos['adelantos'])}",
                (
                    "Otros descuentos: "
                    f"Gs. {formatear_monto(datos['otros_descuentos'])}"
                ),
                "",
                (
                    "NETO A COBRAR: "
                    f"Gs. {formatear_monto(datos['neto_cobrar'])}"
                ),
            ]
        )
        return "\n".join(lineas)

    def generar_liquidacion(self):
        try:
            funcionario = self.mapa_funcionarios.get(
                self.l_funcionario.get()
            )
            if funcionario is None:
                raise ValueError(
                    "Seleccioná un funcionario activo."
                )

            periodo = self.l_periodo.get().strip()
            validar_periodo(periodo)

            if Liquidaciones.liquidacion_ya_registrada(
                funcionario["cedula"],
                periodo,
            ):
                raise ValueError(
                    "Este funcionario ya tiene una liquidación "
                    "guardada para ese período."
                )

            monto_manual = None
            if funcionario["modalidad"] in ("Diario", "Semanal"):
                if not self.l_monto_manual.get().strip():
                    raise ValueError(
                        "Para un funcionario diario o semanal, ingresá "
                        "el monto base total efectivamente liquidado."
                    )
                monto_manual = convertir_monto(
                    self.l_monto_manual.get()
                )

            datos = self.calcular_datos_liquidacion(
                funcionario,
                periodo,
                monto_manual,
            )

            if not messagebox.askyesno(
                "Confirmar liquidación",
                self.resumen_liquidacion(datos)
                + "\n\n¿Guardar esta liquidación?",
                parent=self,
            ):
                return

            lineas = leer_datos(Liquidaciones.RUTA_LIQUIDACIONES)
            lineas.append(
                Liquidaciones.crear_linea_liquidacion(datos)
            )
            guardar_datos(
                Liquidaciones.RUTA_LIQUIDACIONES,
                lineas,
            )
            self.filtro_periodo_liquidacion.delete(0, "end")
            self.filtro_periodo_liquidacion.insert(0, periodo)
            self.l_monto_manual.delete(0, "end")
            self.actualizar_liquidaciones()
            messagebox.showinfo(
                "Liquidaciones",
                "Liquidación guardada correctamente.",
                parent=self,
            )

        except ValueError as error:
            messagebox.showerror(
                "No se pudo liquidar",
                str(error),
                parent=self,
            )

    def actualizar_liquidaciones(self):
        for item in self.tree_liquidaciones.get_children():
            self.tree_liquidaciones.delete(item)

        periodo = self.filtro_periodo_liquidacion.get().strip()
        if periodo:
            try:
                validar_periodo(periodo)
            except ValueError as error:
                messagebox.showerror(
                    "Filtro inválido",
                    str(error),
                    parent=self,
                )
                return

        total = 0
        for indice, linea in enumerate(
            leer_datos(Liquidaciones.RUTA_LIQUIDACIONES)
        ):
            datos = Liquidaciones.separar_liquidacion(linea)

            if datos is None:
                continue
            if periodo and datos["periodo"] != periodo:
                continue

            total += datos["neto_cobrar"]
            self.tree_liquidaciones.insert(
                "",
                "end",
                iid=str(indice),
                values=(
                    datos["nombre"],
                    datos["periodo"],
                    (
                        "-"
                        if datos["tipo_liquidacion"] == "Monto manual"
                        else datos["dias_liquidados"]
                    ),
                    formatear_monto(datos["sueldo_bruto"]),
                    formatear_monto(datos["comisiones"]),
                    (
                        f"{datos['dias_ausencia']} / "
                        f"{formatear_monto(datos['descuento_ausencias'])}"
                    ),
                    (
                        f"{datos['dias_reposo']} / "
                        f"{formatear_monto(datos['descuento_reposos'])}"
                    ),
                    formatear_monto(datos["descuento_ips"]),
                    formatear_monto(datos["adelantos"]),
                    formatear_monto(datos["otros_descuentos"]),
                    formatear_monto(datos["neto_cobrar"]),
                ),
            )

        self.total_liquidaciones.configure(
            text=f"Total neto: Gs. {formatear_monto(total)}"
        )

    def obtener_liquidacion_seleccionada(self):
        indice = self.obtener_indice_tree(self.tree_liquidaciones)
        lineas = leer_datos(Liquidaciones.RUTA_LIQUIDACIONES)

        if indice >= len(lineas):
            raise ValueError("La liquidación seleccionada ya no existe.")

        datos = Liquidaciones.separar_liquidacion(lineas[indice])
        if datos is None:
            raise ValueError("La liquidación seleccionada no es válida.")

        return indice, lineas, datos

    def buscar_funcionario_por_cedula(self, cedula):
        for linea in leer_datos(Funcionarios.RUTA_FUNCIONARIOS):
            datos = Funcionarios.separar_funcionario(linea)
            if datos is not None and datos["cedula"] == cedula:
                return datos
        return None

    def recalcular_liquidacion(self):
        try:
            indice, lineas, anterior = (
                self.obtener_liquidacion_seleccionada()
            )
            funcionario = self.buscar_funcionario_por_cedula(
                anterior["cedula"]
            )
            if funcionario is None:
                raise ValueError(
                    "No se encontró el funcionario de esta liquidación."
                )

            nueva = self.calcular_datos_liquidacion(
                funcionario,
                anterior["periodo"],
                (
                    convertir_monto(self.l_monto_manual.get())
                    if self.l_monto_manual.get().strip()
                    else (
                        anterior["sueldo_bruto"]
                        if anterior["tipo_liquidacion"] == "Monto manual"
                        else None
                    )
                ),
            )
            if not messagebox.askyesno(
                "Recalcular liquidación",
                self.resumen_liquidacion(nueva)
                + "\n\n¿Reemplazar la liquidación seleccionada?",
                parent=self,
            ):
                return

            lineas[indice] = Liquidaciones.crear_linea_liquidacion(
                nueva
            )
            guardar_datos(
                Liquidaciones.RUTA_LIQUIDACIONES,
                lineas,
            )
            self.l_monto_manual.delete(0, "end")
            self.actualizar_liquidaciones()

        except (ValueError, IndexError) as error:
            messagebox.showerror(
                "Liquidaciones",
                str(error),
                parent=self,
            )

    def eliminar_liquidacion(self):
        try:
            indice, lineas, datos = (
                self.obtener_liquidacion_seleccionada()
            )
            if not messagebox.askyesno(
                "Eliminar liquidación",
                f"¿Eliminar la liquidación de {datos['nombre']} "
                f"del período {datos['periodo']}?",
                parent=self,
            ):
                return

            del lineas[indice]
            guardar_datos(
                Liquidaciones.RUTA_LIQUIDACIONES,
                lineas,
            )
            self.actualizar_liquidaciones()

        except (ValueError, IndexError) as error:
            messagebox.showerror(
                "Liquidaciones",
                str(error),
                parent=self,
            )

    def generar_recibo(self):
        try:
            _indice, _lineas, datos = (
                self.obtener_liquidacion_seleccionada()
            )
            fecha = datetime.now().strftime("%d-%m-%Y")
            contenido = Liquidaciones.crear_contenido_recibo(
                datos,
                fecha,
            )

            Liquidaciones.RUTA_RECIBOS.mkdir(
                parents=True,
                exist_ok=True,
            )
            periodo_archivo = datos["periodo"].replace("-", "_")
            cedula_archivo = (
                datos["cedula"]
                .replace(".", "")
                .replace(" ", "")
            )
            ruta = (
                Liquidaciones.RUTA_RECIBOS
                / f"recibo_{periodo_archivo}_{cedula_archivo}.txt"
            )

            if ruta.exists() and not messagebox.askyesno(
                "Reemplazar recibo",
                "Ya existe un recibo para esta liquidación. "
                "¿Querés reemplazarlo?",
                parent=self,
            ):
                return

            ruta.write_text(contenido, encoding="utf-8")
            messagebox.showinfo(
                "Recibo generado",
                f"Recibo guardado en:\n{ruta}",
                parent=self,
            )

            if os.name == "nt":
                os.startfile(ruta)  # type: ignore[attr-defined]

        except (ValueError, IndexError, OSError) as error:
            messagebox.showerror(
                "Recibo",
                str(error),
                parent=self,
            )

    # ------------------------ SALARIO MÍNIMO ------------------------

    def construir_salario_minimo(self):
        pagina = self.pestanas.tab("Salario mínimo")
        pagina.grid_columnconfigure(0, weight=1)
        pagina.grid_rowconfigure(2, weight=1)

        self.salario_vigente_label = ctk.CTkLabel(
            pagina,
            text="Salario mínimo vigente",
            height=90,
            corner_radius=14,
            fg_color=COLOR_PANEL,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.salario_vigente_label.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=8,
            pady=(8, 10),
        )

        formulario = ctk.CTkFrame(
            pagina,
            fg_color=COLOR_PANEL,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        formulario.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=8,
            pady=(0, 10),
        )
        ctk.CTkLabel(
            formulario,
            text="Nueva fecha de vigencia",
            text_color=COLOR_TEXTO_SUAVE,
        ).pack(side="left", padx=(16, 8), pady=14)
        self.s_fecha = ctk.CTkEntry(formulario, width=120)
        self.s_fecha.insert(
            0,
            datetime.now().strftime("%d-%m-%Y"),
        )
        self.s_fecha.pack(side="left", pady=14)
        ctk.CTkLabel(
            formulario,
            text="Nuevo monto",
            text_color=COLOR_TEXTO_SUAVE,
        ).pack(side="left", padx=(18, 8), pady=14)
        self.s_monto = ctk.CTkEntry(formulario, width=145)
        self.s_monto.pack(side="left", pady=14)
        ctk.CTkButton(
            formulario,
            text="Registrar reajuste",
            width=145,
            fg_color="#7B61FF",
            hover_color="#6147D6",
            command=self.guardar_reajuste,
        ).pack(side="left", padx=16, pady=14)

        contenedor_tree = ctk.CTkFrame(
            pagina,
            fg_color="transparent",
        )
        contenedor_tree.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=8,
            pady=(0, 8),
        )
        self.tree_salarios = self.crear_tree(
            contenedor_tree,
            ("fecha", "monto"),
            ("Vigente desde", "Salario mínimo"),
            (180, 180),
        )

    def actualizar_salarios(self):
        for item in self.tree_salarios.get_children():
            self.tree_salarios.delete(item)

        salarios = Funcionarios.obtener_historial_salarios()
        vigente = None
        ahora = datetime.now()

        for indice, salario in enumerate(salarios):
            self.tree_salarios.insert(
                "",
                "end",
                iid=str(indice),
                values=(
                    salario["fecha_texto"],
                    f"Gs. {formatear_monto(salario['monto'])}",
                ),
            )
            if salario["fecha"] <= ahora:
                vigente = salario

        if vigente is None:
            texto = "No existe un salario mínimo vigente"
        else:
            texto = (
                f"Salario mínimo vigente: "
                f"Gs. {formatear_monto(vigente['monto'])}\n"
                f"Desde el {vigente['fecha_texto']}"
            )
        self.salario_vigente_label.configure(text=texto)

    def guardar_reajuste(self):
        try:
            fecha = self.s_fecha.get().strip()
            fecha_convertida = validar_fecha(
                fecha,
                "fecha de vigencia",
            )
            monto = convertir_monto(self.s_monto.get())
            salarios = Funcionarios.obtener_historial_salarios()

            if any(
                salario["fecha"] == fecha_convertida
                for salario in salarios
            ):
                raise ValueError(
                    "Ya existe un salario registrado para esa fecha."
                )

            if not messagebox.askyesno(
                "Registrar reajuste",
                f"Fecha: {fecha}\n"
                f"Nuevo salario: Gs. {formatear_monto(monto)}\n\n"
                "¿Guardar este reajuste?",
                parent=self,
            ):
                return

            lineas = leer_datos(
                Funcionarios.RUTA_SALARIOS_MINIMOS
            )
            lineas.append(
                Funcionarios.crear_linea_salario(fecha, monto)
            )
            validos = []
            for linea in lineas:
                datos = Funcionarios.separar_salario(linea)
                if datos is not None:
                    validos.append(datos)

            validos.sort(key=lambda dato: dato["fecha"])
            guardar_datos(
                Funcionarios.RUTA_SALARIOS_MINIMOS,
                [
                    Funcionarios.crear_linea_salario(
                        dato["fecha_texto"],
                        dato["monto"],
                    )
                    for dato in validos
                ],
            )
            self.s_monto.delete(0, "end")
            self.actualizar_salarios()

        except ValueError as error:
            messagebox.showerror(
                "Salario mínimo",
                str(error),
                parent=self,
            )

    def actualizar_todo(self):
        self.actualizar_funcionarios()
        self.actualizar_lista_funcionarios()
        self.actualizar_novedades()
        self.actualizar_liquidaciones()
        self.actualizar_salarios()


def crear_panel_recursos_humanos(
    master,
    pestana="Gestión de funcionarios",
):
    return VentanaRecursosHumanos(master, pestana)


def abrir_recursos_humanos(
    master,
    pestana="Gestión de funcionarios",
):
    ventana = ctk.CTkToplevel(master)
    ventana.title("BC Gestión | Recursos Humanos")
    ventana.geometry("1240x760")
    ventana.minsize(1080, 690)
    ventana.configure(fg_color=COLOR_FONDO)

    panel = VentanaRecursosHumanos(
        ventana,
        pestana,
    )
    panel.pack(fill="both", expand=True)