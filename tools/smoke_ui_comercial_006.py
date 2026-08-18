"""Smoke de la UI Comercial y del buscador de artículos, sobre base migrada.

Que el paquete lleve los módulos y que la cadena se aplique no dice todavía si
la pantalla abre. Esto la abre de verdad —con Tk, contra una base ya migrada a
027— recorre sus tres pestañas y la cierra. Si algo en el armado quedó atado a
una columna vieja, acá se cae.

    python tools/smoke_ui_comercial_006.py --base <ruta a una copia migrada>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

lineas: list[str] = []
fallas: list[str] = []


def registrar(texto: str = "") -> None:
    print(texto)
    lineas.append(texto)


def comprobar(condicion: bool, descripcion: str) -> bool:
    registrar(f"  {'OK  ' if condicion else 'FALLA'} {descripcion}")
    if not condicion:
        fallas.append(descripcion)
    return bool(condicion)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    args = parser.parse_args()
    base = Path(args.base)

    import customtkinter as ctk

    from modulos.comercial.application.comercial_controller import (
        build_comercial_controller,
    )
    from modulos.comercial.ui.comercial_window import (
        BuscadorDeArticulos,
        VentanaComercial,
    )

    registrar(f"base migrada  : {base}")
    controlador = build_comercial_controller(base)
    raiz = ctk.CTk()
    raiz.withdraw()
    try:
        ventana = VentanaComercial(raiz, controlador, actor="smoke", unidad="PC")
        ventana.withdraw()
        raiz.update_idletasks()
        raiz.update()
        comprobar(bool(ventana.winfo_exists()), "la ventana Comercial abre")
        for pestana in ("Artículos", "Proveedores", "Compras"):
            ventana.pestanas.set(pestana)
            raiz.update_idletasks()
            raiz.update()
            comprobar(True, f"la pestaña {pestana} se arma y se pinta")
        ventana.refrescar_articulos()
        ventana.refrescar_proveedores()
        raiz.update()
        comprobar(True, "refrescar artículos y proveedores no rompe")
        ventana.destroy()
        raiz.update()

        buscador = BuscadorDeArticulos(raiz, controlador, unidad="PC",
                                      al_elegir=lambda *_: None)
        buscador.withdraw()
        raiz.update_idletasks()
        raiz.update()
        comprobar(bool(buscador.winfo_exists()),
                  "el buscador de artículos de la línea de venta abre")
        buscador.destroy()
        raiz.update()
    finally:
        try:
            controlador.close()
        finally:
            raiz.destroy()

    registrar()
    veredicto = "PASS" if not fallas else "FALLA"
    registrar(f"VEREDICTO: {veredicto} ({len(fallas)} fallas)")
    for falla in fallas:
        registrar(f"  - {falla}")

    destino = RAIZ / "artifacts" / "BC-OPTICA-VENTA-REVERSIBLE-Y-RELEASE-GATE-V1-006"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "SMOKE_UI_COMERCIAL.txt").write_text(
        "\n".join(lineas) + "\n", encoding="utf-8")
    return 0 if not fallas else 1


if __name__ == "__main__":
    raise SystemExit(main())
