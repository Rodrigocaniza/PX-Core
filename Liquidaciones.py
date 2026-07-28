from datetime import datetime, timedelta

from datos import leer_datos, guardar_datos
from Movimientos import formatear_monto

from Funcionarios import (
    RUTA_FUNCIONARIOS,
    separar_funcionario,
    calcular_sueldo_funcionario,
)
from Novedades import (
    RUTA_NOVEDADES,
    separar_novedad,
)


PORCENTAJE_IPS = 9

RUTA_LIQUIDACIONES = (
    RUTA_FUNCIONARIOS.parent
    / "liquidaciones.txt"
)

RUTA_RECIBOS = (
    RUTA_FUNCIONARIOS.parent
    / "recibos_sueldo"
)

NOMBRE_EMPRESA = "BC Inversiones EAS"
RUC_EMPRESA = "80172376-0"
CIUDAD_EMPRESA = "Asunción - Paraguay"

def crear_linea_liquidacion(datos):
    campos = [
        datos["cedula"],
        datos["nombre"],
        datos["periodo"],
        str(datos["dias_liquidados"]),
        str(datos["sueldo_referencia"]),
        str(datos["sueldo_bruto"]),
        str(datos["descuento_ips"]),
        str(datos["neto_cobrar"]),
        datos["tipo_liquidacion"],
        str(datos.get("dias_ausencia", 0)),
        str(datos.get("dias_reposo", 0)),
        str(datos.get("descuento_ausencias", 0)),
        str(datos.get("descuento_reposos", 0)),
        str(datos.get("adelantos", 0)),
        str(datos.get("otros_descuentos", 0)),
        str(datos.get("comisiones", 0)),
    ]

    return " | ".join(campos)


def separar_liquidacion(linea):
    partes = [
        parte.strip()
        for parte in linea.split("|")
    ]

    if len(partes) not in [9, 15, 16]:
        return None

    try:
        liquidacion = {
            "cedula": partes[0],
            "nombre": partes[1],
            "periodo": partes[2],
            "dias_liquidados": int(partes[3]),
            "sueldo_referencia": int(partes[4]),
            "sueldo_bruto": int(partes[5]),
            "descuento_ips": int(partes[6]),
            "neto_cobrar": int(partes[7]),
            "tipo_liquidacion": partes[8],
        }

        if len(partes) in [15, 16]:
            liquidacion.update(
                {
                    "dias_ausencia": int(partes[9]),
                    "dias_reposo": int(partes[10]),
                    "descuento_ausencias": int(partes[11]),
                    "descuento_reposos": int(partes[12]),
                    "adelantos": int(partes[13]),
                    "otros_descuentos": int(partes[14]),
                    "comisiones": (
                        int(partes[15])
                        if len(partes) == 16
                        else 0
                    ),
                }
            )
        else:
            liquidacion.update(
                {
                    "dias_ausencia": 0,
                    "dias_reposo": 0,
                    "descuento_ausencias": 0,
                    "descuento_reposos": 0,
                    "adelantos": 0,
                    "otros_descuentos": 0,
                    "comisiones": 0,
                }
            )

        return liquidacion

    except ValueError:
        return None


def obtener_limites_periodo(fecha_periodo):
    inicio = fecha_periodo.replace(day=1)

    if fecha_periodo.month == 12:
        siguiente = fecha_periodo.replace(
            year=fecha_periodo.year + 1,
            month=1,
            day=1
        )
    else:
        siguiente = fecha_periodo.replace(
            month=fecha_periodo.month + 1,
            day=1
        )

    return inicio, siguiente - timedelta(days=1)


def fechas_del_intervalo(fecha_inicio, fecha_fin):
    actual = fecha_inicio
    fechas = set()

    while actual <= fecha_fin:
        fechas.add(actual.date())
        actual += timedelta(days=1)

    return fechas


def obtener_novedades_del_periodo(cedula, fecha_periodo):
    inicio_periodo, fin_periodo = obtener_limites_periodo(
        fecha_periodo
    )

    ausencias = set()
    reposos = set()
    adelantos = 0
    otros_descuentos = 0
    comisiones = 0
    detalle_comisiones = []
    novedades_encontradas = []

    for linea in leer_datos(RUTA_NOVEDADES):
        novedad = separar_novedad(linea)

        if (
            novedad is None
            or novedad["cedula"] != cedula
        ):
            continue

        try:
            fecha_inicio = datetime.strptime(
                novedad["fecha_inicio"],
                "%d-%m-%Y"
            )
            fecha_fin = datetime.strptime(
                novedad["fecha_fin"],
                "%d-%m-%Y"
            )
        except ValueError:
            continue

        if (
            fecha_fin < inicio_periodo
            or fecha_inicio > fin_periodo
        ):
            continue

        novedades_encontradas.append(novedad)

        inicio_aplicable = max(fecha_inicio, inicio_periodo)
        fin_aplicable = min(fecha_fin, fin_periodo)

        if novedad["tipo"] == "Ausencia":
            ausencias.update(
                fechas_del_intervalo(
                    inicio_aplicable,
                    fin_aplicable
                )
            )

        elif novedad["tipo"] == "Reposo":
            reposos.update(
                fechas_del_intervalo(
                    inicio_aplicable,
                    fin_aplicable
                )
            )

        elif novedad["tipo"] == "Adelanto":
            adelantos += novedad["monto"]

        elif novedad["tipo"] == "Otro descuento":
            otros_descuentos += novedad["monto"]

        elif novedad["tipo"] == "Comisión":
            comisiones += novedad["monto"]
            detalle_comisiones.append(
                {
                    "concepto": novedad["motivo"],
                    "monto": novedad["monto"],
                    "fecha": novedad["fecha_inicio"],
                }
            )

    # Una misma fecha no puede descontarse como reposo y ausencia.
    ausencias -= reposos

    return {
        "dias_ausencia": len(ausencias),
        "dias_reposo": len(reposos),
        "adelantos": adelantos,
        "otros_descuentos": otros_descuentos,
        "comisiones": comisiones,
        "detalle_comisiones": detalle_comisiones,
        "novedades": novedades_encontradas,
    }


