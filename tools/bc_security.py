"""Herramienta de instalacion y diagnostico de BC Seguridad, del lado del cliente.

Es lo que se corre en la PC de la Optica. No emite licencias —eso es del
emisor, con la clave privada, en otra maquina— y no puede autorizarse a si
misma: lo mas que hace es preparar la solicitud y aplicar lo que el emisor
firmo.

    python tools/bc_security.py enrolar --etiqueta "Optica - Caja 1"
    python tools/bc_security.py instalar-licencia licencia.bclic
    python tools/bc_security.py verificar
    python tools/bc_security.py proteger-datos --confirmar
    python tools/bc_security.py revertir-datos --confirmar
    python tools/bc_security.py recuperar --frase "...."
    python tools/bc_security.py auditoria

Todo comando que toca la base exige respaldo previo y lo hace el mismo: no se
delega en que alguien se acuerde.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.caja_diaria.config import resolve_data_paths  # noqa: E402
from modulos.seguridad import bootstrap, runtime  # noqa: E402
from modulos.seguridad.application import (  # noqa: E402
    data_migration,
    enrollment,
    keyring,
    verifier,
)
from modulos.seguridad.application.field_protection import FieldCipher  # noqa: E402
from modulos.seguridad.errors import SecurityError  # noqa: E402
from modulos.seguridad.infrastructure import fingerprint as fingerprint_module  # noqa: E402
from modulos.seguridad.infrastructure import security_db  # noqa: E402
from modulos.seguridad.infrastructure.dpapi import default_sealer  # noqa: E402
from modulos.seguridad.infrastructure.store import resolve_security_paths  # noqa: E402

SEPARADOR = "-" * 72


def _base(argumentos) -> Path:
    if argumentos.base:
        return Path(argumentos.base).expanduser().resolve()
    return resolve_data_paths().database


def _contexto(argumentos):
    return bootstrap.build_context(_base(argumentos))


def _respaldar(base: Path) -> Path:
    """Copia de la base ANTES de tocarla, con `sqlite3.backup` y no con `copy`.

    Copiar el archivo mientras hay WAL puede dejar un respaldo inconsistente.
    La API de respaldo de SQLite toma una foto coherente aunque haya lectores.
    """
    import sqlite3
    from contextlib import closing

    marca = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    destino = base.parent / "Backups" / f"pre-seguridad-{marca}-{base.name}"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(base))) as origen:
        with closing(sqlite3.connect(str(destino))) as copia:
            origen.backup(copia)
    return destino


# --------------------------------------------------------------------------
def comando_enrolar(argumentos) -> int:
    paths = resolve_security_paths()
    base = _base(argumentos)
    identity, request = enrollment.enroll(
        paths,
        default_sealer(),
        fingerprint_module.collect(),
        label=argumentos.etiqueta,
        force=argumentos.forzar,
    )
    destino = Path(argumentos.solicitud or (paths.root / "solicitud-de-enrolamiento.json"))
    destino.write_text(
        json.dumps(request.to_document(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(SEPARADOR)
    print(f"installation_id : {identity.installation_id}")
    print(f"sellado por     : {identity.sealer}")
    print(f"componentes     : {', '.join(identity.fingerprint_components)}")
    print(f"solicitud       : {destino}")

    frase = ""
    if base.is_file() and security_db.tables_present(base):
        secreto = enrollment.open_secret(paths, default_sealer(), fingerprint_module.collect())
        if not keyring.has_data_key(base):
            _clave, frase = keyring.create_data_key(base, secreto, created_by=argumentos.etiqueta)
        security_db.record_event(
            base,
            event=security_db.EVENT_ENROLLED,
            outcome="OK",
            installation_id=identity.installation_id,
            details={"etiqueta": argumentos.etiqueta, "sellador": identity.sealer},
        )
    else:
        print("AVISO: la base todavia no tiene las tablas de seguridad (migracion 033).")
        print("       Abri BC una vez para que migre, y volve a correr `enrolar --forzar`")
        print("       solo si hace falta crear la clave de datos.")

    if frase:
        print(SEPARADOR)
        print("FRASE DE RECUPERACION DE LOS DATOS — se muestra UNA SOLA VEZ")
        print()
        print(f"    {frase}")
        print()
        print("Anotala en papel y guardala fuera de esta computadora.")
        print("Sin ella, si esta PC se pierde, la base no se puede volver a abrir.")
    print(SEPARADOR)
    print("Entregale la solicitud al emisor para que firme la licencia.")
    return 0


def comando_instalar_licencia(argumentos) -> int:
    contexto = _contexto(argumentos)
    envelope = json.loads(Path(argumentos.archivo).read_text(encoding="utf-8"))
    firmada = verifier.install_license(contexto, envelope)
    payload = firmada.payload
    print(f"licencia {payload.license_id} instalada")
    print(f"  negocio      : {payload.business_name} / {payload.branch_id}")
    print(f"  capacidades  : {', '.join(payload.capabilities)}")
    print(f"  lease        : {payload.lease_days} dias + {payload.grace_days} de gracia")
    print(f"  vence        : {payload.expires_at or 'sin vencimiento absoluto'}")
    return 0


def comando_instalar_revocaciones(argumentos) -> int:
    contexto = _contexto(argumentos)
    envelope = json.loads(Path(argumentos.archivo).read_text(encoding="utf-8"))
    firmada = verifier.install_revocations(contexto, envelope)
    print(f"lista de revocacion serial {firmada.revocations.serial} instalada")
    return 0


def comando_verificar(argumentos) -> int:
    contexto = _contexto(argumentos)
    arranque = bootstrap.arrancar(contexto)
    if not arranque.enrolled:
        print("SIN_ENROLAR — BC funciona como siempre; esta capa todavia no gobierna esta PC")
        return 0
    decision = arranque.decision
    assert decision is not None
    print(f"{decision.outcome} / {decision.reason}")
    if decision.detail:
        print(f"  {decision.detail}")
    print(f"  installation_id : {decision.installation_id}")
    print(f"  licencia        : {decision.license_id}")
    print(f"  capacidades     : {', '.join(decision.capabilities) or '(ninguna)'}")
    print(f"  lease vence     : {decision.lease_expires_at}")
    print(f"  gracia vence    : {decision.grace_expires_at}")
    print(f"  datos protegidos: {'si' if arranque.data_protected else 'no'}")
    for clave, valor in sorted(decision.evidence.items()):
        print(f"  {clave}: {valor}")
    if arranque.message:
        print(SEPARADOR)
        print(arranque.message)
    return 0 if decision.allowed else 2


def _cifrador(argumentos, base: Path) -> FieldCipher:
    paths = resolve_security_paths()
    if argumentos.frase:
        clave = keyring.open_with_recovery(base, argumentos.frase)
    else:
        secreto = enrollment.open_secret(paths, default_sealer(), fingerprint_module.collect())
        clave = keyring.open_with_installation(base, secreto)
    return FieldCipher(key=clave.raw, dek_id=clave.dek_id)


def comando_proteger_datos(argumentos) -> int:
    base = _base(argumentos)
    antes = data_migration.survey(base)
    en_claro = sum(item["en_claro"] for item in antes.values())
    print(f"valores en claro a proteger: {en_claro}")
    if not argumentos.confirmar:
        for nombre, conteo in sorted(antes.items()):
            print(f"  {nombre}: en claro {conteo['en_claro']}, protegidos {conteo['protegidos']}")
        print("\nEs un ensayo. Volve a correrlo con --confirmar para aplicarlo.")
        return 0
    respaldo = _respaldar(base)
    print(f"respaldo previo: {respaldo}")
    reporte = data_migration.protect(base, _cifrador(argumentos, base), actor=argumentos.actor)
    print(json.dumps(reporte.to_document(), ensure_ascii=False, indent=2))
    faltantes = data_migration.plaintext_leftovers(base)
    print("quedan en claro:", faltantes or "nada")
    return 0 if not faltantes else 1


def comando_revertir_datos(argumentos) -> int:
    base = _base(argumentos)
    if not argumentos.confirmar:
        print("Es un ensayo. Volve a correrlo con --confirmar para revertir.")
        return 0
    respaldo = _respaldar(base)
    print(f"respaldo previo: {respaldo}")
    reporte = data_migration.rollback(base, _cifrador(argumentos, base), actor=argumentos.actor)
    print(json.dumps(reporte.to_document(), ensure_ascii=False, indent=2))
    return 0


def comando_recuperar(argumentos) -> int:
    """Reabre la base con la frase y la vuelve a atar al secreto de ESTA PC."""
    base = _base(argumentos)
    paths = resolve_security_paths()
    clave = keyring.open_with_recovery(base, argumentos.frase)
    secreto = enrollment.open_secret(paths, default_sealer(), fingerprint_module.collect())
    keyring.rewrap_for_installation(base, clave, secreto, created_by=argumentos.actor)
    security_db.record_event(
        base,
        event=security_db.EVENT_KEYRING_RECOVERED,
        outcome="OK",
        installation_id=secreto.installation_id,
        details={"actor": argumentos.actor, "dek_id": clave.dek_id},
    )
    print("la clave de datos quedo reatada a esta instalacion")
    return 0


def comando_auditoria(argumentos) -> int:
    for fila in security_db.read_audit(_base(argumentos), limit=argumentos.limite):
        print(
            f"{fila['occurred_at']}  {fila['event']:<22} {fila['outcome']:<12}"
            f" {fila['reason']:<28} {fila['detail_json']}"
        )
    return 0


def comando_estado(argumentos) -> int:
    base = _base(argumentos)
    paths = resolve_security_paths()
    print(f"carpeta de seguridad : {paths.root}")
    print(f"base                 : {base}")
    print(f"enrolada             : {'si' if enrollment.is_enrolled(paths) else 'no'}")
    print(f"tablas de seguridad  : {'si' if base.is_file() and security_db.tables_present(base) else 'no'}")
    if base.is_file() and security_db.tables_present(base):
        print(f"clave de datos       : {'si' if keyring.has_data_key(base) else 'no'}")
        for nombre, conteo in sorted(data_migration.survey(base).items()):
            print(f"  {nombre}: en claro {conteo['en_claro']}, protegidos {conteo['protegidos']}")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BC Seguridad — instalacion y diagnostico")
    parser.add_argument("--base", help="ruta de la base; por defecto la de BC Caja")
    parser.add_argument("--actor", default="", help="quien ejecuta, para la bitacora")
    sub = parser.add_subparsers(dest="comando", required=True)

    enrolar = sub.add_parser("enrolar", help="crea identidad y secreto de esta PC")
    enrolar.add_argument("--etiqueta", default="", help='por ejemplo "Optica - Caja 1"')
    enrolar.add_argument("--solicitud", help="donde escribir la solicitud para el emisor")
    enrolar.add_argument(
        "--forzar", action="store_true",
        help="re-enrola aunque ya exista identidad; invalida la clave de datos vigente",
    )
    enrolar.set_defaults(func=comando_enrolar)

    licencia = sub.add_parser("instalar-licencia", help="aplica una licencia firmada")
    licencia.add_argument("archivo")
    licencia.set_defaults(func=comando_instalar_licencia)

    revocaciones = sub.add_parser("instalar-revocaciones", help="aplica una lista de revocacion")
    revocaciones.add_argument("archivo")
    revocaciones.set_defaults(func=comando_instalar_revocaciones)

    verificar = sub.add_parser("verificar", help="dice si esta PC esta autorizada")
    verificar.set_defaults(func=comando_verificar)

    proteger = sub.add_parser("proteger-datos", help="cifra los datos sensibles existentes")
    proteger.add_argument("--confirmar", action="store_true")
    proteger.add_argument("--frase", default="", help="frase de recuperacion, si no hay secreto local")
    proteger.set_defaults(func=comando_proteger_datos)

    revertir = sub.add_parser("revertir-datos", help="devuelve los datos a texto plano")
    revertir.add_argument("--confirmar", action="store_true")
    revertir.add_argument("--frase", default="")
    revertir.set_defaults(func=comando_revertir_datos)

    recuperar = sub.add_parser("recuperar", help="reata la clave de datos a esta instalacion")
    recuperar.add_argument("--frase", required=True)
    recuperar.set_defaults(func=comando_recuperar)

    auditoria = sub.add_parser("auditoria", help="ultimas lineas de la bitacora de seguridad")
    auditoria.add_argument("--limite", type=int, default=50)
    auditoria.set_defaults(func=comando_auditoria)

    estado = sub.add_parser("estado", help="resumen de la instalacion")
    estado.set_defaults(func=comando_estado)
    return parser


def main(argv=None) -> int:
    argumentos = construir_parser().parse_args(argv)
    try:
        return argumentos.func(argumentos)
    except SecurityError as error:
        print(f"ERROR DE SEGURIDAD: {error}", file=sys.stderr)
        return 3
    finally:
        runtime.clear()


if __name__ == "__main__":
    raise SystemExit(main())
