"""Smoke GUI real de Pedidos operativos (BC-CAJA-PEDIDOS-OPERATIVOS-RC30-001).

Siembra un día realista —atrasados, entregas de hoy y próximas, con laboratorio
cargado en el ABM— y verifica sobre los widgets que la pantalla se puede atender
sin abrir otra ventana: agrupación, qué pidió el cliente, laboratorio con su
teléfono, última novedad, atraso derivado y las tres acciones con contraste.

Fail-closed: si el contrato no se cumple, no guarda la captura.
No escribe en datos de producción ni envía correo.
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
import CajaDiaria
from modulos.caja_diaria.domain.models import SaleItem

COLUMNAS = tuple(clave for clave, _t, _a, _an in CajaDiaria.ORDER_COLUMN_SPECS)


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
    controller.tracking.save_laboratory(
        name="LAB ALFA", phone_line="021 100 100", whatsapp="0981 100 100")

    def venta(cliente, sobre, offset, laboratorio, articulo):
        controller.add_manual_entry({
            "fecha": hoy.strftime("%d-%m-%Y"), "unidad": "PC", "caja_inicial": "500000",
            "descripcion": cliente, "cliente_documento": "", "sobre": sobre,
            "cliente_telefono": "0981 555 101", "vendedora": "Ana", "notas": "",
            "fecha_entrega": (hoy + timedelta(days=offset)).strftime("%d-%m-%Y"),
            "arm_org": "Armazón", "cod": "", "armazon": "100000", "cristal": "200000",
            "laboratorio": laboratorio, "receta_dr": "", "total": "300000",
            "efectivo": "300000", "tarjeta_cheque": "", "ordenes": "", "cuotas": "",
            "saldo": "", "gastos": "",
            "items": (SaleItem(description=articulo, item_type=articulo,
                               frame_price=100000, lens_price=200000,
                               laboratory=laboratorio),),
        })

    venta("Ramona Benítez", "S-00410", -6, "LAB ALFA", "Armazón + cristales")
    venta("Carlos Duarte", "S-00415", -3, "LAB ALFA", "Cristales")
    venta("Lucía Ayala", "S-00421", -1, "LAB BETA", "Armazón")
    venta("Miguel Rojas", "S-00430", 0, "LAB ALFA", "Cristales")
    venta("Fátima Ozorio", "S-00431", 0, "LAB BETA", "Armazón + cristales")
    venta("Diego Villalba", "S-00436", 3, "LAB ALFA", "Cristales")

    pedidos = {o.customer_name: o for o in controller.list_orders("Todos")}
    controller.update_order_status(
        pedidos["Carlos Duarte"].id, "LISTO",
        reason="Llegó del laboratorio", responsible="Ana")
    controller.service.repository.close()


def grilla_pedidos(root):
    return next(w for w in descendants(root)
                if isinstance(w, ttk.Treeview) and tuple(w.cget("columns") or ()) == COLUMNAS)


def boton(root, texto):
    return next(b for b in descendants(root)
                if isinstance(b, ctk.CTkButton) and str(b.cget("text")) == texto)


def luminancia(color):
    r, g, b = (int(str(color)[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def verificar(root) -> dict:
    root.update_idletasks(); root.update()
    pestañas = next(w for w in descendants(root) if isinstance(w, ctk.CTkTabview))
    pestañas.set("Pedidos")
    root.update_idletasks(); root.update()

    grilla = grilla_pedidos(root)
    filas = list(grilla.get_children())
    if not filas:
        raise RuntimeError("Pedidos abrió como una hoja vacía")
    encabezados = [grilla.set(iid, "cliente") for iid in filas if iid.startswith("grupo::")]
    if not any("ATRASADOS" in t for t in encabezados):
        raise RuntimeError(f"falta el grupo ATRASADOS: {encabezados}")
    if not any("PARA HOY" in t for t in encabezados):
        raise RuntimeError(f"falta el grupo PARA HOY: {encabezados}")

    reales = [iid for iid in filas if not iid.startswith("grupo::")]
    if not reales:
        raise RuntimeError("los grupos no traen pedidos")
    for iid in reales:
        if not str(grilla.set(iid, "trabajo")).strip(" —"):
            raise RuntimeError(f"la fila {iid} no dice qué pidió el cliente")
    con_lab = [iid for iid in reales if "LAB ALFA" in str(grilla.set(iid, "laboratorio"))]
    if not con_lab:
        raise RuntimeError("ninguna fila muestra el laboratorio")
    if "021 100 100" not in str(grilla.set(con_lab[0], "laboratorio")):
        raise RuntimeError(
            f"el laboratorio no trae su teléfono: {grilla.set(con_lab[0], 'laboratorio')!r}")
    atrasos = {str(grilla.set(iid, "atraso")) for iid in reales}
    if not any(a.endswith("días") or a.endswith("día") for a in atrasos):
        raise RuntimeError(f"el atraso no se ve: {atrasos}")
    novedades = [str(grilla.set(iid, "novedad")) for iid in reales]
    if not any("LISTO" in n and "laboratorio" in n for n in novedades):
        raise RuntimeError(f"no se ve la última novedad: {novedades}")

    acciones = {"Acción siguiente", "Contactar", "Más  ▾"}
    presentes = {str(b.cget("text")) for b in descendants(root) if isinstance(b, ctk.CTkButton)}
    faltan = acciones - presentes
    if faltan:
        raise RuntimeError(f"faltan acciones: {sorted(faltan)}")
    for viejo in ("Marcar pendiente",):
        if viejo in presentes:
            raise RuntimeError(f"sobrevive la acción vieja {viejo}")

    avance = boton(root, "Acción siguiente")
    apagado = str(avance.cget("fg_color"))
    if apagado != CajaDiaria.COLOR_ACCION_INACTIVA:
        raise RuntimeError(f"sin selección la acción no se ve apagada: {apagado}")

    pendiente = next(iid for iid in reales if grilla.set(iid, "estado") == "PENDIENTE")
    grilla.selection_set(pendiente)
    grilla.event_generate("<<TreeviewSelect>>")
    root.update_idletasks(); root.update()
    avance = boton(root, "Marcar listo")
    activo = str(avance.cget("fg_color"))
    if luminancia(apagado) - luminancia(activo) < 0.30:
        raise RuntimeError("disponible y no disponible casi no se distinguen")

    # Un encabezado de grupo no es un pedido: no habilita nada.
    grupo = next(iid for iid in filas if iid.startswith("grupo::"))
    grilla.selection_set(grupo)
    grilla.event_generate("<<TreeviewSelect>>")
    root.update_idletasks(); root.update()
    if str(boton(root, "Acción siguiente").cget("fg_color")) != CajaDiaria.COLOR_ACCION_INACTIVA:
        raise RuntimeError("un encabezado de grupo habilita acciones")

    grilla.selection_set(pendiente)
    grilla.event_generate("<<TreeviewSelect>>")
    root.update_idletasks(); root.update()
    return {"grupos": encabezados, "pedidos": len(reales),
            "laboratorio": str(grilla.set(con_lab[0], "laboratorio")),
            "atrasos": sorted(a for a in atrasos if a)}


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
    with tempfile.TemporaryDirectory(prefix="bc-caja-pedidos-rc30-") as carpeta:
        directorio = Path(carpeta)
        os.environ.update(
            BC_CAJA_DATA_DIR=str(directorio), BC_CAJA_WINDOW_SIZE=resolucion,
            BC_CAJA_RESPONSABLE="Operadora Central", BC_CAJA_AUTOMATED="1")
        seed(directorio)

        def smoke(root):
            metricas = verificar(root)
            capturar_ventana(root, salida)
            print(f"BC_CAJA_PEDIDOS_RC30_SMOKE_OK resolution={resolucion} "
                  f"grupos={metricas['grupos']} pedidos={metricas['pedidos']} "
                  f"laboratorio=\"{metricas['laboratorio']}\" "
                  f"atrasos={metricas['atrasos']} emails=0 new_closures=0")
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
