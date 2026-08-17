"""Smoke GUI real RC.28: la alerta de Pedidos abre exactamente sus pedidos.

Reproduce el caso de produccion —dos pedidos vencidos y ninguno para hoy—,
pulsa la alerta `Trabajos 2` de la cabecera y verifica sobre los widgets que la
grilla abre con esos dos y no en blanco.

No escribe en datos de produccion ni envia correo.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import customtkinter as ctk
from tkinter import ttk
from gui_capture import capturar_ventana

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bc_caja
from modulos.caja_diaria.domain.models import Order, OrderOrigin, OrderStatus


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def seed(directory: Path) -> None:
    from modulos.caja_diaria.bootstrap import build_cash_day_controller

    hoy = date.today()
    controller = build_cash_day_controller(directory / "bc_caja.sqlite3")
    controller.admin.open_from_count(
        hoy.strftime("%d-%m-%Y"), "PC", {100_000: 5}, "Operadora Central", "gui-open")
    repositorio = controller.service.repository

    def pedido(envelope, entrega, estado=OrderStatus.PENDING, branch="PC"):
        repositorio.save_order(Order(
            delivery_date=entrega, branch=branch, customer_name=f"Cliente {envelope}",
            saleswoman="Ana", envelope=envelope, origin=OrderOrigin.CASH_REGISTER,
            customer_phone="0981 555 111", status=estado))

    # El caso exacto reportado: dos vencidos, nada para hoy.
    pedido("2999", hoy - timedelta(days=3))
    pedido("0239", hoy - timedelta(days=2))
    # Ruido que NO debe aparecer al abrir desde la alerta.
    pedido("FUTURO", hoy + timedelta(days=6))
    pedido("YA-ENTREGADO", hoy, estado=OrderStatus.DELIVERED)
    pedido("OTRO-LOCAL", hoy - timedelta(days=1), branch="PILAR")
    repositorio.close()


#: La grilla de Movimientos tambien tiene una columna `sobre`, asi que
#: identificar por ahi devolvia la tabla equivocada —y vacia—. La de Pedidos se
#: reconoce por su juego completo de columnas.
COLUMNAS_PEDIDOS = ("entrega", "cliente", "telefono", "documento", "sobre",
                    "sucursal", "vendedora", "origen", "estado")


def filas_visibles(root):
    grilla = next(
        w for w in descendants(root)
        if isinstance(w, ttk.Treeview)
        and tuple(w.cget("columns") or ()) == COLUMNAS_PEDIDOS
    )
    return grilla, [grilla.set(iid, "sobre") for iid in grilla.get_children()]


def verificar(root, capturar_caja=None) -> dict:
    root.update_idletasks()
    root.update()

    alerta = next(
        b for b in descendants(root)
        if isinstance(b, ctk.CTkButton) and str(b.cget("text")).startswith("⚠ Trabajos")
    )
    texto_alerta = str(alerta.cget("text"))
    cantidad = int(texto_alerta.split()[-1])
    if cantidad != 2:
        raise RuntimeError(f"la alerta no dice 2: {texto_alerta!r}")
    if capturar_caja is not None:
        capturar_caja(root)

    alerta.invoke()                       # el clic tiene que abrir esos dos
    root.update_idletasks()
    root.update()

    grilla, sobres = filas_visibles(root)
    if len(sobres) != cantidad:
        raise RuntimeError(
            f"la alerta anuncia {cantidad} y la grilla abre {len(sobres)}: {sobres}")
    if set(sobres) != {"2999", "0239"}:
        raise RuntimeError(f"abrio otros pedidos: {sobres}")

    visibles = {
        str(w.cget("text")) for w in descendants(root)
        if isinstance(w, (ctk.CTkLabel, ctk.CTkButton)) and w.winfo_ismapped()
    }
    contexto = next((t for t in visibles if t.startswith("Mostrando: ")), "")
    if not contexto:
        raise RuntimeError("no se ve el contexto del filtro aplicado")
    if f"({cantidad})" not in contexto:
        raise RuntimeError(f"el contexto no dice la cantidad: {contexto!r}")
    if "Ver todos" not in visibles:
        raise RuntimeError("no se ofrece Ver todos")

    # `Ver todos` saca el filtro y muestra el resto.
    ver_todos = next(
        b for b in descendants(root)
        if isinstance(b, ctk.CTkButton) and str(b.cget("text")) == "Ver todos")
    ver_todos.invoke()
    root.update_idletasks()
    root.update()
    _g, todos = filas_visibles(root)
    if len(todos) <= cantidad:
        raise RuntimeError(f"Ver todos no quito el filtro: {todos}")
    if "OTRO-LOCAL" not in todos:
        raise RuntimeError("Ver todos deberia mostrar tambien el otro local")

    # Y la entrada normal vuelve a lo que requiere atencion, no en blanco.
    requieren = next(
        b for b in descendants(root)
        if isinstance(b, ctk.CTkButton)
        and str(b.cget("text")).startswith("Requieren atenci"))
    requieren.invoke()
    root.update_idletasks()
    root.update()
    _g, normal = filas_visibles(root)
    if set(normal) != {"2999", "0239"}:
        raise RuntimeError(f"la entrada normal no muestra los pendientes: {normal}")

    return {"alerta": texto_alerta, "abre": sobres, "contexto": contexto,
            "ver_todos": len(todos), "entrada_normal": normal}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    salida = Path(sys.argv[1])
    resolucion = sys.argv[2] if len(sys.argv) > 2 else "1920x1080"
    sys.argv = [sys.argv[0]]
    salida.parent.mkdir(parents=True, exist_ok=True)
    original = ctk.CTk.mainloop
    with tempfile.TemporaryDirectory(prefix="bc-caja-rc28-") as carpeta:
        directorio = Path(carpeta)
        os.environ.update(
            BC_CAJA_DATA_DIR=str(directorio), BC_CAJA_WINDOW_SIZE=resolucion,
            BC_CAJA_RESPONSABLE="Operadora Central", BC_CAJA_AUTOMATED="1")
        seed(directorio)
        salida_caja = salida.with_name(salida.stem + "-caja" + salida.suffix)

        def smoke(root):
            metricas = verificar(
                root, capturar_caja=lambda v: capturar_ventana(v, salida_caja))
            capturar_ventana(root, salida)
            print(
                f"BC_CAJA_RC28_VISUAL_SMOKE_OK resolution={resolucion} "
                f"alerta=\"{metricas['alerta']}\" abre={metricas['abre']} "
                f"contexto=\"{metricas['contexto']}\" "
                f"ver_todos={metricas['ver_todos']} "
                f"entrada_normal={metricas['entrada_normal']} "
                f"emails=0 new_closures=0")
            root.destroy()

        ctk.CTk.mainloop = smoke
        try:
            bc_caja.main()
        finally:
            ctk.CTk.mainloop = original
            for clave in ("BC_CAJA_DATA_DIR", "BC_CAJA_WINDOW_SIZE",
                          "BC_CAJA_RESPONSABLE", "BC_CAJA_AUTOMATED"):
                os.environ.pop(clave, None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
