from calendar import monthrange
from datetime import datetime
from uuid import uuid4

from datos import leer_datos, guardar_datos
import Movimientos


RUTA_RETIROS_SOCIOS = "Datos/retiros_socios.txt"
REGISTROS_POR_PAGINA = 10
PORCENTAJE_RETENCION = (
    Movimientos.PORCENTAJE_FONDO_ESTABILIDAD
)

SOCIOS = [
    {
        "id": "SOL",
        "nombre": "Sol",
        "cedula": "6133468",
        "porcentaje_utilidad": 65,
    },
    {
        "id": "RODRIGO",
        "nombre": "Rodrigo",
        "cedula": "5201642",
        "porcentaje_utilidad": 35,
    },
]

TIPOS_MOVIMIENTO_PERSONAL = [
    "Gasto personal",
    "Inversión personal",
]
TIPO_MOVIMIENTO_PREDETERMINADO = "Gasto personal"
TIPOS_QUE_AFECTAN_SALDO = {"Gasto personal"}


def limpiar_texto(texto):
    return texto.strip().replace("|", "/")


def normalizar_tipo_movimiento_personal(tipo):
    texto = limpiar_texto(str(tipo or "")).lower()
    for opcion in TIPOS_MOVIMIENTO_PERSONAL:
        if texto == opcion.lower():
            return opcion
    return None


def seleccionar_tipo_movimiento_personal(valor_actual=None):
    while True:
        print()
        for numero, tipo in enumerate(
            TIPOS_MOVIMIENTO_PERSONAL,
            start=1,
        ):
            print(f"{numero}. {tipo}")

        if valor_actual is not None:
            print("ENTER. Conservar", valor_actual)
        print("0. Volver")
        print()

        opcion = input("Seleccione el tipo: ").strip()
        if opcion == "" and valor_actual is not None:
            return valor_actual
        if opcion == "0":
            return None

        try:
            indice = int(opcion) - 1
            if 0 <= indice < len(TIPOS_MOVIMIENTO_PERSONAL):
                return TIPOS_MOVIMIENTO_PERSONAL[indice]
        except ValueError:
            pass

        print("Opción inválida.")


def obtener_socio(socio_id):
    for socio in SOCIOS:
        if socio["id"] == socio_id:
            return socio
    return None


def seleccionar_socio(valor_actual=None):
    while True:
        print()

        for numero, socio in enumerate(SOCIOS, start=1):
            print(f"{numero}. {socio['nombre']}")

        if valor_actual is not None:
            socio_actual = obtener_socio(valor_actual)
            if socio_actual is not None:
                print("ENTER. Conservar", socio_actual["nombre"])

        print("0. Volver")
        print()

        opcion = input("Seleccione un socio: ").strip()

        if opcion == "" and valor_actual is not None:
            return valor_actual

        if opcion == "0":
            return None

        try:
            indice = int(opcion) - 1
            if 0 <= indice < len(SOCIOS):
                return SOCIOS[indice]["id"]
        except ValueError:
            pass

        print("Opción inválida.")


def pedir_periodo():
    while True:
        print()
        print("0. Volver")
        periodo = input("Mes y año (MM-AAAA): ").strip()

        if periodo == "0":
            return None

        try:
            fecha = datetime.strptime(periodo, "%m-%Y")
            return fecha.month, fecha.year
        except ValueError:
            print("Período inválido. Usá el formato MM-AAAA.")


def limites_periodo(mes, anio):
    ultimo_dia = monthrange(anio, mes)[1]
    return (
        datetime(anio, mes, 1),
        datetime(anio, mes, ultimo_dia),
    )


def separar_retiro(linea):
    partes = [parte.strip() for parte in linea.split("|")]

    if len(partes) not in (5, 6):
        return None

    try:
        Movimientos.convertir_fecha(partes[1])
        monto = int(partes[3])
    except ValueError:
        return None

    tipo = (
        TIPO_MOVIMIENTO_PREDETERMINADO
        if len(partes) == 5
        else normalizar_tipo_movimiento_personal(partes[4])
    )
    observacion = partes[4] if len(partes) == 5 else partes[5]

    if (
        monto <= 0
        or obtener_socio(partes[2]) is None
        or tipo is None
    ):
        return None

    return {
        "id": partes[0],
        "fecha": partes[1],
        "socio_id": partes[2],
        "monto": monto,
        "tipo": tipo,
        "observacion": observacion,
    }


