"""Captura reproducible del layout de BC Caja con almacenamiento temporal vacío."""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import date
from pathlib import Path

import customtkinter as ctk
from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CajaDiaria import abrir_caja_diaria
from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.models import CashEntry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="bc-caja-ux006-") as directory:
        controller = build_cash_day_controller(Path(directory) / "bc_caja.sqlite3")
        day = controller.service.open_day(
            business_date=date.today(), unit="PC", opening_cash=1190000
        )
        controller.service.add_entry(day.id, CashEntry(
            description="María Fernández", envelope="S-00045", frame_origin="Armazón",
            code="ARM-12345", frame=1250000, lens=1450000,
            laboratory="Lab Central", prescription_doctor="Dra. López",
            total=2700000, cash=1500000, card_check=1200000, balance="0",
        ))
        controller.service.add_entry(day.id, CashEntry(
            description="Compra de cristales", expenses=320000
        ))
        root = ctk.CTk()
        root.withdraw()
        window = abrir_caja_diaria(root, controller=controller)
        window.attributes("-topmost", True)
        window.update_idletasks()
        for child in window.winfo_children():
            if isinstance(child, ctk.CTkTabview):
                child.set("Cargar manual")
                break
        window.update_idletasks()
        def invoke_open(widget):
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkButton) and child.cget("text") == "ABRIR / CONSULTAR":
                    child.invoke()
                    return True
                if invoke_open(child):
                    return True
            return False
        invoke_open(window)
        window.update_idletasks()
        window.lift()
        window.focus_force()
        window.update()
        x, y = window.winfo_rootx(), window.winfo_rooty()
        width, height = window.winfo_width(), window.winfo_height()
        ImageGrab.grab((x, y, x + width, y + height)).save(args.output)
        window.attributes("-topmost", False)
        controller.service.repository.close()
        window.destroy()
        root.destroy()
    print(f"BC_CAJA_UX006_CAPTURE_OK {args.output} 1366x768")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
