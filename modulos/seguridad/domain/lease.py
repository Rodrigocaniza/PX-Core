"""Lease offline: hasta cuando vale la ultima autorizacion conocida.

BC no puede depender de Internet para abrir. Una optica sin Caja porque se
cayo el modem es un dano peor que el que este slice previene. Entonces el
cliente guarda la ultima autorizacion valida y la sigue honrando por un plazo.

Tres plazos, en orden:

  * dentro del lease            ALLOW, sin ruido
  * vencido pero en gracia      ALLOW con aviso visible y auditoria
  * pasada la gracia            DENY, con los datos intactos

El estado se sella con un MAC derivado del secreto de instalacion. No es
confidencial —dice fechas, no secretos— pero tiene que ser inalterable: sin el
MAC, extender el lease seria editar un JSON.

Reloj: se guarda la marca de agua del instante mas alto que se vio. Atrasar el
reloj del sistema no devuelve tiempo de lease, porque las cuentas se hacen
contra `max(ahora, marca_de_agua)`. Adelantarlo tampoco sirve para nada util:
solo acelera el vencimiento.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from ..canonical import b64u_decode, b64u_encode, canonical_json
from ..crypto.primitives import mac, mac_equal
from ..errors import SecurityError
from .license import format_instant, parse_instant

LEASE_FORMAT = "bc.lease.v1"

# Tolerancia al desfase normal del reloj: sincronizacion horaria, cambio de
# huso, arranque con la pila de la placa gastada. Por debajo de esto no se
# denuncia manipulacion; con menos, un ajuste legitimo pareceria un ataque.
CLOCK_SKEW_TOLERANCE = timedelta(minutes=15)


class LeaseStateError(SecurityError):
    """El estado de lease no abre: falta, esta truncado o fue editado."""


@dataclass(frozen=True)
class LeaseState:
    installation_id: str
    license_id: str
    last_validated_at: datetime
    lease_expires_at: datetime
    grace_expires_at: datetime
    high_water_mark: datetime
    revocation_serial: int = 0
    security_schema_version: str = ""
    # Una vez que se supo que esta instalacion esta revocada, se queda sabido.
    # Si no, borrar el archivo de revocacion deshacia la revocacion.
    revoked_reason: str = ""

    # ----------------------------------------------------------------- reloj
    def observe(self, now: datetime) -> tuple["LeaseState", bool]:
        """Registra el instante actual y avisa si el reloj retrocedio.

        Devuelve el estado con la marca de agua actualizada y si hubo retroceso
        mas alla de la tolerancia. El estado se devuelve igual: no se "castiga"
        bajando nada, solo se deja de creerle al reloj.
        """
        rolled_back = now < self.high_water_mark - CLOCK_SKEW_TOLERANCE
        if now > self.high_water_mark:
            return replace(self, high_water_mark=now), False
        return self, rolled_back

    def effective_now(self, now: datetime) -> datetime:
        """El instante contra el que se decide. Nunca anterior a lo ya visto."""
        return max(now, self.high_water_mark)

    def within_lease(self, now: datetime) -> bool:
        return self.effective_now(now) <= self.lease_expires_at

    def within_grace(self, now: datetime) -> bool:
        return self.effective_now(now) <= self.grace_expires_at

    def remaining(self, now: datetime) -> timedelta:
        return self.lease_expires_at - self.effective_now(now)

    # ------------------------------------------------------------- serializado
    def to_document(self) -> dict[str, Any]:
        return {
            "format": LEASE_FORMAT,
            "installation_id": self.installation_id,
            "license_id": self.license_id,
            "last_validated_at": format_instant(self.last_validated_at),
            "lease_expires_at": format_instant(self.lease_expires_at),
            "grace_expires_at": format_instant(self.grace_expires_at),
            "high_water_mark": format_instant(self.high_water_mark),
            "revocation_serial": self.revocation_serial,
            "security_schema_version": self.security_schema_version,
            "revoked_reason": self.revoked_reason,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "LeaseState":
        if document.get("format") != LEASE_FORMAT:
            raise LeaseStateError("formato de lease desconocido")
        try:
            return cls(
                installation_id=str(document["installation_id"]),
                license_id=str(document["license_id"]),
                last_validated_at=parse_instant(document["last_validated_at"]),
                lease_expires_at=parse_instant(document["lease_expires_at"]),
                grace_expires_at=parse_instant(document["grace_expires_at"]),
                high_water_mark=parse_instant(document["high_water_mark"]),
                revocation_serial=int(document.get("revocation_serial", 0)),
                security_schema_version=str(document.get("security_schema_version", "")),
                revoked_reason=str(document.get("revoked_reason", "")),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise LeaseStateError("estado de lease incompleto") from error

    def seal(self, lease_key: bytes) -> dict[str, Any]:
        document = self.to_document()
        return {
            "format": LEASE_FORMAT,
            "payload": document,
            "mac": b64u_encode(mac(lease_key, canonical_json(document))),
        }

    @classmethod
    def open_sealed(cls, envelope: Mapping[str, Any], lease_key: bytes) -> "LeaseState":
        if not isinstance(envelope, Mapping) or "payload" not in envelope or "mac" not in envelope:
            raise LeaseStateError("sobre de lease incompleto")
        document = envelope["payload"]
        try:
            presented = b64u_decode(str(envelope["mac"]))
        except (ValueError, TypeError) as error:
            raise LeaseStateError("MAC de lease ilegible") from error
        if not mac_equal(presented, mac(lease_key, canonical_json(document))):
            raise LeaseStateError("el estado de lease fue modificado")
        return cls.from_document(document)


def start(
    *,
    installation_id: str,
    license_id: str,
    validated_at: datetime,
    lease_days: int,
    grace_days: int,
    revocation_serial: int,
    security_schema_version: str,
    previous: "LeaseState | None" = None,
) -> LeaseState:
    """Lease nuevo tras una validacion exitosa contra el emisor.

    La marca de agua se hereda del lease anterior si era mas alta: renovar no
    puede ser una forma de olvidar que ya se vio una fecha posterior.
    El serial de revocacion nunca baja, por el mismo motivo.
    """
    if validated_at.tzinfo is None:
        raise ValueError("la validacion necesita un instante con zona")
    validated_at = validated_at.astimezone(timezone.utc)
    high_water = validated_at
    serial = revocation_serial
    revoked_reason = ""
    if previous is not None:
        high_water = max(high_water, previous.high_water_mark)
        serial = max(serial, previous.revocation_serial)
        revoked_reason = previous.revoked_reason
    lease_expires = validated_at + timedelta(days=lease_days)
    return LeaseState(
        installation_id=installation_id,
        license_id=license_id,
        last_validated_at=validated_at,
        lease_expires_at=lease_expires,
        grace_expires_at=lease_expires + timedelta(days=grace_days),
        high_water_mark=high_water,
        revocation_serial=serial,
        security_schema_version=security_schema_version,
        revoked_reason=revoked_reason,
    )
