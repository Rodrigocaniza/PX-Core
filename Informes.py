"""Informes mensuales de BC Gestión.

Este módulo reutiliza las funciones de cierre de ``Movimientos.py``. De esa
forma, la vista de Informes y el Cierre mensual siempre parten de los mismos
totales.
"""

from calendar import monthrange
from datetime import datetime
from pathlib import Path
import re

from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

import Movimientos
from datos import leer_datos


COLOR_FONDO = ("#F4F7FB", "#0B1220")
COLOR_PANEL = ("#FFFFFF", "#131D2E")
COLOR_PANEL_SECUNDARIO = ("#EAF0F7", "#1A2639")
COLOR_BORDE = ("#DCE4EE", "#26354A")
COLOR_TEXTO = ("#182230", "#F4F7FB")
COLOR_TEXTO_SUAVE = ("#617084", "#9CAFC5")
COLOR_PRIMARIO = "#246BFD"
COLOR_PRIMARIO_HOVER = "#1855D6"
COLOR_VERDE = "#18A874"
COLOR_ROJO = "#E25555"
COLOR_NARANJA = "#E99A35"


def nombre_archivo_seguro(informe, extension):
    """Crea un nombre breve y válido para Windows."""
    unidad = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        informe["unidad"],
    ).strip("_")
    unidad = unidad or "Empresa"
    return (
        f"Informe_BC_{informe['periodo'].replace('-', '_')}_"
        f"{unidad}.{extension}"
    )


def resumir_detalles_por_dia(detalles):
    """Agrupa cada fecha por unidad o categoría, con entradas y salidas."""
    agrupados = {}

    for registro in detalles:
        categoria = str(registro.get("categoria", "")).strip()
        unidad = str(registro.get("unidad", "")).strip()
        if categoria == "Operación diaria" and unidad not in ["", "General"]:
            grupo = unidad
        else:
            grupo = categoria or unidad or "Otros"

        clave = (registro["orden"], registro["fecha"], grupo)
        if clave not in agrupados:
            agrupados[clave] = {
                "orden": registro["orden"],
                "fecha": registro["fecha"],
                "grupo": grupo,
                "entradas": 0,
                "salidas": 0,
                "resultado": 0,
                "cantidad": 0,
            }

        fila = agrupados[clave]
        if registro["tipo"] == "Ingreso":
            fila["entradas"] += registro["monto"]
        elif registro["tipo"] == "Egreso":
            fila["salidas"] += registro["monto"]
        fila["cantidad"] += 1
        fila["resultado"] = fila["entradas"] - fila["salidas"]

    orden_unidades = {
        Movimientos.normalizar_texto(unidad): indice
        for indice, unidad in enumerate(Movimientos.UNIDADES)
    }

    def clave_orden(fila):
        grupo_normalizado = Movimientos.normalizar_texto(fila["grupo"])
        posicion = orden_unidades.get(
            grupo_normalizado,
            len(orden_unidades) + 1,
        )
        return (
            -fila["orden"].toordinal(),
            posicion,
            grupo_normalizado,
        )

    return sorted(agrupados.values(), key=clave_orden)


