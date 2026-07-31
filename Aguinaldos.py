"""Cálculo manual de aguinaldos sobre remuneraciones brutas devengadas."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json

from datos import leer_datos, guardar_datos
from Funcionarios import RUTA_FUNCIONARIOS, separar_funcionario
from Liquidaciones import RUTA_LIQUIDACIONES, separar_liquidacion


RUTA_AGUINALDOS = Path(__file__).resolve().parent / "Datos" / "aguinaldos.txt"
MESES = (
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)


def _entero(valor, campo):
    texto = str(valor or "0").strip().replace(".", "").replace(",", "").replace(" ", "")
    if not texto:
        return 0
    if not texto.isdigit():
        raise ValueError(f"{campo} debe contener solo números.")
    return int(texto)


def listar_funcionarios():
    funcionarios = []
    for linea in leer_datos(RUTA_FUNCIONARIOS):
        funcionario = separar_funcionario(linea)
        if funcionario:
            funcionarios.append(funcionario)
    return sorted(funcionarios, key=lambda x: x["nombre"].casefold())


def _leer_registros():
    registros = []
    for linea in leer_datos(RUTA_AGUINALDOS):
        try:
            dato = json.loads(linea)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(dato, dict):
            registros.append(dato)
    return registros


def _guardar_registros(registros):
    guardar_datos(
        RUTA_AGUINALDOS,
        [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in registros],
    )


def obtener_meses(cedula, anio):
    anio = int(anio)
    guardados = {
        int(x["mes"]): x
        for x in _leer_registros()
        if x.get("cedula") == str(cedula) and int(x.get("anio", 0)) == anio
    }
    return [
        {
            "mes": mes,
            "basico": int(guardados.get(mes, {}).get("basico", 0)),
            "horas_extra": int(guardados.get(mes, {}).get("horas_extra", 0)),
            "comisiones": int(guardados.get(mes, {}).get("comisiones", 0)),
            "otros_remunerativos": int(
                guardados.get(mes, {}).get("otros_remunerativos", 0)
            ),
        }
        for mes in range(1, 13)
    ]


def guardar_meses(cedula, nombre, anio, meses):
    cedula = str(cedula).strip()
    nombre = str(nombre).strip()
    anio = int(anio)
    if anio < 2000 or anio > 2100:
        raise ValueError("El año no es válido.")

    nuevos = []
    for dato in meses:
        mes = int(dato["mes"])
        if mes < 1 or mes > 12:
            raise ValueError("El mes no es válido.")
        nuevos.append({
            "cedula": cedula,
            "nombre": nombre,
            "anio": anio,
            "mes": mes,
            "basico": _entero(dato.get("basico"), "Salario básico"),
            "horas_extra": _entero(dato.get("horas_extra"), "Horas extra"),
            "comisiones": _entero(dato.get("comisiones"), "Comisiones"),
            "otros_remunerativos": _entero(
                dato.get("otros_remunerativos"), "Otros remunerativos"
            ),
            "actualizado": datetime.now().isoformat(timespec="seconds"),
        })

    registros = [
        x for x in _leer_registros()
        if not (
            x.get("cedula") == cedula
            and int(x.get("anio", 0)) == anio
        )
    ]
    registros.extend(nuevos)
    _guardar_registros(registros)
    return calcular(meses)


def importar_desde_liquidaciones(cedula, anio, meses_actuales):
    """Completa meses vacíos usando bruto y comisiones ya liquidados.

    No resta IPS, adelantos, compras ni otros descuentos. Los reposos no se
    incorporan como concepto adicional. Los valores manuales existentes se respetan.
    """
    resultado = {int(x["mes"]): dict(x) for x in meses_actuales}
    for linea in leer_datos(RUTA_LIQUIDACIONES):
        liquidacion = separar_liquidacion(linea)
        if not liquidacion or liquidacion["cedula"] != str(cedula):
            continue
        try:
            mes, anio_liq = map(int, liquidacion["periodo"].split("-"))
        except (ValueError, AttributeError):
            continue
        if anio_liq != int(anio) or mes not in resultado:
            continue

        actual = resultado[mes]
        if not any(
            int(actual.get(campo, 0) or 0)
            for campo in ("basico", "horas_extra", "comisiones", "otros_remunerativos")
        ):
            sueldo_bruto = int(liquidacion.get("sueldo_bruto", 0))
            ausencias = int(liquidacion.get("descuento_ausencias", 0))
            reposos = int(liquidacion.get("descuento_reposos", 0))

            actual["basico"] = max(
            sueldo_bruto - ausencias - reposos,
            0,
        )
            actual["comisiones"] = int(
            liquidacion.get("comisiones", 0)
        )
    return [resultado[mes] for mes in range(1, 13)]


def calcular(meses):
    detalle = []
    total_anual = 0
    for dato in meses:
        total_mes = sum(
            _entero(dato.get(campo), campo)
            for campo in (
                "basico", "horas_extra", "comisiones", "otros_remunerativos"
            )
        )
        total_anual += total_mes
        detalle.append({"mes": int(dato["mes"]), "total": total_mes})

    return {
        "detalle": detalle,
        "total_remuneraciones": total_anual,
        "aguinaldo": total_anual // 12,
    }
