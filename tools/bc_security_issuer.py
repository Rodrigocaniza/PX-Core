"""Emisor de licencias de BC. **Se corre en la maquina de administracion, no en la Optica.**

La clave privada de firma nunca entra al repositorio ni al paquete de BC. Vive
sellada por DPAPI en la maquina que emite, y su respaldo es papel.

    python tools/bc_security_issuer.py generar-clave --etiqueta "BC Emisor 2026"
    python tools/bc_security_issuer.py almacen-de-confianza
    python tools/bc_security_issuer.py emitir --solicitud solicitud.json \
        --negocio "Optica" --organizacion opt --sucursal ASUNCION --salida licencia.bclic
    python tools/bc_security_issuer.py revocar --instalacion <id> --serial 2 --salida rev.bcrl
    python tools/bc_security_issuer.py respaldo-de-clave

`respaldo-de-clave` imprime la clave privada en claro y por eso hay que
pedirlo explicitamente: es el unico modo de que emitir siga siendo posible si
la maquina de administracion se pierde.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.seguridad.crypto.primitives import digest  # noqa: E402
from modulos.seguridad.domain.license import KNOWN_CAPABILITIES  # noqa: E402
from modulos.seguridad.application.enrollment import EnrollmentRequest  # noqa: E402
from modulos.seguridad.errors import SecurityError  # noqa: E402
from modulos.seguridad.infrastructure.dpapi import default_sealer  # noqa: E402
from modulos.seguridad.infrastructure.store import read_json, write_json  # noqa: E402
from modulos.seguridad.issuer import issuer as issuer_module  # noqa: E402
from modulos.seguridad.trust import BUILTIN_TRUST_FILE  # noqa: E402

# La clave del emisor NO vive en el repositorio. Por defecto va a la carpeta de
# datos del usuario que emite, y se puede mover con --clave.
DEFAULT_KEY_PATH = Path.home() / "AppData" / "Local" / "BC" / "Issuer" / "bc-issuer.key.json"

# Entropia de DPAPI para la clave del emisor. Constante y publica: la proteccion
# la da el ambito de usuario de DPAPI, no que este valor sea secreto.
_KEY_ENTROPY = bytes.fromhex(digest(b"issuer-key-entropy"))


def _ruta_clave(argumentos) -> Path:
    return Path(argumentos.clave).expanduser() if argumentos.clave else DEFAULT_KEY_PATH


def _cargar_clave(argumentos):
    documento = read_json(_ruta_clave(argumentos))
    if documento is None:
        raise SecurityError(
            f"no hay clave de emisor en {_ruta_clave(argumentos)}; corre `generar-clave` primero"
        )
    return issuer_module.import_private(documento, default_sealer(), _KEY_ENTROPY)


def comando_generar_clave(argumentos) -> int:
    destino = _ruta_clave(argumentos)
    if destino.is_file() and not argumentos.forzar:
        raise SecurityError(
            f"ya hay una clave en {destino}. Generar otra deja sin verificar las licencias "
            "ya emitidas con la anterior; usa --forzar solo si eso es lo que queres"
        )
    clave = issuer_module.generate(argumentos.etiqueta)
    write_json(destino, issuer_module.export_private(clave, default_sealer(), _KEY_ENTROPY))
    print(f"clave de emisor creada: key_id={clave.key_id}")
    print(f"archivo (sellado con DPAPI de este usuario): {destino}")
    print()
    print("SIGUIENTE PASO OBLIGATORIO: corre `respaldo-de-clave` y guarda la salida")
    print("fuera de linea. Sin respaldo, perder esta maquina es perder la capacidad")
    print("de emitir y de revocar.")
    return 0


def comando_respaldo_de_clave(argumentos) -> int:
    clave = _cargar_clave(argumentos)
    print("CLAVE PRIVADA DEL EMISOR — guardala fuera de linea y no la pegues en ningun repo")
    print()
    print(f"  key_id : {clave.key_id}")
    print(f"  privada: {issuer_module.export_private_plaintext(clave)}")
    return 0


def comando_almacen(argumentos) -> int:
    """Regenera el `trusted_issuers.json` que se empaqueta con el cliente."""
    clave = _cargar_clave(argumentos)
    destino = Path(argumentos.salida) if argumentos.salida else BUILTIN_TRUST_FILE
    write_json(destino, issuer_module.trust_document([clave]))
    print(f"almacen de confianza escrito en {destino} con key_id={clave.key_id}")
    print("Recorda commitearlo: es lo unico del emisor que viaja al cliente.")
    return 0


def comando_emitir(argumentos) -> int:
    clave = _cargar_clave(argumentos)
    documento = read_json(Path(argumentos.solicitud))
    if documento is None:
        raise SecurityError(f"no se encontro la solicitud {argumentos.solicitud}")
    solicitud = EnrollmentRequest.from_document(documento)

    capacidades = argumentos.capacidades or list(KNOWN_CAPABILITIES)
    firmada = issuer_module.issue_license(
        clave,
        license_id=argumentos.license_id or str(uuid4()),
        installation_id=solicitud.installation_id,
        organization_id=argumentos.organizacion,
        branch_id=argumentos.sucursal,
        business_name=argumentos.negocio,
        binding=solicitud.binding,
        secondary_required=solicitud.secondary_required,
        capabilities=capacidades,
        sync_public_key=solicitud.sync_public_key,
        lease_days=argumentos.lease_dias,
        grace_days=argumentos.gracia_dias,
        valid_days=argumentos.vigencia_dias,
        app_version=argumentos.version_app,
        notes=argumentos.nota,
    )
    salida = Path(argumentos.salida)
    write_json(salida, firmada.to_envelope())
    print(f"licencia {firmada.payload.license_id} emitida en {salida}")
    print(f"  instalacion : {solicitud.installation_id}")
    print(f"  capacidades : {', '.join(capacidades)}")
    print(f"  lease       : {argumentos.lease_dias} dias + {argumentos.gracia_dias} de gracia")
    return 0


def comando_revocar(argumentos) -> int:
    clave = _cargar_clave(argumentos)
    firmada = issuer_module.issue_revocations(
        clave,
        serial=argumentos.serial,
        revoked_installations=argumentos.instalacion,
        revoked_licenses=argumentos.licencia,
        reasons={
            identificador: argumentos.motivo
            for identificador in list(argumentos.instalacion) + list(argumentos.licencia)
        },
    )
    salida = Path(argumentos.salida)
    write_json(salida, firmada.to_envelope())
    print(f"lista de revocacion serial {argumentos.serial} emitida en {salida}")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BC Seguridad — emisor de licencias")
    parser.add_argument("--clave", help=f"archivo de clave del emisor (defecto: {DEFAULT_KEY_PATH})")
    sub = parser.add_subparsers(dest="comando", required=True)

    generar = sub.add_parser("generar-clave")
    generar.add_argument("--etiqueta", default="BC Emisor")
    generar.add_argument("--forzar", action="store_true")
    generar.set_defaults(func=comando_generar_clave)

    respaldo = sub.add_parser("respaldo-de-clave")
    respaldo.set_defaults(func=comando_respaldo_de_clave)

    almacen = sub.add_parser("almacen-de-confianza")
    almacen.add_argument("--salida")
    almacen.set_defaults(func=comando_almacen)

    emitir = sub.add_parser("emitir")
    emitir.add_argument("--solicitud", required=True)
    emitir.add_argument("--salida", required=True)
    emitir.add_argument("--negocio", required=True)
    emitir.add_argument("--organizacion", required=True)
    emitir.add_argument("--sucursal", required=True)
    emitir.add_argument("--license-id")
    emitir.add_argument("--capacidades", nargs="*", choices=list(KNOWN_CAPABILITIES))
    emitir.add_argument("--lease-dias", type=int, default=issuer_module.DEFAULT_LEASE_DAYS)
    emitir.add_argument("--gracia-dias", type=int, default=issuer_module.DEFAULT_GRACE_DAYS)
    emitir.add_argument("--vigencia-dias", type=int, default=None)
    emitir.add_argument("--version-app", default="")
    emitir.add_argument("--nota", default="")
    emitir.set_defaults(func=comando_emitir)

    revocar = sub.add_parser("revocar")
    revocar.add_argument("--serial", type=int, required=True)
    revocar.add_argument("--salida", required=True)
    revocar.add_argument("--instalacion", nargs="*", default=[])
    revocar.add_argument("--licencia", nargs="*", default=[])
    revocar.add_argument("--motivo", default="revocada")
    revocar.set_defaults(func=comando_revocar)
    return parser


def main(argv=None) -> int:
    argumentos = construir_parser().parse_args(argv)
    try:
        return argumentos.func(argumentos)
    except SecurityError as error:
        print(f"ERROR DE SEGURIDAD: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