def exportar_excel(informe, ruta):
    """Exporta un informe visual, filtrable y verificable en Excel."""
    try:
        from openpyxl import Workbook
        from openpyxl.chart import DoughnutChart, Reference
        from openpyxl.chart.label import DataLabelList
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
        from openpyxl.worksheet.table import Table, TableStyleInfo
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Falta instalar openpyxl. Cerrá el sistema y volvé a abrir "
            "iniciar_interfaz.bat para completar la instalación."
        ) from error

    ruta = Path(ruta)
    libro = Workbook()
    resumen = libro.active
    resumen.title = "Resumen"

    azul = "246BFD"
    azul_oscuro = "173B73"
    verde = "18A874"
    rojo = "E25555"
    naranja = "E99A35"
    gris = "EAF0F7"
    gris_claro = "F6F8FB"
    gris_texto = "617084"
    blanco = "FFFFFF"
    borde = Side(style="thin", color="DCE4EE")
    borde_fuerte = Side(style="medium", color="C8D4E3")
    formato_gs = '"Gs. "#,##0;[Red]-"Gs. "#,##0;"-"'

    def titulo_hoja(hoja, texto, ultima_columna):
        hoja.sheet_view.showGridLines = False
        hoja.merge_cells(
            start_row=1,
            start_column=1,
            end_row=1,
            end_column=ultima_columna,
        )
        celda = hoja.cell(1, 1, texto)
        celda.font = Font(
            name="Aptos Display",
            size=16,
            bold=True,
            color=blanco,
        )
        celda.fill = PatternFill("solid", fgColor=azul_oscuro)
        celda.alignment = Alignment(vertical="center")
        hoja.row_dimensions[1].height = 30

    def encabezado(hoja, fila, columnas):
        for columna, texto in enumerate(columnas, 1):
            celda = hoja.cell(fila, columna, texto)
            celda.font = Font(bold=True, color=blanco)
            celda.fill = PatternFill("solid", fgColor=azul)
            celda.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )
            celda.border = Border(bottom=borde)

    def ajustar_columnas(hoja, limites=None):
        limites = limites or {}
        for columna in range(1, hoja.max_column + 1):
            letra = get_column_letter(columna)
            mayor = 0
            for celda in hoja[letra]:
                valor = "" if celda.value is None else str(celda.value)
                mayor = max(mayor, len(valor))
            minimo, maximo = limites.get(columna, (11, 42))
            hoja.column_dimensions[letra].width = min(
                max(mayor + 2, minimo),
                maximo,
            )

    def preparar_impresion(hoja, orientacion="landscape"):
        hoja.page_setup.orientation = orientacion
        hoja.page_setup.paperSize = hoja.PAPERSIZE_A4
        hoja.page_setup.fitToWidth = 1
        hoja.page_setup.fitToHeight = 0
        hoja.sheet_properties.pageSetUpPr.fitToPage = True
        hoja.oddFooter.center.text = (
            f"BC Gestión - {informe['periodo']} - Página &P de &N"
        )
        hoja.oddFooter.center.size = 8
        hoja.oddFooter.center.color = gris_texto
        hoja.sheet_properties.outlinePr.summaryBelow = True

    def crear_tarjeta_excel(
        hoja,
        rango_titulo,
        rango_valor,
        titulo,
        valor,
        color,
        formato=formato_gs,
    ):
        hoja.merge_cells(rango_titulo)
        hoja.merge_cells(rango_valor)
        celda_titulo = hoja[rango_titulo.split(":")[0]]
        celda_valor = hoja[rango_valor.split(":")[0]]
        celda_titulo.value = titulo.upper()
        celda_valor.value = valor
        for fila in hoja[rango_titulo]:
            for celda in fila:
                celda.fill = PatternFill("solid", fgColor=gris_claro)
                celda.border = Border(
                    top=borde,
                    left=borde,
                    right=borde,
                )
        for fila in hoja[rango_valor]:
            for celda in fila:
                celda.fill = PatternFill("solid", fgColor=blanco)
                celda.border = Border(
                    bottom=borde_fuerte,
                    left=borde,
                    right=borde,
                )
        celda_titulo.font = Font(
            name="Aptos",
            size=9,
            bold=True,
            color=gris_texto,
        )
        celda_titulo.alignment = Alignment(
            horizontal="left",
            vertical="center",
        )
        celda_valor.font = Font(
            name="Aptos Display",
            size=15,
            bold=True,
            color=color,
        )
        celda_valor.alignment = Alignment(
            horizontal="left",
            vertical="center",
        )
        celda_valor.number_format = formato

    def agregar_tabla(hoja, referencia, nombre):
        tabla = Table(displayName=nombre, ref=referencia)
        tabla.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        hoja.add_table(tabla)

    # El resumen se diseña como un tablero de una sola página.
    titulo_hoja(
        resumen,
        f"BC Inversiones EAS - Informe {informe['periodo']}",
        12,
    )
    resumen.merge_cells("A2:C2")
    resumen["A2"] = f"VISTA: {informe['unidad']}"
    resumen.merge_cells("D2:F2")
    resumen["D2"] = f"PERÍODO: {informe['periodo']}"
    resumen.merge_cells("G2:L2")
    resumen["G2"] = f"GENERADO: {datetime.now():%d/%m/%Y %H:%M}"
    for celda in ("A2", "D2", "G2"):
        resumen[celda].font = Font(size=9, bold=True, color=gris_texto)

    crear_tarjeta_excel(
        resumen, "A4:C4", "A5:C6", "Ingresos",
        informe["ingresos"], verde,
    )
    crear_tarjeta_excel(
        resumen, "D4:F4", "D5:F6", "Egresos",
        informe["egresos"], rojo,
    )
    crear_tarjeta_excel(
        resumen, "G4:I4", "G5:I6", "Utilidad / resultado",
        "=A5-D5", verde if informe["utilidad"] >= 0 else rojo,
    )
    crear_tarjeta_excel(
        resumen, "J4:L4", "J5:L6", "Margen",
        "=IFERROR(G5/A5,0)", azul, "0.00%",
    )
    crear_tarjeta_excel(
        resumen, "A8:C8", "A9:C10", "Fondo",
        informe["fondo"] if informe["fondo"] is not None else 0,
        naranja,
    )
    crear_tarjeta_excel(
        resumen, "D8:F8", "D9:F10", "Inversiones",
        informe["inversiones"], "7B61FF",
    )
    crear_tarjeta_excel(
        resumen, "G8:I8", "G9:I10", "Salida real de dinero",
        informe["salida_caja"], rojo,
    )
    crear_tarjeta_excel(
        resumen, "J8:L8", "J9:L10",
        "Retenciones y otros descuentos",
        informe["retenciones"], naranja,
    )

    resumen.merge_cells("A12:L12")
    resumen["A12"] = "COMPOSICIÓN DE LOS EGRESOS"
    resumen["A12"].font = Font(
        name="Aptos Display",
        size=12,
        bold=True,
        color=azul_oscuro,
    )

    categorias_grafico = min(5, len(informe["categorias_egresos"]))
    fila_grafico_inicio = 14
    encabezado(resumen, 13, ["Categoría", "Monto", "%"])
    for indice in range(categorias_grafico):
        fila = fila_grafico_inicio + indice
        fila_origen = 3 + indice
        resumen.cell(
            fila,
            1,
            (
                f'=IF(LEN(\'Egresos\'!A{fila_origen})>26,'
                f'LEFT(\'Egresos\'!A{fila_origen},23)&"...",'
                f'\'Egresos\'!A{fila_origen})'
            ),
        )
        resumen.cell(fila, 2, f"='Egresos'!B{fila_origen}")
        resumen.cell(fila, 3, f"=IFERROR(B{fila}/$D$5,0)")
    if len(informe["categorias_egresos"]) > categorias_grafico:
        fila_otros = fila_grafico_inicio + categorias_grafico
        resumen.cell(fila_otros, 1, "Otros")
        resumen.cell(
            fila_otros,
            2,
            (
                f"=SUM('Egresos'!B{3 + categorias_grafico}:"
                f"B{2 + len(informe['categorias_egresos'])})"
            ),
        )
        resumen.cell(fila_otros, 3, f"=IFERROR(B{fila_otros}/$D$5,0)")
        cantidad_grafico = categorias_grafico + 1
    else:
        cantidad_grafico = categorias_grafico

    ultima_fila_grafico = fila_grafico_inicio + max(cantidad_grafico, 1) - 1
    for fila in range(fila_grafico_inicio, ultima_fila_grafico + 1):
        resumen.cell(fila, 2).number_format = formato_gs
        resumen.cell(fila, 3).number_format = "0.0%"
        if fila % 2 == 0:
            for columna in range(1, 4):
                resumen.cell(fila, columna).fill = PatternFill(
                    "solid",
                    fgColor=gris_claro,
                )

    if cantidad_grafico:
        grafico = DoughnutChart()
        datos = Reference(
            resumen,
            min_col=2,
            min_row=fila_grafico_inicio - 1,
            max_row=ultima_fila_grafico,
        )
        categorias = Reference(
            resumen,
            min_col=1,
            min_row=fila_grafico_inicio,
            max_row=ultima_fila_grafico,
        )
        grafico.add_data(datos, titles_from_data=True)
        grafico.set_categories(categorias)
        grafico.title = "Participación por categoría"
        grafico.style = 10
        grafico.holeSize = 58
        grafico.varyColors = True
        grafico.height = 7.2
        grafico.width = 13.2
        grafico.legend.position = "r"
        grafico.dataLabels = DataLabelList()
        grafico.dataLabels.showPercent = True
        grafico.dataLabels.showLeaderLines = True
        resumen.add_chart(grafico, "E13")

    resumen.merge_cells("A22:C22")
    resumen["A22"] = "CONTROL DEL INFORME"
    resumen["A22"].font = Font(bold=True, color=blanco)
    resumen["A22"].fill = PatternFill("solid", fgColor=azul)
    resumen["A23"] = "Total de egresos"
    resumen["B23"] = "=D5"
    resumen["A24"] = "Suma del desglose"
    if informe["categorias_egresos"]:
        ultima_fila_egresos = len(informe["categorias_egresos"]) + 2
        resumen["B24"] = (
            f"=SUM('Egresos'!B3:B{ultima_fila_egresos})"
        )
    else:
        resumen["B24"] = 0
    resumen["A25"] = "Estado"
    resumen["B25"] = '=IF(B23=B24,"OK","REVISAR")'
    for fila in (23, 24):
        resumen.cell(fila, 2).number_format = formato_gs
    resumen["B25"].font = Font(bold=True, color=verde)
    resumen.freeze_panes = "A4"
    for columna in range(1, 13):
        resumen.column_dimensions[get_column_letter(columna)].width = 12.5
    resumen.row_dimensions[1].height = 34
    resumen.row_dimensions[4].height = 21
    resumen.row_dimensions[5].height = 25
    resumen.row_dimensions[6].height = 18
    resumen.row_dimensions[8].height = 21
    resumen.row_dimensions[9].height = 25
    resumen.row_dimensions[10].height = 18
    resumen.print_area = "A1:L26"
    preparar_impresion(resumen)

    def crear_hoja_categorias(nombre, categorias, color):
        hoja = libro.create_sheet(nombre)
        titulo_hoja(
            hoja,
            f"{nombre} por categoría - {informe['periodo']}",
            3,
        )
        encabezado(hoja, 2, ["Categoría", "Monto", "% del total"])
        fila_total = max(len(categorias) + 3, 3)
        for fila, (concepto, monto) in enumerate(categorias, 3):
            hoja.cell(fila, 1, concepto)
            hoja.cell(fila, 2, monto)
            hoja.cell(fila, 3, f"=IFERROR(B{fila}/$B${fila_total},0)")
            hoja.cell(fila, 2).number_format = formato_gs
            hoja.cell(fila, 3).number_format = "0.0%"
            hoja.cell(fila, 1).alignment = Alignment(
                wrap_text=True,
                vertical="top",
            )
            lineas = max(1, (len(str(concepto)) + 64) // 65)
            hoja.row_dimensions[fila].height = min(45, 15 * lineas)
            if fila % 2:
                for columna in range(1, 3):
                    hoja.cell(fila, columna).fill = PatternFill(
                        "solid",
                        fgColor="F6F8FB",
                    )

        hoja.cell(fila_total, 1, "TOTAL")
        if categorias:
            hoja.cell(
                fila_total,
                2,
                f"=SUM(B3:B{fila_total - 1})",
            )
        else:
            hoja.cell(fila_total, 2, 0)
        hoja.cell(fila_total, 2).number_format = formato_gs
        hoja.cell(fila_total, 3, 1 if categorias else 0)
        hoja.cell(fila_total, 3).number_format = "0.0%"
        for columna in range(1, 4):
            hoja.cell(fila_total, columna).font = Font(
                bold=True,
                color=blanco,
            )
            hoja.cell(fila_total, columna).fill = PatternFill(
                "solid",
                fgColor=color,
            )
        if categorias:
            agregar_tabla(
                hoja,
                f"A2:C{fila_total - 1}",
                f"Tabla{nombre}",
            )
        hoja.freeze_panes = "A3"
        ajustar_columnas(
            hoja,
            {1: (32, 58), 2: (18, 23), 3: (15, 18)},
        )
        hoja.print_title_rows = "1:2"
        preparar_impresion(hoja, "portrait")
        return hoja

    crear_hoja_categorias(
        "Egresos",
        informe["categorias_egresos"],
        rojo,
    )
    crear_hoja_categorias(
        "Ingresos",
        informe["categorias_ingresos"],
        verde,
    )

    comparacion = libro.create_sheet("Comparación")
    titulo_hoja(
        comparacion,
        f"Comparación por unidad - {informe['periodo']}",
        6,
    )
    encabezado(
        comparacion,
        2,
        [
            "Unidad",
            "Ingresos",
            "Egresos",
            "Resultado",
            "Transf. recibidas",
            "Transf. enviadas",
        ],
    )
    for fila, unidad in enumerate(informe["comparacion_unidades"], 3):
        valores = [
            unidad["unidad"],
            unidad["ingresos"],
            unidad["egresos"],
            unidad["resultado"],
            unidad["recibidas"],
            unidad["enviadas"],
        ]
        for columna, valor in enumerate(valores, 1):
            comparacion.cell(fila, columna, valor)
            if columna > 1:
                comparacion.cell(fila, columna).number_format = formato_gs
        if fila % 2:
            for columna in range(1, 7):
                comparacion.cell(fila, columna).fill = PatternFill(
                    "solid",
                    fgColor=gris_claro,
                )
    if informe["comparacion_unidades"]:
        agregar_tabla(
            comparacion,
            f"A2:F{len(informe['comparacion_unidades']) + 2}",
            "TablaComparacion",
        )
    comparacion.freeze_panes = "A3"
    ajustar_columnas(
        comparacion,
        {
            1: (16, 24),
            2: (16, 22),
            3: (16, 22),
            4: (16, 22),
            5: (18, 24),
            6: (18, 24),
        },
    )
    comparacion.print_title_rows = "1:2"
    preparar_impresion(comparacion)

    detalle = libro.create_sheet("Detalle diario")
    titulo_hoja(
        detalle,
        f"Detalle diario - {informe['periodo']} - {informe['unidad']}",
        5,
    )
    fila = 3
    fecha_actual = None
    total_entradas_dia = 0
    total_salidas_dia = 0

    def cerrar_dia(fila_destino):
        detalle.cell(fila_destino, 1, "TOTAL DEL DÍA")
        detalle.merge_cells(
            start_row=fila_destino,
            start_column=1,
            end_row=fila_destino,
            end_column=2,
        )
        detalle.cell(fila_destino, 3, total_entradas_dia)
        detalle.cell(fila_destino, 4, total_salidas_dia)
        detalle.cell(
            fila_destino,
            5,
            total_entradas_dia - total_salidas_dia,
        )
        for columna in range(1, 6):
            celda = detalle.cell(fila_destino, columna)
            celda.font = Font(bold=True, color=azul_oscuro)
            celda.fill = PatternFill("solid", fgColor=gris)
            celda.border = Border(top=borde_fuerte, bottom=borde)
            if columna >= 3:
                celda.number_format = formato_gs
        return fila_destino + 2

    for registro in informe["resumen_diario"]:
        if registro["fecha"] != fecha_actual:
            if fecha_actual is not None:
                fila = cerrar_dia(fila)
            fecha_actual = registro["fecha"]
            total_entradas_dia = 0
            total_salidas_dia = 0
            detalle.merge_cells(
                start_row=fila,
                start_column=1,
                end_row=fila,
                end_column=5,
            )
            celda_fecha = detalle.cell(fila, 1, str(fecha_actual))
            celda_fecha.font = Font(bold=True, color=blanco, size=11)
            celda_fecha.fill = PatternFill("solid", fgColor=azul_oscuro)
            celda_fecha.alignment = Alignment(vertical="center")
            detalle.row_dimensions[fila].height = 23
            fila += 1
            encabezado(
                detalle,
                fila,
                ["Categoría / unidad", "Movimientos", "Entró", "Salió", "Resultado"],
            )
            fila += 1

        valores = [
            registro["grupo"],
            registro["cantidad"],
            registro["entradas"],
            registro["salidas"],
            registro["resultado"],
        ]
        for columna, valor in enumerate(valores, 1):
            celda = detalle.cell(fila, columna, valor)
            celda.border = Border(bottom=borde)
            if columna >= 3:
                celda.number_format = formato_gs
                celda.alignment = Alignment(horizontal="right")
        if fila % 2:
            for columna in range(1, 6):
                detalle.cell(fila, columna).fill = PatternFill(
                    "solid",
                    fgColor=gris_claro,
                )
        total_entradas_dia += registro["entradas"]
        total_salidas_dia += registro["salidas"]
        fila += 1

    if fecha_actual is not None:
        fila = cerrar_dia(fila)

    detalle.freeze_panes = "A3"
    ajustar_columnas(
        detalle,
        {
            1: (24, 34),
            2: (14, 18),
            3: (18, 22),
            4: (18, 22),
            5: (18, 22),
        },
    )
    detalle.print_title_rows = "1:1"
    preparar_impresion(detalle)

    movimientos = libro.create_sheet("Movimientos")
    titulo_hoja(
        movimientos,
        f"Movimientos verificables - {informe['periodo']} - {informe['unidad']}",
        6,
    )
    encabezado(
        movimientos,
        2,
        ["Fecha", "Unidad", "Tipo", "Categoría", "Concepto / detalle", "Monto"],
    )
    for fila, registro in enumerate(informe["detalles"], 3):
        valores = [
            registro["fecha"],
            registro["unidad"],
            registro["tipo"],
            registro["categoria"],
            registro["detalle"],
            registro["monto"],
        ]
        for columna, valor in enumerate(valores, 1):
            movimientos.cell(fila, columna, valor)
        movimientos.cell(fila, 6).number_format = formato_gs
        movimientos.cell(fila, 4).alignment = Alignment(
            wrap_text=True,
            vertical="top",
        )
        movimientos.cell(fila, 5).alignment = Alignment(
            wrap_text=True,
            vertical="top",
        )
        lineas_categoria = (
            len(str(registro["categoria"])) + 27
        ) // 28
        lineas_detalle = (len(str(registro["detalle"])) + 59) // 60
        movimientos.row_dimensions[fila].height = min(
            45,
            15 * max(1, lineas_categoria, lineas_detalle),
        )
    if informe["detalles"]:
        agregar_tabla(
            movimientos,
            f"A2:F{len(informe['detalles']) + 2}",
            "TablaMovimientos",
        )
    movimientos.freeze_panes = "A3"
    ajustar_columnas(
        movimientos,
        {
            1: (13, 18),
            2: (13, 20),
            3: (12, 18),
            4: (16, 28),
            5: (32, 58),
            6: (18, 22),
        },
    )
    movimientos.print_title_rows = "1:2"
    preparar_impresion(movimientos)

    try:
        libro.calculation.fullCalcOnLoad = True
        libro.calculation.forceFullCalc = True
    except AttributeError:
        pass

    libro.save(ruta)
    return ruta


def exportar_pdf(informe, ruta):
    """Exporta un informe ejecutivo y un detalle legible en PDF."""
    try:
        from reportlab.lib import colors
        from reportlab.graphics.charts.piecharts import Pie
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            KeepTogether,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
        from xml.sax.saxutils import escape
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Falta instalar reportlab. Cerrá el sistema y volvé a abrir "
            "iniciar_interfaz.bat para completar la instalación."
        ) from error

    ruta = Path(ruta)
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloBC",
        parent=estilos["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#173B73"),
        alignment=TA_LEFT,
        spaceAfter=5,
    )
    subtitulo = ParagraphStyle(
        "SubtituloBC",
        parent=estilos["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#173B73"),
        spaceBefore=8,
        spaceAfter=6,
    )
    cuerpo = ParagraphStyle(
        "CuerpoBC",
        parent=estilos["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#182230"),
    )
    cuerpo_centrado = ParagraphStyle(
        "CuerpoCentradoBC",
        parent=cuerpo,
        alignment=1,
    )
    cuerpo_derecha = ParagraphStyle(
        "CuerpoDerechaBC",
        parent=cuerpo,
        alignment=TA_RIGHT,
    )
    fecha_estilo = ParagraphStyle(
        "FechaBC",
        parent=subtitulo,
        fontSize=10,
        leading=12,
        textColor=colors.white,
        backColor=colors.HexColor("#173B73"),
        borderPadding=(4, 6, 4, 6),
        spaceBefore=6,
        spaceAfter=0,
        keepWithNext=True,
    )

    documento = SimpleDocTemplate(
        str(ruta),
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=17 * mm,
        bottomMargin=15 * mm,
        title=f"Informe BC {informe['periodo']}",
        author="BC Inversiones EAS",
    )
    elementos = [
        Paragraph("BC Inversiones EAS", titulo),
        Paragraph(
            (
                f"Informe mensual {informe['periodo']} - "
                f"Vista: {informe['unidad']}"
            ),
            cuerpo,
        ),
        Spacer(1, 3 * mm),
    ]

    estilo_tabla = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#246BFD")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LEADING", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white,
                colors.HexColor("#F4F7FB"),
            ]),
            (
                "LINEBELOW",
                (0, 0),
                (-1, -1),
                0.35,
                colors.HexColor("#DCE4EE"),
            ),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )

    def tarjeta_pdf(nombre, valor, color):
        contenido = Paragraph(
            (
                f'<font color="#617084" size="7"><b>{escape(nombre.upper())}'
                f"</b></font><br/>"
                f'<font color="{color}" size="12"><b>{escape(valor)}</b></font>'
            ),
            cuerpo,
        )
        tabla = Table([[contenido]], colWidths=[62 * mm], rowHeights=[18 * mm])
        tabla.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        0.6,
                        colors.HexColor("#DCE4EE"),
                    ),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return tabla

    fondo_texto = (
        formatear_monto(informe["fondo"])
        if informe["fondo"] is not None
        else "No aplica"
    )
    fila_kpi_1 = [
        tarjeta_pdf("Ingresos", formatear_monto(informe["ingresos"]), "#18A874"),
        tarjeta_pdf("Egresos", formatear_monto(informe["egresos"]), "#E25555"),
        tarjeta_pdf(
            "Utilidad / resultado",
            formatear_monto(informe["utilidad"]),
            "#18A874" if informe["utilidad"] >= 0 else "#E25555",
        ),
        tarjeta_pdf(
            "Margen",
            Movimientos.formatear_porcentaje(informe["margen"]) + "%",
            "#246BFD",
        ),
    ]
    fila_kpi_2 = [
        tarjeta_pdf("Fondo", fondo_texto, "#E99A35"),
        tarjeta_pdf(
            "Inversiones",
            formatear_monto(informe["inversiones"]),
            "#7B61FF",
        ),
        tarjeta_pdf(
            "Salida real de dinero",
            formatear_monto(informe["salida_caja"]),
            "#E25555",
        ),
        tarjeta_pdf(
            "Retenciones y otros descuentos",
            formatear_monto(informe["retenciones"]),
            "#E99A35",
        ),
    ]
    tabla_kpi = Table(
        [fila_kpi_1, fila_kpi_2],
        colWidths=[64 * mm] * 4,
        rowHeights=[20 * mm, 20 * mm],
        hAlign="LEFT",
    )
    tabla_kpi.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    elementos.extend(
        [
            tabla_kpi,
            Spacer(1, 3 * mm),
            Paragraph("Composición de los egresos", subtitulo),
        ]
    )

    # Gráfica de pastel con las cinco categorías principales y "Otros".
    categorias_principales = list(informe["categorias_egresos"][:5])
    if len(informe["categorias_egresos"]) > 5:
        categorias_principales.append(
            (
                "Otros",
                sum(monto for _nombre, monto in informe["categorias_egresos"][5:]),
            )
        )
    dibujo = Drawing(108 * mm, 72 * mm)
    pastel = Pie()
    pastel.x = 8 * mm
    pastel.y = 6 * mm
    pastel.width = 62 * mm
    pastel.height = 62 * mm
    pastel.data = [monto for _nombre, monto in categorias_principales] or [1]
    paleta = ["#246BFD", "#18A874", "#E99A35", "#7B61FF", "#E25555", "#8AA3C0"]
    for indice in range(len(pastel.data)):
        pastel.slices[indice].fillColor = colors.HexColor(
            paleta[indice % len(paleta)]
        )
        pastel.slices[indice].strokeColor = colors.white
        pastel.slices[indice].strokeWidth = 1
    dibujo.add(pastel)
    dibujo.add(
        String(
            34 * mm,
            1 * mm,
            "Participación por categoría",
            fontName="Helvetica-Bold",
            fontSize=9,
            textAnchor="middle",
            fillColor=colors.HexColor("#173B73"),
        )
    )

    leyenda_datos = [["Categoría", "Monto", "%"]]
    total_egresos = informe["egresos"] or 1
    for nombre, monto in categorias_principales:
        leyenda_datos.append(
            [
                Paragraph(escape(str(nombre)), cuerpo),
                Paragraph(formatear_monto(monto), cuerpo_derecha),
                Paragraph(f"{monto / total_egresos:.1%}", cuerpo_derecha),
            ]
        )
    tabla_leyenda = Table(
        leyenda_datos,
        colWidths=[78 * mm, 43 * mm, 18 * mm],
        repeatRows=1,
    )
    tabla_leyenda.setStyle(estilo_tabla)
    tabla_leyenda.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    bloque_grafico = Table(
        [[dibujo, tabla_leyenda]],
        colWidths=[112 * mm, 143 * mm],
        hAlign="LEFT",
    )
    bloque_grafico.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    elementos.extend([bloque_grafico, PageBreak()])

    comparacion_datos = [[
        "Unidad",
        "Ingresos",
        "Egresos",
        "Resultado",
        "Transf. recibidas",
        "Transf. enviadas",
    ]]
    for unidad in informe["comparacion_unidades"]:
        comparacion_datos.append(
            [
                unidad["unidad"],
                Movimientos.formatear_monto(unidad["ingresos"]),
                Movimientos.formatear_monto(unidad["egresos"]),
                Movimientos.formatear_monto(unidad["resultado"]),
                Movimientos.formatear_monto(unidad["recibidas"]),
                Movimientos.formatear_monto(unidad["enviadas"]),
            ]
        )
    tabla_comparacion = Table(
        comparacion_datos,
        colWidths=[35 * mm, 38 * mm, 38 * mm, 38 * mm, 43 * mm, 43 * mm],
        repeatRows=1,
    )
    tabla_comparacion.setStyle(estilo_tabla)
    tabla_comparacion.setStyle(
        TableStyle([("ALIGN", (1, 1), (-1, -1), "RIGHT")])
    )
    elementos.extend(
        [
            Paragraph("Resumen por unidad y categorías", titulo),
            Paragraph("Comparación por unidad", subtitulo),
            tabla_comparacion,
            Spacer(1, 4 * mm),
        ]
    )

    categorias = list(informe["categorias_egresos"])
    punto_medio = (len(categorias) + 1) // 2
    bloque_izquierdo = categorias[:punto_medio]
    bloque_derecho = categorias[punto_medio:]
    categorias_datos = [[
        "Categoría de egreso",
        "Monto",
        "Categoría de egreso",
        "Monto",
    ]]
    for indice in range(punto_medio):
        izquierda = bloque_izquierdo[indice]
        derecha = (
            bloque_derecho[indice]
            if indice < len(bloque_derecho)
            else ("", 0)
        )
        categorias_datos.append(
            [
                Paragraph(escape(str(izquierda[0])), cuerpo),
                Paragraph(formatear_monto(izquierda[1]), cuerpo_derecha),
                (
                    Paragraph(escape(str(derecha[0])), cuerpo)
                    if derecha[0]
                    else ""
                ),
                (
                    Paragraph(formatear_monto(derecha[1]), cuerpo_derecha)
                    if derecha[0]
                    else ""
                ),
            ]
        )
    categorias_datos.append(
        [
            Paragraph("<b>TOTAL</b>", cuerpo),
            Paragraph(
                f"<b>{escape(formatear_monto(informe['egresos']))}</b>",
                cuerpo_derecha,
            ),
            "",
            "",
        ]
    )
    tabla_categorias = Table(
        categorias_datos,
        colWidths=[84 * mm, 42 * mm, 84 * mm, 42 * mm],
        repeatRows=1,
    )
    tabla_categorias.setStyle(estilo_tabla)
    tabla_categorias.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("ALIGN", (3, 1), (3, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                (
                    "BACKGROUND",
                    (0, -1),
                    (-1, -1),
                    colors.HexColor("#EAF0F7"),
                ),
            ]
        )
    )
    elementos.extend(
        [
            Paragraph("Egresos por categoría", subtitulo),
            tabla_categorias,
            PageBreak(),
            Paragraph("Detalle por día", titulo),
            Paragraph(
                (
                    "Cada fecha muestra una sola fila por categoría o unidad, "
                    "con lo que entró, lo que salió y el resultado del día."
                ),
                cuerpo,
            ),
            Spacer(1, 2 * mm),
        ]
    )

    fecha_actual = None
    registros_dia = []

    def agregar_bloque_dia(fecha, registros):
        if not registros:
            return
        encabezado_fecha = Paragraph(escape(str(fecha)), fecha_estilo)
        datos = [[
            Paragraph("Categoría / unidad", cuerpo_centrado),
            Paragraph("Mov.", cuerpo_centrado),
            Paragraph("Entró", cuerpo_centrado),
            Paragraph("Salió", cuerpo_centrado),
            Paragraph("Resultado", cuerpo_centrado),
        ]]
        total_entradas = 0
        total_salidas = 0
        for registro in registros:
            datos.append(
                [
                    Paragraph(
                        f"<b>{escape(str(registro['grupo']))}</b>",
                        cuerpo,
                    ),
                    Paragraph(str(registro["cantidad"]), cuerpo_centrado),
                    Paragraph(
                        formatear_monto(registro["entradas"]),
                        cuerpo_derecha,
                    ),
                    Paragraph(
                        formatear_monto(registro["salidas"]),
                        cuerpo_derecha,
                    ),
                    Paragraph(
                        formatear_monto(registro["resultado"]),
                        cuerpo_derecha,
                    ),
                ]
            )
            total_entradas += registro["entradas"]
            total_salidas += registro["salidas"]
        datos.append(
            [
                Paragraph("<b>TOTAL DEL DÍA</b>", cuerpo),
                "",
                Paragraph(
                    f"<b>{escape(formatear_monto(total_entradas))}</b>",
                    cuerpo_derecha,
                ),
                Paragraph(
                    f"<b>{escape(formatear_monto(total_salidas))}</b>",
                    cuerpo_derecha,
                ),
                Paragraph(
                    f"<b>{escape(formatear_monto(total_entradas - total_salidas))}</b>",
                    cuerpo_derecha,
                ),
            ]
        )

        tabla = Table(
            datos,
            colWidths=[91 * mm, 22 * mm, 46 * mm, 46 * mm, 46 * mm],
            repeatRows=1,
        )
        tabla.setStyle(estilo_tabla)
        tabla.setStyle(
            TableStyle(
                [
                    ("ALIGN", (1, 1), (1, -1), "CENTER"),
                    ("ALIGN", (2, 1), (4, -1), "RIGHT"),
                    ("TEXTCOLOR", (2, 1), (2, -2), colors.HexColor("#18A874")),
                    ("TEXTCOLOR", (3, 1), (3, -2), colors.HexColor("#E25555")),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    (
                        "BACKGROUND",
                        (0, -1),
                        (-1, -1),
                        colors.HexColor("#EAF0F7"),
                    ),
                ]
            )
        )
        elementos.append(
            KeepTogether(
                [
                    encabezado_fecha,
                    tabla,
                    Spacer(1, 2 * mm),
                ]
            )
        )

    for registro in informe["resumen_diario"]:
        if fecha_actual is None:
            fecha_actual = registro["fecha"]
        if registro["fecha"] != fecha_actual:
            agregar_bloque_dia(fecha_actual, registros_dia)
            fecha_actual = registro["fecha"]
            registros_dia = []
        registros_dia.append(registro)
    agregar_bloque_dia(fecha_actual, registros_dia)

    def encabezado_pie(canvas, documento_actual):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#617084"))
        canvas.drawString(
            documento_actual.leftMargin,
            landscape(A4)[1] - 10 * mm,
            f"BC Gestión - Informe {informe['periodo']}",
        )
        canvas.drawRightString(
            landscape(A4)[0] - documento_actual.rightMargin,
            8 * mm,
            f"Página {documento_actual.page}",
        )
        canvas.restoreState()

    documento.build(
        elementos,
        onFirstPage=encabezado_pie,
        onLaterPages=encabezado_pie,
    )
    return ruta


