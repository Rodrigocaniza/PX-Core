"""Smoke visual reproducible de BC Caja rc.11 a 1366x768."""
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
    confirmations = []
    CajaDiaria.messagebox.askyesno = lambda *args, **kwargs: (confirmations.append(args), True)[1]
    with tempfile.TemporaryDirectory(prefix="bc-caja-rc11-") as data_dir:
        os.environ["BC_CAJA_DATA_DIR"] = data_dir
        os.environ["BC_CAJA_WINDOW_SIZE"] = "1366x768"
        from datetime import date
        from modulos.caja_diaria.bootstrap import build_cash_day_controller
        from modulos.caja_diaria.domain.models import SaleItem
        seed = build_cash_day_controller(Path(data_dir) / "bc_caja.sqlite3")
        today = date.today().strftime("%d-%m-%Y")
        seed.open_or_load_day(today, "PC", "0")
        saved_ids = []
        for index in range(3):
            values = {
                "fecha": today, "unidad": "PC", "caja_inicial": "0",
                "descripcion": f"Cliente {index + 1}", "cliente_telefono": f"09810000{index}",
                "cliente_documento": "" if index == 1 else f"DOC-{index}",
                "sobre": f"S-{index}", "fecha_entrega": today, "vendedora": "Ana",
                "total": "100000", "efectivo": "100000", "tarjeta_cheque": "0",
                "transferencia": "0", "monto_convenio": "0", "notas": "",
                "items": (SaleItem(description="Cristal", lens_price=100000),),
            }
            _, entry = seed.add_manual_entry(values); saved_ids.append(entry.id)
        orders = seed.list_orders("Todos", today=today)
        seed.update_order_status(orders[0].id, "LISTO", responsible="smoke")
        seed.update_order_status(orders[0].id, "ENTREGADO", responsible="smoke")
        seed.update_order_status(orders[1].id, "LISTO", responsible="smoke")
        seed.void_entry(today, "PC", saved_ids[2], "Anulado para contraste", user="smoke")
        seed.service.repository.close()

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
                "Laboratorio", "P. Armazón / Desc. %", "P. Cristal / Desc. %", "Receta / Doctor",
                "Efectivo", "Transferencia", "Tarjeta / Cheque", "Orden / Convenio",
                "Monto convenio", "Cuotas", "Total de la venta", "Saldo cliente",
                "OBSERVACIONES", "SALIDA DE CAJA", "Artículo sin costo",
            )
            missing = [text for text in required if text not in texts]
            if missing:
                raise RuntimeError(f"faltan controles rc.11: {missing}")
            initial_notes = next(w for w in widgets if isinstance(w, ctk.CTkTextbox) and w.winfo_ismapped())
            template = CajaDiaria.PLANTILLA_RECETA_OBSERVACIONES
            if initial_notes.get("1.0", "end-1c") != template:
                raise RuntimeError("Observaciones no inicia con la plantilla exacta")
            initial_clear = next(w for w in widgets if isinstance(w, ctk.CTkButton) and w.cget("text") == "Limpiar todo")
            initial_clear.invoke(); root.update()
            if confirmations or initial_notes.get("1.0", "end-1c") != template:
                raise RuntimeError(f"plantilla neutra provocó confirmación o no se restauró: confirmations={len(confirmations)}")
            detail = next(w.master for w in labels if str(w.cget("text")) == "DETALLE DE VENTA")
            discounts = [w for w in widgets if isinstance(w, ctk.CTkEntry) and w.master is detail and int(w.grid_info().get("row", -1)) == 4 and int(w.grid_info().get("column", -1)) in (2, 5)]
            prices = [w for w in widgets if isinstance(w, ctk.CTkEntry) and w.master is detail and int(w.grid_info().get("row", -1)) == 4 and int(w.grid_info().get("column", -1)) in (1, 4)]
            if len(discounts) != 2 or len(prices) != 2 or any(w.winfo_width() > 48 for w in discounts):
                raise RuntimeError(f"descuentos no son dos campos estrechos: count={len(discounts)} widths={[w.winfo_width() for w in discounts]}")
            if {w.winfo_rooty() for w in discounts + prices}.__len__() != 1:
                raise RuntimeError("precios y descuentos no comparten la misma fila")
            add_button = next(w for w in widgets if isinstance(w, ctk.CTkButton) and w.cget("text") == "+ Agregar artículo")
            no_cost = next(w for w in widgets if isinstance(w, ctk.CTkCheckBox) and w.cget("text") == "Artículo sin costo")
            if add_button.winfo_rooty() != no_cost.winfo_rooty() or add_button.winfo_rootx() >= no_cost.winfo_rootx():
                raise RuntimeError("Artículo sin costo no está a la derecha de Agregar artÃ­culo")
            product_type = next(w for w in widgets if isinstance(w, ctk.CTkEntry) and w.master is detail and int(w.grid_info().get("row", -1)) == 1 and int(w.grid_info().get("column", -1)) == 1)
            product_type.insert(0, "Cortesía RC11")
            for price in prices:
                price.delete(0, "end")
            no_cost.select(); add_button.invoke(); root.update_idletasks(); root.update()
            draft_grid = next(w for w in widgets if isinstance(w, ttk.Treeview) and tuple(w.cget("columns")) == ("producto", "codigo", "tipo", "armazon", "cristal", "subtotal"))
            row = draft_grid.item(draft_grid.get_children()[0], "values")
            if row[2] != "SIN COSTO" or str(row[5]) != "0":
                raise RuntimeError(f"fila Sin costo incorrecta: {row}")
            draft_grid.selection_set(draft_grid.get_children()[0])
            edit_button = next(w for w in widgets if isinstance(w, ctk.CTkButton) and w.cget("text") == "Editar artículo seleccionado")
            edit_button.invoke(); root.update()
            if no_cost.get() != "1":
                raise RuntimeError("editar artículo no restauró Sin costo")
            widths = {key: int(draft_grid.column(key, "width")) for key in draft_grid.cget("columns")}
            total_width = sum(widths.values())
            expected = {"producto": .35, "codigo": .12, "tipo": .18, "armazon": .12, "cristal": .12, "subtotal": .11}
            if any(abs(widths[key] / total_width - ratio) > .025 for key, ratio in expected.items()):
                raise RuntimeError(f"distribución de columnas fuera de contrato: {widths}")
            draft_panel = next(w.master for w in labels if str(w.cget("text")) == "VENTA EN CURSO")
            notes_title_panel = next(w.master for w in labels if str(w.cget("text")) == "OBSERVACIONES")
            if draft_panel.master is not notes_title_panel.master or draft_panel is notes_title_panel:
                raise RuntimeError("Venta en curso y Observaciones no son contenedores hermanos independientes")
            panels = [w.master for w in labels if str(w.cget("text")) in (
                "CLIENTE Y COMPROBANTE", "DETALLE DE VENTA", "PAGO"
            )]
            print("BC_CAJA_RC11_PANELS " + " ".join(
                f"x={w.winfo_rootx()} width={w.winfo_width()} req={w.winfo_reqwidth()}" for w in panels
            ))
            if "TOTAL DE LA VENTA" in texts or "OPEN" in texts:
                raise RuntimeError("persisten textos visuales retirados")
            notes = [w for w in widgets if isinstance(w, ctk.CTkTextbox) and w.winfo_ismapped()]
            if len(notes) != 1 or notes[0].winfo_height() < 60:
                raise RuntimeError(f"observaciones multilínea no ocupa el panel: count={len(notes)} height={notes[0].winfo_height() if notes else 0}")
            outflow_panel = next(w.master for w in labels if str(w.cget("text")) == "SALIDA DE CAJA")
            notes_panel = notes_title_panel
            movement_toolbar = next(w.master for w in labels if str(w.cget("text")) == "Movimientos del día")
            right_gap = 1366 - (notes_panel.winfo_rootx() + notes_panel.winfo_width())
            bottom_gap = movement_toolbar.winfo_rooty() - (notes_panel.winfo_rooty() + notes_panel.winfo_height())
            if right_gap > 20 or bottom_gap < 0 or bottom_gap > 4:
                raise RuntimeError(f"Observaciones no ocupa borde derecho/inferior: right={right_gap} bottom={bottom_gap}")
            if outflow_panel.winfo_rootx() + outflow_panel.winfo_width() > notes_panel.winfo_rootx() + 8:
                raise RuntimeError("Salida de caja invade la columna Observaciones")
            if notes_panel.winfo_height() < outflow_panel.winfo_height() + 70:
                raise RuntimeError(f"Observaciones no ocupa la altura combinada: notes={notes_panel.winfo_height()} outflow={outflow_panel.winfo_height()}")
            movement_grids = [w for w in widgets if isinstance(w, ttk.Treeview) and len(w.cget("columns")) > 10]
            movement = movement_grids[0]
            movement_width = sum(int(movement.column(key, "width")) for key in movement.cget("columns"))
            if movement_width > movement.winfo_width() + 4:
                raise RuntimeError(f"Movimientos requiere scroll horizontal: columns={movement_width} tree={movement.winfo_width()}")
            expected_anchors = {"hora":"center", "descripcion":"w", "cliente_telefono":"center", "tipo_resumen":"w", "sobre":"center", "total":"center", "efectivo":"center", "tarjeta_transferencia":"center", "monto_convenio":"center", "cuotas":"center", "saldo":"center", "vendedora":"center", "estado":"center", "acciones":"center"}
            anchors = {key: str(movement.column(key, "anchor")) for key in movement.cget("columns")}
            if anchors != expected_anchors:
                raise RuntimeError(f"anchors Movimientos incorrectos: {anchors}")
            if not movement_grids or movement_grids[0].winfo_height() < 5 * 27:
                raise RuntimeError("no hay capacidad visual para cinco movimientos")
            notes[0].insert("1.7", " María\n")
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
            if notes[0].get("1.0", "end-1c") != template:
                raise RuntimeError("Limpiar no restauró la plantilla exacta")
            if len(confirmations) != 1:
                raise RuntimeError(f"receta escrita no produjo una sola confirmación: {len(confirmations)}")
            outflow_panel = next(w.master for w in labels if str(w.cget("text")) == "SALIDA DE CAJA")
            outflow = [w for w in widgets if isinstance(w, ctk.CTkEntry) and w.master is outflow_panel]
            current_user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
            if any(w.get() and w.get() != current_user for w in outflow):
                raise RuntimeError("Limpiar no vació Salida de caja")
            pedidos_nav = next(w for w in widgets if isinstance(w, ctk.CTkButton) and "Pedidos" in str(w.cget("text")))
            pedidos_nav.invoke(); root.update_idletasks(); root.update()
            for button in [w for w in descendants(root) if isinstance(w, ctk.CTkButton) and w.cget("text") == "Todos"]:
                button.invoke()
            root.update_idletasks(); root.update()
            pedidos_grid = next(w for w in descendants(root) if isinstance(w, ttk.Treeview) and len(w.cget("columns")) == 9)
            headers = {key: str(pedidos_grid.heading(key, "anchor")) for key in pedidos_grid.cget("columns")}
            expected_headers = {"entrega": "center", "cliente": "w", "telefono": "center", "documento": "center", "sobre": "center", "sucursal": "center", "vendedora": "center", "origen": "center", "estado": "center"}
            if headers != expected_headers:
                raise RuntimeError(f"anchors de Pedidos incorrectos: {headers}")
            states = {pedidos_grid.set(iid, "estado") for iid in pedidos_grid.get_children()}
            if not {"PENDIENTE", "LISTO", "ENTREGADO"}.issubset(states):
                raise RuntimeError(f"faltan estados de smoke: {states}")
            root.update()
            chip_texts = {str(w.cget("text")) for w in descendants(root) if isinstance(w, ctk.CTkLabel) and str(w.cget("text")) in {"PENDIENTE", "LISTO", "ENTREGADO"}}
            if chip_texts != {"PENDIENTE", "LISTO", "ENTREGADO"}:
                raise RuntimeError(f"chips no renderizados: {chip_texts}")
            for label in ("Marcar pendiente", "Marcar listo", "Marcar entregado"):
                if not any(isinstance(w, ctk.CTkButton) and w.cget("text") == label for w in descendants(root)):
                    raise RuntimeError(f"falta acción {label}")
            historial_nav = next(w for w in descendants(root) if isinstance(w, ctk.CTkButton) and w.cget("text") == "Historial")
            historial_nav.invoke(); root.update()
            consultar = next(w for w in descendants(root) if isinstance(w, ctk.CTkButton) and w.cget("text") == "Consultar")
            consultar.invoke(); root.update_idletasks(); root.update()
            history_texts = [str(w.cget("text")) for w in descendants(root) if isinstance(w, ctk.CTkLabel)]
            if not any("ANULADO" in text for text in history_texts) or not any("ACTIVO" in text for text in history_texts):
                raise RuntimeError("Historial no muestra filas activas y anuladas")
            caja_nav = next(w for w in descendants(root) if isinstance(w, ctk.CTkButton) and "Caja diaria" in str(w.cget("text")))
            caja_nav.invoke(); root.update()
            root.attributes("-topmost", True); root.update()
            ImageGrab.grab((0, 0, 1366, 768)).save(output)
            print("BC_CAJA_RC11_VISUAL_SMOKE_OK resolution=1366x768 clear=sale+outflow observations=combined-height discounts=no-cost layout=two-columns rows=5")
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
