"""Captura reproducible de BC Caja atravesando el entrypoint real bc_caja.main."""
from __future__ import annotations
import argparse
import os
import sys
import tempfile
from datetime import date
from pathlib import Path
import customtkinter as ctk
from PIL import ImageGrab
from tkinter import ttk
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bc_caja
from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.models import CashEntry


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--rows", type=int, default=0)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    original_mainloop = ctk.CTk.mainloop
    with tempfile.TemporaryDirectory(prefix="bc-caja-entrypoint-") as directory:
        os.environ["BC_CAJA_DATA_DIR"] = directory
        if args.rows:
            controller = build_cash_day_controller()
            day = controller.service.open_day(
                business_date=date.today(), unit="PC", opening_cash=1190000
            )
            for index in range(args.rows):
                controller.service.add_entry(day.id, CashEntry(
                    description=f"CLIENTE DEMO {index + 1:02d}",
                    envelope=f"DEMO-{index + 1:04d}", frame_origin="ARMAZON DEMO",
                    code=f"COD-{index + 1:04d}", frame="1250000", lens="1450000",
                    total=2700000, cash=1500000, card_check=1200000,
                    balance="0", source_reference="DATOS SINTETICOS UX-006",
                ))
            controller.service.repository.close()

        def capture_mainloop(root):
            root.update_idletasks()
            windows = [child for child in root.winfo_children() if isinstance(child, ctk.CTkToplevel)]
            if len(windows) != 1:
                raise RuntimeError(f"entrypoint creó {len(windows)} ventanas de Caja")
            window = windows[0]
            window.attributes("-topmost", True)
            window.update_idletasks()
            if args.rows:
                open_buttons = [w for w in descendants(window) if isinstance(w, ctk.CTkButton) and w.cget("text") == "ABRIR / CONSULTAR"]
                if len(open_buttons) != 1:
                    raise RuntimeError(f"se esperó un botón de apertura, encontrados={len(open_buttons)}")
                open_buttons[0].invoke()
                window.update_idletasks()
                window.update()
                labels = [w for w in descendants(window) if isinstance(w, ctk.CTkLabel)]
                def field_for(label_text):
                    label = next(w for w in labels if w.cget("text") == label_text)
                    siblings_labels = [w for w in label.master.winfo_children() if isinstance(w, ctk.CTkLabel) and w.grid_info().get("row") == 1]
                    siblings_entries = [w for w in label.master.winfo_children() if isinstance(w, ctk.CTkEntry)]
                    return siblings_entries[siblings_labels.index(label)]
                frame_field = field_for("P. Armazón")
                lens_field = field_for("P. Cristal")
                total_field = field_for("Total")
                frame_field.delete(0, "end")
                frame_field.insert(0, "1500000")
                lens_field.delete(0, "end")
                lens_field.insert(0, "250000")
                frame_field._entry.event_generate("<KeyRelease>", keysym="0")
                lens_field._entry.event_generate("<KeyRelease>", keysym="0")
                frame_field._entry.event_generate("<FocusOut>")
                lens_field._entry.event_generate("<FocusOut>")
                window.update()
                values = (frame_field.get(), lens_field.get(), total_field.get())
                if values != ("1.500.000", "250.000", "1.750.000"):
                    raise RuntimeError(f"formato/total visible inválido: {values}")
                print(f"BC_CAJA_MONEY_TOTAL_OK values={values}")
                trees = [w for w in descendants(window) if isinstance(w, ttk.Treeview)]
                if len(trees) != 1:
                    raise RuntimeError(f"se esperó una tabla, encontradas={len(trees)}")
                tree = trees[0]
                before = tree.yview()
                tree.yview_scroll(5, "units")
                window.update_idletasks()
                after = tree.yview()
                if len(tree.get_children()) != args.rows or after == before:
                    raise RuntimeError(f"scroll no operativo rows={len(tree.get_children())} size={tree.winfo_width()}x{tree.winfo_height()} before={before} after={after}")
                print(f"BC_CAJA_SCROLL_OK rows={args.rows} before={before} after={after}")
            visible = [w for w in descendants(window) if w.winfo_ismapped()]
            action_buttons = [
                w for w in visible if isinstance(w, ctk.CTkButton)
                and w.cget("text") in ("Guardar venta  —  F9", "Limpiar", "Registrar gasto")
            ]
            left_entries = [
                w for w in visible if isinstance(w, ctk.CTkEntry)
                and w.winfo_rootx() - window.winfo_rootx() < 590
                and w.winfo_rooty() - window.winfo_rooty() > 200
            ]
            notes_titles = [
                w for w in visible if isinstance(w, ctk.CTkLabel)
                and w.cget("text") == "Notas y gastos"
            ]
            summary_titles = [
                w for w in visible if isinstance(w, ctk.CTkLabel)
                and "Resumen para arqueo" in w.cget("text")
            ]
            if len(action_buttons) != 3 or len(notes_titles) != 1 or len(summary_titles) != 1:
                raise RuntimeError("estructura visible incompleta para validar geometría")
            entry_bottom = max(w.winfo_rooty() + w.winfo_height() for w in left_entries)
            action_top = min(w.winfo_rooty() for w in action_buttons)
            action_bottom = max(w.winfo_rooty() + w.winfo_height() for w in action_buttons)
            summary_top = summary_titles[0].winfo_rooty()
            if not entry_bottom < action_top or not action_bottom < summary_top:
                raise RuntimeError(
                    f"solapamiento entry_bottom={entry_bottom} action={action_top}..{action_bottom} summary_top={summary_top}"
                )
            print(
                f"BC_CAJA_LAYOUT_OK entry_bottom={entry_bottom} action_top={action_top} "
                f"action_bottom={action_bottom} summary_top={summary_top}"
            )
            window.lift()
            window.focus_force()
            window.update()
            x, y = window.winfo_rootx(), window.winfo_rooty()
            width, height = window.winfo_width(), window.winfo_height()
            ImageGrab.grab((x, y, x + width, y + height)).save(args.output)
            window.attributes("-topmost", False)
            window.destroy()
            root.destroy()

        ctk.CTk.mainloop = capture_mainloop
        try:
            result = bc_caja.main([])
        finally:
            ctk.CTk.mainloop = original_mainloop
            os.environ.pop("BC_CAJA_DATA_DIR", None)
    print(f"BC_CAJA_REAL_ENTRYPOINT_CAPTURE_OK {args.output} 1366x768 result={result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())