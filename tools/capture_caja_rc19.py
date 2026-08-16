"""Smoke GUI real RC.19: vista de seguimiento Pilar / laboratorios.

Siembra el caso operativo (15 trabajos del viernes, 14 recibidos, varios
laboratorios y atrasos), abre la ventana real, entra en Seguimiento y verifica
sobre los widgets que la operadora ve lo que necesita para actuar.
No escribe en datos de produccion ni envia correo.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

import customtkinter as ctk
from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bc_caja
import CajaDiaria
from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def seed(directory: Path) -> None:
    from modulos.caja_diaria.bootstrap import build_cash_day_controller

    hoy = date.today()
    controller = build_cash_day_controller(directory / "bc_caja.sqlite3")
    controller.admin.open_from_count(
        hoy.strftime("%d-%m-%Y"), "PC", {100_000: 5}, "Operadora Central", "gui-open",
    )
    tracking = controller.tracking
    lab_a = tracking.save_laboratory(
        name="LAB CENTRAL", phone_line="021 111 222", whatsapp="0981 111 222",
    )
    lab_b = tracking.save_laboratory(
        name="LAB OPTICA SUR", phone_line="021 333 444", whatsapp="0982 333 444",
    )
    tracking.save_laboratory(name="LAB ANTIGUO", phone_line="021 999", active=False)

    lote = tracking.register_pilar_batch(
        [
            {"envelope": f"S-{numero:03d}", "customer_name": f"Cliente operativo {numero:02d}"}
            for numero in range(1, 16)
        ],
        consultation_date=hoy, created_by="Nidia",
    )
    # Asuncion recibio 14 de 15: uno queda pendiente a proposito.
    tracking.receive_batch_in_asuncion([work.id for work in lote[:14]], responsible="Ana")

    ayer = hoy - timedelta(days=1)
    for work, laboratorio in zip(lote[:4], (lab_a, lab_a, lab_a, lab_b)):
        tracking.send_to_laboratory(
            work.id, laboratorio.id, expected_date=ayer, expected_time="15:00",
            responsible="Ana",
        )
    for work in lote[4:7]:
        tracking.send_to_laboratory(
            work.id, lab_b.id, expected_date=hoy + timedelta(days=1),
            expected_time="15:30", responsible="Carla",
        )
    tracking.register_contact(
        lote[0].id, operator="Ana", result="Lab confirmo salida 14:30",
        recorded_at=datetime.combine(hoy, time(13, 12), tzinfo=BUSINESS_TIMEZONE),
    )
    tracking.confirm_for_next_day(
        lote[3].id, operator="Carla", next_expected_date=hoy + timedelta(days=1),
        next_expected_time="15:30", result="Lab confirma envio manana",
        recorded_at=datetime.combine(hoy, time(16, 5), tzinfo=BUSINESS_TIMEZONE),
    )
    for work in lote[7:10]:
        tracking.send_to_laboratory(
            work.id, lab_a.id, expected_date=hoy, expected_time="15:00", responsible="Ana",
        )
        tracking.receive_from_laboratory(work.id, responsible="Ana")
    controller.service.repository.close()


def verificar(root) -> dict:
    # Primer render antes de sondear: sin esto los widgets de la pestana no
    # estan realizados y la sonda lee etiquetas vacias.
    root.update_idletasks()
    root.update()
    seguimiento = next(
        boton for boton in descendants(root)
        if isinstance(boton, ctk.CTkButton) and "Seguimiento" in str(boton.cget("text"))
    )
    seguimiento.invoke()
    root.update_idletasks()
    root.update()

    visibles = [w for w in descendants(root) if w.winfo_ismapped()]
    textos = {str(w.cget("text")) for w in visibles if isinstance(w, ctk.CTkLabel)}

    recepcion = next(
        (texto for texto in textos if texto.startswith("Enviados:")), "",
    )
    if "Enviados: 15" not in recepcion or "Recibidos: 14" not in recepcion \
            or "Falta recibir: 1" not in recepcion:
        raise RuntimeError(f"progreso de recepcion incorrecto: {recepcion!r}")

    alerta = next((texto for texto in textos if "contactar laboratorios" in texto), "")
    if not alerta:
        raise RuntimeError("la alerta de atrasados no se muestra")

    agrupacion = next((texto for texto in textos if "atrasado" in texto and "☎" in texto), "")
    if "LAB CENTRAL" not in agrupacion:
        raise RuntimeError(f"agrupacion por laboratorio ausente: {agrupacion!r}")
    if "021 111 222" not in agrupacion or "0981 111 222" not in agrupacion:
        raise RuntimeError("la agrupacion no expone linea y WhatsApp distintos")

    # La columna "sobre" tambien existe en movimientos e historial: la grilla
    # de seguimiento se identifica por sus columnas propias.
    grillas = [
        w for w in descendants(root)
        if w.winfo_class() == "Treeview"
        and {"whatsapp", "novedad"} <= {str(c) for c in w.cget("columns")}
    ]
    if not grillas:
        raise RuntimeError("la grilla de seguimiento no existe")
    grilla = grillas[0]
    filas = grilla.get_children()
    if not filas:
        raise RuntimeError("la grilla de seguimiento esta vacia")
    columnas = [str(columna) for columna in grilla.cget("columns")]
    for requerida in ("sobre", "cliente", "estado", "laboratorio", "esperado", "novedad"):
        if requerida not in columnas:
            raise RuntimeError(f"falta la columna {requerida}")

    primera = {clave: str(grilla.set(filas[0], clave)) for clave in columnas}
    if primera["estado"] != "ATRASADO":
        raise RuntimeError(f"las excepciones no se ordenan primero: {primera['estado']}")
    if not primera["linea"] or not primera["whatsapp"]:
        raise RuntimeError("la fila atrasada no muestra los telefonos del laboratorio")
    if primera["linea"] == primera["whatsapp"]:
        raise RuntimeError("linea y WhatsApp no deberian coincidir")

    estados = [str(grilla.set(fila, "estado")) for fila in filas]
    if "CONFIRMADO_PARA_MAÑANA" not in estados:
        raise RuntimeError(f"falta el estado confirmado: {sorted(set(estados))}")
    novedades = [str(grilla.set(fila, "novedad")) for fila in filas]
    if not any("Lab confirmo salida 14:30" in texto for texto in novedades):
        raise RuntimeError("la ultima novedad no llega a la grilla")

    atrasados = sum(1 for estado in estados if estado == "ATRASADO")
    return {
        "filas": len(filas),
        "atrasados": atrasados,
        "recepcion": recepcion,
        "alerta": alerta,
        "estados": sorted(set(estados)),
    }


def main() -> int:
    salida = Path(sys.argv[1])
    resolucion = sys.argv[2] if len(sys.argv) > 2 else "1920x1080"
    ancho, alto = (int(valor) for valor in resolucion.split("x"))
    sys.argv = [sys.argv[0]]
    salida.parent.mkdir(parents=True, exist_ok=True)
    original = ctk.CTk.mainloop
    with tempfile.TemporaryDirectory(prefix="bc-caja-rc19-") as carpeta:
        directorio = Path(carpeta)
        os.environ.update(
            BC_CAJA_DATA_DIR=str(directorio), BC_CAJA_WINDOW_SIZE=resolucion,
            BC_CAJA_RESPONSABLE="Operadora Central", BC_CAJA_AUTOMATED="1",
        )
        seed(directorio)

        def smoke(root):
            metricas = verificar(root)
            root.attributes("-topmost", True)
            root.update()
            ImageGrab.grab((0, 0, ancho, alto)).save(salida)
            print(
                f"BC_CAJA_RC19_VISUAL_SMOKE_OK resolution={resolucion} "
                f"filas={metricas['filas']} atrasados={metricas['atrasados']} "
                f"recepcion=\"{metricas['recepcion']}\" alerta=\"{metricas['alerta']}\" "
                f"estados={metricas['estados']} emails=0 new_closures=0"
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
