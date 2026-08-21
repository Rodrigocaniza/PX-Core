"""La pantalla comercial: Artículos, Proveedores y Compras.

Cuatro slices dejaron el circuito cerrado y sin una sola pantalla desde donde
usarlo. Esto es esa pantalla.

Toda la lógica vive en `ComercialController` y en los servicios de dominio. Acá
no se decide nada: se pregunta, se muestra y se avisa. Si una regla apareciera
escrita en esta ventana, el día que el dominio la cambie la pantalla seguiría
diciendo la vieja.

Lo que el operador nunca ve: ids, claves de idempotencia, eventos, efectos. Ve
códigos, nombres, cantidades y guaraníes.
"""

from __future__ import annotations

from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from ..domain.models import ArticleNature, Destination

# Mismo lenguaje visual que Caja: azul de acción, gris de apoyo, rojo de alerta.
AZUL = "#1672E8"
AZUL_HOVER = "#0F5FC7"
GRIS = "#6B7280"
GRIS_HOVER = "#4B5563"
ROJO = "#C0392B"
VERDE = "#1E8449"

NATURALEZAS = [(n.label, n.value) for n in ArticleNature]


def _monto(valor) -> str:
    """Guaraníes con puntos de mil. Vacío cuando no hay dato, nunca «0»."""
    if valor is None or valor == "":
        return ""
    try:
        return f"{int(valor):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(valor)


def _entero(texto: str):
    limpio = str(texto or "").replace(".", "").replace(" ", "").strip()
    return int(limpio) if limpio else None