def crear_linea_retiro(datos):
    return " | ".join(
        [
            datos["id"],
            datos["fecha"],
            datos["socio_id"],
            str(datos["monto"]),
            normalizar_tipo_movimiento_personal(
                datos.get(
                    "tipo",
                    TIPO_MOVIMIENTO_PREDETERMINADO,
                )
            )
            or TIPO_MOVIMIENTO_PREDETERMINADO,
            limpiar_texto(datos["observacion"]) or "-",
        ]
    )


def obtener_retiros_validos():
    retiros = []

    for posicion, linea in enumerate(
        leer_datos(RUTA_RETIROS_SOCIOS)
    ):
        datos = separar_retiro(linea)

        if datos is not None:
            retiros.append((posicion, datos))

    return retiros


def retiros_del_periodo(mes, anio):
    resultado = []

    for posicion, retiro in obtener_retiros_validos():
        fecha = Movimientos.convertir_fecha(retiro["fecha"])

        if fecha.month == mes and fecha.year == anio:
            resultado.append((posicion, retiro))

    return sorted(
        resultado,
        key=lambda elemento: (
            Movimientos.convertir_fecha(elemento[1]["fecha"]),
            elemento[1]["id"],
        ),
        reverse=True,
    )


def total_retirado(socio_id, mes, anio):
    return sum(
        retiro["monto"]
        for _, retiro in retiros_del_periodo(mes, anio)
        if (
            retiro["socio_id"] == socio_id
            and retiro["tipo"] in TIPOS_QUE_AFECTAN_SALDO
        )
    )


def total_retirado_por_tipo(socio_id, mes, anio, tipo):
    tipo_normalizado = normalizar_tipo_movimiento_personal(tipo)
    if tipo_normalizado is None:
        return 0

    return sum(
        retiro["monto"]
        for _, retiro in retiros_del_periodo(mes, anio)
        if (
            retiro["socio_id"] == socio_id
            and retiro["tipo"] == tipo_normalizado
        )
    )


def distribuir_utilidad(utilidad_distribuible):
    distribucion = {}
    acumulado = 0

    for indice, socio in enumerate(SOCIOS):
        if indice == len(SOCIOS) - 1:
            monto = utilidad_distribuible - acumulado
        else:
            monto = (
                utilidad_distribuible
                * socio["porcentaje_utilidad"]
                // 100
            )

        distribucion[socio["id"]] = monto
        acumulado += monto

    return distribucion


