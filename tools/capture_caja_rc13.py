"""Smoke GUI real RC.13 a 1366x768: navegación, Administrador y Arqueo."""
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
    output = Path(sys.argv[1]); sys.argv = [sys.argv[0]]; output.parent.mkdir(parents=True, exist_ok=True)
    original = ctk.CTk.mainloop
    with tempfile.TemporaryDirectory(prefix="bc-caja-rc13-") as directory:
        os.environ.update(BC_CAJA_DATA_DIR=directory, BC_CAJA_WINDOW_SIZE="1366x768",
                          BC_CAJA_RESPONSABLE="Operadora Central", BC_CAJA_AUTOMATED="1")
        from datetime import date
        from modulos.caja_diaria.bootstrap import build_cash_day_controller
        seed = build_cash_day_controller(Path(directory) / "bc_caja.sqlite3")
        seed.admin.open_from_count(date.today().strftime("%d-%m-%Y"), "PC", {100_000: 2},
                                   "Operadora Central", "gui-open")
        seed.service.repository.close()

        def smoke(root):
            root.update_idletasks(); root.update()
            visible = [w for w in descendants(root) if w.winfo_ismapped()]
            buttons = [w for w in visible if isinstance(w, ctk.CTkButton)]
            texts = [str(w.cget("text")) for w in buttons]
            required = ["Administrador", "Arqueo", "Cerrar caja", "Guardar salida", "Limpiar todo"]
            if any(text not in texts for text in required):
                raise RuntimeError(f"controles RC13 ausentes: {[text for text in required if text not in texts]}")
            if any("Importar Excel" in text for text in texts):
                raise RuntimeError("Importar Excel sigue en navegación operativa")
            admin = next(w for w in buttons if w.cget("text") == "Administrador")
            admin.invoke(); root.update_idletasks(); root.update()
            login = next(w for w in root.winfo_children() if isinstance(w, ctk.CTkToplevel))
            login_texts = {str(w.cget("text")) for w in descendants(login)
                           if isinstance(w, (ctk.CTkLabel, ctk.CTkButton))}
            if "CONFIGURACIÓN INICIAL SEGURA" not in login_texts or "Configurar" not in login_texts:
                raise RuntimeError("configuración administrativa inicial incompleta")
            login.destroy(); root.update()
            arqueo = next(w for w in descendants(root) if isinstance(w, ctk.CTkButton) and w.cget("text") == "Arqueo")
            arqueo.invoke(); root.update_idletasks(); root.update()
            modal = next(w for w in root.winfo_children() if isinstance(w, ctk.CTkToplevel))
            modal_texts = {str(w.cget("text")) for w in descendants(modal)
                           if isinstance(w, (ctk.CTkLabel, ctk.CTkButton))}
            if not {"ARQUEO DE CAJA", "Guardar arqueo", "Responsable canónico"} <= modal_texts:
                raise RuntimeError("modal de arqueo intermedio incompleto")
            modal.attributes("-topmost", True); modal.update()
            ImageGrab.grab((0, 0, 1366, 768)).save(output)
            print("BC_CAJA_RC13_VISUAL_SMOKE_OK resolution=1366x768 admin=protected import=admin-only counts=mandatory")
            modal.destroy(); root.destroy()

        ctk.CTk.mainloop = smoke
        try: bc_caja.main()
        finally:
            ctk.CTk.mainloop = original
            for key in ("BC_CAJA_DATA_DIR", "BC_CAJA_WINDOW_SIZE", "BC_CAJA_RESPONSABLE", "BC_CAJA_AUTOMATED"):
                os.environ.pop(key, None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