class VentanaComercial(ctk.CTkToplevel):
    """Ventana única con las tres pestañas de la operación comercial."""

    def __init__(self, master, controller, *, actor: str = "admin",
                 unidad: str = "PC") -> None:
        super().__init__(master)
        self.controller = controller
        self.actor = actor
        self.unidad = unidad
        self.title("Comercial — Artículos, Proveedores y Compras")
        self.geometry("1180x720")
        self.minsize(1024, 640)

        self.pestanas = ctk.CTkTabview(self, anchor="w")
        self.pestanas.pack(fill="both", expand=True, padx=12, pady=12)
        for nombre in ("Artículos", "Proveedores", "Compras"):
            self.pestanas.add(nombre)

        self._armar_articulos(self.pestanas.tab("Artículos"))
        self._armar_proveedores(self.pestanas.tab("Proveedores"))
        self._armar_compras(self.pestanas.tab("Compras"))

        self.refrescar_articulos()
        self.refrescar_proveedores()

    # ==================================================================
    # Artículos
    # ==================================================================

    def _armar_articulos(self, contenedor) -> None:
        barra = ctk.CTkFrame(contenedor, fg_color="transparent")
        barra.pack(fill="x", padx=8, pady=(8, 4))

        self.busqueda_articulo = ctk.CTkEntry(
            barra, placeholder_text="Buscar por código, descripción o código de barras",
            width=380, height=34)
        self.busqueda_articulo.pack(side="left")
        # Enter busca: es lo que la mano hace sola después de tipear.
        self.busqueda_articulo.bind("<Return>", lambda _e: self.refrescar_articulos())

        self.filtro_naturaleza = ctk.CTkOptionMenu(
            barra, width=200, height=34,
            values=["Todas"] + [etiqueta for etiqueta, _ in NATURALEZAS],
            command=lambda _v: self.refrescar_articulos())
        self.filtro_naturaleza.set("Todas")
        self.filtro_naturaleza.pack(side="left", padx=8)

        self.ver_inactivos = ctk.CTkCheckBox(
            barra, text="Ver inactivos", command=self.refrescar_articulos)
        self.ver_inactivos.pack(side="left", padx=8)

        ctk.CTkButton(barra, text="Buscar", width=90, height=34, fg_color=GRIS,
                      hover_color=GRIS_HOVER,
                      command=self.refrescar_articulos).pack(side="left")
        ctk.CTkButton(barra, text="+ Nuevo artículo", width=150, height=34,
                      fg_color=AZUL, hover_color=AZUL_HOVER,
                      command=self.abrir_alta_de_articulo).pack(side="right")
        ctk.CTkButton(barra, text="Cargar desde archivo…", width=180, height=34,
                      fg_color=GRIS, hover_color=GRIS_HOVER,
                      command=self.abrir_carga_inicial).pack(side="right", padx=8)

        columnas = ("codigo", "descripcion", "categoria", "marca", "naturaleza",
                    "costo", "precio", "ubicacion", "estado")
        self.grilla_articulos = ttk.Treeview(
            contenedor, columns=columnas, show="headings", height=20)
        for columna, titulo, ancho in (
            ("codigo", "Código", 120), ("descripcion", "Descripción", 260),
            ("categoria", "Categoría", 130), ("marca", "Marca", 110),
            ("naturaleza", "Naturaleza", 160), ("costo", "Costo", 100),
            ("precio", "Precio", 100), ("ubicacion", "Ubicación", 130),
            ("estado", "Estado", 90),
        ):
            self.grilla_articulos.heading(columna, text=titulo)
            self.grilla_articulos.column(
                columna, width=ancho,
                anchor="e" if columna in ("costo", "precio") else "w")
        self.grilla_articulos.pack(fill="both", expand=True, padx=8, pady=4)
        self.grilla_articulos.bind(
            "<Double-1>", lambda _e: self.abrir_edicion_de_articulo())

        pie = ctk.CTkFrame(contenedor, fg_color="transparent")
        pie.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(pie, text="Editar", width=110, height=32, fg_color=GRIS,
                      hover_color=GRIS_HOVER,
                      command=self.abrir_edicion_de_articulo).pack(side="left")
        ctk.CTkButton(pie, text="Desactivar", width=120, height=32, fg_color=ROJO,
                      hover_color="#96281B",
                      command=self.desactivar_articulo).pack(side="left", padx=8)
        self.resumen_articulos = ctk.CTkLabel(pie, text="", text_color=GRIS)
        self.resumen_articulos.pack(side="right")

    def refrescar_articulos(self) -> None:
        for fila in self.grilla_articulos.get_children():
            self.grilla_articulos.delete(fila)

        naturaleza = None
        elegido = self.filtro_naturaleza.get()
        for etiqueta, valor in NATURALEZAS:
            if etiqueta == elegido:
                naturaleza = valor

        articulos = self.controller.buscar_articulos(
            self.busqueda_articulo.get(), naturaleza=naturaleza,
            solo_activos=not self.ver_inactivos.get())
        categorias = {c.id: c.name for c in self.controller.listar_categorias(
            solo_activas=False)}
        marcas = {m.id: m.name for m in self.controller.listar_marcas(
            solo_activas=False)}

        for articulo in articulos:
            costo = self.controller.costo_de_referencia(articulo.id)
            # Sin factura no se muestra un número: se dice que falta conciliar.
            costo_visible = (_monto(costo.valor) if costo.valor is not None
                             else "pendiente")
            self.grilla_articulos.insert(
                "", "end", iid=articulo.id,
                values=(articulo.sku, articulo.name,
                        categorias.get(articulo.category_id, ""),
                        marcas.get(articulo.brand_id, ""),
                        articulo.nature.label, costo_visible,
                        _monto(articulo.sale_price), articulo.location,
                        "Activo" if articulo.active else "Inactivo"))
        self.resumen_articulos.configure(text=f"{len(articulos)} artículos")

    def _articulo_seleccionado(self):
        seleccion = self.grilla_articulos.selection()
        if not seleccion:
            messagebox.showinfo("Artículos", "Elegí un artículo de la lista.",
                                parent=self)
            return None
        return self.controller.obtener_articulo(seleccion[0])

    def abrir_alta_de_articulo(self) -> None:
        FormularioDeArticulo(self, self.controller, actor=self.actor,
                             al_guardar=self.refrescar_articulos)

    def abrir_edicion_de_articulo(self) -> None:
        articulo = self._articulo_seleccionado()
        if articulo is not None:
            FormularioDeArticulo(self, self.controller, actor=self.actor,
                                 articulo=articulo,
                                 al_guardar=self.refrescar_articulos)

    def desactivar_articulo(self) -> None:
        articulo = self._articulo_seleccionado()
        if articulo is None:
            return
        motivo = ctk.CTkInputDialog(
            text=f"¿Por qué se desactiva «{articulo.name}»?",
            title="Desactivar artículo").get_input()
        if not motivo:
            return
        try:
            self.controller.desactivar_articulo(
                articulo.id, actor=self.actor, motivo=motivo)
        except Exception as error:
            messagebox.showwarning("No se puede desactivar", str(error), parent=self)
            return
        self.refrescar_articulos()

    def abrir_carga_inicial(self) -> None:
        CargaInicialDialog(self, self.controller, actor=self.actor,
                           al_terminar=self.refrescar_articulos)

    # ==================================================================
    # Proveedores
    # ==================================================================

    def _armar_proveedores(self, contenedor) -> None:
        barra = ctk.CTkFrame(contenedor, fg_color="transparent")
        barra.pack(fill="x", padx=8, pady=(8, 4))
        self.busqueda_proveedor = ctk.CTkEntry(
            barra, placeholder_text="Buscar por razón social o RUC", width=380,
            height=34)
        self.busqueda_proveedor.pack(side="left")
        self.busqueda_proveedor.bind("<Return>", lambda _e: self.refrescar_proveedores())
        ctk.CTkButton(barra, text="Buscar", width=90, height=34, fg_color=GRIS,
                      hover_color=GRIS_HOVER,
                      command=self.refrescar_proveedores).pack(side="left", padx=8)
        ctk.CTkButton(barra, text="+ Nuevo proveedor", width=170, height=34,
                      fg_color=AZUL, hover_color=AZUL_HOVER,
                      command=self.abrir_alta_de_proveedor).pack(side="right")

        columnas = ("razon", "ruc", "telefono", "contacto", "estado")
        self.grilla_proveedores = ttk.Treeview(
            contenedor, columns=columnas, show="headings", height=20)
        for columna, titulo, ancho in (
            ("razon", "Razón social", 300), ("ruc", "RUC / CI", 140),
            ("telefono", "Teléfono", 140), ("contacto", "Contacto", 200),
            ("estado", "Estado", 90),
        ):
            self.grilla_proveedores.heading(columna, text=titulo)
            self.grilla_proveedores.column(columna, width=ancho, anchor="w")
        self.grilla_proveedores.pack(fill="both", expand=True, padx=8, pady=4)
        self.grilla_proveedores.bind(
            "<Double-1>", lambda _e: self.abrir_edicion_de_proveedor())

        pie = ctk.CTkFrame(contenedor, fg_color="transparent")
        pie.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(pie, text="Editar", width=110, height=32, fg_color=GRIS,
                      hover_color=GRIS_HOVER,
                      command=self.abrir_edicion_de_proveedor).pack(side="left")
        ctk.CTkButton(pie, text="Desactivar", width=120, height=32, fg_color=ROJO,
                      hover_color="#96281B",
                      command=self.desactivar_proveedor).pack(side="left", padx=8)

    def refrescar_proveedores(self) -> None:
        for fila in self.grilla_proveedores.get_children():
            self.grilla_proveedores.delete(fila)
        for proveedor in self.controller.buscar_proveedores(
                self.busqueda_proveedor.get(), solo_activos=False):
            self.grilla_proveedores.insert(
                "", "end", iid=proveedor.id,
                values=(proveedor.name, proveedor.document, proveedor.phone,
                        proveedor.contact_name,
                        "Activo" if proveedor.active else "Inactivo"))

    def abrir_alta_de_proveedor(self) -> None:
        FormularioDeProveedor(self, self.controller, actor=self.actor,
                              al_guardar=self.refrescar_proveedores)

    def abrir_edicion_de_proveedor(self) -> None:
        seleccion = self.grilla_proveedores.selection()
        if not seleccion:
            return
        FormularioDeProveedor(
            self, self.controller, actor=self.actor,
            proveedor=self.controller.obtener_proveedor(seleccion[0]),
            al_guardar=self.refrescar_proveedores)

    def desactivar_proveedor(self) -> None:
        seleccion = self.grilla_proveedores.selection()
        if not seleccion:
            return
        motivo = ctk.CTkInputDialog(
            text="¿Por qué se desactiva este proveedor?",
            title="Desactivar proveedor").get_input()
        if not motivo:
            return
        self.controller.desactivar_proveedor(
            seleccion[0], actor=self.actor, motivo=motivo)
        self.refrescar_proveedores()

    # ==================================================================
    # Compras
    # ==================================================================

    def _armar_compras(self, contenedor) -> None:
        barra = ctk.CTkFrame(contenedor, fg_color="transparent")
        barra.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(barra, text="Facturas de compra",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        ctk.CTkButton(barra, text="+ Nueva compra", width=160, height=34,
                      fg_color=AZUL, hover_color=AZUL_HOVER,
                      command=self.abrir_nueva_compra).pack(side="right")

        columnas = ("fecha", "proveedor", "numero", "condicion", "vencimiento",
                    "total", "estado")
        self.grilla_compras = ttk.Treeview(
            contenedor, columns=columnas, show="headings", height=20)
        for columna, titulo, ancho in (
            ("fecha", "Fecha", 110), ("proveedor", "Proveedor", 240),
            ("numero", "N.º factura", 160), ("condicion", "Condición", 110),
            ("vencimiento", "Vence", 110), ("total", "Total", 130),
            ("estado", "Estado", 120),
        ):
            self.grilla_compras.heading(columna, text=titulo)
            self.grilla_compras.column(
                columna, width=ancho, anchor="e" if columna == "total" else "w")
        self.grilla_compras.pack(fill="both", expand=True, padx=8, pady=4)
        self.refrescar_compras()

    def refrescar_compras(self) -> None:
        for fila in self.grilla_compras.get_children():
            self.grilla_compras.delete(fila)
        proveedores = {p.id: p.name for p in
                       self.controller.buscar_proveedores(solo_activos=False)}
        for compra in self.controller.listar_compras():
            self.grilla_compras.insert(
                "", "end", iid=compra.id,
                values=(compra.document_date.strftime("%d/%m/%Y"),
                        proveedores.get(compra.supplier_id, ""),
                        compra.document_number, compra.condition.value,
                        compra.due_date.strftime("%d/%m/%Y") if compra.due_date else "",
                        _monto(compra.document_total), compra.status.value))

    def abrir_nueva_compra(self) -> None:
        FormularioDeCompra(self, self.controller, actor=self.actor,
                           al_confirmar=self.refrescar_compras)


class FormularioDeArticulo(ctk.CTkToplevel):
    """Alta y edición. Categoría y marca se crean sin salir de acá."""

    def __init__(self, master, controller, *, actor: str, articulo=None,
                 al_guardar=None) -> None:
        super().__init__(master)
        self.controller = controller
        self.actor = actor
        self.articulo = articulo
        self.al_guardar = al_guardar
        self.title("Editar artículo" if articulo else "Nuevo artículo")
        self.geometry("560x620")
        self.grab_set()

        cuerpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=16, pady=12)

        self.campos = {}
        for clave, etiqueta in (
            ("sku", "Código *"), ("name", "Descripción *"),
            ("sale_price", "Precio de venta"), ("location", "Ubicación / fila / góndola"),
            ("min_stock", "Stock mínimo"), ("barcode", "Código de barras"),
            ("notes", "Observaciones"),
        ):
            ctk.CTkLabel(cuerpo, text=etiqueta, anchor="w").pack(fill="x", pady=(8, 2))
            campo = ctk.CTkEntry(cuerpo, height=34)
            campo.pack(fill="x")
            self.campos[clave] = campo

        ctk.CTkLabel(cuerpo, text="Naturaleza *", anchor="w").pack(fill="x", pady=(12, 2))
        self.naturaleza = ctk.CTkOptionMenu(
            cuerpo, values=[etiqueta for etiqueta, _ in NATURALEZAS], height=34)
        self.naturaleza.pack(fill="x")
        ctk.CTkLabel(
            cuerpo, text="De la naturaleza depende si el artículo mueve stock.",
            text_color=GRIS, anchor="w").pack(fill="x", pady=(2, 0))

        self.categoria = self._selector_con_alta(cuerpo, "Categoría", self._crear_categoria)
        self.marca = self._selector_con_alta(cuerpo, "Marca", self._crear_marca)

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkButton(pie, text="Guardar", height=36, fg_color=AZUL,
                      hover_color=AZUL_HOVER, command=self.guardar).pack(side="right")
        ctk.CTkButton(pie, text="Cancelar", height=36, fg_color=GRIS,
                      hover_color=GRIS_HOVER,
                      command=self.destroy).pack(side="right", padx=8)

        self._recargar_catalogos()
        if articulo is not None:
            self._cargar(articulo)

    def _selector_con_alta(self, contenedor, etiqueta, comando_alta):
        ctk.CTkLabel(contenedor, text=etiqueta, anchor="w").pack(fill="x", pady=(12, 2))
        fila = ctk.CTkFrame(contenedor, fg_color="transparent")
        fila.pack(fill="x")
        selector = ctk.CTkOptionMenu(fila, values=["—"], height=34)
        selector.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(fila, text="+ Crear", width=90, height=34, fg_color=GRIS,
                      hover_color=GRIS_HOVER,
                      command=comando_alta).pack(side="left", padx=(8, 0))
        return selector

    def _recargar_catalogos(self) -> None:
        self._categorias = {c.name: c.id for c in self.controller.listar_categorias()}
        self._marcas = {m.name: m.id for m in self.controller.listar_marcas()}
        self.categoria.configure(values=["—"] + sorted(self._categorias))
        self.marca.configure(values=["—"] + sorted(self._marcas))

    def _crear_categoria(self) -> None:
        nombre = ctk.CTkInputDialog(text="Nombre de la categoría",
                                    title="+ Crear categoría").get_input()
        if not nombre:
            return
        creada = self.controller.crear_categoria(nombre, actor=self.actor)
        self._recargar_catalogos()
        self.categoria.set(creada.name)

    def _crear_marca(self) -> None:
        nombre = ctk.CTkInputDialog(text="Nombre de la marca",
                                    title="+ Crear marca").get_input()
        if not nombre:
            return
        creada = self.controller.crear_marca(nombre, actor=self.actor)
        self._recargar_catalogos()
        self.marca.set(creada.name)

    def _cargar(self, articulo) -> None:
        valores = {
            "sku": articulo.sku, "name": articulo.name,
            "sale_price": _monto(articulo.sale_price), "location": articulo.location,
            "min_stock": "" if articulo.min_stock is None else str(articulo.min_stock),
            "barcode": articulo.barcode or "", "notes": articulo.notes,
        }
        for clave, valor in valores.items():
            self.campos[clave].insert(0, valor)
        self.naturaleza.set(articulo.nature.label)
        for nombre, identificador in self._categorias.items():
            if identificador == articulo.category_id:
                self.categoria.set(nombre)
        for nombre, identificador in self._marcas.items():
            if identificador == articulo.brand_id:
                self.marca.set(nombre)

    def guardar(self) -> None:
        etiqueta = self.naturaleza.get()
        naturaleza = next(v for e, v in NATURALEZAS if e == etiqueta)
        # El formulario no muestra proveedor ni unidad. Al editar se toca sólo lo
        # que está en pantalla: lo que no se ve tampoco se pisa.
        editado = dict(
            sku=self.campos["sku"].get(), name=self.campos["name"].get(),
            nature=naturaleza,
            category_id=self._categorias.get(self.categoria.get()),
            brand_id=self._marcas.get(self.marca.get()),
            sale_price=_entero(self.campos["sale_price"].get()),
            location=self.campos["location"].get(),
            min_stock=_entero(self.campos["min_stock"].get()),
            barcode=self.campos["barcode"].get() or None,
            notes=self.campos["notes"].get())
        try:
            if self.articulo is not None:
                self.controller.actualizar_articulo(
                    self.articulo.id, actor=self.actor, **editado)
            else:
                self.controller.guardar_articulo(actor=self.actor, **editado)
        except Exception as error:
            messagebox.showwarning("No se pudo guardar", str(error), parent=self)
            return
        if self.al_guardar:
            self.al_guardar()
        self.destroy()


