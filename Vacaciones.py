"""Lógica y persistencia del módulo de vacaciones de BC Gestión."""

from calendar import monthrange
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import Funcionarios
from datos import guardar_datos, leer_datos


BASE_DIR = Path(__file__).resolve().parent
RUTA_PERIODOS = BASE_DIR / "Datos" / "vacaciones_periodos.txt"
RUTA_MOVIMIENTOS = BASE_DIR / "Datos" / "vacaciones_movimientos.txt"
# Compatibilidad temporal mientras se migra el módulo
RUTA_REGISTROS = RUTA_MOVIMIENTOS

FORMATO_FECHA = "%d-%m-%Y"

TIPOS_MOVIMIENTO = [
    "Uso",
    "Pago",
    "Ajuste",
]

FECHAS_BASE_MANUALES = {
    "nidia silva": "01-01-2016",
}

CAMPOS_PERIODO = [
    "id",
    "funcionario_cedula",
    "anio",
    "fecha_base_antiguedad",
    "antiguedad",
    "dias_correspondientes",
    "dias_pagados",
    "dias_usados",
    "dias_restantes",
    "sueldo_historico",
    "valor_dia",
    "importe_total",
    "importe_pendiente",
    "fecha_pago",
    "observaciones",
    "fecha_creacion",
]

CAMPOS_MOVIMIENTO = [
    "id",
    "funcionario_cedula",
    "periodo_id",
    "fecha_salida",
    "cantidad_dias",
    "fecha_reincorporacion",
    "tipo",
    "observacion",
    "usuario",
    "fecha",
    "anulado",
]

CAMPOS_PERIODO = [
    "id",
    "funcionario_cedula",
    "periodo_desde",
    "periodo_hasta",
    "fecha_derecho",
    "fecha_limite",
    "dias_generados",
    "fecha_creacion",
]

CAMPOS_REGISTRO = [
    "id",
    "funcionario_cedula",
    "periodo_id",
    "fecha_solicitud",
    "fecha_notificacion",
    "fecha_inicio",
    "fecha_fin",
    "dias",
    "fraccionada",
    "numero_fraccion",
    "salario_base",
    "monto_pagado",
    "fecha_pago",
    "fecha_reop",
    "referencia_reop",
    "estado",
    "usuario",
    "fecha_creacion",
    "fecha_modificacion",
    "motivo_modificacion",
    "observaciones",
    "anulado",
]


def convertir_fecha(valor):
    if isinstance(valor, datetime):
        return valor
    return datetime.strptime(str(valor).strip(), FORMATO_FECHA)


def formatear_fecha(fecha):
    return fecha.strftime(FORMATO_FECHA)


def limpiar_texto(valor):
    return str(valor or "").replace("|", "/").replace("\n", " ").strip()

def normalizar_nombre(valor):
    return " ".join(
        limpiar_texto(valor).lower().split()
    )


def obtener_fecha_base_antiguedad(funcionario):
    nombre = normalizar_nombre(funcionario.get("nombre", ""))

    if nombre in FECHAS_BASE_MANUALES:
        return FECHAS_BASE_MANUALES[nombre]

    return limpiar_texto(funcionario.get("fecha_ingreso", ""))


def sumar_anios(fecha, cantidad):
    try:
        return fecha.replace(year=fecha.year + cantidad)
    except ValueError:
        return fecha.replace(
            year=fecha.year + cantidad,
            month=2,
            day=28,
        )


def sumar_meses(fecha, cantidad):
    indice = fecha.month - 1 + cantidad
    anio = fecha.year + indice // 12
    mes = indice % 12 + 1
    dia = min(fecha.day, monthrange(anio, mes)[1])
    return fecha.replace(year=anio, month=mes, day=dia)


def antiguedad_en_anios(fecha_ingreso, fecha_referencia=None):
    ingreso = convertir_fecha(fecha_ingreso)
    referencia = (
        convertir_fecha(fecha_referencia)
        if fecha_referencia is not None
        else datetime.now()
    )

    if referencia < ingreso:
        return 0

    anios = referencia.year - ingreso.year
    aniversario = sumar_anios(ingreso, anios)

    if referencia < aniversario:
        anios -= 1

    return max(anios, 0)


def dias_correspondientes(antiguedad):
    if antiguedad <= 5:
        return 12
    if antiguedad <= 10:
        return 18
    return 30