def limites_periodo(periodo):
    """Convierte MM-AAAA en los límites completos del mes."""
    try:
        fecha = datetime.strptime(periodo.strip(), "%m-%Y")
    except ValueError as error:
        raise ValueError(
            "El período no es válido. Usá el formato MM-AAAA."
        ) from error

    ultimo_dia = monthrange(fecha.year, fecha.month)[1]
    return (
        datetime(fecha.year, fecha.month, 1),
        datetime(fecha.year, fecha.month, ultimo_dia),
    )


def formatear_monto(valor):
    return "Gs. " + Movimientos.formatear_monto(valor)


def fecha_en_rango(fecha_texto, fecha_desde, fecha_hasta):
    try:
        fecha = Movimientos.convertir_fecha(fecha_texto)
    except ValueError:
        return None

    if fecha_desde <= fecha <= fecha_hasta:
        return fecha
    return None


def agregar_categoria(diccionario, concepto, monto):
    if monto:
        diccionario[concepto] = diccionario.get(concepto, 0) + monto


def detalle_movimientos(
    fecha_desde,
    fecha_hasta,
    unidad_seleccionada,
    categorias_egresos,
    categorias_ingresos,
):
    """Obtiene movimientos que afectan ingresos o egresos del período."""
    detalles = []
    todas = unidad_seleccionada == "Empresa completa"
    unidad_normalizada = Movimientos.normalizar_texto(
        unidad_seleccionada
    )

    for linea in leer_datos(Movimientos.RUTA_MOVIMIENTOS):
        datos = Movimientos.separar_movimiento(linea)
        if datos is None:
            continue

        fecha = fecha_en_rango(
            datos["fecha"],
            fecha_desde,
            fecha_hasta,
        )
        if fecha is None:
            continue

        tipo = datos["tipo"]
        origen = Movimientos.normalizar_texto(datos["origen"])
        destino = Movimientos.normalizar_texto(datos["destino"])
        monto = datos["monto"]

        if tipo in ["Ingreso", "Cobro externo"]:
            if not todas and destino != unidad_normalizada:
                continue

            unidad = datos["destino"]
            agregar_categoria(
                categorias_ingresos,
                f"Ingresos operativos · {unidad}",
                monto,
            )
            detalle = (
                "Ingreso externo"
                if tipo == "Ingreso"
                else f"Cobro recibido en {datos['origen']}"
            )
            detalles.append(
                {
                    "orden": fecha,
                    "fecha": datos["fecha"],
                    "tipo": "Ingreso",
                    "categoria": "Operación diaria",
                    "detalle": detalle,
                    "unidad": unidad,
                    "monto": monto,
                }
            )

        elif tipo == "Egreso":
            if not todas and origen != unidad_normalizada:
                continue

            unidad = datos["origen"]
            agregar_categoria(
                categorias_egresos,
                f"Egresos operativos · {unidad}",
                monto,
            )
            detalles.append(
                {
                    "orden": fecha,
                    "fecha": datos["fecha"],
                    "tipo": "Egreso",
                    "categoria": "Operación diaria",
                    "detalle": "Egreso externo",
                    "unidad": unidad,
                    "monto": monto,
                }
            )

    return detalles


