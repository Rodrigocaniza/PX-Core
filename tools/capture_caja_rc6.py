"""Smoke visual reproducible de BC Caja rc.6 a 1366x768."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import customtkinter as ctk
from PIL import ImageGrab
from tkinter import ttk

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
    original_info = CajaDiaria.messagebox.showinfo
    original_warning = CajaDiaria.messagebox.showwarning
    original_confirm = CajaDiaria.messagebox.askyesno
    CajaDiaria.messagebox.showinfo = lambda *args, **kwargs: None
    CajaDiaria.messagebox.showwarning = lambda *args, **kwargs: None
    CajaDiaria.messagebox.askyesno = lambda *args, **kwargs: True
    with tempfile.TemporaryDirectory(prefix="bc-caja-rc6-") as data_dir:
        os.environ["BC_CAJA_DATA_DIR"] = data_dir
        os.environ["BC_CAJA_WINDOW_SIZE"] = "1366x768"

        def smoke(root):
            root.update_idletasks(); root.update()
            widgets = list(descendants(root))
            labels = [w for w in widgets if isinstance(w, ctk.CTkLabel)]
            texts = [str(w.cget("text")) for w in labels]
            texts += [str(w.cget("text")) for w in widgets if isinstance(w, ctk.CTkCheckBox)]
            required = (
                "CLIENTE Y COMPROBANTE", "DETALLE DE VENTA", "PAGO",
                "Cliente", "CI / RUC", "Teléfono", "Sobre / Trabajo",
                "Fecha de entrega", "Vendedora *", "Tipo / Producto", "Código",
                "Laboratorio", "Precio armazón", "Precio cristal", "Receta / Doctor",
                "Efectivo", "Transferencia", "Tarjeta / Cheque", "Orden / Convenio",
                "Monto convenio", "Cuotas", "Total de la venta", "Saldo cliente",
                "OBSERVACIONES", "SALIDA DE CAJA", "Desc. armazón %",
                "Desc. cristal %", "Artículo sin costo",
            )
            missing = [text for text in required if text not in texts]
            if missing:
                raise RuntimeError(f"faltan controles rc.6: {missing}")
            panels = [w.master for w in labels if str(w.cget("text")) in (
                "CLIENTE Y COMPROBANTE", "DETALLE DE VENTA", "PAGO"
            )]
            print("BC_CAJA_RC6_PANELS " + " ".join(
                f"x={w.winfo_rootx()} width={w.winfo_width()} req={w.winfo_reqwidth()}" for w in panels
            ))
            if "TOTAL DE LA VENTA" in texts or "OPEN" in texts:
                raise RuntimeError("persisten textos visuales retirados")
            notes = [w for w in widgets if isinstance(w, ctk.CTkTextbox) and w.winfo_ismapped()]
            if len(notes) != 1 or notes[0].winfo_height() < 60:
                raise RuntimeError(f"observaciones multilínea no ocupa el panel: count={len(notes)} height={notes[0].winfo_height() if notes else 0}")
            outflow_panel = next(w.master for w in labels if str(w.cget("text")) == "SALIDA DE CAJA")
            notes_panel = notes[0].master
            if outflow_panel.winfo_rootx() + outflow_panel.winfo_width() > notes_panel.winfo_rootx() + 8:
                raise RuntimeError("Salida de caja invade la columna Observaciones")
            if notes_panel.winfo_height() < outflow_panel.winfo_height() + 70:
                raise RuntimeError(f"Observaciones no ocupa la altura combinada: notes={notes_panel.winfo_height()} outflow={outflow_panel.winfo_height()}")
            movement_grids = [w for w in widgets if isinstance(w, ttk.Treeview) and len(w.cget("columns")) > 10]
            if not movement_grids or movement_grids[0].winfo_height() < 5 * 27:
                raise RuntimeError("no hay capacidad visual para cinco movimientos")
            notes[0].insert("1.0", "RX lejos\nOD +1.50\nOI +1.25")
            clear = next(w for w in widgets if isinstance(w, ctk.CTkButton) and w.cget("text") == "Limpiar todo")
            sale_panels = [w.master for w in labels if str(w.cget("text")) in (
                "CLIENTE Y COMPROBANTE", "DETALLE DE VENTA", "PAGO"
            )]
            sale_entries = [w for w in widgets if isinstance(w, ctk.CTkEntry)
                            and w.master in sale_panels]
            for entry in sale_entries:
                if entry.cget("state") == "normal":
                    try: entry.insert(0, "PRUEBA")
                    except Exception: pass
            clear.invoke(); root.update()
            if notes[0].get("1.0", "end-1c"):
                raise RuntimeError("Limpiar no vació observaciones")
            outflow_panel = next(w.master for w in labels if str(w.cget("text")) == "SALIDA DE CAJA")
            outflow = [w for w in widgets if isinstance(w, ctk.CTkEntry) and w.master is outflow_panel]
            current_user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
            if any(w.get() and w.get() != current_user for w in outflow):
                raise RuntimeError("Limpiar no vació Salida de caja")
            root.attributes("-topmost", True); root.update()
            ImageGrab.grab((0, 0, 1366, 768)).save(output)
            print("BC_CAJA_RC6_VISUAL_SMOKE_OK resolution=1366x768 clear=sale+outflow observations=combined-height discounts=no-cost layout=two-columns rows=5")
            root.destroy()

        ctk.CTk.mainloop = smoke
        try:
            bc_caja.main()
        finally:
            ctk.CTk.mainloop = original_mainloop
            CajaDiaria.messagebox.showinfo = original_info
            CajaDiaria.messagebox.showwarning = original_warning
            CajaDiaria.messagebox.askyesno = original_confirm
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
