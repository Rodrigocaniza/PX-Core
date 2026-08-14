"""Caja diaria de la óptica: UI legacy adaptada a Core + SQLite.

La ventana conserva el flujo CustomTkinter conocido. Toda operación nueva de
UI usa ``modulos.caja_diaria``; las funciones TXT permanecen temporalmente
solo como compatibilidad y caracterización, sin doble escritura.
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace
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
from modulos.caja_diaria.domain.models import (
    BUSINESS_TIMEZONE, SaleItem, client_balance_from_classification,
)
from modulos.caja_diaria.ui.controller import friendly_error
from modulos.caja_diaria.ui.privacy import FinancialPrivacy


RUTA_CAJA_DIARIA = "Datos/caja_diaria.txt"
RUTA_ARQUEO = "Datos/arqueo_caja.txt"
UNIDAD_POR_DEFECTO = "PC"
DESCRIPCION_CAJA_INICIAL = "CAJA INICIAL"

# Billetes y monedas en guaraníes. Ajustar si cambia el circulante.
DENOMINACIONES = [
    100000, 50000, 20000, 10000, 5000, 2000, 1000, 500, 100, 50,
]


def perfil_visual(ancho: int, alto: int, escala_dpi: float = 1.0) -> dict:
    """Métricas deterministas; Full HD mejora legibilidad sin duplicar la UI."""
    full_hd = ancho >= 1700 and alto >= 900
    if not full_hd:
        return {
            "nombre": "compacto", "ventana": "1366x768", "fuente": 9,
            "fuente_label": 8, "fuente_seccion": 11, "fuente_kpi": 14,
            "campo_alto": 24, "fila": 27, "izquierda": 570, "separacion": 16,
            "cabecera_alto": 50, "kpi_alto": 74, "form_alto": 400,
            "toolbar_alto": 44, "grilla_alto": 354, "acciones_alto": 38,
            "contenido_ancho": 1330,
        }
    # Tk/CustomTkinter ya aplican el escalado DPI del sistema. No multiplicamos
    # nuevamente por 125%, evitando doble escala y solapamientos.
    return {
        "nombre": "full-hd", "ventana": "1920x1080", "fuente": 12,
        "fuente_label": 10, "fuente_seccion": 14, "fuente_kpi": 20,
        "campo_alto": 34, "fila": 32, "izquierda": 750, "separacion": 18,
        "cabecera_alto": 66, "kpi_alto": 104, "form_alto": 550,
        "toolbar_alto": 58, "grilla_alto": 590, "acciones_alto": 50,
            "contenido_ancho": 1890,
    }


def area_trabajo_windows() -> tuple[int, int, int, int] | None:
    """RectÃ¡ngulo Ãºtil primario, excluida la barra de tareas de Windows."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            return rect.left, rect.top, rect.right, rect.bottom
    except (AttributeError, OSError):
        pass
    return None