def obtener_funcionarios(estado=None):
    resultado = []

    for linea in Funcionarios.obtener_funcionarios_validos():
        datos = Funcionarios.separar_funcionario(linea)

        if datos is None:
            continue

        if estado and datos["estado"].lower() != estado.lower():
            continue

        resultado.append(datos)

    resultado.sort(
        key=lambda dato: (
            dato["unidad"].lower(),
            dato["nombre"].lower(),
        )
    )
    return resultado


def obtener_funcionario(cedula):
    cedula_buscada = str(cedula).strip().lower()

    for datos in obtener_funcionarios():
        if datos["cedula"].strip().lower() == cedula_buscada:
            return datos

    return None


def crear_linea(datos, campos):
    return " | ".join(
        limpiar_texto(datos.get(campo, ""))
        for campo in campos
    )


def separar_linea(linea, campos):
    partes = [parte.strip() for parte in linea.split("|")]

    if len(partes) != len(campos):
        return None

    return dict(zip(campos, partes))


def crear_linea_periodo(datos):
    return crear_linea(datos, CAMPOS_PERIODO)


def separar_periodo(linea):
    datos = separar_linea(linea, CAMPOS_PERIODO)

    if datos is None:
        return None

    try:
        datos["dias_generados"] = int(datos["dias_generados"])
        for campo in [
            "periodo_desde",
            "periodo_hasta",
            "fecha_derecho",
            "fecha_limite",
            "fecha_creacion",
        ]:
            convertir_fecha(datos[campo])
    except (TypeError, ValueError):
        return None

    return datos


def obtener_periodos(funcionario_cedula=None):
    periodos = []

    for linea in leer_datos(RUTA_PERIODOS):
        datos = separar_periodo(linea)

        if datos is None:
            continue

        if (
            funcionario_cedula is not None
            and datos["funcionario_cedula"].lower()
            != str(funcionario_cedula).strip().lower()
        ):
            continue

        periodos.append(datos)

    periodos.sort(
        key=lambda dato: convertir_fecha(dato["fecha_derecho"])
    )
    return periodos


def construir_periodo(funcionario, numero_aniversario):
    ingreso = convertir_fecha(funcionario["fecha_ingreso"])
    desde = sumar_anios(ingreso, numero_aniversario - 1)
    derecho = sumar_anios(ingreso, numero_aniversario)
    hasta = derecho - timedelta(days=1)
    limite = sumar_meses(derecho, 6)
    cedula = limpiar_texto(funcionario["cedula"])

    return {
        "id": f"VACPER-{cedula}-{derecho.year}",
        "funcionario_cedula": cedula,
        "periodo_desde": formatear_fecha(desde),
        "periodo_hasta": formatear_fecha(hasta),
        "fecha_derecho": formatear_fecha(derecho),
        "fecha_limite": formatear_fecha(limite),
        "dias_generados": dias_correspondientes(numero_aniversario),
        "fecha_creacion": formatear_fecha(datetime.now()),
    }


def generar_periodos_funcionario(funcionario, fecha_referencia=None):
    referencia = (
        convertir_fecha(fecha_referencia)
        if fecha_referencia is not None
        else datetime.now()
    )
    ingreso = convertir_fecha(funcionario["fecha_ingreso"])

    if ingreso > referencia:
        return []

    cantidad = antiguedad_en_anios(ingreso, referencia)
    existentes = {
        periodo["id"]
        for periodo in obtener_periodos(funcionario["cedula"])
    }
    nuevos = []

    for numero in range(1, cantidad + 1):
        periodo = construir_periodo(funcionario, numero)

        if periodo["id"] not in existentes:
            nuevos.append(periodo)
            existentes.add(periodo["id"])

    if nuevos:
        lineas = leer_datos(RUTA_PERIODOS)
        lineas.extend(crear_linea_periodo(dato) for dato in nuevos)
        guardar_datos(RUTA_PERIODOS, lineas)

    return nuevos


def generar_periodos_pendientes(fecha_referencia=None):
    nuevos = []

    for funcionario in obtener_funcionarios():
        nuevos.extend(
            generar_periodos_funcionario(
                funcionario,
                fecha_referencia,
            )
        )

    return nuevos


def crear_linea_registro(datos):
    return crear_linea(datos, CAMPOS_REGISTRO)


