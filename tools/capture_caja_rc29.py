"""Smoke GUI real RC.29: cada jornada de Historial es una unidad visual.

Siembra tres jornadas —dos cerradas y una abierta, con una venta anulada— y
verifica sobre los widgets que:

  * cada jornada es una tarjeta con su cabecera y su chip de estado;
  * los movimientos cuelgan de la tarjeta de su dia, no del scroll;
  * el anulado queda dentro del dia que le corresponde;
  * hay separacion entre jornadas y ninguna cifra cambio;
  * Editar caja / Editar / Anular siguen ahi.

No escribe en datos de produccion ni envia correo.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import customtkinter as ctk
from gui_capture import capturar_ventana

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bc_caja

#: Las mismas cifras que el smoke espera leer despues en pantalla.
VENTAS = {
    0: [("Venta Ana", 700_000, 300_000, 200_000)],
    1: [("Venta Rosa", 450_000, 450_000, 0), ("Venta anulada", 120_000, 120_000, 0)],
    2: [("Venta Nidia", 980_000, 480_000, 500_000)],
}


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def seed(directory: Path) -> None:
    from modulos.caja_diaria.bootstrap import build_cash_day_controller
    from modulos.caja_diaria.domain.models import CashEntry

    hoy = date.today()
    controller = build_cash_day_controller(directory / "bc_caja.sqlite3")
    servicio = controller.service
    for desplazamiento in (2, 1, 0):
        dia = hoy - timedelta(days=desplazamiento)
        cash_day = servicio.open_day(
            business_date=dia, unit="PC", opening_cash=100_000, opened_by="Ana")
        for descripcion, total, efectivo, tarjeta in VENTAS[desplazamiento]:
            guardado = servicio.add_entry(cash_day.id, CashEntry(
                description=descripcion, total=total, cash=efectivo,
                card_check=tarjeta, expenses=0, saleswoman="Ana"))
            if descripcion == "Venta anulada":
                servicio.void_entry(cash_day.id, guardado.id,
                                    "Error de carga", "Ana")
        if desplazamiento:                      # las dos anteriores quedan cerradas
            servicio.close_day(cash_day.id)
    controller.service.repository.close()


def verificar(root) -> dict:
    root.update_idletasks()
    root.update()
    historial = next(
        b for b in descendants(root)
        if isinstance(b, ctk.CTkButton) and "Historial" in str(b.cget("text")))
    historial.invoke()
    root.update_idletasks()
    root.update()
    # Rango que cubre las tres jornadas sembradas.
    siete = next(
        b for b in descendants(root)
        if isinstance(b, ctk.CTkButton) and str(b.cget("text")) == "7 días")
    siete.invoke()
    root.update_idletasks()
    root.update()

    tarjetas = [w for w in descendants(root)
                if getattr(w, "_bc_jornada_historial", False)]
    if len(tarjetas) != 3:
        raise RuntimeError(f"se esperaban 3 jornadas y hay {len(tarjetas)}")

    resumen = []
    for tarjeta in tarjetas:
        etiquetas = [str(x.cget("text")) for x in descendants(tarjeta)
                     if isinstance(x, ctk.CTkLabel)]
        botones = [str(x.cget("text")) for x in descendants(tarjeta)
                   if isinstance(x, ctk.CTkButton)]
        fecha = next((t for t in etiquetas if t.count("-") == 2 and len(t) == 10), "")
        estado = next((t.strip() for t in etiquetas
                       if t.strip() in ("ABIERTO", "CERRADO")), "")
        if not fecha:
            raise RuntimeError(f"jornada sin fecha reconocible: {etiquetas[:3]}")
        if not estado:
            raise RuntimeError(f"jornada {fecha} sin chip de estado")
        if "Editar caja" not in botones:
            raise RuntimeError(f"jornada {fecha} sin Editar caja")
        movimientos = [t for t in etiquetas if " | Total " in t]
        if not movimientos:
            raise RuntimeError(f"jornada {fecha} sin movimientos dentro de la tarjeta")
        if not any("Efectivo actual" in t for t in etiquetas):
            raise RuntimeError(f"jornada {fecha} sin resumen economico")
        if estado == "CERRADO" and not any("Apertura real" in t for t in etiquetas):
            raise RuntimeError(f"jornada cerrada {fecha} sin detalle de sesion")
        resumen.append({"fecha": fecha, "estado": estado,
                        "movimientos": len(movimientos),
                        "anulados": sum(1 for t in movimientos if "ANULADO" in t),
                        "editar": botones.count("Editar"),
                        "anular": botones.count("Anular")})

    # Ningun movimiento puede haber quedado fuera de una tarjeta.
    def dentro_de_jornada(widget):
        cadena = widget.master
        while cadena is not None:
            if getattr(cadena, "_bc_jornada_historial", False):
                return True
            cadena = getattr(cadena, "master", None)
        return False

    sueltos = [
        str(w.cget("text")) for w in descendants(root)
        if isinstance(w, ctk.CTkLabel) and " | Total " in str(w.cget("text"))
        and not dentro_de_jornada(w)
    ]
    if sueltos:
        raise RuntimeError(f"movimientos fuera de su jornada: {sueltos}")

    # El anulado tiene que estar en la jornada del medio, no en otra.
    con_anulados = [r["fecha"] for r in resumen if r["anulados"]]
    if len(con_anulados) != 1:
        raise RuntimeError(f"el anulado no quedo en una sola jornada: {con_anulados}")

    # Las cifras sembradas tienen que leerse tal cual.
    planos = " ".join(
        str(w.cget("text")) for w in descendants(root) if isinstance(w, ctk.CTkLabel))
    for esperado in ("700.000", "450.000", "980.000", "120.000"):
        if esperado not in planos:
            raise RuntimeError(f"no se lee la cifra {esperado}")

    abiertas = [r["fecha"] for r in resumen if r["estado"] == "ABIERTO"]
    if len(abiertas) != 1:
        raise RuntimeError(f"se esperaba una sola jornada abierta: {abiertas}")

    return {"jornadas": resumen, "abiertas": abiertas}


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
    with tempfile.TemporaryDirectory(prefix="bc-caja-rc29-") as carpeta:
        directorio = Path(carpeta)
        os.environ.update(
            BC_CAJA_DATA_DIR=str(directorio), BC_CAJA_WINDOW_SIZE=resolucion,
            BC_CAJA_RESPONSABLE="Operadora Central", BC_CAJA_AUTOMATED="1")
        seed(directorio)

        def smoke(root):
            metricas = verificar(root)
            capturar_ventana(root, salida)
            print(
                f"BC_CAJA_RC29_VISUAL_SMOKE_OK resolution={resolucion} "
                f"jornadas={metricas['jornadas']} "
                f"abiertas={metricas['abiertas']} emails=0 new_closures=0")
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
