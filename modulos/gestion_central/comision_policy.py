"""Política canónica de comisión: 1% general, aprobada, versionada y con vigencia.

Vive en su propio módulo porque la migración del repositorio necesita exactamente las
mismas constantes que el cálculo, y `comisiones.py` ya depende del repositorio: dejarla
aquí evita el ciclo y da a la regla aprobada un único lugar donde leerse.

Todo el cálculo monetario es `Decimal` con redondeo `ROUND_HALF_UP` a guaraní entero.
No se usan floats en ningún punto.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

BASIS_POINTS = 10_000
CURRENCY = "GS"
ROUNDING_MODE = "HALF_UP"

# Regla aprobada 4: el convenio deduce exactamente 5% del total antes de comisionar.
AGREEMENT_DISCOUNT_BP = 500

# ------------------------------------------------------------------ decisión aprobada
# Porcentaje general de comisión: 1%, idéntico para toda vendedora y todo local.
CANONICAL_RATE_BP = 100
CANONICAL_SCOPE = "GENERAL"
CANONICAL_CODE = "COMISION_GENERAL_1PCT"
CANONICAL_VERSION = 1
# Vigencia: la política rige para las liquidaciones cuyo período no es anterior a esta fecha.
CANONICAL_EFFECTIVE_FROM = "2026-08-01"
CANONICAL_POLICY_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "bc-comision-politica:GENERAL:"))

# ------------------------------------------------------------------ boundary económico
# Estados en los que una liquidación es un **hecho económico oficial**: alguien comprometió
# dinero sobre un importe concreto. Sólo estos fijan la tasa de un período, y sólo mientras
# alguno siga vivo la sostienen.
#
# Vive aquí, y no en `comisiones.py`, porque el cálculo en caliente y la migración del
# repositorio tienen que usar exactamente el mismo predicado: que la constante gobernara sólo
# al primero y el segundo repitiera la lista a mano fue una observación del Librarian sobre la
# generación 6. `BOUNDARY_SQL_IN` existe para que ni siquiera el SQL pueda divergir.
RATING_BOUNDARY_STATES = ("APROBADA", "PAGADA")
BOUNDARY_SQL_IN = "(" + ",".join(f"'{state}'" for state in RATING_BOUNDARY_STATES) + ")"

# Estados de política que puede llevar una liquidación.
POLICY_CANONICAL = "CANONICA_APROBADA"
POLICY_OUT_OF_EFFECT = "FUERA_DE_VIGENCIA"
POLICY_LEGACY = "POLITICA_HISTORICA_PREVIA"
POLICY_ABSENT = "SIN_POLITICA_APLICADA"
POLICY_STATUSES = (POLICY_CANONICAL, POLICY_OUT_OF_EFFECT, POLICY_LEGACY, POLICY_ABSENT)

# Etiquetas del piloto anterior que la migración retira. Ya no las produce ningún código.
RETIRED_POLICY_STATUSES = ("SINTETICA_PENDIENTE_APROBACION", "SIN_POLITICA_CONFIGURADA")

# ------------------------------------------------------- hecho económico oficial vivo
# Predicado **completo** de vitalidad, en un solo sitio. Espera los alias `e` para
# `commission_entries` y `s` para `commission_sales`.
#
# Un hecho está vivo si hoy sostiene la tasa de su período: lleva la política canónica con una
# tasa concreta, y o bien conserva `paid_at` —el dinero salió— o bien está en el boundary sobre
# una venta que no fue anulada.
#
# El filtro de política **no es opcional ni decorativo**. Una liquidación con
# `POLITICA_HISTORICA_PREVIA` no es un hecho oficial en ninguna otra parte del módulo: el reporte
# la excluye de `commission_amount` y la cuenta aparte en `non_official_amount`, el desglose
# escribe «no es pagable con este importe», y la migración jamás la usa para sembrar. Su importe
# se conserva intacto por auditoría, pero nunca fue la tasa oficial de su mes y no puede sostenerla.
#
# Que este predicado viviera repartido en dos SQL —uno con el filtro de política y otro sin él—
# fue el bloqueante `AB1-g7`: una comisión ya pagada del piloto era invisible para la siembra y
# a la vez sostenía el pin en caliente, de modo que el mes no podía soltarse nunca y volvía a
# pagar mal por las mismas cuatro rutas de `AB1-g6`. Unificar la lista de estados no bastaba,
# porque la parte que decidía era justamente la que no coincidía.
LIVE_OFFICIAL_FACT_SQL = (
    "e.rate_bp IS NOT NULL AND e.policy_status = '" + POLICY_CANONICAL + "'"
    " AND (e.paid_at IS NOT NULL"
    "      OR (e.status IN " + BOUNDARY_SQL_IN + " AND COALESCE(s.voided,0) = 0))"
)
# El período de una liquidación es siempre AAAA-MM, pero una base de procedencia externa puede
# traer una fecha completa. La clave del período se deriva de **una sola expresión**, que es la que
# usan tanto el filtro por período como el agrupamiento de la migración: agrupar en Python con
# `str(period)[:7]` era un segundo texto equivalente, y ésos ya fallaron dos veces.
PERIOD_KEY_SQL = "substr(e.period,1,7)"
PERIOD_MATCH_SQL = PERIOD_KEY_SQL + " = ?"


def period_key(value) -> str:
    """Clave del período, en Python. El equivalente exacto de `PERIOD_KEY_SQL`.

    `str(x)[:7]` estaba escrito ocho veces repartidas por tres módulos. Todas normalizaban el
    **argumento**, que es idempotente e inocuo; la que normalizaba el **dato** era una sola y
    costó la observación `O3` de la generación 9. Tenerla con nombre evita que la próxima vez
    haya que averiguar cuál de las nueve era la que decidía.
    """
    return str(value or "")[:7]

# Columnas que describen un hecho vivo. Las necesitan por igual quien resuelve en caliente y quien
# siembra, así que se declaran una vez.
LIVE_FACT_COLUMNS = (
    "e.id, e.sale_id, e.period, e.rate_bp, e.policy_code, e.policy_version,"
    " e.policy_effective_from, e.policy_scope, e.status, e.paid_at, e.created_at"
)


def live_official_facts_sql() -> str:
    """Consulta de hechos vivos de un período: una sola, columnas y clave incluidas.

    Que la siembra y el código en caliente compartieran el `WHERE` pero no la consulta entera
    dejaba el agrupamiento duplicado. Aquí no queda nada que separar. La variante global —sin
    filtro por período— existía y no la usaba nadie: se retiró.
    """
    return (
        f"SELECT {LIVE_FACT_COLUMNS}, {PERIOD_KEY_SQL} AS period_key"
        f"  FROM commission_entries e JOIN commission_sales s ON s.id = e.sale_id"
        f" WHERE {PERIOD_MATCH_SQL} AND {LIVE_OFFICIAL_FACT_SQL}"
        f" ORDER BY {PERIOD_KEY_SQL}, e.created_at, e.id"
    )


# Resultado de resolver la tasa de un período. `AMBIGUOUS` no es «no hay tasa»: es «hay más de una
# y elegir sería decidir por el propietario», que se trata distinto en la auditoría.
PERIOD_RATE_AMBIGUOUS = "AMBIGUOUS"


def resolve_period_rate(facts):
    """**Única** regla que decide qué tasa tiene un período a partir de sus hechos vivos.

    Devuelve el hecho que la sostiene, `None` si no hay ninguno, o `PERIOD_RATE_AMBIGUOUS` si los
    hechos vivos llevan tasas distintas.

    Un pago manda sobre una aprobación —es el hecho más fuerte del mes— y a igualdad de fuerza gana
    el más antiguo, para que el resultado no dependa del orden de lectura. **Ese orden no decide la
    tasa**: cuando se llega a él, la ambigüedad ya se descartó y todos los hechos llevan la misma.
    Decide qué liquidación se cita como causa del `PINNED`, que es lo que hace legible el libro.

    Que esta pregunta se contestara con **dos** reglas fue el bloqueante `AB1-g8`: la siembra exigía
    coherencia de tasa y se abstenía si no la había, mientras que la reconciliación en caliente
    retenía la fijación con cualquier hecho vivo, llevara la tasa que llevara. El resultado era un
    pin que ninguno de sus hechos justificaba y que nada podía retirar. La regla del propietario
    dice que el período sigue fijado mientras exista un hecho vivo **que justifique ese pin**: un
    hecho a otra tasa no lo justifica.
    """
    if not facts:
        return None
    if len({int(fact["rate_bp"]) for fact in facts}) > 1:
        return PERIOD_RATE_AMBIGUOUS
    return sorted(facts, key=lambda fact: (
        fact["paid_at"] is None and fact["status"] != "PAGADA",
        str(fact["created_at"]), str(fact["id"])))[0]


def quantize_guarani(value: Decimal) -> int:
    """Redondea a guaraní entero con HALF_UP: la política de redondeo es explícita."""
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def apply_basis_points(amount: int, points: int) -> int:
    """Aplica puntos básicos sobre un importe entero con Decimal y HALF_UP.

    La precisión ampliada garantiza que el cociente por 10.000 sea exacto antes de
    redondear: el único redondeo del cálculo es el HALF_UP final.
    """
    with localcontext() as context:
        context.prec = 60
        return quantize_guarani(Decimal(int(amount)) * Decimal(int(points)) / Decimal(BASIS_POINTS))


def agreement_discount(total: int) -> int:
    """Descuento del convenio: exactamente 5% del total de la venta."""
    return apply_basis_points(total, AGREEMENT_DISCOUNT_BP)


def commissionable_base(kind: str, total: int) -> int:
    """Base comisionable: total para venta común, total − 5% para convenio."""
    if kind == "CONVENIO":
        return int(total) - agreement_discount(total)
    return int(total)


def commission_for(base: int, rate_bp: int) -> int:
    """Comisión oficial sobre la base ya resuelta."""
    return apply_basis_points(base, rate_bp)


def rate_decimal_text(rate_bp: int) -> str:
    """Porcentaje en forma de dato estable para exportar: `100` → `"1.00"`."""
    with localcontext() as context:
        context.prec = 60
        return f"{Decimal(int(rate_bp)) / Decimal(100):.2f}"


def rate_percent_text(rate_bp: int) -> str:
    """Porcentaje en forma legible para pantalla: `100` → `"1,00%"`."""
    return rate_decimal_text(rate_bp).replace(".", ",") + "%"


def normalize_effective_from(value: str) -> str:
    """Una vigencia mal formada nunca entra: define desde cuándo se paga dinero."""
    text = str(value).strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as error:
        raise ValueError(
            f"vigencia inválida: se espera AAAA-MM-DD, se recibió {text!r}"
        ) from error


def is_in_effect(period: str | None, effective_from: str) -> bool:
    """Rige para el período de liquidación que no es anterior al mes de vigencia."""
    if not period:
        return False
    return str(period)[:7] >= str(effective_from)[:7]


@dataclass(frozen=True)
class PolicyDecision:
    """Qué porcentaje se aplicó, con qué versión y bajo qué vigencia.

    Es lo que queda grabado en la liquidación: la trazabilidad no se reconstruye
    después, se guarda en el momento del cálculo.
    """

    rate_bp: int | None
    status: str
    version: int | None
    effective_from: str | None
    scope: str
    code: str | None

    @property
    def applies(self) -> bool:
        return self.rate_bp is not None

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "scope": self.scope,
            "status": self.status,
            "version": self.version,
            "effective_from": self.effective_from,
            "rate_bp": self.rate_bp,
            "rate_percent": None if self.rate_bp is None else rate_decimal_text(self.rate_bp),
            "rounding": ROUNDING_MODE,
            "currency": CURRENCY,
        }


def canonical_seed() -> dict:
    """Fila de política que la migración deja instalada en toda base."""
    return {
        "id": CANONICAL_POLICY_ID,
        "scope": CANONICAL_SCOPE,
        "scope_value": "",
        "rate_bp": CANONICAL_RATE_BP,
        "approval_status": POLICY_CANONICAL,
        "code": CANONICAL_CODE,
        "version": CANONICAL_VERSION,
        "effective_from": CANONICAL_EFFECTIVE_FROM,
    }