def detalle_componentes_generales(
    fecha_desde,
    fecha_hasta,
    categorias_egresos,
    categorias_ingresos,
):
    """Detalla conceptos generales que no tienen una unidad asignada."""
    detalles = []

    for linea in leer_datos(Movimientos.RUTA_ADICIONALES):
        datos = Movimientos.separar_adicional(linea)
        if datos is None:
            continue

        fecha = fecha_en_rango(
            datos["fecha"],
            fecha_desde,
            fecha_hasta,
        )
        if fecha is None:
            continue

        categoria = (
            categorias_ingresos
            if datos["tipo"] == "Ingreso"
            else categorias_egresos
        )
        agregar_categoria(
            categoria,
            f"Adicional · {datos['descripcion']}",
            datos["monto"],
        )
        observacion = datos.get("observacion", "").strip()
        detalles.append(
            {
                "orden": fecha,
                "fecha": datos["fecha"],
                "tipo": datos["tipo"],
                "categoria": "Adicional",
                "detalle": (
                    datos["descripcion"]
                    if observacion in ["", "-"]
                    else f"{datos['descripcion']} · {observacion}"
                ),
                "unidad": "General",
                "monto": datos["monto"],
            }
        )

    total_cuotas, detalle_cuotas = Movimientos.resumen_cuotas(
        fecha_desde,
        fecha_hasta,
    )
    agregar_categoria(
        categorias_egresos,
        "Cuotas de préstamos",
        total_cuotas,
    )
    for nombre, cuota in detalle_cuotas:
        fecha = fecha_en_rango(
            cuota["fecha"],
            fecha_desde,
            fecha_hasta,
        )
        if fecha is None:
            continue
        detalles.append(
            {
                "orden": fecha,
                "fecha": cuota["fecha"],
                "tipo": "Egreso",
                "categoria": "Préstamo",
                "detalle": f"{nombre} · Cuota {cuota['numero']}",
                "unidad": "General",
                "monto": cuota["monto"],
            }
        )

    nomina, detalle_nomina = Movimientos.resumen_nomina_liquidada(
        fecha_desde,
        fecha_hasta,
    )
    agregar_categoria(
        categorias_egresos,
        "Nómina",
        nomina["egreso_planilla"],
    )
    for liquidacion in detalle_nomina:
        detalles.append(
            {
                "orden": fecha_hasta,
                "fecha": liquidacion["periodo"],
                "tipo": "Egreso",
                "categoria": "Nómina",
                "detalle": liquidacion["nombre"],
                "unidad": "General",
                "monto": liquidacion["egreso_planilla"],
            }
        )

    return detalles