def liquidacion_ya_registrada(cedula, periodo):
    lineas = leer_datos(
        RUTA_LIQUIDACIONES
    )

    for linea in lineas:
        liquidacion = separar_liquidacion(linea)

        if liquidacion is None:
            continue

        if (
            liquidacion["cedula"] == cedula
            and liquidacion["periodo"] == periodo
        ):
            return True

    return False

def obtener_funcionarios_activos():
    lineas = leer_datos(
        RUTA_FUNCIONARIOS
    )

    funcionarios = []

    for linea in lineas:
        datos = separar_funcionario(linea)

        if (
            datos is not None
            and datos["estado"] == "Activo"
        ):
            funcionarios.append(datos)

    return funcionarios


def seleccionar_funcionario_activo():
    funcionarios = obtener_funcionarios_activos()

    if len(funcionarios) == 0:
        print()
        print("No hay funcionarios activos registrados.")
        return None

    print()
    print("====================================")
    print("       FUNCIONARIOS ACTIVOS")
    print("====================================")
    print()

    for numero, funcionario in enumerate(
        funcionarios,
        start=1
    ):
        print(
            f"{numero}. "
            f"{funcionario['nombre']} | "
            f"{funcionario['cargo']}"
        )

    print("0. Cancelar")
    print()

    while True:
        opcion = input(
            "Seleccione un funcionario: "
        ).strip()

        if opcion == "0":
            return None

        if not opcion.isdigit():
            print("Ingresá un número válido.")
            continue

        indice = int(opcion) - 1

        if indice < 0 or indice >= len(funcionarios):
            print("La opción seleccionada no existe.")
            continue

        return funcionarios[indice]


def pedir_periodo():
    while True:
        periodo = input(
            "Mes y año de la liquidación "
            "(MM-AAAA) o 0 para cancelar: "
        ).strip()

        if periodo == "0":
            return None

        try:
            fecha_periodo = datetime.strptime(
                periodo,
                "%m-%Y"
            )
        except ValueError:
            print()
            print(
                "Periodo inválido. "
                "Ejemplo correcto: 07-2026"
            )
            continue

        return fecha_periodo


def calcular_descuento_ips(funcionario, sueldo):
    if (
        funcionario["ips"] == "Sí"
        and funcionario["tipo_sueldo"]
        == "Salario mínimo"
    ):
        return sueldo * PORCENTAJE_IPS // 100

    return 0

def ajustar_sueldo_por_fecha_ingreso(
    funcionario,
    fecha_periodo,
    sueldo_mensual
):
    try:
        fecha_ingreso = datetime.strptime(
            funcionario["fecha_ingreso"],
            "%d-%m-%Y"
        )
    except (ValueError, TypeError):
        print()
        print(
            "La fecha de ingreso del funcionario "
            "no es válida."
        )
        return None

    inicio_periodo = fecha_periodo.replace(day=1)

    if (
        fecha_periodo.year < fecha_ingreso.year
        or (
            fecha_periodo.year == fecha_ingreso.year
            and fecha_periodo.month < fecha_ingreso.month
        )
    ):
        print()
        print(
            "No se puede generar esta liquidación."
        )
        print(
            "El funcionario ingresó el:",
            fecha_ingreso.strftime("%d-%m-%Y")
        )
        return None

    ingreso_en_el_periodo = (
        fecha_ingreso.year == inicio_periodo.year
        and fecha_ingreso.month == inicio_periodo.month
    )

    if not ingreso_en_el_periodo:
        return {
            "sueldo_bruto": sueldo_mensual,
            "dias_liquidados": 30,
            "es_proporcional": False,
        }

    dia_ingreso = min(
        fecha_ingreso.day,
        30
    )

    dias_liquidados = 30 - dia_ingreso + 1

    sueldo_proporcional = (
        sueldo_mensual
        * dias_liquidados
        // 30
    )

    return {
        "sueldo_bruto": sueldo_proporcional,
        "dias_liquidados": dias_liquidados,
        "es_proporcional": True,
    }