def separar_registro(linea):
    datos = separar_linea(linea, CAMPOS_REGISTRO)

    if datos is None:
        return None

    try:
        for campo in [
            "dias",
            "numero_fraccion",
            "salario_base",
            "monto_pagado",
        ]:
            datos[campo] = int(datos[campo])

        for campo in [
            "fecha_inicio",
            "fecha_fin",
            "fecha_creacion",
        ]:
            convertir_fecha(datos[campo])

        for campo in [
            "fecha_solicitud",
            "fecha_notificacion",
            "fecha_pago",
            "fecha_reop",
            "fecha_modificacion",
        ]:
            if datos[campo]:
                convertir_fecha(datos[campo])
    except (TypeError, ValueError):
        return None

    datos["fraccionada"] = datos["fraccionada"] == "Sí"
    datos["anulado"] = datos["anulado"] == "Sí"
    return datos


def obtener_registros(
    funcionario_cedula=None,
    periodo_id=None,
    incluir_anulados=False,
):
    registros = []

    for linea in leer_datos(RUTA_REGISTROS):
        datos = separar_registro(linea)

        if datos is None:
            continue

        if not incluir_anulados and datos["anulado"]:
            continue

        if (
            funcionario_cedula is not None
            and datos["funcionario_cedula"].lower()
            != str(funcionario_cedula).strip().lower()
        ):
            continue

        if periodo_id is not None and datos["periodo_id"] != periodo_id:
            continue

        registros.append(datos)

    registros.sort(
        key=lambda dato: convertir_fecha(dato["fecha_inicio"]),
        reverse=True,
    )
    return registros


def obtener_periodo(periodo_id):
    for periodo in obtener_periodos():
        if periodo["id"] == periodo_id:
            return periodo
    return None


def dias_utilizados(periodo_id):
    return sum(
        registro["dias"]
        for registro in obtener_registros(periodo_id=periodo_id)
        if registro["estado"] in {
            "Programada",
            "En curso",
            "Utilizada",
        }
    )


def dias_pendientes(periodo):
    return max(
        periodo["dias_generados"] - dias_utilizados(periodo["id"]),
        0,
    )


def obtener_feriados():
    feriados = set()

    for linea in leer_datos(RUTA_FERIADOS):
        fecha_texto = linea.split("|", 1)[0].strip()

        try:
            feriados.add(convertir_fecha(fecha_texto).date())
        except ValueError:
            continue

    return feriados


def es_dia_habil(fecha, trabaja_sabado=True, feriados=None):
    dia = convertir_fecha(fecha)
    feriados = feriados if feriados is not None else obtener_feriados()

    if dia.date() in feriados:
        return False

    if dia.weekday() == 6:
        return False

    if dia.weekday() == 5 and not trabaja_sabado:
        return False

    return True


def contar_dias_habiles(
    fecha_inicio,
    fecha_fin,
    trabaja_sabado=True,
):
    inicio = convertir_fecha(fecha_inicio)
    fin = convertir_fecha(fecha_fin)

    if fin < inicio:
        raise ValueError(
            "La fecha final no puede ser anterior a la inicial."
        )

    feriados = obtener_feriados()
    cantidad = 0
    actual = inicio

    while actual <= fin:
        if es_dia_habil(actual, trabaja_sabado, feriados):
            cantidad += 1
        actual += timedelta(days=1)

    return cantidad


def calcular_fecha_fin(
    fecha_inicio,
    cantidad_dias,
    trabaja_sabado=True,
):
    inicio = convertir_fecha(fecha_inicio)

    if int(cantidad_dias) <= 0:
        raise ValueError("La cantidad de días debe ser mayor que cero.")

    feriados = obtener_feriados()
    actual = inicio
    contados = 0

    while True:
        if es_dia_habil(actual, trabaja_sabado, feriados):
            contados += 1

            if contados == int(cantidad_dias):
                return actual

        actual += timedelta(days=1)


def calcular_monto_vacaciones(funcionario, dias, fecha_goce):
    dias = int(dias)

    if dias <= 0:
        raise ValueError("La cantidad de días debe ser mayor que cero.")

    sueldo = Funcionarios.calcular_sueldo_funcionario(
        funcionario,
        convertir_fecha(fecha_goce),
    )

    modalidad = funcionario["modalidad"]

    if modalidad == "Mensual":
        monto = round((sueldo / 30) * dias)
    elif modalidad == "Semanal":
        monto = round((sueldo / 6) * dias)
    elif modalidad == "Diario":
        monto = sueldo * dias
    else:
        raise ValueError("La modalidad de pago no es válida.")

    return sueldo, int(monto)


