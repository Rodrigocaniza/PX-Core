"""El veredicto de autorizacion y su vocabulario de motivos.

Un booleano no alcanza. "No arranca" y "no arranca porque la licencia vence en
tres dias y hace un mes que no hay Internet" piden acciones distintas de quien
opera, y la auditoria necesita el motivo con nombre estable para que buscar
"intento de clon" en seis meses siga encontrando algo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

ALLOW = "ALLOW"
ALLOW_GRACE = "ALLOW_GRACE"
DENY = "DENY"

# Motivos. Son identificadores, no textos para pantalla: se escriben en la
# auditoria y se comparan en pruebas, asi que cambiarlos rompe historia.
REASON_OK = "OK"
REASON_LEASE_VALID = "LEASE_VALIDO"
REASON_NOT_ENROLLED = "SIN_ENROLAR"
REASON_NO_LICENSE = "SIN_LICENCIA"
REASON_LICENSE_UNREADABLE = "LICENCIA_ILEGIBLE"
REASON_BAD_SIGNATURE = "FIRMA_INVALIDA"
REASON_UNKNOWN_ISSUER = "EMISOR_DESCONOCIDO"
REASON_INSTALLATION_MISMATCH = "LICENCIA_DE_OTRA_INSTALACION"
REASON_BINDING_MISMATCH = "MAQUINA_DISTINTA"
REASON_SECRET_UNAVAILABLE = "SECRETO_NO_RECUPERABLE"
REASON_EXPIRED = "LICENCIA_VENCIDA"
REASON_LEASE_EXPIRED = "LEASE_VENCIDO"
REASON_LEASE_GRACE = "LEASE_EN_GRACIA"
REASON_REVOKED = "REVOCADA"
REASON_CLOCK_ROLLBACK = "RELOJ_ATRASADO"
REASON_SCHEMA_UNSUPPORTED = "ESQUEMA_NO_SOPORTADO"
REASON_STATE_TAMPERED = "ESTADO_MANIPULADO"


@dataclass(frozen=True)
class AuthorizationDecision:
    """Veredicto completo. Inmutable: nadie lo "corrige" aguas abajo."""

    outcome: str
    reason: str
    detail: str = ""
    installation_id: str = ""
    license_id: str = ""
    capabilities: tuple[str, ...] = ()
    lease_expires_at: datetime | None = None
    grace_expires_at: datetime | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        """Grace es ALLOW: la Optica sigue trabajando. La diferencia es el aviso."""
        return self.outcome in (ALLOW, ALLOW_GRACE)

    @property
    def degraded(self) -> bool:
        return self.outcome == ALLOW_GRACE

    def allows(self, capability: str) -> bool:
        return self.allowed and capability in self.capabilities

    def audit_details(self) -> dict[str, Any]:
        """Lo que va a la bitacora. Por construccion no incluye claves ni secretos.

        `evidence` solo lleva nombres de componentes y conteos — nunca valores
        de huella, nunca material derivado.
        """
        return {
            "outcome": self.outcome,
            "reason": self.reason,
            "detail": self.detail,
            "license_id": self.license_id,
            "capabilities": list(self.capabilities),
            "lease_expires_at": self.lease_expires_at.isoformat() if self.lease_expires_at else None,
            "evidence": dict(self.evidence),
        }

    @classmethod
    def deny(cls, reason: str, detail: str = "", **extra: Any) -> "AuthorizationDecision":
        return cls(outcome=DENY, reason=reason, detail=detail, **extra)