def generar_liquidacion():
    print()
    print("====================================")
    print("       GENERAR LIQUIDACIÓN")
    print("====================================")
    print()

    funcionario = seleccionar_funcionario_activo()

    if funcionario is None:
        return

    fecha_periodo = pedir_periodo()

    if fecha_periodo is None:
        return

    periodo = fecha_periodo.strftime("%m-%Y")

    if liquidacion_ya_registrada(
        funcionario["cedula"],
        periodo
    ):
        print()
        print(
            "Este funcionario ya tiene una "
            "liquidación guardada para ese periodo."
        )
        return

    sueldo_mensual = calcular_sueldo_funcionario(
        funcionario,
        fecha_periodo
    )

    resultado = ajustar_sueldo_por_fecha_ingreso(
        funcionario,
        fecha_periodo,
        sueldo_mensual
    )

    if resultado is None:
        return

    liquidacion_manual = (
        funcionario["modalidad"] in ("Diario", "Semanal")
    )

    if liquidacion_manual:
        while True:
            valor = input(
                "Monto base total efectivamente liquidado: "
            ).strip().replace(".", "").replace(",", "")

            try:
                monto_base_manual = int(valor)
            except ValueError:
                print("Ingresá un monto válido usando números.")
                continue

            if monto_base_manual <= 0:
                print("El monto debe ser mayor que cero.")
                continue

            break

        sueldo_mensual = monto_base_manual
        sueldo_bruto = monto_base_manual
        dias_liquidados = 0
        es_proporcional = False
    else:
        sueldo_bruto = resultado["sueldo_bruto"]
        dias_liquidados = resultado["dias_liquidados"]
        es_proporcional = resultado["es_proporcional"]

    novedades = obtener_novedades_del_periodo(
        funcionario["cedula"],
        fecha_periodo
    )

    if liquidacion_manual:
        dias_reposo = novedades["dias_reposo"]
        dias_ausencia = novedades["dias_ausencia"]
        descuento_reposos = 0
        descuento_ausencias = 0
    else:
        dias_reposo = min(
            novedades["dias_reposo"],
            dias_liquidados
        )
        dias_disponibles = dias_liquidados - dias_reposo
        dias_ausencia = min(
            novedades["dias_ausencia"],
            dias_disponibles
        )

        valor_dia = sueldo_mensual // 30
        descuento_reposos = valor_dia * dias_reposo
        descuento_ausencias = valor_dia * dias_ausencia

    sueldo_bruto_empresa = max(
        0,
        sueldo_bruto
        - descuento_reposos
        - descuento_ausencias
    )

    descuento_ips = calcular_descuento_ips(
        funcionario,
        sueldo_bruto_empresa
    )

    adelantos = novedades["adelantos"]
    otros_descuentos = novedades["otros_descuentos"]
    comisiones = novedades["comisiones"]

    neto_cobrar = max(
        0,
        sueldo_bruto_empresa
        + comisiones
        - descuento_ips
        - adelantos
        - otros_descuentos
    )

    print()
    print("====================================")
    print("     RESULTADO DE LIQUIDACIÓN")
    print("====================================")
    print()
    print(
        "Funcionario:",
        funcionario["nombre"]
    )
    print(
        "Fecha de ingreso:",
        funcionario["fecha_ingreso"]
    )
    print(
        "Periodo:",
        fecha_periodo.strftime("%m-%Y")
    )
    print(
        "Modalidad:",
        funcionario["modalidad"]
    )
    print(
        "Tipo de sueldo:",
        funcionario["tipo_sueldo"]
    )
    print(
        "Tiene IPS:",
        funcionario["ips"]
    )

    if liquidacion_manual:
        print(
            "Liquidación:",
            "Monto base manual del período"
        )
    elif es_proporcional:
        print(
            "Días liquidados:",
            f"{dias_liquidados} de 30"
        )
        print(
            "Liquidación:",
            "Proporcional por ingreso durante el mes"
        )
    else:
        print(
            "Días liquidados:",
            "30 de 30"
        )
        print(
            "Liquidación:",
            "Mes completo"
        )

    print()
    print(
        (
            "Monto base manual:"
            if liquidacion_manual
            else "Salario mensual de referencia:"
        ),
        formatear_monto(sueldo_mensual),
        "Gs."
    )
    print(
        "Salario bruto antes de novedades:",
        formatear_monto(sueldo_bruto),
        "Gs."
    )

    if dias_ausencia > 0:
        print(
            f"Ausencias ({dias_ausencia} día/s):",
            "-",
            formatear_monto(descuento_ausencias),
            "Gs."
        )

    if dias_reposo > 0:
        print(
            f"Reposos ({dias_reposo} día/s):",
            "-",
            formatear_monto(descuento_reposos),
            "Gs."
        )
        print(
            "Subsidio IPS:",
            "lo cobra el funcionario directamente; "
            "no se suma al pago de la empresa."
        )

    print(
        "Salario bruto pagado por la empresa:",
        formatear_monto(sueldo_bruto_empresa),
        "Gs."
    )

    if comisiones > 0:
        print(
            "Comisiones:",
            "+",
            formatear_monto(comisiones),
            "Gs."
        )

    print(
        f"Descuento IPS ({PORCENTAJE_IPS}%):",
        formatear_monto(descuento_ips),
        "Gs."
    )

    if adelantos > 0:
        print(
            "Adelantos:",
            "-",
            formatear_monto(adelantos),
            "Gs."
        )

    if otros_descuentos > 0:
        print(
            "Otros descuentos:",
            "-",
            formatear_monto(otros_descuentos),
            "Gs."
        )

    print(
        "Neto a cobrar:",
        formatear_monto(neto_cobrar),
        "Gs."
    )

    print()
    print("¿Confirmar y guardar esta liquidación?")
    print("1. Sí")
    print("2. No")
    print()

    while True:
        confirmacion = input(
            "Seleccione una opción: "
        ).strip()

        if confirmacion == "2":
            print()
            print("La liquidación no fue guardada.")
            return

        if confirmacion != "1":
            print("Opción inválida.")
            continue

        break

    if liquidacion_manual:
        tipo_liquidacion = "Monto manual"
    elif es_proporcional:
        tipo_liquidacion = "Proporcional"
    else:
        tipo_liquidacion = "Mes completo"

    datos_liquidacion = {
        "cedula": funcionario["cedula"],
        "nombre": funcionario["nombre"],
        "periodo": periodo,
        "dias_liquidados": dias_liquidados,
        "sueldo_referencia": sueldo_mensual,
        "sueldo_bruto": sueldo_bruto,
        "descuento_ips": descuento_ips,
        "neto_cobrar": neto_cobrar,
        "tipo_liquidacion": tipo_liquidacion,
        "dias_ausencia": dias_ausencia,
        "dias_reposo": dias_reposo,
        "descuento_ausencias": descuento_ausencias,
        "descuento_reposos": descuento_reposos,
        "adelantos": adelantos,
        "otros_descuentos": otros_descuentos,
        "comisiones": comisiones,
    }

    liquidaciones = leer_datos(
        RUTA_LIQUIDACIONES
    )

    liquidaciones.append(
        crear_linea_liquidacion(
            datos_liquidacion
        )
    )

    guardar_datos(
        RUTA_LIQUIDACIONES,
        liquidaciones
    )

    print()
    print("Liquidación guardada correctamente.")

def menu_liquidaciones():
    while True:
        print()
        print("====================================")
        print("          LIQUIDACIONES")
        print("====================================")
        print()
        print("1. Calcular liquidación mensual")
        print("2. Gestionar liquidaciones")
        print("3. Recibos")
        print("0. Volver")
        print()

        opcion = input(
            "Seleccione una opción: "
        ).strip()

        if opcion == "1":
            generar_liquidacion()

        elif opcion == "2":
            menu_gestion_liquidaciones()

        elif opcion == "3":
            menu_recibos()
                
        elif opcion == "0":
            break

        else:
            print()
            print("Opción inválida.")