def obtener_comparacion_unidades(fecha_desde, fecha_hasta):
    comparacion = []
    for unidad in Movimientos.UNIDADES:
        (
            ingresos,
            egresos,
            resultado,
            recibidas,
            enviadas,
        ) = Movimientos.calcular_resumen_unidad(
            unidad,
            fecha_desde,
            fecha_hasta,
        )
        comparacion.append(
            {
                "unidad": unidad,
                "ingresos": ingresos,
                "egresos": egresos,
                "resultado": resultado,
                "recibidas": recibidas,
                "enviadas": enviadas,
            }
        )
    return comparacion


def obtener_informe(periodo, unidad_seleccionada="Empresa completa"):
    """Construye un informe mensual verificable y compatible con el cierre."""
    fecha_desde, fecha_hasta = limites_periodo(periodo)
    periodo_normalizado = fecha_desde.strftime("%m-%Y")
    categorias_egresos = {}
    categorias_ingresos = {}

    detalles = detalle_movimientos(
        fecha_desde,
        fecha_hasta,
        unidad_seleccionada,
        categorias_egresos,
        categorias_ingresos,
    )
    empresa_completa = unidad_seleccionada == "Empresa completa"

    if empresa_completa:
        indicadores = Movimientos.calcular_indicadores_cierre(
            fecha_desde,
            fecha_hasta,
        )
        detalles.extend(
            detalle_componentes_generales(
                fecha_desde,
                fecha_hasta,
                categorias_egresos,
                categorias_ingresos,
            )
        )
        ingresos = indicadores["ingresos"]
        egresos = indicadores["egresos"]
        utilidad = indicadores["utilidad_mes"]
        margen = indicadores["margen_porcentual"]
        salida_caja = indicadores["salida_caja_total"]
        retenciones = indicadores["diferencia_egreso_caja"]
        registro_fondo = Movimientos.obtener_registro_fondo(
            periodo_normalizado
        )
        fondo = (
            registro_fondo[1]["monto_aplicado"]
            if registro_fondo is not None
            else indicadores["fondo_calculado"]
        )
        fondo_estado = (
            registro_fondo[1]["modo"]
            if registro_fondo is not None
            else "CALCULADO"
        )
    else:
        (
            ingresos,
            egresos,
            utilidad,
            _recibidas,
            _enviadas,
        ) = Movimientos.calcular_resumen_unidad(
            unidad_seleccionada,
            fecha_desde,
            fecha_hasta,
        )
        margen = utilidad / ingresos * 100 if ingresos else 0
        salida_caja = egresos
        retenciones = 0
        fondo = None
        fondo_estado = "NO APLICA"

    total_categorias_ingreso = sum(categorias_ingresos.values())
    total_categorias_egreso = sum(categorias_egresos.values())
    if total_categorias_ingreso != ingresos:
        raise ValueError(
            "No se pudo conciliar el detalle de ingresos con el total."
        )
    if total_categorias_egreso != egresos:
        raise ValueError(
            "No se pudo conciliar el detalle de egresos con el total."
        )

    detalles.sort(
        key=lambda item: (
            item["orden"],
            item["tipo"],
            item["detalle"],
        ),
        reverse=True,
    )
    resumen_diario = resumir_detalles_por_dia(detalles)
    total_entradas_diarias = sum(
        fila["entradas"] for fila in resumen_diario
    )
    total_salidas_diarias = sum(
        fila["salidas"] for fila in resumen_diario
    )
    if total_entradas_diarias != ingresos:
        raise ValueError(
            "No se pudo conciliar el resumen diario de ingresos con el total."
        )
    if total_salidas_diarias != egresos:
        raise ValueError(
            "No se pudo conciliar el resumen diario de egresos con el total."
        )

    return {
        "periodo": periodo_normalizado,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "unidad": unidad_seleccionada,
        "empresa_completa": empresa_completa,
        "ingresos": ingresos,
        "egresos": egresos,
        "utilidad": utilidad,
        "margen": margen,
        "fondo": fondo,
        "fondo_estado": fondo_estado,
        "salida_caja": salida_caja,
        "retenciones": retenciones,
        "inversiones": Movimientos.resumen_inversiones(
            fecha_desde,
            fecha_hasta,
        ),
        "categorias_egresos": sorted(
            categorias_egresos.items(),
            key=lambda item: item[1],
            reverse=True,
        ),
        "categorias_ingresos": sorted(
            categorias_ingresos.items(),
            key=lambda item: item[1],
            reverse=True,
        ),
        "comparacion_unidades": obtener_comparacion_unidades(
            fecha_desde,
            fecha_hasta,
        ),
        "resumen_diario": resumen_diario,
        "detalles": detalles,
    }


