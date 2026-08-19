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