def menu_gestion_liquidaciones():
    while True:
        print()
        print("====================================")
        print("     GESTIONAR LIQUIDACIONES")
        print("====================================")
        print()
        print("1. Ver liquidaciones")
        print("2. Modificar liquidación")
        print("3. Eliminar liquidación")
        print("0. Volver")
        print()

        opcion = input(
            "Seleccione una opción: "
        ).strip()

        if opcion == "1":
            ver_liquidaciones_guardadas()

        elif opcion == "2":
            modificar_liquidacion_guardada()

        elif opcion == "3":
            eliminar_liquidacion_guardada()

        elif opcion == "0":
            break

        else:
            print()
            print("Opción inválida.")


def menu_recibos():
    while True:
        print()
        print("====================================")
        print("              RECIBOS")
        print("====================================")
        print()
        print("1. Generar recibo de sueldo")
        print("2. Gestionar recibos")
        print("0. Volver")
        print()

        opcion = input(
            "Seleccione una opción: "
        ).strip()

        if opcion == "1":
            generar_recibo_sueldo()

        elif opcion == "2":
            gestionar_recibos()

        elif opcion == "0":
            break

        else:
            print()
            print("Opción inválida.")

def pedir_periodo_consulta():
    while True:
        print()
        periodo = input(
            "Periodo a consultar (MM-AAAA) "
            "o 0 para cancelar: "
        ).strip()

        if periodo == "0":
            return None

        try:
            datetime.strptime(
                periodo,
                "%m-%Y"
            )
            return periodo

        except ValueError:
            print()
            print(
                "Periodo inválido. "
                "Ejemplo correcto: 07-2026"
            )


def obtener_liquidaciones_validas(periodo=None):
    lineas = leer_datos(
        RUTA_LIQUIDACIONES
    )

    liquidaciones = []

    for indice_linea, linea in enumerate(lineas):
        liquidacion = separar_liquidacion(linea)

        if liquidacion is None:
            continue

        if (
            periodo is not None
            and liquidacion["periodo"] != periodo
        ):
            continue

        liquidaciones.append(
            {
                "indice_linea": indice_linea,
                "datos": liquidacion,
            }
        )

    return lineas, liquidaciones


def ver_liquidaciones_guardadas():
    periodo = pedir_periodo_consulta()

    if periodo is None:
        return

    _, registros = obtener_liquidaciones_validas(
        periodo
    )

    if len(registros) == 0:
        print()
        print(
            "No hay liquidaciones guardadas "
            f"para el periodo {periodo}."
        )
        return

    print()
    print("====================================")
    print("     LIQUIDACIONES GUARDADAS")
    print("====================================")
    print("Periodo:", periodo)

    total_neto = 0

    for numero, registro in enumerate(
        registros,
        start=1
    ):
        liquidacion = registro["datos"]
        total_neto += liquidacion["neto_cobrar"]

        print()
        print("------------------------------------")
        print(
            f"{numero}.",
            liquidacion["nombre"]
        )
        print(
            "Cédula:",
            liquidacion["cedula"]
        )
        print(
            "Periodo:",
            liquidacion["periodo"]
        )
        print(
            "Tipo:",
            liquidacion["tipo_liquidacion"]
        )
        print(
            "Días liquidados:",
            liquidacion["dias_liquidados"]
        )
        print(
            "Sueldo de referencia:",
            formatear_monto(
                liquidacion["sueldo_referencia"]
            ),
            "Gs."
        )
        print(
            "Sueldo bruto antes de novedades:",
            formatear_monto(
                liquidacion["sueldo_bruto"]
            ),
            "Gs."
        )

        if liquidacion["comisiones"] > 0:
            print(
                "Comisiones:",
                formatear_monto(
                    liquidacion["comisiones"]
                ),
                "Gs."
            )

        if liquidacion["dias_ausencia"] > 0:
            print(
                "Ausencias:",
                liquidacion["dias_ausencia"],
                "día/s | Descuento:",
                formatear_monto(
                    liquidacion["descuento_ausencias"]
                ),
                "Gs."
            )

        if liquidacion["dias_reposo"] > 0:
            print(
                "Reposos:",
                liquidacion["dias_reposo"],
                "día/s | Descuento:",
                formatear_monto(
                    liquidacion["descuento_reposos"]
                ),
                "Gs."
            )

        print(
            f"Descuento IPS ({PORCENTAJE_IPS}%):",
            formatear_monto(
                liquidacion["descuento_ips"]
            ),
            "Gs."
        )

        if liquidacion["adelantos"] > 0:
            print(
                "Adelantos:",
                formatear_monto(
                    liquidacion["adelantos"]
                ),
                "Gs."
            )

        if liquidacion["otros_descuentos"] > 0:
            print(
                "Otros descuentos:",
                formatear_monto(
                    liquidacion["otros_descuentos"]
                ),
                "Gs."
            )

        print(
            "Neto pagado:",
            formatear_monto(
                liquidacion["neto_cobrar"]
            ),
            "Gs."
        )

    print()
    print("====================================")
    print(
        "Cantidad de funcionarios:",
        len(registros)
    )
    print(
        "Total neto del mes:",
        formatear_monto(total_neto),
        "Gs."
    )
    print("====================================")
    print()
    input("Presione ENTER para volver...")

def pedir_numero_entero(mensaje, valor_actual):
    while True:
        valor = input(
            f"{mensaje} [{valor_actual}]: "
        ).strip()

        if valor == "":
            return valor_actual

        if not valor.isdigit():
            print("Ingresá un número válido.")
            continue

        return int(valor)


