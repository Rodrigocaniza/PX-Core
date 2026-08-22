"""El verificador: decide si esta instalacion puede abrir, y lo deja escrito.

Es el corazon del slice. Todo lo demas —identidad, sellado, licencia, lease,
revocacion— existe para que esta funcion pueda decir ALLOW o DENY con
fundamento.

El orden de los controles no es casual. Va de lo barato y lo que no depende de
nadie hacia lo caro, y sobre todo va de lo que da un motivo preciso hacia lo
que da uno generico. Si la carpeta entera aparecio en otra PC, queremos que la
auditoria diga MAQUINA_DISTINTA —que es la verdad y es accionable— y no
SECRETO_NO_RECUPERABLE, que tambien seria cierto pero explica menos.

  1. enrolada
  2. licencia presente y legible
  3. emisor conocido        (el key_id esta en el almacen del paquete)
  4. firma valida           (ni un byte cambiado)
  5. version de esquema soportada
  6. la licencia nombra ESTA instalacion
  7. el binding corresponde a ESTA maquina
  8. el secreto local se puede abrir   <- la barrera dura contra el clon
  9. revocacion
 10. vencimiento de la licencia
 11. lease y reloj

Los pasos 7 y 8 son independientes a proposito: el 7 se puede falsificar
editando archivos, el 8 no. Que el 7 exista igual es lo que convierte un clon
en un evento con nombre en la bitacora en vez de en un fallo generico.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import SECURITY_SCHEMA_VERSION
from ..crypto.primitives import public_key_from_bytes, verify
from ..domain import decisions, lease as lease_module
from ..domain.decisions import AuthorizationDecision
from ..domain.lease import LeaseState
from ..domain.license import SignedLicense, SignedRevocationList
from ..errors import (
    LicenseFormatError,
    NotEnrolledError,
    SealedStoreError,
    SecurityError,
    SignatureError,
    TrustStoreError,
)
from ..infrastructure import fingerprint as fingerprint_module
from ..infrastructure import security_db
from ..infrastructure.fingerprint import MachineFingerprint
from ..infrastructure.store import SecurityPaths, read_json
from ..trust import TrustStore, load as load_trust
from . import enrollment


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


@dataclass
class VerificationContext:
    """Todo lo que hace falta para decidir. Se arma explicito para poder simularlo."""

    paths: SecurityPaths
    sealer: Any
    fingerprint: MachineFingerprint
    database_path: Path | None = None
    trust: TrustStore | None = None
    now: datetime | None = None

    def instant(self) -> datetime:
        return self.now or utc_now()

    def trust_store(self) -> TrustStore:
        if self.trust is None:
            self.trust = load_trust()
        return self.trust


def load_license(paths: SecurityPaths) -> SignedLicense | None:
    envelope = read_json(paths.license)
    if envelope is None:
        return None
    return SignedLicense.from_envelope(envelope)


def load_revocations(paths: SecurityPaths) -> SignedRevocationList | None:
    envelope = read_json(paths.revocations)
    if envelope is None:
        return None
    return SignedRevocationList.from_envelope(envelope)


def _verify_signature(trust: TrustStore, key_id: str, signature: bytes, message: bytes) -> None:
    issuer = trust.find(key_id)
    if issuer is None:
        raise TrustStoreError("el emisor no esta en el almacen de confianza del paquete")
    verify(public_key_from_bytes(issuer.public_key), signature, message)


def verify_license(trust: TrustStore, signed: SignedLicense) -> None:
    """Firma sobre el payload canonico. Un byte distinto y no verifica."""
    if signed.key_id != signed.payload.issuer_key_id:
        # El sobre y el documento tienen que nombrar al mismo emisor. Si no,
        # alguien cambio uno de los dos y la firma podria verificar igual.
        raise SignatureError("el sobre y el documento nombran emisores distintos")
    _verify_signature(trust, signed.key_id, signed.signature, signed.signed_bytes())


def verify_revocations(trust: TrustStore, signed: SignedRevocationList) -> None:
    _verify_signature(trust, signed.key_id, signed.signature, signed.signed_bytes())


# --------------------------------------------------------------------------
# Lease: dos copias, la que manda es la mas avanzada
# --------------------------------------------------------------------------
def _read_lease(context: VerificationContext, lease_key: bytes) -> LeaseState | None:
    """Lee el lease de la base y del archivo, y se queda con el mas conservador.

    Estan los dos porque cada uno tapa un agujero del otro: borrar el archivo
    no resetea el lease porque esta en la base, y restaurar una base vieja no
    lo resetea porque esta en el archivo. Se toma el de validacion mas
    reciente, y de los dos la marca de agua mas alta y el serial de revocacion
    mas alto — nunca se pierde tiempo ya visto ni una revocacion ya conocida.
    """
    candidates: list[LeaseState] = []
    if context.database_path is not None and security_db.tables_present(context.database_path):
        document = security_db.read_state(context.database_path, security_db.STATE_LEASE, lease_key)
        if document is not None:
            candidates.append(LeaseState.from_document(document))
    envelope = read_json(context.paths.lease)
    if envelope is not None:
        candidates.append(LeaseState.open_sealed(envelope, lease_key))
    if not candidates:
        return None
    chosen = max(candidates, key=lambda state: state.last_validated_at)
    return LeaseState(
        installation_id=chosen.installation_id,
        license_id=chosen.license_id,
        last_validated_at=chosen.last_validated_at,
        lease_expires_at=chosen.lease_expires_at,
        grace_expires_at=chosen.grace_expires_at,
        high_water_mark=max(state.high_water_mark for state in candidates),
        revocation_serial=max(state.revocation_serial for state in candidates),
        security_schema_version=chosen.security_schema_version,
        # Alcanza con que UNA de las dos copias sepa de la revocacion: borrar
        # la otra no la desconoce.
        revoked_reason=next(
            (state.revoked_reason for state in candidates if state.revoked_reason), ""
        ),
    )


def _write_lease(context: VerificationContext, state: LeaseState, lease_key: bytes) -> None:
    from ..infrastructure.store import write_json

    write_json(context.paths.lease, state.seal(lease_key))
    if context.database_path is not None and security_db.tables_present(context.database_path):
        security_db.write_state(
            context.database_path, security_db.STATE_LEASE, state.to_document(), lease_key
        )


# --------------------------------------------------------------------------
# La decision
# --------------------------------------------------------------------------
def authorize(context: VerificationContext, *, record: bool = True) -> AuthorizationDecision:
    decision = _decide(context)
    if record and context.database_path is not None:
        try:
            if security_db.tables_present(context.database_path):
                security_db.record_event(
                    context.database_path,
                    event=security_db.EVENT_AUTHORIZATION,
                    outcome=decision.outcome,
                    reason=decision.reason,
                    installation_id=decision.installation_id,
                    details=decision.audit_details()["evidence"],
                )
        except SecurityError:
            # Auditar es importante; impedir que la optica abra porque no se
            # pudo auditar, no. El veredicto ya esta tomado.
            pass
    return decision


def _decide(context: VerificationContext) -> AuthorizationDecision:
    # 1. enrolada
    try:
        identity = enrollment.load_identity(context.paths)
    except NotEnrolledError:
        return AuthorizationDecision.deny(
            decisions.REASON_NOT_ENROLLED, "esta instalacion todavia no fue enrolada"
        )
    except SecurityError as error:
        return AuthorizationDecision.deny(
            decisions.REASON_STATE_TAMPERED, str(error)
        )

    installation_id = identity.installation_id

    # 2. licencia presente y legible
    try:
        signed = load_license(context.paths)
    except (SecurityError, LicenseFormatError) as error:
        return AuthorizationDecision.deny(
            decisions.REASON_LICENSE_UNREADABLE, str(error), installation_id=installation_id
        )
    if signed is None:
        return AuthorizationDecision.deny(
            decisions.REASON_NO_LICENSE,
            "no hay licencia instalada para esta instalacion",
            installation_id=installation_id,
        )

    # 3 y 4. emisor conocido y firma valida
    try:
        trust = context.trust_store()
        verify_license(trust, signed)
    except TrustStoreError as error:
        return AuthorizationDecision.deny(
            decisions.REASON_UNKNOWN_ISSUER, str(error), installation_id=installation_id,
            license_id=signed.payload.license_id,
        )
    except SignatureError as error:
        return AuthorizationDecision.deny(
            decisions.REASON_BAD_SIGNATURE, str(error), installation_id=installation_id,
            license_id=signed.payload.license_id,
        )

    payload = signed.payload

    # 5. version de esquema
    if payload.security_schema_version != SECURITY_SCHEMA_VERSION:
        return AuthorizationDecision.deny(
            decisions.REASON_SCHEMA_UNSUPPORTED,
            f"la licencia declara {payload.security_schema_version}",
            installation_id=installation_id, license_id=payload.license_id,
            evidence={"esquema_licencia": payload.security_schema_version,
                      "esquema_cliente": SECURITY_SCHEMA_VERSION},
        )

    # 6. la licencia nombra esta instalacion
    if payload.installation_id != installation_id:
        return AuthorizationDecision.deny(
            decisions.REASON_INSTALLATION_MISMATCH,
            "la licencia fue emitida para otra instalacion",
            installation_id=installation_id, license_id=payload.license_id,
        )

    # 7. el binding corresponde a esta maquina
    observed = context.fingerprint.hashed(installation_id)
    match = fingerprint_module.compare(
        payload.binding, observed, secondary_required=payload.secondary_required
    )
    evidence = {
        "componentes_coinciden": list(match.matched),
        "componentes_difieren": list(match.mismatched),
        "componentes_ausentes": list(match.missing),
        "secundarios_exigidos": match.secondary_required,
        "secundarios_coinciden": match.secondary_matched,
    }
    if not match.ok:
        return AuthorizationDecision.deny(
            decisions.REASON_BINDING_MISMATCH,
            "la maquina no es la que la licencia autoriza",
            installation_id=installation_id, license_id=payload.license_id, evidence=evidence,
        )

    # 8. el secreto local abre. Aca es donde una copia deja de servir.
    try:
        secret = enrollment.open_secret(context.paths, context.sealer, context.fingerprint)
    except (SealedStoreError, NotEnrolledError) as error:
        return AuthorizationDecision.deny(
            decisions.REASON_SECRET_UNAVAILABLE, str(error),
            installation_id=installation_id, license_id=payload.license_id, evidence=evidence,
        )

    lease_key = secret.lease_key()

    # 9. revocacion
    try:
        revocations = load_revocations(context.paths)
    except (SecurityError, LicenseFormatError) as error:
        return AuthorizationDecision.deny(
            decisions.REASON_LICENSE_UNREADABLE, f"lista de revocacion: {error}",
            installation_id=installation_id, license_id=payload.license_id, evidence=evidence,
        )

    try:
        previous = _read_lease(context, lease_key)
    except SecurityError as error:
        # Fail-safe: un estado ilegible NO borra ni bloquea. Se descarta y se
        # arranca uno nuevo, con la perdida acotada de tiempo de lease ya
        # transcurrido, y queda escrito que paso.
        previous = None
        evidence["estado_de_lease"] = f"descartado: {error}"

    known_serial = previous.revocation_serial if previous else 0

    # Por defecto vale lo que ya se sabia: una revocacion conocida no se olvida
    # porque despues borren `revocations.bcrl`. Solo una lista **mas nueva** que
    # la ultima conocida puede cambiar ese estado, en cualquiera de los dos
    # sentidos — y esto ultimo importa: sin la posibilidad de desrevocar, una
    # instalacion revocada por error quedaria muerta para siempre y la unica
    # salida seria borrar la base, que es lo contrario de lo que queremos.
    revoked_reason = previous.revoked_reason if previous else ""

    if revocations is not None:
        try:
            verify_revocations(context.trust_store(), revocations)
        except (SignatureError, TrustStoreError) as error:
            return AuthorizationDecision.deny(
                decisions.REASON_BAD_SIGNATURE, f"lista de revocacion: {error}",
                installation_id=installation_id, license_id=payload.license_id, evidence=evidence,
            )
        serial = revocations.revocations.serial
        if serial < known_serial:
            # Una lista mas vieja que la ultima conocida es un intento de
            # deshacer una revocacion reponiendo un archivo anterior.
            evidence["revocacion_ignorada_por_serial"] = serial
        else:
            motivo = revocations.revocations.revokes(
                installation_id=installation_id, license_id=payload.license_id
            )
            if serial > known_serial:
                # Autoritativa: lo que diga esta lista reemplaza lo que se sabia.
                revoked_reason = motivo
                known_serial = serial
            elif motivo:
                revoked_reason = motivo

    if revoked_reason:
        # Se persiste ANTES de denegar: si esta escritura no ocurriera, bastaria
        # con borrar el archivo para volver a estar autorizado.
        marcado = lease_module.start(
            installation_id=installation_id,
            license_id=payload.license_id,
            validated_at=context.instant(),
            lease_days=payload.lease_days,
            grace_days=payload.grace_days,
            revocation_serial=known_serial,
            security_schema_version=SECURITY_SCHEMA_VERSION,
            previous=previous,
        )
        try:
            _write_lease(
                context,
                replace(marcado, revoked_reason=revoked_reason),
                lease_key,
            )
        except (OSError, SecurityError):
            pass
        return AuthorizationDecision.deny(
            decisions.REASON_REVOKED, revoked_reason,
            installation_id=installation_id, license_id=payload.license_id, evidence=evidence,
        )

    now = context.instant()

    # 10. vencimiento absoluto de la licencia
    if payload.expires_at is not None:
        effective = previous.effective_now(now) if previous else now
        if effective > payload.expires_at:
            return AuthorizationDecision.deny(
                decisions.REASON_EXPIRED, "la licencia vencio",
                installation_id=installation_id, license_id=payload.license_id, evidence=evidence,
            )

    # 11. lease y reloj
    if previous is None or previous.license_id != payload.license_id:
        # Primera vez con esta licencia: instalarla ES la validacion.
        state = lease_module.start(
            installation_id=installation_id,
            license_id=payload.license_id,
            validated_at=now,
            lease_days=payload.lease_days,
            grace_days=payload.grace_days,
            revocation_serial=known_serial,
            security_schema_version=SECURITY_SCHEMA_VERSION,
            previous=previous,
        )
        rolled_back = False
    else:
        state, rolled_back = previous.observe(now)
        if known_serial > state.revocation_serial:
            state = LeaseState(
                installation_id=state.installation_id,
                license_id=state.license_id,
                last_validated_at=now,
                lease_expires_at=payload.lease_expires_from(now),
                grace_expires_at=payload.lease_expires_from(now)
                + (state.grace_expires_at - state.lease_expires_at),
                high_water_mark=state.high_water_mark,
                revocation_serial=known_serial,
                security_schema_version=SECURITY_SCHEMA_VERSION,
            )

    if rolled_back:
        evidence["reloj"] = decisions.REASON_CLOCK_ROLLBACK

    try:
        _write_lease(context, state, lease_key)
    except (OSError, SecurityError) as error:
        evidence["lease_no_persistido"] = str(error)

    common = {
        "installation_id": installation_id,
        "license_id": payload.license_id,
        "capabilities": payload.capabilities,
        "lease_expires_at": state.lease_expires_at,
        "grace_expires_at": state.grace_expires_at,
        "evidence": evidence,
    }
    if state.within_lease(now):
        return AuthorizationDecision(
            outcome=decisions.ALLOW,
            reason=decisions.REASON_CLOCK_ROLLBACK if rolled_back else decisions.REASON_OK,
            detail="", **common,
        )
    if state.within_grace(now):
        return AuthorizationDecision(
            outcome=decisions.ALLOW_GRACE,
            reason=decisions.REASON_LEASE_GRACE,
            detail="el lease vencio; BC sigue funcionando durante la gracia",
            **common,
        )
    return AuthorizationDecision(
        outcome=decisions.DENY,
        reason=decisions.REASON_LEASE_EXPIRED,
        detail="el lease y su gracia vencieron; hace falta renovar la autorizacion",
        **common,
    )


# --------------------------------------------------------------------------
# Instalacion de documentos
# --------------------------------------------------------------------------
def install_license(context: VerificationContext, envelope: dict[str, Any]) -> SignedLicense:
    """Guarda una licencia despues de verificarla. Nunca guarda una que no verifica.

    Escribir primero y validar despues dejaria a la instalacion sin la licencia
    buena que tenia, por culpa de una mala.
    """
    from ..infrastructure.store import write_json

    signed = SignedLicense.from_envelope(envelope)
    verify_license(context.trust_store(), signed)
    identity = enrollment.load_identity(context.paths)
    if signed.payload.installation_id != identity.installation_id:
        raise SecurityError("esa licencia fue emitida para otra instalacion")
    write_json(context.paths.license, signed.to_envelope())
    if context.database_path is not None and security_db.tables_present(context.database_path):
        security_db.record_event(
            context.database_path,
            event=security_db.EVENT_LICENSE_INSTALLED,
            outcome="OK",
            installation_id=identity.installation_id,
            details={
                "license_id": signed.payload.license_id,
                "capabilities": list(signed.payload.capabilities),
                "lease_days": signed.payload.lease_days,
                "grace_days": signed.payload.grace_days,
                "issuer_key_id": signed.payload.issuer_key_id,
            },
        )
    return signed


def install_revocations(
    context: VerificationContext, envelope: dict[str, Any]
) -> SignedRevocationList:
    from ..infrastructure.store import write_json

    signed = SignedRevocationList.from_envelope(envelope)
    verify_revocations(context.trust_store(), signed)
    current = load_revocations(context.paths)
    if current is not None and signed.revocations.serial < current.revocations.serial:
        raise SecurityError(
            "esa lista de revocacion es anterior a la instalada y no se aplica"
        )
    write_json(context.paths.revocations, signed.to_envelope())
    if context.database_path is not None and security_db.tables_present(context.database_path):
        security_db.record_event(
            context.database_path,
            event=security_db.EVENT_REVOCATION_INSTALLED,
            outcome="OK",
            details={
                "serial": signed.revocations.serial,
                "instalaciones": len(signed.revocations.revoked_installations),
                "licencias": len(signed.revocations.revoked_licenses),
            },
        )
    return signed
