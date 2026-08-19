"""Normaliza los dos inventarios reales de la Óptica a la plantilla del sistema.

Lee los XLSX tal como salen del sistema viejo y emite tres archivos que el
mecanismo de carga ya sabe consumir: el catálogo canónico en el formato de
`docs/PLANTILLA_ARTICULOS.csv`, y un recuento por sucursal.

**No escribe en ninguna base.** Lo que decide, y por qué, está documentado en
`artifacts/BC-OPTICA-CARGA-INICIAL-CATALOGO-V1-008/`.

    python tools/carga_inicial_optica_normalizar.py --pc <xlsx> --p2 <xlsx> --salida <dir>
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

#: Qué sucursal es cada archivo. No es una convención de este script: es el
#: vínculo que `cash_register_branches` ya trae sembrado desde las migraciones
#: 018 y 020, y que los pedidos reales corroboran (`orders.branch = 'PC'`).
FUENTES = {
    "PC": dict(hoja="PC", corte="2026-08-03", sucursal="ASUNCION",
               columnas=dict(articulo=3, marca=4, categoria=5, stock=2)),
    "P2": dict(hoja="Sheet1", corte="2026-08-10", sucursal="PILAR",
               columnas=dict(articulo=0, categoria=1, marca=2, stock=3)),
}

REQUIERE_DECISION = "REQUIRES_POLICY_DECISION"

#: La naturaleza sale de la categoría. **Nunca** de la descripción de la fila:
#: el día que alguien escriba «armazón de cristal», deducirla del texto pondría
#: a un cristal a descontar stock y nadie sabría por qué.
NATURE_POR_CATEGORIA = {
    "armazones": "PRODUCTO_STOCKEABLE",
    "lentes de sol": "PRODUCTO_STOCKEABLE",
    "lente de contacto": "PRODUCTO_STOCKEABLE",
    "sujetadores": "PRODUCTO_STOCKEABLE",
    "accesorios": "PRODUCTO_STOCKEABLE",
    "liquidos multiproposit": "PRODUCTO_STOCKEABLE",
    "estuches": "PRODUCTO_STOCKEABLE",
    "estuche lc": "PRODUCTO_STOCKEABLE",
    "limpia cristales": "PRODUCTO_STOCKEABLE",
    "marcadores": "PRODUCTO_STOCKEABLE",
    "medicamentos": "PRODUCTO_STOCKEABLE",
    "organizadores": "PRODUCTO_STOCKEABLE",
    "panos": "PRODUCTO_STOCKEABLE",
    # La «marca» de un cristal es el laboratorio que lo fabrica, y el stock
    # declarado (949, 984, 999, 1971) no es un conteo sino el número que pone un
    # sistema para que algo no se acabe nunca. Un cristal se pide con la receta.
    "cristales": "TRABAJO_BAJO_PEDIDO",
    # Mezcla servicios, tipos de cristal y repuestos físicos en una sola
    # categoría. Cualquier asignación única sería falsa.
    "compostura": REQUIERE_DECISION,
    # Seis filas de PC sin categoría. Parecen armazones por la descripción, que
    # es exactamente el motivo por el que no se les asigna nada.
    "": REQUIERE_DECISION,
}

MUEVEN_STOCK = {"PRODUCTO_STOCKEABLE", "PRODUCCION_INTERNA"}
PREFIJO_SUCURSAL = {"ASUNCION": "ASU", "PILAR": "PIL"}

#: El código va pegado o separado de la descripción: «000010 Limpia Cristal» y
#: «107648AC PAT FLEX NEGRO» son la misma forma escrita de dos maneras.
SKU_RE = re.compile(r"^\s*(\d{4,})\s*(.*)$")


def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def _clave_categoria(nombre: str) -> str:
    limpio = unicodedata.normalize("NFKD", (nombre or "").strip().lower())
    limpio = "".join(c for c in limpio if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", limpio)[:22]


def identificador_es_global(sku: str) -> bool:
    """¿El código nombra al mismo artículo en las dos sucursales?

    Se resolvió con los datos, no por preferencia. De los 42 códigos de barras
    compartidos, los 42 son el mismo producto. De los 31 del catálogo interno,
    29 tienen la descripción idéntica. Pero de los 107 códigos de armazón
    compartidos **uno solo** describe el mismo marco: cada sucursal numera sus
    armazones por su cuenta, y tratarlos como uno pegaría dos marcos distintos
    en un artículo para después sumarles stock a algo que no existe.
    """
    if 11 <= len(sku) <= 13:          # código de barras del fabricante
        return True
    if len(sku) == 6 and sku.startswith("00"):    # catálogo interno compartido
        return True
    if len(sku) == 7 and sku.startswith("2000"):  # ídem
        return True
    return False


def leer_hoja(ruta: Path, meta: dict) -> list[dict]:
    from openpyxl import load_workbook

    libro = load_workbook(ruta, read_only=True, data_only=True)
    try:
        hoja = libro[meta["hoja"]] if meta["hoja"] in libro.sheetnames else libro.active
        columnas = meta["columnas"]
        filas = []
        for numero, cruda in enumerate(hoja.iter_rows(values_only=True), start=1):
            if numero <= 2:  # fila 1: la fecha del corte. fila 2: el encabezado
                continue
            articulo = _texto(cruda[columnas["articulo"]])
            if not articulo:
                continue  # fila vacía de la exportación, no un artículo
            filas.append(dict(
                fila_fisica=numero, articulo=articulo,
                marca=_texto(cruda[columnas["marca"]]),
                categoria=_texto(cruda[columnas["categoria"]]),
                stock=_texto(cruda[columnas["stock"]])))
        return filas
    finally:
        libro.close()


def normalizar(archivos: dict[str, Path]) -> tuple[list[dict], list[dict]]:
    registros, rechazos = [], []
    for tag, ruta in archivos.items():
        meta = FUENTES[tag]
        for fila in leer_hoja(ruta, meta):
            encontrado = SKU_RE.match(fila["articulo"])
            if not encontrado:
                rechazos.append(dict(fuente=tag, fila=fila["fila_fisica"],
                                     articulo=fila["articulo"],
                                     motivo="sin código: no se puede derivar un SKU"))
                continue
            sku, nombre = encontrado.group(1), encontrado.group(2).strip()
            if not nombre:
                rechazos.append(dict(fuente=tag, fila=fila["fila_fisica"],
                                     articulo=fila["articulo"],
                                     motivo="código sin descripción: no hay nombre de artículo"))
                continue
            try:
                cantidad = int(fila["stock"])
            except ValueError:
                cantidad = None
            registros.append(dict(
                sku=sku, nombre=nombre, categoria=fila["categoria"], marca=fila["marca"],
                sucursal=meta["sucursal"], corte=meta["corte"],
                nature=NATURE_POR_CATEGORIA.get(_clave_categoria(fila["categoria"]),
                                                REQUIERE_DECISION),
                stock_inicial=cantidad, fuente_archivo=ruta.name,
                fuente_fila=fila["fila_fisica"], texto_original=fila["articulo"]))
    return registros, rechazos


def consolidar(registros: list[dict]) -> tuple[list[dict], dict, list[dict]]:
    """Un artículo por identidad canónica, y el recuento aparte.

    Catálogo y stock son dos cosas distintas: acá se separan y el sistema las
    escribe en dos pasos, porque que un artículo exista no significa que haya
    uno en el depósito.
    """
    por_canonico = defaultdict(list)
    for registro in registros:
        registro["sku_canonico"] = (
            registro["sku"] if identificador_es_global(registro["sku"])
            else f"{PREFIJO_SUCURSAL[registro['sucursal']]}-{registro['sku']}")
        por_canonico[registro["sku_canonico"]].append(registro)

    catalogo, pendientes = [], []
    for sku, iguales in sorted(por_canonico.items()):
        if any(r["nature"] == REQUIERE_DECISION for r in iguales):
            pendientes.extend(iguales)
            continue
        # Gana la descripción más informativa; la otra queda anotada con su
        # archivo y su fila, para que se pueda volver a la planilla.
        principal = max(iguales, key=lambda r: (len(r["nombre"]), r["corte"]))
        variantes = [r for r in iguales
                     if r["nombre"].strip().lower() != principal["nombre"].strip().lower()]
        notas = "; ".join(
            f"variante en {r['sucursal']} ({r['fuente_archivo']} fila {r['fuente_fila']}): "
            f"{r['nombre']}" for r in variantes)
        origen = " | ".join(
            f"{r['sucursal']}={r['fuente_archivo']}#{r['fuente_fila']}@{r['corte']}"
            for r in iguales)
        catalogo.append(dict(
            sku=sku, name=principal["nombre"], nature=principal["nature"],
            category=principal["categoria"], brand=principal["marca"],
            sale_price="", location="", min_stock="", barcode="", unit="UNIDAD",
            notes=(notas + " || " if notas else "") + "origen: " + origen))

    recuentos = {s: [] for s in PREFIJO_SUCURSAL}
    for articulo in catalogo:
        for registro in por_canonico[articulo["sku"]]:
            if registro["nature"] not in MUEVEN_STOCK:
                continue  # un servicio o un trabajo bajo pedido no lleva stock
            if not registro["stock_inicial"] or registro["stock_inicial"] <= 0:
                continue
            recuentos[registro["sucursal"]].append(dict(
                sku=articulo["sku"], cantidad=registro["stock_inicial"],
                fuente=f"{registro['fuente_archivo']}#{registro['fuente_fila']}",
                corte=registro["corte"]))
    return catalogo, recuentos, pendientes


CAMPOS = ["sku", "name", "nature", "category", "brand", "sale_price", "location",
          "min_stock", "barcode", "unit", "notes"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pc", required=True, help="PC - Inventario.xlsx (Asunción)")
    parser.add_argument("--p2", required=True, help="P2 - Inventario.xlsx (Pilar)")
    parser.add_argument("--salida", required=True)
    args = parser.parse_args()

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    registros, rechazos = normalizar({"PC": Path(args.pc), "P2": Path(args.p2)})
    catalogo, recuentos, pendientes = consolidar(registros)

    with (salida / "catalogo_canonico.csv").open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=CAMPOS)
        escritor.writeheader()
        escritor.writerows(catalogo)
    for sucursal, lineas in recuentos.items():
        (salida / f"recuento_{sucursal}.json").write_text(
            json.dumps(lineas, ensure_ascii=False, indent=1), encoding="utf-8")

    globales = sum(1 for a in catalogo if identificador_es_global(a["sku"]))
    print(f"registros normalizados : {len(registros)}")
    print(f"filas rechazadas       : {len(rechazos)}")
    print(f"articulos canonicos    : {len(catalogo)} "
          f"({globales} globales, {len(catalogo) - globales} con prefijo de sucursal)")
    for sucursal, lineas in recuentos.items():
        print(f"recuento {sucursal:9}: {len(lineas):>5} lineas, "
              f"{sum(x['cantidad'] for x in lineas):>7} unidades")
    print(f"en espera de decision  : {len(pendientes)}")
    for clave, cuantos in Counter(
            (r["sucursal"], r["categoria"] or "(sin categoria)") for r in pendientes).most_common():
        print(f"    {clave[0]:9} {clave[1]:22} {cuantos:>4}")
    for rechazo in rechazos:
        print(f"    RECHAZO {rechazo['fuente']} fila {rechazo['fila']:>5}: "
              f"{rechazo['motivo']} -- {rechazo['articulo'][:44]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