def pedir_nuevo_periodo(periodo_actual):
    while True:
        periodo = input(
            f"Periodo MM-AAAA [{periodo_actual}]: "
        ).strip()

        if periodo == "":
            return periodo_actual

        try:
            datetime.strptime(
                periodo,
                "%m-%Y"
            )
            return periodo

        except ValueError:
            print(
                "Periodo inválido. "
                "Ejemplo correcto: 07-2026"
            )


def existe_otra_liquidacion(
    lineas,
    cedula,
    periodo,
    indice_ignorado
):
    for indice, linea in enumerate(lineas):
        if indice == indice_ignorado:
            continue

        liquidacion = separar_liquidacion(linea)

        if liquidacion is None:
            continue

        if (
            liquidacion["cedula"] == cedula
            and liquidacion["periodo"] == periodo
        ):
            return True

    return False


def modificar_liquidacion_guardada():
    periodo = pedir_periodo_consulta()

    if periodo is None:
        return

    lineas, liquidaciones_validas = (
        obtener_liquidaciones_validas(periodo)
    )

    if len(liquidaciones_validas) == 0:
        print()
        print(
            "No hay liquidaciones para modificar "
            f"en el periodo {periodo}."
        )
        return

    print()
    print("====================================")
    print("      MODIFICAR LIQUIDACIÓN")
    print("====================================")
    print()

    for numero, registro in enumerate(
        liquidaciones_validas,
        start=1
    ):
        liquidacion = registro["datos"]

        print(
            f"{numero}. "
            f"{liquidacion['nombre']} | "
            f"{liquidacion['periodo']} | "
            f"{formatear_monto(liquidacion['neto_cobrar'])} Gs."
        )

    print("0. Cancelar")
    print()

    while True:
        opcion = input(
            "Seleccione una liquidación: "
        ).strip()

        if opcion == "0":
            return

        if not opcion.isdigit():
            print("Ingresá un número válido.")
            continue

        indice_seleccionado = int(opcion) - 1

        if (
            indice_seleccionado < 0
            or indice_seleccionado
            >= len(liquidaciones_validas)
        ):
            print("La opción seleccionada no existe.")
            continue

        break

    registro = liquidaciones_validas[
        indice_seleccionado
    ]

    indice_linea = registro["indice_linea"]
    liquidacion = registro["datos"]

    print()
    print(
        "Dejá el campo vacío y presioná ENTER "
        "para conservar el valor actual."
    )
    print()

    nuevo_periodo = pedir_nuevo_periodo(
        liquidacion["periodo"]
    )

    if existe_otra_liquidacion(
        lineas,
        liquidacion["cedula"],
        nuevo_periodo,
        indice_linea
    ):
        print()
        print(
            "Ya existe otra liquidación de este "
            "funcionario para ese periodo."
        )
        return

    nuevos_dias = pedir_numero_entero(
        "Días liquidados",
        liquidacion["dias_liquidados"]
    )

    if nuevos_dias < 1 or nuevos_dias > 30:
        print()
        print(
            "Los días liquidados deben estar "
            "entre 1 y 30."
        )
        return

    nuevo_sueldo_referencia = pedir_numero_entero(
        "Sueldo de referencia",
        liquidacion["sueldo_referencia"]
    )

    nuevo_sueldo_bruto = pedir_numero_entero(
        "Sueldo bruto",
        liquidacion["sueldo_bruto"]
    )

    fecha_nuevo_periodo = datetime.strptime(
        nuevo_periodo,
        "%m-%Y"
    )
    nuevas_comisiones = obtener_novedades_del_periodo(
        liquidacion["cedula"],
        fecha_nuevo_periodo
    )["comisiones"]

    nuevo_descuento_ips = pedir_numero_entero(
        "Descuento IPS",
        liquidacion["descuento_ips"]
    )

    if nuevo_descuento_ips > nuevo_sueldo_bruto:
        print()
        print(
            "El descuento IPS no puede ser mayor "
            "que el sueldo bruto."
        )
        return

    if nuevos_dias == 30:
        nuevo_tipo = "Mes completo"
    else:
        nuevo_tipo = "Proporcional"

    nuevo_neto = (
        nuevo_sueldo_bruto
        + nuevas_comisiones
        - nuevo_descuento_ips
        - liquidacion["descuento_ausencias"]
        - liquidacion["descuento_reposos"]
        - liquidacion["adelantos"]
        - liquidacion["otros_descuentos"]
    )

    nuevo_neto = max(0, nuevo_neto)

    nuevos_datos = {
        "cedula": liquidacion["cedula"],
        "nombre": liquidacion["nombre"],
        "periodo": nuevo_periodo,
        "dias_liquidados": nuevos_dias,
        "sueldo_referencia": nuevo_sueldo_referencia,
        "sueldo_bruto": nuevo_sueldo_bruto,
        "descuento_ips": nuevo_descuento_ips,
        "neto_cobrar": nuevo_neto,
        "tipo_liquidacion": nuevo_tipo,
        "dias_ausencia": liquidacion["dias_ausencia"],
        "dias_reposo": liquidacion["dias_reposo"],
        "descuento_ausencias": (
            liquidacion["descuento_ausencias"]
        ),
        "descuento_reposos": (
            liquidacion["descuento_reposos"]
        ),
        "adelantos": liquidacion["adelantos"],
        "otros_descuentos": (
            liquidacion["otros_descuentos"]
        ),
        "comisiones": nuevas_comisiones,
    }

    print()
    print("====================================")
    print("       NUEVA LIQUIDACIÓN")
    print("====================================")
    print()
    print("Funcionario:", nuevos_datos["nombre"])
    print("Periodo:", nuevos_datos["periodo"])
    print(
        "Días liquidados:",
        nuevos_datos["dias_liquidados"]
    )
    print("Tipo:", nuevos_datos["tipo_liquidacion"])
    print(
        "Sueldo bruto:",
        formatear_monto(
            nuevos_datos["sueldo_bruto"]
        ),
        "Gs."
    )
    print(
        "Descuento IPS:",
        formatear_monto(
            nuevos_datos["descuento_ips"]
        ),
        "Gs."
    )
    print(
        "Comisiones:",
        formatear_monto(
            nuevos_datos["comisiones"]
        ),
        "Gs."
    )
    print(
        "Neto:",
        formatear_monto(
            nuevos_datos["neto_cobrar"]
        ),
        "Gs."
    )
    print()
    print("¿Guardar estos cambios?")
    print("1. Sí")
    print("2. No")

    while True:
        confirmacion = input(
            "Seleccione una opción: "
        ).strip()

        if confirmacion == "2":
            print()
            print("No se realizaron cambios.")
            return

        if confirmacion != "1":
            print("Opción inválida.")
            continue

        break

    lineas[indice_linea] = crear_linea_liquidacion(
        nuevos_datos
    )

    guardar_datos(
        RUTA_LIQUIDACIONES,
        lineas
    )

    print()
    print("Liquidación modificada correctamente.")