def crear_tarjeta(master, titulo, valor, color, descripcion, fila, columna):
    tarjeta = ctk.CTkFrame(
        master,
        fg_color=COLOR_PANEL,
        corner_radius=14,
        border_width=1,
        border_color=COLOR_BORDE,
    )
    tarjeta.grid(
        row=fila,
        column=columna,
        sticky="nsew",
        padx=5,
        pady=5,
    )
    ctk.CTkFrame(
        tarjeta,
        width=7,
        height=30,
        corner_radius=4,
        fg_color=color,
    ).pack(anchor="nw", padx=16, pady=(15, 0))
    ctk.CTkLabel(
        tarjeta,
        text=titulo,
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=COLOR_TEXTO_SUAVE,
        anchor="w",
    ).pack(fill="x", padx=16, pady=(7, 2))
    ctk.CTkLabel(
        tarjeta,
        text=valor,
        font=ctk.CTkFont(size=19, weight="bold"),
        text_color=COLOR_TEXTO,
        anchor="w",
    ).pack(fill="x", padx=16)
    ctk.CTkLabel(
        tarjeta,
        text=descripcion,
        font=ctk.CTkFont(size=10),
        text_color=COLOR_TEXTO_SUAVE,
        anchor="w",
        justify="left",
        wraplength=210,
    ).pack(fill="x", padx=16, pady=(3, 15))


def dibujar_tarjetas(master, informe):
    zona = ctk.CTkFrame(master, fg_color="transparent")
    zona.pack(fill="x", pady=(0, 8))
    for columna in range(3):
        zona.grid_columnconfigure(columna, weight=1, uniform="informe")

    fondo_valor = (
        formatear_monto(informe["fondo"])
        if informe["fondo"] is not None
        else "No aplica"
    )
    datos = [
        (
            "Ingresos",
            formatear_monto(informe["ingresos"]),
            COLOR_VERDE,
            "Total incluido en esta vista",
        ),
        (
            "Egresos",
            formatear_monto(informe["egresos"]),
            COLOR_ROJO,
            "Total incluido en esta vista",
        ),
        (
            "Utilidad / resultado",
            formatear_monto(informe["utilidad"]),
            COLOR_VERDE if informe["utilidad"] >= 0 else COLOR_ROJO,
            "Ingresos menos egresos",
        ),
        (
            "Margen",
            Movimientos.formatear_porcentaje(informe["margen"]) + "%",
            COLOR_PRIMARIO,
            "Resultado sobre ingresos",
        ),
        (
            "Fondo",
            fondo_valor,
            COLOR_NARANJA,
            informe["fondo_estado"],
        ),
        (
            "Inversiones",
            formatear_monto(informe["inversiones"]),
            "#7B61FF",
            "Informativo: no reduce la utilidad",
        ),
    ]
    for indice, datos_tarjeta in enumerate(datos):
        crear_tarjeta(
            zona,
            *datos_tarjeta,
            indice // 3,
            indice % 3,
        )


