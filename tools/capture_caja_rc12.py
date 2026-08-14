"""Smoke GUI real de RC.12: Arqueo modal desde Caja diaria a 1366x768."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import customtkinter as ctk
from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bc_caja
import CajaDiaria


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def main() -> int:
    output = Path(sys.argv[1])
    sys.argv = [sys.argv[0]]
    output.parent.mkdir(parents=True, exist_ok=True)
    original_mainloop = ctk.CTk.mainloop
    original_error = CajaDiaria.messagebox.showerror
    CajaDiaria.messagebox.showerror = lambda *args, **kwargs: (_ for _ in ()).throw(
        RuntimeError(f"GUI error: {args}")
    )
    with tempfile.TemporaryDirectory(prefix="bc-caja-rc12-") as data_dir:
        os.environ["BC_CAJA_DATA_DIR"] = data_dir
        os.environ["BC_CAJA_WINDOW_SIZE"] = "1366x768"
        os.environ["BC_CAJA_RESPONSABLE"] = "Operadora Central"
        from datetime import date
        from modulos.caja_diaria.bootstrap import build_cash_day_controller

        today = date.today().strftime("%d-%m-%Y")
        seed = build_cash_day_controller(Path(data_dir) / "bc_caja.sqlite3")
        seed.open_or_load_day(today, "PC", "250000")
        seed.service.repository.close()

        def smoke(root):
            root.update_idletasks()
            root.update()
            buttons = [w for w in descendants(root) if isinstance(w, ctk.CTkButton)]
            arqueo_buttons = [w for w in buttons if w.cget("text") == "Arqueo"]
            if len(arqueo_buttons) != 1:
                raise RuntimeError(f"cantidad inesperada de acciones Arqueo: {len(arqueo_buttons)}")
            arqueo = arqueo_buttons[0]
            if not arqueo.winfo_ismapped():
                raise RuntimeError("botón Arqueo no visible en Caja diaria")
            outflow = next(
                w.master for w in descendants(root)
                if isinstance(w, ctk.CTkLabel) and w.cget("text") == "SALIDA DE CAJA"
            )
            outflow_texts = [str(w.cget("text")) for w in descendants(outflow)
                             if isinstance(w, (ctk.CTkLabel, ctk.CTkButton))]
            if any("Responsable" in text or "Striker" in text for text in outflow_texts):
                raise RuntimeError(f"responsable visible en salida: {outflow_texts}")
            arqueo.invoke()
            root.update_idletasks()
            root.update()
            modal = next(w for w in root.winfo_children() if isinstance(w, ctk.CTkToplevel))
            texts = {str(w.cget("text")) for w in descendants(modal)
                     if isinstance(w, (ctk.CTkLabel, ctk.CTkButton))}
            required = {
                "ARQUEO DE CAJA", "Caja inicial", "Cobros en efectivo", "Gastos",
                "Entregas administración", "Efectivo esperado", "Responsable canónico",
                "Operadora Central", "Guardar arqueo", "Cerrar",
            }
            missing = required - texts
            if missing:
                raise RuntimeError(f"faltan controles del modal: {sorted(missing)}")
            modal.attributes("-topmost", True)
            modal.update()
            ImageGrab.grab((0, 0, 1366, 768)).save(output)
            print("BC_CAJA_RC12_VISUAL_SMOKE_OK resolution=1366x768 modal=arqueo navigation=no-tab responsible=canonical")
            modal.destroy()
            root.destroy()

        ctk.CTk.mainloop = smoke
        try:
            bc_caja.main()
        finally:
            ctk.CTk.mainloop = original_mainloop
            CajaDiaria.messagebox.showerror = original_error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
