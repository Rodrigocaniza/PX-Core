"""Smoke GUI real RC.20: alta de lote desde Pilar y ABM de laboratorios.

Siembra una consulta de Pilar con 15 trabajos ya cargados en Caja, abre la
ventana real y ejercita los dos dialogos: selecciona el lote y lo crea, y da de
alta, edita y desactiva un laboratorio. Verifica sobre los widgets, no sobre el
servicio. No escribe en datos de produccion ni envia correo.
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

HOY = date.today()


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def seed(directory: Path) -> None:
    from modulos.caja_diaria.bootstrap import build_cash_day_controller
    from modulos.caja_diaria.domain.models import CashEntry, SaleItem

    controller = build_cash_day_controller(directory / "bc_caja.sqlite3")
    controller.admin.open_from_count(
        HOY.strftime("%d-%m-%Y"), "PC", {100_000: 5}, "Operadora Central", "gui-open",
    )
    # Consulta de Pilar: las ventas ya existen en Caja y generan sus pedidos.
    pilar = controller.service.open_day(business_date=HOY, unit="Pilar", opening_cash=0)
    for numero in range(1, 16):
        controller.service.add_entry(pilar.id, CashEntry(
            description=f"Cliente Pilar {numero:02d}", envelope=f"P-{numero:03d}",
            saleswoman="Nidia", delivery_date=HOY + timedelta(days=7),
            customer_phone=f"0981 700 {numero:03d}", cash=180_000,
            observations="Armazon + cristales",
            items=(SaleItem(description="Armazon", frame_price=180_000),),
        ))
    controller.tracking.save_laboratory(
        name="LAB CENTRAL", phone_line="021 111 222", whatsapp="0981 111 222",
    )
    controller.service.repository.close()


def capturar(root, dialogo, destino: Path) -> None:
    """Captura la ventana de BC Caja con el dialogo encima.

    Delega en `capturar_ventana`, que dibuja la ventana en memoria en vez de
    leer la pantalla. Se conserva la verificacion de contencion para que el
    dialogo no quede fuera del encuadre.
    """
    root.lift()
    dialogo.lift()
    dialogo.attributes("-topmost", True)
    for _ in range(4):
        root.update_idletasks()
        root.update()

    ventana = (
        root.winfo_rootx(), root.winfo_rooty(),
        root.winfo_rootx() + root.winfo_width(),
        root.winfo_rooty() + root.winfo_height(),
    )
    caja = (
        dialogo.winfo_rootx(), dialogo.winfo_rooty(),
        dialogo.winfo_rootx() + dialogo.winfo_width(),
        dialogo.winfo_rooty() + dialogo.winfo_height(),
    )
    if not (caja[0] >= ventana[0] and caja[1] >= ventana[1]
            and caja[2] <= ventana[2] and caja[3] <= ventana[3]):
        raise RuntimeError(
            f"el dialogo {caja} se sale de la ventana {ventana}: la captura "
            "incluiria contenido ajeno"
        )
    capturar_ventana(root, destino)


def dialogo_visible(root):
    return next(
        w for w in root.winfo_children()
        if isinstance(w, ctk.CTkToplevel) and w.winfo_exists()
    )


def boton(contenedor, texto):
    return next(
        w for w in descendants(contenedor)
        if isinstance(w, ctk.CTkButton) and str(w.cget("text")).strip() == texto
    )


def grilla_con(contenedor, columnas):
    return next(
        w for w in descendants(contenedor)
        if w.winfo_class() == "Treeview"
        and set(columnas) <= {str(c) for c in w.cget("columns")}
    )


def verificar_envio(root) -> dict:
    boton(root, "+ Nuevo envío desde Pilar").invoke()
    root.update_idletasks()
    root.update()
    dialogo = dialogo_visible(root)
    dialogo.update_idletasks()
    dialogo.update()

    candidatos = grilla_con(dialogo, ("marca", "sobre", "cliente", "tipo"))
    filas = candidatos.get_children()
    if len(filas) != 15:
        raise RuntimeError(f"se esperaban 15 candidatos de Pilar, hay {len(filas)}")

    etiquetas = [
        str(w.cget("text")) for w in descendants(dialogo) if isinstance(w, ctk.CTkLabel)
    ]
    resumen = next((t for t in etiquetas if "trabajos encontrados" in t), "")
    if "15 trabajos encontrados" not in resumen or "0 seleccionados" not in resumen:
        raise RuntimeError(f"resumen inicial incorrecto: {resumen!r}")

    crear = boton(dialogo, "Crear envío")
    if str(crear.cget("state")) != "disabled":
        raise RuntimeError("Crear envío deberia estar deshabilitado sin seleccion")

    boton(dialogo, "Seleccionar todos").invoke()
    dialogo.update_idletasks()
    dialogo.update()
    etiquetas = [
        str(w.cget("text")) for w in descendants(dialogo) if isinstance(w, ctk.CTkLabel)
    ]
    resumen = next((t for t in etiquetas if "trabajos encontrados" in t), "")
    if "15 seleccionados" not in resumen:
        raise RuntimeError(f"seleccionar todos no marco las 15 filas: {resumen!r}")
    if str(candidatos.set(filas[0], "marca")) != "✓":
        raise RuntimeError("la fila no muestra su marca de seleccion")

    crear = boton(dialogo, "Crear envío (15)")
    if str(crear.cget("state")) != "normal":
        raise RuntimeError("Crear envío deberia habilitarse con seleccion")

    boton(dialogo, "Quitar selección").invoke()
    dialogo.update_idletasks()
    dialogo.update()
    if str(candidatos.set(filas[0], "marca")) != "":
        raise RuntimeError("quitar seleccion no limpio las marcas")

    # Seleccion parcial mediante clic real sobre tres filas: se ejercita el
    # mismo binding <Button-1> que usa la operadora, no el estado interno.
    for indice in (0, 3, 9):
        caja = candidatos.bbox(filas[indice])
        if not caja:
            raise RuntimeError("la fila candidata no esta renderizada")
        candidatos.event_generate(
            "<Button-1>", x=60, y=caja[1] + caja[3] // 2,
        )
    dialogo.update_idletasks()
    dialogo.update()
    marcadas = [f for f in filas if str(candidatos.set(f, "marca")) == "✓"]
    if len(marcadas) != 3:
        raise RuntimeError(f"la seleccion parcial marco {len(marcadas)} filas, se esperaban 3")

    dialogo.attributes("-topmost", True)
    dialogo.update()
    return {"dialogo": dialogo, "candidatos": len(filas), "parciales": len(marcadas)}


def verificar_abm(root) -> dict:
    boton(root, "Laboratorios").invoke()
    root.update_idletasks()
    root.update()
    dialogo = dialogo_visible(root)
    dialogo.update_idletasks()
    dialogo.update()

    grilla = grilla_con(dialogo, ("nombre", "linea", "whatsapp", "estado"))
    if len(grilla.get_children()) != 1:
        raise RuntimeError("deberia existir el laboratorio sembrado")

    campos = [w for w in descendants(dialogo) if isinstance(w, ctk.CTkEntry)]
    if len(campos) < 3:
        raise RuntimeError("el formulario de laboratorio esta incompleto")
    nombre, linea, whatsapp = campos[0], campos[1], campos[2]
    for campo, valor in (
        (nombre, "LAB NUEVO RC20"), (linea, "021 555 666"), (whatsapp, "0985 777 888"),
    ):
        campo.delete(0, "end")
        campo.insert(0, valor)
    boton(dialogo, "Agregar laboratorio").invoke()
    dialogo.update_idletasks()
    dialogo.update()

    filas = grilla.get_children()
    if len(filas) != 2:
        raise RuntimeError(f"el alta no se reflejo en la grilla: {len(filas)} filas")
    nuevo = next(
        f for f in filas if str(grilla.set(f, "nombre")) == "LAB NUEVO RC20"
    )
    if str(grilla.set(nuevo, "linea")) == str(grilla.set(nuevo, "whatsapp")):
        raise RuntimeError("linea y WhatsApp no deberian coincidir")
    if str(grilla.set(nuevo, "estado")) != "ACTIVO":
        raise RuntimeError("el laboratorio nuevo deberia nacer activo")

    # Edicion: seleccionar, cambiar el nombre y guardar.
    grilla.selection_set(nuevo)
    dialogo.update_idletasks()
    dialogo.update()
    campos[0].delete(0, "end")
    campos[0].insert(0, "LAB RC20 EDITADO")
    boton(dialogo, "Guardar cambios").invoke()
    dialogo.update_idletasks()
    dialogo.update()
    if str(grilla.set(nuevo, "nombre")) != "LAB RC20 EDITADO":
        raise RuntimeError("la edicion de nombre no se reflejo")
    if str(grilla.set(nuevo, "linea")) != "021 555 666":
        raise RuntimeError("la edicion perdio el telefono de linea")

    # Baja logica.
    grilla.selection_set(nuevo)
    dialogo.update_idletasks()
    dialogo.update()
    boton(dialogo, "Desactivar").invoke()
    dialogo.update_idletasks()
    dialogo.update()
    if str(grilla.set(nuevo, "estado")) != "INACTIVO":
        raise RuntimeError("la desactivacion no se reflejo")
    if len(grilla.get_children()) != 2:
        raise RuntimeError("desactivar no debe borrar el laboratorio")

    dialogo.attributes("-topmost", True)
    dialogo.update()
    return {"dialogo": dialogo, "laboratorios": len(grilla.get_children())}


def main() -> int:
    salida = Path(sys.argv[1])
    resolucion = sys.argv[2] if len(sys.argv) > 2 else "1920x1080"
    ancho, alto = (int(valor) for valor in resolucion.split("x"))
    sys.argv = [sys.argv[0]]
    salida.parent.mkdir(parents=True, exist_ok=True)
    original = ctk.CTk.mainloop
    with tempfile.TemporaryDirectory(prefix="bc-caja-rc20-") as carpeta:
        directorio = Path(carpeta)
        os.environ.update(
            BC_CAJA_DATA_DIR=str(directorio), BC_CAJA_WINDOW_SIZE=resolucion,
            BC_CAJA_RESPONSABLE="Nidia", BC_CAJA_AUTOMATED="1",
        )
        seed(directorio)

        def smoke(root):
            root.update_idletasks()
            root.update()
            boton(root, "🚚  Seguimiento").invoke()
            root.update_idletasks()
            root.update()

            envio = verificar_envio(root)
            capturar(root, envio["dialogo"], salida)
            envio["dialogo"].destroy()
            root.update()

            abm = verificar_abm(root)
            capturar(
                root, abm["dialogo"],
                salida.with_name(salida.name.replace("envio", "laboratorios")),
            )
            abm["dialogo"].destroy()
            root.update()

            print(
                f"BC_CAJA_RC20_VISUAL_SMOKE_OK resolution={resolucion} "
                f"candidatos={envio['candidatos']} seleccion_parcial={envio['parciales']} "
                f"laboratorios={abm['laboratorios']} emails=0 new_closures=0"
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
