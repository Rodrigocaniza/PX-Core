"""Caja diaria de la óptica: UI legacy adaptada a Core + SQLite.

La ventana conserva el flujo CustomTkinter conocido. Toda operación nueva de
UI usa ``modulos.caja_diaria``; las funciones TXT permanecen temporalmente
solo como compatibilidad y caracterización, sin doble escritura.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import customtkinter as ctk
from openpyxl import load_workbook
from tkinter import filedialog, messagebox, simpledialog

from ImportadorExcel import (
    COLOR_BORDE,
    COLOR_PANEL,
    COLOR_PANEL_SECUNDARIO,
    COLOR_PRIMARIO,
    COLOR_PRIMARIO_HOVER,
    COLOR_ROJO,
    COLOR_TEXTO,
    COLOR_TEXTO_SUAVE,
    COLOR_VERDE,
    celda_vacia,
    normalizar,
    parsear_fecha,
    parsear_monto,
    texto_seguro,
)
from datos import guardar_datos, leer_datos
from Movimientos import UNIDADES, formatear_monto
from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.ui.controller import friendly_error


RUTA_CAJA_DIARIA = "Datos/caja_diaria.txt"
RUTA_ARQUEO = "Datos/arqueo_caja.txt"
UNIDAD_POR_DEFECTO = "PC"
DESCRIPCION_CAJA_INICIAL = "CAJA INICIAL"

# Billetes y monedas en guaraníes. Ajustar si cambia el circulante.
DENOMINACIONES = [
    100000, 50000, 20000, 10000, 5000, 2000, 1000, 500, 100, 50,
]

CAMPOS = [
    "fecha", "unidad", "descripcion", "sobre", "arm_org", "cod",
    "armazon", "cristal", "receta_dr", "total", "efectivo",
    "tarjeta_cheque", "ordenes", "cuotas", "saldo", "gastos", "origen",
]


# ------------------------------------------------------------------
# Compatibilidad legacy TXT (no usada por el flujo normal de UI)
# ------------------------------------------------------------------

def _texto_archivo(valor):
    """Evita romper el formato TXT delimitado por barras."""
    return texto_seguro(valor).replace("|", "/")


def registro_a_linea(registro):
    return "|".join(_texto_archivo(registro.get(campo, "")) for campo in CAMPOS)


def linea_a_registro(linea):
    partes = linea.split("|")
    partes += [""] * (len(CAMPOS) - len(partes))
    return dict(zip(CAMPOS, partes))


def registros_del_dia(fecha, unidad):
    registros = []
    for linea in leer_datos(RUTA_CAJA_DIARIA):
        registro = linea_a_registro(linea)
        if registro["fecha"] == fecha and registro["unidad"] == unidad:
            registros.append(registro)
    return registros


def agregar_registros(nuevos):
    lineas = leer_datos(RUTA_CAJA_DIARIA)
    lineas.extend(registro_a_linea(registro) for registro in nuevos)
    guardar_datos(RUTA_CAJA_DIARIA, lineas)


def eliminar_dia(fecha, unidad):
    lineas = leer_datos(RUTA_CAJA_DIARIA)
    restantes = [
        linea for linea in lineas
        if not (
            linea_a_registro(linea)["fecha"] == fecha
            and linea_a_registro(linea)["unidad"] == unidad
        )
    ]
    eliminados = len(lineas) - len(restantes)
    guardar_datos(RUTA_CAJA_DIARIA, restantes)
    return eliminados


# ------------------------------------------------------------------
# Importación desde Excel (una hoja = un día)
# ------------------------------------------------------------------

def _num_o_cero(valor, errores, hoja_titulo, fila_num, nombre_campo):
    if celda_vacia(valor):
        return 0
    try:
        return parsear_monto(valor, permitir_cero=True)
    except ValueError as exc:
        errores.append(
            f"Hoja '{hoja_titulo}' fila {fila_num}: "
            f"{nombre_campo} inválido ('{valor}') - {exc}."
        )
        return 0


def _valor_celda(fila, indice):
    return fila[indice].value if indice < len(fila) else None


def analizar_hoja(hoja, unidad, fecha_por_defecto=None):
    """Devuelve (registros, caja_inicial, totales_hoja, errores) de una hoja."""

    registros = []
    errores = []
    caja_inicial = None

    fila_encabezado = None
    for numero in range(1, min(hoja.max_row, 6) + 1):
        valores = {normalizar(celda.value) for celda in hoja[numero]}
        if "total" in valores and "efectivo" in valores:
            fila_encabezado = numero
            break

    if fila_encabezado is None:
        errores.append(
            f"Hoja '{hoja.title}': no se encontró la fila de encabezados "
            "(TOTAL / Efectivo). Se omite la hoja."
        )
        return [], None, None, errores

    fecha_celda = hoja.cell(row=1, column=1).value
    try:
        fecha, _ = parsear_fecha(fecha_celda)
    except ValueError:
        if fecha_por_defecto is None:
            errores.append(
                f"Hoja '{hoja.title}': la fecha en A1 ('{fecha_celda}') es "
                "inválida y no hay fecha de respaldo. Se omite la hoja."
            )
            return [], None, None, errores
        fecha = fecha_por_defecto
        errores.append(
            f"Hoja '{hoja.title}': la fecha en A1 ('{fecha_celda}') es "
            f"inválida. Se usó {fecha} por posición de la hoja. "
            "Revisala manualmente."
        )

    suma_total = suma_efectivo_ventas = suma_tarjeta = suma_gastos = 0

    for numero in range(fila_encabezado + 1, hoja.max_row + 1):
        fila = hoja[numero]

        if all(celda_vacia(celda.value) for celda in fila):
            continue

        descripcion = texto_seguro(_valor_celda(fila, 0))
        sobre = texto_seguro(_valor_celda(fila, 1))
        arm_org = texto_seguro(_valor_celda(fila, 2))
        cod = texto_seguro(_valor_celda(fila, 3))
        armazon = texto_seguro(_valor_celda(fila, 4))
        cristal = texto_seguro(_valor_celda(fila, 5))
        receta_dr = texto_seguro(_valor_celda(fila, 6))
        total_val = _valor_celda(fila, 7)
        efectivo_val = _valor_celda(fila, 8)
        tarjeta_val = _valor_celda(fila, 9)
        ordenes = texto_seguro(_valor_celda(fila, 10))
        cuotas = texto_seguro(_valor_celda(fila, 11))
        saldo = texto_seguro(_valor_celda(fila, 12))
        gastos_val = _valor_celda(fila, 13)

        if normalizar(descripcion) == normalizar(DESCRIPCION_CAJA_INICIAL):
            monto = _num_o_cero(
                efectivo_val, errores, hoja.title, numero, "caja inicial"
            )
            if caja_inicial is not None:
                errores.append(
                    f"Hoja '{hoja.title}' fila {numero}: hay más de una "
                    "fila de CAJA INICIAL, se usó la última encontrada."
                )
            caja_inicial = monto
            continue

        if normalizar(descripcion) in ("totales", ""):
            # Fila de totales o vacía: no se importa como movimiento,
            # más abajo se recalcula y se compara contra lo declarado.
            continue

        total = _num_o_cero(total_val, errores, hoja.title, numero, "TOTAL")
        efectivo = _num_o_cero(
            efectivo_val, errores, hoja.title, numero, "Efectivo"
        )
        tarjeta = _num_o_cero(
            tarjeta_val, errores, hoja.title, numero, "Tarj./Cheq."
        )
        gastos = _num_o_cero(gastos_val, errores, hoja.title, numero, "Gastos")

        campos_con_datos = (
            armazon, cristal, ordenes, cuotas, saldo,
            total, efectivo, tarjeta, gastos,
        )
        if all(celda_vacia(v) for v in campos_con_datos):
            # Fila puramente informativa (ej. "Salida 19:30hs").
            continue

        registros.append({
            "fecha": fecha,
            "unidad": unidad,
            "descripcion": descripcion,
            "sobre": sobre,
            "arm_org": arm_org,
            "cod": cod,
            "armazon": armazon,
            "cristal": cristal,
            "receta_dr": receta_dr,
            "total": total,
            "efectivo": efectivo,
            "tarjeta_cheque": tarjeta,
            "ordenes": ordenes,
            "cuotas": cuotas,
            "saldo": saldo,
            "gastos": gastos,
            "origen": "excel",
        })

        suma_total += total
        suma_efectivo_ventas += efectivo
        suma_tarjeta += tarjeta
        suma_gastos += gastos

    if caja_inicial is None:
        errores.append(
            f"Hoja '{hoja.title}': no se encontró la fila CAJA INICIAL. "
            "Se asumió 0."
        )
        caja_inicial = 0

    totales_hoja = {
        "total": suma_total,
        "efectivo": suma_efectivo_ventas,
        "tarjeta_cheque": suma_tarjeta,
        "gastos": suma_gastos,
        "efectivo_final": caja_inicial + suma_efectivo_ventas - suma_gastos,
    }

    return registros, caja_inicial, totales_hoja, errores


def _fecha_siguiente(fecha_texto):
    try:
        fecha_dt = datetime.strptime(fecha_texto, "%d-%m-%Y")
    except (TypeError, ValueError):
        return None
    return (fecha_dt + timedelta(days=1)).strftime("%d-%m-%Y")


def analizar_archivo(ruta, unidad=UNIDAD_POR_DEFECTO):
    libro = load_workbook(ruta, data_only=True)
    resultado = {
        "por_dia": {},
        "errores": [],
        "duplicados": [],
    }

    existentes = {
        (registro["fecha"], registro["unidad"])
        for linea in leer_datos(RUTA_CAJA_DIARIA)
        for registro in [linea_a_registro(linea)]
    }

    fechas_archivo = set()
    fecha_previa = None

    for hoja in libro.worksheets:
        fecha_respaldo = _fecha_siguiente(fecha_previa) if fecha_previa else None
        registros, caja_inicial, totales, errores = analizar_hoja(
            hoja,
            unidad,
            fecha_por_defecto=fecha_respaldo,
        )
        resultado["errores"].extend(errores)

        if not registros and caja_inicial is None:
            continue

        fecha = registros[0]["fecha"] if registros else fecha_respaldo
        if fecha is None:
            resultado["errores"].append(
                f"Hoja '{hoja.title}': no fue posible determinar la fecha."
            )
            continue

        fecha_previa = fecha

        if fecha in fechas_archivo:
            resultado["duplicados"].append(fecha)
            resultado["errores"].append(
                f"Hoja '{hoja.title}': la fecha {fecha} está repetida "
                "dentro del mismo Excel y fue omitida."
            )
            continue

        fechas_archivo.add(fecha)

        if (fecha, unidad) in existentes:
            resultado["duplicados"].append(fecha)
            continue

        resultado["por_dia"][fecha] = {
            "registros": registros,
            "caja_inicial": caja_inicial,
            "totales": totales,
            "hoja": hoja.title,
            "unidad": unidad,
        }

    return resultado

def aplicar_importacion(resultado):
    nuevos = []
    for fecha, datos in resultado["por_dia"].items():
        nuevos.append({
            "fecha": fecha,
            "unidad": datos.get("unidad", UNIDAD_POR_DEFECTO),
            "descripcion": DESCRIPCION_CAJA_INICIAL,
            "sobre": "", "arm_org": "", "cod": "", "armazon": "",
            "cristal": "", "receta_dr": "",
            "total": "", "efectivo": datos["caja_inicial"],
            "tarjeta_cheque": "", "ordenes": "", "cuotas": "",
            "saldo": "", "gastos": "", "origen": "excel",
        })
        nuevos.extend(datos["registros"])
    agregar_registros(nuevos)
    return len(nuevos)


# ------------------------------------------------------------------
# Cierre del día y arqueo
# ------------------------------------------------------------------

def calcular_cierre(fecha, unidad):
    registros = registros_del_dia(fecha, unidad)
    caja_inicial = 0
    suma_total = suma_efectivo = suma_tarjeta = suma_gastos = 0

    for registro in registros:
        if normalizar(registro["descripcion"]) == normalizar(
            DESCRIPCION_CAJA_INICIAL
        ):
            caja_inicial = int(registro["efectivo"] or 0)
            continue
        suma_total += int(registro["total"] or 0)
        suma_efectivo += int(registro["efectivo"] or 0)
        suma_tarjeta += int(registro["tarjeta_cheque"] or 0)
        suma_gastos += int(registro["gastos"] or 0)

    return {
        "caja_inicial": caja_inicial,
        "total": suma_total,
        "efectivo_ventas": suma_efectivo,
        "tarjeta_cheque": suma_tarjeta,
        "gastos": suma_gastos,
        "efectivo_esperado": caja_inicial + suma_efectivo - suma_gastos,
        "cantidad_registros": len(
            [r for r in registros if normalizar(r["descripcion"])
             != normalizar(DESCRIPCION_CAJA_INICIAL)]
        ),
    }


def registrar_arqueo(fecha, unidad, conteo):
    """Guarda un solo arqueo por fecha y unidad; el nuevo reemplaza al anterior."""

    total_contado = sum(
        denominacion * cantidad for denominacion, cantidad in conteo.items()
    )
    cierre = calcular_cierre(fecha, unidad)
    diferencia = total_contado - cierre["efectivo_esperado"]
    estado = (
        "OK" if diferencia == 0
        else "SOBRA" if diferencia > 0
        else "FALTA"
    )
    detalle = ";".join(
        f"{denominacion}x{cantidad}"
        for denominacion, cantidad in sorted(conteo.items(), reverse=True)
        if cantidad
    )

    linea = "|".join([
        fecha,
        unidad,
        str(total_contado),
        str(cierre["efectivo_esperado"]),
        str(diferencia),
        estado,
        detalle,
    ])

    lineas = []
    for existente in leer_datos(RUTA_ARQUEO):
        partes = existente.split("|")
        if len(partes) >= 2 and partes[0] == fecha and partes[1] == unidad:
            continue
        lineas.append(existente)

    lineas.append(linea)
    guardar_datos(RUTA_ARQUEO, lineas)

    return {
        "total_contado": total_contado,
        "efectivo_esperado": cierre["efectivo_esperado"],
        "diferencia": diferencia,
        "estado": estado,
    }


# TODO (fase 2): una vez validada la importación, generar automáticamente
# en Movimientos.RUTA_MOVIMIENTOS un Ingreso (efectivo + tarjeta/cheque) y
# un Egreso (gastos) por día/unidad, evitando duplicar si ya se generó.


# ------------------------------------------------------------------
# Interfaz gráfica
# ------------------------------------------------------------------

def abrir_caja_diaria(ventana_padre, controller=None):
    """Abre la UI conocida usando Core + SQLite para toda operación nueva."""
    controller = controller or build_cash_day_controller()
    ventana = ctk.CTkToplevel(ventana_padre)
    ventana.title("Caja diaria - Óptica")
    ventana.geometry("880x640")
    ventana.transient(ventana_padre)
    ventana.grab_set()

    pestañas = ctk.CTkTabview(ventana, fg_color=COLOR_PANEL[1])
    pestañas.pack(fill="both", expand=True, padx=16, pady=16)
    tab_importar = pestañas.add("Importar Excel")
    tab_manual = pestañas.add("Cargar manual")
    tab_arqueo = pestañas.add("Arqueo")
    tab_historial = pestañas.add("Historial")

    def mostrar_error(error):
        titulo, detalle = friendly_error(error)
        messagebox.showerror(titulo, detalle, parent=ventana)

    # ---- Importar Excel ----
    estado = {"ruta": ctk.StringVar(), "resultado": None}

    fila_sup = ctk.CTkFrame(tab_importar, fg_color="transparent")
    fila_sup.pack(fill="x", padx=8, pady=8)
    ctk.CTkEntry(
        fila_sup, textvariable=estado["ruta"], placeholder_text="Excel..."
    ).pack(side="left", fill="x", expand=True, padx=(0, 8))

    combo_unidad = ctk.CTkComboBox(fila_sup, values=UNIDADES)
    combo_unidad.set(UNIDAD_POR_DEFECTO)
    combo_unidad.pack(side="left", padx=(0, 8))

    cuadro = ctk.CTkTextbox(tab_importar, fg_color=COLOR_PANEL_SECUNDARIO[1])
    cuadro.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def mostrar(texto):
        cuadro.configure(state="normal")
        cuadro.delete("1.0", "end")
        cuadro.insert("1.0", texto)
        cuadro.configure(state="disabled")

    def resumen_texto(resultado):
        lineas = [f"Días detectados: {len(resultado['por_dia'])}"]
        for fecha, datos in sorted(resultado["por_dia"].items()):
            t = datos["totales"]
            lineas.append(
                f"- {fecha} ({datos['hoja']}): "
                f"{len(datos['registros'])} registros | "
                f"Total {formatear_monto(t['total'])} | "
                f"Efectivo final {formatear_monto(t['efectivo_final'])}"
            )
        if resultado["duplicados"]:
            lineas.append("")
            lineas.append(
                "Ya cargados (se omiten): "
                + ", ".join(sorted(set(resultado["duplicados"])))
            )
        if resultado["errores"]:
            lineas.append("")
            lineas.append("AVISOS / ERRORES:")
            lineas.extend(f"- {e}" for e in resultado["errores"])
        return "\n".join(lineas)

    def elegir():
        ruta = filedialog.askopenfilename(
            parent=ventana, title="Seleccionar caja diaria",
            filetypes=[("Excel", "*.xlsx")],
        )
        if ruta:
            estado["ruta"].set(ruta)
            analizar()

    def analizar():
        ruta = estado["ruta"].get().strip()
        if not ruta:
            messagebox.showwarning(
                "Falta el archivo", "Seleccioná el Excel.", parent=ventana
            )
            return
        try:
            resultado = analizar_archivo(ruta, combo_unidad.get())
        except Exception as exc:
            messagebox.showerror("No se pudo leer", str(exc), parent=ventana)
            return
        estado["resultado"] = resultado
        mostrar(resumen_texto(resultado))
        boton_importar.configure(
            state="normal"
            if resultado["por_dia"] and not resultado["errores"]
            else "disabled"
        )

    def importar():
        resultado = estado["resultado"]
        if not resultado or not resultado["por_dia"]:
            return
        if resultado["errores"]:
            messagebox.showerror(
                "Revisar importación",
                "Corregí los avisos antes de importar. No se guardó ningún dato.",
                parent=ventana,
            )
            return
        if not messagebox.askyesno(
            "Confirmar", f"Se cargarán {len(resultado['por_dia'])} días. "
            "Los datos se guardarán en SQLite. ¿Continuar?",
            parent=ventana,
        ):
            return
        try:
            resumen = controller.import_legacy_analysis(resultado)
        except Exception as exc:
            mostrar_error(exc)
            return
        messagebox.showinfo(
            "Listo",
            f"Se importaron {resumen.entries} registros en {resumen.days} días.",
            parent=ventana,
        )
        boton_importar.configure(state="disabled")

    ctk.CTkButton(
        fila_sup, text="Elegir Excel", command=elegir,
        fg_color=COLOR_PRIMARIO, hover_color=COLOR_PRIMARIO_HOVER,
    ).pack(side="left", padx=(0, 8))
    boton_importar = ctk.CTkButton(
        fila_sup, text="Importar", command=importar, state="disabled",
        fg_color=COLOR_VERDE, hover_color="#12835B",
    )
    boton_importar.pack(side="left")

    # ---- Carga manual ----
    campos_manual = {}
    contenedor = ctk.CTkFrame(tab_manual, fg_color="transparent")
    contenedor.pack(fill="both", expand=True, padx=8, pady=8)

    etiquetas = [
        ("fecha", "Fecha (DD-MM-AAAA)"), ("unidad", "Unidad"),
        ("caja_inicial", "Caja inicial (solo apertura)"),
        ("descripcion", "Descripción/Cliente"), ("sobre", "Sobre"),
        ("arm_org", "Arm/Org"), ("cod", "Cód."), ("armazon", "Armazón"),
        ("cristal", "Cristal"), ("receta_dr", "Receta Dr."),
        ("total", "Total"), ("efectivo", "Efectivo"),
        ("tarjeta_cheque", "Tarj./Cheq."), ("ordenes", "Órdenes"),
        ("cuotas", "Cuotas"), ("saldo", "Saldo"), ("gastos", "Gastos"),
    ]
    for indice, (clave, etiqueta) in enumerate(etiquetas):
        fila = indice // 2
        columna = (indice % 2) * 2
        ctk.CTkLabel(contenedor, text=etiqueta).grid(
            row=fila, column=columna, sticky="w", padx=8, pady=6
        )
        if clave == "unidad":
            campo = ctk.CTkComboBox(contenedor, values=UNIDADES, width=200)
            campo.set(UNIDAD_POR_DEFECTO)
        else:
            campo = ctk.CTkEntry(contenedor, width=200)
        campo.grid(row=fila, column=columna + 1, padx=8, pady=6)
        campos_manual[clave] = campo

    orden_teclado = [clave for clave, _ in etiquetas]
    for indice, clave in enumerate(orden_teclado[:-1]):
        siguiente = orden_teclado[indice + 1]
        campos_manual[clave].bind(
            "<Return>", lambda _event, destino=siguiente: campos_manual[destino].focus_set()
        )

    campos_manual["fecha"].insert(0, date.today().strftime("%d-%m-%Y"))
    estado_edicion = {"entry_id": None, "guardando": False}

    etiqueta_estado = ctk.CTkLabel(
        tab_manual,
        text="Seleccioná una fecha y abrí o consultá la Caja.",
        justify="left",
        text_color=COLOR_TEXTO_SUAVE,
    )
    etiqueta_estado.pack(padx=8, pady=(2, 4), anchor="w")

    def texto_estado(cash_day):
        totales = cash_day.totals()
        cierre = (
            f" | Cierre: {cash_day.closed_at.astimezone().strftime('%d-%m-%Y %H:%M')}"
            if cash_day.closed_at
            else ""
        )
        return (
            f"Caja {cash_day.business_date.strftime('%d-%m-%Y')} / {cash_day.unit} "
            f"— {cash_day.status.value}{cierre}\n"
            f"Inicial: {formatear_monto(cash_day.opening_cash)} | "
            f"Total: {formatear_monto(totales.total)} | "
            f"Efectivo: {formatear_monto(totales.cash)} | "
            f"Tarj./Cheq.: {formatear_monto(totales.card_check)} | "
            f"Gastos: {formatear_monto(totales.expenses)} | "
            f"Efectivo final: {formatear_monto(totales.expected_cash)}"
        )

    def actualizar_estado(cash_day):
        etiqueta_estado.configure(
            text=texto_estado(cash_day),
            text_color=COLOR_VERDE
            if cash_day.status.value == "OPEN"
            else COLOR_TEXTO_SUAVE,
        )

    def abrir_o_consultar():
        try:
            cash_day = controller.open_or_load_day(
                campos_manual["fecha"].get().strip(),
                campos_manual["unidad"].get().strip(),
                campos_manual["caja_inicial"].get().strip(),
            )
        except Exception as exc:
            mostrar_error(exc)
            return
        actualizar_estado(cash_day)

    def cerrar_caja():
        if not messagebox.askyesno(
            "Cerrar Caja",
            "Después del cierre no se podrán cargar ni modificar movimientos. ¿Continuar?",
            parent=ventana,
        ):
            return
        try:
            cash_day = controller.close_day(
                campos_manual["fecha"].get().strip(),
                campos_manual["unidad"].get().strip(),
            )
        except Exception as exc:
            mostrar_error(exc)
            return
        actualizar_estado(cash_day)
        messagebox.showinfo("Caja cerrada", texto_estado(cash_day), parent=ventana)
        if controller.last_warning:
            messagebox.showwarning("Backup pendiente", controller.last_warning, parent=ventana)

    def guardar_manual():
        if estado_edicion["guardando"]:
            return
        estado_edicion["guardando"] = True
        boton_guardar.configure(state="disabled")
        valores = {
            clave: campo.get().strip() for clave, campo in campos_manual.items()
        }
        try:
            if estado_edicion["entry_id"]:
                cash_day, _ = controller.update_manual_entry(
                    estado_edicion["entry_id"], valores
                )
            else:
                cash_day, _ = controller.add_manual_entry(valores)
        except Exception as exc:
            mostrar_error(exc)
            return
        finally:
            estado_edicion["guardando"] = False
            boton_guardar.configure(state="normal")
        actualizar_estado(cash_day)
        mensaje = "Movimiento actualizado." if estado_edicion["entry_id"] else "Registro agregado."
        messagebox.showinfo("Guardado", mensaje, parent=ventana)
        estado_edicion["entry_id"] = None
        boton_guardar.configure(text="Guardar registro")
        for clave, campo in campos_manual.items():
            if clave not in ("fecha", "unidad", "caja_inicial"):
                campo.delete(0, "end")
        campos_manual["descripcion"].focus_set()

    def cancelar_edicion():
        estado_edicion["entry_id"] = None
        boton_guardar.configure(text="Guardar registro")
        for clave, campo in campos_manual.items():
            if clave not in ("fecha", "unidad", "caja_inicial"):
                campo.delete(0, "end")
        campos_manual["descripcion"].focus_set()

    acciones = ctk.CTkFrame(tab_manual, fg_color="transparent")
    acciones.pack(pady=6)
    ctk.CTkButton(
        acciones, text="Abrir / Consultar Caja", command=abrir_o_consultar,
        fg_color=COLOR_PANEL_SECUNDARIO[1], hover_color=COLOR_PRIMARIO_HOVER,
    ).pack(side="left", padx=4)
    boton_guardar = ctk.CTkButton(
        acciones, text="Guardar registro", command=guardar_manual,
        fg_color=COLOR_PRIMARIO, hover_color=COLOR_PRIMARIO_HOVER,
    )
    boton_guardar.pack(side="left", padx=4)
    ctk.CTkButton(
        acciones, text="Cancelar edición", command=cancelar_edicion,
        fg_color=COLOR_PANEL_SECUNDARIO[1], hover_color=COLOR_PRIMARIO_HOVER,
    ).pack(side="left", padx=4)
    ctk.CTkButton(
        acciones, text="Cerrar Caja", command=cerrar_caja,
        fg_color=COLOR_ROJO, hover_color="#B63D49",
    ).pack(side="left", padx=4)

    # ---- Arqueo ----
    superior = ctk.CTkFrame(tab_arqueo, fg_color="transparent")
    superior.pack(fill="x", padx=8, pady=8)
    ctk.CTkLabel(superior, text="Fecha (DD-MM-AAAA)").pack(side="left")
    entrada_fecha = ctk.CTkEntry(superior, width=120)
    entrada_fecha.pack(side="left", padx=8)
    combo_unidad_arqueo = ctk.CTkComboBox(superior, values=UNIDADES, width=140)
    combo_unidad_arqueo.set(UNIDAD_POR_DEFECTO)
    combo_unidad_arqueo.pack(side="left", padx=8)

    grilla = ctk.CTkFrame(tab_arqueo, fg_color="transparent")
    grilla.pack(fill="x", padx=8, pady=8)
    campos_conteo = {}
    for indice, denominacion in enumerate(DENOMINACIONES):
        ctk.CTkLabel(grilla, text=formatear_monto(denominacion)).grid(
            row=indice, column=0, sticky="w", padx=8, pady=4
        )
        campo = ctk.CTkEntry(grilla, width=100, placeholder_text="0")
        campo.grid(row=indice, column=1, padx=8, pady=4)
        campos_conteo[denominacion] = campo

    etiqueta_resultado = ctk.CTkLabel(tab_arqueo, text="", justify="left")
    etiqueta_resultado.pack(padx=8, pady=8, anchor="w")

    def calcular_arqueo():
        fecha = entrada_fecha.get().strip()
        try:
            fecha, _ = parsear_fecha(fecha)
        except ValueError:
            messagebox.showerror(
                "Fecha inválida", "Usá DD-MM-AAAA.", parent=ventana
            )
            return
        conteo = {}
        for denominacion, campo in campos_conteo.items():
            texto = campo.get().strip() or "0"
            try:
                conteo[denominacion] = int(texto)
            except ValueError:
                messagebox.showerror(
                    "Cantidad inválida",
                    f"Revisá la cantidad de {formatear_monto(denominacion)}.",
                    parent=ventana,
                )
                return
        try:
            resultado = controller.record_cash_count(
                fecha, combo_unidad_arqueo.get(), conteo
            )
        except Exception as exc:
            mostrar_error(exc)
            return
        color = {
            "OK": COLOR_VERDE, "SOBRA": COLOR_PRIMARIO, "FALTA": COLOR_ROJO,
        }[resultado.status.value]
        etiqueta_resultado.configure(
            text=(
                f"Contado: {formatear_monto(resultado.counted_total)}\n"
                f"Esperado: {formatear_monto(resultado.expected_total)}\n"
                f"Diferencia: {formatear_monto(resultado.difference)} "
                f"({resultado.status.value})"
            ),
            text_color=color,
        )

    ctk.CTkButton(
        tab_arqueo, text="Calcular y guardar arqueo", command=calcular_arqueo,
        fg_color=COLOR_PRIMARIO, hover_color=COLOR_PRIMARIO_HOVER,
    ).pack(pady=8)

    # ---- Historial / edición / anulación ----
    filtros_historial = ctk.CTkFrame(tab_historial, fg_color="transparent")
    filtros_historial.pack(fill="x", padx=8, pady=8)
    ctk.CTkLabel(filtros_historial, text="Fecha (DD-MM-AAAA)").pack(side="left")
    entrada_historial = ctk.CTkEntry(filtros_historial, width=120)
    entrada_historial.insert(0, date.today().strftime("%d-%m-%Y"))
    entrada_historial.pack(side="left", padx=8)
    unidad_historial = ctk.CTkComboBox(filtros_historial, values=UNIDADES, width=140)
    unidad_historial.set(UNIDAD_POR_DEFECTO)
    unidad_historial.pack(side="left", padx=8)

    resumen_historial = ctk.CTkLabel(
        tab_historial, text="", justify="left", text_color=COLOR_TEXTO_SUAVE
    )
    resumen_historial.pack(fill="x", padx=8, pady=(0, 4), anchor="w")
    lista_historial = ctk.CTkScrollableFrame(tab_historial, fg_color=COLOR_PANEL_SECUNDARIO[1])
    lista_historial.pack(fill="both", expand=True, padx=8, pady=8)

    def cargar_para_editar(cash_day, entry):
        valores = {
            "fecha": cash_day.business_date.strftime("%d-%m-%Y"),
            "unidad": cash_day.unit,
            "caja_inicial": str(cash_day.opening_cash),
            "descripcion": entry.description,
            "sobre": entry.envelope,
            "arm_org": entry.frame_origin,
            "cod": entry.code,
            "armazon": entry.frame,
            "cristal": entry.lens,
            "receta_dr": entry.prescription_doctor,
            "total": "" if entry.total is None else str(entry.total),
            "efectivo": "" if entry.cash is None else str(entry.cash),
            "tarjeta_cheque": "" if entry.card_check is None else str(entry.card_check),
            "ordenes": entry.orders,
            "cuotas": entry.installments,
            "saldo": entry.balance,
            "gastos": "" if entry.expenses is None else str(entry.expenses),
        }
        for clave, valor in valores.items():
            campo = campos_manual[clave]
            if clave == "unidad":
                campo.set(valor)
            else:
                campo.delete(0, "end")
                campo.insert(0, valor)
        estado_edicion["entry_id"] = entry.id
        boton_guardar.configure(text="Guardar cambios")
        pestañas.set("Cargar manual")
        campos_manual["descripcion"].focus_set()

    def anular_desde_historial(cash_day, entry):
        motivo = simpledialog.askstring(
            "Anular movimiento",
            "Motivo de anulación:",
            parent=ventana,
        )
        if not motivo:
            return
        if not messagebox.askyesno(
            "Confirmar anulación",
            f"¿Anular '{entry.description}'? El registro quedará en el historial.",
            parent=ventana,
        ):
            return
        try:
            controller.void_entry(
                cash_day.business_date.strftime("%d-%m-%Y"), cash_day.unit, entry.id, motivo
            )
        except Exception as exc:
            mostrar_error(exc)
            return
        consultar_historial()

    def consultar_historial():
        try:
            cash_day = controller.list_history(
                entrada_historial.get().strip(), unidad_historial.get().strip()
            )
        except Exception as exc:
            mostrar_error(exc)
            return
        for widget in lista_historial.winfo_children():
            widget.destroy()
        resumen_historial.configure(text=texto_estado(cash_day))
        for entry in cash_day.entries:
            fila = ctk.CTkFrame(lista_historial, fg_color="transparent")
            fila.pack(fill="x", padx=4, pady=3)
            estado_texto = "ANULADO" if entry.status.value == "VOIDED" else "ACTIVO"
            detalle = (
                f"{entry.description} | Total {formatear_monto(entry.total or 0)} | "
                f"Efectivo {formatear_monto(entry.cash or 0)} | "
                f"Tarj./Cheq. {formatear_monto(entry.card_check or 0)} | "
                f"Gastos {formatear_monto(entry.expenses or 0)} | {estado_texto}"
            )
            if entry.void_reason:
                detalle += f" ({entry.void_reason})"
            ctk.CTkLabel(fila, text=detalle, anchor="w").pack(
                side="left", fill="x", expand=True
            )
            habilitado = (
                "normal"
                if cash_day.status.value == "OPEN" and entry.status.value == "ACTIVE"
                else "disabled"
            )
            ctk.CTkButton(
                fila, text="Editar", width=65, state=habilitado,
                command=lambda d=cash_day, e=entry: cargar_para_editar(d, e),
            ).pack(side="left", padx=2)
            ctk.CTkButton(
                fila, text="Anular", width=65, state=habilitado,
                fg_color=COLOR_ROJO,
                command=lambda d=cash_day, e=entry: anular_desde_historial(d, e),
            ).pack(side="left", padx=2)

    ctk.CTkButton(
        filtros_historial,
        text="Consultar",
        command=consultar_historial,
        fg_color=COLOR_PRIMARIO,
        hover_color=COLOR_PRIMARIO_HOVER,
    ).pack(side="left", padx=8)

    campos_manual["gastos"].bind("<Return>", lambda _event: guardar_manual())

    ventana.after(100, ventana.focus_set)
