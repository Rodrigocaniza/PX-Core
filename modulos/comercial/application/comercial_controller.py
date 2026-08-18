"""Lo que la pantalla comercial necesita para operar.

Es el mismo papel que `CashDayUIController` cumple para Caja: traducir lo que la
operadora quiere hacer a los servicios de dominio que ya existen, y devolverle
cosas que se puedan mostrar sin que la pantalla tenga que saber de eventos, de
efectos ni de claves de idempotencia.

Este módulo **no** reimplementa nada. Confirmar una compra lo hace Compras;
mover stock lo hace el ledger; emitir un hecho lo hace el spine. Si la lógica
apareciera acá habría dos formas de hacer lo mismo, y tarde o temprano una de
las dos quedaría atrás.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from ..domain.compras import (
    Distribution,
    Purchase,
    PurchaseCondition,
    PurchaseLine,
)
from ..domain.models import (
    Article,
    ArticleNature,
    Brand,
    Category,
    CostStatus,
    Destination,
    StockMovement,
    StockMovementKind,
    Supplier,
)
from ..infrastructure.sqlite_catalog_repository import SQLiteCatalogRepository
from ..infrastructure.sqlite_purchase_repository import SQLitePurchaseRepository
from ..infrastructure.sqlite_stock_ledger import SQLiteStockLedgerRepository
from .carga_inicial import (
    CargaInicialError,
    CorridaDeCarga,
    ResumenDeCompletitud,
    leer_archivo_de_articulos,
    resumir_completitud,
    sha256_de,
)
from .compras import ComprasService, DistribucionInvalida, TotalNoCuadra
from .importer import ImportPlan, planificar_importacion
from .stock_ledger import StockLedgerService
from .ventas import VentasLedgerIntegrator


class ComercialError(ValueError):
    """Base de los rechazos de la pantalla comercial."""


class ArticuloEnUso(ComercialError):
    """No se puede desactivar algo que todavía tiene consecuencias vivas."""


#: Motivo canónico del ingreso por recuento. Lo siembra la migración 026.
MOTIVO_INVENTARIO_INICIAL = "INVENTARIO_INICIAL"

#: Cómo se nombra un recuento como documento de origen de un movimiento.
DOCUMENTO_CARGA_INICIAL = "CARGA_INICIAL"


@dataclass(frozen=True)
class CostoDeReferencia:
    """El costo que la pantalla muestra, con su procedencia.

    No es un dato del artículo: es lo que dijo la última factura. Cuando no hay
    factura no se inventa un número, se dice que falta conciliar.
    """

    valor: int | None
    estado: str
    document_number: str = ""
    document_date: str = ""
    supplier_name: str = ""


@dataclass(frozen=True)
class OpcionDeVenta:
    """Un artículo tal como se ve en el buscador de la venta.

    `stock` es `None` cuando no corresponde saberlo —un servicio no tiene stock
    cero, no tiene stock— y `estado` dice por qué, para que la pantalla no tenga
    que adivinar qué pintar.
    """

    article_id: str
    sku: str
    name: str
    category: str
    brand: str
    sale_price: int | None
    location: str
    mueve_stock: bool
    stock: int | None
    estado: str
    active: bool

    @property
    def vendible(self) -> bool:
        return self.active


@dataclass(frozen=True)
class RevisionDeCompra:
    """Lo que la pantalla muestra antes de dejar confirmar."""

    total_documento: int
    total_lineas: int
    confirmable: bool
    problemas: tuple[str, ...]


@dataclass(frozen=True)
class CambioDeArticulo:
    """Una edición administrativa, tal como quedó registrada."""

    actor: str
    accion: str
    detalle: str
    momento: str


@dataclass(frozen=True)
class PlanDeCargaInicial:
    """El plan de importar un archivo. Todavía no escribió nada."""

    archivo: Path
    file_sha256: str
    filas: tuple[Mapping[str, Any], ...]
    plan: ImportPlan
    completitud: ResumenDeCompletitud

    @property
    def aplicable(self) -> bool:
        return self.plan.aplicable

    @property
    def altas(self):
        return self.plan.altas

    @property
    def actualizaciones(self):
        return self.plan.actualizaciones

    @property
    def rechazos(self):
        return self.plan.rechazos

    @property
    def resumen(self) -> str:
        return self.plan.resumen


def _ahora() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_comercial_controller(database_path: str | Path | None = None):
    """Composition root de la pantalla comercial.

    Arma el mismo repositorio de Caja que usa la aplicación, pero con el
    enganche del ledger conectado: es lo que hace que una venta descuente.
    """
    from modulos.caja_diaria.config import resolve_data_paths
    from modulos.caja_diaria.infrastructure.sqlite_repository import (
        SQLiteCashDayRepository,
    )

    ruta = (Path(database_path) if database_path is not None
            else resolve_data_paths().ensure().database)

    catalogo = SQLiteCatalogRepository(ruta)
    ledger_repo = SQLiteStockLedgerRepository(ruta)
    compras_repo = SQLitePurchaseRepository(ruta)
    integrador = VentasLedgerIntegrator(catalogo, ledger_repo)
    caja = SQLiteCashDayRepository(ruta, sale_integrator=integrador)
    return ComercialController(
        ruta=ruta, catalogo=catalogo, ledger_repo=ledger_repo,
        compras_repo=compras_repo, caja=caja, integrador=integrador)


class ComercialController:
    def __init__(self, *, ruta, catalogo, ledger_repo, compras_repo, caja,
                 integrador) -> None:
        self.ruta = Path(ruta)
        self._catalogo = catalogo
        self._ledger_repo = ledger_repo
        self._caja = caja
        self._integrador = integrador
        self.ledger = StockLedgerService(ledger_repo, catalogo)
        self.compras = ComprasService(compras_repo, catalogo, ledger_repo)

    def close(self) -> None:
        for recurso in (self._catalogo, self._ledger_repo, self.compras, self._caja):
            cerrar = getattr(recurso, "close", None)
            if cerrar is not None:
                cerrar()
        self.compras._repositorio.close()

    def repositorio_de_caja(self):
        """El repositorio de Caja con el enganche puesto, para el circuito."""
        return self._caja

    # -- utilidades de configuración ---------------------------------------

    def vincular_caja_a_sucursal(self, caja: str, sucursal: str, *, actor: str) -> None:
        """Reusa el vínculo canónico de las migraciones 018 y 020."""
        self._caja.bind_register_to_branch(caja, sucursal, assigned_by=actor)

    # -- artículos ----------------------------------------------------------

    def guardar_articulo(
        self,
        *,
        sku: str,
        name: str,
        nature: ArticleNature | str,
        actor: str,
        category_id: str | None = None,
        brand_id: str | None = None,
        supplier_id: str | None = None,
        unit: str = "UNIDAD",
        sale_price: int | None = None,
        location: str = "",
        min_stock: int | None = None,
        barcode: str | None = None,
        notes: str = "",
        active: bool = True,
        article_id: str | None = None,
    ) -> Article:
        """Alta o edición administrativa. Siempre queda registrada."""
        anterior = self.obtener_articulo(article_id) if article_id else None
        articulo = Article(
            sku=sku, name=name, nature=nature, category_id=category_id,
            brand_id=brand_id, supplier_id=supplier_id, unit=unit,
            sale_price=sale_price, location=location, min_stock=min_stock,
            barcode=barcode, notes=notes, active=active,
            **({"id": article_id} if article_id else {}))
        guardado = self._catalogo.save_article(articulo)
        self._auditar(
            actor=actor, accion="ALTA_ARTICULO" if anterior is None else "EDITA_ARTICULO",
            target_type="ARTICLE", target_id=guardado.id,
            detalle={"sku": guardado.sku, "name": guardado.name,
                     "nature": guardado.nature.value,
                     "sale_price": guardado.sale_price,
                     "location": guardado.location,
                     "active": guardado.active})
        return guardado

    def obtener_articulo(self, article_id: str) -> Article | None:
        return self._catalogo.get_article(article_id)

    def articulo_por_sku(self, sku: str) -> Article | None:
        return self._catalogo.get_article_by_sku(sku)

    def buscar_articulos(
        self,
        texto: str = "",
        *,
        naturaleza: ArticleNature | str | None = None,
        solo_activos: bool = True,
    ) -> tuple[Article, ...]:
        buscado = (texto or "").strip().lower()
        articulos = self._catalogo.list_articles(only_active=solo_activos)
        if naturaleza is not None:
            objetivo = ArticleNature(naturaleza)
            articulos = [a for a in articulos if a.nature is objetivo]
        if buscado:
            articulos = [
                a for a in articulos
                if buscado in a.name.lower() or buscado in a.sku.lower()
                or (a.barcode or "").lower() == buscado]
        return tuple(sorted(articulos, key=lambda a: a.name.lower()))

    def desactivar_articulo(self, article_id: str, *, actor: str, motivo: str) -> Article:
        """Baja lógica. Nunca borra: hay movimientos que lo explican."""
        articulo = self.obtener_articulo(article_id)
        if articulo is None:
            raise ComercialError(f"no existe el artículo {article_id}")
        if articulo.tracks_stock:
            for destino in Destination:
                if self.ledger.stock(article_id, destino) != 0:
                    raise ArticuloEnUso(
                        f"«{articulo.name}» todavía tiene "
                        f"{self.ledger.stock(article_id, destino)} en "
                        f"{destino.value}. Desactivarlo lo sacaría de las búsquedas "
                        "y ese stock quedaría sin nadie que lo mire")
        from dataclasses import replace
        return self.guardar_articulo(
            sku=articulo.sku, name=articulo.name, nature=articulo.nature,
            category_id=articulo.category_id, brand_id=articulo.brand_id,
            supplier_id=articulo.supplier_id, unit=articulo.unit,
            sale_price=articulo.sale_price, location=articulo.location,
            min_stock=articulo.min_stock, barcode=articulo.barcode,
            notes=(f"{articulo.notes}\n[baja] {motivo}".strip()),
            active=False, article_id=articulo.id, actor=actor)

    def historial_de_articulo(self, article_id: str) -> tuple[CambioDeArticulo, ...]:
        with self._conexion() as conexion:
            filas = conexion.execute(
                "SELECT actor, action, details_json, recorded_at FROM admin_audit_log"
                " WHERE target_type='ARTICLE' AND target_id = ?"
                " ORDER BY recorded_at, rowid", (article_id,)).fetchall()
        return tuple(
            CambioDeArticulo(actor=f["actor"], accion=f["action"],
                             detalle=f["details_json"], momento=f["recorded_at"])
            for f in filas)

    def costo_de_referencia(self, article_id: str) -> CostoDeReferencia:
        fila = self._catalogo.ultimo_costo_conocido(article_id)
        if fila is None:
            return CostoDeReferencia(valor=None,
                                     estado=CostStatus.PENDIENTE_DE_CONCILIACION.value)
        return CostoDeReferencia(
            valor=int(fila["unit_cost"]), estado=CostStatus.CONOCIDO.value,
            document_number=fila["document_number"],
            document_date=fila["document_date"],
            supplier_name=fila["supplier_name"])

    # -- categorías y marcas ------------------------------------------------

    def crear_categoria(self, nombre: str, *, actor: str) -> Category:
        """Inline, sin salir del alta del artículo.

        Si ya existe con otra combinación de mayúsculas devuelve la que estaba:
        escribirla de nuevo no puede crear un duplicado.
        """
        existente = self._buscar_por_nombre(self._catalogo.list_categories(only_active=False), nombre)
        if existente is not None:
            return existente
        categoria = self._catalogo.save_category(Category(name=nombre))
        self._auditar(actor=actor, accion="ALTA_CATEGORIA", target_type="CATEGORY",
                      target_id=categoria.id, detalle={"name": categoria.name})
        return categoria

    def crear_marca(self, nombre: str, *, actor: str) -> Brand:
        existente = self._buscar_por_nombre(self._catalogo.list_brands(only_active=False), nombre)
        if existente is not None:
            return existente
        marca = self._catalogo.save_brand(Brand(name=nombre))
        self._auditar(actor=actor, accion="ALTA_MARCA", target_type="BRAND",
                      target_id=marca.id, detalle={"name": marca.name})
        return marca

    def listar_categorias(self, *, solo_activas: bool = True) -> Sequence[Category]:
        return self._catalogo.list_categories(only_active=solo_activas)

    def listar_marcas(self, *, solo_activas: bool = True) -> Sequence[Brand]:
        return self._catalogo.list_brands(only_active=solo_activas)

    @staticmethod
    def _buscar_por_nombre(coleccion, nombre: str):
        buscado = (nombre or "").strip().lower()
        for elemento in coleccion:
            if elemento.name.lower() == buscado:
                return elemento
        return None

    # -- proveedores --------------------------------------------------------

    def guardar_proveedor(
        self, *, name: str, actor: str, document: str = "", phone: str = "",
        address: str = "", email: str = "", contact_name: str = "",
        kind: str = "PROVEEDOR", laboratory_id: str | None = None,
        active: bool = True, supplier_id: str | None = None,
    ) -> Supplier:
        proveedor = Supplier(
            name=name, kind=kind, document=document, phone=phone, address=address,
            email=email, contact_name=contact_name, laboratory_id=laboratory_id,
            active=active, **({"id": supplier_id} if supplier_id else {}))
        guardado = self.compras.guardar_proveedor(proveedor)
        self._auditar(actor=actor,
                      accion="ALTA_PROVEEDOR" if supplier_id is None else "EDITA_PROVEEDOR",
                      target_type="SUPPLIER", target_id=guardado.id,
                      detalle={"name": guardado.name, "document": guardado.document,
                               "active": guardado.active})
        return guardado

    def obtener_proveedor(self, supplier_id: str) -> Supplier | None:
        return self.compras.obtener_proveedor(supplier_id)

    def buscar_proveedores(self, texto: str = "", *,
                           solo_activos: bool = True) -> tuple[Supplier, ...]:
        buscado = (texto or "").strip().lower()
        proveedores = self.compras.listar_proveedores(only_active=solo_activos)
        if buscado:
            proveedores = [p for p in proveedores
                           if buscado in p.name.lower() or buscado in p.document.lower()]
        return tuple(sorted(proveedores, key=lambda p: p.name.lower()))

    def desactivar_proveedor(self, supplier_id: str, *, actor: str,
                             motivo: str) -> Supplier:
        proveedor = self.obtener_proveedor(supplier_id)
        if proveedor is None:
            raise ComercialError(f"no existe el proveedor {supplier_id}")
        return self.guardar_proveedor(
            name=proveedor.name, document=proveedor.document, phone=proveedor.phone,
            address=proveedor.address, email=proveedor.email,
            contact_name=proveedor.contact_name, kind=proveedor.kind,
            laboratory_id=proveedor.laboratory_id, active=False,
            supplier_id=proveedor.id, actor=actor)

    # -- compras ------------------------------------------------------------

    def linea_necesita_distribucion(self, article_id: str) -> bool:
        """Si la pantalla tiene que pedir el reparto físico de esta línea.

        Mostrarle el reparto a un cristal invitaría a llenarlo, y repartir algo
        que no genera unidades no significa nada.
        """
        articulo = self.obtener_articulo(article_id)
        return bool(articulo and articulo.tracks_stock)

    def crear_compra_borrador(
        self, *, supplier_id: str, document_date: date, document_number: str,
        condition: PurchaseCondition | str, lineas: Sequence[Mapping[str, Any]],
        actor: str, stamped_number: str = "", receipt_reference: str = "",
        credit_days: int | None = None, document_total: int | None = None,
        notes: str = "",
    ) -> Purchase:
        construidas = []
        for numero, cruda in enumerate(lineas, start=1):
            distribucion = cruda.get("distribucion") or {}
            construidas.append(PurchaseLine(
                article_id=cruda["article_id"],
                line_number=cruda.get("line_number", numero),
                quantity=cruda["quantity"],
                unit_cost=cruda["unit_cost"],
                description=cruda.get("description", ""),
                notes=cruda.get("notes", ""),
                distributions=tuple(
                    Distribution(destination=destino, quantity=cantidad)
                    for destino, cantidad in distribucion.items())))

        total = (document_total if document_total is not None
                 else sum(l.line_total for l in construidas))
        compra = Purchase(
            supplier_id=supplier_id, document_date=document_date,
            document_number=document_number, condition=condition,
            document_total=total, created_by=actor, lines=tuple(construidas),
            stamped_number=stamped_number, receipt_reference=receipt_reference,
            credit_days=credit_days, notes=notes)
        return self.compras.guardar_borrador(compra)

    def obtener_compra(self, purchase_id: str) -> Purchase | None:
        return self.compras.obtener(purchase_id)

    def listar_compras(self, *, supplier_id: str | None = None) -> Sequence[Purchase]:
        return self.compras.listar(supplier_id=supplier_id)

    def revisar_compra(self, purchase_id: str) -> RevisionDeCompra:
        """Lo que hay que mirar antes de confirmar, en un solo lugar.

        La pantalla no repite estas reglas: pregunta. Si las repitiera, el día
        que el dominio cambie una, la pantalla seguiría diciendo la vieja.
        """
        compra = self.obtener_compra(purchase_id)
        if compra is None:
            raise ComercialError(f"no existe la compra {purchase_id}")

        problemas: list[str] = []
        if compra.document_total != compra.lines_total:
            problemas.append(
                f"El total de la factura ({compra.document_total:,}) no coincide con "
                f"la suma de las líneas ({compra.lines_total:,}).")
        if not compra.lines:
            problemas.append("La factura no tiene ninguna línea.")
        for linea in compra.lines:
            articulo = self.obtener_articulo(linea.article_id)
            if articulo is None:
                problemas.append(f"La línea {linea.line_number} apunta a un artículo "
                                 "que no está en el catálogo.")
                continue
            if not articulo.tracks_stock:
                continue
            if linea.distributed_quantity != linea.quantity:
                problemas.append(
                    f"La línea {linea.line_number} ({articulo.name}) compró "
                    f"{linea.quantity} y reparte {linea.distributed_quantity} "
                    "entre las sucursales.")
        if compra.confirmada:
            problemas.append("Esta factura ya fue confirmada.")

        return RevisionDeCompra(
            total_documento=compra.document_total,
            total_lineas=compra.lines_total,
            confirmable=not problemas,
            problemas=tuple(problemas))

    def confirmar_compra(self, purchase_id: str, *, actor: str):
        """Confirma llamando al dominio del slice 3. No lo reimplementa."""
        resultado = self.compras.confirmar(purchase_id, actor=actor)
        self._auditar(actor=actor, accion="CONFIRMA_COMPRA", target_type="PURCHASE",
                      target_id=purchase_id,
                      detalle={"movimientos": len(resultado.movimientos)})
        return resultado

    # -- venta --------------------------------------------------------------

    def buscar_para_venta(
        self, texto: str = "", *, unidad: str, incluir_inactivos: bool = False,
    ) -> tuple[OpcionDeVenta, ...]:
        """Lo que el buscador de la línea de venta muestra.

        Un artículo sin stock aparece igual, marcado: esconderlo haría pensar
        que no existe, y la operadora terminaría creándolo de nuevo.
        """
        destino = self._integrador._destino_opcional(unidad)
        categorias = {c.id: c.name for c in self._catalogo.list_categories(only_active=False)}
        marcas = {m.id: m.name for m in self._catalogo.list_brands(only_active=False)}

        opciones = []
        for articulo in self.buscar_articulos(texto, solo_activos=not incluir_inactivos):
            if not articulo.tracks_stock:
                stock, estado = None, "NO_LLEVA_STOCK"
            elif destino is None:
                stock, estado = None, "SUCURSAL_DESCONOCIDA"
            else:
                stock = self.ledger.stock(articulo.id, destino)
                estado = "DISPONIBLE" if stock > 0 else "SIN_STOCK"
            if not articulo.active:
                estado = "INACTIVO"
            opciones.append(OpcionDeVenta(
                article_id=articulo.id, sku=articulo.sku, name=articulo.name,
                category=categorias.get(articulo.category_id, ""),
                brand=marcas.get(articulo.brand_id, ""),
                sale_price=articulo.sale_price, location=articulo.location,
                mueve_stock=articulo.tracks_stock, stock=stock, estado=estado,
                active=articulo.active))
        return tuple(opciones)

    # -- stock --------------------------------------------------------------

    def stock(self, article_id: str, destino: Destination | str) -> int:
        return self.ledger.stock(article_id, destino)

    def stock_por_destino(self, article_id: str) -> dict:
        return self.ledger.stock_por_destino(article_id)

    def movimientos_de_articulo(self, article_id: str) -> list[StockMovement]:
        return self.ledger.movimientos(article_id=article_id)

    def origen_de_movimiento(self, movement_id: str) -> dict | None:
        """De dónde salió una unidad, sea de una compra, una venta o un recuento."""
        with self._conexion() as conexion:
            for vista in ("stock_origen_compra", "stock_origen_venta"):
                fila = conexion.execute(
                    f"SELECT * FROM {vista} WHERE movement_id = ?",
                    (movement_id,)).fetchone()
                if fila is not None:
                    return dict(fila)
        return None

    def compensar_movimiento(self, movement_id: str, *, actor: str, motivo: str,
                             observacion: str) -> StockMovement:
        """Corregir un recuento mal hecho sin borrar el que se hizo."""
        return self.ledger.compensar(movement_id, reason_code=motivo,
                                     note=observacion, actor=actor)

    # -- carga inicial ------------------------------------------------------

    def planificar_carga_de_articulos(self, archivo: str | Path) -> PlanDeCargaInicial:
        """Calcula qué pasaría. No escribe."""
        ruta = Path(archivo)
        filas = leer_archivo_de_articulos(ruta)
        existentes = {a.sku: a.id for a in self._catalogo.list_articles(only_active=False)}
        plan = planificar_importacion(filas, existentes_por_sku=existentes)
        return PlanDeCargaInicial(
            archivo=ruta, file_sha256=sha256_de(ruta), filas=tuple(filas),
            plan=plan, completitud=resumir_completitud(filas))

    def aplicar_carga_de_articulos(
        self, plan: PlanDeCargaInicial, *, actor: str, unidad: str = "CATALOGO",
    ) -> CorridaDeCarga:
        """Escribe el catálogo, y **sólo** el catálogo.

        No crea una sola unidad de stock. Que un artículo exista no significa
        que haya alguno en el depósito, y confundir las dos cosas daría un
        inventario que nadie contó.
        """
        if not plan.aplicable:
            raise CargaInicialError(
                f"el archivo tiene {len(plan.rechazos)} filas rechazadas. Un plan con "
                "rechazos no se aplica a medias: cargar parte dejaría un catálogo que "
                "nadie sabe describir. Corregí el archivo y volvé a planificar")

        if self._corrida_existente(plan.file_sha256, unidad):
            raise CargaInicialError(
                f"este archivo ya se cargó ({plan.archivo.name}). Volver a aplicarlo "
                "duplicaría lo que ya está")

        # Categorías y marcas nombradas en el archivo, creadas una sola vez.
        categorias: dict[str, str] = {}
        marcas: dict[str, str] = {}
        for fila in plan.filas:
            nombre = (fila.get("category") or "").strip()
            if nombre and nombre.lower() not in categorias:
                categorias[nombre.lower()] = self.crear_categoria(nombre, actor=actor).id
            nombre = (fila.get("brand") or "").strip()
            if nombre and nombre.lower() not in marcas:
                marcas[nombre.lower()] = self.crear_marca(nombre, actor=actor).id

        por_sku = {f["sku"].strip().upper(): f for f in plan.filas}
        escritos = 0
        for articulo in list(plan.altas) + list(plan.actualizaciones):
            fila = por_sku.get(articulo.sku, {})
            self._catalogo.save_article(Article(
                sku=articulo.sku, name=articulo.name, nature=articulo.nature,
                category_id=categorias.get((fila.get("category") or "").strip().lower()),
                brand_id=marcas.get((fila.get("brand") or "").strip().lower()),
                unit=fila.get("unit") or "UNIDAD",
                sale_price=fila.get("sale_price"),
                location=fila.get("location") or "",
                min_stock=fila.get("min_stock"),
                barcode=(fila.get("barcode") or "") or None,
                notes=fila.get("notes") or "",
                id=articulo.id))
            escritos += 1

        return self._registrar_corrida(
            file_name=plan.archivo.name, file_sha256=plan.file_sha256, unidad=unidad,
            rows_processed=len(plan.filas), rows_imported=escritos,
            rows_skipped=0, error_count=0, result="APLICADA", actor=actor)

    def cargar_stock_inicial(
        self,
        recuento: Sequence[tuple[str, Destination | str, int]],
        *,
        actor: str,
        origen: str,
        run_id: str | None = None,
        momento: datetime | None = None,
    ) -> CorridaDeCarga:
        """El inventario físico que hoy hay en el local, como hecho auditado.

        Entra por `INGRESO_ADMINISTRATIVO` con motivo `INVENTARIO_INICIAL`, que
        es lo que realmente pasó: alguien contó. **No** se falsea una compra
        para generarlo — daría un stock correcto colgando de un proveedor que
        nunca facturó eso, y esa mentira no se deshace sin borrar historia.

        Si el recuento estuvo mal, se compensa. Nunca se borra.
        """
        explicacion = (origen or "").strip()
        if not explicacion:
            raise CargaInicialError(
                "un ingreso de inventario inicial tiene que decir de dónde salió: "
                "qué recuento, de qué día y de qué local")

        corrida = (run_id or "").strip() or str(uuid4())
        existente = self._corrida_por_id(corrida)
        if existente is not None:
            return existente

        cuando = momento or datetime.now(timezone.utc).replace(microsecond=0)
        cargados = 0
        for article_id, destino, cantidad in recuento:
            if cantidad <= 0:
                continue
            self.ledger.registrar(StockMovement(
                article_id=article_id,
                destination=Destination(destino),
                kind=StockMovementKind.INGRESO_ADMINISTRATIVO,
                quantity=int(cantidad),
                actor=actor,
                occurred_at=cuando,
                reason_code=MOTIVO_INVENTARIO_INICIAL,
                note=explicacion,
                document_kind=DOCUMENTO_CARGA_INICIAL,
                document_id=corrida,
                idempotency_key=(f"{DOCUMENTO_CARGA_INICIAL}:{corrida}:"
                                 f"{article_id}:{Destination(destino).value}")))
            cargados += 1

        return self._registrar_corrida(
            corrida_id=corrida, file_name=explicacion[:120],
            file_sha256=f"recuento:{corrida}", unidad="INVENTARIO_INICIAL",
            rows_processed=len(recuento), rows_imported=cargados, rows_skipped=0,
            error_count=0, result="APLICADA", actor=actor)

    # -- internos -----------------------------------------------------------

    def _conexion(self):
        from contextlib import closing
        conexion = sqlite3.connect(str(self.ruta))
        conexion.row_factory = sqlite3.Row
        return closing(conexion)

    def _auditar(self, *, actor: str, accion: str, target_type: str, target_id: str,
                 detalle: Mapping[str, Any]) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                "INSERT INTO admin_audit_log(id, actor, action, target_type,"
                " target_id, result, details_json, recorded_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (str(uuid4()), actor, accion, target_type, target_id, "OK",
                 json.dumps(dict(detalle), ensure_ascii=False, sort_keys=True),
                 _ahora()))
            conexion.commit()

    def _corrida_existente(self, file_sha256: str, unidad: str) -> bool:
        with self._conexion() as conexion:
            return conexion.execute(
                "SELECT 1 FROM import_runs WHERE file_sha256 = ? AND unit = ?",
                (file_sha256, unidad)).fetchone() is not None

    def _corrida_por_id(self, corrida_id: str) -> CorridaDeCarga | None:
        with self._conexion() as conexion:
            fila = conexion.execute(
                "SELECT * FROM import_runs WHERE id = ?", (corrida_id,)).fetchone()
        return self._a_corrida(fila) if fila else None

    def _registrar_corrida(
        self, *, file_name: str, file_sha256: str, unidad: str, rows_processed: int,
        rows_imported: int, rows_skipped: int, error_count: int, result: str,
        actor: str, corrida_id: str | None = None,
    ) -> CorridaDeCarga:
        identificador = corrida_id or str(uuid4())
        momento = _ahora()
        with self._conexion() as conexion:
            conexion.execute(
                "INSERT INTO import_runs(id, administrator, file_name, file_sha256,"
                " unit, rows_processed, rows_imported, rows_skipped, error_count,"
                " result, recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (identificador, actor, file_name, file_sha256, unidad, rows_processed,
                 rows_imported, rows_skipped, error_count, result, momento))
            conexion.commit()
        return CorridaDeCarga(
            id=identificador, file_name=file_name, file_sha256=file_sha256,
            unit=unidad, rows_processed=rows_processed, rows_imported=rows_imported,
            rows_skipped=rows_skipped, error_count=error_count, result=result,
            administrator=actor, recorded_at=momento)

    @staticmethod
    def _a_corrida(fila: sqlite3.Row) -> CorridaDeCarga:
        return CorridaDeCarga(
            id=fila["id"], file_name=fila["file_name"],
            file_sha256=fila["file_sha256"], unit=fila["unit"],
            rows_processed=fila["rows_processed"], rows_imported=fila["rows_imported"],
            rows_skipped=fila["rows_skipped"], error_count=fila["error_count"],
            result=fila["result"], administrator=fila["administrator"],
            recorded_at=fila["recorded_at"])
