"""Captura reproducible del layout UX-002 usando almacenamiento temporal vacío."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import customtkinter as ctk
from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CajaDiaria import abrir_caja_diaria
from modulos.caja_diaria.bootstrap import build_cash_day_controller


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="bc-caja-ux002-") as directory:
        controller = build_cash_day_controller(Path(directory) / "bc_caja.sqlite3")
        root = ctk.CTk()
        root.withdraw()
        window = abrir_caja_diaria(root, controller=controller)
        window.update_idletasks()
        for child in window.winfo_children():
            if isinstance(child, ctk.CTkTabview):
                child.set("Cargar manual")
                break
        window.update_idletasks()
        window.update()
        x, y = window.winfo_rootx(), window.winfo_rooty()
        width, height = window.winfo_width(), window.winfo_height()
        ImageGrab.grab((x, y, x + width, y + height)).save(args.output)
        controller.service.repository.close()
        window.destroy()
        root.destroy()
    print(f"BC_CAJA_UX002_CAPTURE_OK {args.output} 1366x768")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
