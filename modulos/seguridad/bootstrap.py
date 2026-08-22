"""Punto unico de arranque de la seguridad, para BC Caja y para lo que venga.

Una sola funcion, `arrancar`, con una regla que gobierna todo:

    **Una instalacion sin enrolar funciona exactamente como antes.**

Esa es la condicion para poder instalar esto sin cortar la operacion. Enrolar
es un acto explicito; hasta que ocurra, `arrancar` devuelve "no aplica", no
activa ningun cifrador y BC abre como abria ayer.

Cuando SI hay enrolamiento, la decision manda:

    ALLOW        abre normal
    ALLOW_GRACE  abre, con un aviso que quien opera tiene que ver
    DENY         no abre, y la base queda intacta

Lo que nunca hace: borrar, truncar ni migrar nada. Un DENY es una puerta
cerrada, no una demolicion — la mision lo pide y es lo unico que hace que el
rollback siga siendo posible.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import runtime
from .application import enrollment, keyring, verifier
from .application.field_protection import FieldCipher
from .application.verifier import VerificationContext
from .domain import decisions
from .domain.decisions import AuthorizationDecision
from .errors import KeyringError, SecurityError
from .infrastructure import fingerprint as fingerprint_module
from .infrastructure import security_db
from .infrastructure.dpapi import default_sealer
from .infrastructure.store import SecurityPaths, resolve_security_paths

# Motivo propio para "no hay nada instalado". No es un DENY: es que esta capa
# todavia no gobierna esta instalacion.
NOT_APPLICABLE = "NO_APLICA"


@dataclass(frozen=True)
class SecurityStartup:
    """Resultado del arranque. Lo consume la UI para decidir que mostrar."""

    enrolled: bool
    decision: AuthorizationDecision | None
    cipher: FieldCipher | None
    data_protected: bool

    @property
    def allowed(self) -> bool:
        return not self.enrolled or (self.decision is not None and self.decision.allowed)

    @property
    def degraded(self) -> bool:
        return self.decision is not None and self.decision.degraded

    @property
    def message(self) -> str:
        """Texto para quien opera. Sin jerga y sin nombrar archivos internos."""
        if not self.enrolled:
            return ""
        assert self.decision is not None
        if self.decision.outcome == decisions.ALLOW:
            return ""
        if self.decision.outcome == decisions.ALLOW_GRACE:
            return (
                "La autorizacion de esta PC esta por vencer. BC sigue funcionando, "
                "pero hay que renovarla antes de que termine el plazo de gracia."
            )
        return _MENSAJES_DE_DENEGACION.get(
            self.decision.reason,
            "Esta copia de BC no esta autorizada para funcionar en esta computadora.",
        )


_MENSAJES_DE_DENEGACION = {
    decisions.REASON_BINDING_MISMATCH: (
        "Esta instalacion de BC pertenece a otra computadora. Copiar la carpeta no "
        "habilita una PC nueva: hay que instalarla y autorizarla."
    ),
    decisions.REASON_SECRET_UNAVAILABLE: (
        "Esta instalacion de BC pertenece a otra computadora. Copiar la carpeta no "
        "habilita una PC nueva: hay que instalarla y autorizarla."
    ),
    decisions.REASON_INSTALLATION_MISMATCH: (
        "La autorizacion instalada corresponde a otra instalacion de BC."
    ),
    decisions.REASON_BAD_SIGNATURE: (
        "La autorizacion de esta PC esta danada o fue modificada. Hay que reponerla."
    ),
    decisions.REASON_LICENSE_UNREADABLE: (
        "La autorizacion de esta PC esta danada o fue modificada. Hay que reponerla."
    ),
    decisions.REASON_NOT_ENROLLED: (
        "Esta base de datos pertenece a otra instalacion de BC. Copiar el archivo no "
        "habilita una PC nueva: hay que instalar BC ahi y autorizarla."
    ),
    decisions.REASON_NO_LICENSE: (
        "Esta PC esta enrolada pero todavia no tiene autorizacion instalada."
    ),
    decisions.REASON_REVOKED: (
        "La autorizacion de esta PC fue dada de baja."
    ),
    decisions.REASON_EXPIRED: (
        "La autorizacion de esta PC vencio y hay que renovarla."
    ),
    decisions.REASON_LEASE_EXPIRED: (
        "Hace demasiado tiempo que esta PC no renueva su autorizacion. "
        "Hay que reponerla para seguir usando BC."
    ),
}


def build_context(
    database_path: str | Path | None,
    *,
    paths: SecurityPaths | None = None,
    sealer: Any = None,
    fingerprint: Any = None,
    now: Any = None,
) -> VerificationContext:
    return VerificationContext(
        paths=paths or resolve_security_paths(),
        sealer=sealer if sealer is not None else default_sealer(),
        fingerprint=fingerprint if fingerprint is not None else fingerprint_module.collect(),
        database_path=Path(database_path) if database_path is not None else None,
        now=now,
    )


def _base_protegida(database_path: Path | None) -> bool:
    """Si la base que se va a abrir ya tiene clave de datos, sea de quien sea."""
    if database_path is None or not Path(database_path).is_file():
        return False
    try:
        return security_db.tables_present(database_path) and keyring.protection_configured(
            database_path
        )
    except SecurityError:
        # Una base que no se puede interrogar se trata como protegida: la duda
        # se resuelve del lado que no arruina datos.
        return True


def arrancar(context: VerificationContext) -> SecurityStartup:
    """Decide, y si corresponde deja el cifrador de datos activo para esta base."""
    if not enrollment.is_enrolled(context.paths):
        # Sin enrolar, BC abre como abria siempre... salvo que la base que le
        # dieron ya este protegida. Ese caso es el pendrive con solo el
        # `bc_caja.sqlite3` adentro: sin este control, BC abriria contento,
        # mostraria criptograma en pantalla y —lo peor— empezaria a guardar
        # datos nuevos en claro al lado de los viejos cifrados, arruinando la
        # base sin que nadie se entere hasta mucho despues.
        if _base_protegida(context.database_path):
            return SecurityStartup(
                enrolled=True,
                decision=AuthorizationDecision.deny(
                    decisions.REASON_NOT_ENROLLED,
                    "esta base pertenece a una instalacion de BC que no es esta",
                ),
                cipher=None,
                data_protected=True,
            )
        return SecurityStartup(
            enrolled=False, decision=None, cipher=None, data_protected=False
        )

    decision = verifier.authorize(context)
    if not decision.allowed or context.database_path is None:
        return SecurityStartup(
            enrolled=True, decision=decision, cipher=None, data_protected=False
        )

    cipher = None
    protected = False
    # `protection_configured` y no `has_data_key`: lo que define si hay que
    # abrir la clave es que esta base este cifrada, no que la envoltura de hoy
    # siga activa. Con la envoltura desactivada BC tiene que denegar, no abrir
    # sin cifrador sobre datos cifrados.
    if security_db.tables_present(context.database_path) and keyring.protection_configured(
        context.database_path
    ):
        try:
            secret = enrollment.open_secret(
                context.paths, context.sealer, context.fingerprint
            )
            data_key = keyring.open_with_installation(context.database_path, secret)
        except (SecurityError, KeyringError) as error:
            # Autorizado pero sin poder abrir la clave de datos. Abrir igual
            # mostraria criptograma en pantalla y —peor— guardaria datos nuevos
            # en claro al lado de los viejos cifrados. Se deniega, y los datos
            # quedan enteros esperando la frase de recuperacion.
            return SecurityStartup(
                enrolled=True,
                decision=AuthorizationDecision.deny(
                    decisions.REASON_SECRET_UNAVAILABLE,
                    f"la clave de datos no se pudo abrir: {error}",
                    installation_id=decision.installation_id,
                    license_id=decision.license_id,
                ),
                cipher=None,
                data_protected=True,
            )
        cipher = FieldCipher(key=data_key.raw, dek_id=data_key.dek_id)
        runtime.activate(context.database_path, cipher)
        protected = True

    return SecurityStartup(
        enrolled=True, decision=decision, cipher=cipher, data_protected=protected
    )