class FormularioDeProveedor(ctk.CTkToplevel):
    def __init__(self, master, controller, *, actor: str, proveedor=None,
                 al_guardar=None) -> None:
        super().__init__(master)
        self.controller = controller
        self.actor = actor
        self.proveedor = proveedor
        self.al_guardar = al_guardar
        self.title("Editar proveedor" if proveedor else "Nuevo proveedor")
        self.geometry("520x520")
        self.grab_set()

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=16, pady=12)
        self.campos = {}
        for clave, etiqueta in (
            ("name", "Razón social *"), ("document", "RUC / CI"),
            ("phone", "Teléfono"), ("address", "Dirección"),
            ("email", "Email"), ("contact_name", "Contacto"),
        ):
            ctk.CTkLabel(cuerpo, text=etiqueta, anchor="w").pack(fill="x", pady=(8, 2))
            campo = ctk.CTkEntry(cuerpo, height=34)
            campo.pack(fill="x")
            self.campos[clave] = campo
            if proveedor is not None:
                campo.insert(0, getattr(proveedor, clave, "") or "")

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkButton(pie, text="Guardar", height=36, fg_color=AZUL,
                      hover_color=AZUL_HOVER, command=self.guardar).pack(side="right")
        ctk.CTkButton(pie, text="Cancelar", height=36, fg_color=GRIS,
                      hover_color=GRIS_HOVER,
                      command=self.destroy).pack(side="right", padx=8)

    def guardar(self) -> None:
        try:
            self.controller.guardar_proveedor(
                actor=self.actor,
                supplier_id=self.proveedor.id if self.proveedor else None,
                active=self.proveedor.active if self.proveedor else True,
                **{clave: campo.get() for clave, campo in self.campos.items()})
        except Exception as error:
            messagebox.showwarning("No se pudo guardar", str(error), parent=self)
            return
        if self.al_guardar:
            self.al_guardar()
        self.destroy()