def calcular_resumen_periodo(mes, anio):
    fecha_desde, fecha_hasta = limites_periodo(mes, anio)
    indicadores = Movimientos.calcular_indicadores_cierre(
        fecha_desde,
        fecha_hasta,
    )
    periodo = f"{mes:02d}-{anio}"
    registro_fondo = Movimientos.obtener_registro_fondo(
        periodo
    )
    retencion_empresa = indicadores["fondo_calculado"]

    if registro_fondo is not None:
        retencion_empresa = (
            registro_fondo[1]["monto_aplicado"]
        )

    utilidad_distribuible = max(
        indicadores["utilidad_mes"] - retencion_empresa,
        0
    )
    utilidades_socios = distribuir_utilidad(
        utilidad_distribuible
    )
    _, detalle_nomina = Movimientos.resumen_nomina_liquidada(
        fecha_desde,
        fecha_hasta,
    )

    resumen_socios = []

    for socio in SOCIOS:
        retirado = total_retirado(
            socio["id"],
            mes,
            anio
        )
        gastos_personales = total_retirado_por_tipo(
            socio["id"],
            mes,
            anio,
            "Gasto personal",
        )
        inversiones_personales = total_retirado_por_tipo(
            socio["id"],
            mes,
            anio,
            "Inversión personal",
        )
        utilidad = utilidades_socios[socio["id"]]
        sueldo_liquidado = sum(
            liquidacion["egreso_planilla"]
            for liquidacion in detalle_nomina
            if liquidacion["cedula"] == socio["cedula"]
        )
        total_a_cobrar = sueldo_liquidado + utilidad
        saldo = total_a_cobrar - retirado

        resumen_socios.append(
            {
                **socio,
                "sueldo_liquidado": sueldo_liquidado,
                "utilidad": utilidad,
                "total_a_cobrar": total_a_cobrar,
                "retirado": retirado,
                "gastos_personales": gastos_personales,
                "inversiones_personales": inversiones_personales,
                "saldo": saldo,
            }
        )

    return {
        "ingresos": indicadores["ingresos"],
        "egresos": indicadores["egresos"],
        "resultado_antes_socios": indicadores["utilidad_mes"],
        "total_sueldos_socios": 0,
        "resultado_despues_sueldos": (
            indicadores["utilidad_mes"]
        ),
        "utilidad_mes": indicadores["utilidad_mes"],
        "margen_porcentual": (
            indicadores["margen_porcentual"]
        ),
        "retencion_empresa": retencion_empresa,
        "fondo_calculado": indicadores["fondo_calculado"],
        "fondo_registrado": registro_fondo is not None,
        "fondo_modo": (
            registro_fondo[1]["modo"]
            if registro_fondo is not None
            else "PROVISORIO"
        ),
        "utilidad_distribuible": utilidad_distribuible,
        "socios": resumen_socios,
    }


def registrar_retiro():
    print()
    print("====================================")
    print("       REGISTRAR RETIRO DE SOCIO")
    print("====================================")
    print()
    print("Escribí 0 para volver.")

    fecha = Movimientos.pedir_fecha()
    if fecha is None:
        return

    socio_id = seleccionar_socio()
    if socio_id is None:
        return

    tipo = seleccionar_tipo_movimiento_personal()
    if tipo is None:
        return

    monto = Movimientos.pedir_monto("Monto retirado: ")
    if monto is None:
        return

    observacion = input(
        "Observación (opcional): "
    ).strip()

    if observacion == "0":
        return

    socio = obtener_socio(socio_id)

    print()
    print("Fecha:", fecha)
    print("Socio:", socio["nombre"])
    print("Tipo:", tipo)
    print("Monto:", Movimientos.formatear_monto(monto))
    print("Observación:", observacion or "-")
    print()

    if not Movimientos.confirmar(
        "Escribí SI para confirmar: "
    ):
        print("Registro cancelado.")
        return

    datos = {
        "id": uuid4().hex[:12].upper(),
        "fecha": fecha,
        "socio_id": socio_id,
        "monto": monto,
        "tipo": tipo,
        "observacion": observacion,
    }

    retiros = leer_datos(RUTA_RETIROS_SOCIOS)
    retiros.append(crear_linea_retiro(datos))
    guardar_datos(RUTA_RETIROS_SOCIOS, retiros)

    print()
    print("Retiro registrado correctamente.")


def mostrar_saldo(saldo):
    if saldo >= 0:
        return (
            "SALDO PENDIENTE A FAVOR: "
            + Movimientos.formatear_monto(saldo)
        )

    return (
        "EXCESO RETIRADO: "
        + Movimientos.formatear_monto(abs(saldo))
    )