def eliminar_liquidacion_guardada():
    periodo = pedir_periodo_consulta()

    if periodo is None:
        return

    lineas, liquidaciones_validas = (
        obtener_liquidaciones_validas(periodo)
    )

    if len(liquidaciones_validas) == 0:
        print()
        print(
            "No hay liquidaciones para eliminar "
            f"en el periodo {periodo}."
        )
        return

    print()
    print("====================================")
    print("       ELIMINAR LIQUIDACIÓN")
    print("====================================")
    print()

    for numero, registro in enumerate(
        liquidaciones_validas,
        start=1
    ):
        liquidacion = registro["datos"]

        print(
            f"{numero}. "
            f"{liquidacion['nombre']} | "
            f"{liquidacion['periodo']} | "
            f"{formatear_monto(liquidacion['neto_cobrar'])} Gs."
        )

    print("0. Cancelar")
    print()

    while True:
        opcion = input(
            "Seleccione una liquidación: "
        ).strip()

        if opcion == "0":
            return

        if not opcion.isdigit():
            print("Ingresá un número válido.")
            continue

        indice_seleccionado = int(opcion) - 1

        if (
            indice_seleccionado < 0
            or indice_seleccionado
            >= len(liquidaciones_validas)
        ):
            print("La opción seleccionada no existe.")
            continue

        break

    registro = liquidaciones_validas[
        indice_seleccionado
    ]

    indice_linea = registro["indice_linea"]
    liquidacion = registro["datos"]

    print()
    print("Liquidación seleccionada:")
    print("Funcionario:", liquidacion["nombre"])
    print("Cédula:", liquidacion["cedula"])
    print("Periodo:", liquidacion["periodo"])
    print("Tipo:", liquidacion["tipo_liquidacion"])
    print(
        "Días liquidados:",
        liquidacion["dias_liquidados"]
    )
    print(
        "Neto pagado:",
        formatear_monto(
            liquidacion["neto_cobrar"]
        ),
        "Gs."
    )
    print()
    print(
        "¿Está seguro de eliminar esta liquidación?"
    )
    print("1. Sí, eliminar")
    print("2. No, cancelar")

    while True:
        confirmacion = input(
            "Seleccione una opción: "
        ).strip()

        if confirmacion == "2":
            print()
            print("La liquidación no fue eliminada.")
            return

        if confirmacion != "1":
            print("Opción inválida.")
            continue

        break

    lineas.pop(indice_linea)

    guardar_datos(
        RUTA_LIQUIDACIONES,
        lineas
    )

    print()
    print("Liquidación eliminada correctamente.")


def seleccionar_liquidacion_del_periodo(
    registros,
    titulo
):
    print()
    print("====================================")
    print(titulo)
    print("====================================")
    print()

    for numero, registro in enumerate(
        registros,
        start=1
    ):
        liquidacion = registro["datos"]

        print(
            f"{numero}. "
            f"{liquidacion['nombre']} | "
            f"{formatear_monto(liquidacion['neto_cobrar'])} Gs."
        )

    print("0. Cancelar")
    print()

    while True:
        opcion = input(
            "Seleccione una liquidación: "
        ).strip()

        if opcion == "0":
            return None

        if not opcion.isdigit():
            print("Ingresá un número válido.")
            continue

        indice = int(opcion) - 1

        if indice < 0 or indice >= len(registros):
            print("La opción seleccionada no existe.")
            continue

        return registros[indice]["datos"]


UNIDADES = [
    "", "uno", "dos", "tres", "cuatro", "cinco",
    "seis", "siete", "ocho", "nueve",
]

ESPECIALES = {
    10: "diez",
    11: "once",
    12: "doce",
    13: "trece",
    14: "catorce",
    15: "quince",
    16: "dieciséis",
    17: "diecisiete",
    18: "dieciocho",
    19: "diecinueve",
    20: "veinte",
    21: "veintiuno",
    22: "veintidós",
    23: "veintitrés",
    24: "veinticuatro",
    25: "veinticinco",
    26: "veintiséis",
    27: "veintisiete",
    28: "veintiocho",
    29: "veintinueve",
}

DECENAS = [
    "", "", "veinte", "treinta", "cuarenta",
    "cincuenta", "sesenta", "setenta", "ochenta", "noventa",
]

CENTENAS = [
    "", "ciento", "doscientos", "trescientos", "cuatrocientos",
    "quinientos", "seiscientos", "setecientos", "ochocientos",
    "novecientos",
]

