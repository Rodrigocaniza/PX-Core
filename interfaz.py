"""Interfaz gráfica de PX-Core.

La interfaz comparte los mismos archivos de ``Datos`` que la aplicación por
consola. La versión de consola continúa disponible en ``main.py``.
"""

from calendar import monthrange
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
from tkinter import messagebox, ttk
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile


BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

try:
    import customtkinter as ctk
except ModuleNotFoundError:
    print()
    print("Falta instalar CustomTkinter.")
    print("Ejecutá: py -m pip install -r requirements.txt")
    print()
    raise SystemExit(1)

import Movimientos
import Socios
import Informes
import ImportadorExcel
import Facturas
from datos import guardar_datos, leer_datos
from panel_rrhh import crear_panel_rrhh


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

TIPOS_MOVIMIENTO_GUI = [
    "Ingreso",
    "Egreso",
    "Transferencia interna",
    "Depósito interno",
    "Cobro externo",
]
TIPOS_ADICIONAL_GUI = ["Ingreso", "Egreso"]
MOVIMIENTOS_POR_PAGINA = 10
ADICIONALES_POR_PAGINA = 10
INVERSIONES_POR_PAGINA = 10
PRESTAMOS_POR_PAGINA = 10
CUOTAS_POR_PAGINA = 10
RETIROS_POR_PAGINA = 10
FONDOS_POR_PAGINA = 10