def ver_resumen_mensual():
    periodo = pedir_periodo()

    if periodo is None:
        return

    mes, anio = periodo
    resumen = calcular_resumen_periodo(mes, anio)
    _, fecha_hasta = limites_periodo(mes, anio)
    es_provisorio = (
        fecha_hasta.date() >= datetime.now().date()
    )

    print()
    print("====================================")
    print("        RESUMEN MENSUAL DE SOCIOS")
    print("====================================")
    print()
    print(f"Período: {mes:02d}-{anio}")

    if es_provisorio:
        print("Estado: PROVISORIO - el mes aún no terminó.")
    else:
        print("Estado: CERRADO")

    print()
    print(
        "Utilidad del mes:",
        Movimientos.formatear_monto(
            resumen["utilidad_mes"]
        )
    )
    print(
        "Margen porcentual:",
        Movimientos.formatear_porcentaje(
            resumen["margen_porcentual"]
        ) + "%"
    )
    print(
        f"Fondo de estabilidad ({PORCENTAJE_RETENCION}%):",
        Movimientos.formatear_monto(
            resumen["retencion_empresa"]
        )
    )
    print(
        "Utilidad total para distribuir:",
        Movimientos.formatear_monto(
            resumen["utilidad_distribuible"]
        )
    )

    if resumen["resultado_despues_sueldos"] < 0:
        print(
            "No se distribuye utilidad porque el resultado "
            "del mes es negativo."
        )

    if resumen["fondo_modo"] == "MANUAL":
        print(
            "El fondo de este mes fue ajustado manualmente."
        )
        print(
            "Cálculo original:",
            Movimientos.formatear_monto(
                resumen["fondo_calculado"]
            )
        )
    elif not resumen["fondo_registrado"]:
        print(
            "Fondo provisorio: todavía no fue generado "
            "desde el cierre mensual."
        )

    for socio in resumen["socios"]:
        print()
        print("------------------------------------")
        print(socio["nombre"].upper())
        print("------------------------------------")
        print(
            "Sueldo liquidado en RR. HH.:",
            Movimientos.formatear_monto(
                socio["sueldo_liquidado"]
            )
        )
        print(
            f"Utilidad ({socio['porcentaje_utilidad']}%):",
            Movimientos.formatear_monto(socio["utilidad"])
        )
        print(
            "Utilidad asignada:",
            Movimientos.formatear_monto(
                socio["total_a_cobrar"]
            )
        )
        print(
            "Total descontado del saldo:",
            Movimientos.formatear_monto(socio["retirado"])
        )
        print(
            "Gastos personales:",
            Movimientos.formatear_monto(
                socio["gastos_personales"]
            )
        )
        print(
            "Inversiones personales:",
            Movimientos.formatear_monto(
                socio["inversiones_personales"]
            )
        )
        print(mostrar_saldo(socio["saldo"]))

    print()
    input("Presioná ENTER para volver...")


def mostrar_retiro(numero, retiro):
    socio = obtener_socio(retiro["socio_id"])
    print(
        f"{numero}. {retiro['fecha']} | "
        f"{socio['nombre']} | "
        f"{retiro['tipo']} | "
        f"{Movimientos.formatear_monto(retiro['monto'])} | "
        f"{retiro['observacion']}"
    )


def pedir_fecha_edicion(fecha_actual):
    while True:
        texto = input(
            f"Fecha [{fecha_actual}] (DD-MM-AAAA): "
        ).strip()

        if texto == "":
            return fecha_actual

        if texto == "0":
            return None

        try:
            Movimientos.convertir_fecha(texto)
            return texto
        except ValueError:
            print("Fecha inválida. Usá el formato DD-MM-AAAA.")


def modificar_retiro(posicion, retiro):
    print()
    print("ENTER conserva el valor actual.")
    print("0. Cancela la modificación.")
    print()

    fecha = pedir_fecha_edicion(retiro["fecha"])
    if fecha is None:
        return

    socio_id = seleccionar_socio(retiro["socio_id"])
    if socio_id is None:
        return

    tipo = seleccionar_tipo_movimiento_personal(retiro["tipo"])
    if tipo is None:
        return

    monto = Movimientos.pedir_monto(
        "Monto retirado: ",
        retiro["monto"]
    )
    if monto is None:
        return

    observacion = input(
        f"Observación [{retiro['observacion']}]: "
    ).strip()

    if observacion == "0":
        return

    if observacion == "":
        observacion = retiro["observacion"]

    actualizado = {
        **retiro,
        "fecha": fecha,
        "socio_id": socio_id,
        "monto": monto,
        "tipo": tipo,
        "observacion": observacion,
    }

    if not Movimientos.confirmar(
        "Escribí SI para guardar los cambios: "
    ):
        print("Modificación cancelada.")
        return

    lista = leer_datos(RUTA_RETIROS_SOCIOS)
    lista[posicion] = crear_linea_retiro(actualizado)
    guardar_datos(RUTA_RETIROS_SOCIOS, lista)

    print("Retiro modificado correctamente.")


