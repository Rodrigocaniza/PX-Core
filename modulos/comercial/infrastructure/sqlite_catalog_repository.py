"""Repositorio SQLite de los catálogos comerciales.

Vive en la misma base que Caja y depende de la cadena de migraciones de Caja:
la 022 es la que crea estas tablas. Deliberadamente no aplica migraciones por su
cuenta — hay una sola cadena y un solo dueño, `SQLiteCashDayRepository`.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence
from uuid import uuid4

from ..domain.models import (
    AdministrativeEntryReasonRow,
    AdministrativeExitReasonRow,
    Article,
    ArticleNature,
    Brand,
    Category,
    Supplier,
)


def _ahora() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SQLiteCatalogRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._memory_connection: sqlite3.Connection | None = None
        if str(database_path) == ":memory:":
            self._memory_connection = self._new_connection()

    def _new_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._memory_connection or self._new_connection()
        try:
            yield connection
        finally:
            if self._memory_connection is None:
                connection.close()

    def close(self) -> None:
        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None

    # -- utilidades de inspección, usadas por las pruebas de contrato --------

    def nombres_de_tablas(self) -> set[str]:
        with self._connection() as connection:
            return {
                fila[0] for fila in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")
            }

    def branch_of_register(self, cash_register: str) -> str | None:
        """La sucursal de una caja, según el vínculo administrativo que ya existe.

        `cash_register_branches` es canónica desde la 018 y la 020. Esto la
        LEE; no la duplica ni la reinterpreta. Devuelve `None` cuando la caja
        no está vinculada, que no es lo mismo que estar en Asunción: es no
        saberlo, y quien pregunte tiene que decidir qué hacer con eso.
        """
        with self._connection() as connection:
            fila = connection.execute(
                "SELECT branch FROM cash_register_branches WHERE cash_register = ?",
                (str(cash_register or "").strip(),)).fetchone()
        return fila["branch"] if fila else None

    def asegurar_laboratorio(self, nombre: str) -> str:
        """Devuelve el id del laboratorio, creándolo si todavía no está.

        `laboratories` es el catálogo canónico desde la 016; los proveedores lo
        referencian en vez de duplicarlo.
        """
        with self._connection() as connection:
            fila = connection.execute(
                "SELECT id FROM laboratories WHERE name = ? COLLATE NOCASE",
                (nombre,)).fetchone()
            if fila:
                return fila["id"]
            nuevo = str(uuid4())
            ahora = _ahora()
            connection.execute(
                "INSERT INTO laboratories(id, name, phone_line, whatsapp, active,"
                " created_at, updated_at) VALUES(?,?,'','',1,?,?)",
                (nuevo, nombre, ahora, ahora))
            connection.commit()
            return nuevo

    # -- categorías ---------------------------------------------------------

    def save_category(self, category: Category) -> Category:
        self._guardar_catalogo_plano("article_categories", category.id,
                                     category.name, category.active)
        return category

    def get_category(self, category_id: str) -> Category | None:
        fila = self._fila("article_categories", category_id)
        return None if fila is None else Category(
            name=fila["name"], active=bool(fila["active"]), id=fila["id"])

    def list_categories(self, *, only_active: bool = True) -> Sequence[Category]:
        return [Category(name=f["name"], active=bool(f["active"]), id=f["id"])
                for f in self._filas("article_categories", only_active)]

    # -- marcas -------------------------------------------------------------

    def save_brand(self, brand: Brand) -> Brand:
        self._guardar_catalogo_plano("brands", brand.id, brand.name, brand.active)
        return brand

    def get_brand(self, brand_id: str) -> Brand | None:
        fila = self._fila("brands", brand_id)
        return None if fila is None else Brand(
            name=fila["name"], active=bool(fila["active"]), id=fila["id"])

    def list_brands(self, *, only_active: bool = True) -> Sequence[Brand]:
        return [Brand(name=f["name"], active=bool(f["active"]), id=f["id"])
                for f in self._filas("brands", only_active)]

    # -- proveedores --------------------------------------------------------

    def save_supplier(self, supplier: Supplier) -> Supplier:
        ahora = _ahora()
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO suppliers(id, name, kind, document, phone, address,"
                " email, contact_name, laboratory_id, active, created_at, updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(id) DO UPDATE SET name=excluded.name,"
                " kind=excluded.kind, document=excluded.document,"
                " phone=excluded.phone, address=excluded.address,"
                " email=excluded.email, contact_name=excluded.contact_name,"
                " laboratory_id=excluded.laboratory_id,"
                " active=excluded.active, updated_at=excluded.updated_at",
                (supplier.id, supplier.name, supplier.kind, supplier.document,
                 supplier.phone, supplier.address, supplier.email,
                 supplier.contact_name, supplier.laboratory_id,
                 int(supplier.active), ahora, ahora))
            connection.commit()
        return supplier

    def get_supplier(self, supplier_id: str) -> Supplier | None:
        fila = self._fila("suppliers", supplier_id)
        return None if fila is None else self._a_proveedor(fila)

    def list_suppliers(self, *, only_active: bool = True) -> Sequence[Supplier]:
        return [self._a_proveedor(f) for f in self._filas("suppliers", only_active)]

    @staticmethod
    def _a_proveedor(fila: sqlite3.Row) -> Supplier:
        return Supplier(
            name=fila["name"], kind=fila["kind"], document=fila["document"],
            phone=fila["phone"], address=fila["address"], email=fila["email"],
            contact_name=fila["contact_name"],
            laboratory_id=fila["laboratory_id"],
            active=bool(fila["active"]), id=fila["id"])

    # -- artículos ----------------------------------------------------------

    def save_article(self, article: Article) -> Article:
        ahora = _ahora()
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO articles(id, sku, name, nature, category_id, brand_id,"
                " supplier_id, unit, sale_price, location, min_stock, barcode, notes,"
                " default_laboratory_id, active, created_at, updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(id) DO UPDATE SET sku=excluded.sku, name=excluded.name,"
                " nature=excluded.nature, category_id=excluded.category_id,"
                " brand_id=excluded.brand_id, supplier_id=excluded.supplier_id,"
                " unit=excluded.unit, sale_price=excluded.sale_price,"
                " location=excluded.location, min_stock=excluded.min_stock,"
                " barcode=excluded.barcode,"
                " notes=excluded.notes,"
                " default_laboratory_id=excluded.default_laboratory_id,"
                " active=excluded.active, updated_at=excluded.updated_at",
                (article.id, article.sku, article.name, article.nature.value,
                 article.category_id, article.brand_id, article.supplier_id,
                 article.unit, article.sale_price, article.location,
                 article.min_stock, article.barcode, article.notes,
                 article.default_laboratory_id, int(article.active), ahora, ahora))
            connection.commit()
        return article

    def get_article(self, article_id: str) -> Article | None:
        fila = self._fila("articles", article_id)
        return None if fila is None else self._a_articulo(fila)

    def get_article_by_sku(self, sku: str) -> Article | None:
        with self._connection() as connection:
            fila = connection.execute(
                "SELECT * FROM articles WHERE sku = ? COLLATE NOCASE",
                (str(sku or "").strip(),)).fetchone()
        return None if fila is None else self._a_articulo(fila)

    def list_articles(self, *, only_active: bool = True) -> Sequence[Article]:
        return [self._a_articulo(f) for f in self._filas("articles", only_active)]

    @staticmethod
    def _a_articulo(fila: sqlite3.Row) -> Article:
        return Article(
            sku=fila["sku"], name=fila["name"], nature=ArticleNature(fila["nature"]),
            category_id=fila["category_id"], brand_id=fila["brand_id"],
            supplier_id=fila["supplier_id"], unit=fila["unit"],
            sale_price=fila["sale_price"], location=fila["location"],
            min_stock=fila["min_stock"], barcode=fila["barcode"],
            notes=fila["notes"],
            default_laboratory_id=fila["default_laboratory_id"],
            active=bool(fila["active"]), id=fila["id"])

    # -- motivos de salida administrativa -----------------------------------

    def list_administrative_exit_reasons(
        self, *, only_active: bool = True
    ) -> Sequence[AdministrativeExitReasonRow]:
        consulta = "SELECT * FROM administrative_exit_reasons"
        if only_active:
            consulta += " WHERE active = 1"
        consulta += " ORDER BY position"
        with self._connection() as connection:
            filas = connection.execute(consulta).fetchall()
        return [AdministrativeExitReasonRow(
            code=f["code"], label=f["label"],
            requires_note=bool(f["requires_note"]),
            position=f["position"], active=bool(f["active"])) for f in filas]

    def list_administrative_entry_reasons(
        self, *, only_active: bool = True
    ) -> Sequence[AdministrativeEntryReasonRow]:
        """El espejo del anterior, para lo que entra sin factura.

        Son dos catálogos y no uno solo con una bandera: «roto» no puede ser el
        motivo por el que algo entró, y «stock encontrado» no puede ser el
        motivo por el que algo salió. Una lista única obligaría a filtrarla en
        cada pantalla y tarde o temprano alguien elegiría el motivo del otro
        lado.
        """
        consulta = "SELECT * FROM administrative_entry_reasons"
        if only_active:
            consulta += " WHERE active = 1"
        consulta += " ORDER BY position"
        with self._connection() as connection:
            filas = connection.execute(consulta).fetchall()
        return [AdministrativeEntryReasonRow(
            code=f["code"], label=f["label"],
            requires_note=bool(f["requires_note"]),
            position=f["position"], active=bool(f["active"])) for f in filas]

    def ultimo_costo_conocido(self, article_id: str) -> sqlite3.Row | None:
        """La última compra confirmada de este artículo, si la hubo.

        El costo no es un dato del artículo: es lo que dijo la factura con que
        se compró. Guardarlo en el maestro sería una segunda verdad que puede
        contradecir al documento, y el documento es el que tiene un papel
        detrás.
        """
        with self._connection() as connection:
            return connection.execute(
                "SELECT l.unit_cost, p.document_number, p.document_date, s.name"
                " AS supplier_name"
                " FROM purchase_lines l"
                " JOIN purchases p ON p.id = l.purchase_id"
                " JOIN suppliers s ON s.id = p.supplier_id"
                " WHERE l.article_id = ? AND p.status = 'CONFIRMADA'"
                " ORDER BY p.document_date DESC, p.rowid DESC LIMIT 1",
                (article_id,)).fetchone()

    # -- helpers privados ---------------------------------------------------

    def _guardar_catalogo_plano(self, tabla: str, identificador: str,
                                nombre: str, activo: bool) -> None:
        ahora = _ahora()
        with self._connection() as connection:
            connection.execute(
                f"INSERT INTO {tabla}(id, name, active, created_at, updated_at)"
                " VALUES(?,?,?,?,?)"
                " ON CONFLICT(id) DO UPDATE SET name=excluded.name,"
                " active=excluded.active, updated_at=excluded.updated_at",
                (identificador, nombre, int(activo), ahora, ahora))
            connection.commit()

    def _fila(self, tabla: str, identificador: str) -> sqlite3.Row | None:
        with self._connection() as connection:
            return connection.execute(
                f"SELECT * FROM {tabla} WHERE id = ?", (identificador,)).fetchone()

    def _filas(self, tabla: str, only_active: bool) -> Sequence[sqlite3.Row]:
        consulta = f"SELECT * FROM {tabla}"
        if only_active:
            consulta += " WHERE active = 1"
        consulta += " ORDER BY name COLLATE NOCASE"
        with self._connection() as connection:
            return connection.execute(consulta).fetchall()