def crear_respaldo_diario():
    """Crea una copia diaria de Datos antes de comenzar a trabajar."""

    carpeta_datos = BASE_DIR / "Datos"

    if not carpeta_datos.exists():
        return None

    carpeta_respaldos = BASE_DIR / "Respaldos"
    carpeta_respaldos.mkdir(parents=True, exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    ruta_respaldo = carpeta_respaldos / f"BC_Gestion_{fecha}.zip"

    if ruta_respaldo.exists():
        return ruta_respaldo

    with ZipFile(
        ruta_respaldo,
        "w",
        compression=ZIP_DEFLATED,
    ) as archivo_zip:
        for ruta in carpeta_datos.rglob("*"):
            if ruta.is_file():
                archivo_zip.write(
                    ruta,
                    ruta.relative_to(BASE_DIR),
                )

    return ruta_respaldo


SECCIONES = {
    "Movimientos": {
        "descripcion": (
            "Registro y control de la operación diaria de la empresa."
        ),
        "opciones": [
            ("Cargar día", "Ingresos, egresos, transferencias y depósitos."),
            (
                "Gestionar movimientos",
                "Ver, modificar o eliminar movimientos registrados.",
            ),
            (
                "Ingresos y egresos adicionales",
                "Gastos fijos y conceptos adicionales editables.",
            ),
            ("Inversiones", "Registro y consulta de inversiones."),
            (
                "Préstamos y cuotas",
                "Préstamos activos, pagos e historial por período.",
            ),
            (
                "Cierre mensual",
                "Utilidad, margen y fondo de estabilidad.",
            ),
            (
                "Importar desde Excel",
                "Carga un mes completo con validación y respaldo.",
            ),
        ],
    },
    "Recursos Humanos": {
        "descripcion": (
            "Funcionarios, novedades, sueldos y liquidaciones."
        ),
        "opciones": [
            (
                "Gestión completa de Recursos Humanos",
                (
                    "Funcionarios, novedades, liquidaciones y salario "
                    "mínimo reunidos en una sola ventana."
                ),
            ),
        ],
    },
    "Socios": {
        "descripcion": (
            "Retiros mensuales, utilidades y fondo de estabilidad."
        ),
        "opciones": [
            (
                "Gestión completa de Socios",
                (
                    "Retiros, resumen mensual, gestión de retiros y "
                    "fondo de estabilidad reunidos en una sola pantalla."
                ),
            ),
        ],
    },
}


def validar_texto_campo(texto, nombre):
    valor = texto.strip()

    if not valor:
        raise ValueError(f"Completá el campo {nombre}.")

    if "|" in valor or "\n" in valor or "\r" in valor:
        raise ValueError(
            f"El campo {nombre} contiene un carácter no permitido."
        )

    return valor


def convertir_monto_grafico(texto):
    valor = (
        texto.strip()
        .replace(".", "")
        .replace(",", "")
        .replace(" ", "")
    )

    try:
        monto_convertido = int(valor)
    except ValueError as error:
        raise ValueError(
            "Ingresá un monto válido usando solamente números."
        ) from error

    if monto_convertido <= 0:
        raise ValueError("El monto debe ser mayor a cero.")

    return monto_convertido


def convertir_monto_no_negativo_grafico(texto):
    valor = (
        texto.strip()
        .replace(".", "")
        .replace(",", "")
        .replace(" ", "")
    )

    try:
        monto_convertido = int(valor)
    except ValueError as error:
        raise ValueError(
            "Ingresá un monto válido usando solamente números."
        ) from error

    if monto_convertido < 0:
        raise ValueError("El monto no puede ser negativo.")

    return monto_convertido


def construir_retiro_grafico(
    fecha,
    socio_nombre,
    monto_texto,
    observacion,
    tipo=None,
):
    try:
        Movimientos.convertir_fecha(fecha.strip())
    except ValueError as error:
        raise ValueError(
            "La fecha no es válida. Usá el formato DD-MM-AAAA."
        ) from error

    socio = next(
        (
            item
            for item in Socios.SOCIOS
            if item["nombre"] == socio_nombre
        ),
        None,
    )
    if socio is None:
        raise ValueError("Seleccioná un socio válido.")

    tipo_normalizado = Socios.normalizar_tipo_movimiento_personal(
        tipo or Socios.TIPO_MOVIMIENTO_PREDETERMINADO
    )
    if tipo_normalizado is None:
        raise ValueError(
            "Seleccioná Gasto personal o Inversión personal."
        )

    retiro = {
        "id": uuid4().hex[:12].upper(),
        "fecha": fecha.strip(),
        "socio_id": socio["id"],
        "monto": convertir_monto_grafico(monto_texto),
        "tipo": tipo_normalizado,
        "observacion": Socios.limpiar_texto(observacion) or "-",
    }
    return retiro, Socios.crear_linea_retiro(retiro)


def construir_movimiento_grafico(tipo, fecha, monto_texto, campos):
    """Construye una línea compatible con ``Datos/movimientos.txt``."""
    try:
        Movimientos.convertir_fecha(fecha.strip())
    except ValueError as error:
        raise ValueError(
            "La fecha no es válida. Usá el formato DD-MM-AAAA."
        ) from error

    monto_movimiento = convertir_monto_grafico(monto_texto)

    if tipo == "Ingreso":
        unidad = validar_texto_campo(
            campos.get("unidad", ""),
            "Unidad",
        )
        linea = (
            f"Ingreso|{fecha.strip()}|Externo|"
            f"{unidad}|{monto_movimiento}|Si"
        )

    elif tipo == "Egreso":
        unidad = validar_texto_campo(
            campos.get("unidad", ""),
            "Unidad",
        )
        linea = (
            f"Egreso|{fecha.strip()}|{unidad}|"
            f"Externo|{monto_movimiento}|Si"
        )

    elif tipo == "Transferencia interna":
        origen = validar_texto_campo(
            campos.get("origen", ""),
            "Unidad de origen",
        )
        destino = validar_texto_campo(
            campos.get("destino", ""),
            "Unidad de destino",
        )

        if origen == destino:
            raise ValueError(
                "La unidad de origen y la de destino no pueden ser iguales."
            )

        linea = (
            f"Transferencia interna|{fecha.strip()}|{origen}|"
            f"{destino}|{monto_movimiento}|No"
        )

    elif tipo == "Depósito interno":
        origen_elegido = validar_texto_campo(
            campos.get("origen", ""),
            "Origen del depósito",
        )

        if origen_elegido == "Otra persona":
            origen = validar_texto_campo(
                campos.get("persona", ""),
                "Nombre de la persona",
            )
        else:
            origen = origen_elegido

        banco = validar_texto_campo(
            campos.get("banco", ""),
            "Banco de destino",
        )
        linea = (
            f"Deposito interno|{fecha.strip()}|{origen}|"
            f"{banco}|{monto_movimiento}|No"
        )

    elif tipo == "Cobro externo":
        banco = validar_texto_campo(
            campos.get("banco", ""),
            "Banco que recibió el cobro",
        )
        unidad = validar_texto_campo(
            campos.get("unidad", ""),
            "Unidad",
        )
        linea = (
            f"Cobro externo|{fecha.strip()}|{banco}|"
            f"{unidad}|{monto_movimiento}|Si"
        )

    else:
        raise ValueError("Seleccioná un tipo de movimiento.")

    datos = Movimientos.separar_movimiento(linea)

    if datos is None:
        raise ValueError("No se pudo construir el movimiento.")

    return linea, datos


def tipo_movimiento_para_gui(tipo):
    equivalencias = {
        "Deposito interno": "Depósito interno",
    }
    return equivalencias.get(tipo, tipo)


def filtrar_movimientos_graficos(
    lineas,
    fecha_desde_texto="",
    fecha_hasta_texto="",
    tipo="Todos",
    unidad="Todas",
):
    """Devuelve movimientos válidos con su posición real en el archivo."""
    fecha_desde_texto = fecha_desde_texto.strip()
    fecha_hasta_texto = fecha_hasta_texto.strip()

    if bool(fecha_desde_texto) != bool(fecha_hasta_texto):
        raise ValueError(
            "Completá las dos fechas del rango o dejá ambas vacías."
        )

    if fecha_desde_texto:
        try:
            fecha_desde = Movimientos.convertir_fecha(fecha_desde_texto)
            fecha_hasta = Movimientos.convertir_fecha(fecha_hasta_texto)
        except ValueError as error:
            raise ValueError(
                "Las fechas no son válidas. Usá el formato DD-MM-AAAA."
            ) from error

        if fecha_desde > fecha_hasta:
            raise ValueError(
                "La fecha inicial no puede ser posterior a la fecha final."
            )
    else:
        fecha_desde = None
        fecha_hasta = None

    registros = []
    tipo_normalizado = Movimientos.normalizar_texto(tipo)
    unidad_normalizada = Movimientos.normalizar_texto(unidad)

    for posicion, linea in enumerate(lineas):
        datos = Movimientos.separar_movimiento(linea)

        if datos is None:
            continue

        try:
            fecha = Movimientos.convertir_fecha(datos["fecha"])
        except ValueError:
            continue

        if (
            fecha_desde is not None
            and not fecha_desde <= fecha <= fecha_hasta
        ):
            continue

        if (
            tipo != "Todos"
            and Movimientos.normalizar_texto(datos["tipo"])
            != tipo_normalizado
        ):
            continue

        if unidad != "Todas":
            origen = Movimientos.normalizar_texto(datos["origen"])
            destino = Movimientos.normalizar_texto(datos["destino"])

            if unidad_normalizada not in (origen, destino):
                continue

        registros.append((posicion, datos, fecha))

    registros.sort(
        key=lambda registro: (registro[2], registro[0]),
        reverse=True,
    )
    return [
        (posicion, datos)
        for posicion, datos, _ in registros
    ]


def unidades_relacionadas_movimiento(datos):
    """Indica en qué grupo de sucursal debe mostrarse un movimiento."""
    unidades_normalizadas = {
        Movimientos.normalizar_texto(unidad): unidad
        for unidad in Movimientos.UNIDADES
    }
    tipo = datos["tipo"]
    origen = Movimientos.normalizar_texto(datos["origen"])
    destino = Movimientos.normalizar_texto(datos["destino"])

    if tipo in ("Ingreso", "Cobro externo"):
        candidatas = [destino]
    elif tipo in ("Egreso", "Deposito interno"):
        candidatas = [origen]
    elif tipo == "Transferencia interna":
        candidatas = [origen, destino]
    else:
        candidatas = [origen, destino]

    resultado = []

    for candidata in candidatas:
        unidad = unidades_normalizadas.get(candidata)

        if unidad is not None and unidad not in resultado:
            resultado.append(unidad)

    return resultado or ["Otros"]


def resumir_movimientos_de_unidad(unidad, registros):
    """Resume el efecto diario de los registros sobre una unidad."""
    unidad_normalizada = Movimientos.normalizar_texto(unidad)
    resumen = {
        "ingresos": 0,
        "egresos": 0,
        "transferencias_recibidas": 0,
        "transferencias_enviadas": 0,
        "depositos": 0,
    }

    for _posicion, datos in registros:
        tipo = datos["tipo"]
        origen = Movimientos.normalizar_texto(datos["origen"])
        destino = Movimientos.normalizar_texto(datos["destino"])
        monto = datos["monto"]

        if (
            tipo in ("Ingreso", "Cobro externo")
            and destino == unidad_normalizada
        ):
            resumen["ingresos"] += monto
        elif tipo == "Egreso" and origen == unidad_normalizada:
            resumen["egresos"] += monto
        elif tipo == "Transferencia interna":
            if destino == unidad_normalizada:
                resumen["transferencias_recibidas"] += monto
            if origen == unidad_normalizada:
                resumen["transferencias_enviadas"] += monto
        elif tipo == "Deposito interno" and origen == unidad_normalizada:
            resumen["depositos"] += monto

    resumen["resultado"] = resumen["ingresos"] - resumen["egresos"]
    return resumen


def construir_adicional_grafico(
    tipo,
    fecha,
    concepto,
    monto_texto,
    observacion="",
):
    """Construye una línea compatible con movimientos_adicionales.txt."""
    if tipo not in TIPOS_ADICIONAL_GUI:
        raise ValueError("Seleccioná si es un ingreso o un egreso.")

    fecha = fecha.strip()
    try:
        Movimientos.convertir_fecha(fecha)
    except ValueError as error:
        raise ValueError(
            "La fecha no es válida. Usá el formato DD-MM-AAAA."
        ) from error

    concepto = validar_texto_campo(concepto, "Concepto")
    monto_adicional = convertir_monto_grafico(monto_texto)
    observacion = observacion.strip()

    if "|" in observacion or "\n" in observacion or "\r" in observacion:
        raise ValueError(
            "La observación no puede contener el símbolo |. "
            "Usá una coma o una barra / para separar detalles."
        )

    if concepto != "Pago de tarjeta de crédito":
        observacion = ""

    linea = (
        f"{tipo}|{fecha}|{concepto}|"
        f"{monto_adicional}|{observacion}"
    )
    datos = Movimientos.separar_adicional(linea)

    if datos is None:
        raise ValueError("No se pudo construir el registro adicional.")

    return linea, datos


def filtrar_adicionales_graficos(
    lineas,
    fecha_desde_texto="",
    fecha_hasta_texto="",
    tipo="Todos",
):
    """Devuelve adicionales válidos con su posición real en el archivo."""
    fecha_desde_texto = fecha_desde_texto.strip()
    fecha_hasta_texto = fecha_hasta_texto.strip()

    if bool(fecha_desde_texto) != bool(fecha_hasta_texto):
        raise ValueError(
            "Completá las dos fechas del rango o dejá ambas vacías."
        )

    if fecha_desde_texto:
        try:
            fecha_desde = Movimientos.convertir_fecha(fecha_desde_texto)
            fecha_hasta = Movimientos.convertir_fecha(fecha_hasta_texto)
        except ValueError as error:
            raise ValueError(
                "Las fechas no son válidas. Usá el formato DD-MM-AAAA."
            ) from error

        if fecha_desde > fecha_hasta:
            raise ValueError(
                "La fecha inicial no puede ser posterior a la fecha final."
            )
    else:
        fecha_desde = None
        fecha_hasta = None

    registros = []

    for posicion, linea in enumerate(lineas):
        datos = Movimientos.separar_adicional(linea)

        if datos is None:
            continue

        try:
            fecha = Movimientos.convertir_fecha(datos["fecha"])
        except ValueError:
            continue

        if (
            fecha_desde is not None
            and not fecha_desde <= fecha <= fecha_hasta
        ):
            continue

        if tipo != "Todos" and datos["tipo"] != tipo:
            continue

        registros.append((posicion, datos, fecha))

    registros.sort(
        key=lambda registro: (registro[2], registro[0]),
        reverse=True,
    )
    return [
        (posicion, datos)
        for posicion, datos, _ in registros
    ]


def construir_inversion_grafica(fecha, descripcion, monto_texto):
    """Construye una línea compatible con ``Datos/inversiones.txt``."""
    fecha = fecha.strip()
    try:
        Movimientos.convertir_fecha(fecha)
    except ValueError as error:
        raise ValueError(
            "La fecha no es válida. Usá el formato DD-MM-AAAA."
        ) from error

    descripcion = validar_texto_campo(descripcion, "Descripción")
    monto_inversion = convertir_monto_grafico(monto_texto)
    linea = f"{fecha}|{descripcion}|{monto_inversion}"
    datos = Movimientos.separar_inversion(linea)

    if datos is None:
        raise ValueError("No se pudo construir la inversión.")

    return linea, datos


def filtrar_inversiones_graficas(
    lineas,
    fecha_desde_texto="",
    fecha_hasta_texto="",
    descripcion_texto="",
):
    """Devuelve inversiones válidas con su posición real en el archivo."""
    fecha_desde_texto = fecha_desde_texto.strip()
    fecha_hasta_texto = fecha_hasta_texto.strip()
    descripcion_texto = Movimientos.normalizar_texto(
        descripcion_texto.strip()
    )

    if bool(fecha_desde_texto) != bool(fecha_hasta_texto):
        raise ValueError(
            "Completá las dos fechas del rango o dejá ambas vacías."
        )

    if fecha_desde_texto:
        try:
            fecha_desde = Movimientos.convertir_fecha(fecha_desde_texto)
            fecha_hasta = Movimientos.convertir_fecha(fecha_hasta_texto)
        except ValueError as error:
            raise ValueError(
                "Las fechas no son válidas. Usá el formato DD-MM-AAAA."
            ) from error

        if fecha_desde > fecha_hasta:
            raise ValueError(
                "La fecha inicial no puede ser posterior a la fecha final."
            )
    else:
        fecha_desde = None
        fecha_hasta = None

    registros = []
    for posicion, linea in enumerate(lineas):
        datos = Movimientos.separar_inversion(linea)

        if datos is None:
            continue

        try:
            fecha = Movimientos.convertir_fecha(datos["fecha"])
        except ValueError:
            continue

        if (
            fecha_desde is not None
            and not fecha_desde <= fecha <= fecha_hasta
        ):
            continue

        if (
            descripcion_texto
            and descripcion_texto
            not in Movimientos.normalizar_texto(datos["descripcion"])
        ):
            continue

        registros.append((posicion, datos, fecha))

    registros.sort(
        key=lambda registro: (registro[2], registro[0]),
        reverse=True,
    )
    return [
        (posicion, datos)
        for posicion, datos, _ in registros
    ]


def construir_prestamo_grafico(
    descripcion,
    banco,
    fecha,
    monto_recibido_texto,
    total_devolver_texto,
    cantidad_cuotas_texto,
    prestamo_id,
):
    """Construye una línea compatible con ``Datos/prestamos.txt``."""
    descripcion = validar_texto_campo(descripcion, "Descripción")
    banco = validar_texto_campo(banco, "Banco")
    fecha = fecha.strip()
    try:
        Movimientos.convertir_fecha(fecha)
    except ValueError as error:
        raise ValueError(
            "La fecha no es válida. Usá el formato DD-MM-AAAA."
        ) from error

    monto_recibido = convertir_monto_grafico(monto_recibido_texto)
    total_devolver = convertir_monto_grafico(total_devolver_texto)
    cantidad_cuotas = convertir_monto_grafico(cantidad_cuotas_texto)

    if total_devolver < monto_recibido:
        raise ValueError(
            "El total a devolver no puede ser menor al monto recibido."
        )

    linea = (
        f"{prestamo_id}|{descripcion}|{banco}|{fecha}|"
        f"{monto_recibido}|{total_devolver}|{cantidad_cuotas}"
    )
    datos = Movimientos.separar_prestamo(linea)
    if datos is None:
        raise ValueError("No se pudo construir el préstamo.")
    return linea, datos


def construir_cuota_grafica(
    prestamo,
    numero,
    fecha,
    monto_texto,
    total_otros_pagos=0,
):
    """Construye una cuota sin permitir superar el total a devolver."""
    fecha = fecha.strip()
    try:
        Movimientos.convertir_fecha(fecha)
    except ValueError as error:
        raise ValueError(
            "La fecha no es válida. Usá el formato DD-MM-AAAA."
        ) from error

    monto_cuota = convertir_monto_grafico(monto_texto)
    saldo_disponible = prestamo["costo_total"] - total_otros_pagos
    if monto_cuota > saldo_disponible:
        raise ValueError(
            "El pago supera el saldo pendiente de Gs. "
            + Movimientos.formatear_monto(max(saldo_disponible, 0))
            + "."
        )

    linea = (
        f"{prestamo['id']}|{numero}|{fecha}|{monto_cuota}"
    )
    datos = Movimientos.separar_cuota(linea)
    if datos is None:
        raise ValueError("No se pudo construir la cuota.")
    return linea, datos


def siguiente_numero_cuota(prestamo_id):
    numeros = {
        datos["numero"]
        for _, datos in Movimientos.cuotas_de_prestamo(prestamo_id)
    }
    numero = 1
    while numero in numeros:
        numero += 1
    return numero


def obtener_prestamos_graficos(estado="Activos", periodo=""):
    """Obtiene préstamos con posición real, estado y filtros gráficos."""
    periodo = periodo.strip()
    mes = None
    anio = None

    if estado == "Pagados" and periodo:
        try:
            fecha_periodo = datetime.strptime(periodo, "%m-%Y")
        except ValueError as error:
            raise ValueError(
                "El período no es válido. Usá el formato MM-AAAA."
            ) from error
        mes = fecha_periodo.month
        anio = fecha_periodo.year

    pagados = estado == "Pagados"
    return Movimientos.obtener_prestamos_por_estado(
        pagados,
        mes,
        anio,
    )


def limites_periodo_grafico(periodo):
    """Convierte MM-AAAA en el primer y último día de ese mes."""
    try:
        fecha_periodo = datetime.strptime(periodo.strip(), "%m-%Y")
    except ValueError as error:
        raise ValueError(
            "El período no es válido. Usá el formato MM-AAAA."
        ) from error

    ultimo_dia = monthrange(
        fecha_periodo.year,
        fecha_periodo.month,
    )[1]
    return (
        datetime(fecha_periodo.year, fecha_periodo.month, 1),
        datetime(
            fecha_periodo.year,
            fecha_periodo.month,
            ultimo_dia,
        ),
    )


def calcular_cierre_grafico(periodo, guardar_fondo=False):
    """Calcula el cierre y, si se solicita, registra su fondo mensual."""
    fecha_desde, fecha_hasta = limites_periodo_grafico(periodo)
    periodo_normalizado = fecha_desde.strftime("%m-%Y")
    indicadores = Movimientos.calcular_indicadores_cierre(
        fecha_desde,
        fecha_hasta,
    )

    unidades = []
    for unidad in Movimientos.UNIDADES:
        (
            ingresos,
            egresos,
            resultado,
            transferencias_recibidas,
            transferencias_enviadas,
        ) = Movimientos.calcular_resumen_unidad(
            unidad,
            fecha_desde,
            fecha_hasta,
        )
        unidades.append(
            {
                "unidad": unidad,
                "ingresos": ingresos,
                "egresos": egresos,
                "resultado": resultado,
                "transferencias_recibidas": transferencias_recibidas,
                "transferencias_enviadas": transferencias_enviadas,
            }
        )

    total_inversiones = Movimientos.resumen_inversiones(
        fecha_desde,
        fecha_hasta,
    )
    total_cuotas, detalle_cuotas = Movimientos.resumen_cuotas(
        fecha_desde,
        fecha_hasta,
    )
    nomina, detalle_sueldos = (
        Movimientos.resumen_nomina_liquidada(
            fecha_desde,
            fecha_hasta,
        )
    )
    total_sueldos = nomina["egreso_planilla"]

    registro_fondo = Movimientos.obtener_registro_fondo(
        periodo_normalizado
    )
    if guardar_fondo:
        fondo = Movimientos.guardar_fondo_del_cierre(
            periodo_normalizado,
            indicadores["fondo_calculado"],
        )
        fondo_registrado = True
    elif registro_fondo is not None:
        fondo = registro_fondo[1]
        fondo_registrado = True
    else:
        fondo = {
            "periodo": periodo_normalizado,
            "monto_calculado": indicadores["fondo_calculado"],
            "monto_aplicado": indicadores["fondo_calculado"],
            "modo": "PROVISORIO",
            "observacion": "Vista previa sin guardar",
        }
        fondo_registrado = False

    utilidad_repartible = max(
        indicadores["utilidad_mes"] - fondo["monto_aplicado"],
        0,
    )
    fondo_acumulado = sum(
        registro["monto_aplicado"]
        for _, registro in Movimientos.obtener_registros_fondo()
    )

    return {
        "periodo": periodo_normalizado,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "indicadores": indicadores,
        "unidades": unidades,
        "total_inversiones": total_inversiones,
        "total_cuotas": total_cuotas,
        "detalle_cuotas": detalle_cuotas,
        "total_sueldos": total_sueldos,
        "nomina": nomina,
        "detalle_sueldos": detalle_sueldos,
        "fondo": fondo,
        "fondo_registrado": fondo_registrado,
        "fondo_acumulado": fondo_acumulado,
        "utilidad_repartible": utilidad_repartible,
    }


def periodo_actual():
    hoy = datetime.now()
    ultimo_dia = monthrange(hoy.year, hoy.month)[1]
    return (
        datetime(hoy.year, hoy.month, 1),
        datetime(hoy.year, hoy.month, ultimo_dia),
    )


def texto_mes(fecha):
    meses = [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    return f"{meses[fecha.month - 1].capitalize()} {fecha.year}"


def monto(valor):
    return "Gs. " + Movimientos.formatear_monto(valor)


def obtener_indicadores():
    fecha_desde, fecha_hasta = periodo_actual()
    indicadores = Movimientos.calcular_indicadores_cierre(
        fecha_desde,
        fecha_hasta,
    )
    fondo_acumulado = sum(
        registro["monto_aplicado"]
        for _, registro in Movimientos.obtener_registros_fondo()
    )
    prestamos_activos = len(
        Movimientos.obtener_prestamos_por_estado(False)
    )

    return {
        "ingresos": monto(indicadores["ingresos"]),
        "egresos": monto(indicadores["egresos"]),
        "utilidad": monto(indicadores["utilidad_mes"]),
        "margen": (
            Movimientos.formatear_porcentaje(
                indicadores["margen_porcentual"]
            )
            + "%"
        ),
        "fondo": monto(fondo_acumulado),
        "prestamos": str(prestamos_activos),
    }


class TarjetaIndicador(ctk.CTkFrame):
    def __init__(
        self,
        master,
        titulo,
        valor,
        color,
        descripcion,
    ):
        super().__init__(
            master,
            fg_color=COLOR_PANEL,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkFrame(
            self,
            width=8,
            height=38,
            corner_radius=4,
            fg_color=color,
        ).grid(
            row=0,
            column=0,
            sticky="nw",
            padx=(20, 0),
            pady=(20, 0),
        )

        ctk.CTkLabel(
            self,
            text=titulo,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="nw",
            padx=(40, 18),
            pady=(18, 0),
        )

        self.etiqueta_valor = ctk.CTkLabel(
            self,
            text=valor,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        )
        self.etiqueta_valor.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=20,
            pady=(12, 2),
        )

        ctk.CTkLabel(
            self,
            text=descripcion,
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=2,
            column=0,
            sticky="ew",
            padx=20,
            pady=(0, 18),
        )


class AplicacionPXCore(ctk.CTk):
    def __init__(self):
        super().__init__()

        try:
            self.ruta_respaldo_diario = crear_respaldo_diario()
            self.error_respaldo_diario = None
        except OSError as error:
            self.ruta_respaldo_diario = None
            self.error_respaldo_diario = str(error)

        self.title("BC Gestión Empresarial")
        self.geometry("1280x760")
        self.minsize(1040, 680)
        self.configure(fg_color=COLOR_FONDO)
        self.habilitar_navegacion_tab(self)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.botones_menu = {}
        self.orden_tablas = {}
        self.campos_movimiento = {}
        self.movimientos_sesion = []
        self.tipo_movimiento_actual = "Ingreso"
        self.fecha_carga_actual = datetime.now().strftime("%d-%m-%Y")
        self.unidad_carga_actual = (
            Movimientos.UNIDADES[0] if Movimientos.UNIDADES else ""
        )
        self.movimientos_filtrados = []
        self.mapa_items_movimientos = {}
        self.pagina_movimientos = 0
        self.posicion_movimiento_seleccionado = None
        self.campos_edicion_movimiento = {}
        self.adicionales_filtrados = []
        self.pagina_adicionales = 0
        self.posicion_adicional_seleccionado = None
        self.campos_edicion_adicional = {}
        self.tipo_catalogo_actual = "Ingreso"
        self.inversiones_filtradas = []
        self.pagina_inversiones = 0
        self.posicion_inversion_seleccionada = None
        self.retiros_filtrados = []
        self.pagina_retiros = 0
        self.posicion_retiro_seleccionado = None
        self.fondos_filtrados = []
        self.pagina_fondos = 0
        self.posicion_fondo_seleccionado = None
        self.construir_barra_lateral()

        self.contenedor = ctk.CTkFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
        )
        self.contenedor.grid(
            row=0,
            column=1,
            sticky="nsew",
        )
        self.contenedor.grid_rowconfigure(0, weight=1)
        self.contenedor.grid_columnconfigure(0, weight=1)

        self.mostrar_inicio()

    def habilitar_navegacion_tab(self, ventana):
        """Activa una navegación de teclado continua y contextual."""
        ventana.bind(
            "<Tab>",
            lambda evento: self.mover_foco_formulario(evento, 1),
            add="+",
        )
        ventana.bind(
            "<Shift-Tab>",
            lambda evento: self.mover_foco_formulario(evento, -1),
            add="+",
        )
        ventana.bind(
            "<ISO_Left_Tab>",
            lambda evento: self.mover_foco_formulario(evento, -1),
            add="+",
        )
        for secuencia, direccion in [
            ("<Up>", "arriba"),
            ("<Down>", "abajo"),
            ("<Left>", "izquierda"),
            ("<Right>", "derecha"),
        ]:
            ventana.bind(
                secuencia,
                lambda evento, sentido=direccion: (
                    self.manejar_flecha(evento, sentido)
                ),
                add="+",
            )

    def controles_editables_visibles(self, contenedor):
        """Devuelve controles útiles visibles en su orden de creación."""
        controles = []
        tipos_navegables = (
            ctk.CTkEntry,
            ctk.CTkComboBox,
            ctk.CTkOptionMenu,
            ctk.CTkTabview,
            ttk.Treeview,
        )

        def recorrer(elemento):
            for hijo in elemento.winfo_children():
                if isinstance(hijo, tipos_navegables):
                    try:
                        estado = str(hijo.cget("state")).lower()
                    except (AttributeError, ValueError):
                        estado = "normal"

                    if estado != "disabled" and hijo.winfo_viewable():
                        controles.append(hijo)

                recorrer(hijo)

        recorrer(contenedor)
        return controles

    @staticmethod
    def control_con_foco_actual(widget, controles, limite):
        """Relaciona el control interno de CustomTkinter con su campo."""
        actual = widget

        while actual is not None:
            if actual in controles:
                return actual

            if actual == limite:
                break

            actual = getattr(actual, "master", None)

        return None

    @staticmethod
    def enfocar_control(control):
        """Coloca el cursor en la parte editable real del control."""
        entrada_interna = getattr(control, "_entry", None)

        if entrada_interna is not None:
            entrada_interna.focus_set()
        else:
            control.focus_set()

    def mover_foco_formulario(self, evento, direccion):
        """Recorre los controles y vuelve al inicio al llegar al final."""
        ventana_activa = evento.widget.winfo_toplevel()
        contenedor = (
            self.contenedor
            if str(ventana_activa) == str(self)
            else ventana_activa
        )
        controles = self.controles_editables_visibles(contenedor)

        if not controles:
            return None

        actual = self.control_con_foco_actual(
            evento.widget,
            controles,
            contenedor,
        )

        if actual is None:
            destino = controles[0] if direccion > 0 else controles[-1]
        else:
            indice = controles.index(actual)
            nuevo_indice = (indice + direccion) % len(controles)
            destino = controles[nuevo_indice]

        self.enfocar_control(destino)
        return "break"

    @staticmethod
    def filas_visibles_treeview(tabla, padre=""):
        """Obtiene las filas visibles de una tabla, incluidas las agrupadas."""
        filas = []
        for item in tabla.get_children(padre):
            filas.append(item)
            if tabla.item(item, "open"):
                filas.extend(
                    AplicacionPXCore.filas_visibles_treeview(tabla, item)
                )
        return filas

    @staticmethod
    def mover_seleccion_treeview(tabla, paso):
        """Mueve la selección una fila y hace ciclo en los extremos."""
        filas = AplicacionPXCore.filas_visibles_treeview(tabla)
        if not filas:
            return

        seleccion = tabla.selection()
        actual = seleccion[0] if seleccion else None
        if actual not in filas:
            destino = filas[0] if paso > 0 else filas[-1]
        else:
            destino = filas[(filas.index(actual) + paso) % len(filas)]

        tabla.selection_set(destino)
        tabla.focus(destino)
        tabla.see(destino)
        tabla.event_generate("<<TreeviewSelect>>")

    @staticmethod
    def cambiar_opcion(control, paso):
        """Cambia una opción de ComboBox u OptionMenu con las flechas."""
        try:
            valores = list(control.cget("values"))
        except (AttributeError, TypeError, ValueError):
            return False

        if not valores:
            return False

        actual = control.get()
        try:
            indice = valores.index(actual)
        except ValueError:
            indice = -1 if paso > 0 else 0

        nuevo = valores[(indice + paso) % len(valores)]
        control.set(nuevo)

        comando = getattr(control, "_command", None)
        if callable(comando):
            comando(nuevo)
        return True

    @staticmethod
    def cambiar_pestana(control, paso):
        """Cambia la pestaña activa con izquierda o derecha."""
        nombres = list(getattr(control, "_name_list", []))
        if not nombres:
            return False

        actual = control.get()
        try:
            indice = nombres.index(actual)
        except ValueError:
            indice = 0

        control.set(nombres[(indice + paso) % len(nombres)])
        return True

    def manejar_flecha(self, evento, direccion):
        """Aplica las flechas según el control que tiene el foco."""
        ventana_activa = evento.widget.winfo_toplevel()
        contenedor = (
            self.contenedor
            if str(ventana_activa) == str(self)
            else ventana_activa
        )
        controles = self.controles_editables_visibles(contenedor)
        actual = self.control_con_foco_actual(
            evento.widget,
            controles,
            contenedor,
        )

        if actual is None or isinstance(actual, ctk.CTkEntry):
            return None

        if isinstance(actual, ttk.Treeview):
            if direccion in ["arriba", "abajo"]:
                # Treeview ya mueve una fila con su navegación nativa.
                return None
            if direccion == "izquierda":
                actual.xview_scroll(-1, "units")
            else:
                actual.xview_scroll(1, "units")
            return "break"

        if isinstance(actual, (ctk.CTkComboBox, ctk.CTkOptionMenu)):
            paso = -1 if direccion in ["arriba", "izquierda"] else 1
            if self.cambiar_opcion(actual, paso):
                return "break"
            return None

        if isinstance(actual, ctk.CTkTabview):
            if direccion not in ["izquierda", "derecha"]:
                return None
            paso = -1 if direccion == "izquierda" else 1
            if self.cambiar_pestana(actual, paso):
                self.after_idle(actual.focus_set)
                return "break"

        return None

    def construir_barra_lateral(self):
        barra = ctk.CTkFrame(
            self,
            width=238,
            corner_radius=0,
            fg_color=COLOR_PANEL,
            border_width=0,
        )
        barra.grid(row=0, column=0, sticky="nsew")
        barra.grid_rowconfigure(10, weight=1)
        barra.grid_propagate(False)

        marca = ctk.CTkFrame(
            barra,
            fg_color="transparent",
        )
        marca.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=20,
            pady=(24, 22),
        )
        marca.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            marca,
            text="BC",
            width=46,
            height=46,
            corner_radius=12,
            fg_color=COLOR_PRIMARIO,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, rowspan=2, padx=(0, 12))

        ctk.CTkLabel(
            marca,
            text="BC Gestión",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(row=0, column=1, sticky="sw")

        ctk.CTkLabel(
            marca,
            text="BC Inversiones EAS",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(row=1, column=1, sticky="nw")

        opciones = [
            ("Inicio", self.mostrar_inicio),
            (
                "Movimientos",
                lambda: self.mostrar_seccion("Movimientos"),
            ),
            (
                "Recursos Humanos",
                self.mostrar_rrhh,
            ),
            ("Socios", lambda: self.mostrar_seccion("Socios")),
            (
                "Facturas",
                self.mostrar_facturas,
            ),
            ("Informes", lambda: Informes.mostrar_informes(self)),
        ]

        for fila, (texto, comando) in enumerate(opciones, start=1):
            boton = ctk.CTkButton(
                barra,
                text=texto,
                command=comando,
                height=44,
                corner_radius=10,
                fg_color="transparent",
                hover_color=COLOR_PANEL_SECUNDARIO,
                text_color=COLOR_TEXTO,
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w",
            )
            boton.grid(
                row=fila,
                column=0,
                sticky="ew",
                padx=14,
                pady=4,
            )
            self.botones_menu[texto] = boton

        ctk.CTkFrame(
            barra,
            height=1,
            fg_color=COLOR_BORDE,
        ).grid(
            row=10,
            column=0,
            sticky="ew",
            padx=18,
            pady=(12, 14),
        )

        ctk.CTkLabel(
            barra,
            text="APARIENCIA",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=11,
            column=0,
            sticky="ew",
            padx=20,
            pady=(0, 8),
        )

        selector_tema = ctk.CTkOptionMenu(
            barra,
            values=["Sistema", "Claro", "Oscuro"],
            command=self.cambiar_tema,
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            text_color=COLOR_TEXTO,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXTO,
        )
        selector_tema.set("Sistema")
        selector_tema.grid(
            row=12,
            column=0,
            sticky="ew",
            padx=18,
            pady=(0, 12),
        )

        ctk.CTkButton(
            barra,
            text="Abrir versión por consola",
            command=self.abrir_consola,
            height=40,
            corner_radius=10,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(
            row=13,
            column=0,
            sticky="ew",
            padx=18,
            pady=(0, 22),
        )

        estado_respaldo = (
            "Respaldo diario listo"
            if self.ruta_respaldo_diario is not None
            else "Revisar respaldo diario"
        )
        ctk.CTkLabel(
            barra,
            text=estado_respaldo,
            font=ctk.CTkFont(size=11),
            text_color=(
                COLOR_VERDE
                if self.ruta_respaldo_diario is not None
                else COLOR_NARANJA
            ),
        ).grid(
            row=14,
            column=0,
            sticky="ew",
            padx=18,
            pady=(0, 16),
        )

    def mostrar_facturas(self):
        self.limpiar_contenedor()
        self.marcar_seleccion("Facturas")

        panel = Facturas.crear_panel_facturas(self.contenedor)
        panel.grid(row=0, column=0, sticky="nsew")

    def mostrar_rrhh(
        self,
        pestana="Gestión de funcionarios",
    ):
        self.limpiar_contenedor()
        self.marcar_seleccion("Recursos Humanos")

        self.panel_rrhh = crear_panel_rrhh(
            self.contenedor,
            pestana,
        )
        self.panel_rrhh.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        self.panel_rrhh.tkraise()

        print(
            "RRHH:",
            self.panel_rrhh.winfo_class(),
            self.panel_rrhh.winfo_children(),
        )
    
    def cambiar_tema(self, tema):
        equivalencias = {
            "Sistema": "system",
            "Claro": "light",
            "Oscuro": "dark",
        }
        ctk.set_appearance_mode(equivalencias[tema])

    def limpiar_contenedor(self):
        self.unbind("<Return>")
        self.unbind("<Escape>")
        self.unbind("<Control-e>")
        self.unbind("<Control-E>")
        self.unbind("<Control-p>")
        self.unbind("<Control-P>")

        for elemento in self.contenedor.winfo_children():
            elemento.destroy()

    def marcar_seleccion(self, nombre):
        for texto, boton in self.botones_menu.items():
            if texto == nombre:
                boton.configure(
                    fg_color=COLOR_PRIMARIO,
                    hover_color=COLOR_PRIMARIO_HOVER,
                    text_color="#FFFFFF",
                )
            else:
                boton.configure(
                    fg_color="transparent",
                    hover_color=COLOR_PANEL_SECUNDARIO,
                    text_color=COLOR_TEXTO,
                )

    def crear_encabezado(self, master, titulo, subtitulo):
        encabezado = ctk.CTkFrame(
            master,
            fg_color="transparent",
        )
        encabezado.pack(fill="x", padx=34, pady=(28, 20))
        encabezado.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            encabezado,
            text=titulo,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            encabezado,
            text=subtitulo,
            font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 0))

        return encabezado

    def mostrar_inicio(self):
        self.limpiar_contenedor()
        self.marcar_seleccion("Inicio")

        pagina = ctk.CTkScrollableFrame(
            self.contenedor,
            fg_color="transparent",
            corner_radius=0,
        )
        pagina.grid(row=0, column=0, sticky="nsew")

        fecha_desde, _ = periodo_actual()
        encabezado = self.crear_encabezado(
            pagina,
            "Panel general",
            (
                "BC Gestión Empresarial · "
                + texto_mes(fecha_desde)
            ),
        )

        ctk.CTkButton(
            encabezado,
            text="Refrescar datos",
            command=self.mostrar_inicio,
            width=132,
            height=38,
            corner_radius=10,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=1, rowspan=2, padx=(20, 0))

        try:
            valores = obtener_indicadores()
            error_indicadores = None
        except (OSError, ValueError, IndexError, TypeError) as error:
            valores = {
                "ingresos": "Sin datos",
                "egresos": "Sin datos",
                "utilidad": "Sin datos",
                "margen": "Sin datos",
                "fondo": "Sin datos",
                "prestamos": "Sin datos",
            }
            error_indicadores = str(error)

        zona_indicadores = ctk.CTkFrame(
            pagina,
            fg_color="transparent",
        )
        zona_indicadores.pack(
            fill="x",
            padx=34,
            pady=(0, 28),
        )

        for columna in range(3):
            zona_indicadores.grid_columnconfigure(
                columna,
                weight=1,
                uniform="indicadores",
            )

        tarjetas = [
            (
                "Ingresos",
                valores["ingresos"],
                COLOR_VERDE,
                "Total del mes actual",
            ),
            (
                "Egresos",
                valores["egresos"],
                COLOR_ROJO,
                "Total del mes actual",
            ),
            (
                "Utilidad",
                valores["utilidad"],
                COLOR_PRIMARIO,
                "Ingresos menos todos los egresos",
            ),
            (
                "Margen",
                valores["margen"],
                COLOR_NARANJA,
                "Utilidad sobre ingresos",
            ),
            (
                "Fondo acumulado",
                valores["fondo"],
                "#7B61FF",
                "Registros mensuales aplicados",
            ),
            (
                "Préstamos activos",
                valores["prestamos"],
                "#00A6B2",
                "Con saldo pendiente",
            ),
        ]

        for indice, tarjeta in enumerate(tarjetas):
            fila = indice // 3
            columna = indice % 3
            TarjetaIndicador(
                zona_indicadores,
                *tarjeta,
            ).grid(
                row=fila,
                column=columna,
                sticky="nsew",
                padx=7,
                pady=7,
            )

        ctk.CTkLabel(
            pagina,
            text="Accesos principales",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).pack(fill="x", padx=34, pady=(0, 12))

        accesos = ctk.CTkFrame(
            pagina,
            fg_color="transparent",
        )
        accesos.pack(fill="x", padx=34, pady=(0, 28))

        for columna in range(3):
            accesos.grid_columnconfigure(
                columna,
                weight=1,
                uniform="accesos",
            )

        botones_acceso = [
            ("Movimientos", "Registrar y consultar la operación diaria"),
            ("Recursos Humanos", "Funcionarios, sueldos y novedades"),
            ("Socios", "Retiros, utilidades y fondo"),
        ]

        for columna, (titulo, descripcion) in enumerate(
            botones_acceso
        ):
            tarjeta = ctk.CTkFrame(
                accesos,
                fg_color=COLOR_PANEL,
                corner_radius=16,
                border_width=1,
                border_color=COLOR_BORDE,
            )
            tarjeta.grid(
                row=0,
                column=columna,
                sticky="nsew",
                padx=7,
            )
            tarjeta.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                tarjeta,
                text=titulo,
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=COLOR_TEXTO,
                anchor="w",
            ).grid(
                row=0,
                column=0,
                sticky="ew",
                padx=18,
                pady=(18, 5),
            )

            ctk.CTkLabel(
                tarjeta,
                text=descripcion,
                font=ctk.CTkFont(size=12),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
                justify="left",
                wraplength=240,
            ).grid(
                row=1,
                column=0,
                sticky="ew",
                padx=18,
            )

            ctk.CTkButton(
                tarjeta,
                text="Ver sección",
                command=lambda nombre=titulo: self.mostrar_seccion(
                    nombre
                ),
                height=36,
                corner_radius=9,
                fg_color=COLOR_PRIMARIO,
                hover_color=COLOR_PRIMARIO_HOVER,
                font=ctk.CTkFont(size=12, weight="bold"),
            ).grid(
                row=2,
                column=0,
                sticky="ew",
                padx=18,
                pady=18,
            )

        if error_indicadores:
            ctk.CTkLabel(
                pagina,
                text=(
                    "No se pudieron leer todos los indicadores: "
                    + error_indicadores
                ),
                font=ctk.CTkFont(size=12),
                text_color=COLOR_ROJO,
                anchor="w",
                wraplength=800,
            ).pack(fill="x", padx=34, pady=(0, 20))

    def mostrar_seccion(self, nombre):
        self.limpiar_contenedor()
        self.marcar_seleccion(nombre)
        datos = SECCIONES[nombre]

        pagina = ctk.CTkScrollableFrame(
            self.contenedor,
            fg_color="transparent",
            corner_radius=0,
        )
        pagina.grid(row=0, column=0, sticky="nsew")

        encabezado = self.crear_encabezado(
            pagina,
            nombre,
            datos["descripcion"],
        )

        ctk.CTkLabel(
            encabezado,
            text=(
                "7 FUNCIONES CONECTADAS"
                if nombre == "Movimientos"
                else (
                    "4 FUNCIONES CONECTADAS"
                    if nombre in ["Socios", "Recursos Humanos"]
                    else "PRÓXIMAMENTE"
                )
            ),
            height=30,
            corner_radius=8,
            fg_color=(
                ("#DDF7EC", "#153D31")
                if nombre in [
                    "Movimientos",
                    "Socios",
                    "Recursos Humanos",
                ]
                else ("#DDE8FF", "#1B3565")
            ),
            text_color=(
                ("#11704F", "#9CE1C5")
                if nombre in [
                    "Movimientos",
                    "Socios",
                    "Recursos Humanos",
                ]
                else ("#174DAF", "#B9D0FF")
            ),
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=1, rowspan=2, padx=(20, 0))

        zona = ctk.CTkFrame(
            pagina,
            fg_color="transparent",
        )
        zona.pack(fill="both", expand=True, padx=34, pady=(0, 24))

        for columna in range(2):
            zona.grid_columnconfigure(
                columna,
                weight=1,
                uniform="opciones",
            )

        for indice, (titulo, descripcion) in enumerate(
            datos["opciones"]
        ):
            fila = indice // 2
            columna = indice % 2
            columnas_ocupadas = 1
            if nombre in ["Socios", "Recursos Humanos"]:
                columna = 0
                columnas_ocupadas = 2
            tarjeta = ctk.CTkFrame(
                zona,
                fg_color=COLOR_PANEL,
                corner_radius=16,
                border_width=1,
                border_color=COLOR_BORDE,
            )
            tarjeta.grid(
                row=fila,
                column=columna,
                columnspan=columnas_ocupadas,
                sticky="nsew",
                padx=7,
                pady=7,
            )
            tarjeta.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                tarjeta,
                text=titulo,
                font=ctk.CTkFont(size=17, weight="bold"),
                text_color=COLOR_TEXTO,
                anchor="w",
            ).grid(
                row=0,
                column=0,
                sticky="ew",
                padx=20,
                pady=(20, 6),
            )

            ctk.CTkLabel(
                tarjeta,
                text=descripcion,
                font=ctk.CTkFont(size=13),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
                justify="left",
                wraplength=360,
            ).grid(
                row=1,
                column=0,
                sticky="ew",
                padx=20,
                pady=(0, 14),
            )

            if nombre == "Movimientos" and titulo == "Cargar día":
                ctk.CTkButton(
                    tarjeta,
                    text="Abrir Cargar día",
                    command=self.mostrar_cargar_dia,
                    height=38,
                    corner_radius=9,
                    fg_color=COLOR_VERDE,
                    hover_color="#12835B",
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).grid(
                    row=2,
                    column=0,
                    sticky="ew",
                    padx=20,
                    pady=(0, 20),
                )
            elif (
                nombre == "Movimientos"
                and titulo == "Gestionar movimientos"
            ):
                ctk.CTkButton(
                    tarjeta,
                    text="Abrir movimientos",
                    command=self.mostrar_gestion_movimientos,
                    height=38,
                    corner_radius=9,
                    fg_color=COLOR_PRIMARIO,
                    hover_color=COLOR_PRIMARIO_HOVER,
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).grid(
                    row=2,
                    column=0,
                    sticky="ew",
                    padx=20,
                    pady=(0, 20),
                )
            elif (
                nombre == "Movimientos"
                and titulo == "Ingresos y egresos adicionales"
            ):
                ctk.CTkButton(
                    tarjeta,
                    text="Abrir adicionales",
                    command=self.mostrar_adicionales,
                    height=38,
                    corner_radius=9,
                    fg_color=COLOR_NARANJA,
                    hover_color="#C77B20",
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).grid(
                    row=2,
                    column=0,
                    sticky="ew",
                    padx=20,
                    pady=(0, 20),
                )
            elif nombre == "Movimientos" and titulo == "Inversiones":
                ctk.CTkButton(
                    tarjeta,
                    text="Abrir inversiones",
                    command=self.mostrar_inversiones,
                    height=38,
                    corner_radius=9,
                    fg_color=COLOR_VERDE,
                    hover_color="#12835B",
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).grid(
                    row=2,
                    column=0,
                    sticky="ew",
                    padx=20,
                    pady=(0, 20),
                )
            elif (
                nombre == "Movimientos"
                and titulo == "Préstamos y cuotas"
            ):
                ctk.CTkButton(
                    tarjeta,
                    text="Abrir préstamos",
                    command=self.mostrar_prestamos,
                    height=38,
                    corner_radius=9,
                    fg_color=COLOR_NARANJA,
                    hover_color="#C77B20",
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).grid(
                    row=2,
                    column=0,
                    sticky="ew",
                    padx=20,
                    pady=(0, 20),
                )
            elif (
                nombre == "Movimientos"
                and titulo == "Cierre mensual"
            ):
                ctk.CTkButton(
                    tarjeta,
                    text="Abrir cierre mensual",
                    command=self.mostrar_cierre_mensual,
                    height=38,
                    corner_radius=9,
                    fg_color=COLOR_PRIMARIO,
                    hover_color=COLOR_PRIMARIO_HOVER,
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).grid(
                    row=2,
                    column=0,
                    sticky="ew",
                    padx=20,
                    pady=(0, 20),
                )
            elif (
                nombre == "Movimientos"
                and titulo == "Importar desde Excel"
            ):
                ctk.CTkButton(
                    tarjeta,
                    text="Abrir importador",
                    command=lambda: ImportadorExcel.abrir_importador(self),
                    height=38,
                    corner_radius=9,
                    fg_color=COLOR_VERDE,
                    hover_color="#12835B",
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).grid(
                    row=2,
                    column=0,
                    sticky="ew",
                    padx=20,
                    pady=(0, 20),
                )
            elif nombre == "Socios":
                ctk.CTkButton(
                    tarjeta,
                    text="Abrir Socios",
                    command=lambda: self.mostrar_socios(
                        "Registrar movimiento"
                    ),
                    height=38,
                    corner_radius=9,
                    fg_color=COLOR_PRIMARIO,
                    hover_color=COLOR_PRIMARIO_HOVER,
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).grid(
                    row=2,
                    column=0,
                    sticky="ew",
                    padx=20,
                    pady=(0, 20),
                )

            elif nombre == "Recursos Humanos":
                ctk.CTkButton(
                tarjeta,
                text="Abrir Recursos Humanos",
                command=lambda: self.mostrar_rrhh(
                    "Gestión de funcionarios"
                    ),
                    height=38,
                    corner_radius=9,
                    fg_color=COLOR_PRIMARIO,
                    hover_color=COLOR_PRIMARIO_HOVER,
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).grid(
                    row=2,
                    column=0,
                    sticky="ew",
                    padx=20,
                    pady=(0, 20),
                )
            else:
                ctk.CTkLabel(
                    tarjeta,
                    text="Disponible actualmente en la consola",
                    height=28,
                    corner_radius=8,
                    fg_color=COLOR_PANEL_SECUNDARIO,
                    text_color=COLOR_TEXTO_SUAVE,
                    font=ctk.CTkFont(size=11, weight="bold"),
                ).grid(
                    row=2,
                    column=0,
                    sticky="w",
                    padx=20,
                    pady=(0, 20),
                )

        aviso = ctk.CTkFrame(
            pagina,
            fg_color=("#EAF1FF", "#142746"),
            corner_radius=14,
            border_width=1,
            border_color=("#CADBFF", "#24416D"),
        )
        aviso.pack(fill="x", padx=41, pady=(0, 28))
        aviso.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            aviso,
            text=(
                (
                    "Cargar día, Gestionar movimientos, Ingresos y "
                    "egresos adicionales, Inversiones y Préstamos "
                    "y cuotas, Cierre mensual e Importar desde Excel "
                    "ya funcionan "
                    "directamente desde esta interfaz."
                )
                if nombre == "Movimientos"
                else (
                    (
                        "Los retiros, el resumen mensual y el fondo "
                        "de estabilidad ya funcionan directamente "
                        "desde esta interfaz."
                    )
                    if nombre == "Socios"
                    else (
                        (
                            "Funcionarios, novedades, liquidaciones, "
                            "recibos y salario mínimo ya funcionan "
                            "directamente desde esta interfaz."
                        )
                        if nombre == "Recursos Humanos"
                        else (
                            "La navegación visual ya está preparada. "
                            "Los formularios se conectarán por etapas para "
                            "mantener intactos los cálculos actuales."
                        )
                    )
                )
            ),
            font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXTO,
            anchor="w",
            justify="left",
            wraplength=720,
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=18,
            pady=18,
        )

        ctk.CTkButton(
            aviso,
            text="Abrir consola",
            command=self.abrir_consola,
            width=130,
            height=36,
            corner_radius=9,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(
            row=0,
            column=1,
            padx=18,
            pady=14,
        )

    def mostrar_cargar_dia(self):
        self.limpiar_contenedor()
        self.marcar_seleccion("Movimientos")
        self.movimientos_sesion = []
        self.tipo_movimiento_actual = "Ingreso"
        self.bind("<Return>", self.atajo_guardar_movimiento)
        self.bind("<Escape>", self.atajo_volver_a_movimientos)

        pagina = ctk.CTkScrollableFrame(
            self.contenedor,
            fg_color="transparent",
            corner_radius=0,
        )
        pagina.grid(row=0, column=0, sticky="nsew")

        encabezado = self.crear_encabezado(
            pagina,
            "Cargar día",
            (
                "La fecha se completa una sola vez y se reutiliza "
                "en todos los movimientos de esta carga."
            ),
        )

        ctk.CTkButton(
            encabezado,
            text="Volver a Movimientos",
            command=lambda: self.mostrar_seccion("Movimientos"),
            width=170,
            height=38,
            corner_radius=10,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, rowspan=2, padx=(20, 0))

        bloque_fecha = ctk.CTkFrame(
            pagina,
            fg_color=COLOR_PANEL,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        bloque_fecha.pack(fill="x", padx=34, pady=(0, 16))
        bloque_fecha.grid_columnconfigure(1, weight=1)
        bloque_fecha.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            bloque_fecha,
            text="Fecha del día",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(20, 14),
            pady=20,
        )

        self.entrada_fecha_carga = ctk.CTkEntry(
            bloque_fecha,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="DD-MM-AAAA",
        )
        self.entrada_fecha_carga.insert(
            0,
            self.fecha_carga_actual,
        )
        self.entrada_fecha_carga.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(0, 18),
            pady=(18, 10),
        )
        self.entrada_fecha_carga.bind(
            "<KeyRelease>",
            self.actualizar_indicador_carga,
        )

        ctk.CTkLabel(
            bloque_fecha,
            text="Unidad activa",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0,
            column=2,
            sticky="w",
            padx=(6, 14),
            pady=(18, 10),
        )

        self.combo_unidad_carga = ctk.CTkComboBox(
            bloque_fecha,
            values=Movimientos.UNIDADES,
            command=self.seleccionar_unidad_carga,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXTO,
            text_color=COLOR_TEXTO,
            state="readonly",
        )
        self.combo_unidad_carga.set(self.unidad_carga_actual)
        self.combo_unidad_carga.grid(
            row=0,
            column=3,
            sticky="ew",
            padx=(0, 20),
            pady=(18, 10),
        )

        self.etiqueta_unidad_fecha_activa = ctk.CTkLabel(
            bloque_fecha,
            text="",
            height=36,
            corner_radius=9,
            fg_color=COLOR_PRIMARIO,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.etiqueta_unidad_fecha_activa.grid(
            row=1,
            column=0,
            columnspan=4,
            sticky="ew",
            padx=20,
            pady=(0, 18),
        )
        self.actualizar_indicador_carga()

        bloque_tipos = ctk.CTkFrame(
            pagina,
            fg_color=COLOR_PANEL,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        bloque_tipos.pack(fill="x", padx=34, pady=(0, 16))

        ctk.CTkLabel(
            bloque_tipos,
            text="1. Elegí el tipo de movimiento",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).pack(fill="x", padx=20, pady=(20, 12))

        zona_tipos = ctk.CTkFrame(
            bloque_tipos,
            fg_color="transparent",
        )
        zona_tipos.pack(fill="x", padx=14, pady=(0, 16))

        for columna in range(3):
            zona_tipos.grid_columnconfigure(
                columna,
                weight=1,
                uniform="tipos",
            )

        self.botones_tipo_movimiento = {}

        for indice, tipo in enumerate(TIPOS_MOVIMIENTO_GUI):
            boton = ctk.CTkButton(
                zona_tipos,
                text=tipo,
                command=lambda valor=tipo: (
                    self.seleccionar_tipo_movimiento_grafico(valor)
                ),
                height=42,
                corner_radius=9,
                fg_color=COLOR_PANEL_SECUNDARIO,
                hover_color=COLOR_BORDE,
                text_color=COLOR_TEXTO,
                font=ctk.CTkFont(size=12, weight="bold"),
            )
            boton.grid(
                row=indice // 3,
                column=indice % 3,
                sticky="ew",
                padx=6,
                pady=6,
            )
            self.botones_tipo_movimiento[tipo] = boton

        self.formulario_movimiento = ctk.CTkFrame(
            pagina,
            fg_color=COLOR_PANEL,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        self.formulario_movimiento.pack(
            fill="x",
            padx=34,
            pady=(0, 16),
        )
        self.formulario_movimiento.grid_columnconfigure(0, weight=1)
        self.formulario_movimiento.grid_columnconfigure(1, weight=1)

        acciones = ctk.CTkFrame(
            pagina,
            fg_color="transparent",
        )
        acciones.pack(fill="x", padx=34, pady=(0, 16))
        acciones.grid_columnconfigure(0, weight=1)

        self.etiqueta_estado_carga = ctk.CTkLabel(
            acciones,
            text="Completá los campos y registrá el movimiento.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        )
        self.etiqueta_estado_carga.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 16),
        )

        ctk.CTkButton(
            acciones,
            text="Registrar movimiento",
            command=self.guardar_movimiento_grafico,
            width=190,
            height=42,
            corner_radius=10,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=1, padx=(0, 10))

        ctk.CTkButton(
            acciones,
            text="Finalizar carga del día",
            command=self.finalizar_carga_grafica,
            width=180,
            height=42,
            corner_radius=10,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=2)

        bloque_resumen = ctk.CTkFrame(
            pagina,
            fg_color=COLOR_PANEL,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        bloque_resumen.pack(fill="x", padx=34, pady=(0, 28))
        bloque_resumen.grid_columnconfigure(0, weight=1)

        self.etiqueta_cantidad_carga = ctk.CTkLabel(
            bloque_resumen,
            text="Movimientos registrados en esta carga: 0",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        )
        self.etiqueta_cantidad_carga.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=20,
            pady=(18, 8),
        )

        self.resumen_carga = ctk.CTkTextbox(
            bloque_resumen,
            height=120,
            corner_radius=10,
            fg_color=COLOR_PANEL_SECUNDARIO,
            border_width=1,
            border_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=12),
            activate_scrollbars=True,
        )
        self.resumen_carga.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=20,
            pady=(0, 20),
        )
        self.resumen_carga.insert(
            "1.0",
            "Los movimientos que registres aparecerán aquí.",
        )
        self.resumen_carga.configure(state="disabled")

        self.seleccionar_tipo_movimiento_grafico("Ingreso")

    def actualizar_indicador_carga(self, _evento=None):
        fecha = self.entrada_fecha_carga.get().strip()
        fecha_visible = fecha or "sin fecha"
        self.etiqueta_unidad_fecha_activa.configure(
            text=(
                f"CARGANDO: {self.unidad_carga_actual} "
                f"— {fecha_visible}"
            )
        )

    def seleccionar_unidad_carga(self, unidad):
        if unidad not in Movimientos.UNIDADES:
            return

        self.unidad_carga_actual = unidad
        self.actualizar_indicador_carga()

        control_unidad = self.campos_movimiento.get("unidad")
        if control_unidad is not None:
            control_unidad.set(unidad)

        control_origen = self.campos_movimiento.get("origen")
        if control_origen is not None:
            control_origen.set(unidad)
            self.actualizar_campo_persona_deposito(unidad)

        if self.tipo_movimiento_actual == "Transferencia interna":
            destino = self.campos_movimiento.get("destino")
            if destino is not None and destino.get() == unidad:
                alternativa = next(
                    (
                        item
                        for item in Movimientos.UNIDADES
                        if item != unidad
                    ),
                    unidad,
                )
                destino.set(alternativa)

    def seleccionar_unidad_desde_formulario(self, unidad):
        if unidad in Movimientos.UNIDADES:
            self.combo_unidad_carga.set(unidad)
            self.seleccionar_unidad_carga(unidad)

    def seleccionar_origen_deposito(self, origen):
        self.actualizar_campo_persona_deposito(origen)
        self.seleccionar_unidad_desde_formulario(origen)

    def atajo_guardar_movimiento(self, _evento=None):
        self.guardar_movimiento_grafico()
        return "break"

    def atajo_volver_a_movimientos(self, _evento=None):
        self.mostrar_seccion("Movimientos")
        return "break"

    def crear_etiqueta_campo(self, texto, fila, columna):
        ctk.CTkLabel(
            self.formulario_movimiento,
            text=texto,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=fila,
            column=columna,
            sticky="ew",
            padx=20,
            pady=(8, 5),
        )

    def crear_combo_campo(
        self,
        clave,
        valores,
        fila,
        columna,
        comando=None,
    ):
        combo = ctk.CTkComboBox(
            self.formulario_movimiento,
            values=valores,
            command=comando,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXTO,
            text_color=COLOR_TEXTO,
            state="readonly",
        )
        combo.set(valores[0])
        combo.grid(
            row=fila,
            column=columna,
            sticky="ew",
            padx=20,
            pady=(0, 10),
        )
        self.campos_movimiento[clave] = combo
        return combo

    def crear_entrada_campo(
        self,
        clave,
        fila,
        columna,
        marcador,
    ):
        entrada = ctk.CTkEntry(
            self.formulario_movimiento,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text=marcador,
        )
        entrada.grid(
            row=fila,
            column=columna,
            sticky="ew",
            padx=20,
            pady=(0, 10),
        )
        self.campos_movimiento[clave] = entrada
        return entrada

    def seleccionar_tipo_movimiento_grafico(self, tipo):
        self.tipo_movimiento_actual = tipo

        for nombre, boton in self.botones_tipo_movimiento.items():
            if nombre == tipo:
                boton.configure(
                    fg_color=COLOR_PRIMARIO,
                    hover_color=COLOR_PRIMARIO_HOVER,
                    text_color="#FFFFFF",
                )
            else:
                boton.configure(
                    fg_color=COLOR_PANEL_SECUNDARIO,
                    hover_color=COLOR_BORDE,
                    text_color=COLOR_TEXTO,
                )

        for elemento in self.formulario_movimiento.winfo_children():
            elemento.destroy()

        self.campos_movimiento = {}
        self.etiqueta_persona_deposito = None

        explicaciones = {
            "Ingreso": "Suma como ingreso de la unidad elegida.",
            "Egreso": "Resta como egreso de la unidad elegida.",
            "Transferencia interna": (
                "Mueve dinero entre unidades sin cambiar la utilidad."
            ),
            "Depósito interno": (
                "Mueve dinero a un banco y no suma como ingreso."
            ),
            "Cobro externo": (
                "Registra dinero externo recibido y sí suma como ingreso."
            ),
        }

        ctk.CTkLabel(
            self.formulario_movimiento,
            text=f"2. Datos de {tipo}",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=20,
            pady=(20, 3),
        )

        ctk.CTkLabel(
            self.formulario_movimiento,
            text=explicaciones[tipo],
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=20,
            pady=(0, 10),
        )

        if tipo in ["Ingreso", "Egreso"]:
            self.crear_etiqueta_campo("Unidad", 2, 0)
            unidad = self.crear_combo_campo(
                "unidad",
                Movimientos.UNIDADES,
                3,
                0,
                self.seleccionar_unidad_desde_formulario,
            )
            unidad.set(self.unidad_carga_actual)

        elif tipo == "Transferencia interna":
            self.crear_etiqueta_campo("Unidad de origen", 2, 0)
            self.crear_etiqueta_campo("Unidad de destino", 2, 1)
            origen = self.crear_combo_campo(
                "origen",
                Movimientos.UNIDADES,
                3,
                0,
                self.seleccionar_unidad_desde_formulario,
            )
            origen.set(self.unidad_carga_actual)
            destino = self.crear_combo_campo(
                "destino",
                Movimientos.UNIDADES,
                3,
                1,
            )

            alternativa = next(
                (
                    unidad
                    for unidad in Movimientos.UNIDADES
                    if unidad != self.unidad_carga_actual
                ),
                self.unidad_carga_actual,
            )
            destino.set(alternativa)

        elif tipo == "Depósito interno":
            self.crear_etiqueta_campo("Origen del depósito", 2, 0)
            self.crear_etiqueta_campo("Banco de destino", 2, 1)
            origen = self.crear_combo_campo(
                "origen",
                Movimientos.UNIDADES + ["Otra persona"],
                3,
                0,
                self.seleccionar_origen_deposito,
            )
            origen.set(self.unidad_carga_actual)
            self.crear_entrada_campo(
                "banco",
                3,
                1,
                "Ej.: Ueno, Itaú, Continental",
            )
            self.etiqueta_persona_deposito = ctk.CTkLabel(
                self.formulario_movimiento,
                text="Nombre de la persona",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            )
            self.etiqueta_persona_deposito.grid(
                row=4,
                column=0,
                sticky="ew",
                padx=20,
                pady=(8, 5),
            )
            persona = self.crear_entrada_campo(
                "persona",
                5,
                0,
                "Nombre completo",
            )
            self.etiqueta_persona_deposito.grid_remove()
            persona.grid_remove()

        elif tipo == "Cobro externo":
            self.crear_etiqueta_campo(
                "Banco que recibió el cobro",
                2,
                0,
            )
            self.crear_etiqueta_campo("Unidad", 2, 1)
            self.crear_entrada_campo(
                "banco",
                3,
                0,
                "Ej.: Ueno, Itaú, Continental",
            )
            unidad = self.crear_combo_campo(
                "unidad",
                Movimientos.UNIDADES,
                3,
                1,
                self.seleccionar_unidad_desde_formulario,
            )
            unidad.set(self.unidad_carga_actual)

        fila_monto = 6 if tipo == "Depósito interno" else 4
        self.crear_etiqueta_campo(
            "Monto en guaraníes",
            fila_monto,
            0,
        )
        self.crear_entrada_campo(
            "monto",
            fila_monto + 1,
            0,
            "Ej.: 1.500.000",
        )

        ctk.CTkLabel(
            self.formulario_movimiento,
            text="Podés escribir el monto con o sin puntos.",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=fila_monto + 1,
            column=1,
            sticky="w",
            padx=20,
            pady=(0, 10),
        )

        self.etiqueta_estado_carga.configure(
            text="Completá los campos y registrá el movimiento.",
            text_color=COLOR_TEXTO_SUAVE,
        )

    def actualizar_campo_persona_deposito(self, origen):
        persona = self.campos_movimiento.get("persona")

        if persona is None or self.etiqueta_persona_deposito is None:
            return

        if origen == "Otra persona":
            self.etiqueta_persona_deposito.grid()
            persona.grid()
            persona.focus()
        else:
            self.etiqueta_persona_deposito.grid_remove()
            persona.grid_remove()

    def guardar_movimiento_grafico(self):
        fecha = self.entrada_fecha_carga.get()
        campos = {
            clave: control.get()
            for clave, control in self.campos_movimiento.items()
        }

        try:
            linea, datos = construir_movimiento_grafico(
                self.tipo_movimiento_actual,
                fecha,
                campos.get("monto", ""),
                campos,
            )
            movimientos = Movimientos.leer_datos(
                Movimientos.RUTA_MOVIMIENTOS
            )
            movimientos.append(linea)
            Movimientos.guardar_datos(
                Movimientos.RUTA_MOVIMIENTOS,
                movimientos,
            )
        except ValueError as error:
            self.etiqueta_estado_carga.configure(
                text=str(error),
                text_color=COLOR_ROJO,
            )
            return
        except OSError as error:
            self.etiqueta_estado_carga.configure(
                text=f"No se pudo guardar el movimiento: {error}",
                text_color=COLOR_ROJO,
            )
            return

        self.movimientos_sesion.append(datos)
        self.fecha_carga_actual = datos["fecha"]
        unidad_usada = (
            datos["destino"]
            if datos["tipo"] in ("Ingreso", "Cobro externo")
            else datos["origen"]
        )
        if unidad_usada in Movimientos.UNIDADES:
            self.unidad_carga_actual = unidad_usada
            self.combo_unidad_carga.set(unidad_usada)
        self.actualizar_indicador_carga()
        self.etiqueta_estado_carga.configure(
            text="Movimiento registrado correctamente.",
            text_color=COLOR_VERDE,
        )
        self.etiqueta_cantidad_carga.configure(
            text=(
                "Movimientos registrados en esta carga: "
                + str(len(self.movimientos_sesion))
            )
        )
        self.actualizar_resumen_carga()

        entrada_monto = self.campos_movimiento.get("monto")
        if entrada_monto is not None:
            entrada_monto.delete(0, "end")
            entrada_monto.focus()

    def actualizar_resumen_carga(self):
        lineas = []
        cantidad = len(self.movimientos_sesion)

        for desplazamiento, datos in enumerate(
            reversed(self.movimientos_sesion)
        ):
            numero = cantidad - desplazamiento
            lineas.append(
                f"{numero}. {datos['fecha']} | {datos['tipo']} | "
                f"{datos['origen']} → {datos['destino']} | "
                f"Gs. {Movimientos.formatear_monto(datos['monto'])}"
            )

        self.resumen_carga.configure(state="normal")
        self.resumen_carga.delete("1.0", "end")
        self.resumen_carga.insert("1.0", "\n".join(lineas))
        self.resumen_carga.configure(state="disabled")

    def finalizar_carga_grafica(self):
        cantidad = len(self.movimientos_sesion)
        texto = (
            f"Carga finalizada. Movimientos registrados: {cantidad}."
            if cantidad != 1
            else "Carga finalizada. Movimiento registrado: 1."
        )
        messagebox.showinfo(
            "Cargar día",
            texto,
            parent=self,
        )
        self.mostrar_seccion("Movimientos")

    def mostrar_gestion_movimientos(self):
        self.limpiar_contenedor()
        self.marcar_seleccion("Movimientos")
        self.pagina_movimientos = 0
        self.posicion_movimiento_seleccionado = None
        self.bind("<Return>", self.atajo_aplicar_filtros_movimientos)
        self.bind("<Escape>", self.atajo_volver_a_movimientos)

        pagina = ctk.CTkFrame(
            self.contenedor,
            fg_color="transparent",
            corner_radius=0,
        )
        pagina.grid(row=0, column=0, sticky="nsew")

        encabezado = self.crear_encabezado(
            pagina,
            "Ver, modificar o eliminar movimientos",
            (
                "Filtrá los registros, seleccioná una fila y elegí "
                "la acción que necesitás."
            ),
        )

        ctk.CTkButton(
            encabezado,
            text="Volver a Movimientos",
            command=lambda: self.mostrar_seccion("Movimientos"),
            width=170,
            height=38,
            corner_radius=10,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, rowspan=2, padx=(20, 0))

        filtros = ctk.CTkFrame(
            pagina,
            fg_color=COLOR_PANEL,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        filtros.pack(
            fill="x",
            padx=34,
            pady=(0, 14),
        )

        for columna in range(6):
            filtros.grid_columnconfigure(
                columna,
                weight=1 if columna < 4 else 0,
            )

        fecha_desde, fecha_hasta = periodo_actual()
        campos_filtro = [
            ("Desde", fecha_desde.strftime("%d-%m-%Y")),
            ("Hasta", fecha_hasta.strftime("%d-%m-%Y")),
        ]

        for columna, (titulo, valor) in enumerate(campos_filtro):
            ctk.CTkLabel(
                filtros,
                text=titulo,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            ).grid(
                row=0,
                column=columna,
                sticky="ew",
                padx=(18 if columna == 0 else 8, 8),
                pady=(14, 4),
            )
            entrada = ctk.CTkEntry(
                filtros,
                height=38,
                corner_radius=9,
                border_color=COLOR_BORDE,
                fg_color=COLOR_PANEL_SECUNDARIO,
                text_color=COLOR_TEXTO,
                placeholder_text="DD-MM-AAAA",
            )
            entrada.insert(0, valor)
            entrada.grid(
                row=1,
                column=columna,
                sticky="ew",
                padx=(18 if columna == 0 else 8, 8),
                pady=(0, 14),
            )

            if columna == 0:
                self.filtro_fecha_desde = entrada
            else:
                self.filtro_fecha_hasta = entrada

        ctk.CTkLabel(
            filtros,
            text="Tipo",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=0,
            column=2,
            sticky="ew",
            padx=8,
            pady=(14, 4),
        )

        self.filtro_tipo_movimiento = ctk.CTkComboBox(
            filtros,
            values=["Todos"] + TIPOS_MOVIMIENTO_GUI,
            height=38,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXTO,
            text_color=COLOR_TEXTO,
            state="readonly",
        )
        self.filtro_tipo_movimiento.set("Todos")
        self.filtro_tipo_movimiento.grid(
            row=1,
            column=2,
            sticky="ew",
            padx=8,
            pady=(0, 14),
        )

        ctk.CTkLabel(
            filtros,
            text="Sucursal",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=0,
            column=3,
            sticky="ew",
            padx=8,
            pady=(14, 4),
        )

        self.filtro_unidad_movimiento = ctk.CTkComboBox(
            filtros,
            values=["Todas"] + Movimientos.UNIDADES,
            height=38,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXTO,
            text_color=COLOR_TEXTO,
            state="readonly",
        )
        self.filtro_unidad_movimiento.set("Todas")
        self.filtro_unidad_movimiento.grid(
            row=1,
            column=3,
            sticky="ew",
            padx=8,
            pady=(0, 14),
        )

        ctk.CTkButton(
            filtros,
            text="Aplicar filtros",
            command=self.aplicar_filtros_movimientos,
            width=125,
            height=38,
            corner_radius=9,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(
            row=1,
            column=4,
            padx=(10, 6),
            pady=(0, 14),
        )

        ctk.CTkButton(
            filtros,
            text="Ver todos",
            command=self.mostrar_todos_los_movimientos,
            width=105,
            height=38,
            corner_radius=9,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(
            row=1,
            column=5,
            padx=(6, 18),
            pady=(0, 14),
        )

        bloque_tabla = ctk.CTkFrame(
            pagina,
            fg_color=COLOR_PANEL,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        bloque_tabla.pack(
            fill="both",
            expand=True,
            padx=34,
            pady=(0, 14),
        )
        bloque_tabla.grid_rowconfigure(1, weight=1)
        bloque_tabla.grid_columnconfigure(0, weight=1)

        cabecera_tabla = ctk.CTkFrame(
            bloque_tabla,
            fg_color="transparent",
        )
        cabecera_tabla.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=18,
            pady=(14, 8),
        )
        cabecera_tabla.grid_columnconfigure(0, weight=1)

        self.etiqueta_resultados_movimientos = ctk.CTkLabel(
            cabecera_tabla,
            text="Cargando movimientos...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        )
        self.etiqueta_resultados_movimientos.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        self.etiqueta_estado_movimientos = ctk.CTkLabel(
            cabecera_tabla,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="e",
        )
        self.etiqueta_estado_movimientos.grid(
            row=0,
            column=1,
            padx=(12, 0),
        )

        zona_tree = ctk.CTkFrame(
            bloque_tabla,
            fg_color=COLOR_PANEL_SECUNDARIO,
            corner_radius=10,
        )
        zona_tree.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=18,
            pady=(0, 10),
        )
        zona_tree.grid_rowconfigure(0, weight=1)
        zona_tree.grid_columnconfigure(0, weight=1)

        estilo = ttk.Style(self)
        estilo.configure(
            "PX.Treeview",
            rowheight=34,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        estilo.configure(
            "PX.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
        )
        estilo.map(
            "PX.Treeview",
            background=[("selected", COLOR_PRIMARIO)],
            foreground=[("selected", "#FFFFFF")],
        )

        columnas = ("tipo", "origen", "destino", "monto")
        self.tabla_movimientos = ttk.Treeview(
            zona_tree,
            columns=columnas,
            show="tree headings",
            selectmode="browse",
            style="PX.Treeview",
        )

        configuracion_columnas = {
            "tipo": ("Tipo", 145, "w"),
            "origen": ("Origen", 105, "w"),
            "destino": ("Destino", 105, "w"),
            "monto": ("Monto", 130, "e"),
        }

        self.tabla_movimientos.heading(
            "#0",
            text="Fecha y sucursal · resumen del día",
        )
        self.tabla_movimientos.column(
            "#0",
            width=450,
            minwidth=310,
            anchor="w",
            stretch=True,
        )

        for columna, (titulo, ancho, ancla) in (
            configuracion_columnas.items()
        ):
            self.tabla_movimientos.heading(columna, text=titulo)
            self.tabla_movimientos.column(
                columna,
                width=ancho,
                minwidth=80,
                anchor=ancla,
                stretch=True,
            )

        barra_vertical = ttk.Scrollbar(
            zona_tree,
            orient="vertical",
            command=self.tabla_movimientos.yview,
        )
        self.tabla_movimientos.configure(
            yscrollcommand=barra_vertical.set
        )
        self.tabla_movimientos.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        barra_vertical.grid(row=0, column=1, sticky="ns")
        self.tabla_movimientos.bind(
            "<<TreeviewSelect>>",
            self.seleccionar_fila_movimiento,
        )
        self.tabla_movimientos.bind(
            "<Double-1>",
            self.manejar_doble_clic_movimiento,
        )

        pie_tabla = ctk.CTkFrame(
            bloque_tabla,
            fg_color="transparent",
        )
        pie_tabla.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=18,
            pady=(0, 14),
        )
        pie_tabla.grid_columnconfigure(1, weight=1)

        self.boton_pagina_anterior = ctk.CTkButton(
            pie_tabla,
            text="Anterior",
            command=lambda: self.cambiar_pagina_movimientos(-1),
            width=90,
            height=34,
            corner_radius=8,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.boton_pagina_anterior.grid(row=0, column=0)

        self.etiqueta_pagina_movimientos = ctk.CTkLabel(
            pie_tabla,
            text="Página 1 de 1",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.etiqueta_pagina_movimientos.grid(
            row=0,
            column=1,
            sticky="ew",
        )

        self.boton_pagina_siguiente = ctk.CTkButton(
            pie_tabla,
            text="Siguiente",
            command=lambda: self.cambiar_pagina_movimientos(1),
            width=90,
            height=34,
            corner_radius=8,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.boton_pagina_siguiente.grid(row=0, column=2)

        acciones = ctk.CTkFrame(
            pagina,
            fg_color="transparent",
        )
        acciones.pack(
            fill="x",
            padx=34,
            pady=(0, 24),
        )
        acciones.grid_columnconfigure(0, weight=1)

        self.etiqueta_seleccion_movimiento = ctk.CTkLabel(
            acciones,
            text="Seleccioná un movimiento de la tabla.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        )
        self.etiqueta_seleccion_movimiento.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 14),
        )

        self.boton_modificar_movimiento = ctk.CTkButton(
            acciones,
            text="Modificar seleccionado",
            command=self.abrir_edicion_movimiento,
            width=175,
            height=40,
            corner_radius=9,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
            state="disabled",
        )
        self.boton_modificar_movimiento.grid(
            row=0,
            column=1,
            padx=(0, 8),
        )

        self.boton_eliminar_movimiento = ctk.CTkButton(
            acciones,
            text="Eliminar seleccionado",
            command=self.eliminar_movimiento_grafico,
            width=165,
            height=40,
            corner_radius=9,
            fg_color=COLOR_ROJO,
            hover_color="#BE3F3F",
            font=ctk.CTkFont(size=12, weight="bold"),
            state="disabled",
        )
        self.boton_eliminar_movimiento.grid(row=0, column=2)

        self.aplicar_filtros_movimientos()

    def aplicar_filtros_movimientos(self):
        try:
            lineas = Movimientos.leer_datos(
                Movimientos.RUTA_MOVIMIENTOS
            )
            self.movimientos_filtrados = filtrar_movimientos_graficos(
                lineas,
                self.filtro_fecha_desde.get(),
                self.filtro_fecha_hasta.get(),
                self.filtro_tipo_movimiento.get(),
                self.filtro_unidad_movimiento.get(),
            )
        except ValueError as error:
            self.etiqueta_estado_movimientos.configure(
                text=str(error),
                text_color=COLOR_ROJO,
            )
            return
        except OSError as error:
            self.etiqueta_estado_movimientos.configure(
                text=f"No se pudieron leer los datos: {error}",
                text_color=COLOR_ROJO,
            )
            return

        self.pagina_movimientos = 0
        self.etiqueta_estado_movimientos.configure(
            text="Filtros aplicados.",
            text_color=COLOR_VERDE,
        )
        self.actualizar_tabla_movimientos()

    def mostrar_todos_los_movimientos(self):
        self.filtro_fecha_desde.delete(0, "end")
        self.filtro_fecha_hasta.delete(0, "end")
        self.filtro_tipo_movimiento.set("Todos")
        self.filtro_unidad_movimiento.set("Todas")
        self.aplicar_filtros_movimientos()

    def atajo_aplicar_filtros_movimientos(self, _evento=None):
        self.aplicar_filtros_movimientos()
        return "break"

    def actualizar_tabla_movimientos(self):
        for item in self.tabla_movimientos.get_children():
            self.tabla_movimientos.delete(item)

        self.mapa_items_movimientos = {}
        cantidad = len(self.movimientos_filtrados)
        fechas_ordenadas = []

        for _posicion, datos in self.movimientos_filtrados:
            if datos["fecha"] not in fechas_ordenadas:
                fechas_ordenadas.append(datos["fecha"])

        total_paginas = max(
            1,
            (len(fechas_ordenadas) + MOVIMIENTOS_POR_PAGINA - 1)
            // MOVIMIENTOS_POR_PAGINA,
        )
        self.pagina_movimientos = min(
            max(self.pagina_movimientos, 0),
            total_paginas - 1,
        )
        inicio = self.pagina_movimientos * MOVIMIENTOS_POR_PAGINA
        fin = inicio + MOVIMIENTOS_POR_PAGINA
        fechas_pagina = set(fechas_ordenadas[inicio:fin])
        registros_pagina = [
            (posicion, datos)
            for posicion, datos in self.movimientos_filtrados
            if datos["fecha"] in fechas_pagina
        ]
        grupos = {}
        unidad_filtrada = self.filtro_unidad_movimiento.get()

        for posicion, datos in registros_pagina:
            unidades = unidades_relacionadas_movimiento(datos)

            if unidad_filtrada != "Todas":
                unidades = [
                    unidad
                    for unidad in unidades
                    if unidad == unidad_filtrada
                ]

            for unidad in unidades:
                clave = (datos["fecha"], unidad)
                grupos.setdefault(clave, []).append((posicion, datos))

        orden_unidades = Movimientos.UNIDADES + ["Otros"]
        contador_items = 0

        for indice_fecha, fecha in enumerate(
            fechas_ordenadas[inicio:fin]
        ):
            item_fecha = f"fecha:{self.pagina_movimientos}:{indice_fecha}"
            self.tabla_movimientos.insert(
                "",
                "end",
                iid=item_fecha,
                text=fecha,
                open=True,
                values=("", "", "", ""),
            )

            for unidad in orden_unidades:
                registros = grupos.get((fecha, unidad), [])

                if not registros:
                    continue

                resumen = resumir_movimientos_de_unidad(
                    unidad,
                    registros,
                )
                detalles_internos = []

                if (
                    resumen["transferencias_recibidas"]
                    or resumen["transferencias_enviadas"]
                ):
                    detalles_internos.append(
                        "Transf. "
                        f"+Gs. {Movimientos.formatear_monto(resumen['transferencias_recibidas'])}"
                        " / "
                        f"−Gs. {Movimientos.formatear_monto(resumen['transferencias_enviadas'])}"
                    )

                if resumen["depositos"]:
                    detalles_internos.append(
                        "Depósitos Gs. "
                        + Movimientos.formatear_monto(
                            resumen["depositos"]
                        )
                    )

                texto_unidad = unidad
                if detalles_internos:
                    texto_unidad += " · " + " · ".join(detalles_internos)

                item_unidad = (
                    f"unidad:{self.pagina_movimientos}:"
                    f"{indice_fecha}:{orden_unidades.index(unidad)}"
                )
                self.tabla_movimientos.insert(
                    item_fecha,
                    "end",
                    iid=item_unidad,
                    text=texto_unidad,
                    open=True,
                    values=(
                        "Ingresos Gs. "
                        + Movimientos.formatear_monto(
                            resumen["ingresos"]
                        ),
                        "Egresos Gs. "
                        + Movimientos.formatear_monto(
                            resumen["egresos"]
                        ),
                        "Resultado",
                        "Gs. "
                        + Movimientos.formatear_monto(
                            resumen["resultado"]
                        ),
                    ),
                )

                for posicion, datos in registros:
                    item_movimiento = (
                        f"mov:{posicion}:{contador_items}"
                    )
                    contador_items += 1
                    self.mapa_items_movimientos[
                        item_movimiento
                    ] = posicion
                    self.tabla_movimientos.insert(
                        item_unidad,
                        "end",
                        iid=item_movimiento,
                        text="Detalle",
                        values=(
                            tipo_movimiento_para_gui(datos["tipo"]),
                            datos["origen"],
                            datos["destino"],
                            "Gs. " + Movimientos.formatear_monto(
                                datos["monto"]
                            ),
                        ),
                    )

        self.etiqueta_resultados_movimientos.configure(
            text=(
                f"{cantidad} movimiento"
                if cantidad == 1
                else f"{cantidad} movimientos"
            )
        )
        self.etiqueta_pagina_movimientos.configure(
            text=(
                f"Página {self.pagina_movimientos + 1} "
                f"de {total_paginas}"
            )
        )
        self.boton_pagina_anterior.configure(
            state=(
                "normal"
                if self.pagina_movimientos > 0
                else "disabled"
            )
        )
        self.boton_pagina_siguiente.configure(
            state=(
                "normal"
                if self.pagina_movimientos < total_paginas - 1
                else "disabled"
            )
        )
        self.posicion_movimiento_seleccionado = None
        self.etiqueta_seleccion_movimiento.configure(
            text=(
                "No hay movimientos para mostrar."
                if cantidad == 0
                else "Seleccioná un movimiento de la tabla."
            ),
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.boton_modificar_movimiento.configure(state="disabled")
        self.boton_eliminar_movimiento.configure(state="disabled")

    def cambiar_pagina_movimientos(self, desplazamiento):
        self.pagina_movimientos += desplazamiento
        self.actualizar_tabla_movimientos()

    def seleccionar_fila_movimiento(self, _evento=None):
        seleccion = self.tabla_movimientos.selection()

        if not seleccion:
            return

        posicion = self.mapa_items_movimientos.get(seleccion[0])

        if posicion is None:
            self.posicion_movimiento_seleccionado = None
            self.etiqueta_seleccion_movimiento.configure(
                text=(
                    "Este es un resumen. Abrí el grupo y seleccioná "
                    "un movimiento para modificarlo o eliminarlo."
                ),
                text_color=COLOR_TEXTO_SUAVE,
            )
            self.boton_modificar_movimiento.configure(state="disabled")
            self.boton_eliminar_movimiento.configure(state="disabled")
            return

        self.posicion_movimiento_seleccionado = posicion
        lineas = Movimientos.leer_datos(Movimientos.RUTA_MOVIMIENTOS)

        if not 0 <= posicion < len(lineas):
            self.actualizar_tabla_movimientos()
            return

        datos = Movimientos.separar_movimiento(lineas[posicion])

        if datos is None:
            self.actualizar_tabla_movimientos()
            return

        self.etiqueta_seleccion_movimiento.configure(
            text=(
                f"Seleccionado: {datos['fecha']} · "
                f"{tipo_movimiento_para_gui(datos['tipo'])} · "
                f"Gs. {Movimientos.formatear_monto(datos['monto'])}"
            ),
            text_color=COLOR_TEXTO,
        )
        self.boton_modificar_movimiento.configure(state="normal")
        self.boton_eliminar_movimiento.configure(state="normal")

    def manejar_doble_clic_movimiento(self, evento):
        item = self.tabla_movimientos.identify_row(evento.y)

        if item not in self.mapa_items_movimientos:
            return

        self.tabla_movimientos.selection_set(item)
        self.seleccionar_fila_movimiento()
        self.abrir_edicion_movimiento()

    def abrir_edicion_movimiento(self):
        posicion = self.posicion_movimiento_seleccionado

        if posicion is None:
            messagebox.showinfo(
                "Modificar movimiento",
                "Seleccioná primero un movimiento de la tabla.",
                parent=self,
            )
            return

        lineas = Movimientos.leer_datos(Movimientos.RUTA_MOVIMIENTOS)

        if not 0 <= posicion < len(lineas):
            messagebox.showerror(
                "Modificar movimiento",
                "El movimiento seleccionado ya no está disponible.",
                parent=self,
            )
            self.aplicar_filtros_movimientos()
            return

        datos = Movimientos.separar_movimiento(lineas[posicion])

        if datos is None:
            messagebox.showerror(
                "Modificar movimiento",
                "No se pudo leer el movimiento seleccionado.",
                parent=self,
            )
            return

        ventana = ctk.CTkToplevel(self)
        self.habilitar_navegacion_tab(ventana)
        ventana.title("Modificar movimiento")
        ventana.geometry("640x610")
        ventana.minsize(580, 560)
        ventana.configure(fg_color=COLOR_FONDO)
        ventana.transient(self)
        ventana.grab_set()
        ventana.grid_columnconfigure(0, weight=1)
        ventana.grid_rowconfigure(2, weight=1)
        self.ventana_edicion_movimiento = ventana
        self.datos_movimiento_edicion = datos

        ctk.CTkLabel(
            ventana,
            text="Modificar movimiento",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=26,
            pady=(24, 4),
        )

        ctk.CTkLabel(
            ventana,
            text="Los cambios reemplazarán solamente este registro.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=26,
            pady=(0, 14),
        )

        contenido = ctk.CTkScrollableFrame(
            ventana,
            fg_color=COLOR_PANEL,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        contenido.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=26,
            pady=(0, 14),
        )
        contenido.grid_columnconfigure(0, weight=1)
        contenido.grid_columnconfigure(1, weight=1)
        self.formulario_edicion_movimiento = contenido

        ctk.CTkLabel(
            contenido,
            text="Fecha",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=16,
            pady=(16, 5),
        )
        ctk.CTkLabel(
            contenido,
            text="Tipo",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=16,
            pady=(16, 5),
        )

        self.entrada_fecha_edicion = ctk.CTkEntry(
            contenido,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
        )
        self.entrada_fecha_edicion.insert(0, datos["fecha"])
        self.entrada_fecha_edicion.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=16,
            pady=(0, 12),
        )

        self.combo_tipo_edicion = ctk.CTkComboBox(
            contenido,
            values=TIPOS_MOVIMIENTO_GUI,
            command=self.actualizar_formulario_edicion_movimiento,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXTO,
            text_color=COLOR_TEXTO,
            state="readonly",
        )
        self.combo_tipo_edicion.set(
            tipo_movimiento_para_gui(datos["tipo"])
        )
        self.combo_tipo_edicion.grid(
            row=1,
            column=1,
            sticky="ew",
            padx=16,
            pady=(0, 12),
        )

        self.bloque_campos_edicion = ctk.CTkFrame(
            contenido,
            fg_color="transparent",
        )
        self.bloque_campos_edicion.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="nsew",
        )
        self.bloque_campos_edicion.grid_columnconfigure(0, weight=1)
        self.bloque_campos_edicion.grid_columnconfigure(1, weight=1)
        self.actualizar_formulario_edicion_movimiento(
            tipo_movimiento_para_gui(datos["tipo"]),
            conservar_datos=True,
        )

        acciones = ctk.CTkFrame(
            ventana,
            fg_color="transparent",
        )
        acciones.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=26,
            pady=(0, 22),
        )
        acciones.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            acciones,
            text="Cancelar",
            command=ventana.destroy,
            width=110,
            height=40,
            corner_radius=9,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, padx=(0, 8))

        ctk.CTkButton(
            acciones,
            text="Guardar cambios",
            command=lambda: self.guardar_edicion_movimiento(posicion),
            width=150,
            height=40,
            corner_radius=9,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=2)
        ventana.bind(
            "<Return>",
            lambda _evento: self.guardar_edicion_movimiento(posicion),
        )
        ventana.bind("<Escape>", lambda _evento: ventana.destroy())

    def crear_control_edicion(
        self,
        clave,
        titulo,
        fila,
        columna,
        valores=None,
        valor="",
    ):
        ctk.CTkLabel(
            self.bloque_campos_edicion,
            text=titulo,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=fila,
            column=columna,
            sticky="ew",
            padx=16,
            pady=(6, 5),
        )

        if valores is None:
            control = ctk.CTkEntry(
                self.bloque_campos_edicion,
                height=40,
                corner_radius=9,
                border_color=COLOR_BORDE,
                fg_color=COLOR_PANEL_SECUNDARIO,
                text_color=COLOR_TEXTO,
            )
            control.insert(0, valor)
        else:
            control = ctk.CTkComboBox(
                self.bloque_campos_edicion,
                values=valores,
                height=40,
                corner_radius=9,
                border_color=COLOR_BORDE,
                fg_color=COLOR_PANEL_SECUNDARIO,
                button_color=COLOR_PRIMARIO,
                button_hover_color=COLOR_PRIMARIO_HOVER,
                dropdown_fg_color=COLOR_PANEL,
                dropdown_text_color=COLOR_TEXTO,
                text_color=COLOR_TEXTO,
                state="readonly",
            )
            control.set(valor if valor in valores else valores[0])

        control.grid(
            row=fila + 1,
            column=columna,
            sticky="ew",
            padx=16,
            pady=(0, 10),
        )
        self.campos_edicion_movimiento[clave] = control
        return control

    def actualizar_formulario_edicion_movimiento(
        self,
        tipo,
        conservar_datos=False,
    ):
        for elemento in self.bloque_campos_edicion.winfo_children():
            elemento.destroy()

        self.campos_edicion_movimiento = {}
        datos = (
            self.datos_movimiento_edicion
            if conservar_datos
            else None
        )
        mismo_tipo = (
            datos is not None
            and Movimientos.normalizar_texto(datos["tipo"])
            == Movimientos.normalizar_texto(tipo)
        )
        origen = datos["origen"] if mismo_tipo else ""
        destino = datos["destino"] if mismo_tipo else ""
        monto_actual = (
            Movimientos.formatear_monto(datos["monto"])
            if mismo_tipo
            else ""
        )

        if tipo == "Ingreso":
            self.crear_control_edicion(
                "unidad",
                "Unidad",
                0,
                0,
                Movimientos.UNIDADES,
                destino,
            )

        elif tipo == "Egreso":
            self.crear_control_edicion(
                "unidad",
                "Unidad",
                0,
                0,
                Movimientos.UNIDADES,
                origen,
            )

        elif tipo == "Transferencia interna":
            self.crear_control_edicion(
                "origen",
                "Unidad de origen",
                0,
                0,
                Movimientos.UNIDADES,
                origen,
            )
            self.crear_control_edicion(
                "destino",
                "Unidad de destino",
                0,
                1,
                Movimientos.UNIDADES,
                destino,
            )

        elif tipo == "Depósito interno":
            origenes = Movimientos.UNIDADES + ["Otra persona"]
            origen_control = (
                origen if origen in Movimientos.UNIDADES else "Otra persona"
            )
            combo_origen = self.crear_control_edicion(
                "origen",
                "Origen del depósito",
                0,
                0,
                origenes,
                origen_control,
            )
            self.crear_control_edicion(
                "banco",
                "Banco de destino",
                0,
                1,
                valor=destino,
            )
            persona = self.crear_control_edicion(
                "persona",
                "Nombre de la persona",
                2,
                0,
                valor=(
                    origen
                    if origen not in Movimientos.UNIDADES
                    else ""
                ),
            )
            etiqueta_persona = persona.master.grid_slaves(
                row=2,
                column=0,
            )[0]

            def alternar_persona(valor):
                if valor == "Otra persona":
                    etiqueta_persona.grid()
                    persona.grid()
                else:
                    etiqueta_persona.grid_remove()
                    persona.grid_remove()

            combo_origen.configure(command=alternar_persona)
            alternar_persona(origen_control)

        elif tipo == "Cobro externo":
            self.crear_control_edicion(
                "banco",
                "Banco que recibió el cobro",
                0,
                0,
                valor=origen,
            )
            self.crear_control_edicion(
                "unidad",
                "Unidad",
                0,
                1,
                Movimientos.UNIDADES,
                destino,
            )

        self.crear_control_edicion(
            "monto",
            "Monto en guaraníes",
            4,
            0,
            valor=monto_actual,
        )

    def guardar_edicion_movimiento(self, posicion):
        campos = {
            clave: control.get()
            for clave, control in self.campos_edicion_movimiento.items()
        }

        try:
            linea_nueva, _ = construir_movimiento_grafico(
                self.combo_tipo_edicion.get(),
                self.entrada_fecha_edicion.get(),
                campos.get("monto", ""),
                campos,
            )
            lineas = Movimientos.leer_datos(
                Movimientos.RUTA_MOVIMIENTOS
            )

            if not 0 <= posicion < len(lineas):
                raise ValueError(
                    "El movimiento seleccionado ya no está disponible."
                )

            lineas[posicion] = linea_nueva
            Movimientos.guardar_datos(
                Movimientos.RUTA_MOVIMIENTOS,
                lineas,
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo modificar",
                str(error),
                parent=self.ventana_edicion_movimiento,
            )
            return

        self.ventana_edicion_movimiento.destroy()
        self.aplicar_filtros_movimientos()
        self.etiqueta_estado_movimientos.configure(
            text="Movimiento modificado correctamente.",
            text_color=COLOR_VERDE,
        )
        messagebox.showinfo(
            "Modificar movimiento",
            "El movimiento se modificó correctamente.",
            parent=self,
        )

    def eliminar_movimiento_grafico(self):
        posicion = self.posicion_movimiento_seleccionado

        if posicion is None:
            messagebox.showinfo(
                "Eliminar movimiento",
                "Seleccioná primero un movimiento de la tabla.",
                parent=self,
            )
            return

        lineas = Movimientos.leer_datos(Movimientos.RUTA_MOVIMIENTOS)

        if not 0 <= posicion < len(lineas):
            messagebox.showerror(
                "Eliminar movimiento",
                "El movimiento seleccionado ya no está disponible.",
                parent=self,
            )
            self.aplicar_filtros_movimientos()
            return

        datos = Movimientos.separar_movimiento(lineas[posicion])

        if datos is None:
            messagebox.showerror(
                "Eliminar movimiento",
                "No se pudo leer el movimiento seleccionado.",
                parent=self,
            )
            return

        confirmar = messagebox.askyesno(
            "Confirmar eliminación",
            (
                "¿Querés eliminar este movimiento?\n\n"
                f"{datos['fecha']} | "
                f"{tipo_movimiento_para_gui(datos['tipo'])}\n"
                f"{datos['origen']} → {datos['destino']}\n"
                f"Gs. {Movimientos.formatear_monto(datos['monto'])}"
            ),
            icon="warning",
            parent=self,
        )

        if not confirmar:
            return

        try:
            lineas.pop(posicion)
            Movimientos.guardar_datos(
                Movimientos.RUTA_MOVIMIENTOS,
                lineas,
            )
        except OSError as error:
            messagebox.showerror(
                "No se pudo eliminar",
                str(error),
                parent=self,
            )
            return

        self.aplicar_filtros_movimientos()
        self.etiqueta_estado_movimientos.configure(
            text="Movimiento eliminado correctamente.",
            text_color=COLOR_VERDE,
        )

    def mostrar_adicionales(self):
        self.limpiar_contenedor()
        self.marcar_seleccion("Movimientos")
        self.pagina_adicionales = 0
        self.posicion_adicional_seleccionado = None
        self.orden_tablas.pop("adicionales", None)

        pagina = ctk.CTkFrame(
            self.contenedor,
            fg_color="transparent",
            corner_radius=0,
        )
        pagina.grid(row=0, column=0, sticky="nsew")

        encabezado = self.crear_encabezado(
            pagina,
            "Ingresos y egresos adicionales",
            (
                "Registrá gastos fijos y otros conceptos que también "
                "forman parte del cierre mensual."
            ),
        )

        ctk.CTkButton(
            encabezado,
            text="Administrar conceptos",
            command=self.abrir_administrador_conceptos,
            width=165,
            height=38,
            corner_radius=10,
            fg_color=COLOR_NARANJA,
            hover_color="#C77B20",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, rowspan=2, padx=(20, 8))

        ctk.CTkButton(
            encabezado,
            text="Volver a Movimientos",
            command=lambda: self.mostrar_seccion("Movimientos"),
            width=165,
            height=38,
            corner_radius=10,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=2, rowspan=2)

        self.pestanas_adicionales = ctk.CTkTabview(
            pagina,
            fg_color=COLOR_PANEL,
            segmented_button_fg_color=COLOR_PANEL_SECUNDARIO,
            segmented_button_selected_color=COLOR_PRIMARIO,
            segmented_button_selected_hover_color=COLOR_PRIMARIO_HOVER,
            segmented_button_unselected_color=COLOR_PANEL_SECUNDARIO,
            segmented_button_unselected_hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        self.pestanas_adicionales.pack(
            fill="both",
            expand=True,
            padx=34,
            pady=(0, 26),
        )
        pestaña_registrar = self.pestanas_adicionales.add("Registrar")
        pestaña_gestionar = self.pestanas_adicionales.add(
            "Ver, modificar o eliminar"
        )

        self.construir_registro_adicional(pestaña_registrar)
        self.construir_gestion_adicionales(pestaña_gestionar)
        self.aplicar_filtros_adicionales()

    def construir_registro_adicional(self, master):
        master.grid_columnconfigure(0, weight=1)

        formulario = ctk.CTkFrame(
            master,
            fg_color="transparent",
        )
        formulario.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=18,
            pady=18,
        )
        formulario.grid_columnconfigure(0, weight=1)
        formulario.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            formulario,
            text="Nuevo registro adicional",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=(4, 16),
        )

        controles = [
            ("Fecha", 1, 0),
            ("Tipo", 1, 1),
            ("Concepto", 3, 0),
            ("Monto en guaraníes", 3, 1),
        ]
        for texto, fila, columna in controles:
            ctk.CTkLabel(
                formulario,
                text=texto,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            ).grid(
                row=fila,
                column=columna,
                sticky="ew",
                padx=8,
                pady=(0, 5),
            )

        self.entrada_fecha_adicional = ctk.CTkEntry(
            formulario,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="DD-MM-AAAA",
        )
        self.entrada_fecha_adicional.insert(
            0,
            datetime.now().strftime("%d-%m-%Y"),
        )
        self.entrada_fecha_adicional.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=8,
            pady=(0, 14),
        )

        self.combo_tipo_adicional = ctk.CTkComboBox(
            formulario,
            values=TIPOS_ADICIONAL_GUI,
            command=self.actualizar_conceptos_registro_adicional,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXTO,
            text_color=COLOR_TEXTO,
            state="readonly",
        )
        self.combo_tipo_adicional.set("Egreso")
        self.combo_tipo_adicional.grid(
            row=2,
            column=1,
            sticky="ew",
            padx=8,
            pady=(0, 14),
        )

        self.combo_concepto_adicional = ctk.CTkComboBox(
            formulario,
            values=["Otro concepto"],
            command=self.actualizar_campos_registro_adicional,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXTO,
            text_color=COLOR_TEXTO,
            state="readonly",
        )
        self.combo_concepto_adicional.grid(
            row=4,
            column=0,
            sticky="ew",
            padx=8,
            pady=(0, 14),
        )

        self.entrada_monto_adicional = ctk.CTkEntry(
            formulario,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="Ej.: 2500000",
        )
        self.entrada_monto_adicional.grid(
            row=4,
            column=1,
            sticky="ew",
            padx=8,
            pady=(0, 14),
        )

        self.etiqueta_otro_concepto = ctk.CTkLabel(
            formulario,
            text="Descripción del otro concepto",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        )
        self.etiqueta_otro_concepto.grid(
            row=5,
            column=0,
            sticky="ew",
            padx=8,
            pady=(0, 5),
        )

        self.entrada_otro_concepto = ctk.CTkEntry(
            formulario,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="Escribí la descripción",
        )
        self.entrada_otro_concepto.grid(
            row=6,
            column=0,
            sticky="ew",
            padx=8,
            pady=(0, 14),
        )

        self.etiqueta_observacion_adicional = ctk.CTkLabel(
            formulario,
            text="Observación de tarjeta de crédito",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        )
        self.etiqueta_observacion_adicional.grid(
            row=5,
            column=1,
            sticky="ew",
            padx=8,
            pady=(0, 5),
        )

        self.entrada_observacion_adicional = ctk.CTkEntry(
            formulario,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text=(
                "Ej.: Visa Oro 200.000 / Visa Clásica 2.234.343"
            ),
        )
        self.entrada_observacion_adicional.grid(
            row=6,
            column=1,
            sticky="ew",
            padx=8,
            pady=(0, 14),
        )

        ctk.CTkLabel(
            formulario,
            text=(
                "Los conceptos frecuentes se administran sin cambiar "
                "los movimientos que ya fueron guardados."
            ),
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=7,
            column=0,
            sticky="ew",
            padx=8,
            pady=(8, 0),
        )

        ctk.CTkButton(
            formulario,
            text="Guardar registro",
            command=self.guardar_adicional_grafico,
            width=160,
            height=42,
            corner_radius=9,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(
            row=7,
            column=1,
            sticky="e",
            padx=8,
            pady=(8, 0),
        )

        self.actualizar_conceptos_registro_adicional("Egreso")

    def actualizar_conceptos_registro_adicional(self, tipo=None):
        tipo = tipo or self.combo_tipo_adicional.get()
        catalogo = Movimientos.cargar_catalogo_conceptos()
        valores = list(catalogo.get(tipo, [])) + ["Otro concepto"]
        actual = self.combo_concepto_adicional.get()
        self.combo_concepto_adicional.configure(values=valores)
        self.combo_concepto_adicional.set(
            actual if actual in valores else valores[0]
        )
        self.actualizar_campos_registro_adicional(
            self.combo_concepto_adicional.get()
        )

    def actualizar_campos_registro_adicional(self, concepto=None):
        concepto = concepto or self.combo_concepto_adicional.get()

        if concepto == "Otro concepto":
            self.etiqueta_otro_concepto.grid()
            self.entrada_otro_concepto.grid()
        else:
            self.etiqueta_otro_concepto.grid_remove()
            self.entrada_otro_concepto.grid_remove()

        permite_observacion = concepto == "Pago de tarjeta de crédito"
        self.entrada_observacion_adicional.configure(
            state="normal" if permite_observacion else "disabled"
        )
        if not permite_observacion:
            self.entrada_observacion_adicional.configure(state="normal")
            self.entrada_observacion_adicional.delete(0, "end")
            self.entrada_observacion_adicional.configure(state="disabled")

    def guardar_adicional_grafico(self):
        concepto = self.combo_concepto_adicional.get()
        if concepto == "Otro concepto":
            concepto = self.entrada_otro_concepto.get()

        try:
            linea, datos = construir_adicional_grafico(
                self.combo_tipo_adicional.get(),
                self.entrada_fecha_adicional.get(),
                concepto,
                self.entrada_monto_adicional.get(),
                self.entrada_observacion_adicional.get(),
            )
            registros = Movimientos.leer_datos(
                Movimientos.RUTA_ADICIONALES
            )
            registros.append(linea)
            Movimientos.guardar_datos(
                Movimientos.RUTA_ADICIONALES,
                registros,
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo guardar",
                str(error),
                parent=self,
            )
            return

        self.entrada_monto_adicional.delete(0, "end")
        self.entrada_otro_concepto.delete(0, "end")
        self.entrada_observacion_adicional.configure(state="normal")
        self.entrada_observacion_adicional.delete(0, "end")
        self.actualizar_campos_registro_adicional(
            self.combo_concepto_adicional.get()
        )
        self.aplicar_filtros_adicionales()
        messagebox.showinfo(
            "Registro adicional",
            (
                f"{datos['tipo']} guardado correctamente.\n\n"
                f"{datos['fecha']} · {datos['descripcion']}\n"
                f"Gs. {Movimientos.formatear_monto(datos['monto'])}"
            ),
            parent=self,
        )

    def construir_gestion_adicionales(self, master):
        master.grid_rowconfigure(1, weight=1)
        master.grid_columnconfigure(0, weight=1)

        filtros = ctk.CTkFrame(
            master,
            fg_color="transparent",
        )
        filtros.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=16,
            pady=(14, 10),
        )
        for columna in range(5):
            filtros.grid_columnconfigure(
                columna,
                weight=1 if columna < 3 else 0,
            )

        fecha_desde, fecha_hasta = periodo_actual()
        for columna, (titulo, valor) in enumerate(
            [
                ("Desde", fecha_desde.strftime("%d-%m-%Y")),
                ("Hasta", fecha_hasta.strftime("%d-%m-%Y")),
            ]
        ):
            ctk.CTkLabel(
                filtros,
                text=titulo,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            ).grid(
                row=0,
                column=columna,
                sticky="ew",
                padx=6,
                pady=(0, 4),
            )
            entrada = ctk.CTkEntry(
                filtros,
                height=36,
                corner_radius=9,
                border_color=COLOR_BORDE,
                fg_color=COLOR_PANEL_SECUNDARIO,
                text_color=COLOR_TEXTO,
                placeholder_text="DD-MM-AAAA",
            )
            entrada.insert(0, valor)
            entrada.grid(
                row=1,
                column=columna,
                sticky="ew",
                padx=6,
            )
            if columna == 0:
                self.filtro_adicional_desde = entrada
            else:
                self.filtro_adicional_hasta = entrada

        ctk.CTkLabel(
            filtros,
            text="Tipo",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=0,
            column=2,
            sticky="ew",
            padx=6,
            pady=(0, 4),
        )
        self.filtro_tipo_adicional = ctk.CTkComboBox(
            filtros,
            values=["Todos"] + TIPOS_ADICIONAL_GUI,
            height=36,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXTO,
            text_color=COLOR_TEXTO,
            state="readonly",
        )
        self.filtro_tipo_adicional.set("Todos")
        self.filtro_tipo_adicional.grid(
            row=1,
            column=2,
            sticky="ew",
            padx=6,
        )

        ctk.CTkButton(
            filtros,
            text="Aplicar filtros",
            command=self.aplicar_filtros_adicionales,
            width=120,
            height=36,
            corner_radius=9,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=1, column=3, padx=6)

        ctk.CTkButton(
            filtros,
            text="Ver todos",
            command=self.mostrar_todos_adicionales,
            width=95,
            height=36,
            corner_radius=9,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=1, column=4, padx=6)

        bloque_tabla = ctk.CTkFrame(
            master,
            fg_color=COLOR_PANEL_SECUNDARIO,
            corner_radius=10,
        )
        bloque_tabla.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=22,
            pady=(0, 8),
        )
        bloque_tabla.grid_rowconfigure(1, weight=1)
        bloque_tabla.grid_columnconfigure(0, weight=1)

        cabecera = ctk.CTkFrame(
            bloque_tabla,
            fg_color="transparent",
        )
        cabecera.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=12,
            pady=(9, 5),
        )
        cabecera.grid_columnconfigure(0, weight=1)
        self.etiqueta_resultados_adicionales = ctk.CTkLabel(
            cabecera,
            text="Cargando registros...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        )
        self.etiqueta_resultados_adicionales.grid(
            row=0,
            column=0,
            sticky="ew",
        )
        self.etiqueta_estado_adicionales = ctk.CTkLabel(
            cabecera,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="e",
        )
        self.etiqueta_estado_adicionales.grid(
            row=0,
            column=1,
            padx=(10, 0),
        )

        estilo = ttk.Style(self)
        estilo.configure(
            "PXAdicional.Treeview",
            rowheight=32,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        estilo.configure(
            "PXAdicional.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
        )
        estilo.map(
            "PXAdicional.Treeview",
            background=[("selected", COLOR_PRIMARIO)],
            foreground=[("selected", "#FFFFFF")],
        )

        columnas = (
            "fecha",
            "tipo",
            "concepto",
            "monto",
            "observacion",
        )
        self.tabla_adicionales = ttk.Treeview(
            bloque_tabla,
            columns=columnas,
            show="headings",
            selectmode="browse",
            style="PXAdicional.Treeview",
        )
        configuracion = {
            "fecha": ("Fecha", 95, "center"),
            "tipo": ("Tipo", 80, "center"),
            "concepto": ("Concepto", 220, "w"),
            "monto": ("Monto", 130, "e"),
            "observacion": ("Observación", 240, "w"),
        }
        for columna, (titulo, ancho, ancla) in configuracion.items():
            self.tabla_adicionales.heading(columna, text=titulo)
            self.tabla_adicionales.column(
                columna,
                width=ancho,
                minwidth=70,
                anchor=ancla,
                stretch=True,
            )
        self._bind_orden_columnas(
            tabla=self.tabla_adicionales,
            clave="adicionales",
            titulos={
                "fecha": "Fecha",
                "tipo": "Tipo",
                "concepto": "Concepto",
                "monto": "Monto",
                "observacion": "Observación",
            },
            tipos={
                "fecha": "fecha",
                "tipo": "texto",
                "concepto": "texto",
                "monto": "monto",
                "observacion": "texto",
            },
            campos={"concepto": "descripcion"},
            atributo_lista="adicionales_filtrados",
            callback_actualizar=self._actualizar_tras_orden_adicionales,
        )

        barra = ttk.Scrollbar(
            bloque_tabla,
            orient="vertical",
            command=self.tabla_adicionales.yview,
        )
        self.tabla_adicionales.configure(yscrollcommand=barra.set)
        self.tabla_adicionales.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(12, 0),
        )
        barra.grid(
            row=1,
            column=1,
            sticky="ns",
            padx=(0, 8),
        )
        self.tabla_adicionales.bind(
            "<<TreeviewSelect>>",
            self.seleccionar_fila_adicional,
        )
        self.tabla_adicionales.bind(
            "<Double-1>",
            lambda _evento: self.abrir_edicion_adicional(),
        )

        pie = ctk.CTkFrame(
            bloque_tabla,
            fg_color="transparent",
        )
        pie.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=12,
            pady=8,
        )
        pie.grid_columnconfigure(1, weight=1)
        self.boton_anterior_adicional = ctk.CTkButton(
            pie,
            text="Anterior",
            command=lambda: self.cambiar_pagina_adicionales(-1),
            width=82,
            height=30,
            corner_radius=8,
            fg_color=COLOR_PANEL,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        self.boton_anterior_adicional.grid(row=0, column=0)
        self.etiqueta_pagina_adicionales = ctk.CTkLabel(
            pie,
            text="Página 1 de 1",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.etiqueta_pagina_adicionales.grid(
            row=0,
            column=1,
            sticky="ew",
        )
        self.boton_siguiente_adicional = ctk.CTkButton(
            pie,
            text="Siguiente",
            command=lambda: self.cambiar_pagina_adicionales(1),
            width=82,
            height=30,
            corner_radius=8,
            fg_color=COLOR_PANEL,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        self.boton_siguiente_adicional.grid(row=0, column=2)

        acciones = ctk.CTkFrame(
            master,
            fg_color="transparent",
        )
        acciones.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=22,
            pady=(0, 12),
        )
        acciones.grid_columnconfigure(0, weight=1)
        self.etiqueta_seleccion_adicional = ctk.CTkLabel(
            acciones,
            text="Seleccioná un registro de la tabla.",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        )
        self.etiqueta_seleccion_adicional.grid(
            row=0,
            column=0,
            sticky="ew",
        )
        self.boton_modificar_adicional = ctk.CTkButton(
            acciones,
            text="Modificar seleccionado",
            command=self.abrir_edicion_adicional,
            width=165,
            height=36,
            corner_radius=9,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"),
            state="disabled",
        )
        self.boton_modificar_adicional.grid(
            row=0,
            column=1,
            padx=(8, 6),
        )
        self.boton_eliminar_adicional = ctk.CTkButton(
            acciones,
            text="Eliminar seleccionado",
            command=self.eliminar_adicional_grafico,
            width=155,
            height=36,
            corner_radius=9,
            fg_color=COLOR_ROJO,
            hover_color="#BE3F3F",
            font=ctk.CTkFont(size=11, weight="bold"),
            state="disabled",
        )
        self.boton_eliminar_adicional.grid(row=0, column=2)

    def _actualizar_tras_orden_adicionales(self):
        self.pagina_adicionales = 0
        self.actualizar_tabla_adicionales()

    def aplicar_filtros_adicionales(self):
        try:
            lineas = Movimientos.leer_datos(
                Movimientos.RUTA_ADICIONALES
            )
            self.adicionales_filtrados = filtrar_adicionales_graficos(
                lineas,
                self.filtro_adicional_desde.get(),
                self.filtro_adicional_hasta.get(),
                self.filtro_tipo_adicional.get(),
            )
        except (ValueError, OSError) as error:
            self.etiqueta_estado_adicionales.configure(
                text=str(error),
                text_color=COLOR_ROJO,
            )
            return

        self.pagina_adicionales = 0
        self.etiqueta_estado_adicionales.configure(
            text="Filtros aplicados.",
            text_color=COLOR_VERDE,
        )
        self._reaplicar_orden_tabla("adicionales")
        self.actualizar_tabla_adicionales()

    def mostrar_todos_adicionales(self):
        self.filtro_adicional_desde.delete(0, "end")
        self.filtro_adicional_hasta.delete(0, "end")
        self.filtro_tipo_adicional.set("Todos")
        self.aplicar_filtros_adicionales()

    def actualizar_tabla_adicionales(self):
        for item in self.tabla_adicionales.get_children():
            self.tabla_adicionales.delete(item)

        cantidad = len(self.adicionales_filtrados)
        total_paginas = max(
            1,
            (cantidad + ADICIONALES_POR_PAGINA - 1)
            // ADICIONALES_POR_PAGINA,
        )
        self.pagina_adicionales = min(
            max(self.pagina_adicionales, 0),
            total_paginas - 1,
        )
        inicio = self.pagina_adicionales * ADICIONALES_POR_PAGINA
        fin = inicio + ADICIONALES_POR_PAGINA

        for posicion, datos in self.adicionales_filtrados[inicio:fin]:
            self.tabla_adicionales.insert(
                "",
                "end",
                iid=str(posicion),
                values=(
                    datos["fecha"],
                    datos["tipo"],
                    datos["descripcion"],
                    "Gs. " + Movimientos.formatear_monto(
                        datos["monto"]
                    ),
                    datos["observacion"] or "—",
                ),
            )

        self.etiqueta_resultados_adicionales.configure(
            text=(
                f"{cantidad} registro"
                if cantidad == 1
                else f"{cantidad} registros"
            )
        )
        self.etiqueta_pagina_adicionales.configure(
            text=(
                f"Página {self.pagina_adicionales + 1} "
                f"de {total_paginas}"
            )
        )
        self.boton_anterior_adicional.configure(
            state=(
                "normal"
                if self.pagina_adicionales > 0
                else "disabled"
            )
        )
        self.boton_siguiente_adicional.configure(
            state=(
                "normal"
                if self.pagina_adicionales < total_paginas - 1
                else "disabled"
            )
        )
        self.posicion_adicional_seleccionado = None
        self.etiqueta_seleccion_adicional.configure(
            text=(
                "No hay registros para mostrar."
                if cantidad == 0
                else "Seleccioná un registro de la tabla."
            ),
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.boton_modificar_adicional.configure(state="disabled")
        self.boton_eliminar_adicional.configure(state="disabled")

    def cambiar_pagina_adicionales(self, desplazamiento):
        self.pagina_adicionales += desplazamiento
        self.actualizar_tabla_adicionales()

    def seleccionar_fila_adicional(self, _evento=None):
        seleccion = self.tabla_adicionales.selection()
        if not seleccion:
            return

        posicion = int(seleccion[0])
        lineas = Movimientos.leer_datos(Movimientos.RUTA_ADICIONALES)
        if not 0 <= posicion < len(lineas):
            self.aplicar_filtros_adicionales()
            return

        datos = Movimientos.separar_adicional(lineas[posicion])
        if datos is None:
            self.aplicar_filtros_adicionales()
            return

        self.posicion_adicional_seleccionado = posicion
        self.etiqueta_seleccion_adicional.configure(
            text=(
                f"Seleccionado: {datos['fecha']} · "
                f"{datos['tipo']} · {datos['descripcion']} · "
                f"Gs. {Movimientos.formatear_monto(datos['monto'])}"
            ),
            text_color=COLOR_TEXTO,
        )
        self.boton_modificar_adicional.configure(state="normal")
        self.boton_eliminar_adicional.configure(state="normal")

    def abrir_edicion_adicional(self):
        posicion = self.posicion_adicional_seleccionado
        if posicion is None:
            messagebox.showinfo(
                "Modificar registro",
                "Seleccioná primero un registro de la tabla.",
                parent=self,
            )
            return

        lineas = Movimientos.leer_datos(Movimientos.RUTA_ADICIONALES)
        if not 0 <= posicion < len(lineas):
            messagebox.showerror(
                "Modificar registro",
                "El registro seleccionado ya no está disponible.",
                parent=self,
            )
            self.aplicar_filtros_adicionales()
            return

        datos = Movimientos.separar_adicional(lineas[posicion])
        if datos is None:
            messagebox.showerror(
                "Modificar registro",
                "No se pudo leer el registro seleccionado.",
                parent=self,
            )
            return

        ventana = ctk.CTkToplevel(self)
        self.habilitar_navegacion_tab(ventana)
        ventana.title("Modificar ingreso o egreso adicional")
        ventana.geometry("620x560")
        ventana.minsize(560, 520)
        ventana.configure(fg_color=COLOR_FONDO)
        ventana.transient(self)
        ventana.grab_set()
        ventana.grid_columnconfigure(0, weight=1)
        self.ventana_edicion_adicional = ventana
        self.datos_adicional_edicion = datos

        ctk.CTkLabel(
            ventana,
            text="Modificar registro adicional",
            font=ctk.CTkFont(size=23, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=26,
            pady=(24, 4),
        )
        ctk.CTkLabel(
            ventana,
            text="Los cambios reemplazarán solamente este registro.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=26,
            pady=(0, 14),
        )

        contenido = ctk.CTkFrame(
            ventana,
            fg_color=COLOR_PANEL,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        contenido.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=26,
            pady=(0, 14),
        )
        contenido.grid_columnconfigure(0, weight=1)
        contenido.grid_columnconfigure(1, weight=1)

        for texto, fila, columna in [
            ("Fecha", 0, 0),
            ("Tipo", 0, 1),
            ("Concepto", 2, 0),
            ("Monto", 2, 1),
            ("Otro concepto", 4, 0),
            ("Observación de tarjeta", 4, 1),
        ]:
            ctk.CTkLabel(
                contenido,
                text=texto,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            ).grid(
                row=fila,
                column=columna,
                sticky="ew",
                padx=14,
                pady=(14 if fila == 0 else 4, 5),
            )

        self.entrada_fecha_edicion_adicional = ctk.CTkEntry(
            contenido,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
        )
        self.entrada_fecha_edicion_adicional.insert(0, datos["fecha"])
        self.entrada_fecha_edicion_adicional.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=14,
        )

        self.combo_tipo_edicion_adicional = ctk.CTkComboBox(
            contenido,
            values=TIPOS_ADICIONAL_GUI,
            command=self.actualizar_conceptos_edicion_adicional,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXTO,
            text_color=COLOR_TEXTO,
            state="readonly",
        )
        self.combo_tipo_edicion_adicional.set(datos["tipo"])
        self.combo_tipo_edicion_adicional.grid(
            row=1,
            column=1,
            sticky="ew",
            padx=14,
        )

        self.combo_concepto_edicion_adicional = ctk.CTkComboBox(
            contenido,
            values=["Otro concepto"],
            command=self.actualizar_campos_edicion_adicional,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXTO,
            text_color=COLOR_TEXTO,
            state="readonly",
        )
        self.combo_concepto_edicion_adicional.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=14,
        )

        self.entrada_monto_edicion_adicional = ctk.CTkEntry(
            contenido,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
        )
        self.entrada_monto_edicion_adicional.insert(
            0,
            Movimientos.formatear_monto(datos["monto"]),
        )
        self.entrada_monto_edicion_adicional.grid(
            row=3,
            column=1,
            sticky="ew",
            padx=14,
        )

        self.entrada_otro_edicion_adicional = ctk.CTkEntry(
            contenido,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
        )
        self.entrada_otro_edicion_adicional.grid(
            row=5,
            column=0,
            sticky="ew",
            padx=14,
            pady=(0, 16),
        )

        self.entrada_observacion_edicion_adicional = ctk.CTkEntry(
            contenido,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
        )
        self.entrada_observacion_edicion_adicional.insert(
            0,
            datos["observacion"],
        )
        self.entrada_observacion_edicion_adicional.grid(
            row=5,
            column=1,
            sticky="ew",
            padx=14,
            pady=(0, 16),
        )

        acciones = ctk.CTkFrame(
            ventana,
            fg_color="transparent",
        )
        acciones.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=26,
            pady=(0, 22),
        )
        acciones.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            acciones,
            text="Cancelar",
            command=ventana.destroy,
            width=105,
            height=40,
            corner_radius=9,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(
            acciones,
            text="Guardar cambios",
            command=lambda: self.guardar_edicion_adicional(posicion),
            width=145,
            height=40,
            corner_radius=9,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=2)

        self.actualizar_conceptos_edicion_adicional(
            datos["tipo"],
            conservar_actual=True,
        )

    def actualizar_conceptos_edicion_adicional(
        self,
        tipo,
        conservar_actual=False,
    ):
        catalogo = Movimientos.cargar_catalogo_conceptos()
        valores = list(catalogo.get(tipo, [])) + ["Otro concepto"]
        actual = (
            self.datos_adicional_edicion["descripcion"]
            if conservar_actual
            else ""
        )
        self.combo_concepto_edicion_adicional.configure(values=valores)
        self.entrada_otro_edicion_adicional.configure(state="normal")
        if actual in valores:
            self.combo_concepto_edicion_adicional.set(actual)
            self.entrada_otro_edicion_adicional.delete(0, "end")
        else:
            self.combo_concepto_edicion_adicional.set("Otro concepto")
            self.entrada_otro_edicion_adicional.delete(0, "end")
            self.entrada_otro_edicion_adicional.insert(0, actual)
        self.actualizar_campos_edicion_adicional(
            self.combo_concepto_edicion_adicional.get()
        )

    def actualizar_campos_edicion_adicional(self, concepto):
        estado_otro = "normal" if concepto == "Otro concepto" else "disabled"
        self.entrada_otro_edicion_adicional.configure(state=estado_otro)
        permite_observacion = concepto == "Pago de tarjeta de crédito"
        self.entrada_observacion_edicion_adicional.configure(
            state="normal" if permite_observacion else "disabled"
        )
        if not permite_observacion:
            self.entrada_observacion_edicion_adicional.configure(
                state="normal"
            )
            self.entrada_observacion_edicion_adicional.delete(0, "end")
            self.entrada_observacion_edicion_adicional.configure(
                state="disabled"
            )

    def guardar_edicion_adicional(self, posicion):
        concepto = self.combo_concepto_edicion_adicional.get()
        if concepto == "Otro concepto":
            concepto = self.entrada_otro_edicion_adicional.get()

        try:
            linea_nueva, _ = construir_adicional_grafico(
                self.combo_tipo_edicion_adicional.get(),
                self.entrada_fecha_edicion_adicional.get(),
                concepto,
                self.entrada_monto_edicion_adicional.get(),
                self.entrada_observacion_edicion_adicional.get(),
            )
            lineas = Movimientos.leer_datos(
                Movimientos.RUTA_ADICIONALES
            )
            if not 0 <= posicion < len(lineas):
                raise ValueError(
                    "El registro seleccionado ya no está disponible."
                )
            lineas[posicion] = linea_nueva
            Movimientos.guardar_datos(
                Movimientos.RUTA_ADICIONALES,
                lineas,
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo modificar",
                str(error),
                parent=self.ventana_edicion_adicional,
            )
            return

        self.ventana_edicion_adicional.destroy()
        self.aplicar_filtros_adicionales()
        self.etiqueta_estado_adicionales.configure(
            text="Registro modificado correctamente.",
            text_color=COLOR_VERDE,
        )
        messagebox.showinfo(
            "Modificar registro",
            "El registro se modificó correctamente.",
            parent=self,
        )

    def eliminar_adicional_grafico(self):
        posicion = self.posicion_adicional_seleccionado
        if posicion is None:
            messagebox.showinfo(
                "Eliminar registro",
                "Seleccioná primero un registro de la tabla.",
                parent=self,
            )
            return

        lineas = Movimientos.leer_datos(Movimientos.RUTA_ADICIONALES)
        if not 0 <= posicion < len(lineas):
            messagebox.showerror(
                "Eliminar registro",
                "El registro seleccionado ya no está disponible.",
                parent=self,
            )
            self.aplicar_filtros_adicionales()
            return

        datos = Movimientos.separar_adicional(lineas[posicion])
        if datos is None:
            messagebox.showerror(
                "Eliminar registro",
                "No se pudo leer el registro seleccionado.",
                parent=self,
            )
            return

        confirmar = messagebox.askyesno(
            "Confirmar eliminación",
            (
                "¿Querés eliminar este registro?\n\n"
                f"{datos['fecha']} | {datos['tipo']}\n"
                f"{datos['descripcion']}\n"
                f"Gs. {Movimientos.formatear_monto(datos['monto'])}"
            ),
            icon="warning",
            parent=self,
        )
        if not confirmar:
            return

        try:
            lineas.pop(posicion)
            Movimientos.guardar_datos(
                Movimientos.RUTA_ADICIONALES,
                lineas,
            )
        except OSError as error:
            messagebox.showerror(
                "No se pudo eliminar",
                str(error),
                parent=self,
            )
            return

        self.aplicar_filtros_adicionales()
        self.etiqueta_estado_adicionales.configure(
            text="Registro eliminado correctamente.",
            text_color=COLOR_VERDE,
        )

    def abrir_administrador_conceptos(self):
        ventana = ctk.CTkToplevel(self)
        self.habilitar_navegacion_tab(ventana)
        ventana.title("Administrar conceptos adicionales")
        ventana.geometry("680x560")
        ventana.minsize(600, 510)
        ventana.configure(fg_color=COLOR_FONDO)
        ventana.transient(self)
        ventana.grab_set()
        ventana.grid_columnconfigure(0, weight=1)
        ventana.grid_rowconfigure(2, weight=1)
        self.ventana_conceptos = ventana

        ctk.CTkLabel(
            ventana,
            text="Administrar conceptos",
            font=ctk.CTkFont(size=23, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=26,
            pady=(24, 4),
        )
        ctk.CTkLabel(
            ventana,
            text=(
                "Los cambios afectan la lista futura; los registros "
                "anteriores conservan el concepto que tenían."
            ),
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=26,
            pady=(0, 14),
        )

        cuerpo = ctk.CTkFrame(
            ventana,
            fg_color=COLOR_PANEL,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        cuerpo.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=26,
            pady=(0, 14),
        )
        cuerpo.grid_rowconfigure(2, weight=1)
        cuerpo.grid_columnconfigure(0, weight=1)

        selector = ctk.CTkFrame(cuerpo, fg_color="transparent")
        selector.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=16,
            pady=(16, 8),
        )
        selector.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            selector,
            text="Lista:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
        ).grid(row=0, column=0, padx=(0, 10))
        self.combo_tipo_catalogo = ctk.CTkComboBox(
            selector,
            values=TIPOS_ADICIONAL_GUI,
            command=self.actualizar_lista_conceptos,
            height=38,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXTO,
            text_color=COLOR_TEXTO,
            state="readonly",
        )
        self.combo_tipo_catalogo.set("Ingreso")
        self.combo_tipo_catalogo.grid(
            row=0,
            column=1,
            sticky="ew",
        )

        self.tabla_conceptos = ttk.Treeview(
            cuerpo,
            columns=("concepto",),
            show="headings",
            selectmode="browse",
            style="PXAdicional.Treeview",
        )
        self.tabla_conceptos.heading("concepto", text="Concepto")
        self.tabla_conceptos.column(
            "concepto",
            anchor="w",
            width=520,
        )
        self.tabla_conceptos.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=16,
            pady=(0, 10),
        )
        self.tabla_conceptos.bind(
            "<<TreeviewSelect>>",
            self.seleccionar_concepto_catalogo,
        )

        editor = ctk.CTkFrame(cuerpo, fg_color="transparent")
        editor.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=16,
            pady=(0, 16),
        )
        editor.grid_columnconfigure(0, weight=1)
        self.entrada_nombre_concepto = ctk.CTkEntry(
            editor,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="Nombre del concepto",
        )
        self.entrada_nombre_concepto.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 8),
        )
        ctk.CTkButton(
            editor,
            text="Agregar",
            command=self.agregar_concepto_grafico,
            width=80,
            height=40,
            corner_radius=9,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=1, padx=4)
        ctk.CTkButton(
            editor,
            text="Modificar",
            command=self.modificar_concepto_grafico,
            width=85,
            height=40,
            corner_radius=9,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=2, padx=4)
        ctk.CTkButton(
            editor,
            text="Eliminar",
            command=self.eliminar_concepto_grafico,
            width=80,
            height=40,
            corner_radius=9,
            fg_color=COLOR_ROJO,
            hover_color="#BE3F3F",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=3, padx=(4, 0))

        ctk.CTkButton(
            ventana,
            text="Cerrar",
            command=ventana.destroy,
            width=105,
            height=40,
            corner_radius=9,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(
            row=3,
            column=0,
            sticky="e",
            padx=26,
            pady=(0, 22),
        )
        self.actualizar_lista_conceptos("Ingreso")

    def actualizar_lista_conceptos(self, tipo=None):
        tipo = tipo or self.combo_tipo_catalogo.get()
        self.tipo_catalogo_actual = tipo
        for item in self.tabla_conceptos.get_children():
            self.tabla_conceptos.delete(item)

        catalogo = Movimientos.cargar_catalogo_conceptos()
        for indice, concepto in enumerate(catalogo[tipo]):
            self.tabla_conceptos.insert(
                "",
                "end",
                iid=str(indice),
                values=(concepto,),
            )
        self.entrada_nombre_concepto.delete(0, "end")

    def seleccionar_concepto_catalogo(self, _evento=None):
        seleccion = self.tabla_conceptos.selection()
        if not seleccion:
            return
        valores = self.tabla_conceptos.item(seleccion[0], "values")
        if not valores:
            return
        self.entrada_nombre_concepto.delete(0, "end")
        self.entrada_nombre_concepto.insert(0, valores[0])

    def agregar_concepto_grafico(self):
        tipo = self.combo_tipo_catalogo.get()
        try:
            concepto = validar_texto_campo(
                self.entrada_nombre_concepto.get(),
                "Concepto",
            )
            catalogo = Movimientos.cargar_catalogo_conceptos()
            if Movimientos.concepto_ya_existe(
                catalogo[tipo],
                concepto,
            ):
                raise ValueError("Ese concepto ya existe.")
            catalogo[tipo].append(concepto)
            Movimientos.guardar_catalogo_conceptos(catalogo)
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo agregar",
                str(error),
                parent=self.ventana_conceptos,
            )
            return
        self.actualizar_lista_conceptos(tipo)
        self.actualizar_conceptos_registro_adicional(
            self.combo_tipo_adicional.get()
        )

    def modificar_concepto_grafico(self):
        seleccion = self.tabla_conceptos.selection()
        if not seleccion:
            messagebox.showinfo(
                "Modificar concepto",
                "Seleccioná primero un concepto.",
                parent=self.ventana_conceptos,
            )
            return
        tipo = self.combo_tipo_catalogo.get()
        indice = int(seleccion[0])
        try:
            concepto = validar_texto_campo(
                self.entrada_nombre_concepto.get(),
                "Concepto",
            )
            catalogo = Movimientos.cargar_catalogo_conceptos()
            if not 0 <= indice < len(catalogo[tipo]):
                raise ValueError(
                    "El concepto seleccionado ya no está disponible."
                )
            if Movimientos.concepto_ya_existe(
                catalogo[tipo],
                concepto,
                ignorar_indice=indice,
            ):
                raise ValueError("Ese concepto ya existe.")
            catalogo[tipo][indice] = concepto
            Movimientos.guardar_catalogo_conceptos(catalogo)
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo modificar",
                str(error),
                parent=self.ventana_conceptos,
            )
            return
        self.actualizar_lista_conceptos(tipo)
        self.actualizar_conceptos_registro_adicional(
            self.combo_tipo_adicional.get()
        )
        messagebox.showinfo(
            "Concepto modificado",
            (
                "La lista se actualizó. Los registros anteriores "
                "conservan el nombre que tenían."
            ),
            parent=self.ventana_conceptos,
        )

    def eliminar_concepto_grafico(self):
        seleccion = self.tabla_conceptos.selection()
        if not seleccion:
            messagebox.showinfo(
                "Eliminar concepto",
                "Seleccioná primero un concepto.",
                parent=self.ventana_conceptos,
            )
            return
        tipo = self.combo_tipo_catalogo.get()
        indice = int(seleccion[0])
        catalogo = Movimientos.cargar_catalogo_conceptos()
        if not 0 <= indice < len(catalogo[tipo]):
            self.actualizar_lista_conceptos(tipo)
            return
        concepto = catalogo[tipo][indice]
        confirmar = messagebox.askyesno(
            "Confirmar eliminación",
            (
                f"¿Querés quitar “{concepto}” de la lista?\n\n"
                "Los registros anteriores no se eliminarán ni "
                "se modificarán."
            ),
            icon="warning",
            parent=self.ventana_conceptos,
        )
        if not confirmar:
            return
        try:
            catalogo[tipo].pop(indice)
            Movimientos.guardar_catalogo_conceptos(catalogo)
        except OSError as error:
            messagebox.showerror(
                "No se pudo eliminar",
                str(error),
                parent=self.ventana_conceptos,
            )
            return
        self.actualizar_lista_conceptos(tipo)
        self.actualizar_conceptos_registro_adicional(
            self.combo_tipo_adicional.get()
        )

    def mostrar_inversiones(self):
        self.limpiar_contenedor()
        self.marcar_seleccion("Movimientos")
        self.pagina_inversiones = 0
        self.posicion_inversion_seleccionada = None
        self.orden_tablas.pop("inversiones", None)

        pagina = ctk.CTkFrame(
            self.contenedor,
            fg_color="transparent",
            corner_radius=0,
        )
        pagina.grid(row=0, column=0, sticky="nsew")

        encabezado = self.crear_encabezado(
            pagina,
            "Inversiones",
            (
                "Registrá y controlá las inversiones sin afectar los "
                "ingresos, egresos ni la utilidad del mes."
            ),
        )
        ctk.CTkButton(
            encabezado,
            text="Volver a Movimientos",
            command=lambda: self.mostrar_seccion("Movimientos"),
            width=165,
            height=38,
            corner_radius=10,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, rowspan=2, padx=(20, 0))

        self.pestanas_inversiones = ctk.CTkTabview(
            pagina,
            fg_color=COLOR_PANEL,
            segmented_button_fg_color=COLOR_PANEL_SECUNDARIO,
            segmented_button_selected_color=COLOR_PRIMARIO,
            segmented_button_selected_hover_color=COLOR_PRIMARIO_HOVER,
            segmented_button_unselected_color=COLOR_PANEL_SECUNDARIO,
            segmented_button_unselected_hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        self.pestanas_inversiones.pack(
            fill="both",
            expand=True,
            padx=34,
            pady=(0, 26),
        )
        pestaña_registrar = self.pestanas_inversiones.add("Registrar")
        pestaña_gestionar = self.pestanas_inversiones.add(
            "Ver, modificar o eliminar"
        )

        self.construir_registro_inversion(pestaña_registrar)
        self.construir_gestion_inversiones(pestaña_gestionar)
        self.aplicar_filtros_inversiones()

    def construir_registro_inversion(self, master):
        master.grid_columnconfigure(0, weight=1)

        formulario = ctk.CTkFrame(master, fg_color="transparent")
        formulario.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=18,
            pady=18,
        )
        formulario.grid_columnconfigure(0, weight=1)
        formulario.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            formulario,
            text="Nueva inversión",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=(4, 16),
        )

        for texto, fila, columna in [
            ("Fecha", 1, 0),
            ("Monto en guaraníes", 1, 1),
            ("Descripción", 3, 0),
        ]:
            ctk.CTkLabel(
                formulario,
                text=texto,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            ).grid(
                row=fila,
                column=columna,
                columnspan=2 if texto == "Descripción" else 1,
                sticky="ew",
                padx=8,
                pady=(0, 5),
            )

        self.entrada_fecha_inversion = ctk.CTkEntry(
            formulario,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="DD-MM-AAAA",
        )
        self.entrada_fecha_inversion.insert(
            0,
            datetime.now().strftime("%d-%m-%Y"),
        )
        self.entrada_fecha_inversion.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=8,
            pady=(0, 14),
        )

        self.entrada_monto_inversion = ctk.CTkEntry(
            formulario,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="Ej.: 100000000",
        )
        self.entrada_monto_inversion.grid(
            row=2,
            column=1,
            sticky="ew",
            padx=8,
            pady=(0, 14),
        )

        self.entrada_descripcion_inversion = ctk.CTkEntry(
            formulario,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="Ej.: CDA, compra de equipo o mercadería",
        )
        self.entrada_descripcion_inversion.grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=(0, 16),
        )

        aviso = ctk.CTkFrame(
            formulario,
            fg_color=("#EAF1FF", "#142746"),
            corner_radius=10,
        )
        aviso.grid(
            row=5,
            column=0,
            sticky="ew",
            padx=8,
            pady=(8, 0),
        )
        ctk.CTkLabel(
            aviso,
            text=(
                "La inversión queda registrada para control, pero no "
                "suma como ingreso ni resta como egreso."
            ),
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO,
            anchor="w",
            justify="left",
            wraplength=560,
        ).pack(fill="x", padx=14, pady=12)

        ctk.CTkButton(
            formulario,
            text="Guardar inversión",
            command=self.guardar_inversion_grafica,
            width=160,
            height=42,
            corner_radius=9,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(
            row=5,
            column=1,
            sticky="e",
            padx=8,
            pady=(8, 0),
        )

    def guardar_inversion_grafica(self):
        try:
            linea, datos = construir_inversion_grafica(
                self.entrada_fecha_inversion.get(),
                self.entrada_descripcion_inversion.get(),
                self.entrada_monto_inversion.get(),
            )
            registros = Movimientos.leer_datos(
                Movimientos.RUTA_INVERSIONES
            )
            registros.append(linea)
            Movimientos.guardar_datos(
                Movimientos.RUTA_INVERSIONES,
                registros,
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo guardar",
                str(error),
                parent=self,
            )
            return

        self.entrada_descripcion_inversion.delete(0, "end")
        self.entrada_monto_inversion.delete(0, "end")
        self.aplicar_filtros_inversiones()
        messagebox.showinfo(
            "Inversión registrada",
            (
                "La inversión se guardó correctamente.\n\n"
                f"{datos['fecha']} · {datos['descripcion']}\n"
                f"Gs. {Movimientos.formatear_monto(datos['monto'])}"
            ),
            parent=self,
        )

    def construir_gestion_inversiones(self, master):
        master.grid_rowconfigure(1, weight=1)
        master.grid_columnconfigure(0, weight=1)

        filtros = ctk.CTkFrame(master, fg_color="transparent")
        filtros.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=16,
            pady=(14, 10),
        )
        for columna in range(5):
            filtros.grid_columnconfigure(
                columna,
                weight=1 if columna < 3 else 0,
            )

        fecha_desde, fecha_hasta = periodo_actual()
        for columna, (titulo, valor) in enumerate(
            [
                ("Desde", fecha_desde.strftime("%d-%m-%Y")),
                ("Hasta", fecha_hasta.strftime("%d-%m-%Y")),
            ]
        ):
            ctk.CTkLabel(
                filtros,
                text=titulo,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            ).grid(
                row=0,
                column=columna,
                sticky="ew",
                padx=6,
                pady=(0, 4),
            )
            entrada = ctk.CTkEntry(
                filtros,
                height=36,
                corner_radius=9,
                border_color=COLOR_BORDE,
                fg_color=COLOR_PANEL_SECUNDARIO,
                text_color=COLOR_TEXTO,
                placeholder_text="DD-MM-AAAA",
            )
            entrada.insert(0, valor)
            entrada.grid(
                row=1,
                column=columna,
                sticky="ew",
                padx=6,
            )
            if columna == 0:
                self.filtro_inversion_desde = entrada
            else:
                self.filtro_inversion_hasta = entrada

        ctk.CTkLabel(
            filtros,
            text="Buscar descripción",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=0,
            column=2,
            sticky="ew",
            padx=6,
            pady=(0, 4),
        )
        self.filtro_descripcion_inversion = ctk.CTkEntry(
            filtros,
            height=36,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="Ej.: CDA",
        )
        self.filtro_descripcion_inversion.grid(
            row=1,
            column=2,
            sticky="ew",
            padx=6,
        )

        ctk.CTkButton(
            filtros,
            text="Aplicar filtros",
            command=self.aplicar_filtros_inversiones,
            width=120,
            height=36,
            corner_radius=9,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=1, column=3, padx=6)

        ctk.CTkButton(
            filtros,
            text="Ver todas",
            command=self.mostrar_todas_inversiones,
            width=95,
            height=36,
            corner_radius=9,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=1, column=4, padx=6)

        bloque_tabla = ctk.CTkFrame(
            master,
            fg_color=COLOR_PANEL_SECUNDARIO,
            corner_radius=10,
        )
        bloque_tabla.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=22,
            pady=(0, 8),
        )
        bloque_tabla.grid_rowconfigure(1, weight=1)
        bloque_tabla.grid_columnconfigure(0, weight=1)

        cabecera = ctk.CTkFrame(
            bloque_tabla,
            fg_color="transparent",
        )
        cabecera.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=12,
            pady=(9, 5),
        )
        cabecera.grid_columnconfigure(0, weight=1)
        self.etiqueta_resultados_inversiones = ctk.CTkLabel(
            cabecera,
            text="Cargando inversiones...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        )
        self.etiqueta_resultados_inversiones.grid(
            row=0,
            column=0,
            sticky="ew",
        )
        self.etiqueta_estado_inversiones = ctk.CTkLabel(
            cabecera,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="e",
        )
        self.etiqueta_estado_inversiones.grid(
            row=0,
            column=1,
            padx=(10, 0),
        )

        estilo = ttk.Style(self)
        estilo.configure(
            "PXInversion.Treeview",
            rowheight=34,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        estilo.configure(
            "PXInversion.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
        )
        estilo.map(
            "PXInversion.Treeview",
            background=[("selected", COLOR_PRIMARIO)],
            foreground=[("selected", "#FFFFFF")],
        )

        columnas = ("fecha", "descripcion", "monto")
        self.tabla_inversiones = ttk.Treeview(
            bloque_tabla,
            columns=columnas,
            show="headings",
            selectmode="browse",
            style="PXInversion.Treeview",
        )
        configuracion = {
            "fecha": ("Fecha", 120, "center"),
            "descripcion": ("Descripción", 430, "w"),
            "monto": ("Monto", 180, "e"),
        }
        for columna, (titulo, ancho, ancla) in configuracion.items():
            self.tabla_inversiones.heading(columna, text=titulo)
            self.tabla_inversiones.column(
                columna,
                width=ancho,
                minwidth=90,
                anchor=ancla,
                stretch=True,
            )
        self._bind_orden_columnas(
            tabla=self.tabla_inversiones,
            clave="inversiones",
            titulos={
                "fecha": "Fecha",
                "descripcion": "Descripción",
                "monto": "Monto",
            },
            tipos={
                "fecha": "fecha",
                "descripcion": "texto",
                "monto": "monto",
            },
            campos={},
            atributo_lista="inversiones_filtradas",
            callback_actualizar=self._actualizar_tras_orden_inversiones,
        )

        barra = ttk.Scrollbar(
            bloque_tabla,
            orient="vertical",
            command=self.tabla_inversiones.yview,
        )
        self.tabla_inversiones.configure(yscrollcommand=barra.set)
        self.tabla_inversiones.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(12, 0),
        )
        barra.grid(
            row=1,
            column=1,
            sticky="ns",
            padx=(0, 8),
        )
        self.tabla_inversiones.bind(
            "<<TreeviewSelect>>",
            self.seleccionar_fila_inversion,
        )
        self.tabla_inversiones.bind(
            "<Double-1>",
            lambda _evento: self.abrir_edicion_inversion(),
        )

        paginacion = ctk.CTkFrame(
            bloque_tabla,
            fg_color="transparent",
        )
        paginacion.grid(
            row=2,
            column=0,
            columnspan=2,
            pady=9,
        )
        self.boton_anterior_inversion = ctk.CTkButton(
            paginacion,
            text="Anterior",
            command=lambda: self.cambiar_pagina_inversiones(-1),
            width=82,
            height=30,
            corner_radius=8,
            fg_color=COLOR_PANEL,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        self.boton_anterior_inversion.grid(row=0, column=0)
        self.etiqueta_pagina_inversiones = ctk.CTkLabel(
            paginacion,
            text="Página 1 de 1",
            width=120,
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.etiqueta_pagina_inversiones.grid(
            row=0,
            column=1,
            padx=10,
        )
        self.boton_siguiente_inversion = ctk.CTkButton(
            paginacion,
            text="Siguiente",
            command=lambda: self.cambiar_pagina_inversiones(1),
            width=82,
            height=30,
            corner_radius=8,
            fg_color=COLOR_PANEL,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        self.boton_siguiente_inversion.grid(row=0, column=2)

        acciones = ctk.CTkFrame(master, fg_color="transparent")
        acciones.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=22,
            pady=(0, 12),
        )
        acciones.grid_columnconfigure(0, weight=1)
        self.etiqueta_seleccion_inversion = ctk.CTkLabel(
            acciones,
            text="Seleccioná una inversión de la tabla.",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        )
        self.etiqueta_seleccion_inversion.grid(
            row=0,
            column=0,
            sticky="ew",
        )
        self.boton_modificar_inversion = ctk.CTkButton(
            acciones,
            text="Modificar seleccionada",
            command=self.abrir_edicion_inversion,
            width=165,
            height=36,
            corner_radius=9,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"),
            state="disabled",
        )
        self.boton_modificar_inversion.grid(
            row=0,
            column=1,
            padx=(8, 6),
        )
        self.boton_eliminar_inversion = ctk.CTkButton(
            acciones,
            text="Eliminar seleccionada",
            command=self.eliminar_inversion_grafica,
            width=155,
            height=36,
            corner_radius=9,
            fg_color=COLOR_ROJO,
            hover_color="#BE3F3F",
            font=ctk.CTkFont(size=11, weight="bold"),
            state="disabled",
        )
        self.boton_eliminar_inversion.grid(row=0, column=2)

    def _bind_orden_columnas(
        self, tabla, clave, titulos, tipos, campos,
        atributo_lista, callback_actualizar, resolutores=None,
    ):
        """Registra clic-en-encabezado para ordenar una tabla ttk.Treeview.

        - tabla: el widget Treeview.
        - clave: nombre único para guardar el estado (columna/asc) de esta
          tabla en self.orden_tablas.
        - titulos: dict {columna: "Título visible"} (sin flechas).
        - tipos: dict {columna: "fecha" | "monto" | "texto"}.
        - campos: dict {columna: "clave_en_el_dict_de_datos"}; úsalo cuando
          el nombre de columna no coincide con la clave real del registro
          (ej. columna "concepto" pero el dato vive en datos["descripcion"]).
        - atributo_lista: nombre (string) del atributo de instancia que
          contiene la lista filtrada [(posicion, datos), ...].
        - callback_actualizar: función sin argumentos que redibuja la tabla
          (ya se encarga de resetear la página a 0 si corresponde).
        - resolutores: dict opcional {columna: función(datos) -> valor} para
          columnas cuyo valor no vive directo en el dict (ej. el nombre de
          un socio que se busca por id). Tiene prioridad sobre "campos".
        """
        self.orden_tablas[clave] = {
            "columna": None,
            "asc": True,
            "tabla": tabla,
            "titulos": titulos,
            "tipos": tipos,
            "campos": campos,
            "resolutores": resolutores or {},
            "atributo_lista": atributo_lista,
            "callback_actualizar": callback_actualizar,
        }
        for columna in titulos:
            tabla.heading(
                columna,
                command=lambda c=columna, k=clave: self._ordenar_tabla(k, c),
            )

    def _clave_orden_tabla(self, tipo, campo, resolutor=None):
        if resolutor is not None:
            if tipo == "fecha":
                def clave(item):
                    try:
                        return Movimientos.convertir_fecha(
                            resolutor(item[1]) or ""
                        )
                    except (ValueError, TypeError):
                        return datetime.min
            elif tipo == "monto":
                def clave(item):
                    valor = resolutor(item[1])
                    return valor if isinstance(valor, (int, float)) else 0
            else:
                def clave(item):
                    return str(resolutor(item[1]) or "").strip().lower()
            return clave

        if tipo == "fecha":
            def clave(item):
                try:
                    return Movimientos.convertir_fecha(
                        item[1].get(campo, "")
                    )
                except (ValueError, TypeError):
                    return datetime.min
        elif tipo == "periodo":
            def clave(item):
                try:
                    return datetime.strptime(
                        item[1].get(campo, ""), "%m-%Y"
                    )
                except (ValueError, TypeError):
                    return datetime.min
        elif tipo == "monto":
            def clave(item):
                valor = item[1].get(campo, 0)
                return valor if isinstance(valor, (int, float)) else 0
        else:
            def clave(item):
                return str(item[1].get(campo, "") or "").strip().lower()
        return clave

    def _ordenar_tabla(self, clave_estado, columna, alternar=True):
        estado = self.orden_tablas.get(clave_estado)
        if estado is None:
            return

        if alternar:
            if estado["columna"] == columna:
                estado["asc"] = not estado["asc"]
            else:
                estado["columna"] = columna
                estado["asc"] = True

        columna_activa = estado["columna"]
        if columna_activa is None:
            return

        lista = getattr(self, estado["atributo_lista"])
        tipo = estado["tipos"].get(columna_activa, "texto")
        campo = estado["campos"].get(columna_activa, columna_activa)
        resolutor = estado["resolutores"].get(columna_activa)
        lista.sort(
            key=self._clave_orden_tabla(tipo, campo, resolutor),
            reverse=not estado["asc"],
        )

        flecha = " ▲" if estado["asc"] else " ▼"
        for nombre_col, titulo in estado["titulos"].items():
            estado["tabla"].heading(
                nombre_col,
                text=titulo + (
                    flecha if nombre_col == columna_activa else ""
                ),
            )

        if alternar and estado["callback_actualizar"] is not None:
            estado["callback_actualizar"]()

    def _reaplicar_orden_tabla(self, clave_estado):
        estado = self.orden_tablas.get(clave_estado)
        if estado and estado["columna"] is not None:
            self._ordenar_tabla(clave_estado, estado["columna"], alternar=False)

    def _actualizar_tras_orden_inversiones(self):
        self.pagina_inversiones = 0
        self.actualizar_tabla_inversiones()

    def aplicar_filtros_inversiones(self):
        try:
            lineas = Movimientos.leer_datos(
                Movimientos.RUTA_INVERSIONES
            )
            self.inversiones_filtradas = filtrar_inversiones_graficas(
                lineas,
                self.filtro_inversion_desde.get(),
                self.filtro_inversion_hasta.get(),
                self.filtro_descripcion_inversion.get(),
            )
        except (ValueError, OSError) as error:
            self.etiqueta_estado_inversiones.configure(
                text=str(error),
                text_color=COLOR_ROJO,
            )
            return

        self.pagina_inversiones = 0
        self.etiqueta_estado_inversiones.configure(
            text="Filtros aplicados.",
            text_color=COLOR_VERDE,
        )
        self._reaplicar_orden_tabla("inversiones")
        self.actualizar_tabla_inversiones()

    def mostrar_todas_inversiones(self):
        self.filtro_inversion_desde.delete(0, "end")
        self.filtro_inversion_hasta.delete(0, "end")
        self.filtro_descripcion_inversion.delete(0, "end")
        self.aplicar_filtros_inversiones()

    def actualizar_tabla_inversiones(self):
        for item in self.tabla_inversiones.get_children():
            self.tabla_inversiones.delete(item)

        cantidad = len(self.inversiones_filtradas)
        total_paginas = max(
            1,
            (cantidad + INVERSIONES_POR_PAGINA - 1)
            // INVERSIONES_POR_PAGINA,
        )
        self.pagina_inversiones = min(
            max(self.pagina_inversiones, 0),
            total_paginas - 1,
        )
        inicio = self.pagina_inversiones * INVERSIONES_POR_PAGINA
        fin = inicio + INVERSIONES_POR_PAGINA
        inversiones_pagina = self.inversiones_filtradas[inicio:fin]

        for posicion, datos in inversiones_pagina:
            self.tabla_inversiones.insert(
                "",
                "end",
                iid=str(posicion),
                values=(
                    datos["fecha"],
                    datos["descripcion"],
                    "Gs. " + Movimientos.formatear_monto(
                        datos["monto"]
                    ),
                ),
            )

        total_filtrado = sum(
            datos["monto"]
            for _, datos in self.inversiones_filtradas
        )
        self.etiqueta_resultados_inversiones.configure(
            text=(
                f"{cantidad} inversión"
                if cantidad == 1
                else f"{cantidad} inversiones"
            )
            + " · Total: Gs. "
            + Movimientos.formatear_monto(total_filtrado)
        )
        self.etiqueta_pagina_inversiones.configure(
            text=(
                f"Página {self.pagina_inversiones + 1} "
                f"de {total_paginas}"
            )
        )
        self.boton_anterior_inversion.configure(
            state=(
                "normal"
                if self.pagina_inversiones > 0
                else "disabled"
            )
        )
        self.boton_siguiente_inversion.configure(
            state=(
                "normal"
                if self.pagina_inversiones < total_paginas - 1
                else "disabled"
            )
        )
        self.posicion_inversion_seleccionada = None
        self.etiqueta_seleccion_inversion.configure(
            text=(
                "No hay inversiones para mostrar."
                if cantidad == 0
                else "Seleccioná una inversión de la tabla."
            ),
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.boton_modificar_inversion.configure(state="disabled")
        self.boton_eliminar_inversion.configure(state="disabled")

    def cambiar_pagina_inversiones(self, desplazamiento):
        self.pagina_inversiones += desplazamiento
        self.actualizar_tabla_inversiones()

    def seleccionar_fila_inversion(self, _evento=None):
        seleccion = self.tabla_inversiones.selection()
        if not seleccion:
            return

        posicion = int(seleccion[0])
        lineas = Movimientos.leer_datos(Movimientos.RUTA_INVERSIONES)
        if not 0 <= posicion < len(lineas):
            self.aplicar_filtros_inversiones()
            return

        datos = Movimientos.separar_inversion(lineas[posicion])
        if datos is None:
            self.aplicar_filtros_inversiones()
            return

        self.posicion_inversion_seleccionada = posicion
        self.etiqueta_seleccion_inversion.configure(
            text=(
                f"Seleccionada: {datos['fecha']} · "
                f"{datos['descripcion']} · "
                f"Gs. {Movimientos.formatear_monto(datos['monto'])}"
            ),
            text_color=COLOR_TEXTO,
        )
        self.boton_modificar_inversion.configure(state="normal")
        self.boton_eliminar_inversion.configure(state="normal")

    def abrir_edicion_inversion(self):
        posicion = self.posicion_inversion_seleccionada
        if posicion is None:
            messagebox.showinfo(
                "Modificar inversión",
                "Seleccioná primero una inversión de la tabla.",
                parent=self,
            )
            return

        lineas = Movimientos.leer_datos(Movimientos.RUTA_INVERSIONES)
        if not 0 <= posicion < len(lineas):
            messagebox.showerror(
                "Modificar inversión",
                "La inversión seleccionada ya no está disponible.",
                parent=self,
            )
            self.aplicar_filtros_inversiones()
            return

        datos = Movimientos.separar_inversion(lineas[posicion])
        if datos is None:
            messagebox.showerror(
                "Modificar inversión",
                "No se pudo leer la inversión seleccionada.",
                parent=self,
            )
            return

        ventana = ctk.CTkToplevel(self)
        self.habilitar_navegacion_tab(ventana)
        ventana.title("Modificar inversión")
        ventana.geometry("570x430")
        ventana.minsize(520, 400)
        ventana.configure(fg_color=COLOR_FONDO)
        ventana.transient(self)
        ventana.grab_set()
        ventana.grid_columnconfigure(0, weight=1)
        self.ventana_edicion_inversion = ventana

        ctk.CTkLabel(
            ventana,
            text="Modificar inversión",
            font=ctk.CTkFont(size=23, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=26,
            pady=(24, 4),
        )
        ctk.CTkLabel(
            ventana,
            text="Los cambios reemplazarán solamente esta inversión.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=26,
            pady=(0, 14),
        )

        contenido = ctk.CTkFrame(
            ventana,
            fg_color=COLOR_PANEL,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        contenido.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=26,
            pady=(0, 14),
        )
        contenido.grid_columnconfigure(0, weight=1)
        contenido.grid_columnconfigure(1, weight=1)

        for texto, fila, columna in [
            ("Fecha", 0, 0),
            ("Monto", 0, 1),
            ("Descripción", 2, 0),
        ]:
            ctk.CTkLabel(
                contenido,
                text=texto,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            ).grid(
                row=fila,
                column=columna,
                columnspan=2 if texto == "Descripción" else 1,
                sticky="ew",
                padx=14,
                pady=(14 if fila == 0 else 8, 5),
            )

        self.entrada_fecha_edicion_inversion = ctk.CTkEntry(
            contenido,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
        )
        self.entrada_fecha_edicion_inversion.insert(0, datos["fecha"])
        self.entrada_fecha_edicion_inversion.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=14,
        )

        self.entrada_monto_edicion_inversion = ctk.CTkEntry(
            contenido,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
        )
        self.entrada_monto_edicion_inversion.insert(
            0,
            Movimientos.formatear_monto(datos["monto"]),
        )
        self.entrada_monto_edicion_inversion.grid(
            row=1,
            column=1,
            sticky="ew",
            padx=14,
        )

        self.entrada_descripcion_edicion_inversion = ctk.CTkEntry(
            contenido,
            height=40,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
        )
        self.entrada_descripcion_edicion_inversion.insert(
            0,
            datos["descripcion"],
        )
        self.entrada_descripcion_edicion_inversion.grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=14,
            pady=(0, 16),
        )

        acciones = ctk.CTkFrame(ventana, fg_color="transparent")
        acciones.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=26,
            pady=(0, 22),
        )
        acciones.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            acciones,
            text="Cancelar",
            command=ventana.destroy,
            width=105,
            height=40,
            corner_radius=9,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(
            acciones,
            text="Guardar cambios",
            command=lambda: self.guardar_edicion_inversion(posicion),
            width=145,
            height=40,
            corner_radius=9,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=2)

    def guardar_edicion_inversion(self, posicion):
        try:
            linea_nueva, _ = construir_inversion_grafica(
                self.entrada_fecha_edicion_inversion.get(),
                self.entrada_descripcion_edicion_inversion.get(),
                self.entrada_monto_edicion_inversion.get(),
            )
            lineas = Movimientos.leer_datos(
                Movimientos.RUTA_INVERSIONES
            )
            if not 0 <= posicion < len(lineas):
                raise ValueError(
                    "La inversión seleccionada ya no está disponible."
                )
            lineas[posicion] = linea_nueva
            Movimientos.guardar_datos(
                Movimientos.RUTA_INVERSIONES,
                lineas,
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo modificar",
                str(error),
                parent=self.ventana_edicion_inversion,
            )
            return

        self.ventana_edicion_inversion.destroy()
        self.aplicar_filtros_inversiones()
        self.etiqueta_estado_inversiones.configure(
            text="Inversión modificada correctamente.",
            text_color=COLOR_VERDE,
        )

    def eliminar_inversion_grafica(self):
        posicion = self.posicion_inversion_seleccionada
        if posicion is None:
            messagebox.showinfo(
                "Eliminar inversión",
                "Seleccioná primero una inversión de la tabla.",
                parent=self,
            )
            return

        lineas = Movimientos.leer_datos(Movimientos.RUTA_INVERSIONES)
        if not 0 <= posicion < len(lineas):
            messagebox.showerror(
                "Eliminar inversión",
                "La inversión seleccionada ya no está disponible.",
                parent=self,
            )
            self.aplicar_filtros_inversiones()
            return

        datos = Movimientos.separar_inversion(lineas[posicion])
        if datos is None:
            messagebox.showerror(
                "Eliminar inversión",
                "No se pudo leer la inversión seleccionada.",
                parent=self,
            )
            return

        confirmar = messagebox.askyesno(
            "Confirmar eliminación",
            (
                "¿Querés eliminar esta inversión?\n\n"
                f"{datos['fecha']} | {datos['descripcion']}\n"
                f"Gs. {Movimientos.formatear_monto(datos['monto'])}"
            ),
            icon="warning",
            parent=self,
        )
        if not confirmar:
            return

        try:
            lineas.pop(posicion)
            Movimientos.guardar_datos(
                Movimientos.RUTA_INVERSIONES,
                lineas,
            )
        except OSError as error:
            messagebox.showerror(
                "No se pudo eliminar",
                str(error),
                parent=self,
            )
            return

        self.aplicar_filtros_inversiones()
        self.etiqueta_estado_inversiones.configure(
            text="Inversión eliminada correctamente.",
            text_color=COLOR_VERDE,
        )

    def mostrar_prestamos(self):
        self.limpiar_contenedor()
        self.marcar_seleccion("Movimientos")
        self.pagina_prestamos = 0
        self.posicion_prestamo_seleccionado = None
        self.prestamo_seleccionado = None

        pagina = ctk.CTkFrame(
            self.contenedor,
            fg_color="transparent",
            corner_radius=0,
        )
        pagina.grid(row=0, column=0, sticky="nsew")

        encabezado = self.crear_encabezado(
            pagina,
            "Préstamos y cuotas",
            (
                "Controlá préstamos activos, pagos realizados e "
                "historial de préstamos totalmente pagados."
            ),
        )
        ctk.CTkButton(
            encabezado,
            text="Volver a Movimientos",
            command=lambda: self.mostrar_seccion("Movimientos"),
            width=165,
            height=38,
            corner_radius=10,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, rowspan=2, padx=(20, 0))

        self.pestanas_prestamos = ctk.CTkTabview(
            pagina,
            fg_color=COLOR_PANEL,
            segmented_button_fg_color=COLOR_PANEL_SECUNDARIO,
            segmented_button_selected_color=COLOR_PRIMARIO,
            segmented_button_selected_hover_color=COLOR_PRIMARIO_HOVER,
            segmented_button_unselected_color=COLOR_PANEL_SECUNDARIO,
            segmented_button_unselected_hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        self.pestanas_prestamos.pack(
            fill="both",
            expand=True,
            padx=34,
            pady=(0, 26),
        )
        pestaña_registrar = self.pestanas_prestamos.add(
            "Registrar préstamo"
        )
        pestaña_gestionar = self.pestanas_prestamos.add(
            "Ver, modificar o eliminar"
        )

        self.construir_registro_prestamo(pestaña_registrar)
        self.construir_gestion_prestamos(pestaña_gestionar)
        self.aplicar_filtros_prestamos()

    def construir_registro_prestamo(self, master):
        master.grid_columnconfigure(0, weight=1)

        formulario = ctk.CTkFrame(master, fg_color="transparent")
        formulario.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=18,
            pady=18,
        )
        formulario.grid_columnconfigure(0, weight=1)
        formulario.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            formulario,
            text="Nuevo préstamo",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=(4, 16),
        )

        etiquetas = [
            ("Descripción", 1, 0),
            ("Banco", 1, 1),
            ("Fecha de recepción", 3, 0),
            ("Cantidad de cuotas", 3, 1),
            ("Monto recibido", 5, 0),
            ("Total a devolver", 5, 1),
        ]
        for texto, fila, columna in etiquetas:
            ctk.CTkLabel(
                formulario,
                text=texto,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            ).grid(
                row=fila,
                column=columna,
                sticky="ew",
                padx=8,
                pady=(0, 5),
            )

        self.entrada_descripcion_prestamo = ctk.CTkEntry(
            formulario,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="Ej.: Compra de armazones",
        )
        self.entrada_descripcion_prestamo.grid(
            row=2, column=0, sticky="ew", padx=8, pady=(0, 14)
        )
        self.entrada_banco_prestamo = ctk.CTkEntry(
            formulario,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="Ej.: Ueno",
        )
        self.entrada_banco_prestamo.grid(
            row=2, column=1, sticky="ew", padx=8, pady=(0, 14)
        )
        self.entrada_fecha_prestamo = ctk.CTkEntry(
            formulario,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="DD-MM-AAAA",
        )
        self.entrada_fecha_prestamo.insert(
            0, datetime.now().strftime("%d-%m-%Y")
        )
        self.entrada_fecha_prestamo.grid(
            row=4, column=0, sticky="ew", padx=8, pady=(0, 14)
        )
        self.entrada_cantidad_cuotas_prestamo = ctk.CTkEntry(
            formulario,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="Ej.: 12",
        )
        self.entrada_cantidad_cuotas_prestamo.grid(
            row=4, column=1, sticky="ew", padx=8, pady=(0, 14)
        )
        self.entrada_monto_recibido_prestamo = ctk.CTkEntry(
            formulario,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="Ej.: 10000000",
        )
        self.entrada_monto_recibido_prestamo.grid(
            row=6, column=0, sticky="ew", padx=8, pady=(0, 16)
        )
        self.entrada_total_devolver_prestamo = ctk.CTkEntry(
            formulario,
            height=42,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="Ej.: 14000000",
        )
        self.entrada_total_devolver_prestamo.grid(
            row=6, column=1, sticky="ew", padx=8, pady=(0, 16)
        )

        aviso = ctk.CTkFrame(
            formulario,
            fg_color=("#FFF4E5", "#3D2A13"),
            corner_radius=10,
        )
        aviso.grid(
            row=7,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=(4, 14),
        )
        ctk.CTkLabel(
            aviso,
            text=(
                "El préstamo queda PAGADO solamente cuando la suma de "
                "las cuotas alcanza el total a devolver."
            ),
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).pack(fill="x", padx=14, pady=12)

        ctk.CTkButton(
            formulario,
            text="Guardar préstamo",
            command=self.guardar_prestamo_grafico,
            height=42,
            corner_radius=9,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(
            row=8,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
        )

    def guardar_prestamo_grafico(self):
        try:
            existentes = Movimientos.obtener_prestamos_validos()
            ids = [
                int(datos["id"])
                for _, datos in existentes
                if datos["id"].isdigit()
            ]
            nuevo_id = str(max(ids, default=0) + 1)
            linea, datos = construir_prestamo_grafico(
                self.entrada_descripcion_prestamo.get(),
                self.entrada_banco_prestamo.get(),
                self.entrada_fecha_prestamo.get(),
                self.entrada_monto_recibido_prestamo.get(),
                self.entrada_total_devolver_prestamo.get(),
                self.entrada_cantidad_cuotas_prestamo.get(),
                nuevo_id,
            )
            lineas = Movimientos.leer_datos(
                Movimientos.RUTA_PRESTAMOS
            )
            lineas.append(linea)
            Movimientos.guardar_datos(
                Movimientos.RUTA_PRESTAMOS,
                lineas,
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo guardar",
                str(error),
                parent=self,
            )
            return

        for entrada in [
            self.entrada_descripcion_prestamo,
            self.entrada_banco_prestamo,
            self.entrada_cantidad_cuotas_prestamo,
            self.entrada_monto_recibido_prestamo,
            self.entrada_total_devolver_prestamo,
        ]:
            entrada.delete(0, "end")
        self.aplicar_filtros_prestamos()
        messagebox.showinfo(
            "Préstamo registrado",
            (
                f"{datos['descripcion']} se guardó correctamente.\n\n"
                "Monto recibido: Gs. "
                + Movimientos.formatear_monto(
                    datos["monto_recibido"]
                )
                + "\nTotal a devolver: Gs. "
                + Movimientos.formatear_monto(datos["costo_total"])
            ),
            parent=self,
        )

    def construir_gestion_prestamos(self, master):
        master.grid_columnconfigure(0, weight=1)
        master.grid_rowconfigure(2, weight=1)

        filtros = ctk.CTkFrame(master, fg_color="transparent")
        filtros.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=18,
            pady=(16, 8),
        )
        filtros.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            filtros,
            text="Mostrar:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
        ).grid(row=0, column=0, padx=(0, 6))
        self.combo_estado_prestamos = ctk.CTkComboBox(
            filtros,
            values=["Activos", "Pagados"],
            command=self.cambiar_estado_prestamos,
            width=135,
            height=36,
            state="readonly",
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXTO,
            text_color=COLOR_TEXTO,
        )
        self.combo_estado_prestamos.set("Activos")
        self.combo_estado_prestamos.grid(row=0, column=1, padx=(0, 14))

        self.etiqueta_periodo_prestamos = ctk.CTkLabel(
            filtros,
            text="Período de pago:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.etiqueta_periodo_prestamos.grid(row=0, column=2, padx=(0, 6))
        self.entrada_periodo_prestamos = ctk.CTkEntry(
            filtros,
            width=115,
            height=36,
            corner_radius=9,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
            placeholder_text="MM-AAAA",
        )
        self.entrada_periodo_prestamos.grid(
            row=0, column=3, sticky="w", padx=(0, 12)
        )
        ctk.CTkButton(
            filtros,
            text="Aplicar",
            command=self.aplicar_filtros_prestamos,
            width=90,
            height=36,
            corner_radius=9,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=4)

        self.etiqueta_estado_prestamos = ctk.CTkLabel(
            master,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        )
        self.etiqueta_estado_prestamos.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=22,
            pady=(0, 5),
        )

        bloque = ctk.CTkFrame(
            master,
            fg_color=COLOR_PANEL_SECUNDARIO,
            corner_radius=12,
        )
        bloque.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=18,
            pady=(0, 8),
        )
        bloque.grid_columnconfigure(0, weight=1)
        bloque.grid_rowconfigure(1, weight=1)

        self.etiqueta_resultados_prestamos = ctk.CTkLabel(
            bloque,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        )
        self.etiqueta_resultados_prestamos.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=12,
            pady=(8, 4),
        )

        estilo = ttk.Style(self)
        estilo.configure(
            "PXPrestamo.Treeview",
            rowheight=34,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        estilo.configure(
            "PXPrestamo.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
        )
        estilo.map(
            "PXPrestamo.Treeview",
            background=[("selected", COLOR_PRIMARIO)],
            foreground=[("selected", "#FFFFFF")],
        )

        columnas = (
            "descripcion",
            "banco",
            "fecha",
            "recibido",
            "pagado",
            "saldo",
            "cuotas",
        )
        self.tabla_prestamos = ttk.Treeview(
            bloque,
            columns=columnas,
            show="headings",
            selectmode="browse",
            style="PXPrestamo.Treeview",
        )
        configuracion = {
            "descripcion": ("Descripción", 175, "w"),
            "banco": ("Banco", 100, "w"),
            "fecha": ("Recepción", 90, "center"),
            "recibido": ("Recibido", 125, "e"),
            "pagado": ("Pagado", 125, "e"),
            "saldo": ("Saldo", 125, "e"),
            "cuotas": ("Cuotas", 75, "center"),
        }
        for columna, (titulo, ancho, ancla) in configuracion.items():
            self.tabla_prestamos.heading(columna, text=titulo)
            self.tabla_prestamos.column(
                columna,
                width=ancho,
                minwidth=70,
                anchor=ancla,
                stretch=True,
            )
        barra = ttk.Scrollbar(
            bloque,
            orient="vertical",
            command=self.tabla_prestamos.yview,
        )
        self.tabla_prestamos.configure(yscrollcommand=barra.set)
        self.tabla_prestamos.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(12, 0),
        )
        barra.grid(row=1, column=1, sticky="ns", padx=(0, 8))
        self.tabla_prestamos.bind(
            "<<TreeviewSelect>>",
            self.seleccionar_fila_prestamo,
        )

        paginacion = ctk.CTkFrame(bloque, fg_color="transparent")
        paginacion.grid(
            row=2,
            column=0,
            columnspan=2,
            pady=8,
        )
        self.boton_anterior_prestamo = ctk.CTkButton(
            paginacion,
            text="Anterior",
            command=lambda: self.cambiar_pagina_prestamos(-1),
            width=82,
            height=30,
            fg_color=COLOR_PANEL,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        )
        self.boton_anterior_prestamo.grid(row=0, column=0)
        self.etiqueta_pagina_prestamos = ctk.CTkLabel(
            paginacion,
            text="Página 1 de 1",
            width=120,
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.etiqueta_pagina_prestamos.grid(
            row=0, column=1, padx=10
        )
        self.boton_siguiente_prestamo = ctk.CTkButton(
            paginacion,
            text="Siguiente",
            command=lambda: self.cambiar_pagina_prestamos(1),
            width=82,
            height=30,
            fg_color=COLOR_PANEL,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        )
        self.boton_siguiente_prestamo.grid(row=0, column=2)

        acciones = ctk.CTkFrame(master, fg_color="transparent")
        acciones.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=20,
            pady=(0, 14),
        )
        acciones.grid_columnconfigure(0, weight=1)
        self.etiqueta_seleccion_prestamo = ctk.CTkLabel(
            acciones,
            text="Seleccioná un préstamo de la tabla.",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        )
        self.etiqueta_seleccion_prestamo.grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(0, 7),
        )
        self.boton_registrar_cuota = ctk.CTkButton(
            acciones,
            text="Registrar cuota",
            command=self.abrir_registro_cuota,
            height=34,
            width=125,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
            state="disabled",
        )
        self.boton_registrar_cuota.grid(row=1, column=1, padx=4)
        self.boton_gestionar_cuotas = ctk.CTkButton(
            acciones,
            text="Ver o modificar cuotas",
            command=self.abrir_gestion_cuotas,
            height=34,
            width=155,
            fg_color=COLOR_NARANJA,
            hover_color="#C77B20",
            state="disabled",
        )
        self.boton_gestionar_cuotas.grid(row=1, column=2, padx=4)
        self.boton_modificar_prestamo = ctk.CTkButton(
            acciones,
            text="Modificar préstamo",
            command=self.abrir_edicion_prestamo,
            height=34,
            width=140,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            state="disabled",
        )
        self.boton_modificar_prestamo.grid(row=1, column=3, padx=4)
        self.boton_eliminar_prestamo = ctk.CTkButton(
            acciones,
            text="Eliminar préstamo",
            command=self.eliminar_prestamo_grafico,
            height=34,
            width=135,
            fg_color=COLOR_ROJO,
            hover_color="#BE3F3F",
            state="disabled",
        )
        self.boton_eliminar_prestamo.grid(row=1, column=4, padx=(4, 0))
        self.cambiar_estado_prestamos("Activos")

    def cambiar_estado_prestamos(self, estado):
        es_pagado = estado == "Pagados"
        estado_control = "normal" if es_pagado else "disabled"
        self.entrada_periodo_prestamos.configure(state=estado_control)
        if es_pagado and not self.entrada_periodo_prestamos.get():
            self.entrada_periodo_prestamos.insert(
                0, datetime.now().strftime("%m-%Y")
            )
        self.aplicar_filtros_prestamos()

    def aplicar_filtros_prestamos(self):
        try:
            estado = self.combo_estado_prestamos.get()
            periodo = (
                self.entrada_periodo_prestamos.get()
                if estado == "Pagados"
                else ""
            )
            self.prestamos_filtrados = obtener_prestamos_graficos(
                estado,
                periodo,
            )
        except (ValueError, OSError) as error:
            self.etiqueta_estado_prestamos.configure(
                text=str(error),
                text_color=COLOR_ROJO,
            )
            return

        self.pagina_prestamos = 0
        self.etiqueta_estado_prestamos.configure(
            text=(
                "Préstamos activos."
                if estado == "Activos"
                else "Historial de préstamos pagados."
            ),
            text_color=COLOR_VERDE,
        )
        self.actualizar_tabla_prestamos()

    def actualizar_tabla_prestamos(self):
        for item in self.tabla_prestamos.get_children():
            self.tabla_prestamos.delete(item)

        cantidad = len(self.prestamos_filtrados)
        total_paginas = max(
            1,
            (cantidad + PRESTAMOS_POR_PAGINA - 1)
            // PRESTAMOS_POR_PAGINA,
        )
        self.pagina_prestamos = min(
            max(self.pagina_prestamos, 0),
            total_paginas - 1,
        )
        inicio = self.pagina_prestamos * PRESTAMOS_POR_PAGINA
        fin = inicio + PRESTAMOS_POR_PAGINA

        for posicion, prestamo, estado in self.prestamos_filtrados[
            inicio:fin
        ]:
            self.tabla_prestamos.insert(
                "",
                "end",
                iid=str(posicion),
                values=(
                    prestamo["descripcion"],
                    prestamo["banco"],
                    prestamo["fecha"],
                    "Gs. "
                    + Movimientos.formatear_monto(
                        prestamo["monto_recibido"]
                    ),
                    "Gs. "
                    + Movimientos.formatear_monto(
                        estado["total_pagado"]
                    ),
                    "Gs. "
                    + Movimientos.formatear_monto(estado["saldo"]),
                    (
                        f"{len(estado['cuotas'])}/"
                        f"{prestamo['cantidad_cuotas']}"
                    ),
                ),
            )

        self.etiqueta_resultados_prestamos.configure(
            text=(
                f"{cantidad} préstamo"
                if cantidad == 1
                else f"{cantidad} préstamos"
            )
        )
        self.etiqueta_pagina_prestamos.configure(
            text=(
                f"Página {self.pagina_prestamos + 1} "
                f"de {total_paginas}"
            )
        )
        self.boton_anterior_prestamo.configure(
            state="normal" if self.pagina_prestamos > 0 else "disabled"
        )
        self.boton_siguiente_prestamo.configure(
            state=(
                "normal"
                if self.pagina_prestamos < total_paginas - 1
                else "disabled"
            )
        )
        self.posicion_prestamo_seleccionado = None
        self.prestamo_seleccionado = None
        self.etiqueta_seleccion_prestamo.configure(
            text=(
                "No hay préstamos para mostrar."
                if cantidad == 0
                else "Seleccioná un préstamo de la tabla."
            ),
            text_color=COLOR_TEXTO_SUAVE,
        )
        for boton in [
            self.boton_registrar_cuota,
            self.boton_gestionar_cuotas,
            self.boton_modificar_prestamo,
            self.boton_eliminar_prestamo,
        ]:
            boton.configure(state="disabled")

    def cambiar_pagina_prestamos(self, desplazamiento):
        self.pagina_prestamos += desplazamiento
        self.actualizar_tabla_prestamos()

    def seleccionar_fila_prestamo(self, _evento=None):
        seleccion = self.tabla_prestamos.selection()
        if not seleccion:
            return

        posicion = int(seleccion[0])
        lineas = Movimientos.leer_datos(Movimientos.RUTA_PRESTAMOS)
        if not 0 <= posicion < len(lineas):
            self.aplicar_filtros_prestamos()
            return
        prestamo = Movimientos.separar_prestamo(lineas[posicion])
        if prestamo is None:
            self.aplicar_filtros_prestamos()
            return

        estado = Movimientos.estado_prestamo(prestamo)
        self.posicion_prestamo_seleccionado = posicion
        self.prestamo_seleccionado = prestamo
        texto_estado = "PAGADO" if estado["pagado"] else "ACTIVO"
        self.etiqueta_seleccion_prestamo.configure(
            text=(
                f"{prestamo['descripcion']} · {prestamo['banco']} · "
                f"{texto_estado} · Pagado Gs. "
                f"{Movimientos.formatear_monto(estado['total_pagado'])} "
                f"· Saldo Gs. "
                f"{Movimientos.formatear_monto(estado['saldo'])}"
            ),
            text_color=COLOR_TEXTO,
        )
        self.boton_registrar_cuota.configure(
            state="disabled" if estado["pagado"] else "normal"
        )
        self.boton_gestionar_cuotas.configure(state="normal")
        self.boton_modificar_prestamo.configure(state="normal")
        self.boton_eliminar_prestamo.configure(state="normal")

    def obtener_prestamo_seleccionado_actual(self):
        posicion = self.posicion_prestamo_seleccionado
        if posicion is None:
            raise ValueError("Seleccioná primero un préstamo.")
        lineas = Movimientos.leer_datos(Movimientos.RUTA_PRESTAMOS)
        if not 0 <= posicion < len(lineas):
            raise ValueError(
                "El préstamo seleccionado ya no está disponible."
            )
        prestamo = Movimientos.separar_prestamo(lineas[posicion])
        if prestamo is None:
            raise ValueError("No se pudo leer el préstamo seleccionado.")
        return posicion, prestamo

    def abrir_registro_cuota(self):
        try:
            _, prestamo = self.obtener_prestamo_seleccionado_actual()
            estado = Movimientos.estado_prestamo(prestamo)
            if estado["pagado"]:
                raise ValueError(
                    "Este préstamo ya está totalmente pagado."
                )
        except (ValueError, OSError) as error:
            messagebox.showerror("Registrar cuota", str(error), parent=self)
            return

        numero = siguiente_numero_cuota(prestamo["id"])
        sugerido = min(
            round(
                prestamo["costo_total"]
                / prestamo["cantidad_cuotas"]
            ),
            estado["saldo"],
        )
        ventana = ctk.CTkToplevel(self)
        self.habilitar_navegacion_tab(ventana)
        ventana.title("Registrar pago de cuota")
        ventana.geometry("520x430")
        ventana.minsize(500, 410)
        ventana.configure(fg_color=COLOR_FONDO)
        ventana.transient(self)
        ventana.grab_set()
        ventana.grid_columnconfigure(0, weight=1)
        self.ventana_registro_cuota = ventana

        ctk.CTkLabel(
            ventana,
            text="Registrar pago de cuota",
            font=ctk.CTkFont(size=23, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0, column=0, sticky="ew", padx=26, pady=(24, 4)
        )
        ctk.CTkLabel(
            ventana,
            text=(
                f"{prestamo['descripcion']} · {prestamo['banco']}\n"
                f"Próxima cuota: {numero} · Saldo: Gs. "
                f"{Movimientos.formatear_monto(estado['saldo'])}"
            ),
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
            justify="left",
        ).grid(
            row=1, column=0, sticky="ew", padx=26, pady=(0, 14)
        )

        contenido = ctk.CTkFrame(
            ventana,
            fg_color=COLOR_PANEL,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        contenido.grid(
            row=2, column=0, sticky="ew", padx=26, pady=(0, 14)
        )
        contenido.grid_columnconfigure(0, weight=1)
        contenido.grid_columnconfigure(1, weight=1)
        for texto, columna in [("Fecha de pago", 0), ("Monto real", 1)]:
            ctk.CTkLabel(
                contenido,
                text=texto,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            ).grid(
                row=0,
                column=columna,
                sticky="ew",
                padx=14,
                pady=(14, 5),
            )
        self.entrada_fecha_cuota = ctk.CTkEntry(
            contenido,
            height=40,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
        )
        self.entrada_fecha_cuota.insert(
            0, datetime.now().strftime("%d-%m-%Y")
        )
        self.entrada_fecha_cuota.grid(
            row=1, column=0, sticky="ew", padx=14, pady=(0, 16)
        )
        self.entrada_monto_cuota = ctk.CTkEntry(
            contenido,
            height=40,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
        )
        self.entrada_monto_cuota.insert(
            0, Movimientos.formatear_monto(sugerido)
        )
        self.entrada_monto_cuota.grid(
            row=1, column=1, sticky="ew", padx=14, pady=(0, 16)
        )

        ctk.CTkLabel(
            ventana,
            text=(
                "El monto completo de esta cuota se incluirá como "
                "egreso del mes."
            ),
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO_SUAVE,
        ).grid(row=3, column=0, sticky="w", padx=26)
        acciones = ctk.CTkFrame(ventana, fg_color="transparent")
        acciones.grid(
            row=4, column=0, sticky="ew", padx=26, pady=(18, 22)
        )
        acciones.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            acciones,
            text="Cancelar",
            command=ventana.destroy,
            width=105,
            height=40,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        ).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(
            acciones,
            text="Guardar cuota",
            command=lambda: self.guardar_cuota_grafica(
                prestamo, numero
            ),
            width=135,
            height=40,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
        ).grid(row=0, column=2)

    def guardar_cuota_grafica(self, prestamo, numero):
        estado = Movimientos.estado_prestamo(prestamo)
        try:
            linea, _ = construir_cuota_grafica(
                prestamo,
                numero,
                self.entrada_fecha_cuota.get(),
                self.entrada_monto_cuota.get(),
                estado["total_pagado"],
            )
            cuotas = Movimientos.leer_datos(
                Movimientos.RUTA_CUOTAS_PRESTAMOS
            )
            cuotas.append(linea)
            Movimientos.guardar_datos(
                Movimientos.RUTA_CUOTAS_PRESTAMOS,
                cuotas,
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo guardar",
                str(error),
                parent=self.ventana_registro_cuota,
            )
            return

        self.ventana_registro_cuota.destroy()
        self.aplicar_filtros_prestamos()
        nuevo_estado = Movimientos.estado_prestamo(prestamo)
        mensaje = "Cuota registrada correctamente."
        if nuevo_estado["pagado"]:
            mensaje += "\n\nEl préstamo quedó totalmente PAGADO."
        messagebox.showinfo("Pago de cuota", mensaje, parent=self)

    def abrir_edicion_prestamo(self):
        try:
            posicion, prestamo = (
                self.obtener_prestamo_seleccionado_actual()
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "Modificar préstamo", str(error), parent=self
            )
            return

        ventana = ctk.CTkToplevel(self)
        self.habilitar_navegacion_tab(ventana)
        ventana.title("Modificar préstamo")
        ventana.geometry("640x580")
        ventana.minsize(600, 550)
        ventana.configure(fg_color=COLOR_FONDO)
        ventana.transient(self)
        ventana.grab_set()
        ventana.grid_columnconfigure(0, weight=1)
        self.ventana_edicion_prestamo = ventana

        ctk.CTkLabel(
            ventana,
            text="Modificar préstamo",
            font=ctk.CTkFont(size=23, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0, column=0, sticky="ew", padx=26, pady=(24, 4)
        )
        ctk.CTkLabel(
            ventana,
            text=(
                "Las cuotas ya registradas se conservarán sin cambios."
            ),
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).grid(
            row=1, column=0, sticky="ew", padx=26, pady=(0, 14)
        )

        contenido = ctk.CTkFrame(
            ventana,
            fg_color=COLOR_PANEL,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        contenido.grid(
            row=2, column=0, sticky="nsew", padx=26, pady=(0, 14)
        )
        contenido.grid_columnconfigure(0, weight=1)
        contenido.grid_columnconfigure(1, weight=1)
        campos = [
            ("Descripción", "descripcion", 0, 0, prestamo["descripcion"]),
            ("Banco", "banco", 0, 1, prestamo["banco"]),
            ("Fecha", "fecha", 2, 0, prestamo["fecha"]),
            (
                "Cantidad de cuotas",
                "cantidad",
                2,
                1,
                str(prestamo["cantidad_cuotas"]),
            ),
            (
                "Monto recibido",
                "recibido",
                4,
                0,
                Movimientos.formatear_monto(
                    prestamo["monto_recibido"]
                ),
            ),
            (
                "Total a devolver",
                "total",
                4,
                1,
                Movimientos.formatear_monto(
                    prestamo["costo_total"]
                ),
            ),
        ]
        self.campos_edicion_prestamo = {}
        for titulo, clave, fila, columna, valor in campos:
            ctk.CTkLabel(
                contenido,
                text=titulo,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            ).grid(
                row=fila,
                column=columna,
                sticky="ew",
                padx=14,
                pady=(14 if fila == 0 else 8, 5),
            )
            entrada = ctk.CTkEntry(
                contenido,
                height=40,
                border_color=COLOR_BORDE,
                fg_color=COLOR_PANEL_SECUNDARIO,
                text_color=COLOR_TEXTO,
            )
            entrada.insert(0, valor)
            entrada.grid(
                row=fila + 1,
                column=columna,
                sticky="ew",
                padx=14,
                pady=(0, 14 if fila < 4 else 18),
            )
            self.campos_edicion_prestamo[clave] = entrada

        acciones = ctk.CTkFrame(ventana, fg_color="transparent")
        acciones.grid(
            row=3, column=0, sticky="ew", padx=26, pady=(0, 22)
        )
        acciones.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            acciones,
            text="Cancelar",
            command=ventana.destroy,
            width=105,
            height=40,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        ).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(
            acciones,
            text="Guardar cambios",
            command=lambda: self.guardar_edicion_prestamo(
                posicion, prestamo
            ),
            width=145,
            height=40,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
        ).grid(row=0, column=2)

    def guardar_edicion_prestamo(self, posicion, prestamo):
        campos = self.campos_edicion_prestamo
        try:
            linea, datos = construir_prestamo_grafico(
                campos["descripcion"].get(),
                campos["banco"].get(),
                campos["fecha"].get(),
                campos["recibido"].get(),
                campos["total"].get(),
                campos["cantidad"].get(),
                prestamo["id"],
            )
            cuotas = Movimientos.cuotas_de_prestamo(prestamo["id"])
            if datos["cantidad_cuotas"] < len(cuotas):
                raise ValueError(
                    "La cantidad de cuotas no puede ser menor que las "
                    "cuotas ya registradas."
                )
            total_pagado = sum(
                cuota["monto"] for _, cuota in cuotas
            )
            if datos["costo_total"] < total_pagado:
                raise ValueError(
                    "El total a devolver no puede ser menor que lo "
                    "ya pagado: Gs. "
                    + Movimientos.formatear_monto(total_pagado)
                    + "."
                )
            lineas = Movimientos.leer_datos(
                Movimientos.RUTA_PRESTAMOS
            )
            if not 0 <= posicion < len(lineas):
                raise ValueError(
                    "El préstamo seleccionado ya no está disponible."
                )
            lineas[posicion] = linea
            Movimientos.guardar_datos(
                Movimientos.RUTA_PRESTAMOS,
                lineas,
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo modificar",
                str(error),
                parent=self.ventana_edicion_prestamo,
            )
            return

        self.ventana_edicion_prestamo.destroy()
        self.aplicar_filtros_prestamos()
        messagebox.showinfo(
            "Modificar préstamo",
            "El préstamo se modificó correctamente.",
            parent=self,
        )

    def eliminar_prestamo_grafico(self):
        try:
            posicion, prestamo = (
                self.obtener_prestamo_seleccionado_actual()
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "Eliminar préstamo", str(error), parent=self
            )
            return

        cuotas = Movimientos.cuotas_de_prestamo(prestamo["id"])
        confirmar = messagebox.askyesno(
            "Confirmar eliminación",
            (
                "¿Querés eliminar este préstamo y todas sus cuotas?\n\n"
                f"{prestamo['descripcion']} · {prestamo['banco']}\n"
                f"Cuotas asociadas: {len(cuotas)}"
            ),
            icon="warning",
            parent=self,
        )
        if not confirmar:
            return

        try:
            prestamos = Movimientos.leer_datos(
                Movimientos.RUTA_PRESTAMOS
            )
            if not 0 <= posicion < len(prestamos):
                raise ValueError(
                    "El préstamo seleccionado ya no está disponible."
                )
            prestamos.pop(posicion)
            Movimientos.guardar_datos(
                Movimientos.RUTA_PRESTAMOS,
                prestamos,
            )
            lineas_cuotas = Movimientos.leer_datos(
                Movimientos.RUTA_CUOTAS_PRESTAMOS
            )
            lineas_cuotas = [
                linea
                for linea in lineas_cuotas
                if (
                    Movimientos.separar_cuota(linea) is None
                    or Movimientos.separar_cuota(linea)[
                        "prestamo_id"
                    ]
                    != prestamo["id"]
                )
            ]
            Movimientos.guardar_datos(
                Movimientos.RUTA_CUOTAS_PRESTAMOS,
                lineas_cuotas,
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo eliminar", str(error), parent=self
            )
            return

        self.aplicar_filtros_prestamos()
        self.etiqueta_estado_prestamos.configure(
            text="Préstamo y cuotas eliminados correctamente.",
            text_color=COLOR_VERDE,
        )

    def abrir_gestion_cuotas(self):
        try:
            _, prestamo = self.obtener_prestamo_seleccionado_actual()
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "Cuotas del préstamo", str(error), parent=self
            )
            return

        ventana = ctk.CTkToplevel(self)
        self.habilitar_navegacion_tab(ventana)
        ventana.title("Cuotas del préstamo")
        ventana.geometry("680x560")
        ventana.minsize(620, 510)
        ventana.configure(fg_color=COLOR_FONDO)
        ventana.transient(self)
        ventana.grab_set()
        ventana.grid_columnconfigure(0, weight=1)
        ventana.grid_rowconfigure(2, weight=1)
        self.ventana_gestion_cuotas = ventana
        self.prestamo_cuotas_actual = prestamo
        self.pagina_cuotas = 0
        self.posicion_cuota_seleccionada = None

        estado = Movimientos.estado_prestamo(prestamo)
        ctk.CTkLabel(
            ventana,
            text=f"Cuotas de {prestamo['descripcion']}",
            font=ctk.CTkFont(size=23, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0, column=0, sticky="ew", padx=26, pady=(24, 4)
        )
        self.etiqueta_resumen_cuotas = ctk.CTkLabel(
            ventana,
            text=(
                f"{prestamo['banco']} · Pagado Gs. "
                f"{Movimientos.formatear_monto(estado['total_pagado'])}"
                f" · Saldo Gs. "
                f"{Movimientos.formatear_monto(estado['saldo'])}"
            ),
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        )
        self.etiqueta_resumen_cuotas.grid(
            row=1, column=0, sticky="ew", padx=26, pady=(0, 14)
        )

        bloque = ctk.CTkFrame(
            ventana,
            fg_color=COLOR_PANEL,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        bloque.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=26,
            pady=(0, 12),
        )
        bloque.grid_columnconfigure(0, weight=1)
        bloque.grid_rowconfigure(0, weight=1)
        self.tabla_cuotas = ttk.Treeview(
            bloque,
            columns=("numero", "fecha", "monto"),
            show="headings",
            selectmode="browse",
            style="PXPrestamo.Treeview",
        )
        for columna, titulo, ancho, ancla in [
            ("numero", "Cuota", 100, "center"),
            ("fecha", "Fecha", 160, "center"),
            ("monto", "Monto pagado", 240, "e"),
        ]:
            self.tabla_cuotas.heading(columna, text=titulo)
            self.tabla_cuotas.column(
                columna, width=ancho, anchor=ancla, stretch=True
            )
        self.tabla_cuotas.grid(
            row=0, column=0, sticky="nsew", padx=12, pady=(12, 0)
        )
        self.tabla_cuotas.bind(
            "<<TreeviewSelect>>", self.seleccionar_fila_cuota
        )

        paginacion = ctk.CTkFrame(bloque, fg_color="transparent")
        paginacion.grid(row=1, column=0, pady=10)
        self.boton_anterior_cuota = ctk.CTkButton(
            paginacion,
            text="Anterior",
            command=lambda: self.cambiar_pagina_cuotas(-1),
            width=82,
            height=30,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        )
        self.boton_anterior_cuota.grid(row=0, column=0)
        self.etiqueta_pagina_cuotas = ctk.CTkLabel(
            paginacion,
            text="Página 1 de 1",
            width=120,
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.etiqueta_pagina_cuotas.grid(row=0, column=1, padx=10)
        self.boton_siguiente_cuota = ctk.CTkButton(
            paginacion,
            text="Siguiente",
            command=lambda: self.cambiar_pagina_cuotas(1),
            width=82,
            height=30,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        )
        self.boton_siguiente_cuota.grid(row=0, column=2)

        acciones = ctk.CTkFrame(ventana, fg_color="transparent")
        acciones.grid(
            row=3, column=0, sticky="ew", padx=26, pady=(0, 22)
        )
        acciones.grid_columnconfigure(0, weight=1)
        self.boton_modificar_cuota = ctk.CTkButton(
            acciones,
            text="Modificar cuota",
            command=self.abrir_edicion_cuota,
            width=125,
            height=38,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            state="disabled",
        )
        self.boton_modificar_cuota.grid(row=0, column=1, padx=(0, 8))
        self.boton_eliminar_cuota = ctk.CTkButton(
            acciones,
            text="Eliminar cuota",
            command=self.eliminar_cuota_grafica,
            width=120,
            height=38,
            fg_color=COLOR_ROJO,
            hover_color="#BE3F3F",
            state="disabled",
        )
        self.boton_eliminar_cuota.grid(row=0, column=2, padx=(0, 8))
        ctk.CTkButton(
            acciones,
            text="Cerrar",
            command=ventana.destroy,
            width=95,
            height=38,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        ).grid(row=0, column=3)
        self.actualizar_tabla_cuotas()

    def actualizar_tabla_cuotas(self):
        for item in self.tabla_cuotas.get_children():
            self.tabla_cuotas.delete(item)
        cuotas = Movimientos.cuotas_de_prestamo(
            self.prestamo_cuotas_actual["id"]
        )
        cantidad = len(cuotas)
        total_paginas = max(
            1,
            (cantidad + CUOTAS_POR_PAGINA - 1)
            // CUOTAS_POR_PAGINA,
        )
        self.pagina_cuotas = min(
            max(self.pagina_cuotas, 0), total_paginas - 1
        )
        inicio = self.pagina_cuotas * CUOTAS_POR_PAGINA
        fin = inicio + CUOTAS_POR_PAGINA
        for posicion, cuota in cuotas[inicio:fin]:
            self.tabla_cuotas.insert(
                "",
                "end",
                iid=str(posicion),
                values=(
                    cuota["numero"],
                    cuota["fecha"],
                    "Gs. "
                    + Movimientos.formatear_monto(cuota["monto"]),
                ),
            )
        self.etiqueta_pagina_cuotas.configure(
            text=(
                f"Página {self.pagina_cuotas + 1} "
                f"de {total_paginas}"
            )
        )
        self.boton_anterior_cuota.configure(
            state="normal" if self.pagina_cuotas > 0 else "disabled"
        )
        self.boton_siguiente_cuota.configure(
            state=(
                "normal"
                if self.pagina_cuotas < total_paginas - 1
                else "disabled"
            )
        )
        estado = Movimientos.estado_prestamo(
            self.prestamo_cuotas_actual
        )
        self.etiqueta_resumen_cuotas.configure(
            text=(
                f"{self.prestamo_cuotas_actual['banco']} · "
                f"{cantidad} pagos · Pagado Gs. "
                f"{Movimientos.formatear_monto(estado['total_pagado'])}"
                f" · Saldo Gs. "
                f"{Movimientos.formatear_monto(estado['saldo'])}"
            )
        )
        self.posicion_cuota_seleccionada = None
        self.boton_modificar_cuota.configure(state="disabled")
        self.boton_eliminar_cuota.configure(state="disabled")

    def cambiar_pagina_cuotas(self, desplazamiento):
        self.pagina_cuotas += desplazamiento
        self.actualizar_tabla_cuotas()

    def seleccionar_fila_cuota(self, _evento=None):
        seleccion = self.tabla_cuotas.selection()
        if not seleccion:
            return
        self.posicion_cuota_seleccionada = int(seleccion[0])
        self.boton_modificar_cuota.configure(state="normal")
        self.boton_eliminar_cuota.configure(state="normal")

    def obtener_cuota_seleccionada(self):
        posicion = self.posicion_cuota_seleccionada
        if posicion is None:
            raise ValueError("Seleccioná primero una cuota.")
        lineas = Movimientos.leer_datos(
            Movimientos.RUTA_CUOTAS_PRESTAMOS
        )
        if not 0 <= posicion < len(lineas):
            raise ValueError(
                "La cuota seleccionada ya no está disponible."
            )
        cuota = Movimientos.separar_cuota(lineas[posicion])
        if (
            cuota is None
            or cuota["prestamo_id"]
            != self.prestamo_cuotas_actual["id"]
        ):
            raise ValueError("No se pudo leer la cuota seleccionada.")
        return posicion, cuota

    def abrir_edicion_cuota(self):
        try:
            posicion, cuota = self.obtener_cuota_seleccionada()
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "Modificar cuota",
                str(error),
                parent=self.ventana_gestion_cuotas,
            )
            return

        ventana = ctk.CTkToplevel(self.ventana_gestion_cuotas)
        self.habilitar_navegacion_tab(ventana)
        ventana.title("Modificar cuota")
        ventana.geometry("500x360")
        ventana.minsize(470, 340)
        ventana.configure(fg_color=COLOR_FONDO)
        ventana.transient(self.ventana_gestion_cuotas)
        ventana.grab_set()
        ventana.grid_columnconfigure(0, weight=1)
        self.ventana_edicion_cuota = ventana

        ctk.CTkLabel(
            ventana,
            text=f"Modificar cuota {cuota['numero']}",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0, column=0, sticky="ew", padx=26, pady=(24, 14)
        )
        cuerpo = ctk.CTkFrame(
            ventana,
            fg_color=COLOR_PANEL,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        cuerpo.grid(row=1, column=0, sticky="ew", padx=26)
        cuerpo.grid_columnconfigure(0, weight=1)
        cuerpo.grid_columnconfigure(1, weight=1)
        for texto, columna in [("Fecha", 0), ("Monto", 1)]:
            ctk.CTkLabel(
                cuerpo,
                text=texto,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            ).grid(
                row=0,
                column=columna,
                sticky="ew",
                padx=14,
                pady=(14, 5),
            )
        self.entrada_fecha_edicion_cuota = ctk.CTkEntry(
            cuerpo,
            height=40,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
        )
        self.entrada_fecha_edicion_cuota.insert(0, cuota["fecha"])
        self.entrada_fecha_edicion_cuota.grid(
            row=1, column=0, sticky="ew", padx=14, pady=(0, 16)
        )
        self.entrada_monto_edicion_cuota = ctk.CTkEntry(
            cuerpo,
            height=40,
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
        )
        self.entrada_monto_edicion_cuota.insert(
            0, Movimientos.formatear_monto(cuota["monto"])
        )
        self.entrada_monto_edicion_cuota.grid(
            row=1, column=1, sticky="ew", padx=14, pady=(0, 16)
        )
        acciones = ctk.CTkFrame(ventana, fg_color="transparent")
        acciones.grid(
            row=2, column=0, sticky="ew", padx=26, pady=(18, 22)
        )
        acciones.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            acciones,
            text="Cancelar",
            command=ventana.destroy,
            width=100,
            height=38,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        ).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(
            acciones,
            text="Guardar cambios",
            command=lambda: self.guardar_edicion_cuota(
                posicion, cuota
            ),
            width=140,
            height=38,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
        ).grid(row=0, column=2)

    def guardar_edicion_cuota(self, posicion, cuota_original):
        prestamo = self.prestamo_cuotas_actual
        cuotas = Movimientos.cuotas_de_prestamo(prestamo["id"])
        total_otros = sum(
            cuota["monto"]
            for pos, cuota in cuotas
            if pos != posicion
        )
        try:
            linea, _ = construir_cuota_grafica(
                prestamo,
                cuota_original["numero"],
                self.entrada_fecha_edicion_cuota.get(),
                self.entrada_monto_edicion_cuota.get(),
                total_otros,
            )
            lineas = Movimientos.leer_datos(
                Movimientos.RUTA_CUOTAS_PRESTAMOS
            )
            if not 0 <= posicion < len(lineas):
                raise ValueError(
                    "La cuota seleccionada ya no está disponible."
                )
            lineas[posicion] = linea
            Movimientos.guardar_datos(
                Movimientos.RUTA_CUOTAS_PRESTAMOS,
                lineas,
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo modificar",
                str(error),
                parent=self.ventana_edicion_cuota,
            )
            return

        self.ventana_edicion_cuota.destroy()
        self.actualizar_tabla_cuotas()
        self.aplicar_filtros_prestamos()

    def eliminar_cuota_grafica(self):
        try:
            posicion, cuota = self.obtener_cuota_seleccionada()
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "Eliminar cuota",
                str(error),
                parent=self.ventana_gestion_cuotas,
            )
            return
        confirmar = messagebox.askyesno(
            "Confirmar eliminación",
            (
                f"¿Querés eliminar la cuota {cuota['numero']}?\n\n"
                f"{cuota['fecha']} · Gs. "
                f"{Movimientos.formatear_monto(cuota['monto'])}"
            ),
            icon="warning",
            parent=self.ventana_gestion_cuotas,
        )
        if not confirmar:
            return
        try:
            lineas = Movimientos.leer_datos(
                Movimientos.RUTA_CUOTAS_PRESTAMOS
            )
            if not 0 <= posicion < len(lineas):
                raise ValueError(
                    "La cuota seleccionada ya no está disponible."
                )
            lineas.pop(posicion)
            Movimientos.guardar_datos(
                Movimientos.RUTA_CUOTAS_PRESTAMOS,
                lineas,
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo eliminar",
                str(error),
                parent=self.ventana_gestion_cuotas,
            )
            return
        self.actualizar_tabla_cuotas()
        self.aplicar_filtros_prestamos()

    def mostrar_cierre_mensual(self):
        self.limpiar_contenedor()
        self.marcar_seleccion("Movimientos")

        pagina = ctk.CTkScrollableFrame(
            self.contenedor,
            fg_color="transparent",
            corner_radius=0,
        )
        pagina.grid(row=0, column=0, sticky="nsew")

        self.crear_encabezado(
            pagina,
            "Cierre mensual",
            (
                "Calculá el resultado del mes y registrá el fondo "
                "de estabilidad cuando el cierre esté confirmado."
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
        controles.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            controles,
            text="Período",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXTO,
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(20, 10),
            pady=20,
        )

        self.entrada_periodo_cierre = ctk.CTkEntry(
            controles,
            width=150,
            height=40,
            placeholder_text="MM-AAAA",
            border_color=COLOR_BORDE,
            fg_color=COLOR_PANEL_SECUNDARIO,
            text_color=COLOR_TEXTO,
        )
        self.entrada_periodo_cierre.insert(
            0,
            datetime.now().strftime("%m-%Y"),
        )
        self.entrada_periodo_cierre.grid(
            row=0,
            column=1,
            sticky="w",
            padx=(0, 16),
            pady=20,
        )
        self.entrada_periodo_cierre.bind(
            "<Return>",
            lambda _evento: self.calcular_y_mostrar_cierre(False),
        )

        ctk.CTkButton(
            controles,
            text="Calcular vista previa",
            command=lambda: self.calcular_y_mostrar_cierre(False),
            width=165,
            height=40,
            corner_radius=9,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(
            row=0,
            column=2,
            padx=(0, 10),
            pady=20,
        )

        ctk.CTkButton(
            controles,
            text="Guardar cierre y fondo",
            command=lambda: self.calcular_y_mostrar_cierre(True),
            width=175,
            height=40,
            corner_radius=9,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(
            row=0,
            column=3,
            padx=(0, 20),
            pady=20,
        )

        aviso = ctk.CTkFrame(
            pagina,
            fg_color=("#FFF7E8", "#3B2C16"),
            corner_radius=12,
            border_width=1,
            border_color=("#F2D49B", "#684B20"),
        )
        aviso.pack(fill="x", padx=34, pady=(0, 14))
        ctk.CTkLabel(
            aviso,
            text=(
                "La vista previa no modifica datos. “Guardar cierre y "
                "fondo” crea o actualiza el registro automático del mes. "
                "Si el fondo fue ajustado manualmente desde Socios, "
                "ese monto se conserva."
            ),
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO,
            justify="left",
            anchor="w",
            wraplength=850,
        ).pack(fill="x", padx=16, pady=13)

        self.zona_resultado_cierre = ctk.CTkFrame(
            pagina,
            fg_color="transparent",
        )
        self.zona_resultado_cierre.pack(
            fill="both",
            expand=True,
            padx=34,
            pady=(0, 30),
        )

        self.calcular_y_mostrar_cierre(False)

    def calcular_y_mostrar_cierre(self, guardar):
        periodo = self.entrada_periodo_cierre.get().strip()

        if guardar:
            try:
                fecha_desde, _ = limites_periodo_grafico(periodo)
            except ValueError as error:
                messagebox.showerror(
                    "Período inválido",
                    str(error),
                    parent=self,
                )
                return

            hoy = datetime.now()
            periodo_en_curso = (
                fecha_desde.year == hoy.year
                and fecha_desde.month == hoy.month
            )
            mensaje = (
                f"¿Querés guardar el cierre de {periodo} y "
                "actualizar su fondo de estabilidad?"
            )
            if periodo_en_curso:
                mensaje += (
                    "\n\nEste mes todavía está en curso. Podrás volver "
                    "a guardarlo más adelante para actualizar los cálculos."
                )

            if not messagebox.askyesno(
                "Guardar cierre mensual",
                mensaje,
                icon="question",
                parent=self,
            ):
                return

        try:
            cierre = calcular_cierre_grafico(
                periodo,
                guardar_fondo=guardar,
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo calcular el cierre",
                str(error),
                parent=self,
            )
            return

        self.entrada_periodo_cierre.delete(0, "end")
        self.entrada_periodo_cierre.insert(0, cierre["periodo"])
        self.dibujar_resultado_cierre(cierre)

        if guardar:
            fondo = cierre["fondo"]
            detalle = (
                "El ajuste manual existente fue conservado."
                if fondo["modo"] == "MANUAL"
                else "El fondo automático quedó actualizado."
            )
            messagebox.showinfo(
                "Cierre guardado",
                (
                    f"El cierre de {cierre['periodo']} quedó guardado.\n\n"
                    f"{detalle}"
                ),
                parent=self,
            )

    def dibujar_resultado_cierre(self, cierre):
        for widget in self.zona_resultado_cierre.winfo_children():
            widget.destroy()

        indicadores = cierre["indicadores"]
        fondo = cierre["fondo"]

        cabecera = ctk.CTkFrame(
            self.zona_resultado_cierre,
            fg_color="transparent",
        )
        cabecera.pack(fill="x", pady=(4, 10))
        cabecera.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            cabecera,
            text=(
                "Resultado · "
                + cierre["fecha_desde"].strftime("%d-%m-%Y")
                + " al "
                + cierre["fecha_hasta"].strftime("%d-%m-%Y")
            ),
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        estado_texto = {
            "AUTOMATICO": "CIERRE AUTOMÁTICO GUARDADO",
            "MANUAL": "FONDO AJUSTADO MANUALMENTE",
            "PROVISORIO": "VISTA PREVIA · SIN GUARDAR",
        }[fondo["modo"]]
        estado_color = (
            ("#DDF7EC", "#153D31")
            if fondo["modo"] == "AUTOMATICO"
            else (
                ("#FFF0D9", "#4A3215")
                if fondo["modo"] == "MANUAL"
                else ("#DDE8FF", "#1B3565")
            )
        )
        estado_texto_color = (
            ("#11704F", "#9CE1C5")
            if fondo["modo"] == "AUTOMATICO"
            else (
                ("#9B5D05", "#FFD18B")
                if fondo["modo"] == "MANUAL"
                else ("#174DAF", "#B9D0FF")
            )
        )
        ctk.CTkLabel(
            cabecera,
            text=estado_texto,
            height=30,
            corner_radius=8,
            fg_color=estado_color,
            text_color=estado_texto_color,
            font=ctk.CTkFont(size=10, weight="bold"),
        ).grid(row=0, column=1, padx=(16, 0))

        tarjetas = ctk.CTkFrame(
            self.zona_resultado_cierre,
            fg_color="transparent",
        )
        tarjetas.pack(fill="x", pady=(0, 10))
        for columna in range(4):
            tarjetas.grid_columnconfigure(
                columna,
                weight=1,
                uniform="cierre",
            )

        datos_tarjetas = [
            (
                "Ingresos",
                monto(indicadores["ingresos"]),
                COLOR_VERDE,
                "Incluye ingresos adicionales",
            ),
            (
                "Egresos",
                monto(indicadores["egresos"]),
                COLOR_ROJO,
                "Incluye todos los egresos y la nómina bruta",
            ),
            (
                "Utilidad del mes",
                monto(indicadores["utilidad_mes"]),
                (
                    COLOR_VERDE
                    if indicadores["utilidad_mes"] >= 0
                    else COLOR_ROJO
                ),
                "Ingresos menos todos los egresos",
            ),
            (
                "Margen",
                (
                    Movimientos.formatear_porcentaje(
                        indicadores["margen_porcentual"]
                    )
                    + "%"
                ),
                COLOR_PRIMARIO,
                "Utilidad sobre ingresos",
            ),
            (
                "Fondo aplicado",
                monto(fondo["monto_aplicado"]),
                COLOR_NARANJA,
                f"{Movimientos.PORCENTAJE_FONDO_ESTABILIDAD}% "
                "de utilidad positiva",
            ),
            (
                "Utilidad repartible",
                monto(cierre["utilidad_repartible"]),
                COLOR_VERDE,
                "Después del fondo",
            ),
            (
                "Salida real de dinero",
                monto(indicadores["salida_caja_total"]),
                COLOR_PRIMARIO,
                "Pagos efectivamente realizados",
            ),
            (
                "Descuentos retenidos",
                monto(indicadores["diferencia_egreso_caja"]),
                COLOR_NARANJA,
                "IPS y otros descuentos de nómina",
            ),
        ]

        for indice, (titulo, valor, color, descripcion) in enumerate(
            datos_tarjetas
        ):
            tarjeta = ctk.CTkFrame(
                tarjetas,
                fg_color=COLOR_PANEL,
                corner_radius=14,
                border_width=1,
                border_color=COLOR_BORDE,
            )
            tarjeta.grid(
                row=indice // 4,
                column=indice % 4,
                sticky="nsew",
                padx=5,
                pady=5,
            )
            ctk.CTkFrame(
                tarjeta,
                width=7,
                height=32,
                corner_radius=4,
                fg_color=color,
            ).pack(anchor="nw", padx=16, pady=(16, 0))
            ctk.CTkLabel(
                tarjeta,
                text=titulo,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            ).pack(fill="x", padx=16, pady=(8, 2))
            ctk.CTkLabel(
                tarjeta,
                text=valor,
                font=ctk.CTkFont(size=18, weight="bold"),
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
                wraplength=190,
            ).pack(fill="x", padx=16, pady=(3, 16))

        self.dibujar_tabla_unidades_cierre(cierre)
        self.dibujar_componentes_cierre(cierre)
        self.dibujar_conciliacion_nomina(cierre)
        self.dibujar_detalles_cierre(cierre)

    def dibujar_tabla_unidades_cierre(self, cierre):
        panel = ctk.CTkFrame(
            self.zona_resultado_cierre,
            fg_color=COLOR_PANEL,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        panel.pack(fill="x", pady=7)

        ctk.CTkLabel(
            panel,
            text="Resultado por unidad",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).pack(fill="x", padx=18, pady=(16, 10))

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
            height=max(len(cierre["unidades"]), 1),
        )
        titulos = {
            "unidad": "Unidad",
            "ingresos": "Ingresos",
            "egresos": "Egresos",
            "resultado": "Resultado",
            "recibidas": "Transf. recibidas",
            "enviadas": "Transf. enviadas",
        }
        anchos = {
            "unidad": 130,
            "ingresos": 130,
            "egresos": 130,
            "resultado": 130,
            "recibidas": 130,
            "enviadas": 130,
        }
        for columna in columnas:
            tabla.heading(columna, text=titulos[columna])
            tabla.column(
                columna,
                width=anchos[columna],
                minwidth=90,
                anchor="center",
                stretch=True,
            )

        for unidad in cierre["unidades"]:
            tabla.insert(
                "",
                "end",
                values=(
                    unidad["unidad"],
                    Movimientos.formatear_monto(unidad["ingresos"]),
                    Movimientos.formatear_monto(unidad["egresos"]),
                    Movimientos.formatear_monto(unidad["resultado"]),
                    Movimientos.formatear_monto(
                        unidad["transferencias_recibidas"]
                    ),
                    Movimientos.formatear_monto(
                        unidad["transferencias_enviadas"]
                    ),
                ),
            )
        tabla.pack(fill="x", padx=18, pady=(0, 18))

    def dibujar_componentes_cierre(self, cierre):
        indicadores = cierre["indicadores"]
        panel = ctk.CTkFrame(
            self.zona_resultado_cierre,
            fg_color=COLOR_PANEL,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        panel.pack(fill="x", pady=7)
        panel.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            panel,
            text="Componentes del cierre",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=18,
            pady=(16, 10),
        )

        componentes = [
            (
                "Ingresos adicionales",
                indicadores["ingresos_adicionales"],
                "Suman a los ingresos",
            ),
            (
                "Egresos adicionales",
                indicadores["egresos_adicionales"],
                "Suman a los egresos",
            ),
            (
                "Cuotas de préstamos",
                cierre["total_cuotas"],
                "Cada cuota completa suma como egreso",
            ),
            (
                "Nómina del mes",
                cierre["total_sueldos"],
                "Remuneración bruta incluida en Egresos",
            ),
            (
                "Inversiones",
                cierre["total_inversiones"],
                "Informativo: no modifica el resultado",
            ),
            (
                "Fondo acumulado",
                cierre["fondo_acumulado"],
                "Suma de cierres guardados",
            ),
        ]

        for indice, (nombre, valor, nota) in enumerate(componentes, start=1):
            fondo_fila = (
                COLOR_PANEL_SECUNDARIO
                if indice % 2 == 1
                else "transparent"
            )
            fila = ctk.CTkFrame(panel, fg_color=fondo_fila)
            fila.grid(
                row=indice,
                column=0,
                columnspan=2,
                sticky="ew",
                padx=18,
                pady=2,
            )
            fila.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                fila,
                text=nombre,
                width=190,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXTO,
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=12, pady=9)
            ctk.CTkLabel(
                fila,
                text=monto(valor),
                width=160,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXTO,
                anchor="e",
            ).grid(row=0, column=1, sticky="e", padx=12, pady=9)
            ctk.CTkLabel(
                fila,
                text=nota,
                width=310,
                font=ctk.CTkFont(size=11),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            ).grid(row=0, column=2, sticky="w", padx=12, pady=9)

        fondo = cierre["fondo"]
        texto_fondo = (
            f"Fondo calculado: {monto(fondo['monto_calculado'])} · "
            f"Fondo aplicado: {monto(fondo['monto_aplicado'])} · "
            f"Modo: {fondo['modo']}"
        )
        if fondo["modo"] == "MANUAL":
            texto_fondo += (
                " · El monto manual se conserva aunque cambien "
                "los movimientos."
            )
        ctk.CTkLabel(
            panel,
            text=texto_fondo,
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO_SUAVE,
            justify="left",
            anchor="w",
            wraplength=850,
        ).grid(
            row=len(componentes) + 1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=18,
            pady=(10, 16),
        )

    def dibujar_conciliacion_nomina(self, cierre):
        nomina = cierre["nomina"]
        panel = ctk.CTkFrame(
            self.zona_resultado_cierre,
            fg_color=COLOR_PANEL,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        panel.pack(fill="x", pady=7)

        ctk.CTkLabel(
            panel,
            text="Conciliación de nómina",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).pack(fill="x", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            panel,
            text=(
                "El total de Egresos usa la remuneración bruta, como "
                "tu planilla. La salida real muestra lo efectivamente "
                "pagado sin volver a contar retenciones."
            ),
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).pack(fill="x", padx=18, pady=(0, 10))

        filas = [
            (
                "Sueldo bruto ajustado",
                nomina["sueldo_bruto_ajustado"],
                "Después de ausencias y reposos",
            ),
            (
                "Comisiones",
                nomina["comisiones"],
                "Suman a la remuneración",
            ),
            (
                "Remuneración bruta",
                nomina["remuneracion_bruta"],
                "Sueldo ajustado + comisiones",
            ),
            (
                "IPS descontado",
                nomina["descuento_ips"],
                "No se suma aquí; el pago de IPS va en adicionales",
            ),
            (
                "Otros descuentos",
                nomina["otros_descuentos"],
                "Reducen el pago al funcionario",
            ),
            (
                "Adelantos ya entregados",
                nomina["adelantos"],
                "Salida de caja incluida automáticamente",
            ),
            (
                "Neto pagado al liquidar",
                nomina["neto_cobrar"],
                "Importe pendiente abonado al funcionario",
            ),
            (
                "Nómina incluida en Egresos",
                nomina["egreso_planilla"],
                "Remuneración bruta del mes",
            ),
            (
                "Salida real de caja por nómina",
                nomina["salida_caja"],
                "Neto + adelantos efectivamente entregados",
            ),
        ]

        tabla = ttk.Treeview(
            panel,
            columns=("concepto", "monto", "tratamiento"),
            show="headings",
            height=len(filas),
        )
        for columna, titulo, ancho, ancla in [
            ("concepto", "Concepto", 260, "w"),
            ("monto", "Monto", 180, "e"),
            ("tratamiento", "Tratamiento en el cierre", 500, "w"),
        ]:
            tabla.heading(columna, text=titulo)
            tabla.column(
                columna,
                width=ancho,
                minwidth=100,
                anchor=ancla,
                stretch=True,
            )

        for concepto, valor, tratamiento in filas:
            tabla.insert(
                "",
                "end",
                values=(
                    concepto,
                    Movimientos.formatear_monto(valor),
                    tratamiento,
                ),
            )
        tabla.pack(fill="x", padx=18, pady=(0, 10))

        ctk.CTkLabel(
            panel,
            text=(
                "Sol y Rodrigo deben tener una liquidación mensual de "
                "Gs. 8.000.000 en Recursos Humanos. No cargues esos "
                "sueldos ni los adelantos nuevamente como movimientos."
            ),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_NARANJA,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=18, pady=(0, 16))

    def dibujar_detalles_cierre(self, cierre):
        panel = ctk.CTkFrame(
            self.zona_resultado_cierre,
            fg_color=COLOR_PANEL,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        panel.pack(fill="x", pady=7)

        ctk.CTkLabel(
            panel,
            text="Detalle incluido en los egresos",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).pack(fill="x", padx=18, pady=(16, 10))

        pestanas = ctk.CTkTabview(
            panel,
            fg_color=COLOR_PANEL_SECUNDARIO,
            segmented_button_fg_color=COLOR_PANEL_SECUNDARIO,
            segmented_button_selected_color=COLOR_PRIMARIO,
            segmented_button_selected_hover_color=COLOR_PRIMARIO_HOVER,
        )
        pestanas.pack(fill="x", padx=18, pady=(0, 18))
        tab_cuotas = pestanas.add(
            f"Cuotas ({len(cierre['detalle_cuotas'])})"
        )
        tab_sueldos = pestanas.add(
            f"Sueldos ({len(cierre['detalle_sueldos'])})"
        )

        tabla_cuotas = ttk.Treeview(
            tab_cuotas,
            columns=("fecha", "prestamo", "cuota", "monto"),
            show="headings",
            height=5,
        )
        for columna, titulo, ancho in [
            ("fecha", "Fecha", 120),
            ("prestamo", "Préstamo", 340),
            ("cuota", "Cuota", 90),
            ("monto", "Monto", 150),
        ]:
            tabla_cuotas.heading(columna, text=titulo)
            tabla_cuotas.column(
                columna,
                width=ancho,
                minwidth=80,
                anchor="center",
                stretch=True,
            )
        for nombre, cuota in cierre["detalle_cuotas"]:
            tabla_cuotas.insert(
                "",
                "end",
                values=(
                    cuota["fecha"],
                    nombre,
                    cuota["numero"],
                    Movimientos.formatear_monto(cuota["monto"]),
                ),
            )
        tabla_cuotas.pack(fill="x", padx=10, pady=10)

        tabla_sueldos = ttk.Treeview(
            tab_sueldos,
            columns=(
                "periodo",
                "funcionario",
                "bruto",
                "comisiones",
                "ips",
                "adelantos",
                "otros",
                "neto",
                "salida",
            ),
            show="headings",
            height=5,
        )
        for columna, titulo, ancho in [
            ("periodo", "Período", 80),
            ("funcionario", "Funcionario", 190),
            ("bruto", "Bruto ajustado", 105),
            ("comisiones", "Comisiones", 95),
            ("ips", "IPS", 85),
            ("adelantos", "Adelantos", 90),
            ("otros", "Otros", 80),
            ("neto", "Neto", 100),
            ("salida", "Salida de caja", 110),
        ]:
            tabla_sueldos.heading(columna, text=titulo)
            tabla_sueldos.column(
                columna,
                width=ancho,
                minwidth=90,
                anchor="center",
                stretch=True,
            )
        for sueldo in cierre["detalle_sueldos"]:
            tabla_sueldos.insert(
                "",
                "end",
                values=(
                    sueldo["periodo"],
                    sueldo["nombre"],
                    Movimientos.formatear_monto(
                        sueldo["sueldo_bruto_ajustado"]
                    ),
                    Movimientos.formatear_monto(
                        sueldo["comisiones"]
                    ),
                    Movimientos.formatear_monto(
                        sueldo["descuento_ips"]
                    ),
                    Movimientos.formatear_monto(
                        sueldo["adelantos"]
                    ),
                    Movimientos.formatear_monto(
                        sueldo["otros_descuentos"]
                    ),
                    Movimientos.formatear_monto(
                        sueldo["neto_cobrar"]
                    ),
                    Movimientos.formatear_monto(
                        sueldo["salida_caja"]
                    ),
                ),
            )
        tabla_sueldos.pack(fill="x", padx=10, pady=10)

    def mostrar_socios(self, pestana_inicial="Resumen mensual"):
        self.limpiar_contenedor()
        self.marcar_seleccion("Socios")
        self.orden_tablas.pop("retiros", None)
        self.orden_tablas.pop("fondos", None)

        pagina = ctk.CTkScrollableFrame(
            self.contenedor,
            fg_color="transparent",
            corner_radius=0,
        )
        pagina.grid(row=0, column=0, sticky="nsew")

        self.crear_encabezado(
            pagina,
            "Socios",
            (
                "Movimientos personales de Sol y Rodrigo, distribución mensual "
                "y fondo de estabilidad."
            ),
        )

        aviso = ctk.CTkFrame(
            pagina,
            fg_color=("#EAF1FF", "#142746"),
            corner_radius=12,
            border_width=1,
            border_color=("#CADBFF", "#24416D"),
        )
        aviso.pack(fill="x", padx=34, pady=(0, 14))
        ctk.CTkLabel(
            aviso,
            text=(
                "Los gastos e inversiones personales de los socios no son "
                "gastos operativos. Los gastos personales reducen el saldo "
                "del socio; las inversiones personales quedan solo para "
                "control y no modifican ese saldo."
            ),
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO,
            justify="left",
            anchor="w",
            wraplength=850,
        ).pack(fill="x", padx=16, pady=13)

        pestanas = ctk.CTkTabview(
            pagina,
            fg_color=COLOR_PANEL,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDE,
            segmented_button_fg_color=COLOR_PANEL_SECUNDARIO,
            segmented_button_selected_color=COLOR_PRIMARIO,
            segmented_button_selected_hover_color=COLOR_PRIMARIO_HOVER,
        )
        pestanas.pack(
            fill="both",
            expand=True,
            padx=34,
            pady=(0, 30),
        )

        tab_registrar = pestanas.add("Registrar movimiento")
        tab_resumen = pestanas.add("Resumen mensual")
        tab_gestionar = pestanas.add("Gestionar retiros")
        tab_fondo = pestanas.add("Fondo de estabilidad")

        self.construir_registro_retiro(tab_registrar)
        self.construir_resumen_socios(tab_resumen)
        self.construir_gestion_retiros(tab_gestionar)
        self.construir_fondo_estabilidad(tab_fondo)

        if pestana_inicial in [
            "Registrar movimiento",
            "Resumen mensual",
            "Gestionar retiros",
            "Fondo de estabilidad",
        ]:
            pestanas.set(pestana_inicial)

    def construir_registro_retiro(self, master):
        master.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            master,
            text="Registrar movimiento personal",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=20,
            pady=(22, 6),
        )
        ctk.CTkLabel(
            master,
            text=(
                "Gasto personal se descuenta del sueldo y la utilidad "
                "asignada. Inversión personal queda solo para control y "
                "no modifica el saldo mensual ni la utilidad del negocio."
            ),
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
            justify="left",
            wraplength=760,
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=20,
            pady=(0, 18),
        )

        etiquetas = [
            ("Fecha", "DD-MM-AAAA"),
            ("Socio", ""),
            ("Tipo", ""),
            ("Monto retirado", "Ej.: 2.000.000"),
            ("Observación", "Opcional"),
        ]
        for fila, (titulo, ayuda) in enumerate(etiquetas, start=2):
            ctk.CTkLabel(
                master,
                text=titulo,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXTO,
                anchor="w",
            ).grid(
                row=fila,
                column=0,
                sticky="w",
                padx=(20, 14),
                pady=7,
            )

            if titulo == "Socio":
                self.selector_socio_retiro = ctk.CTkOptionMenu(
                    master,
                    values=[
                        socio["nombre"]
                        for socio in Socios.SOCIOS
                    ],
                    fg_color=COLOR_PANEL_SECUNDARIO,
                    button_color=COLOR_PRIMARIO,
                    button_hover_color=COLOR_PRIMARIO_HOVER,
                    text_color=COLOR_TEXTO,
                )
                self.selector_socio_retiro.set("Sol")
                campo = self.selector_socio_retiro
            elif titulo == "Tipo":
                self.selector_tipo_retiro = ctk.CTkOptionMenu(
                    master,
                    values=Socios.TIPOS_MOVIMIENTO_PERSONAL,
                    fg_color=COLOR_PANEL_SECUNDARIO,
                    button_color=COLOR_PRIMARIO,
                    button_hover_color=COLOR_PRIMARIO_HOVER,
                    text_color=COLOR_TEXTO,
                )
                self.selector_tipo_retiro.set(
                    Socios.TIPO_MOVIMIENTO_PREDETERMINADO
                )
                campo = self.selector_tipo_retiro
            else:
                campo = ctk.CTkEntry(
                    master,
                    placeholder_text=ayuda,
                    height=38,
                    fg_color=COLOR_PANEL_SECUNDARIO,
                    border_color=COLOR_BORDE,
                    text_color=COLOR_TEXTO,
                )
                if titulo == "Fecha":
                    self.entrada_fecha_retiro = campo
                    campo.insert(0, datetime.now().strftime("%d-%m-%Y"))
                elif titulo == "Monto retirado":
                    self.entrada_monto_retiro = campo
                else:
                    self.entrada_observacion_retiro = campo

            campo.grid(
                row=fila,
                column=1,
                sticky="ew",
                padx=(0, 20),
                pady=7,
            )

        ctk.CTkButton(
            master,
            text="Guardar movimiento",
            command=self.guardar_retiro_grafico,
            width=180,
            height=42,
            corner_radius=9,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(
            row=7,
            column=1,
            sticky="e",
            padx=(0, 20),
            pady=(16, 24),
        )

    def guardar_retiro_grafico(self):
        try:
            retiro, linea = construir_retiro_grafico(
                self.entrada_fecha_retiro.get(),
                self.selector_socio_retiro.get(),
                self.entrada_monto_retiro.get(),
                self.entrada_observacion_retiro.get(),
                self.selector_tipo_retiro.get(),
            )
        except ValueError as error:
            messagebox.showerror(
                "Datos inválidos",
                str(error),
                parent=self,
            )
            return

        socio = Socios.obtener_socio(retiro["socio_id"])
        if not messagebox.askyesno(
            "Confirmar movimiento",
            (
                f"Fecha: {retiro['fecha']}\n"
                f"Socio: {socio['nombre']}\n"
                f"Tipo: {retiro['tipo']}\n"
                f"Monto: {monto(retiro['monto'])}\n\n"
                "¿Querés guardar este movimiento?"
            ),
            icon="question",
            parent=self,
        ):
            return

        try:
            lista = leer_datos(Socios.RUTA_RETIROS_SOCIOS)
            lista.append(linea)
            guardar_datos(Socios.RUTA_RETIROS_SOCIOS, lista)
        except OSError as error:
            messagebox.showerror(
                "No se pudo guardar",
                str(error),
                parent=self,
            )
            return

        self.entrada_monto_retiro.delete(0, "end")
        self.entrada_observacion_retiro.delete(0, "end")
        messagebox.showinfo(
            "Movimiento guardado",
            "El movimiento personal fue registrado correctamente.",
            parent=self,
        )

    def construir_resumen_socios(self, master):
        controles = ctk.CTkFrame(
            master,
            fg_color=COLOR_PANEL_SECUNDARIO,
            corner_radius=12,
        )
        controles.pack(fill="x", padx=16, pady=(18, 12))
        controles.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            controles,
            text="Período",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO,
        ).grid(row=0, column=0, padx=(16, 10), pady=16)

        self.entrada_periodo_resumen_socios = ctk.CTkEntry(
            controles,
            placeholder_text="MM-AAAA",
            width=150,
            height=38,
            fg_color=COLOR_PANEL,
            border_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        )
        self.entrada_periodo_resumen_socios.insert(
            0,
            datetime.now().strftime("%m-%Y"),
        )
        self.entrada_periodo_resumen_socios.grid(
            row=0,
            column=1,
            sticky="w",
            pady=16,
        )
        self.entrada_periodo_resumen_socios.bind(
            "<Return>",
            lambda _evento: self.actualizar_resumen_socios(),
        )

        ctk.CTkButton(
            controles,
            text="Calcular resumen",
            command=self.actualizar_resumen_socios,
            width=165,
            height=38,
            corner_radius=9,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(
            row=0,
            column=2,
            padx=16,
            pady=16,
        )

        self.zona_resumen_socios = ctk.CTkFrame(
            master,
            fg_color="transparent",
        )
        self.zona_resumen_socios.pack(
            fill="both",
            expand=True,
            padx=16,
            pady=(0, 18),
        )
        self.actualizar_resumen_socios()

    def actualizar_resumen_socios(self):
        periodo = self.entrada_periodo_resumen_socios.get().strip()
        try:
            fecha_desde, fecha_hasta = limites_periodo_grafico(periodo)
            resumen = Socios.calcular_resumen_periodo(
                fecha_desde.month,
                fecha_desde.year,
            )
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo calcular",
                str(error),
                parent=self,
            )
            return

        self.dibujar_resumen_socios(
            periodo,
            fecha_hasta,
            resumen,
        )

    def dibujar_resumen_socios(self, periodo, fecha_hasta, resumen):
        for widget in self.zona_resumen_socios.winfo_children():
            widget.destroy()

        provisorio = fecha_hasta.date() >= datetime.now().date()
        cabecera = ctk.CTkFrame(
            self.zona_resumen_socios,
            fg_color="transparent",
        )
        cabecera.pack(fill="x", pady=(4, 10))
        cabecera.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            cabecera,
            text=f"Resumen de socios · {periodo}",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            cabecera,
            text=(
                "PROVISORIO · MES EN CURSO"
                if provisorio
                else "CERRADO"
            ),
            height=30,
            corner_radius=8,
            fg_color=(
                ("#FFF0D9", "#4A3215")
                if provisorio
                else ("#DDF7EC", "#153D31")
            ),
            text_color=(
                ("#9B5D05", "#FFD18B")
                if provisorio
                else ("#11704F", "#9CE1C5")
            ),
            font=ctk.CTkFont(size=10, weight="bold"),
        ).grid(row=0, column=1, padx=(16, 0))

        tarjetas = ctk.CTkFrame(
            self.zona_resumen_socios,
            fg_color="transparent",
        )
        tarjetas.pack(fill="x")
        for columna in range(4):
            tarjetas.grid_columnconfigure(
                columna,
                weight=1,
                uniform="resumen_socios",
            )

        datos = [
            (
                "Utilidad del mes",
                resumen["utilidad_mes"],
                (
                    COLOR_VERDE
                    if resumen["utilidad_mes"] >= 0
                    else COLOR_ROJO
                ),
            ),
            (
                "Fondo aplicado",
                resumen["retencion_empresa"],
                "#7B61FF",
            ),
            (
                "Utilidad repartible",
                resumen["utilidad_distribuible"],
                COLOR_VERDE,
            ),
            (
                "Retiros personales",
                sum(
                    socio["retirado"]
                    for socio in resumen["socios"]
                ),
                COLOR_NARANJA,
            ),
        ]
        for indice, (titulo, valor, color) in enumerate(datos):
            tarjeta = ctk.CTkFrame(
                tarjetas,
                fg_color=COLOR_PANEL,
                corner_radius=12,
                border_width=1,
                border_color=COLOR_BORDE,
            )
            tarjeta.grid(
                row=indice // 4,
                column=indice % 4,
                sticky="nsew",
                padx=5,
                pady=5,
            )
            ctk.CTkLabel(
                tarjeta,
                text=titulo,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLOR_TEXTO_SUAVE,
                anchor="w",
            ).pack(fill="x", padx=14, pady=(14, 4))
            ctk.CTkLabel(
                tarjeta,
                text=monto(valor),
                font=ctk.CTkFont(size=17, weight="bold"),
                text_color=color,
                anchor="w",
            ).pack(fill="x", padx=14, pady=(0, 14))

        fondo_nota = (
            "Fondo provisorio: todavía no fue guardado desde el cierre."
            if not resumen["fondo_registrado"]
            else (
                "Fondo ajustado manualmente. "
                f"Cálculo original: {monto(resumen['fondo_calculado'])}."
                if resumen["fondo_modo"] == "MANUAL"
                else "Fondo automático guardado desde el cierre mensual."
            )
        )
        ctk.CTkLabel(
            self.zona_resumen_socios,
            text=fondo_nota,
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=5, pady=(6, 8))

        zona_socios = ctk.CTkFrame(
            self.zona_resumen_socios,
            fg_color="transparent",
        )
        zona_socios.pack(fill="x")
        for columna in range(2):
            zona_socios.grid_columnconfigure(
                columna,
                weight=1,
                uniform="socios",
            )

        for columna, socio in enumerate(resumen["socios"]):
            exceso = socio["saldo"] < 0
            tarjeta = ctk.CTkFrame(
                zona_socios,
                fg_color=COLOR_PANEL,
                corner_radius=14,
                border_width=1,
                border_color=COLOR_BORDE,
            )
            tarjeta.grid(
                row=0,
                column=columna,
                sticky="nsew",
                padx=5,
                pady=5,
            )
            ctk.CTkLabel(
                tarjeta,
                text=(
                    f"{socio['nombre']} · "
                    f"{socio['porcentaje_utilidad']}%"
                ),
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color=COLOR_TEXTO,
                anchor="w",
            ).pack(fill="x", padx=18, pady=(18, 12))

            filas = [
                (
                    "Sueldo liquidado en RR. HH.",
                    socio["sueldo_liquidado"],
                ),
                ("Utilidad asignada", socio["utilidad"]),
                ("Total disponible", socio["total_a_cobrar"]),
                (
                    "Gastos personales",
                    socio["gastos_personales"],
                ),
                (
                    "Inversiones personales",
                    socio["inversiones_personales"],
                ),
                ("Total descontado del saldo", socio["retirado"]),
            ]
            for nombre, valor in filas:
                fila = ctk.CTkFrame(
                    tarjeta,
                    fg_color=COLOR_PANEL_SECUNDARIO,
                    corner_radius=8,
                )
                fila.pack(fill="x", padx=18, pady=3)
                fila.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(
                    fila,
                    text=nombre,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=COLOR_TEXTO_SUAVE,
                ).grid(row=0, column=0, padx=10, pady=8)
                ctk.CTkLabel(
                    fila,
                    text=monto(valor),
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=COLOR_TEXTO,
                ).grid(
                    row=0,
                    column=1,
                    sticky="e",
                    padx=10,
                    pady=8,
                )

            ctk.CTkLabel(
                tarjeta,
                text=(
                    f"EXCESO RETIRADO: {monto(abs(socio['saldo']))}"
                    if exceso
                    else (
                        "SALDO PENDIENTE A FAVOR: "
                        f"{monto(socio['saldo'])}"
                    )
                ),
                height=38,
                corner_radius=9,
                fg_color=(
                    ("#FFE4E4", "#4A2226")
                    if exceso
                    else ("#DDF7EC", "#153D31")
                ),
                text_color=(
                    ("#A82424", "#FFB5B5")
                    if exceso
                    else ("#11704F", "#9CE1C5")
                ),
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(fill="x", padx=18, pady=(12, 18))

        if resumen["utilidad_mes"] < 0:
            ctk.CTkLabel(
                self.zona_resumen_socios,
                text=(
                    "No se distribuye utilidad porque el resultado "
                    "del mes es negativo."
                ),
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_ROJO,
                anchor="w",
            ).pack(fill="x", padx=5, pady=(8, 0))

    def construir_gestion_retiros(self, master):
        controles = ctk.CTkFrame(
            master,
            fg_color=COLOR_PANEL_SECUNDARIO,
            corner_radius=12,
        )
        controles.pack(fill="x", padx=16, pady=(18, 12))
        controles.grid_columnconfigure(6, weight=1)

        ctk.CTkLabel(
            controles,
            text="Período",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO,
        ).grid(row=0, column=0, padx=(16, 8), pady=14)
        self.entrada_periodo_retiros = ctk.CTkEntry(
            controles,
            width=135,
            height=36,
            placeholder_text="MM-AAAA",
            fg_color=COLOR_PANEL,
            border_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        )
        self.entrada_periodo_retiros.insert(
            0,
            datetime.now().strftime("%m-%Y"),
        )
        self.entrada_periodo_retiros.grid(
            row=0,
            column=1,
            pady=14,
        )
        self.entrada_periodo_retiros.bind(
            "<Return>",
            lambda _evento: self.filtrar_retiros_graficos(),
        )

        ctk.CTkLabel(
            controles,
            text="Socio",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO,
        ).grid(row=0, column=2, padx=(18, 8), pady=14)
        self.selector_filtro_socio_retiros = ctk.CTkOptionMenu(
            controles,
            values=["Todos", "Sol", "Rodrigo"],
            width=135,
            height=36,
            fg_color=COLOR_PANEL,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            text_color=COLOR_TEXTO,
            command=lambda _valor: self.filtrar_retiros_graficos(),
        )
        self.selector_filtro_socio_retiros.set("Todos")
        self.selector_filtro_socio_retiros.grid(
            row=0,
            column=3,
            pady=14,
        )

        ctk.CTkLabel(
            controles,
            text="Tipo",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO,
        ).grid(row=0, column=4, padx=(18, 8), pady=14)
        self.selector_filtro_tipo_retiros = ctk.CTkOptionMenu(
            controles,
            values=["Todos", *Socios.TIPOS_MOVIMIENTO_PERSONAL],
            width=170,
            height=36,
            fg_color=COLOR_PANEL,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            text_color=COLOR_TEXTO,
            command=lambda _valor: self.filtrar_retiros_graficos(),
        )
        self.selector_filtro_tipo_retiros.set("Todos")
        self.selector_filtro_tipo_retiros.grid(
            row=0,
            column=5,
            pady=14,
        )

        ctk.CTkButton(
            controles,
            text="Filtrar",
            command=self.filtrar_retiros_graficos,
            width=105,
            height=36,
            corner_radius=8,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(
            row=0,
            column=7,
            padx=16,
            pady=14,
        )

        panel = ctk.CTkFrame(
            master,
            fg_color=COLOR_PANEL,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        panel.pack(
            fill="both",
            expand=True,
            padx=16,
            pady=(0, 18),
        )

        columnas = (
            "fecha",
            "socio",
            "tipo",
            "monto",
            "observacion",
        )
        self.tabla_retiros = ttk.Treeview(
            panel,
            columns=columnas,
            show="headings",
            height=10,
            selectmode="browse",
        )
        configuracion = [
            ("fecha", "Fecha", 120, "center"),
            ("socio", "Socio", 130, "center"),
            ("tipo", "Tipo", 170, "center"),
            ("monto", "Monto", 150, "e"),
            ("observacion", "Observación", 330, "w"),
        ]
        for columna, titulo, ancho, ancla in configuracion:
            self.tabla_retiros.heading(columna, text=titulo)
            self.tabla_retiros.column(
                columna,
                width=ancho,
                minwidth=90,
                anchor=ancla,
                stretch=True,
            )
        self._bind_orden_columnas(
            tabla=self.tabla_retiros,
            clave="retiros",
            titulos={
                "fecha": "Fecha",
                "socio": "Socio",
                "tipo": "Tipo",
                "monto": "Monto",
                "observacion": "Observación",
            },
            tipos={
                "fecha": "fecha",
                "socio": "texto",
                "tipo": "texto",
                "monto": "monto",
                "observacion": "texto",
            },
            campos={},
            resolutores={
                "socio": lambda retiro: (
                    Socios.obtener_socio(retiro.get("socio_id"))
                    or {}
                ).get("nombre", ""),
            },
            atributo_lista="retiros_filtrados",
            callback_actualizar=self._actualizar_tras_orden_retiros,
        )
        self.tabla_retiros.pack(
            fill="both",
            expand=True,
            padx=14,
            pady=(14, 8),
        )
        self.tabla_retiros.bind(
            "<<TreeviewSelect>>",
            self.seleccionar_retiro_tabla,
        )
        self.tabla_retiros.bind(
            "<Double-1>",
            lambda _evento: self.abrir_edicion_retiro(),
        )

        pie = ctk.CTkFrame(panel, fg_color="transparent")
        pie.pack(fill="x", padx=14, pady=(0, 14))
        pie.grid_columnconfigure(2, weight=1)

        self.boton_retiros_anterior = ctk.CTkButton(
            pie,
            text="← Anterior",
            command=lambda: self.cambiar_pagina_retiros(-1),
            width=105,
            height=34,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        )
        self.boton_retiros_anterior.grid(row=0, column=0, padx=(0, 6))
        self.etiqueta_pagina_retiros = ctk.CTkLabel(
            pie,
            text="Página 1 de 1",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.etiqueta_pagina_retiros.grid(row=0, column=1, padx=6)
        self.boton_retiros_siguiente = ctk.CTkButton(
            pie,
            text="Siguiente →",
            command=lambda: self.cambiar_pagina_retiros(1),
            width=105,
            height=34,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        )
        self.boton_retiros_siguiente.grid(row=0, column=2, sticky="w", padx=6)

        self.etiqueta_total_retiros = ctk.CTkLabel(
            pie,
            text="Total filtrado: Gs. 0",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO,
        )
        self.etiqueta_total_retiros.grid(
            row=0,
            column=3,
            padx=(8, 16),
        )

        self.boton_modificar_retiro = ctk.CTkButton(
            pie,
            text="Modificar",
            command=self.abrir_edicion_retiro,
            width=105,
            height=34,
            fg_color=COLOR_NARANJA,
            hover_color="#C77B20",
            state="disabled",
        )
        self.boton_modificar_retiro.grid(row=0, column=4, padx=5)
        self.boton_eliminar_retiro = ctk.CTkButton(
            pie,
            text="Eliminar",
            command=self.eliminar_retiro_grafico,
            width=105,
            height=34,
            fg_color=COLOR_ROJO,
            hover_color="#B63F3F",
            state="disabled",
        )
        self.boton_eliminar_retiro.grid(row=0, column=5, padx=(5, 0))

        self.filtrar_retiros_graficos()

    def filtrar_retiros_graficos(self):
        periodo = self.entrada_periodo_retiros.get().strip()
        try:
            fecha_desde, _ = limites_periodo_grafico(periodo)
        except ValueError as error:
            messagebox.showerror(
                "Período inválido",
                str(error),
                parent=self,
            )
            return

        socio_nombre = self.selector_filtro_socio_retiros.get()
        tipo = self.selector_filtro_tipo_retiros.get()
        socio_id = None
        if socio_nombre != "Todos":
            socio_id = next(
                socio["id"]
                for socio in Socios.SOCIOS
                if socio["nombre"] == socio_nombre
            )

        try:
            retiros = Socios.retiros_del_periodo(
                fecha_desde.month,
                fecha_desde.year,
            )
        except OSError as error:
            messagebox.showerror(
                "No se pudieron leer los retiros",
                str(error),
                parent=self,
            )
            return

        self.retiros_filtrados = [
            item
            for item in retiros
            if (
                (socio_id is None or item[1]["socio_id"] == socio_id)
                and (tipo == "Todos" or item[1]["tipo"] == tipo)
            )
        ]
        self.pagina_retiros = 0
        self._reaplicar_orden_tabla("retiros")
        self.dibujar_tabla_retiros()

    def _actualizar_tras_orden_retiros(self):
        self.pagina_retiros = 0
        self.dibujar_tabla_retiros()

    def dibujar_tabla_retiros(self):
        for item in self.tabla_retiros.get_children():
            self.tabla_retiros.delete(item)

        total_paginas = max(
            1,
            (
                len(self.retiros_filtrados)
                + RETIROS_POR_PAGINA
                - 1
            )
            // RETIROS_POR_PAGINA,
        )
        self.pagina_retiros = min(
            self.pagina_retiros,
            total_paginas - 1,
        )
        inicio = self.pagina_retiros * RETIROS_POR_PAGINA
        fin = inicio + RETIROS_POR_PAGINA

        for posicion, retiro in self.retiros_filtrados[inicio:fin]:
            socio = Socios.obtener_socio(retiro["socio_id"])
            self.tabla_retiros.insert(
                "",
                "end",
                iid=str(posicion),
                values=(
                    retiro["fecha"],
                    socio["nombre"],
                    retiro["tipo"],
                    monto(retiro["monto"]),
                    retiro["observacion"],
                ),
            )

        self.etiqueta_pagina_retiros.configure(
            text=(
                f"Página {self.pagina_retiros + 1} "
                f"de {total_paginas}"
            )
        )
        self.etiqueta_total_retiros.configure(
            text=(
                "Total filtrado: "
                + monto(
                    sum(
                        retiro["monto"]
                        for _, retiro in self.retiros_filtrados
                    )
                )
            )
        )
        self.boton_retiros_anterior.configure(
            state=(
                "normal"
                if self.pagina_retiros > 0
                else "disabled"
            )
        )
        self.boton_retiros_siguiente.configure(
            state=(
                "normal"
                if self.pagina_retiros < total_paginas - 1
                else "disabled"
            )
        )
        self.posicion_retiro_seleccionado = None
        self.boton_modificar_retiro.configure(state="disabled")
        self.boton_eliminar_retiro.configure(state="disabled")

    def cambiar_pagina_retiros(self, cambio):
        self.pagina_retiros += cambio
        self.dibujar_tabla_retiros()

    def seleccionar_retiro_tabla(self, _evento=None):
        seleccion = self.tabla_retiros.selection()
        if not seleccion:
            return
        self.posicion_retiro_seleccionado = int(seleccion[0])
        self.boton_modificar_retiro.configure(state="normal")
        self.boton_eliminar_retiro.configure(state="normal")

    def obtener_retiro_seleccionado(self):
        posicion = self.posicion_retiro_seleccionado
        if posicion is None:
            return None
        for posicion_real, retiro in Socios.obtener_retiros_validos():
            if posicion_real == posicion:
                return posicion_real, retiro
        return None

    def abrir_edicion_retiro(self):
        seleccionado = self.obtener_retiro_seleccionado()
        if seleccionado is None:
            messagebox.showwarning(
                "Seleccioná un retiro",
                "Elegí una fila de la tabla para modificarla.",
                parent=self,
            )
            return
        posicion, retiro = seleccionado
        socio = Socios.obtener_socio(retiro["socio_id"])

        ventana = ctk.CTkToplevel(self)
        self.habilitar_navegacion_tab(ventana)
        ventana.title("Modificar retiro")
        ventana.geometry("560x500")
        ventana.resizable(False, False)
        ventana.transient(self)
        ventana.grab_set()
        ventana.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            ventana,
            text="Modificar retiro",
            font=ctk.CTkFont(size=21, weight="bold"),
            text_color=COLOR_TEXTO,
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            padx=24,
            pady=(24, 18),
        )

        campos = {}
        for fila, (nombre, valor) in enumerate(
            [
                ("Fecha", retiro["fecha"]),
                ("Monto", str(retiro["monto"])),
                ("Observación", retiro["observacion"]),
            ],
            start=1,
        ):
            ctk.CTkLabel(
                ventana,
                text=nombre,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXTO,
            ).grid(
                row=fila,
                column=0,
                sticky="w",
                padx=(24, 12),
                pady=8,
            )
            entrada = ctk.CTkEntry(
                ventana,
                height=38,
                fg_color=COLOR_PANEL_SECUNDARIO,
                border_color=COLOR_BORDE,
                text_color=COLOR_TEXTO,
            )
            entrada.insert(0, valor)
            entrada.grid(
                row=fila,
                column=1,
                sticky="ew",
                padx=(0, 24),
                pady=8,
            )
            campos[nombre] = entrada

        ctk.CTkLabel(
            ventana,
            text="Socio",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO,
        ).grid(
            row=4,
            column=0,
            sticky="w",
            padx=(24, 12),
            pady=8,
        )
        selector = ctk.CTkOptionMenu(
            ventana,
            values=[item["nombre"] for item in Socios.SOCIOS],
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            text_color=COLOR_TEXTO,
        )
        selector.set(socio["nombre"])
        selector.grid(
            row=4,
            column=1,
            sticky="ew",
            padx=(0, 24),
            pady=8,
        )

        ctk.CTkLabel(
            ventana,
            text="Tipo",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO,
        ).grid(
            row=5,
            column=0,
            sticky="w",
            padx=(24, 12),
            pady=8,
        )
        selector_tipo = ctk.CTkOptionMenu(
            ventana,
            values=Socios.TIPOS_MOVIMIENTO_PERSONAL,
            fg_color=COLOR_PANEL_SECUNDARIO,
            button_color=COLOR_PRIMARIO,
            button_hover_color=COLOR_PRIMARIO_HOVER,
            text_color=COLOR_TEXTO,
        )
        selector_tipo.set(retiro["tipo"])
        selector_tipo.grid(
            row=5,
            column=1,
            sticky="ew",
            padx=(0, 24),
            pady=8,
        )

        def guardar_cambios():
            try:
                _, _linea_temporal = construir_retiro_grafico(
                    campos["Fecha"].get(),
                    selector.get(),
                    campos["Monto"].get(),
                    campos["Observación"].get(),
                    selector_tipo.get(),
                )
                socio_actualizado = next(
                    item
                    for item in Socios.SOCIOS
                    if item["nombre"] == selector.get()
                )
                actualizado = {
                    **retiro,
                    "fecha": campos["Fecha"].get().strip(),
                    "socio_id": socio_actualizado["id"],
                    "monto": convertir_monto_grafico(
                        campos["Monto"].get()
                    ),
                    "tipo": selector_tipo.get(),
                    "observacion": (
                        Socios.limpiar_texto(
                            campos["Observación"].get()
                        )
                        or "-"
                    ),
                }
                lista = leer_datos(Socios.RUTA_RETIROS_SOCIOS)
                lista[posicion] = Socios.crear_linea_retiro(actualizado)
                guardar_datos(Socios.RUTA_RETIROS_SOCIOS, lista)
            except (ValueError, OSError) as error:
                messagebox.showerror(
                    "No se pudo modificar",
                    str(error),
                    parent=ventana,
                )
                return
            ventana.destroy()
            self.filtrar_retiros_graficos()
            messagebox.showinfo(
                "Retiro modificado",
                "Los cambios quedaron guardados correctamente.",
                parent=self,
            )

        ctk.CTkButton(
            ventana,
            text="Guardar cambios",
            command=guardar_cambios,
            height=40,
            fg_color=COLOR_VERDE,
            hover_color="#12835B",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(
            row=6,
            column=1,
            sticky="e",
            padx=24,
            pady=(22, 24),
        )

    def eliminar_retiro_grafico(self):
        seleccionado = self.obtener_retiro_seleccionado()
        if seleccionado is None:
            return
        posicion, retiro = seleccionado
        socio = Socios.obtener_socio(retiro["socio_id"])
        if not messagebox.askyesno(
            "Eliminar retiro",
            (
                f"Fecha: {retiro['fecha']}\n"
                f"Socio: {socio['nombre']}\n"
                f"Tipo: {retiro['tipo']}\n"
                f"Monto: {monto(retiro['monto'])}\n\n"
                "¿Querés eliminar definitivamente este retiro?"
            ),
            icon="warning",
            parent=self,
        ):
            return
        try:
            lista = leer_datos(Socios.RUTA_RETIROS_SOCIOS)
            lista.pop(posicion)
            guardar_datos(Socios.RUTA_RETIROS_SOCIOS, lista)
        except (OSError, IndexError) as error:
            messagebox.showerror(
                "No se pudo eliminar",
                str(error),
                parent=self,
            )
            return
        self.filtrar_retiros_graficos()
        messagebox.showinfo(
            "Retiro eliminado",
            "El retiro fue eliminado correctamente.",
            parent=self,
        )

    def construir_fondo_estabilidad(self, master):
        resumen = ctk.CTkFrame(
            master,
            fg_color="transparent",
        )
        resumen.pack(fill="x", padx=16, pady=(18, 10))
        resumen.grid_columnconfigure(0, weight=1)
        resumen.grid_columnconfigure(1, weight=1)

        self.tarjeta_fondo_acumulado = TarjetaIndicador(
            resumen,
            "Fondo acumulado",
            "Gs. 0",
            "#7B61FF",
            "Suma de los montos mensuales aplicados",
        )
        self.tarjeta_fondo_acumulado.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 6),
        )
        self.tarjeta_meses_fondo = TarjetaIndicador(
            resumen,
            "Meses registrados",
            "0",
            COLOR_PRIMARIO,
            "Cierres mensuales guardados",
        )
        self.tarjeta_meses_fondo.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(6, 0),
        )

        aviso = ctk.CTkFrame(
            master,
            fg_color=("#FFF7E8", "#3B2C16"),
            corner_radius=10,
            border_width=1,
            border_color=("#F2D49B", "#684B20"),
        )
        aviso.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkLabel(
            aviso,
            text=(
                "Podés ajustar manualmente un mes sin superar su "
                "utilidad positiva. Un registro MANUAL se conserva al "
                "volver a guardar el cierre; también puede restaurarse "
                "al cálculo automático."
            ),
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXTO,
            anchor="w",
            justify="left",
            wraplength=830,
        ).pack(fill="x", padx=14, pady=11)

        panel = ctk.CTkFrame(
            master,
            fg_color=COLOR_PANEL,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDE,
        )
        panel.pack(
            fill="both",
            expand=True,
            padx=16,
            pady=(0, 18),
        )

        columnas = (
            "periodo",
            "calculado",
            "aplicado",
            "modo",
            "observacion",
        )
        self.tabla_fondos = ttk.Treeview(
            panel,
            columns=columnas,
            show="headings",
            height=10,
            selectmode="browse",
        )
        configuracion = [
            ("periodo", "Período", 110, "center"),
            ("calculado", "Calculado", 145, "e"),
            ("aplicado", "Aplicado", 145, "e"),
            ("modo", "Modo", 115, "center"),
            ("observacion", "Observación", 340, "w"),
        ]
        for columna, titulo, ancho, ancla in configuracion:
            self.tabla_fondos.heading(columna, text=titulo)
            self.tabla_fondos.column(
                columna,
                width=ancho,
                minwidth=85,
                anchor=ancla,
                stretch=True,
            )
        self._bind_orden_columnas(
            tabla=self.tabla_fondos,
            clave="fondos",
            titulos={
                "periodo": "Período",
                "calculado": "Calculado",
                "aplicado": "Aplicado",
                "modo": "Modo",
                "observacion": "Observación",
            },
            tipos={
                "periodo": "periodo",
                "calculado": "monto",
                "aplicado": "monto",
                "modo": "texto",
                "observacion": "texto",
            },
            campos={
                "calculado": "monto_calculado",
                "aplicado": "monto_aplicado",
            },
            atributo_lista="fondos_filtrados",
            callback_actualizar=self._actualizar_tras_orden_fondos,
        )
        self.tabla_fondos.pack(
            fill="both",
            expand=True,
            padx=14,
            pady=(14, 8),
        )
        self.tabla_fondos.bind(
            "<<TreeviewSelect>>",
            self.seleccionar_fondo_tabla,
        )
        self.tabla_fondos.bind(
            "<Double-1>",
            lambda _evento: self.abrir_edicion_fondo(),
        )

        pie = ctk.CTkFrame(panel, fg_color="transparent")
        pie.pack(fill="x", padx=14, pady=(0, 14))
        pie.grid_columnconfigure(2, weight=1)

        self.boton_fondos_anterior = ctk.CTkButton(
            pie,
            text="← Anterior",
            command=lambda: self.cambiar_pagina_fondos(-1),
            width=105,
            height=34,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        )
        self.boton_fondos_anterior.grid(row=0, column=0, padx=(0, 6))
        self.etiqueta_pagina_fondos = ctk.CTkLabel(
            pie,
            text="Página 1 de 1",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.etiqueta_pagina_fondos.grid(row=0, column=1, padx=6)
        self.boton_fondos_siguiente = ctk.CTkButton(
            pie,
            text="Siguiente →",
            command=lambda: self.cambiar_pagina_fondos(1),
            width=105,
            height=34,
            fg_color=COLOR_PANEL_SECUNDARIO,
            hover_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        )
        self.boton_fondos_siguiente.grid(row=0, column=2, sticky="w", padx=6)

        self.boton_modificar_fondo = ctk.CTkButton(
            pie,
            text="Ajustar monto",
            command=self.abrir_edicion_fondo,
            width=125,
            height=34,
            fg_color=COLOR_NARANJA,
            hover_color="#C77B20",
            state="disabled",
        )
        self.boton_modificar_fondo.grid(row=0, column=3, padx=5)
        self.boton_restaurar_fondo = ctk.CTkButton(
            pie,
            text="Restaurar automático",
            command=self.restaurar_fondo_grafico,
            width=155,
            height=34,
            fg_color=COLOR_PRIMARIO,
            hover_color=COLOR_PRIMARIO_HOVER,
            state="disabled",
        )
        self.boton_restaurar_fondo.grid(row=0, column=4, padx=(5, 0))

        self.actualizar_fondos_graficos()

    def _actualizar_tras_orden_fondos(self):
        self.pagina_fondos = 0
        self.dibujar_tabla_fondos()

    def actualizar_fondos_graficos(self):
        try:
            self.fondos_filtrados = Socios.ordenar_registros_fondo()
        except (OSError, ValueError) as error:
            messagebox.showerror(
                "No se pudo leer el fondo",
                str(error),
                parent=self,
            )
            return
        self.pagina_fondos = 0
        self._reaplicar_orden_tabla("fondos")
        self.dibujar_tabla_fondos()

    def dibujar_tabla_fondos(self):
        for item in self.tabla_fondos.get_children():
            self.tabla_fondos.delete(item)

        total_paginas = max(
            1,
            (
                len(self.fondos_filtrados)
                + FONDOS_POR_PAGINA
                - 1
            )
            // FONDOS_POR_PAGINA,
        )
        self.pagina_fondos = min(
            self.pagina_fondos,
            total_paginas - 1,
        )
        inicio = self.pagina_fondos * FONDOS_POR_PAGINA
        fin = inicio + FONDOS_POR_PAGINA

        for posicion, registro in self.fondos_filtrados[inicio:fin]:
            self.tabla_fondos.insert(
                "",
                "end",
                iid=str(posicion),
                values=(
                    registro["periodo"],
                    monto(registro["monto_calculado"]),
                    monto(registro["monto_aplicado"]),
                    registro["modo"],
                    registro["observacion"],
                ),
            )

        total = sum(
            registro["monto_aplicado"]
            for _, registro in self.fondos_filtrados
        )
        self.tarjeta_fondo_acumulado.etiqueta_valor.configure(
            text=monto(total)
        )
        self.tarjeta_meses_fondo.etiqueta_valor.configure(
            text=str(len(self.fondos_filtrados))
        )
        self.etiqueta_pagina_fondos.configure(
            text=(
                f"Página {self.pagina_fondos + 1} "
                f"de {total_paginas}"
            )
        )
        self.boton_fondos_anterior.configure(
            state=(
                "normal"
                if self.pagina_fondos > 0
                else "disabled"
            )
        )
        self.boton_fondos_siguiente.configure(
            state=(
                "normal"
                if self.pagina_fondos < total_paginas - 1
                else "disabled"
            )
        )
        self.posicion_fondo_seleccionado = None
        self.boton_modificar_fondo.configure(state="disabled")
        self.boton_restaurar_fondo.configure(state="disabled")

    def cambiar_pagina_fondos(self, cambio):
        self.pagina_fondos += cambio
        self.dibujar_tabla_fondos()

    def seleccionar_fondo_tabla(self, _evento=None):
        seleccion = self.tabla_fondos.selection()
        if not seleccion:
            return
        self.posicion_fondo_seleccionado = int(seleccion[0])
        seleccionado = self.obtener_fondo_seleccionado()
        self.boton_modificar_fondo.configure(state="normal")
        self.boton_restaurar_fondo.configure(
            state=(
                "normal"
                if (
                    seleccionado is not None
                    and seleccionado[1]["modo"] == "MANUAL"
                )
                else "disabled"
            )
        )

    def obtener_fondo_seleccionado(self):
        posicion = self.posicion_fondo_seleccionado
        if posicion is None:
            return None
        for posicion_real, registro in Movimientos.obtener_registros_fondo():
            if posicion_real == posicion:
                return posicion_real, registro
        return None

    def abrir_edicion_fondo(self):
        seleccionado = self.obtener_fondo_seleccionado()
        if seleccionado is None:
            messagebox.showwarning(
                "Seleccioná un período",
                "Elegí un registro del fondo para modificarlo.",
                parent=self,
            )
            return
        posicion, registro = seleccionado
        mes, anio = [
            int(parte)
            for parte in registro["periodo"].split("-")
        ]
        try:
            resumen = Socios.calcular_resumen_periodo(mes, anio)
        except (ValueError, OSError) as error:
            messagebox.showerror(
                "No se pudo calcular el límite",
                str(error),
                parent=self,
            )
            return
        limite = max(resumen["resultado_despues_sueldos"], 0)

        ventana = ctk.CTkToplevel(self)
        self.habilitar_navegacion_tab(ventana)
        ventana.title("Ajustar fondo de estabilidad")
        ventana.geometry("590x420")
        ventana.resizable(False, False)
        ventana.transient(self)
        ventana.grab_set()
        ventana.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            ventana,
            text=f"Ajustar fondo · {registro['periodo']}",
            font=ctk.CTkFont(size=21, weight="bold"),
            text_color=COLOR_TEXTO,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=24,
            pady=(24, 8),
        )
        ctk.CTkLabel(
            ventana,
            text=(
                f"Cálculo automático: {monto(registro['monto_calculado'])}\n"
                f"Utilidad positiva disponible: {monto(limite)}"
            ),
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXTO_SUAVE,
            justify="left",
            anchor="w",
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=24,
            pady=(0, 18),
        )

        ctk.CTkLabel(
            ventana,
            text="Monto aplicado",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO,
        ).grid(
            row=2,
            column=0,
            sticky="w",
            padx=(24, 12),
            pady=8,
        )
        entrada_monto = ctk.CTkEntry(
            ventana,
            height=38,
            fg_color=COLOR_PANEL_SECUNDARIO,
            border_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        )
        entrada_monto.insert(0, str(registro["monto_aplicado"]))
        entrada_monto.grid(
            row=2,
            column=1,
            sticky="ew",
            padx=(0, 24),
            pady=8,
        )

        ctk.CTkLabel(
            ventana,
            text="Motivo del ajuste",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXTO,
        ).grid(
            row=3,
            column=0,
            sticky="w",
            padx=(24, 12),
            pady=8,
        )
        entrada_observacion = ctk.CTkEntry(
            ventana,
            height=38,
            fg_color=COLOR_PANEL_SECUNDARIO,
            border_color=COLOR_BORDE,
            text_color=COLOR_TEXTO,
        )
        entrada_observacion.insert(0, registro["observacion"])
        entrada_observacion.grid(
            row=3,
            column=1,
            sticky="ew",
            padx=(0, 24),
            pady=8,
        )

        def guardar_ajuste():
            try:
                nuevo_monto = convertir_monto_no_negativo_grafico(
                    entrada_monto.get()
                )
                if nuevo_monto > limite:
                    raise ValueError(
                        "El fondo no puede superar la utilidad positiva "
                        f"disponible: {monto(limite)}."
                    )
                observacion = (
                    Socios.limpiar_texto(entrada_observacion.get())
                    or "Ajustado manualmente"
                )
                actualizado = {
                    **registro,
                    "monto_aplicado": nuevo_monto,
                    "modo": "MANUAL",
                    "observacion": observacion,
                }
                lista = leer_datos(
                    Movimientos.RUTA_FONDO_ESTABILIDAD
                )
                lista[posicion] = Movimientos.crear_linea_fondo(
                    actualizado
                )
                guardar_datos(
                    Movimientos.RUTA_FONDO_ESTABILIDAD,
                    lista,
                )
            except (ValueError, OSError, IndexError) as error:
                messagebox.showerror(
                    "No se pudo guardar",
                    str(error),
                    parent=ventana,
                )
                return
            ventana.destroy()
            self.actualizar_fondos_graficos()
            messagebox.showinfo(
                "Fondo actualizado",
                "El monto quedó guardado como ajuste MANUAL.",
                parent=self,
            )

        ctk.CTkButton(
            ventana,
            text="Guardar ajuste",
            command=guardar_ajuste,
            height=40,
            fg_color=COLOR_NARANJA,
            hover_color="#C77B20",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(
            row=4,
            column=1,
            sticky="e",
            padx=24,
            pady=(22, 24),
        )

    def restaurar_fondo_grafico(self):
        seleccionado = self.obtener_fondo_seleccionado()
        if seleccionado is None:
            return
        posicion, registro = seleccionado
        if registro["modo"] != "MANUAL":
            return
        if not messagebox.askyesno(
            "Restaurar cálculo automático",
            (
                f"El fondo de {registro['periodo']} volverá a "
                f"{monto(registro['monto_calculado'])}.\n\n"
                "¿Querés continuar?"
            ),
            icon="question",
            parent=self,
        ):
            return
        actualizado = {
            **registro,
            "monto_aplicado": registro["monto_calculado"],
            "modo": "AUTOMATICO",
            "observacion": "Restaurado al cálculo automático",
        }
        try:
            lista = leer_datos(Movimientos.RUTA_FONDO_ESTABILIDAD)
            lista[posicion] = Movimientos.crear_linea_fondo(actualizado)
            guardar_datos(Movimientos.RUTA_FONDO_ESTABILIDAD, lista)
        except (OSError, IndexError) as error:
            messagebox.showerror(
                "No se pudo restaurar",
                str(error),
                parent=self,
            )
            return
        self.actualizar_fondos_graficos()
        messagebox.showinfo(
            "Cálculo restaurado",
            "El fondo volvió al cálculo automático.",
            parent=self,
        )

    def abrir_consola(self):
        if sys.platform != "win32":
            messagebox.showinfo(
                "Versión por consola",
                "Abrí una terminal en PX-Core y ejecutá: python main.py",
                parent=self,
            )
            return

        try:
            subprocess.Popen(
                [sys.executable, str(BASE_DIR / "main.py")],
                cwd=BASE_DIR,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except OSError as error:
            messagebox.showerror(
                "No se pudo abrir la consola",
                str(error),
                parent=self,
            )


def iniciar():
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    aplicacion = AplicacionPXCore()
    aplicacion.mainloop()


if __name__ == "__main__":
    iniciar()
