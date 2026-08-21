# -*- coding: utf-8 -*-
"""Arma una base de prueba con la forma del catálogo de la Óptica.

No es producción y no puede serlo: la base de la Óptica vive sólo en la PC de la
Óptica. Esto reconstruye el catálogo desde `catalogo_canonico.csv` —el mismo
archivo que se importó allá en V1-008— y le pone los laboratorios por defecto
que asignó V1-012. Alcanza para correr el plan sobre los 31 casos reales y ver
qué haría, sin afirmar nada sobre la base real.

Lo que esta copia NO tiene: movimientos, ventas, caja, ni las 767 bajas de
V1-010/V1-013. Por eso el dry-run que sale de acá dice qué se cambiaría en el
catálogo, y nada sobre stock — que es justamente lo que la misión no toca.

    python artifacts/.../base_de_prueba.py <destino.sqlite3>
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from modulos.caja_diaria.infrastructure.sqlite_repository import (  # noqa: E402
    SQLiteCashDayRepository,
)
from modulos.comercial.application.comercial_controller import (  # noqa: E402
    build_comercial_controller,
)

CATALOGO = (RAIZ / "artifacts" / "BC-OPTICA-CARGA-INICIAL-CATALOGO-V1-008"
            / "catalogo_canonico.csv")

ACTOR = "BASE_DE_PRUEBA/V1-015"

#: Los 24 cristales que V1-012 dejó con laboratorio por defecto en producción.
#: Copiados uno por uno de su APLICACION_PRODUCTIVA.txt —16 Optilab, 7
#: ServiOptica, 1 Laboratorio Cristal—, no reconstruidos por criterio. Sin esto
#: la copia no serviría para comprobar que limpiar la marca deja quieto el
#: laboratorio.
DEFAULTS = {
    "Laboratorio Optilab": [
        "2000060", "2000061", "2000062", "2000063", "2000064", "2000066",
        "2000067", "2000073", "2000074", "2000086", "2000206", "2000207",
        "2000213", "2000215", "2000217", "2000218"],
    "ServiOptica": [
        "2000075", "2000076", "2000125", "2000208", "2000209", "2000214",
        "2000216"],
    "Laboratorio Cristal": ["2000126"],
}


def main() -> int:
    destino = Path(sys.argv[1])
    if destino.exists():
        destino.unlink()
    destino.parent.mkdir(parents=True, exist_ok=True)
    SQLiteCashDayRepository(destino).close()

    ctrl = build_comercial_controller(destino)
    try:
        categorias: dict[str, str] = {}
        marcas: dict[str, str] = {}
        laboratorios = {n: ctrl.laboratorio_por_nombre(n).id for n in DEFAULTS}
        por_sku = {}
        with CATALOGO.open(encoding="utf-8-sig", newline="") as f:
            for fila in csv.DictReader(f):
                cat = fila["category"].strip()
                marca = fila["brand"].strip()
                if cat and cat not in categorias:
                    categorias[cat] = ctrl.crear_categoria(cat, actor=ACTOR).id
                if marca and marca not in marcas:
                    marcas[marca] = ctrl.crear_marca(marca, actor=ACTOR).id
                articulo = ctrl.guardar_articulo(
                    sku=fila["sku"], name=fila["name"], nature=fila["nature"],
                    actor=ACTOR,
                    category_id=categorias.get(cat), brand_id=marcas.get(marca),
                    unit=fila["unit"] or "UNIDAD",
                    sale_price=int(fila["sale_price"]) if fila["sale_price"] else None,
                    location=fila["location"], barcode=fila["barcode"] or None,
                    min_stock=int(fila["min_stock"]) if fila["min_stock"] else None,
                    notes=fila["notes"])
                por_sku[fila["sku"]] = articulo.id
        puestos = 0
        for laboratorio, skus in DEFAULTS.items():
            for sku in skus:
                if sku in por_sku:
                    ctrl.asignar_laboratorio_por_defecto(
                        por_sku[sku], laboratorios[laboratorio], actor=ACTOR)
                    puestos += 1
    finally:
        ctrl.close()
    print(f"base de prueba: {destino}")
    print(f"  articulos   : {len(por_sku)}")
    print(f"  categorias  : {len(categorias)}")
    print(f"  marcas      : {len(marcas)}")
    print(f"  defaults    : {puestos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