def periodos_superpuestos(
    funcionario_cedula,
    fecha_inicio,
    fecha_fin,
    excluir_id=None,
):
    inicio = convertir_fecha(fecha_inicio)
    fin = convertir_fecha(fecha_fin)

    for registro in obtener_registros(funcionario_cedula):
        if excluir_id and registro["id"] == excluir_id:
            continue

        otro_inicio = convertir_fecha(registro["fecha_inicio"])
        otro_fin = convertir_fecha(registro["fecha_fin"])

        if inicio <= otro_fin and fin >= otro_inicio:
            return True

    return False


def validar_registro(datos, excluir_id=None):
    funcionario = obtener_funcionario(datos["funcionario_cedula"])

    if funcionario is None:
        raise ValueError("El funcionario no existe.")

    periodo = obtener_periodo(datos["periodo_id"])

    if periodo is None:
        raise ValueError("El período de vacaciones no existe.")

    if (
        periodo["funcionario_cedula"].lower()
        != funcionario["cedula"].lower()
    ):
        raise ValueError("El período no corresponde al funcionario.")

    inicio = convertir_fecha(datos["fecha_inicio"])
    fin = convertir_fecha(datos["fecha_fin"])
    dias = int(datos["dias"])

    if fin < inicio:
        raise ValueError(
            "La fecha final no puede ser anterior a la inicial."
        )

    dias_calculados = contar_dias_habiles(
        inicio,
        fin,
        datos.get("trabaja_sabado", True),
    )

    if dias_calculados != dias:
        raise ValueError(
            f"El rango contiene {dias_calculados} días hábiles, "
            f"no {dias}."
        )

    pendientes = dias_pendientes(periodo)

    if excluir_id:
        anterior = next(
            (
                registro
                for registro in obtener_registros(
                    incluir_anulados=True
                )
                if registro["id"] == excluir_id
            ),
            None,
        )
        if anterior and not anterior["anulado"]:
            pendientes += anterior["dias"]

    if dias > pendientes:
        raise ValueError(
            f"El período solamente tiene {pendientes} días pendientes."
        )

    if periodos_superpuestos(
        funcionario["cedula"],
        inicio,
        fin,
        excluir_id,
    ):
        raise ValueError(
            "Las fechas se superponen con otras vacaciones registradas."
        )

    if datos.get("fraccionada") and dias < 6:
        raise ValueError(
            "Una fracción no puede ser inferior a 6 días hábiles."
        )

    return periodo


def obtener_advertencias(datos):
    advertencias = []
    periodo = obtener_periodo(datos["periodo_id"])

    if periodo is None:
        return advertencias

    inicio = convertir_fecha(datos["fecha_inicio"])
    limite = convertir_fecha(periodo["fecha_limite"])
    notificacion = datos.get("fecha_notificacion", "").strip()

    if inicio > limite:
        advertencias.append(
            "Las vacaciones se encuentran fuera del plazo de 6 meses."
        )

    if notificacion:
        anticipacion = (inicio - convertir_fecha(notificacion)).days

        if anticipacion < 15:
            advertencias.append(
                "La notificación tiene menos de 15 días de anticipación."
            )
    else:
        advertencias.append(
            "Falta registrar la fecha de notificación al trabajador."
        )

    if inicio.weekday() != 0:
        advertencias.append(
            "Las vacaciones no comienzan un lunes."
        )

    if datos.get("fraccionada") and int(datos["dias"]) < 6:
        advertencias.append(
            "La fracción es inferior a 6 días hábiles."
        )

    if not datos.get("fecha_pago", "").strip():
        advertencias.append(
            "El pago adelantado todavía no fue registrado."
        )

    if not datos.get("fecha_reop", "").strip():
        advertencias.append(
            "La comunicación al MTESS/REOP está pendiente."
        )

    return advertencias


