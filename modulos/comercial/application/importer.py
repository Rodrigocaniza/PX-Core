"""Importador de artículos: contrato y plan, no carga masiva.

El pedido fue explícito: primero el mecanismo, y la base real de artículos sólo
si puede cargarse de forma segura, reversible y verificada. Este módulo hace la
mitad segura — calcular qué pasaría — y no escribe nada.

`planificar_importacion()` recibe filas crudas y devuelve un plan: qué se daría
de alta, qué se actualizaría y qué se rechaza, con el motivo de cada rechazo. Un
plan con rechazos no es aplicable. Recién con un plan limpio, y con una decisión
explícita de aplicarlo, se escribe en la base.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..domain.models import Article, ArticleNature


@dataclass(frozen=True)
class ImportRejection:
    fila: int
    sku: str
    motivo: str


@dataclass(frozen=True)
class ImportPlan:
    altas: list[Article] = field(default_factory=list)
    actualizaciones: list[Article] = field(default_factory=list)
    rechazos: list[ImportRejection] = field(default_factory=list)

    @property
    def aplicable(self) -> bool:
        """Un plan con rechazos no se aplica a medias.

        Importar 900 de 1000 filas y dejar 100 afuera deja el catálogo en un
        estado que nadie sabe describir. O entra el archivo entero, o se corrige
        el archivo.
        """
        return not self.rechazos

    @property
    def resumen(self) -> str:
        return (f"{len(self.altas)} altas, {len(self.actualizaciones)} actualizaciones, "
                f"{len(self.rechazos)} rechazadas")


def _sku_normalizado(valor: Any) -> str:
    return str(valor or "").strip().upper()


def planificar_importacion(
    filas: Sequence[Mapping[str, Any]],
    *,
    existentes_por_sku: Mapping[str, str] | None = None,
) -> ImportPlan:
    """Calcula el plan sin tocar la base.

    `existentes_por_sku` mapea SKU -> id de artículo ya existente; se pasa desde
    afuera para que esta función siga siendo pura y testeable sin repositorio.
    """
    existentes = {
        _sku_normalizado(sku): article_id
        for sku, article_id in (existentes_por_sku or {}).items()
    }

    altas: list[Article] = []
    actualizaciones: list[Article] = []
    rechazos: list[ImportRejection] = []
    vistos: set[str] = set()

    for numero, fila in enumerate(filas, start=1):
        sku = _sku_normalizado(fila.get("sku"))
        if not sku:
            rechazos.append(ImportRejection(numero, "", "falta el SKU"))
            continue
        if sku in vistos:
            rechazos.append(ImportRejection(
                numero, sku, "SKU repetido dentro del mismo archivo"))
            continue

        naturaleza = str(fila.get("nature") or "").strip().upper()
        if naturaleza not in {n.value for n in ArticleNature}:
            rechazos.append(ImportRejection(
                numero, sku, f"naturaleza inválida: {fila.get('nature')!r}"))
            continue

        try:
            articulo = Article(
                sku=sku,
                name=fila.get("name", ""),
                nature=naturaleza,
                category_id=fila.get("category_id") or None,
                brand_id=fila.get("brand_id") or None,
                supplier_id=fila.get("supplier_id") or None,
                unit=fila.get("unit") or "UNIDAD",
                sale_price=fila.get("sale_price"),
                notes=fila.get("notes") or "",
                id=existentes.get(sku) or Article.__dataclass_fields__["id"].default_factory(),
            )
        except ValueError as exc:
            rechazos.append(ImportRejection(numero, sku, str(exc)))
            continue

        vistos.add(sku)
        if sku in existentes:
            actualizaciones.append(articulo)
        else:
            altas.append(articulo)

    return ImportPlan(altas=altas, actualizaciones=actualizaciones, rechazos=rechazos)
