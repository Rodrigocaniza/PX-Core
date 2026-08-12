"""Captura reproducible de BC Caja atravesando el entrypoint real bc_caja.main."""
from __future__ import annotations
import argparse
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
import customtkinter as ctk
from PIL import ImageGrab
from tkinter import ttk
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bc_caja
import CajaDiaria
from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.errors import CashDayClosedError
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
    original_showinfo = CajaDiaria.messagebox.showinfo
    original_showwarning = CajaDiaria.messagebox.showwarning
    CajaDiaria.messagebox.showinfo = lambda *args, **kwargs: None
    CajaDiaria.messagebox.showwarning = lambda *args, **kwargs: None
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
            controller.add_expense(date.today().strftime("%d-%m-%Y"), "PC", "Ferretería", "200000")
            audit_date = date.today() - timedelta(days=2)
            controller.service.open_day(business_date=audit_date, unit="PC", opening_cash=1500000)
            closed_date = date.today() - timedelta(days=1)
            closed = controller.service.open_day(business_date=closed_date, unit="PC", opening_cash=500000)
            controller.service.close_day(closed.id)
            try:
                controller.add_expense(closed_date.strftime("%d-%m-%Y"), "PC", "No permitido", "1000")
                raise RuntimeError("la caja cerrada aceptó un gasto")
            except CashDayClosedError:
                print("BC_CAJA_CLOSED_PROTECTION_OK")
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
                cash_field = field_for("Efectivo")
                card_field = field_for("Tarjeta / Cheque")
                transfer_field = field_for("Transferencia")
                balance_field = field_for("Saldo pendiente")
                for field, value in ((cash_field, "1000000"), (card_field, "500000"), (transfer_field, "0")):
                    field.delete(0, "end")
                    field.insert(0, value)
                    field._entry.event_generate("<KeyRelease>", keysym="0")
                    field._entry.event_generate("<FocusOut>")
                window.update()
                values = (frame_field.get(), lens_field.get(), total_field.get(), balance_field.get())
                if values != ("1.500.000", "250.000", "1.750.000", "250.000"):
                    raise RuntimeError(f"formato/total/saldo visible inválido: {values}")
                print(f"BC_CAJA_MONEY_TOTAL_BALANCE_OK values={values}")
                expense_description = field_for("Descripción *")
                expense_amount = field_for("Monto *")
                expense_description.insert(0, "Ferretería")
                expense_amount.insert(0, "200000")
                expense_amount._entry.event_generate("<FocusOut>")
                expense_buttons = [
                    w for w in descendants(window) if isinstance(w, ctk.CTkButton)
                    and w.cget("text") == "Guardar gasto"
                ]
                if expense_amount.get() != "200.000" or len(expense_buttons) != 1:
                    raise RuntimeError("sección integrada de gasto inválida")
                expense_buttons[0].invoke()
                window.update()
                print("BC_CAJA_INTEGRATED_EXPENSE_OK amount=200.000")
                trees = [w for w in descendants(window) if isinstance(w, ttk.Treeview)]
                if len(trees) != 1:
                    raise RuntimeError(f"se esperó una tabla, encontradas={len(trees)}")
                tree = trees[0]
                before = tree.yview()
                tree.yview_scroll(5, "units")
                window.update_idletasks()
                after = tree.yview()
                if len(tree.get_children()) != args.rows + 2 or after == before:
                    raise RuntimeError(f"scroll no operativo rows={len(tree.get_children())} size={tree.winfo_width()}x{tree.winfo_height()} before={before} after={after}")
                print(f"BC_CAJA_SCROLL_OK rows={args.rows} before={before} after={after}")
            visible = [w for w in descendants(window) if w.winfo_ismapped()]
            action_buttons = [
                w for w in visible if isinstance(w, ctk.CTkButton)
                and w.cget("text") in ("Guardar venta  —  F9", "Limpiar")
            ]
            left_entries = [
                w for w in visible if isinstance(w, ctk.CTkEntry)
                and w.winfo_rootx() - window.winfo_rootx() < 590
                and w.winfo_rooty() - window.winfo_rooty() > 200
            ]
            notes_titles = [
                w for w in visible if isinstance(w, ctk.CTkLabel)
                and w.cget("text") == "Notas"
            ]
            expense_buttons = [
                w for w in visible if isinstance(w, ctk.CTkButton)
                and w.cget("text") == "Guardar gasto"
            ]
            expense_titles = [
                w for w in visible if isinstance(w, ctk.CTkLabel)
                and w.cget("text") == "Gastos"
            ]
            if len(action_buttons) != 2 or len(notes_titles) != 1 or len(expense_buttons) != 1 or len(expense_titles) != 1:
                raise RuntimeError("estructura visible incompleta para validar geometría")
            entry_bottom = max(w.winfo_rooty() + w.winfo_height() for w in left_entries)
            action_top = min(w.winfo_rooty() for w in action_buttons)
            action_bottom = max(w.winfo_rooty() + w.winfo_height() for w in action_buttons)
            if not entry_bottom < action_top:
                raise RuntimeError(
                    f"solapamiento entry_bottom={entry_bottom} action={action_top}..{action_bottom}"
                )
            print(
                f"BC_CAJA_LAYOUT_OK entry_bottom={entry_bottom} action_top={action_top} "
                f"action_bottom={action_bottom}"
            )
            window.lift()
            window.focus_force()
            window.update()
            x, y = window.winfo_rootx(), window.winfo_rooty()
            width, height = window.winfo_width(), window.winfo_height()
            ImageGrab.grab((x, y, x + width, y + height)).save(args.output)
            if args.rows:
                arqueo_buttons = [
                    w for w in descendants(window) if isinstance(w, ctk.CTkButton)
                    and str(w.cget("text")).strip().endswith("Arqueo")
                ]
                if len(arqueo_buttons) != 1:
                    raise RuntimeError("navegación de Arqueo no disponible")
                arqueo_buttons[0].invoke()
                window.update()
                visible_entries = [
                    w for w in descendants(window) if isinstance(w, ctk.CTkEntry)
                    and w.winfo_ismapped()
                ]
                date_field = next(w for w in visible_entries if w.get() == date.today().strftime("%d-%m-%Y"))
                date_field.delete(0, "end")
                date_field.insert(0, (date.today() - timedelta(days=2)).strftime("%d-%m-%Y"))
                consult = next(
                    w for w in descendants(window) if isinstance(w, ctk.CTkButton)
                    and w.cget("text") == "Consultar caja"
                )
                consult.invoke()
                window.update()
                def denomination_field(text_value):
                    label = next(
                        w for w in descendants(window) if isinstance(w, ctk.CTkLabel)
                        and w.winfo_ismapped() and w.cget("text") == text_value
                    )
                    row = label.grid_info()["row"]
                    return next(
                        w for w in label.master.winfo_children()
                        if isinstance(w, ctk.CTkEntry) and w.grid_info().get("row") == row
                    )
                hundred = denomination_field("100.000")
                fifty = denomination_field("50.000")
                hundred.insert(0, "15")
                hundred._entry.event_generate("<KeyRelease>", keysym="5")
                save = next(w for w in descendants(window) if isinstance(w, ctk.CTkButton) and w.cget("text") == "Guardar arqueo")
                save.invoke()
                window.update()
                visible_texts = {
                    w.cget("text") for w in descendants(window)
                    if isinstance(w, ctk.CTkLabel) and w.winfo_ismapped()
                }
                required = {
                    "Efectivo esperado por sistema: 1.500.000",
                    "Efectivo contado: 1.500.000",
                    "Diferencia: 0",
                    "ARQUEO CONFORME\nCaja conforme",
                }
                if not required.issubset(visible_texts):
                    raise RuntimeError(f"arqueo conforme inválido: {required - visible_texts}")
                hundred.delete(0, "end")
                hundred.insert(0, "14")
                fifty.insert(0, "1")
                hundred._entry.event_generate("<KeyRelease>", keysym="4")
                save.invoke()
                window.update()
                texts = {w.cget("text") for w in descendants(window) if isinstance(w, ctk.CTkLabel) and w.winfo_ismapped()}
                if "Diferencia: -50.000" not in texts or "ARQUEO CON DIFERENCIA\nFaltan 50.000" not in texts:
                    raise RuntimeError("arqueo con faltante inválido")
                hundred.delete(0, "end")
                hundred.insert(0, "15")
                hundred._entry.event_generate("<KeyRelease>", keysym="5")
                save.invoke()
                window.update()
                texts = {w.cget("text") for w in descendants(window) if isinstance(w, ctk.CTkLabel) and w.winfo_ismapped()}
                if "Diferencia: +50.000" not in texts or "ARQUEO CON DIFERENCIA\nSobran 50.000" not in texts:
                    raise RuntimeError("arqueo con sobrante inválido")
                save.invoke()
                print("BC_CAJA_CASH_COUNT_OK conforming=0 shortage=-50.000 surplus=+50.000")
            window.attributes("-topmost", False)
            window.destroy()
            root.destroy()

        ctk.CTk.mainloop = capture_mainloop
        try:
            result = bc_caja.main([])
        finally:
            ctk.CTk.mainloop = original_mainloop
            CajaDiaria.messagebox.showinfo = original_showinfo
            CajaDiaria.messagebox.showwarning = original_showwarning
            os.environ.pop("BC_CAJA_DATA_DIR", None)
    print(f"BC_CAJA_REAL_ENTRYPOINT_CAPTURE_OK {args.output} 1366x768 result={result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())