CAMPOS = [
    "fecha", "unidad", "descripcion", "sobre", "arm_org", "cod",
    "armazon", "cristal", "receta_dr", "total", "efectivo",
    "tarjeta_cheque", "ordenes", "cuotas", "saldo", "gastos", "origen",
]
MOVEMENT_COLUMN_SPECS = (
    ("hora", "Hora", 48, "center"),
    ("descripcion", "Cliente", 180, "w"),
    ("cliente_telefono", "Teléfono", 82, "w"),
    ("tipo_resumen", "Tipo/Resumen", 105, "w"),
    ("sobre", "Comprobante", 85, "w"),
    ("total", "Total", 72, "e"),
    ("efectivo", "Efectivo", 72, "e"),
    ("tarjeta_transferencia", "Tarjeta/Transferencia", 120, "e"),
    ("monto_convenio", "A cobrar convenio", 105, "e"),
    ("cuotas", "Cuotas", 55, "center"),
    ("saldo", "Saldo", 72, "e"),
    ("vendedora", "Vendedora", 80, "w"),
    ("estado", "Estado", 65, "center"),
)
COLUMNAS_OPERATIVAS = [
    (key, title, width) for key, title, width, _anchor in MOVEMENT_COLUMN_SPECS
]
PRODUCTO_TRABAJO = (
    ("arm_org", "Tipo / Producto", 150), ("cod", "Código", 90),
    ("laboratorio", "Laboratorio", 140), ("armazon", "Precio armazón", 125),
    ("cristal", "Precio cristal", 125), ("receta_dr", "Receta / Doctor", 170),
)
COBRO_PAGO = (
    ("total", "Total de la venta", 150), ("efectivo", "Efectivo", 125),
    ("tarjeta_cheque", "Tarjeta / Cheque", 135),
    ("transferencia", "Transferencia", 125),
    ("ordenes", "Orden / Convenio", 150), ("monto_convenio", "Monto convenio", 125),
    ("cuotas", "Cuotas", 75), ("saldo", "Saldo cliente", 125),
)
CAMPOS_MONETARIOS_UI = (
    "caja_inicial", "armazon", "cristal", "total", "efectivo",
    "tarjeta_cheque", "transferencia", "monto_convenio", "saldo", "gasto_monto",
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


def calcular_saldo_pendiente(total, efectivo, tarjeta_cheque, transferencia, monto_convenio=0):
    """Saldo visible; un sobrepago nunca se representa como deuda negativa."""
    montos = [
        parsear_monto(valor or "0", permitir_cero=True)
        for valor in (total, efectivo, tarjeta_cheque, transferencia, monto_convenio)
    ]
    tarjeta_transferencia = montos[2] + montos[3]
    pendiente_antes_convenio = max(0, montos[0] - montos[1] - tarjeta_transferencia)
    if montos[4] > pendiente_antes_convenio:
        raise ValueError("El monto convenio excede el total pendiente.")
    return client_balance_from_classification(
        montos[0], montos[1], tarjeta_transferencia, montos[4]
    )


def construir_item_producto_visible(valores):
    """Convierte el producto actualmente visible en el primer item de la venta."""
    item = SaleItem(
        description=valores.get("arm_org") or valores.get("cod") or "Producto",
        code=valores.get("cod", ""), item_type=valores.get("arm_org", ""),
        frame_price=valores.get("armazon", ""), lens_price=valores.get("cristal", ""),
        laboratory=valores.get("laboratorio", ""),
        prescription_doctor=valores.get("receta_dr", ""),
    )
    if item.subtotal <= 0:
        raise ValueError("El producto debe tener un precio de armazón o cristal.")
    return item


def completar_items_para_guardar(valores, items):
    """Conserva N items o promueve el producto visible para la venta habitual."""
    return tuple(items) if items else (construir_item_producto_visible(valores),)


def escribir_importe_formateado(campo, valor):
    """Escribe un importe legible en UI sin alterar su valor numérico."""
    texto = formatear_importe_ui(valor)
    campo.delete(0, "end")
    campo.insert(0, texto)
    return texto


def leer_valores_formulario(campos):
    """Lee únicamente controles de entrada; los botones no forman parte del payload."""
    return {
        clave: getter().strip()
        for clave, campo in campos.items()
        if callable(getter := getattr(campo, "get", None))
    }


def resumen_venta_en_curso(cliente, items, privacidad):
    """Modelo visual del draft; no persiste ni altera sus artículos."""
    total = sum(item.subtotal for item in items)
    return {
        "cliente": str(cliente or "").strip() or "Cliente sin nombre",
        "cantidad": len(items),
        "total": formatear_monto(total),
        "estado": "EN CURSO",
        "items": tuple(
            (item.description, formatear_monto(item.subtotal))
            for item in items
        ),
    }


def mostrar_error_guardado(error, parent=None):
    """Hace visible cualquier rechazo del guardado usando mensajes seguros."""
    titulo, detalle = friendly_error(error)
    messagebox.showerror(titulo, detalle, parent=parent)


def formatear_diferencia_ui(diferencia):
    prefijo = "+" if diferencia > 0 else ""
    return prefijo + formatear_monto(diferencia)


def describir_diferencia_arqueo(diferencia):
    if diferencia == 0:
        return "ARQUEO CONFORME", "Caja conforme"
    if diferencia < 0:
        return "ARQUEO CON DIFERENCIA", f"Faltan {formatear_monto(abs(diferencia))}"
    return "ARQUEO CON DIFERENCIA", f"Sobran {formatear_monto(diferencia)}"

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

def abrir_caja_diaria(ventana_padre, controller=None, usar_ventana_raiz=False):
    """Abre la UI conocida usando Core + SQLite para toda operación nueva."""
    controller = controller or build_cash_day_controller()
    ctk.set_appearance_mode("light")
    ventana = ventana_padre if usar_ventana_raiz else ctk.CTkToplevel(ventana_padre)
    ventana.title("Caja diaria - Óptica")
    tamano_forzado = os.environ.get("BC_CAJA_WINDOW_SIZE", "").lower().split("x")
    area_trabajo = area_trabajo_windows()
    if area_trabajo:
        area_x, area_y, area_derecha, area_inferior = area_trabajo
        ancho_trabajo = area_derecha - area_x
        alto_trabajo = area_inferior - area_y
        barra_tareas = max(0, ventana.winfo_screenheight() - alto_trabajo)
    else:
        area_x = area_y = barra_tareas = 0
        ancho_trabajo, alto_trabajo = ventana.winfo_screenwidth(), ventana.winfo_screenheight()
    tamano_de_prueba = len(tamano_forzado) == 2 and all(
        valor.isdigit() for valor in tamano_forzado
    )
    if tamano_de_prueba:
        ancho_disponible, alto_disponible = map(int, tamano_forzado)
    else:
        ancho_disponible, alto_disponible = ancho_trabajo, alto_trabajo
    perfil = perfil_visual(ancho_disponible, alto_disponible)
    # El perfil describe la UI interna. La ventana conserva siempre el marco
    # nativo: maximizar no equivale a forzar una geometría fullscreen.
    ancho_logico = min(ancho_disponible, ancho_trabajo)
    alto_objetivo = alto_disponible - barra_tareas if tamano_de_prueba else alto_disponible
    alto_logico = min(alto_objetivo, alto_trabajo)
    if tamano_de_prueba:
        ventana.geometry(f"{ancho_logico}x{alto_logico}+{area_x}+{area_y}")
    else:
        ancho_inicial = min(1440, max(1100, ancho_logico - 120))
        alto_inicial = min(900, max(680, alto_logico - 100))
        ventana.geometry(f"{ancho_inicial}x{alto_inicial}+40+30")
    ventana.minsize(1100, 680)
    ventana.resizable(True, True)
    ventana.overrideredirect(False)
    ventana.attributes("-fullscreen", False)
    if sys.platform == "win32" and not tamano_de_prueba:
        ventana.after_idle(lambda: ventana.state("zoomed"))

    color_fondo = "#EAF2FB"
    color_panel = "#F4F8FD"
    color_panel_alto = "#F8FBFF"
    color_borde_suave = "#B9CDE5"
    color_texto = "#162238"
    color_suave = "#607089"
    color_azul = "#1672E8"
    color_verde = "#18A66A"
    color_naranja = "#F59E0B"
    ventana.configure(fg_color=color_fondo)

    barra_superior = ctk.CTkFrame(
        ventana, height=(40 if perfil["nombre"] == "full-hd" else 30), fg_color="#0F5FB9", corner_radius=0
    )
    barra_superior.pack(fill="x", padx=0, pady=0)
    barra_superior.pack_propagate(False)
    ctk.CTkLabel(
        barra_superior, text="BC", width=28, height=22, corner_radius=5,
        fg_color="#FFFFFF", text_color="#0F5FB9",
        font=ctk.CTkFont(size=(18 if perfil["nombre"] == "full-hd" else 14), weight="bold"), anchor="center",
    ).pack(side="left", padx=(16, 8))
    ctk.CTkLabel(
        barra_superior, text="BC Caja Diaria   │   Óptica Central",
        text_color="#FFFFFF", font=ctk.CTkFont(size=(18 if perfil["nombre"] == "full-hd" else 14), weight="bold"),
    ).pack(side="left", padx=(0, 12))
    privacidad = FinancialPrivacy(timeout_seconds=300)
    navegacion = ctk.CTkFrame(
        ventana, height=(44 if perfil["nombre"] == "full-hd" else 32), fg_color="#F5F9FE", corner_radius=0,
        border_width=1, border_color=color_borde_suave,
    )
    navegacion.pack(fill="x")
    navegacion.pack_propagate(False)
    ctk.CTkLabel(
        barra_superior, text="⚙  Configuración        📅  " + date.today().strftime("Hoy, %d/%m/%Y"),
        text_color="#DCEBFF", font=ctk.CTkFont(size=11, weight="bold"),
    ).pack(side="right", padx=18)

    pestañas = ctk.CTkTabview(
        ventana, fg_color=color_fondo, border_width=0, corner_radius=0
    )
    pestañas.pack(fill="both", expand=True, padx=8, pady=(2, 4))
    tab_importar = pestañas.add("Importar Excel")
    tab_manual = pestañas.add("Cargar manual")
    tab_pedidos = pestañas.add("Pedidos")
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
        ("Pedidos", "📦  Pedidos"),
        ("Arqueo", "▤  Arqueo"),
        ("Importar Excel", "▣  Importar Excel"),
        ("Historial", "Historial"),
    ):
        boton = ctk.CTkButton(
            navegacion, text=etiqueta_nav, width=(190 if perfil["nombre"] == "full-hd" else 150), height=(42 if perfil["nombre"] == "full-hd" else 30), corner_radius=0,
            fg_color="transparent", hover_color=color_panel_alto,
            text_color=color_suave, font=ctk.CTkFont(size=(14 if perfil["nombre"] == "full-hd" else 11), weight="bold"),
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
    items_venta = []
    item_editando = {"index": None}

    cabecera = ctk.CTkFrame(tab_manual, fg_color=color_panel, corner_radius=7)
    cabecera.pack(fill="x", padx=4, pady=(2, 2))
    cabecera.grid_propagate(False)
    cabecera.grid_columnconfigure(7, weight=1)
    ctk.CTkLabel(
        cabecera, text="RESUMEN DE CAJA", text_color=COLOR_TEXTO_SUAVE,
        font=ctk.CTkFont(size=10, weight="bold")
    ).grid(row=0, column=0, sticky="w", padx=(10, 8), pady=4)

    controles_cabecera = [
        ("fecha", "Fecha", 130),
        ("unidad", "Sucursal", 130),
        ("caja_inicial", "Caja inicial", 150),
    ]
    for indice, (clave, etiqueta, ancho) in enumerate(controles_cabecera):
        ctk.CTkLabel(cabecera, text=etiqueta, text_color=COLOR_TEXTO_SUAVE).grid(
            row=0, column=indice * 2 + 1, sticky="w", padx=(4, 3), pady=4
        )
        if clave == "unidad":
            campo = ctk.CTkComboBox(cabecera, values=UNIDADES, width=ancho, height=max(27, perfil["campo_alto"]))
            campo.set(UNIDAD_POR_DEFECTO)
        else:
            campo = ctk.CTkEntry(cabecera, width=ancho, height=max(27, perfil["campo_alto"]))
        campo.grid(row=0, column=indice * 2 + 2, padx=(0, 8), pady=4)
        campos_manual[clave] = campo
    campos_manual["fecha"].insert(0, date.today().strftime("%d-%m-%Y"))

    columnas_operativas = COLUMNAS_OPERATIVAS

    formulario = ctk.CTkFrame(tab_manual, fg_color="transparent", corner_radius=0)
    columnas_bloque = 3
    for columna in range(columnas_bloque):
        formulario.grid_columnconfigure(columna, weight=1, uniform="bloques_operador")

    secciones_formulario = (
        ("1", "CLIENTE Y COMPROBANTE", (
            ("descripcion", "Cliente", 185), ("cliente_telefono", "Teléfono", 140),
            ("cliente_documento", "CI / RUC", 100), ("sobre", "Sobre / Trabajo", 100),
            ("fecha_entrega", "Fecha de entrega", 150), ("vendedora", "Vendedora *", 140),
        )),
        ("2", "DETALLE DE VENTA", PRODUCTO_TRABAJO),
        ("3", "PAGO", COBRO_PAGO + (("notas", "Observaciones", 220),)),
    )
    secciones_widgets = {}
    for indice_seccion, (numero, titulo, columnas) in enumerate(secciones_formulario):
        seccion = ctk.CTkFrame(
            formulario, fg_color="#F7FAFF", corner_radius=10,
            border_width=2, border_color="#8FB3D9",
        )
        secciones_widgets[titulo] = seccion
        fila_bloque = 0
        columna_bloque = indice_seccion
        seccion.grid(row=fila_bloque, column=columna_bloque, sticky="nsew", padx=6, pady=2)
        formulario.grid_rowconfigure(fila_bloque, weight=1)
        seccion.grid_columnconfigure(0, weight=0, minsize=(116 if perfil["nombre"] == "full-hd" else 90))
        seccion.grid_columnconfigure(1, weight=1)
        es_pago = titulo == "PAGO"
        if es_pago:
            seccion.grid_columnconfigure(2, weight=0, minsize=(116 if perfil["nombre"] == "full-hd" else 90))
            seccion.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(
            seccion, text=numero, width=18, height=18, corner_radius=9,
            fg_color=color_azul, text_color="#FFFFFF",
            font=ctk.CTkFont(size=10, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(10, 0), pady=(8, 4))
        ctk.CTkLabel(
            seccion, text=titulo, height=22, text_color=color_texto, anchor="w",
            font=ctk.CTkFont(size=perfil["fuente_seccion"], weight="bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=(38, 10), pady=(8, 4))
        for indice_campo, (clave, etiqueta, ancho) in enumerate(columnas):
            if es_pago and clave not in ("saldo", "notas"):
                fila_campo = 1 + (indice_campo // 2)
                columna_etiqueta = (indice_campo % 2) * 2
                columna_campo = columna_etiqueta + 1
                expansion = 1
            elif es_pago:
                fila_campo = 4 if clave == "saldo" else 5
                columna_etiqueta = 2 if clave == "saldo" else 0
                columna_campo = 3 if clave == "saldo" else 1
                expansion = 1 if clave == "saldo" else 3
            else:
                fila_campo = indice_campo + 1
                columna_etiqueta = 0
                columna_campo = 1
                expansion = 1
            ctk.CTkLabel(
                seccion, text=etiqueta, height=perfil["campo_alto"], text_color=color_suave, anchor="w",
                font=ctk.CTkFont(size=perfil["fuente_label"], weight="bold"),
            ).grid(row=fila_campo, column=columna_etiqueta, sticky="ew", padx=(10, 5), pady=2)
            if clave == "vendedora":
                campo = ctk.CTkComboBox(
                    seccion, values=["Seleccionar...", "Ana", "Belén", "Carla", "Diana"],
                    width=ancho, height=perfil["campo_alto"], fg_color="#FFFFFF",
                    border_color=color_borde_suave,
                )
                campo.set("Seleccionar...")
            else:
                campo = ctk.CTkEntry(
                    seccion, width=ancho, height=perfil["campo_alto"], fg_color="#FFFFFF",
                    border_width=1, border_color=color_borde_suave, text_color=color_texto,
                    font=ctk.CTkFont(size=perfil["fuente"]),
                )
            campo.grid(
                row=fila_campo, column=columna_campo, columnspan=expansion,
                sticky="ew", padx=(0, 10), pady=2,
            )
            campos_manual[clave] = campo

    campos_manual["notas"].configure(placeholder_text="Observaciones de la operación")
    campos_manual["fecha_entrega"].configure(placeholder_text="dd-mm-aaaa")

    zona_secundaria = ctk.CTkFrame(tab_manual, fg_color="#F8FAFD", corner_radius=7,
                                   border_width=1, border_color=color_borde_suave)
    ctk.CTkLabel(zona_secundaria, text="OPERACIONES SECUNDARIAS", text_color=color_suave,
                 font=ctk.CTkFont(size=perfil["fuente_label"], weight="bold")).pack(side="left", padx=(10, 8))
    campos_manual["gasto_descripcion"] = ctk.CTkEntry(
        zona_secundaria, width=220, height=perfil["campo_alto"], placeholder_text="Descripción del gasto"
    )
    campos_manual["gasto_descripcion"].pack(side="left", padx=4, pady=5)
    campos_manual["gasto_monto"] = ctk.CTkEntry(
        zona_secundaria, width=125, height=perfil["campo_alto"], placeholder_text="Monto"
    )
    campos_manual["gasto_monto"].pack(side="left", padx=4, pady=5)
    campos_manual["accion_gasto"] = ctk.CTkButton(
        zona_secundaria, text="Guardar gasto", width=120, height=perfil["campo_alto"],
        fg_color="#FFF7ED", text_color="#B45309", border_width=1,
        border_color="#F2C69F", hover_color="#FFEBD7",
    )
    campos_manual["accion_gasto"].pack(side="left", padx=4, pady=5)

    # El draft es una zona propia: nunca cuenta como movimiento persistido.
    lista_productos = ctk.CTkFrame(tab_manual, fg_color="#F7FAFF", corner_radius=9,
                                   border_width=2, border_color="#8FB3D9")
    ctk.CTkLabel(lista_productos, text="VENTA EN CURSO", text_color=color_texto,
                 font=ctk.CTkFont(size=perfil["fuente_seccion"], weight="bold")).place(x=12, y=6)
    cuerpo_draft = ctk.CTkFrame(lista_productos, fg_color="transparent")
    cuerpo_draft.pack(fill="both", expand=True, padx=8, pady=(28, 6))
    cuerpo_draft.grid_columnconfigure(0, weight=5)
    cuerpo_draft.grid_columnconfigure(
        1, weight=2, minsize=(230 if perfil["nombre"] == "full-hd" else 175)
    )
    cuerpo_draft.grid_rowconfigure(0, weight=1)
    panel_items = ctk.CTkFrame(cuerpo_draft, fg_color="transparent")
    panel_items.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    panel_items.grid_rowconfigure(0, weight=1)
    panel_items.grid_columnconfigure(0, weight=1)
    columnas_items = ("producto", "codigo", "tipo", "armazon", "cristal", "subtotal")
    grilla_items = ttk.Treeview(
        panel_items, columns=columnas_items, show="headings", height=2,
        style="Draft.Treeview",
    )
    for clave, titulo, ancho in (
        ("producto", "Artículo", 220), ("codigo", "Código", 90),
        ("tipo", "Tipo", 115), ("armazon", "P. Armazón", 100),
        ("cristal", "P. Cristal", 100), ("subtotal", "Subtotal", 110),
    ):
        grilla_items.heading(clave, text=titulo)
        anchor = "e" if clave in ("armazon", "cristal", "subtotal") else "w"
        grilla_items.column(
            clave, width=ancho, minwidth=70, anchor=anchor,
            stretch=clave == "producto",
        )
    scroll_items = ttk.Scrollbar(panel_items, orient="vertical", command=grilla_items.yview)
    grilla_items.configure(yscrollcommand=scroll_items.set)
    grilla_items.grid(row=0, column=0, sticky="nsew")
    scroll_items.grid(row=0, column=1, sticky="ns")
    acciones_item = ctk.CTkFrame(lista_productos, fg_color="transparent")
    acciones_item.place(relx=0.52, y=3, anchor="ne")
    panel_total_draft = ctk.CTkFrame(
        cuerpo_draft, fg_color="#E7F1FC", corner_radius=8,
        border_width=1, border_color="#7DA9D7",
    )
    panel_total_draft.grid(row=0, column=1, sticky="nsew")
    ctk.CTkLabel(
        panel_total_draft, text="TOTAL DE LA VENTA", text_color="#42627F",
        font=ctk.CTkFont(size=perfil["fuente_label"], weight="bold"),
    ).pack(padx=8, pady=(10, 2))
    total_draft_var = ctk.StringVar(value="0")
    ctk.CTkLabel(
        panel_total_draft, textvariable=total_draft_var, text_color="#0F5FB9",
        font=ctk.CTkFont(
            size=(22 if perfil["nombre"] == "full-hd" else 17), weight="bold"
        ),
    ).pack(padx=8, pady=(0, 8))

    bloque_producto = formulario
    columna_guardar = None
    claves_operacion = tuple(
        clave for clave in (
            "descripcion", "cliente_telefono", "cliente_documento", "sobre",
            "fecha_entrega", "vendedora", "arm_org", "cod", "laboratorio",
            "armazon", "cristal", "receta_dr", "total", "efectivo",
            "tarjeta_cheque", "transferencia", "ordenes", "monto_convenio",
            "cuotas", "saldo", "notas",
        ) if clave in campos_manual
    )
    orden_teclado = list(claves_operacion)
    for indice, clave in enumerate(orden_teclado[:-1]):
        siguiente = orden_teclado[indice + 1]
        campos_manual[clave].bind(
            "<Return>", lambda _event, destino=siguiente: campos_manual[destino].focus_set()
        )

    estado_operativo = ctk.CTkFrame(cabecera, fg_color="transparent")
    estado_operativo.grid(row=0, column=7, sticky="e", padx=8, pady=4)
    zona_estado = ctk.CTkFrame(tab_manual, fg_color="transparent")

    estado_caja = ctk.CTkLabel(
        estado_operativo, text="SIN CONSULTAR", width=120, height=20, corner_radius=5,
        fg_color=color_panel_alto, text_color=COLOR_TEXTO_SUAVE,
        font=ctk.CTkFont(size=9, weight="bold"),
    )
    estado_caja.pack(side="left", padx=(0, 5))
    boton_cerrar_caja = ctk.CTkButton(
        estado_operativo, text="Cerrar caja", width=92, height=24,
        fg_color="#B42318", hover_color="#8F1C13", state="disabled",
        command=lambda: cerrar_caja(),
    )
    boton_cerrar_caja.pack(side="left")
    etiquetas_kpi = {}
    for clave, titulo, color in (
        ("ventas", "VENTA TOTAL DEL DÍA", color_azul),
        ("efectivo", "EFECTIVO", color_verde),
        ("saldo", "SALDO CLIENTE", "#E5484D"),
        ("convenio", "A COBRAR CONVENIO", "#7C3AED"),
    ):
        tarjeta = ctk.CTkFrame(
            zona_estado, width=(perfil["contenido_ancho"] - 40) // 4,
            height=(48 if perfil["nombre"] == "full-hd" else 36), fg_color="#FFFFFF", corner_radius=7,
            border_width=1, border_color=color,
        )
        tarjeta.pack(side="left", padx=4, pady=2)
        tarjeta.pack_propagate(False)
        iconos_kpi = {
            "ventas": "▤", "efectivo": "▭", "saldo": "△",
        }
        ctk.CTkLabel(
            tarjeta, text=f"{iconos_kpi.get(clave, '◇')}   {titulo}", text_color=color_suave,
            font=ctk.CTkFont(size=perfil["fuente"], weight="bold"),
        ).pack(side="left", padx=(12, 6), pady=3)
        valor = ctk.CTkLabel(
            tarjeta, text="—", text_color=color,
            font=ctk.CTkFont(size=perfil["fuente_kpi"], weight="bold"),
        )
        valor.pack(side="right", padx=(6, 12), pady=3)
        etiquetas_kpi[clave] = valor
    def formatear_campo_monetario(clave):
        campo = campos_manual[clave]
        texto = formatear_importe_ui(campo.get())
        if texto != campo.get():
            escribir_importe_formateado(campo, texto)

    def recalcular_total_visible(_event=None):
        if items_venta:
            total = sum(item.subtotal for item in items_venta)
            total_draft_var.set(formatear_monto(total))
            campo_total = campos_manual["total"]
            campo_total.delete(0, "end")
            campo_total.insert(0, formatear_importe_ui(total))
            recalcular_saldo_visible()
            return
        try:
            total = sumar_importes_formulario(
                campos_manual["armazon"].get(), campos_manual["cristal"].get()
            )
        except (TypeError, ValueError):
            return
        total_draft_var.set(formatear_monto(total))
        campo_total = campos_manual["total"]
        campo_total.delete(0, "end")
        campo_total.insert(0, formatear_importe_ui(total))
        recalcular_saldo_visible()

    def refrescar_items():
        for row in grilla_items.get_children():
            grilla_items.delete(row)
        for index, item in enumerate(items_venta):
            grilla_items.insert("", "end", iid=str(index), values=(
                item.description, item.code, item.item_type,
                formatear_monto(item.frame_price or 0),
                formatear_monto(item.lens_price or 0),
                formatear_monto(item.subtotal),
            ))
        recalcular_total_visible()
        try:
            refrescar_grilla(controller.load_day(
                campos_manual["fecha"].get().strip(), campos_manual["unidad"].get().strip()
            ))
        except (NameError, Exception):
            pass

    def agregar_producto():
        try:
            item = construir_item_producto_visible(
                {clave: campos_manual[clave].get() for clave in (
                    "arm_org", "cod", "armazon", "cristal", "laboratorio", "receta_dr"
                )}
            )
            if item.subtotal <= 0:
                raise ValueError("El producto debe tener un precio de armazón o cristal.")
        except Exception as exc:
            messagebox.showwarning("Producto inválido", str(exc), parent=ventana)
            return
        index = item_editando["index"]
        if index is None:
            items_venta.append(item)
        else:
            items_venta[index] = replace(item, id=items_venta[index].id)
            item_editando["index"] = None
        for clave in ("arm_org", "cod", "armazon", "cristal", "laboratorio", "receta_dr"):
            campos_manual[clave].delete(0, "end")
        refrescar_items()

    def editar_item():
        selected = grilla_items.selection()
        if not selected:
            return
        index = int(selected[0]); item = items_venta[index]; item_editando["index"] = index
        values = {"arm_org": item.item_type, "cod": item.code, "armazon": item.frame_price,
                  "cristal": item.lens_price, "laboratorio": item.laboratory,
                  "receta_dr": item.prescription_doctor}
        for clave, value in values.items():
            campos_manual[clave].delete(0, "end"); campos_manual[clave].insert(0, "" if value is None else str(value))

    def quitar_item():
        selected = grilla_items.selection()
        if selected:
            items_venta.pop(int(selected[0])); item_editando["index"] = None; refrescar_items()

    detalle_venta = secciones_widgets["DETALLE DE VENTA"]
    boton_agregar_articulo = ctk.CTkButton(
        detalle_venta, text="+ Agregar artículo", height=perfil["campo_alto"],
        command=agregar_producto, fg_color="#1672E8", hover_color="#0F5FC7",
        font=ctk.CTkFont(size=perfil["fuente"], weight="bold"),
    )
    boton_agregar_articulo.grid(
        row=7, column=0, columnspan=2, sticky="ew", padx=10, pady=(5, 9)
    )
    ctk.CTkButton(
        acciones_item, text="Editar artículo seleccionado", width=165, height=22,
        command=editar_item,
    ).pack(side="left", padx=(0, 3))
    ctk.CTkButton(
        acciones_item, text="Quitar", width=70, height=22,
        command=quitar_item, fg_color="#D9534F",
    ).pack(side="left", padx=1)

    def recalcular_saldo_visible(_event=None):
        try:
            saldo = calcular_saldo_pendiente(
                campos_manual["total"].get(), campos_manual["efectivo"].get(),
                campos_manual["tarjeta_cheque"].get(), campos_manual["transferencia"].get(),
                campos_manual["monto_convenio"].get(),
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
    for clave in ("total", "efectivo", "tarjeta_cheque", "transferencia", "monto_convenio"):
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
        font=ctk.CTkFont(size=(18 if perfil["nombre"] == "full-hd" else 14), weight="bold"),
    ).pack(side="left", padx=12)
    entrada_busqueda = ctk.CTkEntry(
        toolbar_movimientos, textvariable=busqueda_movimientos,
        placeholder_text="Buscar movimiento…", width=(290 if perfil["nombre"] == "full-hd" else 205), height=(38 if perfil["nombre"] == "full-hd" else 28),
        fg_color="#F7F9FC", border_color=color_borde_suave,
    )
    entrada_busqueda.pack(side="left", padx=(8, 6), pady=6)
    botones_filtro = {}
    for nombre_filtro in ("Todos", "Ventas", "Gastos", "Pendientes"):
        boton_filtro = ctk.CTkButton(
            toolbar_movimientos, text=nombre_filtro, width=(82 if perfil["nombre"] == "full-hd" else 68), height=(38 if perfil["nombre"] == "full-hd" else 28),
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
        "Caja.Treeview", rowheight=perfil["fila"], font=("Segoe UI", perfil["fuente"]),
        background="#FFFFFF", fieldbackground="#FFFFFF", foreground="#24324A",
        borderwidth=0, relief="flat",
    )
    estilo.map(
        "Caja.Treeview",
        background=[("selected", "#245DA8")],
        foreground=[("selected", "#FFFFFF")],
    )
    estilo.configure(
        "Caja.Treeview.Heading", font=("Segoe UI", perfil["fuente"], "bold"),
        background="#EDF3FA", foreground="#33425B", relief="flat", padding=(4, 5),
    )
    estilo.map("Caja.Treeview.Heading", background=[("active", "#245DA8")])
    estilo.configure(
        "Draft.Treeview", rowheight=(27 if perfil["nombre"] == "full-hd" else 22),
        font=("Segoe UI", perfil["fuente"]), background="#FFFFFF",
        fieldbackground="#FFFFFF", foreground="#24324A", borderwidth=0,
    )
    estilo.configure(
        "Draft.Treeview.Heading", font=("Segoe UI", perfil["fuente"], "bold"),
        background="#EDF3FA", foreground="#33425B", relief="flat", padding=(3, 2),
    )
    claves_grilla = [clave for clave, _, _ in columnas_operativas] + ["acciones"]
    grilla_caja = ttk.Treeview(
        marco_grilla, columns=claves_grilla, show="headings", style="Caja.Treeview"
    )
    for clave, etiqueta, ancho, anchor in MOVEMENT_COLUMN_SPECS:
        grilla_caja.heading(clave, text=etiqueta, anchor=anchor)
        ancho_perfil = int(ancho * (1.24 if perfil["nombre"] == "full-hd" else 1.0))
        grilla_caja.column(
            clave, width=ancho_perfil, minwidth=65, stretch=False, anchor=anchor
        )
    grilla_caja.heading("acciones", text="Acciones", anchor="center")
    grilla_caja.column("acciones", width=105, minwidth=105, stretch=False, anchor="center")
    grilla_caja.tag_configure("voided", foreground="#E0717C", background="#241824")
    grilla_caja.tag_configure("expense", foreground="#F5A3AA")
    grilla_caja.tag_configure("pending", foreground="#3B2A05", background="#FFF3CD")
    grilla_caja.tag_configure("draft", foreground="#174A7E", background="#EAF3FF")
    grilla_caja.tag_configure("draft_item", foreground="#42627F", background="#F5F9FE")
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
            f"Retiros  {formatear_monto(totales.withdrawals)}    "
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

    def tiene_saldo_cliente(entry):
        return entry.client_balance_amount > 0

    def valores_fila(entry):
        importe = lambda value: formatear_monto(value or 0)
        item_count = len(entry.effective_items)
        resumen = f"{item_count} producto{'s' if item_count != 1 else ''}"
        if entry.withdrawal:
            resumen = f"Retiro · {entry.withdrawal_destination or entry.description}"
        elif entry.expenses:
            resumen = f"Gasto · {entry.description}"
        estado_fila = "ANULADO" if entry.status.value == "VOIDED" else "PENDIENTE" if tiene_saldo_cliente(entry) else "COBRADO"
        return (
            entry.created_at.astimezone(BUSINESS_TIMEZONE).strftime("%H:%M"),
            entry.description, entry.customer_phone, resumen, entry.envelope,
            importe(entry.total), importe(entry.cash), importe(entry.card_check),
            importe(entry.agreement_amount), entry.installments,
            importe(entry.client_balance_amount), entry.saleswoman, estado_fila,
            "Editar · Anular",
        )
    def refrescar_grilla(cash_day):
        for item in grilla_caja.get_children():
            grilla_caja.delete(item)
        consulta = busqueda_movimientos.get().strip().casefold()
        filtro = filtro_movimientos.get()
        for entry in cash_day.entries:
            if consulta and consulta not in " ".join(str(value) for value in valores_fila(entry)).casefold():
                continue
            if filtro == "Ventas" and ((entry.expenses or 0) > 0 or (entry.withdrawal or 0) > 0):
                continue
            if filtro == "Gastos" and not (entry.expenses or 0):
                continue
            if filtro == "Pendientes" and not tiene_saldo_cliente(entry):
                continue
            if entry.status.value == "VOIDED":
                tags = ("voided",)
            elif entry.expenses or entry.withdrawal:
                tags = ("expense",)
            elif tiene_saldo_cliente(entry):
                tags = ("pending",)
            else:
                tags = ()
            values = list(valores_fila(entry))
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
        cobrar_convenio = 0
        for entry in cash_day.entries:
            if entry.status.value != "ACTIVE":
                continue
            try:
                saldo_pendiente += entry.client_balance_amount
                cobrar_convenio += entry.agreement_amount or 0
            except (TypeError, ValueError):
                pass
        mostrar_importe = lambda value: privacidad.display(formatear_monto(value))
        escribir_importe_formateado(campos_manual["caja_inicial"], cash_day.opening_cash)
        etiquetas_kpi["ventas"].configure(text=mostrar_importe(totales.total))
        etiquetas_kpi["efectivo"].configure(text=mostrar_importe(totales.cash))
        etiquetas_kpi["saldo"].configure(text=mostrar_importe(saldo_pendiente))
        etiquetas_kpi["convenio"].configure(text=mostrar_importe(cobrar_convenio))
        refrescar_grilla(cash_day)
        estado_control = "normal" if cash_day.status.value == "OPEN" else "disabled"
        estado_edicion["caja_abierta"] = cash_day.status.value == "OPEN"
        boton_cerrar_caja.configure(state="normal" if abierta else "disabled")
        for clave in claves_operacion:
            campos_manual[clave].configure(state=estado_control)
        campos_manual["transferencia"].configure(state=estado_control)
        campos_manual["notas"].configure(state=estado_control)
        campos_manual["cliente_documento"].configure(state=estado_control)
        campos_manual["cliente_telefono"].configure(state=estado_control)
        campos_manual["fecha_entrega"].configure(state=estado_control)
        campos_manual["vendedora"].configure(state=estado_control)
        campos_manual["gasto_descripcion"].configure(state=estado_control)
        campos_manual["gasto_monto"].configure(state=estado_control)
        boton_guardar.configure(state=estado_control)
        boton_gasto.configure(state=estado_control)

    def abrir_o_consultar():
        try:
            cash_day, aviso = controller.open_or_load_day_with_notice(
                campos_manual["fecha"].get().strip(),
                campos_manual["unidad"].get().strip(),
                campos_manual["caja_inicial"].get().strip(),
            )
        except Exception as exc:
            mostrar_error(exc)
            return
        actualizar_estado(cash_day)
        diferencia = controller.opening_difference_message(cash_day)
        if diferencia:
            messagebox.showwarning("Diferencia de apertura", diferencia, parent=ventana)
        if aviso:
            messagebox.showinfo("Caja existente", aviso, parent=ventana)
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
        for clave in claves_operacion:
            if clave != "vendedora":
                campos_manual[clave].delete(0, "end")
        campos_manual["notas"].delete(0, "end")
        for clave in ("cliente_documento", "cliente_telefono", "fecha_entrega"):
            campos_manual[clave].delete(0, "end")
        campos_manual["vendedora"].set("Seleccionar...")
        items_venta.clear()
        item_editando["index"] = None
        refrescar_items()
        campos_manual["descripcion"].focus_set()

    def guardar_manual():
        if estado_edicion["guardando"]:
            return
        estado_edicion["guardando"] = True
        boton_guardar.configure(state="disabled")
        try:
            recalcular_total_visible()
            recalcular_saldo_visible()
            valores = leer_valores_formulario(campos_manual)
            if not items_venta:
                if estado_edicion["entry_id"]:
                    raise ValueError(
                        "La venta editada no puede quedar sin productos. "
                        "Cancelá la edición o anulá la venta completa."
                    )
                items_venta[:] = completar_items_para_guardar(valores, items_venta)
                refrescar_items()
                valores = leer_valores_formulario(campos_manual)
            valores["items"] = tuple(items_venta)
            valores["tarjeta_cheque"] = str(sumar_medios_no_efectivo(
                valores["tarjeta_cheque"], valores["transferencia"]
            ))
            if estado_edicion["entry_id"]:
                motivo_edicion = simpledialog.askstring(
                    "Edición auditada", "Motivo obligatorio de la edición:", parent=ventana
                )
                if not str(motivo_edicion or "").strip():
                    return
                responsable = os.environ.get("USERNAME") or os.environ.get("USER") or ""
                if not responsable:
                    responsable = simpledialog.askstring(
                        "Edición auditada", "Usuario responsable:", parent=ventana
                    )
                if not str(responsable or "").strip():
                    return
                cash_day, _ = controller.update_manual_entry(
                    estado_edicion["entry_id"], valores,
                    reason=motivo_edicion, user=responsable,
                )
            else:
                cash_day, _ = controller.add_manual_entry(valores)
        except Exception as exc:
            mostrar_error_guardado(exc, ventana)
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
        "ordenes": "orders", "monto_convenio": "agreement_amount",
        "cuotas": "installments", "saldo": "balance",
        "gastos": "expenses", "notas": "source_reference",
        "cliente_documento": "customer_document", "cliente_telefono": "customer_phone", "vendedora": "saleswoman",
        "fecha_entrega": "delivery_date",
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
        cargar_para_editar(cash_day, entry)


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
    def alternar_privacidad():
        privacidad.show() if privacidad.hidden else privacidad.hide()
        boton_privacidad.configure(text="👁 Mostrar totales" if privacidad.hidden else "👁 Ocultar totales")
        refrescar_estado_consultado()
        refrescar_items()

    def aplicar_privacidad_campos():
        # El modo privacidad sólo afecta KPIs globales, nunca la operación en curso.
        return None

    boton_privacidad = ctk.CTkButton(
        barra_superior, text="👁 Ocultar totales", width=145, height=28,
        fg_color="transparent", text_color="#FFFFFF", border_width=1,
        border_color="#8EB9EA", hover_color="#0B4D98", command=alternar_privacidad,
    )
    boton_privacidad.pack(side="right", padx=6)

    def registrar_actividad(_event=None):
        privacidad.activity()

    def revisar_auto_privacidad():
        estaba_oculta = privacidad.hidden
        if privacidad.check_timeout() and not estaba_oculta:
            boton_privacidad.configure(text="👁 Mostrar totales")
            refrescar_estado_consultado()
            refrescar_items()
        ventana.after(1000, revisar_auto_privacidad)

    for evento in ("<KeyPress>", "<Button>", "<Motion>"):
        ventana.bind_all(evento, registrar_actividad, add="+")
    ventana.after(1000, revisar_auto_privacidad)
    pago = secciones_widgets["PAGO"]
    boton_guardar = ctk.CTkButton(
        pago, text="Guardar venta  —  F9", command=guardar_manual,
        height=perfil["campo_alto"], fg_color=color_azul, hover_color="#0F5FC7",
        font=ctk.CTkFont(size=perfil["fuente"], weight="bold"),
    )
    boton_guardar.grid(
        row=6, column=0, columnspan=4, sticky="ew", padx=10, pady=(5, 9)
    )
    ctk.CTkButton(
        acciones_primarias, text="Limpiar", command=limpiar_operacion, width=100, height=32,
        fg_color="#FFFFFF", text_color=color_texto, border_width=1,
        border_color=color_borde_suave, hover_color="#F1F5FA",
    ).pack(side="left", padx=4, pady=3)
    def guardar_gasto_integrado():
        try:
            cash_day, _ = controller.add_expense(
                campos_manual["fecha"].get().strip(),
                campos_manual["unidad"].get().strip(),
                campos_manual["gasto_descripcion"].get(),
                campos_manual["gasto_monto"].get(),
                campos_manual["notas"].get(),
            )
        except Exception as exc:
            mostrar_error(exc)
            return
        actualizar_estado(cash_day)
        campos_manual["gasto_descripcion"].delete(0, "end")
        campos_manual["gasto_monto"].delete(0, "end")
        messagebox.showinfo("Gasto guardado", "El gasto se registró en la Caja.", parent=ventana)

    boton_gasto = campos_manual["accion_gasto"]
    boton_gasto.configure(command=guardar_gasto_integrado)
    campos_manual["gasto_monto"].bind(
        "<Return>", lambda _event: guardar_gasto_integrado()
    )
    def registrar_retiro():
        monto = simpledialog.askstring("Entrega a Administración", "Monto *", parent=ventana)
        if monto is None:
            return
        destino = simpledialog.askstring(
            "Entrega a Administración", "Destino", initialvalue="Administración", parent=ventana
        )
        if destino is None:
            return
        observacion = simpledialog.askstring(
            "Entrega a Administración", "Observación (opcional)", parent=ventana
        ) or ""
        try:
            cash_day, _ = controller.add_withdrawal(
                campos_manual["fecha"].get().strip(), campos_manual["unidad"].get().strip(),
                monto, destino, observacion,
            )
        except Exception as exc:
            mostrar_error(exc)
            return
        actualizar_estado(cash_day)
        messagebox.showinfo("Retiro guardado", "La entrega quedó registrada.", parent=ventana)

    ctk.CTkButton(
        acciones_primarias, text="Entrega a Administración", command=registrar_retiro,
        width=170, height=32, fg_color="#6B5B95",
    ).pack(side="left", padx=4, pady=3)
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
    grilla_items.bind("<MouseWheel>", lambda event: (
        grilla_items.yview_scroll(-1 if event.delta > 0 else 1, "units"), "break"
    )[1], add="+")
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
        cabecera, zona_estado, formulario, lista_productos, zona_secundaria,
        toolbar_movimientos, marco_grilla, pie_movimientos, acciones, pie,
    ):
        bloque.pack_forget()
    ancho_total = min(perfil["contenido_ancho"], ancho_logico - 22)
    y_cabecera = 4
    es_full_hd = perfil["nombre"] == "full-hd"
    alto_cabecera = 52 if es_full_hd else 36
    alto_kpi = 48 if es_full_hd else 36
    alto_form = 310 if es_full_hd else 210
    alto_draft = 220 if es_full_hd else 160
    alto_secundario = 40 if es_full_hd else 36
    faltante_vertical = 0 if es_full_hd else max(0, 768 - alto_logico)
    separacion_vertical = 5 if es_full_hd else (0 if faltante_vertical else 3)
    reduccion_grilla = max(0, faltante_vertical - (15 if faltante_vertical else 0))
    alto_grilla = 220 if es_full_hd else max(140, 167 - reduccion_grilla)
    y_kpi = y_cabecera + alto_cabecera + separacion_vertical
    y_form = y_kpi + alto_kpi + separacion_vertical
    y_draft = y_form + alto_form + separacion_vertical
    y_secundario = y_draft + alto_draft + separacion_vertical
    y_toolbar = y_secundario if not es_full_hd else y_secundario + alto_secundario + separacion_vertical
    y_grilla = (
        y_secundario + alto_secundario + separacion_vertical
        if not es_full_hd else y_toolbar + perfil["toolbar_alto"]
    )
    cabecera.configure(width=ancho_total, height=alto_cabecera)
    cabecera.place(x=4, y=4)
    zona_estado.configure(width=ancho_total, height=alto_kpi)
    zona_estado.place(x=4, y=y_kpi)
    formulario.configure(width=ancho_total, height=alto_form)
    formulario.grid_propagate(False)
    formulario.place(x=4, y=y_form)
    lista_productos.configure(width=ancho_total, height=alto_draft)
    lista_productos.pack_propagate(False)
    lista_productos.place(x=4, y=y_draft)
    zona_secundaria.configure(
        width=(500 if not es_full_hd else ancho_total), height=alto_secundario
    )
    zona_secundaria.pack_propagate(False)
    zona_secundaria.place(x=4, y=y_secundario)
    acciones.configure(width=(280 if not es_full_hd else 500), height=alto_secundario)
    acciones.pack_propagate(False)
    acciones.place(x=(504 if not es_full_hd else ancho_total - 496), y=y_secundario)
    toolbar_movimientos.configure(
        width=(ancho_total - 774 if not es_full_hd else ancho_total),
        height=(alto_secundario if not es_full_hd else perfil["toolbar_alto"]),
    )
    toolbar_movimientos.place(x=(774 if not es_full_hd else 4), y=y_toolbar)
    if not es_full_hd:
        campos_manual["gasto_descripcion"].configure(width=160)
        campos_manual["gasto_monto"].configure(width=90)
        boton_gasto.configure(width=100)
        entrada_busqueda.configure(width=130)
        for boton in botones_filtro.values():
            boton.configure(width=55)
    marco_grilla.configure(width=ancho_total, height=alto_grilla)
    marco_grilla.grid_propagate(False)
    marco_grilla.place(x=4, y=y_grilla)
    alto_pie = perfil["acciones_alto"] if es_full_hd else 28
    pie_movimientos.configure(width=ancho_total, height=alto_pie)
    pie_movimientos.place(x=4, y=y_grilla + alto_grilla + 3)
    pie.configure(width=ancho_total - 8, height=24 if perfil["nombre"] == "full-hd" else 18)
    pie.place(
        x=(8 if es_full_hd else ancho_total // 2),
        y=(y_grilla + alto_grilla + alto_pie + 5 if es_full_hd else y_grilla + alto_grilla + 7),
    )
    estado_layout = {"after": None, "metricas": {}}

    def aplicar_macro_layout():
        """Recalcula posiciones con el area cliente Tk ya renderizada."""
        estado_layout["after"] = None
        ventana.update_idletasks()
        ancho_cliente = max(1, tab_manual.winfo_width())
        alto_cliente = max(1, tab_manual.winfo_height())
        ancho_actual = min(perfil["contenido_ancho"], ancho_cliente - 8)
        x_actual = max(4, (ancho_cliente - ancho_actual) // 2)
        full_hd_actual = ancho_cliente >= 1700 and alto_cliente >= 850
        if full_hd_actual:
            alto_cab, alto_tot = 52, 48
            form_preferido, form_minimo = 310, 280
            draft_preferido, draft_minimo = 220, 110
            alto_sec, sep = 40, 5
        else:
            alto_cab, alto_tot = 34, 34
            form_preferido, form_minimo = 198, 158
            draft_preferido, draft_minimo = 160, 80
            alto_sec, sep = 32, 1
        margen_inferior = 4
        alto_pie_actual = max(26, pie_movimientos.winfo_reqheight())
        fila_renderizada = int(estilo.lookup("Caja.Treeview", "rowheight"))
        alto_grilla_minimo = 46 + (5 * fila_renderizada) + scroll_horizontal.winfo_reqheight() + 4
        extra_toolbar = alto_sec + sep + perfil["toolbar_alto"] if full_hd_actual else alto_sec + sep
        fijos_sin_form_draft = 4 + alto_cab + sep + alto_tot + sep + sep + extra_toolbar
        presupuesto_form_draft = max(
            form_minimo + draft_minimo,
            alto_cliente - alto_pie_actual - margen_inferior - 2
            - alto_grilla_minimo - fijos_sin_form_draft,
        )
        alto_form_actual = min(
            form_preferido,
            max(form_minimo, presupuesto_form_draft - draft_minimo),
        )
        draft_actual = min(
            draft_preferido,
            max(draft_minimo, presupuesto_form_draft - alto_form_actual),
        )
        y_cab = 4
        y_tot = y_cab + alto_cab + sep
        y_form_actual = y_tot + alto_tot + sep
        y_draft_actual = y_form_actual + alto_form_actual + sep
        y_sec = y_draft_actual + draft_actual + sep
        y_toolbar_actual = y_sec if not full_hd_actual else y_sec + alto_sec + sep
        y_grid = y_sec + alto_sec + sep if not full_hd_actual else y_toolbar_actual + perfil["toolbar_alto"]
        y_footer = alto_cliente - alto_pie_actual - margen_inferior
        alto_grid = max(1, y_footer - 2 - y_grid)
        cabecera.configure(width=ancho_actual, height=alto_cab); cabecera.place(x=x_actual, y=y_cab)
        zona_estado.configure(width=ancho_actual, height=alto_tot); zona_estado.place(x=x_actual, y=y_tot)
        formulario.configure(width=ancho_actual, height=alto_form_actual); formulario.place(x=x_actual, y=y_form_actual)
        lista_productos.configure(width=ancho_actual, height=draft_actual); lista_productos.place(x=x_actual, y=y_draft_actual)
        zona_secundaria.configure(width=(500 if not full_hd_actual else ancho_actual), height=alto_sec); zona_secundaria.place(x=x_actual, y=y_sec)
        acciones.configure(width=(280 if not full_hd_actual else 500), height=alto_sec); acciones.place(x=(x_actual + 500 if not full_hd_actual else x_actual + ancho_actual - 500), y=y_sec)
        toolbar_movimientos.configure(width=(ancho_actual - 780 if not full_hd_actual else ancho_actual), height=(alto_sec if not full_hd_actual else perfil["toolbar_alto"])); toolbar_movimientos.place(x=(x_actual + 780 if not full_hd_actual else x_actual), y=y_toolbar_actual)
        marco_grilla.configure(width=ancho_actual, height=alto_grid); marco_grilla.place(x=x_actual, y=y_grid)
        pie_movimientos.configure(width=ancho_actual, height=alto_pie_actual); pie_movimientos.place(x=x_actual, y=y_footer)
        pie.configure(width=ancho_actual // 2 - 8, height=alto_pie_actual - 4); pie.place(x=x_actual + ancho_actual // 2, y=y_footer + 2)
        estado_layout["metricas"] = {"cliente": (ancho_cliente, alto_cliente), "grilla_y": y_grid, "grilla_alto": alto_grid, "pie_y": y_footer, "pie_alto": alto_pie_actual, "footer_bottom": y_footer + alto_pie_actual, "required": y_footer + alto_pie_actual + margen_inferior, "draft_alto": draft_actual, "overflow": max(0, y_footer + alto_pie_actual + margen_inferior - alto_cliente)}

    def programar_macro_layout(_event=None):
        if estado_layout["after"] is not None:
            ventana.after_cancel(estado_layout["after"])
        estado_layout["after"] = ventana.after_idle(aplicar_macro_layout)

    tab_manual.bind("<Configure>", programar_macro_layout, add="+")
    ventana.after_idle(aplicar_macro_layout)
    def actualizar_reloj():
        if reloj.winfo_exists():
            reloj.configure(text=datetime.now().strftime("%H:%M:%S"))
            ventana.after(1000, actualizar_reloj)

    actualizar_reloj()
    # ---- Arqueo ----
    superior = ctk.CTkFrame(
        tab_arqueo, fg_color="#FFFFFF", corner_radius=8,
        border_width=1, border_color=color_borde_suave,
    )
    superior.pack(fill="x", padx=12, pady=(10, 6))
    ctk.CTkLabel(superior, text="Resumen esperado", font=ctk.CTkFont(size=14, weight="bold")).pack(
        side="left", padx=12, pady=10
    )
    entrada_fecha = ctk.CTkEntry(superior, width=120)
    entrada_fecha.insert(0, date.today().strftime("%d-%m-%Y"))
    entrada_fecha.pack(side="left", padx=6)
    combo_unidad_arqueo = ctk.CTkComboBox(superior, values=UNIDADES, width=140)
    combo_unidad_arqueo.set(UNIDAD_POR_DEFECTO)
    combo_unidad_arqueo.pack(side="left", padx=6)
    etiqueta_esperado = ctk.CTkLabel(
        superior, text="Efectivo esperado por sistema: —",
        font=ctk.CTkFont(size=13, weight="bold"), text_color=color_azul,
    )
    etiqueta_esperado.pack(side="right", padx=16)

    cuerpo_arqueo = ctk.CTkFrame(tab_arqueo, fg_color="transparent")
    cuerpo_arqueo.pack(fill="both", expand=True, padx=12, pady=4)
    cuerpo_arqueo.grid_columnconfigure(0, weight=3)
    cuerpo_arqueo.grid_columnconfigure(1, weight=2)

    conteo_frame = ctk.CTkFrame(
        cuerpo_arqueo, fg_color="#FFFFFF", corner_radius=8,
        border_width=1, border_color=color_borde_suave,
    )
    conteo_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    ctk.CTkLabel(
        conteo_frame, text="Conteo físico", font=ctk.CTkFont(size=14, weight="bold")
    ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(8, 4))
    for columna, titulo in enumerate(("Denominación", "Cantidad", "Subtotal")):
        ctk.CTkLabel(
            conteo_frame, text=titulo, text_color=color_suave,
            font=ctk.CTkFont(size=9, weight="bold"),
        ).grid(row=1, column=columna, padx=12, pady=2, sticky="w")

    campos_conteo = {}
    etiquetas_subtotal = {}
    estado_arqueo = {"esperado": None}
    for indice, denominacion in enumerate(DENOMINACIONES, start=2):
        ctk.CTkLabel(conteo_frame, text=formatear_monto(denominacion)).grid(
            row=indice, column=0, sticky="w", padx=12, pady=2
        )
        campo = ctk.CTkEntry(conteo_frame, width=100, height=25, placeholder_text="0")
        campo.grid(row=indice, column=1, padx=12, pady=2)
        subtotal = ctk.CTkLabel(conteo_frame, text="0", width=120, anchor="e")
        subtotal.grid(row=indice, column=2, padx=12, pady=2, sticky="e")
        campos_conteo[denominacion] = campo
        etiquetas_subtotal[denominacion] = subtotal

    resultado_frame = ctk.CTkFrame(
        cuerpo_arqueo, fg_color="#FFFFFF", corner_radius=8,
        border_width=1, border_color=color_borde_suave,
    )
    resultado_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    ctk.CTkLabel(
        resultado_frame, text="Resultado del arqueo",
        font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(anchor="w", padx=16, pady=(14, 10))
    etiqueta_contado = ctk.CTkLabel(resultado_frame, text="Efectivo contado: 0", anchor="w")
    etiqueta_contado.pack(fill="x", padx=16, pady=5)
    etiqueta_diferencia = ctk.CTkLabel(resultado_frame, text="Diferencia: —", anchor="w")
    etiqueta_diferencia.pack(fill="x", padx=16, pady=5)
    etiqueta_estado_arqueo = ctk.CTkLabel(
        resultado_frame, text="Consultá una caja", anchor="w", justify="left",
        corner_radius=6, fg_color="#EEF3F8",
    )
    etiqueta_estado_arqueo.pack(fill="x", padx=16, pady=(10, 16), ipady=10)

    def cantidades_arqueo():
        cantidades = {}
        for denominacion, campo in campos_conteo.items():
            texto = campo.get().strip() or "0"
            cantidades[denominacion] = int(texto)
        return cantidades

    def actualizar_previsualizacion(_event=None):
        try:
            cantidades = cantidades_arqueo()
        except ValueError:
            etiqueta_estado_arqueo.configure(
                text="Revisá las cantidades", fg_color="#FFF1F2", text_color=COLOR_ROJO
            )
            return
        contado = sum(denominacion * cantidad for denominacion, cantidad in cantidades.items())
        for denominacion, cantidad in cantidades.items():
            etiquetas_subtotal[denominacion].configure(
                text=formatear_monto(denominacion * cantidad)
            )
        etiqueta_contado.configure(text=f"Efectivo contado: {formatear_monto(contado)}")
        esperado = estado_arqueo["esperado"]
        if esperado is None:
            return
        diferencia = contado - esperado
        estado_texto, detalle = describir_diferencia_arqueo(diferencia)
        etiqueta_diferencia.configure(
            text=f"Diferencia: {formatear_diferencia_ui(diferencia)}"
        )
        etiqueta_estado_arqueo.configure(
            text=f"{estado_texto}\n{detalle}",
            fg_color="#EAF8F1" if diferencia == 0 else "#FFF7E6",
            text_color=color_verde if diferencia == 0 else "#B45309",
        )

    def consultar_arqueo():
        try:
            cash_day = controller.load_day(
                entrada_fecha.get().strip(), combo_unidad_arqueo.get().strip()
            )
        except Exception as exc:
            mostrar_error(exc)
            return
        estado_arqueo["esperado"] = cash_day.totals().expected_cash
        etiqueta_esperado.configure(
            text="Efectivo esperado por sistema: "
            + formatear_monto(estado_arqueo["esperado"])
        )
        actualizar_previsualizacion()

    def guardar_arqueo():
        try:
            resultado = controller.record_cash_count(
                entrada_fecha.get().strip(), combo_unidad_arqueo.get().strip(),
                cantidades_arqueo(),
            )
        except Exception as exc:
            mostrar_error(exc)
            return
        estado_arqueo["esperado"] = resultado.expected_total
        actualizar_previsualizacion()
        if resultado.difference:
            messagebox.showwarning(
                "Arqueo con diferencia",
                describir_diferencia_arqueo(resultado.difference)[1]
                + ". El arqueo fue guardado correctamente.",
                parent=ventana,
            )
        else:
            messagebox.showinfo(
                "Arqueo conforme", "El arqueo fue guardado correctamente.", parent=ventana
            )

    for campo in campos_conteo.values():
        campo.bind("<KeyRelease>", actualizar_previsualizacion, add="+")

    botones_arqueo = ctk.CTkFrame(resultado_frame, fg_color="transparent")
    botones_arqueo.pack(fill="x", padx=12, pady=8)
    ctk.CTkButton(
        botones_arqueo, text="Consultar caja", command=consultar_arqueo,
        fg_color="#FFFFFF", text_color=color_texto, border_width=1,
        border_color=color_borde_suave,
    ).pack(side="left", padx=4)
    ctk.CTkButton(
        botones_arqueo, text="Guardar arqueo", command=guardar_arqueo,
        fg_color=COLOR_PRIMARIO, hover_color=COLOR_PRIMARIO_HOVER,
    ).pack(side="left", padx=4)
    # ---- Historial / edición / anulación ----
    filtros_historial = ctk.CTkFrame(tab_historial, fg_color="transparent")
    filtros_historial.pack(fill="x", padx=8, pady=8)
    ctk.CTkLabel(filtros_historial, text="Desde").pack(side="left")
    entrada_historial = ctk.CTkEntry(filtros_historial, width=105)
    entrada_historial.insert(0, date.today().strftime("%d-%m-%Y"))
    entrada_historial.pack(side="left", padx=(4, 8))
    ctk.CTkLabel(filtros_historial, text="Hasta").pack(side="left")
    entrada_historial_hasta = ctk.CTkEntry(filtros_historial, width=105)
    entrada_historial_hasta.insert(0, date.today().strftime("%d-%m-%Y"))
    entrada_historial_hasta.pack(side="left", padx=(4, 8))
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
        if cash_day.status.value != "OPEN" or entry.status.value != "ACTIVE":
            messagebox.showwarning(
                "No editable", "La fila está cerrada o anulada.", parent=ventana
            )
            return
        valores = {
            "fecha": cash_day.business_date.strftime("%d-%m-%Y"),
            "unidad": cash_day.unit,
            "caja_inicial": cash_day.opening_cash,
            "descripcion": entry.description,
            "sobre": entry.envelope,
            "arm_org": entry.frame_origin,
            "cod": entry.code,
            "armazon": entry.frame,
            "cristal": entry.lens,
            "laboratorio": entry.laboratory,
            "receta_dr": entry.prescription_doctor,
            "total": entry.total,
            "efectivo": entry.cash,
            "tarjeta_cheque": entry.card_check,
            "ordenes": entry.orders,
            "monto_convenio": entry.agreement_amount,
            "cuotas": entry.installments,
            "saldo": entry.balance,
            "gastos": entry.expenses,
            "notas": entry.observations or entry.source_reference,
            "cliente_documento": entry.customer_document,
            "cliente_telefono": entry.customer_phone,
            "vendedora": entry.saleswoman,
            "fecha_entrega": (
                entry.delivery_date.strftime("%d-%m-%Y") if entry.delivery_date else ""
            ),
        }
        for clave, valor in valores.items():
            if clave not in campos_manual:
                continue
            campo = campos_manual[clave]
            if clave in ("unidad", "vendedora"):
                campo.set("" if valor is None else str(valor))
            else:
                campo.delete(0, "end")
                campo.insert(
                    0,
                    formatear_importe_ui(valor)
                    if clave in CAMPOS_MONETARIOS_UI else "" if valor is None else str(valor),
                )
        estado_edicion["entry_id"] = entry.id
        items_venta[:] = list(entry.effective_items)
        item_editando["index"] = None
        refrescar_items()
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

    def editar_caja(cash_day):
        nuevo = simpledialog.askinteger(
            "Editar caja", "Nueva caja inicial:", initialvalue=cash_day.opening_cash,
            minvalue=0, parent=ventana,
        )
        if nuevo is None or nuevo == cash_day.opening_cash:
            return
        motivo = simpledialog.askstring(
            "Corrección auditada", "Motivo obligatorio:", parent=ventana
        )
        if not motivo:
            messagebox.showwarning("Motivo requerido", "La corrección no fue guardada.", parent=ventana)
            return
        usuario = simpledialog.askstring(
            "Corrección auditada", "Usuario responsable:", parent=ventana
        )
        if not usuario:
            return
        try:
            controller.correct_opening_cash(
                cash_day.business_date.strftime("%d-%m-%Y"), cash_day.unit,
                nuevo, motivo, usuario,
            )
        except Exception as exc:
            mostrar_error(exc)
            return
        consultar_historial()

    def consultar_historial():
        try:
            cash_days = controller.list_history_range(
                entrada_historial.get().strip(), entrada_historial_hasta.get().strip(),
                unidad_historial.get().strip(),
            )
        except Exception as exc:
            mostrar_error(exc)
            return
        for widget in lista_historial.winfo_children():
            widget.destroy()
        resumen_historial.configure(text=f"{len(cash_days)} jornadas en el período")
        for cash_day in cash_days:
            cabecera = ctk.CTkFrame(lista_historial, fg_color="#EAF3FF")
            cabecera.pack(fill="x", padx=4, pady=(7, 2))
            ctk.CTkLabel(
                cabecera,
                text=f"{cash_day.business_date.strftime('%d-%m-%Y')} · {texto_estado(cash_day)}",
                anchor="w", text_color="#174A7E",
            ).pack(side="left", fill="x", expand=True, padx=6)
            ctk.CTkButton(
                cabecera, text="Editar caja", width=90,
                command=lambda d=cash_day: editar_caja(d),
            ).pack(side="right", padx=4, pady=3)
            for entry in cash_day.entries:
                fila = ctk.CTkFrame(lista_historial, fg_color="transparent")
                fila.pack(fill="x", padx=12, pady=3)
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

    def rango_rapido(dias=None, mes=False):
        hoy = date.today()
        desde = hoy.replace(day=1) if mes else hoy - timedelta(days=(dias or 1) - 1)
        for campo, valor in ((entrada_historial, desde), (entrada_historial_hasta, hoy)):
            campo.delete(0, "end")
            campo.insert(0, valor.strftime("%d-%m-%Y"))
        consultar_historial()

    for texto, comando in (
        ("Hoy", lambda: rango_rapido(1)),
        ("7 días", lambda: rango_rapido(7)),
        ("Este mes", lambda: rango_rapido(mes=True)),
    ):
        ctk.CTkButton(
            filtros_historial, text=texto, width=68, command=comando,
            fg_color="#FFFFFF", text_color=color_texto, border_width=1,
            border_color=color_borde_suave,
        ).pack(side="right", padx=2)

    ctk.CTkButton(
        filtros_historial,
        text="Consultar",
        command=consultar_historial,
        fg_color=COLOR_PRIMARIO,
        hover_color=COLOR_PRIMARIO_HOVER,
    ).pack(side="left", padx=8)

    # ---- Pedidos V1 (estado central; Caja es solamente el primer origen) ----
    barra_pedidos = ctk.CTkFrame(tab_pedidos, fg_color="transparent")
    barra_pedidos.pack(fill="x", padx=10, pady=10)
    filtro_pedidos = ctk.StringVar(value="Hoy")
    marco_pedidos = ctk.CTkFrame(tab_pedidos, fg_color="#FFFFFF")
    marco_pedidos.pack(fill="both", expand=True, padx=10, pady=(0, 8))
    columnas_pedido = ("entrega", "cliente", "telefono", "documento", "sobre", "sucursal", "vendedora", "origen", "estado")
    grilla_pedidos = ttk.Treeview(marco_pedidos, columns=columnas_pedido, show="headings", style="Caja.Treeview")
    for clave, titulo, ancho in (
        ("entrega", "Entrega", 100), ("cliente", "Cliente", 220),
        ("telefono", "Teléfono", 125),
        ("documento", "CI/RUC", 120), ("sobre", "Sobre", 75),
        ("sucursal", "Sucursal", 100), ("vendedora", "Vendedora", 120),
        ("origen", "Origen", 90), ("estado", "Estado", 110),
    ):
        grilla_pedidos.heading(clave, text=titulo)
        grilla_pedidos.column(clave, width=ancho, anchor="w")
    grilla_pedidos.pack(fill="both", expand=True, padx=5, pady=5)

    def refrescar_pedidos(nombre=None):
        if nombre:
            filtro_pedidos.set(nombre)
        for item in grilla_pedidos.get_children():
            grilla_pedidos.delete(item)
        for pedido in controller.list_orders(filtro_pedidos.get()):
            grilla_pedidos.insert("", "end", iid=pedido.id, values=(
                pedido.delivery_date.strftime("%d-%m-%Y"), pedido.customer_name,
                pedido.customer_phone, pedido.customer_document, pedido.envelope, pedido.branch,
                pedido.saleswoman, pedido.origin.value, pedido.status.value,
            ))

    for nombre in ("Hoy", "Atrasados", "Próximos", "Todos"):
        ctk.CTkButton(
            barra_pedidos, text=nombre, width=95,
            command=lambda valor=nombre: refrescar_pedidos(valor),
        ).pack(side="left", padx=3)

    def cambiar_estado_pedido(estado):
        seleccion = grilla_pedidos.selection()
        if not seleccion:
            messagebox.showwarning("Seleccioná un pedido", "Elegí una fila.", parent=ventana)
            return
        try:
            controller.update_order_status(seleccion[0], estado)
            refrescar_pedidos()
        except Exception as exc:
            mostrar_error(exc)

    ctk.CTkButton(barra_pedidos, text="Marcar listo", command=lambda: cambiar_estado_pedido("LISTO"), fg_color=color_verde).pack(side="right", padx=3)
    ctk.CTkButton(barra_pedidos, text="Marcar entregado", command=lambda: cambiar_estado_pedido("ENTREGADO"), fg_color=color_azul).pack(side="right", padx=3)

    aviso_entregas = ctk.CTkButton(
        acciones_primarias, text="", width=210, height=32, fg_color="#FFF7ED",
        text_color="#9A5B00", border_width=1, border_color="#F2C69F",
        command=lambda: (seleccionar_pestaña("Pedidos"), refrescar_pedidos("Hoy")),
    )

    def refrescar_avisos():
        hoy, atrasados = controller.order_counts()
        partes = []
        if hoy:
            partes.append(f"📦 {hoy} pedidos para entregar hoy")
        if atrasados:
            partes.append(f"⚠ {atrasados} pedidos atrasados")
        if partes:
            aviso_entregas.configure(text="  ·  ".join(partes))
            if not aviso_entregas.winfo_manager():
                aviso_entregas.pack(side="left", padx=8)
        else:
            aviso_entregas.pack_forget()

    refrescar_avisos()

    ventana.after(100, ventana.focus_set)
    return ventana
