"""Captura reproducible de Pedidos / "Requieren atención" (BC-CAJA-RC12-PEDIDOS-ATENCION-001).

Siembra un día realista de la Óptica -- atrasados, entregas de hoy y próximas --
y captura la pestaña Pedidos tal como la ve la operadora al abrir el aviso.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import customtkinter as ctk
from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CajaDiaria import abrir_caja_diaria
from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.models import CashEntry

PEDIDOS = (
    ("Ramona Benítez", "0981 555 101", "S-00410", -6, "Ana", None),
    ("Carlos Duarte", "0982 555 102", "S-00415", -3, "Sol", ("LISTO", "Ana", "Llegó del laboratorio")),
    ("Lucía Ayala", "0983 555 103", "S-00421", -1, "Ana", None),
    ("Miguel Rojas", "0984 555 104", "S-00430", 0, "Sol", None),
    ("Fátima Ozorio", "0985 555 105", "S-00431", 0, "Ana", ("LISTO", "Sol", "Cristal repuesto")),
    ("Diego Villalba", "0986 555 106", "S-00436", 2, "Ana", None),
)


def seed(controller) -> None:
    hoy = date.today()
    day = controller.service.open_day(business_date=hoy, unit="PC", opening_cash=1190000)
    for nombre, telefono, sobre, offset, vendedora, _revision in PEDIDOS:
        controller.service.add_entry(day.id, CashEntry(
            description=nombre, customer_phone=telefono, envelope=sobre,
            saleswoman=vendedora, delivery_date=hoy + timedelta(days=offset),
            frame_origin="Armazón", frame=1250000, lens=1450000,
            laboratory="Lab Central", total=2700000, cash=2700000, balance="0",
        ))


def apply_revisions(controller) -> None:
    por_nombre = {order.customer_name: order for order in controller.list_orders("Todos")}
    for nombre, _tel, _sobre, _offset, _vendedora, revision in PEDIDOS:
        if not revision or nombre not in por_nombre:
            continue
        estado, responsable, motivo = revision
        controller.update_order_status(
            por_nombre[nombre].id, estado, reason=motivo, responsible=responsable
        )


def buscar_widget(raiz, predicado):
    for hijo in raiz.winfo_children():
        if predicado(hijo):
            return hijo
        encontrado = buscar_widget(hijo, predicado)
        if encontrado is not None:
            return encontrado
    return None


def seleccionar_primer_pedido(window) -> None:
    """Selecciona la primera fila real (los encabezados de grupo no son pedidos)."""
    from tkinter import ttk

    grilla = buscar_widget(window, lambda w: isinstance(w, ttk.Treeview) and "novedad" in w["columns"])
    for iid in grilla.get_children():
        if not iid.startswith("grupo::"):
            grilla.selection_set(iid)
            grilla.focus(iid)
            grilla.event_generate("<<TreeviewSelect>>")
            return


def invocar_boton(window, texto: str) -> None:
    boton = buscar_widget(
        window, lambda w: isinstance(w, ctk.CTkButton) and w.cget("text") == texto
    )
    boton.invoke()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument(
        "--dialogo", action="store_true",
        help="captura el diálogo 'Corregir estado' sobre el primer pedido atrasado",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Único camino soportado para fijar el tamaño: forzar geometría a mano pelea
    # con el ``state("zoomed")`` que la ventana programa en after_idle.
    os.environ["BC_CAJA_WINDOW_SIZE"] = f"{args.width}x{args.height}"

    with tempfile.TemporaryDirectory(prefix="bc-caja-rc12-") as directory:
        controller = build_cash_day_controller(Path(directory) / "bc_caja.sqlite3")
        seed(controller)
        apply_revisions(controller)
        root = ctk.CTk()
        root.withdraw()
        window = abrir_caja_diaria(root, controller=controller)
        window.attributes("-topmost", True)

        def settle(ciclos: int = 4) -> None:
            for _ in range(ciclos):
                window.after(120)
                window.update_idletasks()
                window.update()

        # CTkTabview.set() programa un ``after(100)`` que descarta las pestañas no
        # seleccionadas. Hay que dejar vencer el de la pestaña inicial antes de
        # cambiar a Pedidos, o ese temporizador viejo la borra apenas se dibuja.
        settle()
        for child in window.winfo_children():
            if isinstance(child, ctk.CTkTabview):
                child.set("Pedidos")
                break
        window.lift()
        window.focus_force()
        # El overlay de chips se posiciona en after_idle: dejar respirar el loop.
        settle()
        if args.dialogo:
            seleccionar_primer_pedido(window)
            settle()
            invocar_boton(window, "Corregir estado")
            settle()
        x, y = window.winfo_rootx(), window.winfo_rooty()
        width, height = window.winfo_width(), window.winfo_height()
        ImageGrab.grab((x, y, x + width, y + height)).save(args.output)
        window.attributes("-topmost", False)
        controller.service.repository.close()
        window.destroy()
        root.destroy()
    print(f"BC_CAJA_RC12_CAPTURE_OK {args.output} {args.width}x{args.height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
