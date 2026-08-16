"""Smoke GUI real RC.18 a 1920x1080 (ViewSonic 24"): jerarquia del resumen de caja.

Verifica sobre la ventana real que los importes principales se dibujan mas
grandes que los secundarios, que el resumen quedo agrupado en dos bloques y que
el macro-layout no desborda. No escribe en datos de produccion: usa un
directorio temporal y no dispara cierres ni correos.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import customtkinter as ctk
from gui_capture import capturar_ventana

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bc_caja
import CajaDiaria


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def seed(directory: Path) -> None:
    from modulos.caja_diaria.bootstrap import build_cash_day_controller
    from modulos.caja_diaria.domain.models import CashEntry, SaleItem

    hoy = date.today().strftime("%d-%m-%Y")
    controller = build_cash_day_controller(directory / "bc_caja.sqlite3")
    controller.admin.open_from_count(hoy, "PC", {100_000: 5}, "Operadora Central", "gui-open")
    dia = controller.service.get_by_date_and_unit(hoy, "PC")
    base = datetime.now(timezone.utc).replace(hour=11, minute=0, second=0, microsecond=0)
    for indice in range(1, 9):
        items = (SaleItem(description=f"Armazon modelo {indice:02d}", code=f"ARM-{indice:03d}",
                          frame_price=180_000),)
        total = sum(item.subtotal for item in items)
        controller.service.add_entry(dia.id, CashEntry(
            description=f"Cliente operativo {indice:02d}", envelope=f"S-{indice:03d}",
            customer_phone=f"0981 000 {indice:03d}", saleswoman=("Ana", "Belen", "Carla")[indice % 3],
            cash=total if indice % 3 else 0,
            card_check=0 if indice % 3 else total,
            items=items, created_at=base + timedelta(minutes=indice * 9),
        ))
    controller.service.add_entry(dia.id, CashEntry(
        description="Compra de insumos", expenses=90_000, outflow_type="GASTO",
        observations="Control interno", created_at=base + timedelta(hours=4),
    ))
    controller.service.add_entry(dia.id, CashEntry(
        description="Administracion", withdrawal=250_000,
        outflow_type="ENTREGA_ADMINISTRACION", observations="Entrega registrada",
        created_at=base + timedelta(hours=4, minutes=15),
    ))
    controller.service.repository.close()


def tamano_fuente(widget) -> int:
    return int(widget.cget("font").cget("size"))


def verificar(root) -> dict:
    root.update_idletasks()
    root.update()
    # El resumen se puebla con ABRIR / CONSULTAR. La caja ya fue abierta por el
    # seed, de modo que esta invocacion solo consulta: no abre ni cierra nada.
    consultar = next(
        w for w in descendants(root)
        if isinstance(w, ctk.CTkButton) and str(w.cget("text")) == "ABRIR / CONSULTAR"
    )
    consultar.invoke()
    root.update_idletasks()
    root.update()
    visibles = [w for w in descendants(root) if w.winfo_ismapped()]
    # "Efectivo" tambien rotula un campo de la seccion PAGO: la sonda se limita
    # a la cabecera para medir el resumen y no otro widget homonimo.
    rotulo = next(
        w for w in visibles
        if isinstance(w, ctk.CTkLabel) and str(w.cget("text")) == "RESUMEN DE CAJA"
    )
    cabecera = rotulo.master
    etiquetas = [w for w in descendants(cabecera) if isinstance(w, ctk.CTkLabel)]
    titulos_principales = {titulo for _c, titulo, _color in CajaDiaria.KPI_PRINCIPALES}
    titulos_secundarios = {titulo for _c, titulo, _color in CajaDiaria.KPI_SECUNDARIOS}

    def valores(titulos):
        encontrados = {}
        for etiqueta in etiquetas:
            texto = str(etiqueta.cget("text"))
            if texto not in titulos:
                continue
            hermanos = etiqueta.master.winfo_children()
            valor = hermanos[hermanos.index(etiqueta) + 1]
            encontrados[texto] = valor
        return encontrados

    principales = valores(titulos_principales)
    secundarios = valores(titulos_secundarios)
    if set(principales) != titulos_principales or set(secundarios) != titulos_secundarios:
        raise RuntimeError(
            f"resumen incompleto: principales={sorted(principales)} secundarios={sorted(secundarios)}"
        )
    tam_principal = {tamano_fuente(w) for w in principales.values()}
    tam_secundario = {tamano_fuente(w) for w in secundarios.values()}
    if len(tam_principal) != 1 or len(tam_secundario) != 1:
        raise RuntimeError(f"tamanos inconsistentes: {tam_principal} / {tam_secundario}")
    principal, secundario = tam_principal.pop(), tam_secundario.pop()
    if principal <= secundario:
        raise RuntimeError(f"sin jerarquia: principal={principal} secundario={secundario}")

    padres_principales = {w.master.master for w in principales.values()}
    padres_secundarios = {w.master.master for w in secundarios.values()}
    if len(padres_principales) != 1 or len(padres_secundarios) != 1:
        raise RuntimeError("el resumen no quedo agrupado en dos bloques")
    if padres_principales & padres_secundarios:
        raise RuntimeError("principales y secundarios comparten bloque")

    importes = {t: str(w.cget("text")) for t, w in {**principales, **secundarios}.items()}
    if any(texto in ("", "—") for texto in importes.values()):
        raise RuntimeError(f"importes sin calcular: {importes}")

    marcos = [w for w in visibles if isinstance(w, ctk.CTkFrame)]
    bajo_cabecera = cabecera.winfo_rooty() + cabecera.winfo_height()
    for widget in principales.values():
        if widget.winfo_rooty() + widget.winfo_height() > bajo_cabecera:
            raise RuntimeError("un importe principal desborda la cabecera")
    return {
        "principal": principal,
        "secundario": secundario,
        "cabecera_alto": cabecera.winfo_height(),
        "importes": importes,
        "marcos_visibles": len(marcos),
    }


def main() -> int:
    salida = Path(sys.argv[1])
    resolucion = sys.argv[2] if len(sys.argv) > 2 else "1920x1080"
    ancho, alto = (int(valor) for valor in resolucion.split("x"))
    sys.argv = [sys.argv[0]]
    salida.parent.mkdir(parents=True, exist_ok=True)
    original = ctk.CTk.mainloop
    with tempfile.TemporaryDirectory(prefix="bc-caja-rc18-") as carpeta:
        directorio = Path(carpeta)
        os.environ.update(
            BC_CAJA_DATA_DIR=str(directorio), BC_CAJA_WINDOW_SIZE=resolucion,
            BC_CAJA_RESPONSABLE="Operadora Central", BC_CAJA_AUTOMATED="1",
        )
        seed(directorio)

        def smoke(root):
            metricas = verificar(root)
            capturar_ventana(root, salida)
            print(
                f"BC_CAJA_RC18_VISUAL_SMOKE_OK resolution={resolucion} "
                f"kpi_principal={metricas['principal']} kpi_secundario={metricas['secundario']} "
                f"cabecera_alto={metricas['cabecera_alto']} "
                f"importes={metricas['importes']} emails=0 new_closures=0"
            )
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
