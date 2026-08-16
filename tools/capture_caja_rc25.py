"""Smoke GUI real RC.25: recepcion con discrepancias y alerta principal.

Siembra la recepcion de los mismos 15 TEST (12 recibidos, 2 NO LLEGO, 1 que no
estaba en la lista), abre la ventana real y verifica sobre los widgets:

  * que la pantalla principal de Caja muestre la alerta de la sucursal;
  * que el clic lleve a Seguimiento con el grupo ya filtrado;
  * que la conciliacion se lea en una linea;
  * que las discrepancias se lean en la propia fila;
  * que sigan siendo tres botones principales, sin overlays.

No escribe en datos de produccion ni envia correo.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

import customtkinter as ctk
from gui_capture import capturar_ventana

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bc_caja
import CajaDiaria
from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE, Order, OrderOrigin


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def textos_visibles(root):
    return {
        str(w.cget("text")) for w in descendants(root)
        if isinstance(w, (ctk.CTkLabel, ctk.CTkButton)) and w.winfo_ismapped()
    }


def seed(directory: Path) -> None:
    from modulos.caja_diaria.bootstrap import build_cash_day_controller

    hoy, ayer = date.today(), date.today() - timedelta(days=1)
    manana = hoy + timedelta(days=1)
    controller = build_cash_day_controller(directory / "bc_caja.sqlite3")
    controller.admin.open_from_count(
        hoy.strftime("%d-%m-%Y"), "PC", {100_000: 5}, "Operadora Central", "gui-open",
    )
    tracking, repositorio = controller.tracking, controller.service.repository
    labs = {
        nombre: tracking.save_laboratory(name=nombre, phone_line=f"021 {i}00 {i}00",
                                         whatsapp=f"098{i} {i}00 {i}00")
        for i, nombre in enumerate(("LAB ALFA", "LAB BETA", "LAB GAMMA"), start=1)
    }

    def pedido(numero, prefijo="TEST"):
        item = Order(
            delivery_date=hoy + timedelta(days=7), branch="PILAR",
            customer_name=f"Cliente TEST {numero:02d}", saleswoman="Nidia (TEST)",
            envelope=f"{prefijo}-{numero:03d}", origin=OrderOrigin.WORKSHOP,
            # RC26: el telefono ya existe en el pedido; Seguimiento lo muestra.
            customer_phone=f"0981 {numero:03d} {numero:03d}",
            observations="Armazon + cristales",
            created_at=datetime.combine(ayer, time(14, 0), tzinfo=BUSINESS_TIMEZONE))
        repositorio.save_order(item)
        return item

    lote = tracking.create_pilar_shipment(
        [pedido(n).id for n in range(1, 16)], operator="Nidia (TEST)")
    works = lote["works"]

    # 12 recibidos, 2 NO LLEGO, 1 sin revisar todavia.
    tracking.apply_next_action([w.id for w in works[:12]], responsible="Ana")
    tracking.mark_batch_not_arrived([w.id for w in works[12:14]], responsible="Ana")

    # Un fisico que no figuraba: reutiliza su pedido, no se recarga nada.
    extra = pedido(1, prefijo="EXTRA")
    agregado = tracking.add_unlisted_reception(
        extra.id, responsible="Ana", shipment_id=lote["shipment"].id)

    # Reparto entre tres laboratorios; ALFA vence ayer para dejar atrasados.
    listos = [w.id for w in works[:12]] + [agregado.id]
    for nombre, grupo, vence in (
        ("LAB ALFA", listos[:5], ayer),
        ("LAB BETA", listos[5:9], manana),
        ("LAB GAMMA", listos[9:], manana),
    ):
        tracking.apply_next_action(
            grupo, responsible="Ana", laboratory_id=labs[nombre].id,
            expected_date=vence, expected_time="15:00")

    # Novedades legibles: hoy, manana y la ultima respuesta del laboratorio.
    tracking.confirm_for_next_day(
        listos[0], operator="Ana", next_expected_date=hoy, next_expected_time="17:30",
        result="Lab confirmó salida 14:30",
        recorded_at=datetime.combine(hoy, time(9, 30), tzinfo=BUSINESS_TIMEZONE))
    tracking.confirm_for_next_day(
        listos[1], operator="Ana", next_expected_date=manana, next_expected_time="15:00",
        channel="WHATSAPP", result="",
        recorded_at=datetime.combine(hoy, time(9, 31), tzinfo=BUSINESS_TIMEZONE))
    repositorio.close()


def verificar(root, capturar_caja=None) -> dict:
    root.update_idletasks()
    root.update()

    # --- Mision 3: la alerta esta en la pantalla principal de Caja ---------
    en_caja = textos_visibles(root)
    alerta_principal = next(
        (t for t in en_caja if t.startswith("⚠") and "clic para ver" in t), "")
    if not alerta_principal:
        raise RuntimeError(
            "la pantalla principal de Caja no muestra la alerta de la sucursal")
    if "por recibir" not in alerta_principal and "atrasado" not in alerta_principal:
        raise RuntimeError(f"la alerta no dice que requiere atencion: {alerta_principal!r}")
    if not any(caracter.isdigit() for caracter in alerta_principal):
        raise RuntimeError(f"la alerta no muestra cantidad: {alerta_principal!r}")

    boton_alerta = next(
        b for b in descendants(root)
        if isinstance(b, ctk.CTkButton) and str(b.cget("text")) == alerta_principal
    )
    # Evidencia de la Mision 3: la alerta se ve en la pantalla en la que la
    # operadora ya esta, antes de entrar a ninguna otra pestaña.
    if capturar_caja is not None:
        capturar_caja(root)

    boton_alerta.invoke()                     # el clic lleva a Seguimiento
    root.update_idletasks()
    root.update()

    # El clic tiene que abrir exactamente los trabajos que originaron la
    # alerta: ni mas, ni "algo parecido" que haya que volver a filtrar.
    cantidad_alerta = int(
        next(p for p in alerta_principal.split() if p.isdigit()))
    filas_tras_clic = [
        w for w in descendants(root) if getattr(w, "_bc_fila_seguimiento", False)
    ]
    if len(filas_tras_clic) != cantidad_alerta:
        raise RuntimeError(
            f"la alerta anuncia {cantidad_alerta} y el clic abre "
            f"{len(filas_tras_clic)} trabajos")

    # Vuelta a la vista normal de la sucursal para revisar la recepcion.
    boton_activos = next(
        b for b in descendants(root)
        if isinstance(b, ctk.CTkButton) and str(b.cget("text")) == "Activos"
    )
    boton_activos.invoke()
    root.update_idletasks()
    root.update()

    visibles = textos_visibles(root)

    # --- Mision 2: conciliacion en una linea -------------------------------
    conciliacion = next((t for t in visibles if t.startswith("Declarados ")), "")
    esperado = "Declarados 15 · Recibidos 12 · No llegó 2 · Extra 1"
    if conciliacion != esperado:
        raise RuntimeError(f"conciliacion {conciliacion!r}, se esperaba {esperado!r}")
    for accion in ("No llegó", "+ No estaba en lista"):
        if accion not in visibles:
            raise RuntimeError(f"la recepcion no ofrece {accion!r} de forma directa")

    # --- Agrupacion operativa: secciones, no seis pantallas ----------------
    grupos_esperados = ("Por recibir", "Para laboratorio", "En laboratorio",
                        "Para enviar a Pilar", "Por recibir en Pilar", "Completados")
    secciones = sorted(
        t for t in visibles
        if any(t.strip().startswith(g + "  ·") for g in grupos_esperados)
    )
    if not secciones:
        raise RuntimeError("la lista no muestra los grupos operativos")

    # --- Discrepancias legibles en la propia fila --------------------------
    filas = [w for w in descendants(root) if getattr(w, "_bc_fila_seguimiento", False)]
    if not filas:
        raise RuntimeError("la grilla de seguimiento esta vacia")
    chips_por_fila = []
    for fila in filas:
        etiquetas = [
            str(x.cget("text")).strip() for x in descendants(fila)
            if isinstance(x, ctk.CTkLabel)
        ]
        chips_por_fila.append(etiquetas)
    planos = [t for fila in chips_por_fila for t in fila]
    if "NO LLEGÓ" not in planos:
        raise RuntimeError("NO LLEGÓ no se lee en la fila")
    # NO LLEGO conserva el origen: no reemplaza la etapa fisica.
    con_no_llego = [f for f in chips_por_fila if "NO LLEGÓ" in f]
    if not all("ENVIADO DESDE PILAR" in f for f in con_no_llego):
        raise RuntimeError("NO LLEGÓ borro la etapa fisica en vez de anteponerse")

    # --- RC26: el telefono se lee en la fila -------------------------------
    if "Teléfono" not in visibles:
        raise RuntimeError("la tabla no muestra la columna Teléfono")
    if not any(t.startswith("0981 ") for t in planos):
        raise RuntimeError("la columna Teléfono no muestra numeros reales")

    # --- Observaciones operativas legibles sin abrir el detalle ------------
    observaciones = [t for t in planos if "Hoy 17:30" in t or "Mañana 15:00" in t]
    if not observaciones:
        raise RuntimeError("las novedades de hoy/mañana no se leen en la lista")
    if not any("Lab confirmó salida 14:30" in t for t in planos):
        raise RuntimeError("la ultima respuesta del laboratorio no se lee en la lista")
    if not any(t.startswith("☎") or t.startswith("✆") for t in planos):
        raise RuntimeError("el medio de contacto no se distingue en la lista")

    # --- Sin overlays: todo chip cuelga de su fila -------------------------
    etapas = {"ENVIADO DESDE PILAR", "RECIBIDO EN ASUNCIÓN", "EN LABORATORIO",
              "RECIBIDO DEL LABORATORIO", "ENVIADO A PILAR", "RECIBIDO EN PILAR"}
    condiciones = {"ATRASADO", "CONFIRMADO PARA MAÑANA", "NO LLEGÓ", "NO ESTABA EN LISTA"}
    huerfanos = []
    for chip in descendants(root):
        if not isinstance(chip, ctk.CTkLabel):
            continue
        if str(chip.cget("text")).strip() not in (etapas | condiciones):
            continue
        cadena, dentro = chip.master, False
        while cadena is not None:
            if getattr(cadena, "_bc_fila_seguimiento", False):
                dentro = True
                break
            cadena = getattr(cadena, "master", None)
        if not dentro:
            huerfanos.append(str(chip.cget("text")).strip())
    if huerfanos:
        raise RuntimeError(f"chips flotando fuera de su fila: {huerfanos}")

    # --- Maximo tres botones principales -----------------------------------
    principales = [
        b for b in descendants(root)
        if isinstance(b, ctk.CTkButton) and b.winfo_ismapped()
        and str(b.cget("text")) in ("Novedad", "Más  ▾")
        or (isinstance(b, ctk.CTkButton) and b.winfo_ismapped()
            and str(b.cget("text")).startswith(("Acción siguiente", "Recibir", "Enviar",
                                                "Contactar", "Resolver", "Sin acción")))
    ]
    if len(principales) != 3:
        raise RuntimeError(
            f"la barra principal tiene {len(principales)} botones: "
            f"{[str(b.cget('text')) for b in principales]}")

    # --- RC26: un atrasado sigue ofreciendo su transicion fisica -----------
    #
    # Se marca una fila ATRASADA y se lee la barra: el boton principal tiene
    # que ofrecer "Recibir del laboratorio" —no quedarse en "Contactar"— y la
    # sugerencia de contacto tiene que estar a la vista sin bloquear nada.
    fila_atrasada = next(
        (f for f in filas
         if any(str(x.cget("text")).strip() == "ATRASADO"
                for x in descendants(f) if isinstance(x, ctk.CTkLabel))), None)
    if fila_atrasada is None:
        raise RuntimeError("el escenario no dejo ninguna fila atrasada")
    tilde = next(x for x in descendants(fila_atrasada)
                 if isinstance(x, ctk.CTkCheckBox))
    tilde.toggle()
    root.update_idletasks()
    root.update()
    botones_barra = {
        str(b.cget("text")) for b in descendants(root)
        if isinstance(b, ctk.CTkButton) and b.winfo_ismapped()
    }
    principal_atrasado = next(
        (t for t in botones_barra if t.startswith("Recibir del laboratorio")), "")
    if not principal_atrasado:
        raise RuntimeError(
            f"un trabajo ATRASADO no ofrece su transicion fisica: {sorted(botones_barra)}")
    if "Contactar laboratorio" not in botones_barra:
        raise RuntimeError("no se sugiere contactar al laboratorio atrasado")
    tilde.toggle()
    root.update_idletasks()
    root.update()

    return {
        "atrasado_ofrece": principal_atrasado,
        "alerta": alerta_principal,
        "conciliacion": conciliacion,
        "grupos": secciones,
        "filas": len(filas),
        "botones_principales": [str(b.cget("text")) for b in principales],
    }


def main() -> int:
    # La consola de Windows es cp1252 y la evidencia lleva ⚠, · y ñ. Sin esto
    # el smoke "falla" por no poder imprimir su propio resultado.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    salida = Path(sys.argv[1])
    resolucion = sys.argv[2] if len(sys.argv) > 2 else "1920x1080"
    sys.argv = [sys.argv[0]]
    salida.parent.mkdir(parents=True, exist_ok=True)
    original = ctk.CTk.mainloop
    with tempfile.TemporaryDirectory(prefix="bc-caja-rc25-") as carpeta:
        directorio = Path(carpeta)
        os.environ.update(
            BC_CAJA_DATA_DIR=str(directorio), BC_CAJA_WINDOW_SIZE=resolucion,
            BC_CAJA_RESPONSABLE="Operadora Central", BC_CAJA_AUTOMATED="1",
        )
        seed(directorio)

        salida_caja = salida.with_name(salida.stem + "-caja-principal" + salida.suffix)

        def smoke(root):
            metricas = verificar(
                root, capturar_caja=lambda ventana: capturar_ventana(ventana, salida_caja))
            capturar_ventana(root, salida)
            print(
                f"BC_CAJA_RC25_VISUAL_SMOKE_OK resolution={resolucion} "
                f"filas={metricas['filas']} "
                f"alerta=\"{metricas['alerta']}\" "
                f"conciliacion=\"{metricas['conciliacion']}\" "
                f"atrasado_ofrece=\"{metricas['atrasado_ofrece']}\" "
                f"grupos={metricas['grupos']} "
                f"botones={metricas['botones_principales']} "
                f"emails=0 new_closures=0"
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