def dibujar_comparacion(master, informe):
    panel = ctk.CTkFrame(
        master,
        fg_color=COLOR_PANEL,
        corner_radius=16,
        border_width=1,
        border_color=COLOR_BORDE,
    )
    panel.pack(fill="x", pady=7)
    ctk.CTkLabel(
        panel,
        text="Comparación por unidad",
        font=ctk.CTkFont(size=16, weight="bold"),
        text_color=COLOR_TEXTO,
        anchor="w",
    ).pack(fill="x", padx=18, pady=(16, 4))
    ctk.CTkLabel(
        panel,
        text=(
            "Compara solamente movimientos asignados directamente a cada "
            "unidad. Nómina, adicionales y cuotas aparecen como generales."
        ),
        font=ctk.CTkFont(size=11),
        text_color=COLOR_TEXTO_SUAVE,
        anchor="w",
    ).pack(fill="x", padx=18, pady=(0, 10))

    columnas = (
        "unidad",
        "ingresos",
        "egresos",
        "resultado",
        "recibidas",
        "enviadas",
    )
    tabla = ttk.Treeview(
        panel,
        columns=columnas,
        show="headings",
        height=max(len(informe["comparacion_unidades"]), 1),
    )
    titulos = {
        "unidad": "Unidad",
        "ingresos": "Ingresos",
        "egresos": "Egresos",
        "resultado": "Resultado",
        "recibidas": "Transf. recibidas",
        "enviadas": "Transf. enviadas",
    }
    for columna in columnas:
        tabla.heading(columna, text=titulos[columna])
        tabla.column(
            columna,
            width=140,
            minwidth=95,
            anchor="center",
            stretch=True,
        )
    for unidad in informe["comparacion_unidades"]:
        tabla.insert(
            "",
            "end",
            values=(
                unidad["unidad"],
                Movimientos.formatear_monto(unidad["ingresos"]),
                Movimientos.formatear_monto(unidad["egresos"]),
                Movimientos.formatear_monto(unidad["resultado"]),
                Movimientos.formatear_monto(unidad["recibidas"]),
                Movimientos.formatear_monto(unidad["enviadas"]),
            ),
        )
    tabla.pack(fill="x", padx=18, pady=(0, 18))


def dibujar_barras_egresos(master, informe):
    panel = ctk.CTkFrame(
        master,
        fg_color=COLOR_PANEL,
        corner_radius=16,
        border_width=1,
        border_color=COLOR_BORDE,
    )
    panel.pack(fill="x", pady=7)
    ctk.CTkLabel(
        panel,
        text="Egresos por categoría",
        font=ctk.CTkFont(size=16, weight="bold"),
        text_color=COLOR_TEXTO,
        anchor="w",
    ).pack(fill="x", padx=18, pady=(16, 4))
    ctk.CTkLabel(
        panel,
        text=(
            f"Las categorías suman exactamente "
            f"{formatear_monto(informe['egresos'])}."
        ),
        font=ctk.CTkFont(size=11),
        text_color=COLOR_TEXTO_SUAVE,
        anchor="w",
    ).pack(fill="x", padx=18, pady=(0, 12))

    categorias = informe["categorias_egresos"]
    if not categorias:
        ctk.CTkLabel(
            panel,
            text="No hay egresos registrados para este filtro.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
        ).pack(fill="x", padx=18, pady=(0, 18))
        return

    maximo = max(valor for _, valor in categorias)
    for indice, (concepto, valor) in enumerate(categorias):
        fila = ctk.CTkFrame(
            panel,
            fg_color=(
                COLOR_PANEL_SECUNDARIO
                if indice % 2 == 0
                else "transparent"
            ),
            corner_radius=8,
        )
        fila.pack(fill="x", padx=18, pady=2)
        fila.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            fila,
            text=concepto,
            width=250,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=10, pady=9)
        barra = ctk.CTkProgressBar(
            fila,
            height=12,
            progress_color=COLOR_ROJO,
            fg_color=COLOR_BORDE,
        )
        barra.grid(row=0, column=1, sticky="ew", padx=10, pady=9)
        barra.set(valor / maximo if maximo else 0)
        ctk.CTkLabel(
            fila,
            text=formatear_monto(valor),
            width=155,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="e",
        ).grid(row=0, column=2, sticky="e", padx=10, pady=9)
    ctk.CTkFrame(panel, height=10, fg_color="transparent").pack()


def dibujar_conciliacion(master, informe):
    panel = ctk.CTkFrame(
        master,
        fg_color=COLOR_PANEL,
        corner_radius=16,
        border_width=1,
        border_color=COLOR_BORDE,
    )
    panel.pack(fill="x", pady=7)
    ctk.CTkLabel(
        panel,
        text="Control del total",
        font=ctk.CTkFont(size=16, weight="bold"),
        text_color=COLOR_TEXTO,
        anchor="w",
    ).pack(fill="x", padx=18, pady=(16, 10))

    filas = [
        ("Total del informe", informe["egresos"]),
        ("Suma del desglose", sum(
            valor for _, valor in informe["categorias_egresos"]
        )),
    ]
    if informe["empresa_completa"]:
        filas.extend(
            [
                ("Salida real de dinero", informe["salida_caja"]),
                (
                    "Retenciones y otros descuentos",
                    informe["retenciones"],
                ),
            ]
        )

    for indice, (texto, valor) in enumerate(filas):
        fila = ctk.CTkFrame(
            panel,
            fg_color=(
                COLOR_PANEL_SECUNDARIO
                if indice % 2 == 0
                else "transparent"
            ),
        )
        fila.pack(fill="x", padx=18, pady=2)
        fila.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            fila,
            text=texto,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=9)
        ctk.CTkLabel(
            fila,
            text=formatear_monto(valor),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="e",
        ).grid(row=0, column=1, sticky="e", padx=12, pady=9)
    ctk.CTkFrame(panel, height=12, fg_color="transparent").pack()


def dibujar_detalle(master, informe):
    panel = ctk.CTkFrame(
        master,
        fg_color=COLOR_PANEL,
        corner_radius=16,
        border_width=1,
        border_color=COLOR_BORDE,
    )
    panel.pack(fill="x", pady=7)
    ctk.CTkLabel(
        panel,
        text="Detalle diario por categoría",
        font=ctk.CTkFont(size=16, weight="bold"),
        text_color=COLOR_TEXTO,
        anchor="w",
    ).pack(fill="x", padx=18, pady=(16, 4))
    ctk.CTkLabel(
        panel,
        text=(
            f"{len(informe['resumen_diario'])} grupos diarios, formados por "
            f"{len(informe['detalles'])} movimientos verificables."
        ),
        font=ctk.CTkFont(size=11),
        text_color=COLOR_TEXTO_SUAVE,
        anchor="w",
    ).pack(fill="x", padx=18, pady=(0, 10))

    zona_tabla = ctk.CTkFrame(panel, fg_color="transparent")
    zona_tabla.pack(fill="x", padx=18, pady=(0, 18))
    zona_tabla.grid_columnconfigure(0, weight=1)

    columnas = (
        "fecha",
        "grupo",
        "cantidad",
        "entradas",
        "salidas",
        "resultado",
    )
    tabla = ttk.Treeview(
        zona_tabla,
        columns=columnas,
        show="headings",
        height=min(max(len(informe["resumen_diario"]), 3), 15),
    )
    configuracion = [
        ("fecha", "Fecha", 95, "center"),
        ("grupo", "Categoría / unidad", 210, "w"),
        ("cantidad", "Mov.", 70, "center"),
        ("entradas", "Entró", 145, "e"),
        ("salidas", "Salió", 145, "e"),
        ("resultado", "Resultado", 145, "e"),
    ]
    for columna, titulo, ancho, ancla in configuracion:
        tabla.heading(columna, text=titulo)
        tabla.column(
            columna,
            width=ancho,
            minwidth=75,
            anchor=ancla,
            stretch=columna == "grupo",
        )
    for detalle in informe["resumen_diario"]:
        tabla.insert(
            "",
            "end",
            values=(
                detalle["fecha"],
                detalle["grupo"],
                detalle["cantidad"],
                Movimientos.formatear_monto(detalle["entradas"]),
                Movimientos.formatear_monto(detalle["salidas"]),
                Movimientos.formatear_monto(detalle["resultado"]),
            ),
        )

    desplazamiento = ttk.Scrollbar(
        zona_tabla,
        orient="vertical",
        command=tabla.yview,
    )
    tabla.configure(yscrollcommand=desplazamiento.set)
    tabla.grid(row=0, column=0, sticky="nsew")
    desplazamiento.grid(row=0, column=1, sticky="ns")