class FormularioDeCompra(ctk.CTkToplevel):
    """Cargar una factura real: proveedor, datos, líneas, reparto y confirmar."""

    def __init__(self, master, controller, *, actor: str, al_confirmar=None) -> None:
        super().__init__(master)
        self.controller = controller
        self.actor = actor
        self.al_confirmar = al_confirmar
        self.lineas = []
        self.title("Nueva compra")
        self.geometry("960x720")
        self.grab_set()

        cabecera = ctk.CTkFrame(self)
        cabecera.pack(fill="x", padx=14, pady=(12, 6))
        self._proveedores = {p.name: p.id
                             for p in controller.buscar_proveedores()}
        self.campos = {}

        fila = ctk.CTkFrame(cabecera, fg_color="transparent")
        fila.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(fila, text="Proveedor *", width=110, anchor="w").pack(side="left")
        self.proveedor = ctk.CTkOptionMenu(
            fila, values=["—"] + sorted(self._proveedores), width=300, height=32)
        self.proveedor.pack(side="left")
        ctk.CTkButton(fila, text="+ Crear proveedor", width=150, height=32,
                      fg_color=GRIS, hover_color=GRIS_HOVER,
                      command=self._crear_proveedor).pack(side="left", padx=8)

        for clave, etiqueta, ancho in (
            ("document_date", "Fecha *", 140), ("document_number", "N.º factura *", 200),
            ("stamped_number", "Timbrado", 160), ("receipt_reference", "Recibo / ref.", 160),
        ):
            fila = ctk.CTkFrame(cabecera, fg_color="transparent")
            fila.pack(fill="x", padx=10, pady=4)
            ctk.CTkLabel(fila, text=etiqueta, width=110, anchor="w").pack(side="left")
            campo = ctk.CTkEntry(fila, width=ancho, height=32)
            campo.pack(side="left")
            self.campos[clave] = campo
        self.campos["document_date"].insert(0, date.today().strftime("%d/%m/%Y"))

        fila = ctk.CTkFrame(cabecera, fg_color="transparent")
        fila.pack(fill="x", padx=10, pady=(4, 10))
        ctk.CTkLabel(fila, text="Condición *", width=110, anchor="w").pack(side="left")
        self.condicion = ctk.CTkOptionMenu(
            fila, values=["CONTADO", "CREDITO"], width=140, height=32,
            command=lambda _v: self._refrescar_vencimiento())
        self.condicion.pack(side="left")
        ctk.CTkLabel(fila, text="Plazo (días)", width=100, anchor="e").pack(side="left")
        self.plazo = ctk.CTkEntry(fila, width=80, height=32)
        self.plazo.pack(side="left", padx=6)
        self.plazo.bind("<KeyRelease>", lambda _e: self._refrescar_vencimiento())
        # El vencimiento no se escribe: se deriva de la fecha y el plazo.
        self.vencimiento = ctk.CTkLabel(fila, text="Vence: —", text_color=GRIS)
        self.vencimiento.pack(side="left", padx=12)

        acciones = ctk.CTkFrame(self, fg_color="transparent")
        acciones.pack(fill="x", padx=14)
        ctk.CTkButton(acciones, text="+ Agregar línea", height=32, width=150,
                      fg_color=AZUL, hover_color=AZUL_HOVER,
                      command=self._agregar_linea).pack(side="left")
        ctk.CTkButton(acciones, text="Quitar línea", height=32, width=130,
                      fg_color=GRIS, hover_color=GRIS_HOVER,
                      command=self._quitar_linea).pack(side="left", padx=8)

        columnas = ("codigo", "descripcion", "cantidad", "costo", "subtotal",
                    "asuncion", "pilar")
        self.grilla = ttk.Treeview(self, columns=columnas, show="headings", height=12)
        for columna, titulo, ancho in (
            ("codigo", "Código", 120), ("descripcion", "Artículo", 260),
            ("cantidad", "Cant.", 70), ("costo", "Costo unit.", 110),
            ("subtotal", "Subtotal", 120), ("asuncion", "Asunción", 90),
            ("pilar", "Pilar", 90),
        ):
            self.grilla.heading(columna, text=titulo)
            self.grilla.column(
                columna, width=ancho,
                anchor="e" if columna in ("cantidad", "costo", "subtotal",
                                          "asuncion", "pilar") else "w")
        self.grilla.pack(fill="both", expand=True, padx=14, pady=8)

        pie = ctk.CTkFrame(self)
        pie.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkLabel(pie, text="Total de la factura", anchor="w").pack(
            side="left", padx=(10, 6), pady=10)
        self.total_documento = ctk.CTkEntry(pie, width=140, height=32)
        self.total_documento.pack(side="left")
        self.total_calculado = ctk.CTkLabel(pie, text="Suma de líneas: 0",
                                            text_color=GRIS)
        self.total_calculado.pack(side="left", padx=16)
        ctk.CTkButton(pie, text="Confirmar compra", height=36, width=180,
                      fg_color=VERDE, hover_color="#186A3B",
                      command=self.confirmar).pack(side="right", padx=10)

    def _crear_proveedor(self) -> None:
        FormularioDeProveedor(self, self.controller, actor=self.actor,
                              al_guardar=self._recargar_proveedores)

    def _recargar_proveedores(self) -> None:
        self._proveedores = {p.name: p.id
                             for p in self.controller.buscar_proveedores()}
        self.proveedor.configure(values=["—"] + sorted(self._proveedores))

    def _refrescar_vencimiento(self) -> None:
        if self.condicion.get() != "CREDITO":
            self.vencimiento.configure(text="Vence: —")
            return
        try:
            fecha = datetime.strptime(
                self.campos["document_date"].get().strip(), "%d/%m/%Y").date()
            dias = int(self.plazo.get().strip())
        except ValueError:
            self.vencimiento.configure(text="Vence: —")
            return
        from datetime import timedelta
        self.vencimiento.configure(
            text=f"Vence: {(fecha + timedelta(days=dias)).strftime('%d/%m/%Y')}")

    def _agregar_linea(self) -> None:
        LineaDeCompraDialog(self, self.controller, al_aceptar=self._sumar_linea)

    def _sumar_linea(self, linea: dict) -> None:
        self.lineas.append(linea)
        self._refrescar_lineas()

    def _quitar_linea(self) -> None:
        seleccion = self.grilla.selection()
        if seleccion:
            self.lineas.pop(int(seleccion[0]))
            self._refrescar_lineas()

    def _refrescar_lineas(self) -> None:
        for fila in self.grilla.get_children():
            self.grilla.delete(fila)
        total = 0
        for indice, linea in enumerate(self.lineas):
            subtotal = linea["quantity"] * linea["unit_cost"]
            total += subtotal
            reparto = linea.get("distribucion") or {}
            self.grilla.insert(
                "", "end", iid=str(indice),
                values=(linea["sku"], linea["description"], linea["quantity"],
                        _monto(linea["unit_cost"]), _monto(subtotal),
                        reparto.get(Destination.ASUNCION, "") or "",
                        reparto.get(Destination.PILAR, "") or ""))
        self.total_calculado.configure(text=f"Suma de líneas: {_monto(total)}")

    def confirmar(self) -> None:
        if self.proveedor.get() not in self._proveedores:
            messagebox.showwarning("Falta el proveedor",
                                   "Elegí el proveedor de la factura.", parent=self)
            return
        try:
            fecha = datetime.strptime(
                self.campos["document_date"].get().strip(), "%d/%m/%Y").date()
        except ValueError:
            messagebox.showwarning("Fecha inválida",
                                   "La fecha va en formato dd/mm/aaaa.", parent=self)
            return

        try:
            compra = self.controller.crear_compra_borrador(
                supplier_id=self._proveedores[self.proveedor.get()],
                document_date=fecha,
                document_number=self.campos["document_number"].get(),
                stamped_number=self.campos["stamped_number"].get(),
                receipt_reference=self.campos["receipt_reference"].get(),
                condition=self.condicion.get(),
                credit_days=(_entero(self.plazo.get())
                             if self.condicion.get() == "CREDITO" else None),
                document_total=_entero(self.total_documento.get()),
                lineas=self.lineas, actor=self.actor)
        except Exception as error:
            messagebox.showwarning("No se pudo cargar la factura", str(error),
                                   parent=self)
            return

        # La pantalla no repite las reglas: le pregunta al dominio.
        revision = self.controller.revisar_compra(compra.id)
        if not revision.confirmable:
            messagebox.showwarning(
                "Falta corregir", "\n\n".join(revision.problemas), parent=self)
            return
        try:
            self.controller.confirmar_compra(compra.id, actor=self.actor)
        except Exception as error:
            messagebox.showwarning("No se pudo confirmar", str(error), parent=self)
            return
        messagebox.showinfo(
            "Compra confirmada",
            "La mercadería quedó ingresada al stock de cada sucursal.", parent=self)
        if self.al_confirmar:
            self.al_confirmar()
        self.destroy()