def registrar_vacaciones(datos):
    ahora = datetime.now()
    datos = dict(datos)
    datos["fraccionada"] = bool(datos.get("fraccionada", False))
    datos["anulado"] = False
    validar_registro(datos)

    registro = {
        "id": f"VAC-{ahora:%Y%m%d}-{uuid4().hex[:8].upper()}",
        "funcionario_cedula": limpiar_texto(
            datos["funcionario_cedula"]
        ),
        "periodo_id": limpiar_texto(datos["periodo_id"]),
        "fecha_solicitud": limpiar_texto(
            datos.get("fecha_solicitud", "")
        ),
        "fecha_notificacion": limpiar_texto(
            datos.get("fecha_notificacion", "")
        ),
        "fecha_inicio": formatear_fecha(
            convertir_fecha(datos["fecha_inicio"])
        ),
        "fecha_fin": formatear_fecha(
            convertir_fecha(datos["fecha_fin"])
        ),
        "dias": int(datos["dias"]),
        "fraccionada": "Sí" if datos["fraccionada"] else "No",
        "numero_fraccion": int(datos.get("numero_fraccion", 0)),
        "salario_base": int(datos.get("salario_base", 0)),
        "monto_pagado": int(datos.get("monto_pagado", 0)),
        "fecha_pago": limpiar_texto(datos.get("fecha_pago", "")),
        "fecha_reop": limpiar_texto(datos.get("fecha_reop", "")),
        "referencia_reop": limpiar_texto(
            datos.get("referencia_reop", "")
        ),
        "estado": limpiar_texto(
            datos.get("estado", "Programada")
        ),
        "usuario": limpiar_texto(
            datos.get("usuario", "Sistema")
        ),
        "fecha_creacion": formatear_fecha(ahora),
        "fecha_modificacion": "",
        "motivo_modificacion": "",
        "observaciones": limpiar_texto(
            datos.get("observaciones", "")
        ),
        "anulado": "No",
    }

    if registro["estado"] not in ESTADOS_REGISTRO:
        raise ValueError("El estado del registro no es válido.")

    lineas = leer_datos(RUTA_REGISTROS)
    lineas.append(crear_linea_registro(registro))
    guardar_datos(RUTA_REGISTROS, lineas)
    return separar_registro(crear_linea_registro(registro))


def anular_registro(registro_id, motivo, usuario="Sistema"):
    motivo = limpiar_texto(motivo)

    if not motivo:
        raise ValueError("Indicá el motivo de anulación.")

    lineas = leer_datos(RUTA_REGISTROS)

    for indice, linea in enumerate(lineas):
        datos = separar_registro(linea)

        if datos is None or datos["id"] != registro_id:
            continue

        if datos["anulado"]:
            raise ValueError("El registro ya está anulado.")

        datos["estado"] = "Anulada"
        datos["anulado"] = "Sí"
        datos["usuario"] = limpiar_texto(usuario)
        datos["fecha_modificacion"] = formatear_fecha(datetime.now())
        datos["motivo_modificacion"] = motivo
        datos["fraccionada"] = (
            "Sí" if datos["fraccionada"] else "No"
        )
        lineas[indice] = crear_linea_registro(datos)
        guardar_datos(RUTA_REGISTROS, lineas)
        return

    raise ValueError("No se encontró el registro de vacaciones.")


def estado_periodo(periodo, fecha_referencia=None):
    hoy = (
        convertir_fecha(fecha_referencia)
        if fecha_referencia is not None
        else datetime.now()
    )
    utilizados = dias_utilizados(periodo["id"])
    pendientes = max(periodo["dias_generados"] - utilizados, 0)
    limite = convertir_fecha(periodo["fecha_limite"])

    if pendientes == 0:
        return "Utilizada"

    registros = obtener_registros(periodo_id=periodo["id"])

    if any(
        registro["estado"] == "Programada"
        for registro in registros
    ) and utilizados < periodo["dias_generados"]:
        return "Programada"

    if registros and utilizados < periodo["dias_generados"]:
        return "Parcialmente utilizada"

    if hoy > limite:
        return "Fuera de plazo"

    if (limite - hoy).days <= 90:
        return "Vencimiento próximo"

    return "Disponible"


def resumen_periodo(periodo, fecha_referencia=None):
    funcionario = obtener_funcionario(
        periodo["funcionario_cedula"]
    )
    utilizados = dias_utilizados(periodo["id"])

    return {
        **periodo,
        "funcionario": funcionario,
        "dias_utilizados": utilizados,
        "dias_pendientes": max(
            periodo["dias_generados"] - utilizados,
            0,
        ),
        "estado": estado_periodo(periodo, fecha_referencia),
    }


def obtener_resumen_general(fecha_referencia=None):
    generar_periodos_pendientes(fecha_referencia)

    return [
        resumen_periodo(periodo, fecha_referencia)
        for periodo in obtener_periodos()
    ]