def dibujar_informe(zona_resultado, informe):
    for widget in zona_resultado.winfo_children():
        widget.destroy()

    ctk.CTkLabel(
        zona_resultado,
        text=(
            f"Informe · {informe['periodo']} · {informe['unidad']}"
        ),
        font=ctk.CTkFont(size=20, weight="bold"),
        text_color=COLOR_TEXTO,
        anchor="w",
    ).pack(fill="x", pady=(2, 8))

    if not informe["empresa_completa"]:
        aviso = ctk.CTkFrame(
            zona_resultado,
            fg_color=("#FFF7E8", "#3B2C16"),
            corner_radius=12,
            border_width=1,
            border_color=("#F2D49B", "#684B20"),
        )
        aviso.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            aviso,
            text=(
                "Esta vista incluye solo movimientos asignados directamente "
                f"a {informe['unidad']}. La nómina, los adicionales y las "
                "cuotas no tienen unidad asignada y aparecen únicamente en "
                "Empresa completa."
            ),
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO,
            anchor="w",
            justify="left",
            wraplength=900,
        ).pack(fill="x", padx=16, pady=12)

    dibujar_tarjetas(zona_resultado, informe)
    dibujar_comparacion(zona_resultado, informe)
    dibujar_barras_egresos(zona_resultado, informe)
    dibujar_conciliacion(zona_resultado, informe)
    dibujar_detalle(zona_resultado, informe)


def mostrar_informes(aplicacion):
    """Abre la pantalla principal del módulo Informes."""
    aplicacion.limpiar_contenedor()
    aplicacion.marcar_seleccion("Informes")
    aplicacion.bind(
        "<Escape>",
        lambda _evento: aplicacion.mostrar_inicio(),
    )
    estado_informe = {"actual": None}

    pagina = ctk.CTkScrollableFrame(
        aplicacion.contenedor,
        fg_color="transparent",
        corner_radius=0,
    )
    pagina.grid(row=0, column=0, sticky="nsew")

    aplicacion.crear_encabezado(
        pagina,
        "Informes",
        (
            "Analizá un mes, compará unidades y verificá exactamente "
            "de dónde salen los ingresos y egresos."
        ),
    )

    controles = ctk.CTkFrame(
        pagina,
        fg_color=COLOR_PANEL,
        corner_radius=16,
        border_width=1,
        border_color=COLOR_BORDE,
    )
    controles.pack(fill="x", padx=34, pady=(0, 14))
    controles.grid_columnconfigure(4, weight=1)

    ctk.CTkLabel(
        controles,
        text="Período",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=COLOR_TEXTO,
    ).grid(row=0, column=0, padx=(20, 8), pady=18)
    entrada_periodo = ctk.CTkEntry(
        controles,
        width=130,
        height=40,
        placeholder_text="MM-AAAA",
        border_color=COLOR_BORDE,
        fg_color=COLOR_PANEL_SECUNDARIO,
        text_color=COLOR_TEXTO,
    )
    entrada_periodo.insert(0, datetime.now().strftime("%m-%Y"))
    entrada_periodo.grid(row=0, column=1, padx=(0, 18), pady=18)

    ctk.CTkLabel(
        controles,
        text="Vista",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=COLOR_TEXTO,
    ).grid(row=0, column=2, padx=(0, 8), pady=18)
    selector_unidad = ctk.CTkComboBox(
        controles,
        values=["Empresa completa", *Movimientos.UNIDADES],
        width=190,
        height=40,
        state="readonly",
        border_color=COLOR_BORDE,
        fg_color=COLOR_PANEL_SECUNDARIO,
        button_color=COLOR_PRIMARIO,
        button_hover_color=COLOR_PRIMARIO_HOVER,
        dropdown_fg_color=COLOR_PANEL,
        dropdown_text_color=COLOR_TEXTO,
        text_color=COLOR_TEXTO,
    )
    selector_unidad.set("Empresa completa")
    selector_unidad.grid(row=0, column=3, padx=(0, 18), pady=18)

    zona_resultado = ctk.CTkFrame(
        pagina,
        fg_color="transparent",
    )
    zona_resultado.pack(
        fill="both",
        expand=True,
        padx=34,
        pady=(0, 30),
    )

    boton_excel = None
    boton_pdf = None

    def generar():
        try:
            informe = obtener_informe(
                entrada_periodo.get(),
                selector_unidad.get(),
            )
        except (ValueError, OSError, IndexError, TypeError) as error:
            from tkinter import messagebox

            messagebox.showerror(
                "No se pudo generar el informe",
                str(error),
                parent=aplicacion,
            )
            return

        entrada_periodo.delete(0, "end")
        entrada_periodo.insert(0, informe["periodo"])
        estado_informe["actual"] = informe
        boton_excel.configure(state="normal")
        boton_pdf.configure(state="normal")
        dibujar_informe(zona_resultado, informe)

    def guardar_exportacion(tipo):
        informe = estado_informe["actual"]
        if informe is None:
            generar()
            informe = estado_informe["actual"]
        if informe is None:
            return

        extension = "xlsx" if tipo == "excel" else "pdf"
        tipo_archivo = (
            [("Libro de Excel", "*.xlsx")]
            if tipo == "excel"
            else [("Documento PDF", "*.pdf")]
        )
        ruta = filedialog.asksaveasfilename(
            parent=aplicacion,
            title=(
                "Guardar informe en Excel"
                if tipo == "excel"
                else "Guardar informe en PDF"
            ),
            defaultextension=f".{extension}",
            initialfile=nombre_archivo_seguro(informe, extension),
            filetypes=tipo_archivo,
        )
        if not ruta:
            return

        try:
            if tipo == "excel":
                exportar_excel(informe, ruta)
            else:
                exportar_pdf(informe, ruta)
        except (OSError, RuntimeError, ValueError, TypeError) as error:
            messagebox.showerror(
                "No se pudo guardar el informe",
                str(error),
                parent=aplicacion,
            )
            return

        messagebox.showinfo(
            "Informe guardado",
            f"El archivo se guardó correctamente en:\n{ruta}",
            parent=aplicacion,
        )

    ctk.CTkButton(
        controles,
        text="Generar informe",
        command=generar,
        width=150,
        height=40,
        corner_radius=9,
        fg_color=COLOR_PRIMARIO,
        hover_color=COLOR_PRIMARIO_HOVER,
        font=ctk.CTkFont(size=12, weight="bold"),
    ).grid(row=0, column=5, padx=(0, 20), pady=18)

    acciones_exportacion = ctk.CTkFrame(
        controles,
        fg_color="transparent",
    )
    acciones_exportacion.grid(
        row=1,
        column=0,
        columnspan=6,
        sticky="e",
        padx=20,
        pady=(0, 18),
    )

    ctk.CTkLabel(
        acciones_exportacion,
        text="Atajos: Ctrl+E Excel · Ctrl+P PDF",
        font=ctk.CTkFont(size=11),
        text_color=COLOR_TEXTO_SUAVE,
    ).pack(side="left", padx=(0, 14))

    boton_excel = ctk.CTkButton(
        acciones_exportacion,
        text="Descargar Excel",
        command=lambda: guardar_exportacion("excel"),
        width=145,
        height=38,
        corner_radius=9,
        fg_color=COLOR_VERDE,
        hover_color="#12855C",
        font=ctk.CTkFont(size=12, weight="bold"),
        state="disabled",
    )
    boton_excel.pack(side="left", padx=(0, 8))

    boton_pdf = ctk.CTkButton(
        acciones_exportacion,
        text="Descargar PDF",
        command=lambda: guardar_exportacion("pdf"),
        width=145,
        height=38,
        corner_radius=9,
        fg_color=COLOR_ROJO,
        hover_color="#BD4040",
        font=ctk.CTkFont(size=12, weight="bold"),
        state="disabled",
    )
    boton_pdf.pack(side="left")

    entrada_periodo.bind("<Return>", lambda _evento: generar())
    selector_unidad.configure(command=lambda _valor: generar())
    aplicacion.bind(
        "<Control-e>",
        lambda _evento: guardar_exportacion("excel"),
    )
    aplicacion.bind(
        "<Control-E>",
        lambda _evento: guardar_exportacion("excel"),
    )
    aplicacion.bind(
        "<Control-p>",
        lambda _evento: guardar_exportacion("pdf"),
    )
    aplicacion.bind(
        "<Control-P>",
        lambda _evento: guardar_exportacion("pdf"),
    )
    generar()