class LineaDeCompraDialog(ctk.CTkToplevel):
    """Una línea: artículo, cantidad, costo y —si mueve stock— el reparto."""

    def __init__(self, master, controller, *, al_aceptar) -> None:
        super().__init__(master)
        self.controller = controller
        self.al_aceptar = al_aceptar
        self.articulo = None
        self.title("Línea de la factura")
        self.geometry("560x420")
        self.grab_set()

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=16, pady=12)

        ctk.CTkLabel(cuerpo, text="Artículo *", anchor="w").pack(fill="x")
        fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
        fila.pack(fill="x", pady=(2, 8))
        self.articulo_texto = ctk.CTkLabel(fila, text="— sin elegir —", anchor="w")
        self.articulo_texto.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(fila, text="Buscar…", width=110, height=32, fg_color=GRIS,
                      hover_color=GRIS_HOVER,
                      command=self._buscar_articulo).pack(side="left")

        self.campos = {}
        for clave, etiqueta in (("quantity", "Cantidad *"),
                                ("unit_cost", "Costo unitario *")):
            ctk.CTkLabel(cuerpo, text=etiqueta, anchor="w").pack(fill="x", pady=(8, 2))
            campo = ctk.CTkEntry(cuerpo, height=34)
            campo.pack(fill="x")
            self.campos[clave] = campo

        # El reparto sólo aparece si el artículo genera unidades. Mostrárselo a
        # un cristal invitaría a llenarlo, y no significaría nada.
        self.marco_reparto = ctk.CTkFrame(cuerpo, fg_color="transparent")
        ctk.CTkLabel(self.marco_reparto, text="Distribución física", anchor="w").pack(
            fill="x", pady=(12, 2))
        reparto = ctk.CTkFrame(self.marco_reparto, fg_color="transparent")
        reparto.pack(fill="x")
        self.reparto = {}
        for destino in Destination:
            ctk.CTkLabel(reparto, text=destino.value.title(), width=90,
                         anchor="w").pack(side="left")
            campo = ctk.CTkEntry(reparto, width=80, height=32)
            campo.pack(side="left", padx=(0, 16))
            self.reparto[destino] = campo

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkButton(pie, text="Agregar", height=36, fg_color=AZUL,
                      hover_color=AZUL_HOVER, command=self.aceptar).pack(side="right")
        ctk.CTkButton(pie, text="Cancelar", height=36, fg_color=GRIS,
                      hover_color=GRIS_HOVER,
                      command=self.destroy).pack(side="right", padx=8)

    def _buscar_articulo(self) -> None:
        BuscadorDeArticulos(self, self.controller, unidad=None,
                            al_elegir=self._elegir_articulo)

    def _elegir_articulo(self, opcion) -> None:
        self.articulo = opcion
        self.articulo_texto.configure(text=f"{opcion.sku} — {opcion.name}")
        if self.controller.linea_necesita_distribucion(opcion.article_id):
            self.marco_reparto.pack(fill="x")
        else:
            self.marco_reparto.pack_forget()

    def aceptar(self) -> None:
        if self.articulo is None:
            messagebox.showwarning("Falta el artículo",
                                   "Elegí el artículo de la línea.", parent=self)
            return
        cantidad = _entero(self.campos["quantity"].get())
        costo = _entero(self.campos["unit_cost"].get())
        if not cantidad or costo is None:
            messagebox.showwarning("Faltan datos",
                                   "La línea necesita cantidad y costo unitario.",
                                   parent=self)
            return
        distribucion = {}
        if self.controller.linea_necesita_distribucion(self.articulo.article_id):
            for destino, campo in self.reparto.items():
                valor = _entero(campo.get())
                if valor:
                    distribucion[destino] = valor
        self.al_aceptar({
            "article_id": self.articulo.article_id, "sku": self.articulo.sku,
            "description": self.articulo.name, "quantity": cantidad,
            "unit_cost": costo, "distribucion": distribucion})
        self.destroy()


