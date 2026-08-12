"""Captura reproducible de BC Comunicaciones a 1366x768 sobre datos temporales vacíos."""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

import customtkinter as ctk
from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.comunicaciones.bootstrap import build_controller
from modulos.comunicaciones.infrastructure.clipboard import InMemoryClipboard
from modulos.comunicaciones.ui.app import abrir_comunicaciones


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--query", default="retirar")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="bc-comunicaciones-capture-") as directory:
        controller = build_controller(
            Path(directory) / "bc_comunicaciones.sqlite3", clipboard=InMemoryClipboard()
        )
        root = ctk.CTk()
        root.withdraw()
        window = abrir_comunicaciones(root, controller)
        window.update()
        window._primer_dibujado()

        # Estado representativo: una plantilla abierta con sus datos completados.
        window.entrada_operador.insert(0, "Rocío")
        window.entrada_busqueda.insert(0, args.query)
        window._refrescar_resultados()
        window.update()
        if window._resultados:
            window._abrir_plantilla(window._resultados[0].id)
            window.update()
            ejemplos = {
                "cliente": "María González",
                "pedido": "1245",
                "sucursal": "Casa Central",
                "horario": "lunes a viernes de 08:00 a 18:00 y sábados de 08:00 a 12:00",
                "fecha": "martes 18/08",
                "producto": "cristales antirreflejo",
                "monto": "850.000 Gs.",
                "estado": "en laboratorio",
            }
            for nombre, campo in window._campos_variables.items():
                campo.delete(0, "end")
                campo.insert(0, ejemplos.get(nombre, f"{nombre} de ejemplo"))
            window._refrescar_vista_previa()

        # La captura toma la pantalla: hay que garantizar que nada quede encima.
        window.deiconify()
        window.lift()
        window.focus_force()
        window.attributes("-topmost", True)
        for _ in range(5):
            window.update_idletasks()
            window.update()
            time.sleep(0.25)

        x, y = window.winfo_rootx(), window.winfo_rooty()
        width, height = window.winfo_width(), window.winfo_height()
        ImageGrab.grab((x, y, x + width, y + height)).save(args.output)
        window.attributes("-topmost", False)

        controller.repository.close()
        window.destroy()
        root.destroy()

    print(f"BC_COMUNICACIONES_CAPTURE_OK {args.output} {width}x{height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