MESES = [
    "",
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


def convertir_centenas(numero):
    if numero == 0:
        return ""

    if numero == 100:
        return "cien"

    partes = []
    centenas = numero // 100
    resto = numero % 100

    if centenas > 0:
        partes.append(CENTENAS[centenas])

    if resto in ESPECIALES:
        partes.append(ESPECIALES[resto])
    elif resto > 0:
        decena = resto // 10
        unidad = resto % 10

        if decena > 0:
            texto_decena = DECENAS[decena]

            if unidad > 0:
                texto_decena += f" y {UNIDADES[unidad]}"

            partes.append(texto_decena)
        else:
            partes.append(UNIDADES[unidad])

    return " ".join(partes)


def numero_a_letras(numero):
    numero = int(numero)

    if numero == 0:
        return "cero"

    if numero < 0:
        return f"menos {numero_a_letras(abs(numero))}"

    if numero > 999_999_999:
        return str(numero)

    partes = []
    millones = numero // 1_000_000
    miles = (numero % 1_000_000) // 1_000
    unidades = numero % 1_000

    if millones == 1:
        partes.append("un millón")
    elif millones > 1:
        partes.append(
            f"{convertir_centenas(millones)} millones"
        )

    if miles == 1:
        partes.append("mil")
    elif miles > 1:
        partes.append(
            f"{convertir_centenas(miles)} mil"
        )

    if unidades > 0:
        partes.append(convertir_centenas(unidades))

    return " ".join(partes)


def pedir_fecha_recibo():
    fecha_hoy = datetime.now().strftime("%d-%m-%Y")

    while True:
        fecha = input(
            "Fecha del recibo "
            f"(DD-MM-AAAA) [{fecha_hoy}]: "
        ).strip()

        if fecha == "":
            return fecha_hoy

        try:
            datetime.strptime(fecha, "%d-%m-%Y")
            return fecha
        except ValueError:
            print(
                "Fecha inválida. "
                "Ejemplo correcto: 26-07-2026"
            )


def obtener_periodo_en_letras(periodo):
    mes, anio = periodo.split("-")
    return f"{MESES[int(mes)]} del {anio}"


def crear_contenido_recibo(liquidacion, fecha_recibo):
    total_descuentos = (
        liquidacion["descuento_ausencias"]
        + liquidacion["descuento_reposos"]
        + liquidacion["descuento_ips"]
        + liquidacion["adelantos"]
        + liquidacion["otros_descuentos"]
    )

    lineas = [
        "============================================================",
        "                    RECIBO DE SUELDO",
        "============================================================",
        "",
        NOMBRE_EMPRESA,
        f"RUC: {RUC_EMPRESA}",
        CIUDAD_EMPRESA,
        "",
        f"Funcionario: {liquidacion['nombre']}",
        f"Cédula: {liquidacion['cedula']}",
        f"Fecha: {fecha_recibo}",
        f"Periodo: {liquidacion['periodo']}",
        "",
        "HABERES",
        "------------------------------------------------------------",
        (
            (
                "Monto base liquidado: "
                if liquidacion["tipo_liquidacion"] == "Monto manual"
                else "Sueldo: "
            )
            + f"{formatear_monto(liquidacion['sueldo_bruto'])} Gs."
        ),
    ]

    if liquidacion.get("comisiones", 0) > 0:
        lineas.append(
            "Comisiones: "
            f"{formatear_monto(liquidacion['comisiones'])} Gs."
        )

    if liquidacion.get("bonificaciones", 0) > 0:
        lineas.append(
            "Bonificaciones: "
            f"{formatear_monto(liquidacion['bonificaciones'])} Gs."
        )

    if liquidacion.get("horas_extras", 0) > 0:
        lineas.append(
            "Horas extras: "
            f"{formatear_monto(liquidacion['horas_extras'])} Gs."
        )

    lineas.extend(
        [
            "",
            "DESCUENTOS",
            "------------------------------------------------------------",
        ]
    )

    if liquidacion["descuento_ausencias"] > 0:
        lineas.append(
            "Ausencias "
            f"({liquidacion['dias_ausencia']} día/s): "
            f"{formatear_monto(liquidacion['descuento_ausencias'])} Gs."
        )

    if liquidacion["descuento_reposos"] > 0:
        lineas.append(
            "Reposos "
            f"({liquidacion['dias_reposo']} día/s): "
            f"{formatear_monto(liquidacion['descuento_reposos'])} Gs."
        )

    if liquidacion["descuento_ips"] > 0:
        lineas.append(
            f"IPS ({PORCENTAJE_IPS}%): "
            f"{formatear_monto(liquidacion['descuento_ips'])} Gs."
        )

    if liquidacion["adelantos"] > 0:
        lineas.append(
            "Adelantos: "
            f"{formatear_monto(liquidacion['adelantos'])} Gs."
        )

    if liquidacion["otros_descuentos"] > 0:
        lineas.append(
            "Otros descuentos: "
            f"{formatear_monto(liquidacion['otros_descuentos'])} Gs."
        )

    lineas.extend(
        [
            (
                "Total descuentos: "
                f"{formatear_monto(total_descuentos)} Gs."
            ),
            "",
            "============================================================",
            (
                "NETO A COBRAR: "
                f"{formatear_monto(liquidacion['neto_cobrar'])} Gs."
            ),
            "============================================================",
        ]
    )

    if liquidacion["descuento_reposos"] > 0:
        lineas.extend(
            [
                "",
                (
                    "Observación: el subsidio de IPS por reposo se cobra "
                    "por separado y no integra este pago."
                ),
            ]
        )

    lineas.extend(
        [
            "",
            (
                f"Recibí de {NOMBRE_EMPRESA} la suma de "
                f"G. {formatear_monto(liquidacion['neto_cobrar'])} "
                f"(Guaraníes "
                f"{numero_a_letras(liquidacion['neto_cobrar'])}) "
                "en concepto de sueldo, correspondiente al mes de "
                f"{obtener_periodo_en_letras(liquidacion['periodo'])}."
            ),
            "",
            "",
            "____________________________",
            "Firma del funcionario",
            f"C.I. N.º {liquidacion['cedula']}",
            "",
            "____________________________",
            "Firma del empleador",
            "",
        ]
    )

    return "\n".join(lineas)


def generar_recibo_sueldo():
    periodo = pedir_periodo_consulta()

    if periodo is None:
        return

    _, registros = obtener_liquidaciones_validas(
        periodo
    )

    if len(registros) == 0:
        print()
        print(
            "No hay liquidaciones guardadas "
            f"para el periodo {periodo}."
        )
        return

    liquidacion = seleccionar_liquidacion_del_periodo(
        registros,
        "       GENERAR RECIBO DE SUELDO"
    )

    if liquidacion is None:
        return

    fecha_recibo = pedir_fecha_recibo()

    contenido = crear_contenido_recibo(
        liquidacion,
        fecha_recibo
    )

    print()
    print(contenido)
    print()
    print("¿Guardar este recibo?")
    print("1. Sí")
    print("2. No")

    while True:
        confirmacion = input(
            "Seleccione una opción: "
        ).strip()

        if confirmacion == "2":
            print()
            print("El recibo no fue guardado.")
            return

        if confirmacion != "1":
            print("Opción inválida.")
            continue

        break

    RUTA_RECIBOS.mkdir(
        parents=True,
        exist_ok=True
    )

    periodo_archivo = liquidacion[
        "periodo"
    ].replace("-", "_")

    cedula_archivo = (
        liquidacion["cedula"]
        .replace(".", "")
        .replace(" ", "")
    )

    nombre_archivo = (
        f"recibo_{periodo_archivo}_"
        f"{cedula_archivo}.txt"
    )

    ruta_recibo = (
        RUTA_RECIBOS
        / nombre_archivo
    )

    with open(
        ruta_recibo,
        "w",
        encoding="utf-8"
    ) as archivo:
        archivo.write(contenido)

    print()
    print("Recibo guardado correctamente.")
    print("Ubicación:", ruta_recibo)


def obtener_recibos_del_periodo(periodo):
    if not RUTA_RECIBOS.exists():
        return []

    periodo_archivo = periodo.replace("-", "_")
    patron = f"recibo_{periodo_archivo}_*.txt"

    return sorted(RUTA_RECIBOS.glob(patron))


def obtener_cedula_archivo_recibo(ruta_recibo, periodo):
    periodo_archivo = periodo.replace("-", "_")
    prefijo = f"recibo_{periodo_archivo}_"
    nombre = ruta_recibo.stem

    if not nombre.startswith(prefijo):
        return ""

    return nombre[len(prefijo):]


def buscar_liquidacion_recibo(periodo, cedula_archivo):
    _, registros = obtener_liquidaciones_validas(periodo)

    for registro in registros:
        liquidacion = registro["datos"]
        cedula_limpia = (
            liquidacion["cedula"]
            .replace(".", "")
            .replace(" ", "")
        )

        if cedula_limpia == cedula_archivo:
            return liquidacion

    return None


def seleccionar_recibo(periodo):
    recibos = obtener_recibos_del_periodo(periodo)

    if len(recibos) == 0:
        print()
        print(
            "No hay recibos guardados "
            f"para el periodo {periodo}."
        )
        return None

    print()
    print("====================================")
    print("       RECIBOS DEL PERIODO")
    print("====================================")
    print()

    for numero, ruta_recibo in enumerate(
        recibos,
        start=1
    ):
        cedula_archivo = obtener_cedula_archivo_recibo(
            ruta_recibo,
            periodo
        )
        liquidacion = buscar_liquidacion_recibo(
            periodo,
            cedula_archivo
        )

        if liquidacion is None:
            descripcion = ruta_recibo.name
        else:
            descripcion = (
                f"{liquidacion['nombre']} | "
                f"C.I. {liquidacion['cedula']}"
            )

        print(f"{numero}. {descripcion}")

    print("0. Cancelar")
    print()

    while True:
        opcion = input(
            "Seleccione un recibo: "
        ).strip()

        if opcion == "0":
            return None

        if not opcion.isdigit():
            print("Ingresá un número válido.")
            continue

        indice = int(opcion) - 1

        if indice < 0 or indice >= len(recibos):
            print("La opción seleccionada no existe.")
            continue

        return recibos[indice]


def gestionar_recibos():
    periodo = pedir_periodo_consulta()

    if periodo is None:
        return

    ruta_recibo = seleccionar_recibo(periodo)

    if ruta_recibo is None:
        return

    while True:
        print()
        print("====================================")
        print("        GESTIONAR RECIBO")
        print("====================================")
        print()
        print("1. Ver recibo")
        print("2. Modificar fecha y regenerar")
        print("3. Eliminar recibo")
        print("0. Volver")
        print()

        opcion = input(
            "Seleccione una opción: "
        ).strip()

        if opcion == "1":
            print()

            with open(
                ruta_recibo,
                "r",
                encoding="utf-8"
            ) as archivo:
                print(archivo.read())

            print()
            input("Presione ENTER para volver...")

        elif opcion == "2":
            cedula_archivo = obtener_cedula_archivo_recibo(
                ruta_recibo,
                periodo
            )
            liquidacion = buscar_liquidacion_recibo(
                periodo,
                cedula_archivo
            )

            if liquidacion is None:
                print()
                print(
                    "No se encontró la liquidación original. "
                    "No se puede regenerar el recibo."
                )
                continue

            nueva_fecha = pedir_fecha_recibo()
            contenido = crear_contenido_recibo(
                liquidacion,
                nueva_fecha
            )

            print()
            print(contenido)
            print()
            print("¿Guardar esta modificación?")
            print("1. Sí")
            print("2. No")

            confirmacion = input(
                "Seleccione una opción: "
            ).strip()

            if confirmacion == "1":
                with open(
                    ruta_recibo,
                    "w",
                    encoding="utf-8"
                ) as archivo:
                    archivo.write(contenido)

                print()
                print("Recibo modificado correctamente.")
            else:
                print()
                print("No se realizaron cambios.")

        elif opcion == "3":
            print()
            print("¿Está seguro de eliminar este recibo?")
            print("1. Sí, eliminar")
            print("2. No, cancelar")

            confirmacion = input(
                "Seleccione una opción: "
            ).strip()

            if confirmacion == "1":
                ruta_recibo.unlink()
                print()
                print("Recibo eliminado correctamente.")
                return

            print()
            print("El recibo no fue eliminado.")

        elif opcion == "0":
            break

        else:
            print()
            print("Opción inválida.")