class BuscadorDeArticulos(ctk.CTkToplevel):
    """Buscador reusable. Es el mismo que usa la línea de venta en Caja."""

    def __init__(self, master, controller, *, unidad, al_elegir,
                 solo_stockeables: bool = False) -> None:
        super().__init__(master)
        self.controller = controller
        self.unidad = unidad
        self.al_elegir = al_elegir
        self.solo_stockeables = solo_stockeables
        self.title("Buscar artículo")
        self.geometry("820x460")
        self.grab_set()

        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", padx=14, pady=(12, 6))
        self.busqueda = ctk.CTkEntry(
            barra, placeholder_text="Código, descripción o código de barras",
            height=36)
        self.busqueda.pack(side="left", fill="x", expand=True)
        self.busqueda.bind("<Return>", lambda _e: self.buscar())
        self.busqueda.focus_set()
        ctk.CTkButton(barra, text="Buscar", width=100, height=36, fg_color=AZUL,
                      hover_color=AZUL_HOVER, command=self.buscar).pack(
                          side="left", padx=8)

        columnas = ("codigo", "descripcion", "categoria", "marca", "precio",
                    "ubicacion", "stock")
        self.grilla = ttk.Treeview(self, columns=columnas, show="headings", height=14)
        for columna, titulo, ancho in (
            ("codigo", "Código", 120), ("descripcion", "Descripción", 250),
            ("categoria", "Categoría", 120), ("marca", "Marca", 100),
            ("precio", "Precio", 100), ("ubicacion", "Ubicación", 110),
            ("stock", "Stock acá", 90),
        ):
            self.grilla.heading(columna, text=titulo)
            self.grilla.column(
                columna, width=ancho,
                anchor="e" if columna in ("precio", "stock") else "w")
        self.grilla.pack(fill="both", expand=True, padx=14, pady=6)
        self.grilla.bind("<Double-1>", lambda _e: self.elegir())

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkButton(pie, text="Elegir", height=36, width=120, fg_color=AZUL,
                      hover_color=AZUL_HOVER, command=self.elegir).pack(side="right")
        self.aviso = ctk.CTkLabel(pie, text="", text_color=GRIS)
        self.aviso.pack(side="left")

        self._opciones = {}
        self.buscar()

    def buscar(self) -> None:
        for fila in self.grilla.get_children():
            self.grilla.delete(fila)
        self._opciones = {}
        opciones = self.controller.buscar_para_venta(
            self.busqueda.get(), unidad=self.unidad or "")
        for opcion in opciones:
            if self.solo_stockeables and not opcion.mueve_stock:
                continue
            self._opciones[opcion.article_id] = opcion
            # Un servicio no tiene stock cero: no tiene stock.
            stock = {"NO_LLEVA_STOCK": "—",
                     "SUCURSAL_DESCONOCIDA": "?",
                     "SIN_STOCK": "sin stock",
                     "INACTIVO": "inactivo"}.get(opcion.estado, str(opcion.stock))
            self.grilla.insert(
                "", "end", iid=opcion.article_id,
                values=(opcion.sku, opcion.name, opcion.category, opcion.brand,
                        _monto(opcion.sale_price), opcion.location, stock))
        self.aviso.configure(text=f"{len(self._opciones)} artículos")

    def elegir(self) -> None:
        seleccion = self.grilla.selection()
        if not seleccion:
            return
        opcion = self._opciones[seleccion[0]]
        if not opcion.vendible:
            messagebox.showwarning(
                "Artículo inactivo",
                f"«{opcion.name}» está inactivo y no se puede usar.", parent=self)
            return
        self.al_elegir(opcion)
        self.destroy()