def eliminar_retiro(posicion, retiro):
    socio = obtener_socio(retiro["socio_id"])

    print()
    print("Fecha:", retiro["fecha"])
    print("Socio:", socio["nombre"])
    print("Tipo:", retiro["tipo"])
    print(
        "Monto:",
        Movimientos.formatear_monto(retiro["monto"])
    )
    print()

    if not Movimientos.confirmar(
        "Escribí SI para eliminar este retiro: "
    ):
        print("Eliminación cancelada.")
        return

    lista = leer_datos(RUTA_RETIROS_SOCIOS)
    lista.pop(posicion)
    guardar_datos(RUTA_RETIROS_SOCIOS, lista)

    print("Retiro eliminado correctamente.")


def gestionar_retiro(posicion, retiro):
    while True:
        socio = obtener_socio(retiro["socio_id"])

        print()
        print("====================================")
        print("           DETALLE DEL RETIRO")
        print("====================================")
        print()
        print("Fecha:", retiro["fecha"])
        print("Socio:", socio["nombre"])
        print("Tipo:", retiro["tipo"])
        print(
            "Monto:",
            Movimientos.formatear_monto(retiro["monto"])
        )
        print("Observación:", retiro["observacion"])
        print()
        print("1. Modificar")
        print("2. Eliminar")
        print("0. Volver")
        print()

        opcion = input("Seleccione una opción: ").strip()

        if opcion == "1":
            modificar_retiro(posicion, retiro)
            return
        elif opcion == "2":
            eliminar_retiro(posicion, retiro)
            return
        elif opcion == "0":
            return
        else:
            print("Opción inválida.")


def gestionar_retiros():
    periodo = pedir_periodo()

    if periodo is None:
        return

    mes, anio = periodo
    pagina = 0

    while True:
        retiros = retiros_del_periodo(mes, anio)

        if not retiros:
            print()
            print(
                f"No hay retiros registrados en "
                f"{mes:02d}-{anio}."
            )
            return

        total_paginas = (
            len(retiros) + REGISTROS_POR_PAGINA - 1
        ) // REGISTROS_POR_PAGINA
        pagina = min(pagina, total_paginas - 1)
        inicio = pagina * REGISTROS_POR_PAGINA
        fin = inicio + REGISTROS_POR_PAGINA

        print()
        print("====================================")
        print("        RETIROS DE SOCIOS")
        print("====================================")
        print()
        print(f"Período: {mes:02d}-{anio}")
        print(f"Página {pagina + 1} de {total_paginas}")
        print()

        for numero, (_, retiro) in enumerate(
            retiros[inicio:fin],
            start=inicio + 1
        ):
            mostrar_retiro(numero, retiro)

        print()
        if pagina > 0:
            print("A. Página anterior")
        if pagina < total_paginas - 1:
            print("S. Página siguiente")
        print("0. Volver")
        print()

        opcion = input(
            "Seleccione un retiro u opción: "
        ).strip().upper()

        if opcion == "0":
            return

        if opcion == "A" and pagina > 0:
            pagina -= 1
            continue

        if opcion == "S" and pagina < total_paginas - 1:
            pagina += 1
            continue

        try:
            indice = int(opcion) - 1

            if inicio <= indice < min(fin, len(retiros)):
                posicion, retiro = retiros[indice]
                gestionar_retiro(posicion, retiro)
                continue
        except ValueError:
            pass

        print("Opción inválida.")


def ordenar_registros_fondo():
    return sorted(
        Movimientos.obtener_registros_fondo(),
        key=lambda elemento: datetime.strptime(
            elemento[1]["periodo"],
            "%m-%Y"
        ),
        reverse=True,
    )


