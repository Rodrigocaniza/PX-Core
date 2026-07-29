"""Registro documental de facturas. No afecta movimientos ni resultados."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk
from uuid import uuid4

import customtkinter as ctk

from datos import guardar_datos, leer_datos


BASE_DIR = Path(__file__).resolve().parent
RUTA_FACTURAS = BASE_DIR / "Datos" / "facturas.txt"
RUTA_PROVEEDORES = BASE_DIR / "Datos" / "proveedores.txt"

ORIGENES = ["PC", "P2", "Administración", "General EAS"]
PLAZOS = ["30", "60", "90", "Personalizado"]

COLOR_FONDO = ("#F4F7FB", "#0B1220")
COLOR_PANEL = ("#FFFFFF", "#131D2E")
COLOR_PANEL_SECUNDARIO = ("#EAF0F7", "#1A2639")
COLOR_BORDE = ("#DCE4EE", "#26354A")
COLOR_TEXTO = ("#182230", "#F4F7FB")
COLOR_TEXTO_SUAVE = ("#617084", "#9CAFC5")
COLOR_PRIMARIO = "#246BFD"
COLOR_PRIMARIO_HOVER = "#1855D6"
COLOR_VERDE = "#18A874"


def _texto(valor, nombre, obligatorio=True):
    valor = valor.strip()
    if obligatorio and not valor:
        raise ValueError(f"Completá el campo {nombre}.")
    if any(caracter in valor for caracter in ("\n", "\r")):
        raise ValueError(f"El campo {nombre} contiene un salto de línea.")
    return valor


def _fecha(texto):
    try:
        return datetime.strptime(texto.strip(), "%d-%m-%Y")
    except ValueError as error:
        raise ValueError("La fecha debe tener formato DD-MM-AAAA.") from error


def _monto(texto):
    limpio = texto.strip().replace(".", "").replace(",", "").replace(" ", "")
    try:
        valor = int(limpio)
    except ValueError as error:
        raise ValueError("Ingresá un monto válido usando solo números.") from error
    if valor <= 0:
        raise ValueError("El monto debe ser mayor a cero.")
    return valor


def _formatear_monto(valor):
    return f"{int(valor):,}".replace(",", ".")


def _leer_json(ruta):
    registros = []
    for posicion, linea in enumerate(leer_datos(ruta)):
        try:
            dato = json.loads(linea)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(dato, dict):
            registros.append((posicion, dato))
    return registros


def _guardar_json(ruta, registros):
    lineas = [
        json.dumps(registro, ensure_ascii=False, separators=(",", ":"))
        for registro in registros
    ]
    guardar_datos(ruta, lineas)


def obtener_facturas():
    return _leer_json(RUTA_FACTURAS)


def obtener_proveedores():
    return _leer_json(RUTA_PROVEEDORES)


def guardar_factura(registro):
    facturas = [dato for _, dato in obtener_facturas()]
    facturas.append(registro)
    _guardar_json(RUTA_FACTURAS, facturas)


def guardar_proveedor(registro):
    proveedores = [dato for _, dato in obtener_proveedores()]
    nombre_normalizado = registro["nombre"].casefold()
    if any(p.get("nombre", "").casefold() == nombre_normalizado for p in proveedores):
        raise ValueError("Ese proveedor ya está registrado.")
    proveedores.append(registro)
    _guardar_json(RUTA_PROVEEDORES, proveedores)


def eliminar_factura_por_id(factura_id):
    facturas = [
        dato for _, dato in obtener_facturas()
        if dato.get("id") != factura_id
    ]
    _guardar_json(RUTA_FACTURAS, facturas)


class VentanaFacturas(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Registro de facturas")
        self.geometry("1180x760")
        self.minsize(980, 680)
        self.configure(fg_color=COLOR_FONDO)
        self.transient(master)
        self.after(100, self.lift)

        self.factura_seleccionada_id = None
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._crear_encabezado()
        self.pestanas = ctk.CTkTabview(
            self,
            fg_color=COLOR_PANEL,
            segmented_button_selected_color=COLOR_PRIMARIO,
            segmented_button_selected_hover_color=COLOR_PRIMARIO_HOVER,
        )
        self.pestanas.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 24))

        for nombre in ("Factura al contado", "Factura a crédito", "Proveedores", "Informes"):
            self.pestanas.add(nombre)

        self._crear_contado()
        self._crear_credito()
        self._crear_proveedores()
        self._crear_informes()
        self._actualizar_proveedores()
        self._actualizar_informe()

    def _crear_encabezado(self):
        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.grid(row=0, column=0, sticky="ew", padx=28, pady=20)
        encabezado.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            encabezado,
            text="Registro documental de facturas",
            font=ctk.CTkFont(size=25, weight="bold"),
            text_color=COLOR_TEXTO,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            encabezado,
            text="No modifica movimientos, saldos, cierres ni resultados.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        self.etiqueta_reloj = ctk.CTkLabel(
            encabezado,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXTO,
        )
        self.etiqueta_reloj.grid(row=0, column=1, rowspan=2, padx=(20, 0))
        self._actualizar_reloj()

    def _actualizar_reloj(self):
        if not self.winfo_exists():
            return
        self.etiqueta_reloj.configure(
            text=datetime.now().strftime("%d-%m-%Y  %H:%M:%S")
        )
        self.after(1000, self._actualizar_reloj)

    def _campo(self, master, fila, etiqueta, ancho=1, placeholder=""):
        ctk.CTkLabel(
            master,
            text=etiqueta,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(row=fila, column=0, sticky="w", padx=18, pady=8)
        entrada = ctk.CTkEntry(
            master,
            placeholder_text=placeholder,
            fg_color=COLOR_PANEL_SECUNDARIO,
            border_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            height=38,
        )
        entrada.grid(row=fila, column=1, columnspan=ancho, sticky="ew", padx=(0, 18), pady=8)
        return entrada

    def _panel_formulario(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        panel = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        panel.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        panel.grid_columnconfigure(1, weight=1)
        return panel

    def _crear_contado(self):
        tab = self.pestanas.tab("Factura al contado")
        panel = self._panel_formulario(tab)

        self.contado_fecha = self._campo(panel, 0, "Fecha", placeholder="DD-MM-AAAA")
        self.contado_fecha.insert(0, datetime.now().strftime("%d-%m-%Y"))
        self.contado_numero = self._campo(panel, 1, "Número de factura")
        self.contado_monto = self._campo(panel, 2, "Monto", placeholder="Ej.: 150000")

        ctk.CTkLabel(panel, text="Origen / sucursal", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COLOR_TEXTO).grid(row=3, column=0, sticky="w", padx=18, pady=8)
        self.contado_origen = ctk.CTkComboBox(
            panel, values=ORIGENES, state="readonly", height=38,
            fg_color=COLOR_PANEL_SECUNDARIO, border_color=COLOR_BORDE,
            button_color=COLOR_PRIMARIO, text_color=COLOR_TEXTO,
        )
        self.contado_origen.set(ORIGENES[0])
        self.contado_origen.grid(row=3, column=1, sticky="ew", padx=(0, 18), pady=8)

        self.contado_local = self._campo(panel, 4, "Local / negocio")
        self.contado_descripcion = self._campo(panel, 5, "Descripción de la compra")

        ctk.CTkButton(
            panel, text="Guardar factura al contado",
            command=self._guardar_contado, fg_color=COLOR_VERDE,
            hover_color="#12835B", height=42,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=6, column=0, columnspan=2, sticky="ew", padx=18, pady=20)

    def _guardar_contado(self):
        try:
            fecha = _fecha(self.contado_fecha.get())
            registro = {
                "id": uuid4().hex[:12].upper(),
                "tipo": "CONTADO",
                "fecha": fecha.strftime("%d-%m-%Y"),
                "numero": _texto(self.contado_numero.get(), "Número de factura"),
                "monto": _monto(self.contado_monto.get()),
                "origen": _texto(self.contado_origen.get(), "Origen"),
                "proveedor": _texto(self.contado_local.get(), "Local / negocio"),
                "descripcion": _texto(self.contado_descripcion.get(), "Descripción"),
                "plazo_dias": 0,
                "vencimiento": "",
                "registrado_en": datetime.now().isoformat(timespec="seconds"),
            }
            guardar_factura(registro)
        except (ValueError, OSError) as error:
            messagebox.showerror("No se pudo guardar", str(error), parent=self)
            return

        self.contado_numero.delete(0, "end")
        self.contado_monto.delete(0, "end")
        self.contado_local.delete(0, "end")
        self.contado_descripcion.delete(0, "end")
        self._actualizar_informe()
        messagebox.showinfo("Factura guardada", "La factura al contado quedó registrada.", parent=self)

    def _crear_credito(self):
        tab = self.pestanas.tab("Factura a crédito")
        panel = self._panel_formulario(tab)

        self.credito_fecha = self._campo(panel, 0, "Fecha", placeholder="DD-MM-AAAA")
        self.credito_fecha.insert(0, datetime.now().strftime("%d-%m-%Y"))
        self.credito_numero = self._campo(panel, 1, "Número de factura")
        self.credito_monto = self._campo(panel, 2, "Monto")

        ctk.CTkLabel(panel, text="Proveedor", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COLOR_TEXTO).grid(row=3, column=0, sticky="w", padx=18, pady=8)
        self.credito_proveedor = ctk.CTkComboBox(
            panel, values=[], state="normal", height=38,
            fg_color=COLOR_PANEL_SECUNDARIO, border_color=COLOR_BORDE,
            button_color=COLOR_PRIMARIO, text_color=COLOR_TEXTO,
        )
        self.credito_proveedor.grid(row=3, column=1, sticky="ew", padx=(0, 18), pady=8)

        self.credito_descripcion = self._campo(panel, 4, "Descripción", placeholder="Opcional")

        ctk.CTkLabel(panel, text="Plazo", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COLOR_TEXTO).grid(row=5, column=0, sticky="w", padx=18, pady=8)
        zona_plazo = ctk.CTkFrame(panel, fg_color="transparent")
        zona_plazo.grid(row=5, column=1, sticky="ew", padx=(0, 18), pady=8)
        zona_plazo.grid_columnconfigure(0, weight=1)
        zona_plazo.grid_columnconfigure(1, weight=1)

        self.credito_plazo = ctk.CTkComboBox(
            zona_plazo, values=PLAZOS, state="readonly", command=self._cambiar_plazo,
            fg_color=COLOR_PANEL_SECUNDARIO, border_color=COLOR_BORDE,
            button_color=COLOR_PRIMARIO, text_color=COLOR_TEXTO,
        )
        self.credito_plazo.set("30")
        self.credito_plazo.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.credito_dias = ctk.CTkEntry(
            zona_plazo, placeholder_text="Días personalizados",
            state="disabled", fg_color=COLOR_PANEL_SECUNDARIO,
            border_color=COLOR_BORDE, text_color=COLOR_TEXTO,
        )
        self.credito_dias.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.etiqueta_vencimiento = ctk.CTkLabel(
            panel, text="Vencimiento estimado: -", text_color=COLOR_TEXTO_SUAVE,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.etiqueta_vencimiento.grid(row=6, column=0, columnspan=2, sticky="w", padx=18, pady=8)

        self.credito_fecha.bind("<KeyRelease>", lambda _e: self._mostrar_vencimiento())
        self.credito_dias.bind("<KeyRelease>", lambda _e: self._mostrar_vencimiento())
        self._mostrar_vencimiento()

        ctk.CTkButton(
            panel, text="Guardar factura a crédito",
            command=self._guardar_credito, fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER, height=42,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=7, column=0, columnspan=2, sticky="ew", padx=18, pady=20)

    def _cambiar_plazo(self, valor):
        self.credito_dias.configure(state="normal" if valor == "Personalizado" else "disabled")
        self._mostrar_vencimiento()

    def _dias_credito(self):
        valor = self.credito_plazo.get()
        if valor == "Personalizado":
            try:
                dias = int(self.credito_dias.get().strip())
            except ValueError as error:
                raise ValueError("Ingresá una cantidad válida de días.") from error
            if dias <= 0:
                raise ValueError("El plazo debe ser mayor a cero.")
            return dias
        return int(valor)

    def _mostrar_vencimiento(self):
        try:
            vencimiento = _fecha(self.credito_fecha.get()) + timedelta(days=self._dias_credito())
            texto = "Vencimiento estimado: " + vencimiento.strftime("%d-%m-%Y")
        except ValueError:
            texto = "Vencimiento estimado: -"
        self.etiqueta_vencimiento.configure(text=texto)

    def _guardar_credito(self):
        try:
            fecha = _fecha(self.credito_fecha.get())
            dias = self._dias_credito()
            proveedor = _texto(self.credito_proveedor.get(), "Proveedor")
            registro = {
                "id": uuid4().hex[:12].upper(),
                "tipo": "CREDITO",
                "fecha": fecha.strftime("%d-%m-%Y"),
                "numero": _texto(self.credito_numero.get(), "Número de factura"),
                "monto": _monto(self.credito_monto.get()),
                "origen": "",
                "proveedor": proveedor,
                "descripcion": _texto(self.credito_descripcion.get(), "Descripción", obligatorio=False),
                "plazo_dias": dias,
                "vencimiento": (fecha + timedelta(days=dias)).strftime("%d-%m-%Y"),
                "registrado_en": datetime.now().isoformat(timespec="seconds"),
            }
            guardar_factura(registro)
        except (ValueError, OSError) as error:
            messagebox.showerror("No se pudo guardar", str(error), parent=self)
            return

        self.credito_numero.delete(0, "end")
        self.credito_monto.delete(0, "end")
        self.credito_proveedor.set("")
        self.credito_descripcion.delete(0, "end")
        self._actualizar_informe()
        messagebox.showinfo("Factura guardada", "La factura a crédito quedó registrada.", parent=self)

    def _crear_proveedores(self):
        tab = self.pestanas.tab("Proveedores")
        panel = self._panel_formulario(tab)

        self.proveedor_nombre = self._campo(panel, 0, "Nombre / razón social")
        self.proveedor_ruc = self._campo(panel, 1, "RUC", placeholder="Opcional")
        self.proveedor_telefono = self._campo(panel, 2, "Teléfono", placeholder="Opcional")
        self.proveedor_direccion = self._campo(panel, 3, "Dirección", placeholder="Opcional")
        self.proveedor_observacion = self._campo(panel, 4, "Observación", placeholder="Opcional")

        ctk.CTkButton(
            panel, text="Crear proveedor", command=self._guardar_proveedor,
            fg_color=COLOR_PRIMARIO, hover_color=COLOR_PRIMARIO_HOVER,
            height=42, font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=18, pady=20)

        self.lista_proveedores = ctk.CTkTextbox(
            panel, height=220, fg_color=COLOR_PANEL_SECUNDARIO,
            border_width=1, border_color=COLOR_BORDE, text_color=COLOR_TEXTO,
        )
        self.lista_proveedores.grid(row=6, column=0, columnspan=2, sticky="nsew", padx=18, pady=(0, 18))

    def _guardar_proveedor(self):
        try:
            registro = {
                "id": uuid4().hex[:12].upper(),
                "nombre": _texto(self.proveedor_nombre.get(), "Nombre / razón social"),
                "ruc": _texto(self.proveedor_ruc.get(), "RUC", obligatorio=False),
                "telefono": _texto(self.proveedor_telefono.get(), "Teléfono", obligatorio=False),
                "direccion": _texto(self.proveedor_direccion.get(), "Dirección", obligatorio=False),
                "observacion": _texto(self.proveedor_observacion.get(), "Observación", obligatorio=False),
                "registrado_en": datetime.now().isoformat(timespec="seconds"),
            }
            guardar_proveedor(registro)
        except (ValueError, OSError) as error:
            messagebox.showerror("No se pudo guardar", str(error), parent=self)
            return

        for entrada in (
            self.proveedor_nombre, self.proveedor_ruc, self.proveedor_telefono,
            self.proveedor_direccion, self.proveedor_observacion,
        ):
            entrada.delete(0, "end")
        self._actualizar_proveedores()
        messagebox.showinfo("Proveedor creado", "El proveedor quedó disponible para futuras facturas.", parent=self)

    def _actualizar_proveedores(self):
        proveedores = [dato for _, dato in obtener_proveedores()]
        nombres = sorted((p.get("nombre", "") for p in proveedores if p.get("nombre")), key=str.casefold)
        self.credito_proveedor.configure(values=nombres)

        self.lista_proveedores.configure(state="normal")
        self.lista_proveedores.delete("1.0", "end")
        if not proveedores:
            self.lista_proveedores.insert("end", "Todavía no hay proveedores registrados.")
        else:
            for proveedor in sorted(proveedores, key=lambda p: p.get("nombre", "").casefold()):
                detalle = proveedor.get("nombre", "")
                if proveedor.get("ruc"):
                    detalle += f" · RUC {proveedor['ruc']}"
                if proveedor.get("telefono"):
                    detalle += f" · {proveedor['telefono']}"
                self.lista_proveedores.insert("end", detalle + "\n")
        self.lista_proveedores.configure(state="disabled")

    def _crear_informes(self):
        tab = self.pestanas.tab("Informes")
        tab.grid_rowconfigure(2, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        filtros = ctk.CTkFrame(tab, fg_color="transparent")
        filtros.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        for columna in range(4):
            filtros.grid_columnconfigure(columna, weight=1)

        self.filtro_periodo = ctk.CTkEntry(
            filtros, placeholder_text="MM-AAAA", fg_color=COLOR_PANEL_SECUNDARIO,
            border_color=COLOR_BORDE, text_color=COLOR_TEXTO,
        )
        self.filtro_periodo.insert(0, datetime.now().strftime("%m-%Y"))
        self.filtro_periodo.grid(row=0, column=0, sticky="ew", padx=5)

        self.filtro_tipo = ctk.CTkComboBox(
            filtros, values=["Todos", "Contado", "Crédito"], state="readonly",
            fg_color=COLOR_PANEL_SECUNDARIO, border_color=COLOR_BORDE,
            button_color=COLOR_PRIMARIO, text_color=COLOR_TEXTO,
        )
        self.filtro_tipo.set("Todos")
        self.filtro_tipo.grid(row=0, column=1, sticky="ew", padx=5)

        self.filtro_proveedor = ctk.CTkEntry(
            filtros, placeholder_text="Proveedor / local", fg_color=COLOR_PANEL_SECUNDARIO,
            border_color=COLOR_BORDE, text_color=COLOR_TEXTO,
        )
        self.filtro_proveedor.grid(row=0, column=2, sticky="ew", padx=5)

        ctk.CTkButton(
            filtros, text="Aplicar filtros", command=self._actualizar_informe,
            fg_color=COLOR_PRIMARIO, hover_color=COLOR_PRIMARIO_HOVER,
        ).grid(row=0, column=3, sticky="ew", padx=5)

        self.resumen = ctk.CTkLabel(
            tab, text="", justify="left", anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_TEXTO,
            fg_color=COLOR_PANEL_SECUNDARIO, corner_radius=10,
        )
        self.resumen.grid(row=1, column=0, sticky="ew", padx=17, pady=(0, 12))

        columnas = ("fecha", "tipo", "numero", "proveedor", "monto", "origen", "plazo", "vencimiento")
        self.tabla = ttk.Treeview(tab, columns=columnas, show="headings", height=15)
        titulos = {
            "fecha": "Fecha", "tipo": "Tipo", "numero": "N.º factura",
            "proveedor": "Proveedor / local", "monto": "Monto",
            "origen": "Origen", "plazo": "Plazo", "vencimiento": "Vencimiento",
        }
        anchos = {"fecha": 90, "tipo": 80, "numero": 110, "proveedor": 190, "monto": 110,
                  "origen": 110, "plazo": 70, "vencimiento": 100}
        for columna in columnas:
            self.tabla.heading(columna, text=titulos[columna])
            self.tabla.column(columna, width=anchos[columna], anchor="center")
        self.tabla.column("proveedor", anchor="w")
        self.tabla.grid(row=2, column=0, sticky="nsew", padx=17, pady=(0, 10))
        self.tabla.bind("<<TreeviewSelect>>", self._seleccionar_factura)

        ctk.CTkButton(
            tab, text="Eliminar factura seleccionada",
            command=self._eliminar_factura, fg_color="#E25555",
            hover_color="#BE3F3F", height=38,
        ).grid(row=3, column=0, sticky="e", padx=17, pady=(0, 15))

    def _facturas_filtradas(self):
        periodo = self.filtro_periodo.get().strip()
        try:
            mes = datetime.strptime(periodo, "%m-%Y")
        except ValueError as error:
            raise ValueError("El período debe tener formato MM-AAAA.") from error

        tipo_gui = self.filtro_tipo.get()
        tipo = {"Contado": "CONTADO", "Crédito": "CREDITO"}.get(tipo_gui)
        proveedor = self.filtro_proveedor.get().strip().casefold()

        resultado = []
        for _, factura in obtener_facturas():
            try:
                fecha = _fecha(factura.get("fecha", ""))
            except ValueError:
                continue
            if (fecha.month, fecha.year) != (mes.month, mes.year):
                continue
            if tipo and factura.get("tipo") != tipo:
                continue
            if proveedor and proveedor not in factura.get("proveedor", "").casefold():
                continue
            resultado.append(factura)

        resultado.sort(key=lambda f: _fecha(f["fecha"]), reverse=True)
        return resultado

    def _actualizar_informe(self):
        try:
            facturas = self._facturas_filtradas()
        except ValueError as error:
            messagebox.showerror("Filtro inválido", str(error), parent=self)
            return

        total_contado = sum(f.get("monto", 0) for f in facturas if f.get("tipo") == "CONTADO")
        total_credito = sum(f.get("monto", 0) for f in facturas if f.get("tipo") == "CREDITO")
        self.resumen.configure(
            text=(
                f"  Contado: Gs. {_formatear_monto(total_contado)}"
                f"    |    Crédito: Gs. {_formatear_monto(total_credito)}"
                f"    |    Total general: Gs. {_formatear_monto(total_contado + total_credito)}"
                f"    |    Cantidad: {len(facturas)}"
            )
        )

        for item in self.tabla.get_children():
            self.tabla.delete(item)

        for factura in facturas:
            plazo = f"{factura.get('plazo_dias', 0)} días" if factura.get("tipo") == "CREDITO" else "-"
            self.tabla.insert(
                "", "end", iid=factura.get("id"),
                values=(
                    factura.get("fecha", ""),
                    "Crédito" if factura.get("tipo") == "CREDITO" else "Contado",
                    factura.get("numero", ""),
                    factura.get("proveedor", ""),
                    _formatear_monto(factura.get("monto", 0)),
                    factura.get("origen", "") or "-",
                    plazo,
                    factura.get("vencimiento", "") or "-",
                ),
            )
        self.factura_seleccionada_id = None

    def _seleccionar_factura(self, _evento=None):
        seleccion = self.tabla.selection()
        self.factura_seleccionada_id = seleccion[0] if seleccion else None

    def _eliminar_factura(self):
        if not self.factura_seleccionada_id:
            messagebox.showwarning("Sin selección", "Seleccioná una factura de la tabla.", parent=self)
            return
        confirmar = messagebox.askyesno(
            "Eliminar factura",
            "¿Confirmás la eliminación del registro seleccionado?",
            parent=self,
        )
        if not confirmar:
            return
        try:
            eliminar_factura_por_id(self.factura_seleccionada_id)
        except OSError as error:
            messagebox.showerror("No se pudo eliminar", str(error), parent=self)
            return
        self._actualizar_informe()


def abrir_facturas(master):
    ventana = VentanaFacturas(master)
    ventana.grab_set()
    return ventana
