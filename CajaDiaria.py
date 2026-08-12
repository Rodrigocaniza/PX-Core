"""Caja diaria de la óptica: UI legacy adaptada a Core + SQLite.

La ventana conserva el flujo CustomTkinter conocido. Toda operación nueva de
UI usa ``modulos.caja_diaria``; las funciones TXT permanecen temporalmente
solo como compatibilidad y caracterización, sin doble escritura.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

import customtkinter as ctk
from openpyxl import load_workbook
from tkinter import filedialog, messagebox, simpledialog, ttk

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
from modulos.caja_diaria.config import resolve_data_paths
from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE
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
COLUMNAS_OPERATIVAS = [
    ("descripcion", "Descripción / Cliente", 145),
    ("sobre", "Sobre", 55),
    ("arm_org", "Producto / Tipo", 95),
    ("cod", "Código", 60),
    ("armazon", "P. Armazón", 80),
    ("cristal", "P. Cristal", 80),
    ("laboratorio", "Laboratorio", 90),
    ("receta_dr", "Receta Dr.", 80),
    ("total", "Total", 75),
    ("efectivo", "Efectivo", 75),
    ("tarjeta_cheque", "Tarj./Cheq./Transf.", 105),
    ("ordenes", "Órdenes", 70),
    ("cuotas", "Cuotas", 55),
    ("saldo", "Saldo", 70),
    ("gastos", "Gastos", 70),
]
PRODUCTO_TRABAJO = COLUMNAS_OPERATIVAS[:8]
COBRO_PAGO = COLUMNAS_OPERATIVAS[8:]
CAMPOS_MONETARIOS_UI = (
    "caja_inicial", "armazon", "cristal", "total", "efectivo",
    "tarjeta_cheque", "transferencia", "saldo",
)


def formatear_importe_ui(valor):
    """Formatea enteros monetarios para edición visual sin alterar su valor."""
    texto = "" if valor is None else str(valor).strip()
    if not texto:
        return ""
    limpio = texto.replace(".", "").replace(" ", "")
    if not limpio.isdigit():
        return texto
    return f"{int(limpio):,}".replace(",", ".")


def sumar_importes_formulario(armazon, cristal):
    """Total visible canónico: únicamente precio de armazón más cristal."""
    return parsear_monto(armazon or "0", permitir_cero=True) + parsear_monto(
        cristal or "0", permitir_cero=True
    )


def sumar_medios_no_efectivo(tarjeta_cheque, transferencia):
    """Combina los medios no efectivos en el campo canónico persistido."""
    return parsear_monto(tarjeta_cheque or "0", permitir_cero=True) + parsear_monto(
        transferencia or "0", permitir_cero=True
    )


def calcular_saldo_pendiente(total, efectivo, tarjeta_cheque, transferencia):
    """Saldo visible; un sobrepago nunca se representa como deuda negativa."""
    montos = [
        parsear_monto(valor or "0", permitir_cero=True)
        for valor in (total, efectivo, tarjeta_cheque, transferencia)
    ]
    return max(0, montos[0] - sum(montos[1:]))


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
    declarados = None
    efectivo_final_declarado = None

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

    # Las hojas futuras del libro real son plantillas con formulas en cero.
    # No constituyen dias operativos y no deben crear cajas vacias ni errores.
    filas_operativas = []
    for numero in range(fila_encabezado + 1, hoja.max_row + 1):
        fila = hoja[numero]
        descripcion_normalizada = normalizar(_valor_celda(fila, 0))
        if descripcion_normalizada in (
            "", "totales", "efectivo final", normalizar(DESCRIPCION_CAJA_INICIAL)
        ):
            continue
        if any(not celda_vacia(_valor_celda(fila, indice)) for indice in range(4, 14)):
            filas_operativas.append(numero)
    if not filas_operativas:
        return [], None, None, []

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

        if normalizar(descripcion) == "totales":
            valores_declarados = (total_val, efectivo_val, tarjeta_val, gastos_val)
            if not any(isinstance(valor, str) and valor.startswith("=") for valor in valores_declarados):
                declarados = {
                    indice: _num_o_cero(valor, errores, hoja.title, numero, campo)
                    for indice, (valor, campo) in enumerate(zip(
                        valores_declarados,
                        ("TOTAL declarado", "Efectivo declarado", "Tarj./Cheq. declarado", "Gastos declarados"),
                    ))
                    if not celda_vacia(valor)
                }
            continue

        if normalizar(descripcion) in ("efectivo final", ""):
            # Fila de totales o vacía: no se importa como movimiento,
            # más abajo se recalcula y se compara contra lo declarado.
            if not celda_vacia(efectivo_val) and not (
                isinstance(efectivo_val, str) and efectivo_val.startswith("=")
            ):
                efectivo_final_declarado = _num_o_cero(
                    efectivo_val, errores, hoja.title, numero, "Efectivo final declarado"
                )
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

    calculados_declarables = (
        suma_total,
        caja_inicial + suma_efectivo_ventas,
        suma_tarjeta,
        suma_gastos,
    )
    diferencias_declaradas = {
        indice: (valor, calculados_declarables[indice])
        for indice, valor in (declarados or {}).items()
        if valor != calculados_declarables[indice]
    }
    if diferencias_declaradas:
        errores.append(
            f"Hoja '{hoja.title}': los TOTALES declarados no coinciden con los "
            f"recalculados: {diferencias_declaradas}."
        )
    if efectivo_final_declarado is not None and efectivo_final_declarado != totales_hoja["efectivo_final"]:
        errores.append(
            f"Hoja '{hoja.title}': el efectivo final declarado {efectivo_final_declarado} "
            f"no coincide con el recalculado {totales_hoja['efectivo_final']}."
        )

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

        if not registros:
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
    ctk.set_appearance_mode("light")
    ventana = ctk.CTkToplevel(ventana_padre)
    ventana.title("Caja diaria - Óptica")
    ventana.geometry("1366x768")
    ventana.minsize(1100, 680)
    ventana.transient(ventana_padre)
    ventana.grab_set()

    color_fondo = "#F3F6FA"
    color_panel = "#FBFCFE"
    color_panel_alto = "#FFFFFF"
    color_borde_suave = "#D8E0EB"
    color_texto = "#162238"
    color_suave = "#607089"
    color_azul = "#1672E8"
    color_verde = "#18A66A"
    color_naranja = "#F59E0B"
    ventana.configure(fg_color=color_fondo)

    barra_superior = ctk.CTkFrame(
        ventana, height=40, fg_color="#FFFFFF", corner_radius=0
    )
    barra_superior.pack(fill="x", padx=0, pady=0)
    barra_superior.pack_propagate(False)
    ctk.CTkLabel(
        barra_superior, text="BC", width=32, height=28, corner_radius=6,
        fg_color=color_azul, text_color="#FFFFFF",
        font=ctk.CTkFont(size=14, weight="bold"), anchor="center",
    ).pack(side="left", padx=(16, 8))
    ctk.CTkLabel(
        barra_superior, text="BC Caja Diaria   │   Óptica Central",
        text_color=color_texto, font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(side="left", padx=(0, 12))
    navegacion = ctk.CTkFrame(
        ventana, height=50, fg_color="#FFFFFF", corner_radius=0,
        border_width=1, border_color=color_borde_suave,
    )
    navegacion.pack(fill="x")
    navegacion.pack_propagate(False)
    ctk.CTkLabel(
        barra_superior, text="⚙  Configuración        📅  " + date.today().strftime("Hoy, %d/%m/%Y"),
        text_color=COLOR_TEXTO_SUAVE, font=ctk.CTkFont(size=11, weight="bold"),
    ).pack(side="right", padx=18)

    pestañas = ctk.CTkTabview(
        ventana, fg_color=color_fondo, border_width=0, corner_radius=0
    )
    pestañas.pack(fill="both", expand=True, padx=8, pady=(2, 4))
    tab_importar = pestañas.add("Importar Excel")
    tab_manual = pestañas.add("Cargar manual")
    tab_arqueo = pestañas.add("Arqueo")
    tab_historial = pestañas.add("Historial")
    pestañas._segmented_button.grid_forget()
    for fila_oculta in (0, 1, 2):
        pestañas.grid_rowconfigure(fila_oculta, minsize=0, weight=0)

    botones_navegacion = {}

    def seleccionar_pestaña(nombre):
        pestañas.set(nombre)
        for etiqueta, boton in botones_navegacion.items():
            boton.configure(
                fg_color="#EAF3FF" if etiqueta == nombre else "transparent",
                text_color=color_azul if etiqueta == nombre else color_suave,
            )

    for nombre, etiqueta_nav in (
        ("Cargar manual", "▣  Caja diaria"),
        ("Arqueo", "▤  Arqueo"),
        ("Importar Excel", "▣  Importar Excel"),
        ("Historial", "Historial"),
    ):
        boton = ctk.CTkButton(
            navegacion, text=etiqueta_nav, width=170, height=48, corner_radius=0,
            fg_color="transparent", hover_color=color_panel_alto,
            text_color=color_suave, font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda destino=nombre: seleccionar_pestaña(destino),
        )
        boton.pack(side="left", padx=(16 if nombre == "Cargar manual" else 0, 0), pady=0)
        botones_navegacion[nombre] = boton
    seleccionar_pestaña("Cargar manual")

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

    # ---- Caja operativa (disposición tipo planilla) ----
    campos_manual = {}
    estado_edicion = {"entry_id": None, "guardando": False, "caja_abierta": True}

    cabecera = ctk.CTkFrame(tab_manual, fg_color=color_panel, corner_radius=7)
    cabecera.pack(fill="x", padx=4, pady=(2, 2))
    cabecera.grid_columnconfigure(6, weight=1)
    ctk.CTkLabel(
        cabecera, text="RESUMEN DE CAJA", text_color=COLOR_TEXTO_SUAVE,
        font=ctk.CTkFont(size=10, weight="bold")
    ).grid(row=0, column=0, columnspan=6, sticky="w", padx=10, pady=(3, 0))

    controles_cabecera = [
        ("fecha", "Fecha", 130),
        ("unidad", "Sucursal", 130),
        ("caja_inicial", "Caja inicial", 150),
    ]
    for indice, (clave, etiqueta, ancho) in enumerate(controles_cabecera):
        ctk.CTkLabel(cabecera, text=etiqueta, text_color=COLOR_TEXTO_SUAVE).grid(
            row=1, column=indice * 2, sticky="w", padx=(10, 3), pady=(0, 5)
        )
        if clave == "unidad":
            campo = ctk.CTkComboBox(cabecera, values=UNIDADES, width=ancho, height=27)
            campo.set(UNIDAD_POR_DEFECTO)
        else:
            campo = ctk.CTkEntry(cabecera, width=ancho, height=27)
        campo.grid(row=1, column=indice * 2 + 1, padx=(0, 10), pady=(0, 5))
        campos_manual[clave] = campo
    campos_manual["fecha"].insert(0, date.today().strftime("%d-%m-%Y"))

    columnas_operativas = COLUMNAS_OPERATIVAS

    formulario = ctk.CTkFrame(
        tab_manual, fg_color="#FFFFFF", corner_radius=9,
        border_width=1, border_color=color_borde_suave,
    )
    formulario.grid_columnconfigure(0, weight=1)

    secciones_formulario = (
        ("1", "Cliente y comprobante", PRODUCTO_TRABAJO[:2]),
        ("2", "Detalle de venta", PRODUCTO_TRABAJO[2:]),
        ("3", "Importes", (COBRO_PAGO[0], COBRO_PAGO[3], COBRO_PAGO[4])),
        ("4", "Cobro", (("efectivo", "Efectivo", 100), ("tarjeta_cheque", "Tarjeta / Cheque", 110), ("transferencia", "Transferencia", 105), ("saldo", "Saldo pendiente", 100))),
        ("5", "Notas", (("notas", "Observaciones", 330),)),
    )
    for indice_seccion, (numero, titulo, columnas) in enumerate(secciones_formulario):
        seccion = ctk.CTkFrame(formulario, fg_color="transparent", corner_radius=0)
        seccion.grid(row=indice_seccion, column=0, sticky="ew", padx=10, pady=0)
        for columna in range(max(1, len(columnas))):
            seccion.grid_columnconfigure(columna, weight=1, uniform=f"sec{indice_seccion}")
        ctk.CTkLabel(
            seccion, text=numero, width=18, height=18, corner_radius=9,
            fg_color=color_azul, text_color="#FFFFFF",
            font=ctk.CTkFont(size=10, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=0)
        ctk.CTkLabel(
            seccion, text=titulo, height=18, text_color=color_texto, anchor="w",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=0, columnspan=max(1, len(columnas)), sticky="w", padx=(26, 0), pady=0)
        for columna, (clave, etiqueta, ancho) in enumerate(columnas):
            ctk.CTkLabel(
                seccion, text=etiqueta, height=14, text_color=color_suave, anchor="w",
                font=ctk.CTkFont(size=8, weight="bold"),
            ).grid(row=1, column=columna, sticky="ew", padx=(0 if columna == 0 else 5, 0))
            campo = ctk.CTkEntry(
                seccion, width=ancho, height=24, fg_color="#F8FAFD",
                border_width=1, border_color=color_borde_suave, text_color=color_texto,
                font=ctk.CTkFont(size=9),
            )
            campo.grid(row=2, column=columna, sticky="ew", padx=(0 if columna == 0 else 5, 0), pady=0)
            campos_manual[clave] = campo

    campos_manual["notas"].configure(placeholder_text="Observaciones de la operación")

    bloque_producto = formulario
    columna_guardar = None
    orden_teclado = [clave for clave, _, _ in columnas_operativas if clave in campos_manual]
    for indice, clave in enumerate(orden_teclado[:-1]):
        siguiente = orden_teclado[indice + 1]
        campos_manual[clave].bind(
            "<Return>", lambda _event, destino=siguiente: campos_manual[destino].focus_set()
        )

    estado_operativo = ctk.CTkFrame(cabecera, fg_color="transparent")
    estado_operativo.grid(row=0, column=6, rowspan=2, sticky="e", padx=8)
    zona_estado = ctk.CTkFrame(tab_manual, fg_color="transparent")

    estado_caja = ctk.CTkLabel(
        estado_operativo, text="SIN CONSULTAR", width=120, height=20, corner_radius=5,
        fg_color=color_panel_alto, text_color=COLOR_TEXTO_SUAVE,
        font=ctk.CTkFont(size=9, weight="bold"),
    )
    estado_caja.pack(side="left", padx=(0, 5))
    etiquetas_kpi = {}
    for clave, titulo, color in (
        ("inicial", "CAJA INICIAL", color_azul),
        ("ventas", "VENTA TOTAL", color_verde),
        ("efectivo", "EFECTIVO", color_verde),
        ("tarjeta", "TARJ. / TRANSF.", "#6558E8"),
        ("gastos", "GASTOS", "#E8753B"),
        ("saldo", "SALDO PEND.", "#E5484D"),
        ("final", "EFECTIVO FINAL", color_azul),
    ):
        tarjeta = ctk.CTkFrame(
            zona_estado, width=181, height=68, fg_color="#FFFFFF", corner_radius=7,
            border_width=1, border_color=color,
        )
        tarjeta.pack(side="left", padx=4, pady=2)
        tarjeta.pack_propagate(False)
        iconos_kpi = {
            "inicial": "▣", "ventas": "▤", "efectivo": "▭",
            "tarjeta": "▱", "gastos": "⊖", "saldo": "△", "final": "✓",
        }
        ctk.CTkLabel(
            tarjeta, text=f"{iconos_kpi[clave]}   {titulo}", text_color=color_suave,
            font=ctk.CTkFont(size=9, weight="bold"),
        ).pack(padx=3, pady=(5, 0))
        valor = ctk.CTkLabel(
            tarjeta, text="—", text_color=color,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        valor.pack(padx=3, pady=(0, 4))
        etiquetas_kpi[clave] = valor
    def formatear_campo_monetario(clave):
        campo = campos_manual[clave]
        texto = formatear_importe_ui(campo.get())
        if texto != campo.get():
            campo.delete(0, "end")
            campo.insert(0, texto)

    def recalcular_total_visible(_event=None):
        try:
            total = sumar_importes_formulario(
                campos_manual["armazon"].get(), campos_manual["cristal"].get()
            )
        except (TypeError, ValueError):
            return
        campo_total = campos_manual["total"]
        campo_total.delete(0, "end")
        campo_total.insert(0, formatear_importe_ui(total))
        recalcular_saldo_visible()

    def recalcular_saldo_visible(_event=None):
        try:
            saldo = calcular_saldo_pendiente(
                campos_manual["total"].get(), campos_manual["efectivo"].get(),
                campos_manual["tarjeta_cheque"].get(), campos_manual["transferencia"].get(),
            )
        except (TypeError, ValueError):
            return
        campo = campos_manual["saldo"]
        campo.delete(0, "end")
        campo.insert(0, formatear_importe_ui(saldo))

    for clave in CAMPOS_MONETARIOS_UI:
        campos_manual[clave].bind(
            "<FocusOut>", lambda _event, campo=clave: formatear_campo_monetario(campo), add="+"
        )
    for clave in ("armazon", "cristal"):
        campos_manual[clave].bind("<KeyRelease>", recalcular_total_visible, add="+")
        campos_manual[clave].bind("<FocusOut>", recalcular_total_visible, add="+")
    for clave in ("total", "efectivo", "tarjeta_cheque", "transferencia"):
        campos_manual[clave].bind("<KeyRelease>", recalcular_saldo_visible, add="+")
        campos_manual[clave].bind("<FocusOut>", recalcular_saldo_visible, add="+")
    filtro_movimientos = ctk.StringVar(value="Todos")
    busqueda_movimientos = ctk.StringVar()
    toolbar_movimientos = ctk.CTkFrame(
        tab_manual, fg_color=color_panel, corner_radius=8,
        border_width=1, border_color=color_borde_suave,
    )
    ctk.CTkLabel(
        toolbar_movimientos, text="Movimientos del día", text_color=color_texto,
        font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(side="left", padx=12)
    entrada_busqueda = ctk.CTkEntry(
        toolbar_movimientos, textvariable=busqueda_movimientos,
        placeholder_text="Buscar movimiento…", width=205, height=28,
        fg_color="#F7F9FC", border_color=color_borde_suave,
    )
    entrada_busqueda.pack(side="left", padx=(8, 6), pady=6)
    botones_filtro = {}
    for nombre_filtro in ("Todos", "Ventas", "Gastos", "Pendientes"):
        boton_filtro = ctk.CTkButton(
            toolbar_movimientos, text=nombre_filtro, width=68, height=28,
            corner_radius=4, fg_color="#EAF3FF" if nombre_filtro == "Todos" else "transparent",
            text_color=color_azul if nombre_filtro == "Todos" else color_suave,
            border_width=1, border_color=color_borde_suave,
            command=lambda valor=nombre_filtro: aplicar_filtro_movimientos(valor),
        )
        boton_filtro.pack(side="left", padx=1, pady=6)
        botones_filtro[nombre_filtro] = boton_filtro
    marco_grilla = ctk.CTkFrame(tab_manual, fg_color=color_panel, corner_radius=5)
    marco_grilla.pack(fill="both", expand=True, padx=6, pady=3)
    estilo = ttk.Style(ventana)
    estilo.theme_use("clam")
    estilo.configure(
        "Caja.Treeview", rowheight=27, font=("Segoe UI", 9),
        background="#FFFFFF", fieldbackground="#FFFFFF", foreground="#24324A",
        borderwidth=0, relief="flat",
    )
    estilo.map(
        "Caja.Treeview",
        background=[("selected", "#245DA8")],
        foreground=[("selected", "#FFFFFF")],
    )
    estilo.configure(
        "Caja.Treeview.Heading", font=("Segoe UI", 9, "bold"),
        background="#EDF3FA", foreground="#33425B", relief="flat", padding=(4, 5),
    )
    estilo.map("Caja.Treeview.Heading", background=[("active", "#245DA8")])
    claves_grilla = [clave for clave, _, _ in columnas_operativas] + ["acciones"]
    grilla_caja = ttk.Treeview(
        marco_grilla, columns=claves_grilla, show="headings", style="Caja.Treeview"
    )
    for clave, etiqueta, ancho in columnas_operativas:
        grilla_caja.heading(clave, text=etiqueta)
        grilla_caja.column(clave, width=ancho, minwidth=65, stretch=False, anchor="w")
    grilla_caja.heading("acciones", text="Acciones")
    grilla_caja.column("acciones", width=105, minwidth=105, stretch=False, anchor="center")
    grilla_caja.tag_configure("voided", foreground="#E0717C", background="#241824")
    grilla_caja.tag_configure("expense", foreground="#F5A3AA")
    grilla_caja.tag_configure("pending", foreground="#F7BF62")
    scroll_horizontal = ttk.Scrollbar(
        marco_grilla, orient="horizontal", command=grilla_caja.xview
    )
    scroll_vertical = ttk.Scrollbar(
        marco_grilla, orient="vertical", command=grilla_caja.yview
    )
    grilla_caja.configure(
        xscrollcommand=scroll_horizontal.set, yscrollcommand=scroll_vertical.set
    )
    grilla_caja.grid(row=0, column=0, sticky="nsew")
    scroll_vertical.grid(row=0, column=1, sticky="ns")
    scroll_horizontal.grid(row=1, column=0, sticky="ew")
    marco_grilla.grid_rowconfigure(0, weight=1)
    marco_grilla.grid_columnconfigure(0, weight=1)
    pie_movimientos = ctk.CTkFrame(
        tab_manual, fg_color="#FFFFFF", corner_radius=7,
        border_width=1, border_color=color_borde_suave,
    )
    etiqueta_conteo_movimientos = ctk.CTkLabel(
        pie_movimientos, text="Mostrando 0 de 0 movimientos", anchor="w",
        text_color=color_suave, font=ctk.CTkFont(size=9),
    )
    etiqueta_conteo_movimientos.pack(side="left", padx=12)
    for pagina in ("‹", "1", "2", "3", "›"):
        ctk.CTkButton(
            pie_movimientos, text=pagina, width=30, height=27, corner_radius=5,
            fg_color=color_azul if pagina == "1" else "transparent",
            text_color="#FFFFFF" if pagina == "1" else color_texto,
            border_width=1, border_color=color_borde_suave,
        ).pack(side="right", padx=2, pady=4)

    def texto_estado(cash_day):
        totales = cash_day.totals()
        texto = (
            f"{cash_day.status.value}   ·   "
            f"Efectivo actual  {formatear_monto(totales.expected_cash)}    "
            f"Total ventas  {formatear_monto(totales.total)}\n"
            f"Gastos  {formatear_monto(totales.expenses)}    "
            f"Efectivo final  {formatear_monto(totales.expected_cash)}"
        )
        if cash_day.closed_at is None or cash_day.session_duration_seconds is None:
            return texto
        apertura = cash_day.opened_at.astimezone(BUSINESS_TIMEZONE).strftime("%H:%M:%S")
        cierre = cash_day.closed_at.astimezone(BUSINESS_TIMEZONE).strftime("%H:%M:%S")
        horas, resto = divmod(cash_day.session_duration_seconds, 3600)
        minutos = resto // 60
        if cash_day.overtime_triggered is None:
            extra = "Hora extra: política pendiente para este día"
        elif cash_day.overtime_triggered:
            extra = f"Hora extra: SÍ · {cash_day.overtime_minutes} min"
        else:
            extra = "Hora extra: NO"
        return (
            f"{texto}\n\nApertura real  {apertura}    Cierre real  {cierre}\n"
            f"Duración  {horas:02d}:{minutos:02d}    {extra}"
        )

    def valores_fila(entry):
        return (
            (f"GASTO - {entry.description}" if entry.expenses else entry.description),
            entry.envelope, entry.frame_origin, entry.code,
            formatear_importe_ui(entry.frame), formatear_importe_ui(entry.lens),
            entry.laboratory, entry.prescription_doctor,
            formatear_monto(entry.total or 0), formatear_monto(entry.cash or 0),
            formatear_monto(entry.card_check or 0), entry.orders, entry.installments,
            formatear_importe_ui(entry.balance), formatear_monto(entry.expenses or 0),
            "Editar  ·  Anular",
        )
    def refrescar_grilla(cash_day):
        for item in grilla_caja.get_children():
            grilla_caja.delete(item)
        consulta = busqueda_movimientos.get().strip().casefold()
        filtro = filtro_movimientos.get()
        for entry in cash_day.entries:
            if consulta and consulta not in " ".join(str(value) for value in valores_fila(entry)).casefold():
                continue
            if filtro == "Ventas" and (entry.expenses or 0) > 0:
                continue
            if filtro == "Gastos" and not (entry.expenses or 0):
                continue
            if filtro == "Pendientes" and not entry.balance:
                continue
            if entry.status.value == "VOIDED":
                tags = ("voided",)
            elif entry.expenses:
                tags = ("expense",)
            elif entry.balance:
                tags = ("pending",)
            else:
                tags = ()
            values = list(valores_fila(entry))
            if entry.status.value == "VOIDED":
                values[0] = f"ANULADO · {values[0]}"
            grilla_caja.insert("", "end", iid=entry.id, values=values, tags=tags)
        etiqueta_conteo_movimientos.configure(
            text=f"Mostrando {len(grilla_caja.get_children())} de {len(cash_day.entries)} movimientos"
        )

    def aplicar_filtro_movimientos(nombre):
        filtro_movimientos.set(nombre)
        for etiqueta, boton in botones_filtro.items():
            activo = etiqueta == nombre
            boton.configure(
                fg_color="#EAF3FF" if activo else "transparent",
                text_color=color_azul if activo else color_suave,
            )
        try:
            refrescar_grilla(controller.load_day(
                campos_manual["fecha"].get().strip(), campos_manual["unidad"].get().strip()
            ))
        except Exception:
            pass

    entrada_busqueda.bind("<KeyRelease>", lambda _event: aplicar_filtro_movimientos(filtro_movimientos.get()))
    def actualizar_estado(cash_day):
        totales = cash_day.totals()
        abierta = cash_day.status.value == "OPEN"
        estado_caja.configure(
            text="Estado: ABIERTA" if abierta else "Estado: CERRADA",
            fg_color="#123B2C" if abierta else "#3A2630",
            text_color=color_verde if abierta else "#E0717C",
        )
        saldo_pendiente = 0
        for entry in cash_day.entries:
            if entry.status.value != "ACTIVE":
                continue
            try:
                saldo_pendiente += parsear_monto(entry.balance, permitir_cero=True)
            except (TypeError, ValueError):
                pass
        etiquetas_kpi["inicial"].configure(text=formatear_monto(cash_day.opening_cash))
        etiquetas_kpi["ventas"].configure(text=formatear_monto(totales.total))
        etiquetas_kpi["efectivo"].configure(text=formatear_monto(totales.cash))
        etiquetas_kpi["tarjeta"].configure(text=formatear_monto(totales.card_check))
        etiquetas_kpi["gastos"].configure(text=formatear_monto(totales.expenses))
        etiquetas_kpi["saldo"].configure(text=formatear_monto(saldo_pendiente))
        etiquetas_kpi["final"].configure(text=formatear_monto(totales.expected_cash))
        refrescar_grilla(cash_day)
        estado_control = "normal" if cash_day.status.value == "OPEN" else "disabled"
        estado_edicion["caja_abierta"] = cash_day.status.value == "OPEN"
        for clave, _, _ in columnas_operativas:
            if clave in campos_manual:
                campos_manual[clave].configure(state=estado_control)
        campos_manual["transferencia"].configure(state=estado_control)
        campos_manual["notas"].configure(state=estado_control)
        boton_guardar.configure(state=estado_control)
        boton_gasto.configure(state=estado_control)

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
        boton_abrir.pack_forget()

    def cerrar_caja():
        try:
            cash_day_abierta = controller.load_day(
                campos_manual["fecha"].get().strip(),
                campos_manual["unidad"].get().strip(),
            )
        except Exception as exc:
            mostrar_error(exc)
            return
        totales = cash_day_abierta.totals()
        if not messagebox.askyesno(
            "Cerrar Caja",
            "Caja inicial: " + formatear_monto(cash_day_abierta.opening_cash) + "\n"
            "Ventas en efectivo: " + formatear_monto(totales.cash) + "\n"
            "Tarjeta / transferencia: " + formatear_monto(totales.card_check) + "\n"
            "Gastos: " + formatear_monto(totales.expenses) + "\n"
            "Efectivo esperado: " + formatear_monto(totales.expected_cash) + "\n\n"
            "Después del cierre no se podrán modificar movimientos. ¿Cerrar caja?",
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

    def limpiar_operacion():
        for clave, _, _ in columnas_operativas:
            if clave in campos_manual:
                campos_manual[clave].delete(0, "end")
        campos_manual["notas"].delete(0, "end")
        campos_manual["descripcion"].focus_set()

    def guardar_manual():
        recalcular_total_visible()
        recalcular_saldo_visible()
        if estado_edicion["guardando"]:
            return
        estado_edicion["guardando"] = True
        boton_guardar.configure(state="disabled")
        valores = {clave: campo.get().strip() for clave, campo in campos_manual.items()}
        valores["tarjeta_cheque"] = str(sumar_medios_no_efectivo(
            valores["tarjeta_cheque"], valores["transferencia"]
        ))
        try:
            if estado_edicion["entry_id"]:
                cash_day, _ = controller.update_manual_entry(estado_edicion["entry_id"], valores)
            else:
                cash_day, _ = controller.add_manual_entry(valores)
        except Exception as exc:
            mostrar_error(exc)
            return
        finally:
            estado_edicion["guardando"] = False
            boton_guardar.configure(
                state="normal" if estado_edicion["caja_abierta"] else "disabled"
            )
        actualizar_estado(cash_day)
        messagebox.showinfo(
            "Guardado",
            "Movimiento actualizado." if estado_edicion["entry_id"] else "Movimiento agregado.",
            parent=ventana,
        )
        estado_edicion["entry_id"] = None
        boton_guardar.configure(text="Guardar movimiento")
        boton_cancelar.pack_forget()
        limpiar_operacion()

    atributos_ui = {
        "descripcion": "description", "sobre": "envelope", "arm_org": "frame_origin",
        "cod": "code", "armazon": "frame", "cristal": "lens",
        "laboratorio": "laboratory", "receta_dr": "prescription_doctor",
        "total": "total", "efectivo": "cash", "tarjeta_cheque": "card_check",
        "ordenes": "orders", "cuotas": "installments", "saldo": "balance",
        "gastos": "expenses", "notas": "source_reference",
    }

    def movimiento_seleccionado():
        seleccion = grilla_caja.selection()
        if not seleccion:
            messagebox.showwarning("Seleccioná una fila", "Elegí un movimiento de la grilla.", parent=ventana)
            return None, None
        try:
            cash_day = controller.load_day(
                campos_manual["fecha"].get().strip(), campos_manual["unidad"].get().strip()
            )
        except Exception as exc:
            mostrar_error(exc)
            return None, None
        entry = next((item for item in cash_day.entries if item.id == seleccion[0]), None)
        return cash_day, entry

    def editar_seleccionado(_event=None):
        cash_day, entry = movimiento_seleccionado()
        if entry is None:
            return
        if cash_day.status.value != "OPEN" or entry.status.value != "ACTIVE":
            messagebox.showwarning("No editable", "La fila está cerrada o anulada.", parent=ventana)
            return
        for clave, atributo in atributos_ui.items():
            if clave not in campos_manual:
                continue
            campo = campos_manual[clave]
            campo.delete(0, "end")
            valor = getattr(entry, atributo)
            campo.insert(0, "" if valor is None else str(valor))
        estado_edicion["entry_id"] = entry.id
        boton_guardar.configure(text="Guardar cambios")
        boton_cancelar.pack(side="left", padx=3)
        campos_manual["descripcion"].focus_set()

    def cancelar_edicion():
        estado_edicion["entry_id"] = None
        boton_guardar.configure(text="Guardar movimiento")
        boton_cancelar.pack_forget()
        limpiar_operacion()

    def anular_seleccionado():
        cash_day, entry = movimiento_seleccionado()
        if entry is None:
            return
        if cash_day.status.value != "OPEN" or entry.status.value != "ACTIVE":
            messagebox.showwarning("No anulable", "La fila está cerrada o ya fue anulada.", parent=ventana)
            return
        motivo = simpledialog.askstring("Anular movimiento", "Motivo de anulación:", parent=ventana)
        if not motivo:
            return
        if not messagebox.askyesno("Confirmar anulación", f"¿Anular '{entry.description}'?", parent=ventana):
            return
        try:
            controller.void_entry(
                cash_day.business_date.strftime("%d-%m-%Y"), cash_day.unit, entry.id, motivo
            )
            actualizar_estado(controller.load_day(
                cash_day.business_date.strftime("%d-%m-%Y"), cash_day.unit
            ))
        except Exception as exc:
            mostrar_error(exc)

    acciones = ctk.CTkFrame(tab_manual, fg_color=color_panel, corner_radius=6)
    acciones.pack(fill="x", padx=6, pady=(1, 2))
    acciones_primarias = ctk.CTkFrame(acciones, fg_color="transparent")
    acciones_primarias.pack(fill="x", padx=4, pady=3)
    boton_abrir = ctk.CTkButton(
        estado_operativo, text="ABRIR / CONSULTAR", command=abrir_o_consultar,
        width=118, height=21, corner_radius=4, fg_color=color_azul,
        hover_color="#1D65C5", font=ctk.CTkFont(size=9, weight="bold"),
    )
    boton_abrir.pack(side="left", padx=(0, 5), before=estado_caja)

    def mostrar_boton_abrir(_event=None):
        if not boton_abrir.winfo_manager():
            boton_abrir.pack(side="left", padx=(0, 5), before=estado_caja)

    for clave in ("fecha", "unidad", "caja_inicial"):
        campos_manual[clave].bind("<FocusIn>", mostrar_boton_abrir, add="+")

    def refrescar_estado_consultado(_event=None):
        try:
            actualizar_estado(controller.load_day(
                campos_manual["fecha"].get().strip(), campos_manual["unidad"].get().strip()
            ))
        except Exception:
            estado_caja.configure(text="SIN CONSULTAR")

    for clave in ("fecha", "unidad"):
        campos_manual[clave].bind("<FocusOut>", refrescar_estado_consultado, add="+")
    boton_guardar = ctk.CTkButton(
        acciones_primarias, text="Guardar venta  —  F9", command=guardar_manual,
        width=150, height=32, fg_color=color_azul, hover_color="#0F5FC7",
        font=ctk.CTkFont(size=11, weight="bold"),
    )
    boton_guardar.pack(side="left", padx=(8, 4), pady=3)
    ctk.CTkButton(
        acciones_primarias, text="Limpiar", command=limpiar_operacion, width=100, height=32,
        fg_color="#FFFFFF", text_color=color_texto, border_width=1,
        border_color=color_borde_suave, hover_color="#F1F5FA",
    ).pack(side="left", padx=4, pady=3)
    def abrir_dialogo_gasto():
        dialogo = ctk.CTkToplevel(ventana)
        dialogo.title("Registrar gasto")
        dialogo.geometry("430x270")
        dialogo.transient(ventana)
        dialogo.grab_set()
        campos_gasto = {}
        for fila, (clave, etiqueta) in enumerate((
            ("concepto", "Concepto / Origen *"),
            ("monto", "Monto *"),
            ("observaciones", "Observaciones (opcional)"),
        )):
            ctk.CTkLabel(dialogo, text=etiqueta, anchor="w").grid(
                row=fila * 2, column=0, sticky="ew", padx=20, pady=(12, 2)
            )
            campo = ctk.CTkEntry(dialogo, width=390)
            campo.grid(row=fila * 2 + 1, column=0, padx=20)
            campos_gasto[clave] = campo

        def guardar_gasto():
            try:
                cash_day, _ = controller.add_expense(
                    campos_manual["fecha"].get().strip(), campos_manual["unidad"].get().strip(),
                    campos_gasto["concepto"].get(), campos_gasto["monto"].get(),
                    campos_gasto["observaciones"].get(),
                )
            except Exception as exc:
                mostrar_error(exc)
                return
            actualizar_estado(cash_day)
            dialogo.destroy()

        campos_gasto["monto"].bind(
            "<FocusOut>", lambda _event: formatear_entry_gasto(campos_gasto["monto"])
        )
        ctk.CTkButton(dialogo, text="Guardar gasto", command=guardar_gasto).grid(
            row=6, column=0, pady=16
        )
        campos_gasto["concepto"].focus_set()

    def formatear_entry_gasto(campo):
        valor = formatear_importe_ui(campo.get())
        campo.delete(0, "end")
        campo.insert(0, valor)

    boton_gasto = ctk.CTkButton(
        acciones_primarias, text="Registrar gasto",
        command=abrir_dialogo_gasto, width=115, height=32,
        fg_color="#FFF7ED", text_color="#D96C2C", border_width=1,
        border_color="#F2C69F", hover_color="#FFEBD7",
    )
    boton_gasto.pack(side="left", padx=4, pady=3)
    boton_cancelar = ctk.CTkButton(
        acciones_primarias, text="Cancelar edición", command=cancelar_edicion,
        fg_color=COLOR_PANEL_SECUNDARIO[1], hover_color=COLOR_PRIMARIO_HOVER,
    )
    def accion_en_fila(event):
        if grilla_caja.identify_region(event.x, event.y) != "cell":
            return
        if grilla_caja.identify_column(event.x) != f"#{len(claves_grilla)}":
            return
        item = grilla_caja.identify_row(event.y)
        if not item:
            return
        grilla_caja.selection_set(item)
        izquierda, _, ancho, _ = grilla_caja.bbox(item, "acciones")
        if event.x < izquierda + ancho / 2:
            editar_seleccionado()
        else:
            anular_seleccionado()

    def desplazar_movimientos(event):
        pasos = -1 if event.delta > 0 else 1
        grilla_caja.yview_scroll(pasos, "units")
        return "break"

    grilla_caja.bind("<MouseWheel>", desplazar_movimientos, add="+")
    grilla_caja.bind("<Double-1>", editar_seleccionado)
    grilla_caja.bind("<ButtonRelease-1>", accion_en_fila, add="+")
    ventana.bind("<F2>", editar_seleccionado)
    ventana.bind("<F3>", lambda _event: anular_seleccionado())
    ventana.bind("<F9>", lambda _event: guardar_manual())
    ventana.bind("<F12>", lambda _event: cerrar_caja())
    campos_manual["fecha"].bind(
        "<Return>", lambda _event: campos_manual["unidad"].focus_set()
    )
    campos_manual["unidad"].bind(
        "<Return>", lambda _event: campos_manual["caja_inicial"].focus_set()
    )
    campos_manual["caja_inicial"].bind(
        "<Return>", lambda _event: abrir_o_consultar()
    )

    pie = ctk.CTkFrame(tab_manual, fg_color="transparent", height=18)
    pie.pack(fill="x", padx=8, pady=(0, 1))
    ruta_datos = resolve_data_paths().root
    usuario = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    etiqueta_pie = ctk.CTkLabel(
        pie,
        text=f"BC Caja 0.4.0   ·   Datos: {ruta_datos}"
             + (f"   ·   Usuario: {usuario}" if usuario else ""),
        anchor="w", text_color=COLOR_TEXTO_SUAVE, font=ctk.CTkFont(size=9),
    )
    etiqueta_pie.pack(side="left", fill="x", expand=True)
    reloj = ctk.CTkLabel(
        pie, text="", anchor="e", text_color=COLOR_TEXTO_SUAVE,
        font=ctk.CTkFont(size=9),
    )
    reloj.pack(side="right")
    # Macro-layout UX-006: header context, KPI cards, five-section form,
    # movements table with footer, using the freed cash-count-summary space.
    for bloque in (
        cabecera, zona_estado, formulario, toolbar_movimientos,
        marco_grilla, pie_movimientos, acciones, pie,
    ):
        bloque.pack_forget()
    cabecera.configure(width=1330, height=50)
    cabecera.place(x=4, y=4)
    zona_estado.configure(width=1330, height=74)
    zona_estado.place(x=4, y=62)
    formulario.configure(width=570, height=400)
    formulario.grid_propagate(False)
    formulario.place(x=4, y=146)
    acciones.configure(width=570, height=38)
    acciones.pack_propagate(False)
    acciones.place(x=4, y=552)
    toolbar_movimientos.configure(width=744, height=44)
    toolbar_movimientos.place(x=590, y=146)
    marco_grilla.configure(width=744, height=354)
    marco_grilla.grid_propagate(False)
    marco_grilla.place(x=590, y=196)
    pie_movimientos.configure(width=744, height=38)
    pie_movimientos.place(x=590, y=556)
    pie.configure(width=1322, height=18)
    pie.place(x=8, y=600)
    def actualizar_reloj():
        if reloj.winfo_exists():
            reloj.configure(text=datetime.now().strftime("%H:%M:%S"))
            ventana.after(1000, actualizar_reloj)

    actualizar_reloj()
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
            cash_day = controller.load_day(fecha, combo_unidad_arqueo.get())
            totales = cash_day.totals()
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
                f"Caja inicial: {formatear_monto(cash_day.opening_cash)}\n"
                f"Ventas en efectivo: {formatear_monto(totales.cash)}\n"
                f"Tarjeta / transferencia: {formatear_monto(totales.card_check)}\n"
                f"Gastos: {formatear_monto(totales.expenses)}\n"
                f"Efectivo esperado: {formatear_monto(resultado.expected_total)}\n"
                f"Efectivo contado: {formatear_monto(resultado.counted_total)}\n"
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
            "laboratorio": entry.laboratory,
            "receta_dr": entry.prescription_doctor,
            "total": "" if entry.total is None else str(entry.total),
            "efectivo": "" if entry.cash is None else str(entry.cash),
            "tarjeta_cheque": "" if entry.card_check is None else str(entry.card_check),
            "ordenes": entry.orders,
            "cuotas": entry.installments,
            "saldo": entry.balance,
            "gastos": "" if entry.expenses is None else str(entry.expenses),
            "notas": entry.source_reference,
        }
        for clave, valor in valores.items():
            if clave not in campos_manual:
                continue
            campo = campos_manual[clave]
            if clave == "unidad":
                campo.set(valor)
            else:
                campo.delete(0, "end")
                campo.insert(0, valor)
        estado_edicion["entry_id"] = entry.id
        boton_guardar.configure(text="Guardar cambios")
        boton_cancelar.pack(side="left", padx=3)
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


    ventana.after(100, ventana.focus_set)
    return ventana