def mostrar_resumen_fondo():
    registros = ordenar_registros_fondo()

    print()
    print("====================================")
    print("       FONDO DE ESTABILIDAD")
    print("====================================")
    print()

    if not registros:
        print(
            "Todavía no hay cierres mensuales "
            "registrados."
        )
        print()
        input("Presioná ENTER para volver...")
        return

    total = sum(
        registro["monto_aplicado"]
        for _, registro in registros
    )
    print(
        "FONDO ACUMULADO:",
        Movimientos.formatear_monto(total)
    )
    print(
        "Meses registrados:",
        len(registros)
    )
    print()
    input("Presioná ENTER para volver...")


def pedir_monto_fondo(valor_actual, limite):
    while True:
        print()
        print("ENTER. Conservar el monto actual")
        print("CERO. Cambiar el monto a 0")
        print("0. Volver")
        texto = input(
            "Nuevo monto del fondo "
            f"[{Movimientos.formatear_monto(valor_actual)}]: "
        ).strip()

        if texto == "":
            return valor_actual

        if texto == "0":
            return None

        if texto.upper() == "CERO":
            return 0

        texto_limpio = (
            texto
            .replace(".", "")
            .replace(",", "")
            .replace(" ", "")
        )

        try:
            monto = int(texto_limpio)

            if monto < 0:
                raise ValueError

            if monto > limite:
                print(
                    "El fondo no puede superar la utilidad "
                    "positiva disponible del mes: "
                    + Movimientos.formatear_monto(limite)
                )
                continue

            return monto
        except ValueError:
            print("Monto inválido.")


def modificar_registro_fondo(posicion, registro):
    mes, anio = [
        int(parte)
        for parte in registro["periodo"].split("-")
    ]
    resumen = calcular_resumen_periodo(mes, anio)
    utilidad_disponible = max(
        resumen["resultado_despues_sueldos"],
        0
    )

    print()
    print("====================================")
    print("       MODIFICAR FONDO DEL MES")
    print("====================================")
    print()
    print("Período:", registro["periodo"])
    print(
        "Cálculo automático:",
        Movimientos.formatear_monto(
            registro["monto_calculado"]
        )
    )
    print(
        "Monto aplicado:",
        Movimientos.formatear_monto(
            registro["monto_aplicado"]
        )
    )
    print(
        "Utilidad positiva disponible:",
        Movimientos.formatear_monto(
            utilidad_disponible
        )
    )

    monto = pedir_monto_fondo(
        registro["monto_aplicado"],
        utilidad_disponible
    )

    if monto is None:
        return

    print()
    print("0. Volver")
    observacion = input(
        f"Motivo del ajuste [{registro['observacion']}]: "
    ).strip()

    if observacion == "0":
        return

    if observacion == "":
        observacion = registro["observacion"]

    actualizado = {
        **registro,
        "monto_aplicado": monto,
        "modo": "MANUAL",
        "observacion": observacion,
    }

    if not Movimientos.confirmar(
        "Escribí SI para guardar el ajuste: "
    ):
        print("Modificación cancelada.")
        return

    lista = leer_datos(
        Movimientos.RUTA_FONDO_ESTABILIDAD
    )
    lista[posicion] = Movimientos.crear_linea_fondo(
        actualizado
    )
    guardar_datos(
        Movimientos.RUTA_FONDO_ESTABILIDAD,
        lista
    )
    print("Fondo del mes modificado correctamente.")


def restaurar_fondo_automatico(posicion, registro):
    actualizado = {
        **registro,
        "monto_aplicado": registro["monto_calculado"],
        "modo": "AUTOMATICO",
        "observacion": "Restaurado al cálculo automático",
    }

    print()
    print(
        "El fondo volverá a:",
        Movimientos.formatear_monto(
            registro["monto_calculado"]
        )
    )

    if not Movimientos.confirmar(
        "Escribí SI para restaurarlo: "
    ):
        print("Restauración cancelada.")
        return

    lista = leer_datos(
        Movimientos.RUTA_FONDO_ESTABILIDAD
    )
    lista[posicion] = Movimientos.crear_linea_fondo(
        actualizado
    )
    guardar_datos(
        Movimientos.RUTA_FONDO_ESTABILIDAD,
        lista
    )
    print("Cálculo automático restaurado.")