class CargaInicialDialog(ctk.CTkToplevel):
    """Cargar el catálogo desde un archivo, en dos pasos: mirar y recién aplicar."""

    def __init__(self, master, controller, *, actor: str, al_terminar=None) -> None:
        super().__init__(master)
        self.controller = controller
        self.actor = actor
        self.al_terminar = al_terminar
        self.plan = None
        self.title("Cargar artículos desde archivo")
        self.geometry("720x520")
        self.grab_set()

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=16, pady=12)
        ctk.CTkLabel(
            cuerpo, anchor="w", justify="left", text=(
                "El archivo tiene que traer al menos estas columnas:\n"
                "    sku, name, nature\n"
                "y puede traer: category, brand, sale_price, location, min_stock,\n"
                "barcode, unit, notes.\n\n"
                "La naturaleza no se adivina: si falta, la fila se rechaza.\n"
                "Cargar el catálogo NO crea stock. Las unidades entran por un\n"
                "recuento, que es otro hecho.")).pack(fill="x", pady=(0, 10))

        acciones = ctk.CTkFrame(cuerpo, fg_color="transparent")
        acciones.pack(fill="x")
        ctk.CTkButton(acciones, text="Elegir archivo…", height=36, width=160,
                      fg_color=GRIS, hover_color=GRIS_HOVER,
                      command=self.elegir_archivo).pack(side="left")
        self.boton_aplicar = ctk.CTkButton(
            acciones, text="Aplicar carga", height=36, width=160, fg_color=AZUL,
            hover_color=AZUL_HOVER, state="disabled", command=self.aplicar)
        self.boton_aplicar.pack(side="left", padx=10)

        self.detalle = ctk.CTkTextbox(cuerpo, height=280)
        self.detalle.pack(fill="both", expand=True, pady=(12, 0))

    def elegir_archivo(self) -> None:
        ruta = filedialog.askopenfilename(
            parent=self, title="Archivo de artículos",
            filetypes=[("Planillas", "*.csv *.xlsx"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            self.plan = self.controller.planificar_carga_de_articulos(ruta)
        except Exception as error:
            self.plan = None
            self.boton_aplicar.configure(state="disabled")
            messagebox.showwarning("No se pudo leer el archivo", str(error),
                                   parent=self)
            return
        self._mostrar_plan()

    def _mostrar_plan(self) -> None:
        completitud = self.plan.completitud
        lineas = [
            f"Archivo: {self.plan.archivo.name}",
            f"Filas leídas: {completitud.filas}",
            "",
            f"Altas: {len(self.plan.altas)}",
            f"Actualizaciones: {len(self.plan.actualizaciones)}",
            f"Rechazadas: {len(self.plan.rechazos)}",
            "",
            "Lo que el archivo NO trae y habrá que completar después:",
        ]
        lineas += [f"  · {p}" for p in completitud.pendientes] or ["  · nada"]
        if self.plan.rechazos:
            lineas += ["", "Filas rechazadas (hay que corregir el archivo):"]
            lineas += [f"  · fila {r.fila} [{r.sku}]: {r.motivo}"
                       for r in self.plan.rechazos[:40]]
            if len(self.plan.rechazos) > 40:
                lineas.append(f"  · … y {len(self.plan.rechazos) - 40} más")
            lineas += ["", "Un plan con rechazos no se aplica a medias: cargar parte",
                       "dejaría un catálogo que nadie sabe describir."]
        self.detalle.delete("1.0", "end")
        self.detalle.insert("1.0", "\n".join(lineas))
        self.boton_aplicar.configure(
            state="normal" if self.plan.aplicable else "disabled")

    def aplicar(self) -> None:
        if self.plan is None:
            return
        try:
            corrida = self.controller.aplicar_carga_de_articulos(
                self.plan, actor=self.actor)
        except Exception as error:
            messagebox.showwarning("No se pudo aplicar", str(error), parent=self)
            return
        messagebox.showinfo(
            "Catálogo cargado",
            f"Se cargaron {corrida.rows_imported} artículos.\n\n"
            "Todavía no hay stock: las unidades entran por un recuento.",
            parent=self)
        if self.al_terminar:
            self.al_terminar()
        self.destroy()