def gestionar_registro_fondo(posicion, registro):
    while True:
        print()
        print("====================================")
        print("         DETALLE DEL FONDO")
        print("====================================")
        print()
        print("Período:", registro["periodo"])
        print(
            "Calculado:",
            Movimientos.formatear_monto(
                registro["monto_calculado"]
            )
        )
        print(
            "Aplicado:",
            Movimientos.formatear_monto(
                registro["monto_aplicado"]
            )
        )
        print("Modo:", registro["modo"])
        print("Observación:", registro["observacion"])
        print()
        print("1. Modificar monto aplicado")

        if registro["modo"] == "MANUAL":
            print("2. Restaurar cálculo automático")

        print("0. Volver")
        print()
        opcion = input("Seleccione una opción: ").strip()

        if opcion == "1":
            modificar_registro_fondo(posicion, registro)
            return
        elif (
            opcion == "2"
            and registro["modo"] == "MANUAL"
        ):
            restaurar_fondo_automatico(
                posicion,
                registro
            )
            return
        elif opcion == "0":
            return
        else:
            print("Opción inválida.")


def gestionar_registros_fondo():
    pagina = 0

    while True:
        registros = ordenar_registros_fondo()

        if not registros:
            print()
            print(
                "Todavía no hay cierres mensuales "
                "registrados."
            )
            return

        total_paginas = (
            len(registros) + REGISTROS_POR_PAGINA - 1
        ) // REGISTROS_POR_PAGINA
        pagina = min(pagina, total_paginas - 1)
        inicio = pagina * REGISTROS_POR_PAGINA
        fin = inicio + REGISTROS_POR_PAGINA

        print()
        print("====================================")
        print("       REGISTROS DEL FONDO")
        print("====================================")
        print()
        print(f"Página {pagina + 1} de {total_paginas}")
        print()

        for numero, (_, registro) in enumerate(
            registros[inicio:fin],
            start=inicio + 1
        ):
            print(
                f"{numero}. {registro['periodo']} | "
                f"Aplicado: "
                f"{Movimientos.formatear_monto(registro['monto_aplicado'])} | "
                f"{registro['modo']}"
            )

        print()

        if pagina > 0:
            print("A. Página anterior")

        if pagina < total_paginas - 1:
            print("S. Página siguiente")

        print("0. Volver")
        print()
        opcion = input(
            "Seleccione un período u opción: "
        ).strip().upper()

        if opcion == "0":
            return

        if opcion == "A" and pagina > 0:
            pagina -= 1
            continue

        if opcion == "S" and pagina < total_paginas - 1:
            pagina += 1
            continue

        try:
            indice = int(opcion) - 1

            if inicio <= indice < min(
                fin,
                len(registros)
            ):
                posicion, registro = registros[indice]
                gestionar_registro_fondo(
                    posicion,
                    registro
                )
                continue
        except ValueError:
            pass

        print("Opción inválida.")


def menu_fondo_estabilidad():
    while True:
        print()
        print("====================================")
        print("       FONDO DE ESTABILIDAD")
        print("====================================")
        print()
        print("1. Ver fondo acumulado")
        print("2. Ver o modificar registros mensuales")
        print("0. Volver")
        print()
        opcion = input("Seleccione una opción: ").strip()

        if opcion == "1":
            mostrar_resumen_fondo()
        elif opcion == "2":
            gestionar_registros_fondo()
        elif opcion == "0":
            return
        else:
            print("Opción inválida.")


def menu_socios():
    while True:
        print()
        print("====================================")
        print("              SOCIOS")
        print("====================================")
        print()
        print("1. Registrar retiro")
        print("2. Resumen mensual")
        print("3. Ver, modificar o eliminar retiros")
        print("4. Fondo de estabilidad")
        print("0. Volver")
        print()

        opcion = input("Seleccione una opción: ").strip()

        if opcion == "1":
            registrar_retiro()
        elif opcion == "2":
            ver_resumen_mensual()
        elif opcion == "3":
            gestionar_retiros()
        elif opcion == "4":
            menu_fondo_estabilidad()
        elif opcion == "0":
            return
        else:
            print("Opción inválida.")
