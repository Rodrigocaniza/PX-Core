# -*- coding: utf-8 -*-
"""Da de alta a las personas reales de la Optica y carga sus tarifas de compostura.

Ni un nombre ni un monto vienen del codigo. Todo sale de un archivo que completa
quien sabe: como se llama cada una, que rol tiene, en que sucursal trabaja, si
necesita entrar al sistema, y cuanto cobra por compostura la que comisiona.

    python tools/alta_personas_y_comisiones_optica.py --plantilla personas.json
    python tools/alta_personas_y_comisiones_optica.py personas.json
    python tools/alta_personas_y_comisiones_optica.py personas.json --confirmar

Sin `--confirmar` no escribe: valida todo el archivo, dice exactamente que haria
persona por persona, y sale. Ese es el dry-run, y conviene mirarlo antes.

Es re-corrible: una persona que ya existe se actualiza en vez de duplicarse, y
una tarifa igual a la vigente no agrega una version que no cambia nada.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from modulos.caja_diaria.bootstrap import build_cash_day_controller  # noqa: E402
from modulos.caja_diaria.config import resolve_data_paths  # noqa: E402
from modulos.caja_diaria.application.admin_ops import ROL_ADMIN, ROL_OPERADOR  # noqa: E402

ROLES = (ROL_ADMIN, ROL_OPERADOR)
SUCURSALES = ("ASUNCION", "PILAR", "")

PLANTILLA = {
    "_como_se_completa": [
        "administrador_inicial: solo hace falta la primera vez, cuando la base no",
        "  tiene ninguna credencial administrativa. Si ya hay una, borra este bloque.",
        "personas: una por cada persona real. `contrasena` en null significa que la",
        "  persona existe, se la puede elegir como vendedora y como responsable de un",
        "  trabajo, y no puede entrar al sistema. Eso es lo normal para quien atiende.",
        "  Minimo 10 caracteres si se pone. `sucursal` vacia significa todas, que es",
        "  lo que corresponde a quien administra.",
        "comisiones: una por cada persona que cobre por compostura. Quien no cobra no",
        "  necesita ninguna linea: sin politica el trabajo funciona entero y no",
        "  devenga, y el reporte lo lista aparte. `sucursal` y `tipo_de_trabajo`",
        "  vacios significan todas y todos. `rige_desde` puede ser futura.",
    ],
    "administrador_inicial": {"usuario": "", "contrasena": ""},
    "personas": [
        {"usuario": "", "nombre_visible": "", "rol": "OPERADOR",
         "sucursal": "ASUNCION", "contrasena": None},
    ],
    "comisiones": [
        {"usuario": "", "importe": 0, "sucursal": "", "tipo_de_trabajo": "",
         "rige_desde": "", "motivo": ""},
    ],
}

lineas: list[str] = []
errores: list[str] = []


def registrar(texto: str = "") -> None:
    print(texto, flush=True)
    lineas.append(texto)


def error(texto: str) -> None:
    errores.append(texto)
    registrar(f"  ERROR {texto}")


def validar(datos: dict, tipos_validos: set[str]) -> None:
    """Todo el archivo se valida antes de escribir una sola fila."""
    personas = datos.get("personas") or []
    if not isinstance(personas, list):
        error("`personas` tiene que ser una lista.")
        return
    usuarios: set[str] = set()
    for i, p in enumerate(personas, 1):
        etiqueta = f"personas[{i}]"
        usuario = str(p.get("usuario", "")).strip()
        if len(usuario) < 3:
            error(f"{etiqueta}: el usuario necesita al menos 3 caracteres.")
        if usuario.lower() in usuarios:
            error(f"{etiqueta}: el usuario «{usuario}» esta dos veces en el archivo.")
        usuarios.add(usuario.lower())
        if not str(p.get("nombre_visible", "")).strip():
            error(f"{etiqueta}: falta el nombre visible, que es como se la nombra en una venta.")
        rol = str(p.get("rol", "")).strip().upper()
        if rol not in ROLES:
            error(f"{etiqueta}: rol {p.get('rol')!r}; tiene que ser ADMIN u OPERADOR.")
        sucursal = str(p.get("sucursal", "") or "").strip().upper()
        if sucursal not in SUCURSALES:
            error(f"{etiqueta}: sucursal {p.get('sucursal')!r};"
                  f" tiene que ser ASUNCION, PILAR o vacia.")
        clave = p.get("contrasena")
        if clave is not None and len(str(clave)) < 10:
            error(f"{etiqueta}: la contrasena necesita al menos 10 caracteres"
                  f" (o null si no tiene que entrar).")

    for i, com in enumerate(datos.get("comisiones") or [], 1):
        etiqueta = f"comisiones[{i}]"
        usuario = str(com.get("usuario", "")).strip()
        if not usuario:
            error(f"{etiqueta}: falta el usuario.")
        try:
            importe = int(com.get("importe"))
        except (TypeError, ValueError):
            error(f"{etiqueta}: importe {com.get('importe')!r} no es un numero entero.")
            importe = -1
        if importe < 0:
            error(f"{etiqueta}: una comision no puede ser negativa.")
        sucursal = str(com.get("sucursal", "") or "").strip().upper()
        if sucursal not in SUCURSALES:
            error(f"{etiqueta}: sucursal {com.get('sucursal')!r}.")
        tipo = str(com.get("tipo_de_trabajo", "") or "").strip().upper()
        if tipo and tipo not in tipos_validos:
            error(f"{etiqueta}: tipo de trabajo {tipo!r};"
                  f" los que hay son {sorted(tipos_validos)}.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivo", nargs="?", type=Path)
    parser.add_argument("--plantilla", type=Path, default=None,
                        help="escribe un archivo de ejemplo para completar y sale")
    parser.add_argument("--base", type=Path, default=None)
    parser.add_argument("--confirmar", action="store_true")
    args = parser.parse_args()

    if args.plantilla:
        args.plantilla.write_text(
            json.dumps(PLANTILLA, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Plantilla escrita en {args.plantilla}")
        print("Completala y despues corre:")
        print(f"  python tools/alta_personas_y_comisiones_optica.py {args.plantilla}")
        return 0

    if not args.archivo:
        parser.error("hace falta el archivo, o --plantilla para generar uno.")
    if not args.archivo.exists():
        print(f"No existe el archivo: {args.archivo}")
        return 2

    base = args.base or resolve_data_paths().database
    datos = json.loads(args.archivo.read_text(encoding="utf-8"))

    registrar("PERSONAS Y TARIFAS DE COMPOSTURA DE LA OPTICA")
    registrar("=" * 60)
    registrar(f"base    {base}")
    registrar(f"archivo {args.archivo}")
    registrar(f"modo    {'APLICAR' if args.confirmar else 'DRY-RUN (no escribe)'}")
    registrar()

    c = build_cash_day_controller(database_path=base)
    admin, jobs = c.admin, c.jobs
    tipos_validos = {t["code"] for t in jobs.tipos_de_trabajo()}

    registrar("Validacion del archivo")
    validar(datos, tipos_validos)
    if errores:
        registrar()
        registrar(f"STOP: {len(errores)} error(es) en el archivo. No se escribio nada.")
        return 1
    registrar("  OK    el archivo entero es valido")
    registrar()

    # -- credencial administrativa ------------------------------------------
    inicial = datos.get("administrador_inicial") or {}
    usuario_inicial = str(inicial.get("usuario", "")).strip()
    if not admin.has_admin():
        if not usuario_inicial:
            registrar("STOP: la base no tiene ninguna credencial administrativa y el")
            registrar("      archivo no trae `administrador_inicial`. Sin una ADMIN no se")
            registrar("      puede dar de alta a nadie: es la unica que puede.")
            return 1
        if len(str(inicial.get("contrasena", ""))) < 10:
            registrar("STOP: la contrasena del administrador inicial necesita 10 caracteres.")
            return 1
        registrar(f"Administrador inicial: se crea «{usuario_inicial}»")
        if not args.confirmar:
            token = None
        else:
            token = admin.create_initial_admin(
                usuario_inicial, str(inicial["contrasena"])).token
    else:
        registrar("Ya existe una credencial administrativa en la base.")
        if not usuario_inicial:
            registrar("STOP: hace falta `administrador_inicial` con usuario y contrasena de")
            registrar("      una ADMIN que ya exista, para poder autenticarse y dar de alta.")
            return 1
        try:
            token = admin.authenticate(usuario_inicial, str(inicial.get("contrasena", ""))).token
        except Exception as exc:  # noqa: BLE001
            registrar(f"STOP: no se pudo entrar como «{usuario_inicial}»: {exc}")
            return 1
        registrar(f"  OK    autenticada «{usuario_inicial}»")
    registrar()

    existentes = {}
    if token:
        existentes = {u.username.lower(): u for u in admin.list_users(token)}

    # -- personas ------------------------------------------------------------
    registrar("Personas")
    por_usuario: dict[str, str] = {}
    for p in datos.get("personas") or []:
        usuario = str(p["usuario"]).strip()
        nombre = str(p["nombre_visible"]).strip()
        rol = str(p["rol"]).strip().upper()
        sucursal = str(p.get("sucursal", "") or "").strip().upper()
        clave = p.get("contrasena")
        entra = "con contrasena" if clave else "sin contrasena (no entra)"
        previa = existentes.get(usuario.lower())
        verbo = "actualizar" if previa else "dar de alta"
        registrar(f"  {verbo:10} {usuario:16} «{nombre}» {rol}"
                  f" {sucursal or 'TODAS':9} {entra}")
        if not args.confirmar:
            continue
        if previa:
            actualizada = admin.update_user(
                token, previa.id, display_name=nombre, role=rol, branch=sucursal)
            if clave:
                admin.set_user_password(token, previa.id, str(clave))
            por_usuario[usuario.lower()] = actualizada.id
        else:
            creada = admin.create_user(
                token, username=usuario, display_name=nombre, role=rol,
                branch=sucursal, password=str(clave) if clave else None)
            por_usuario[usuario.lower()] = creada.id
    registrar()

    if args.confirmar:
        por_usuario.update({u.username.lower(): u.id for u in admin.list_users(token)})

    # -- comisiones ----------------------------------------------------------
    registrar("Tarifas de compostura")
    comisiones = datos.get("comisiones") or []
    if not comisiones:
        registrar("  ninguna. Las composturas van a funcionar enteras y no van a devengar,")
        registrar("  que es lo correcto: el reporte las lista aparte.")
    for com in comisiones:
        usuario = str(com["usuario"]).strip()
        importe = int(com["importe"])
        sucursal = str(com.get("sucursal", "") or "").strip().upper()
        tipo = str(com.get("tipo_de_trabajo", "") or "").strip().upper()
        rige = str(com.get("rige_desde", "") or "").strip()
        motivo = str(com.get("motivo", "") or "").strip()
        alcance = f"{sucursal or 'TODAS':9} {tipo or 'TODOS':11}"
        registrar(f"  {usuario:16} {importe:>10,} Gs  {alcance}"
                  f" desde {rige or 'hoy'}")
        if not args.confirmar:
            continue
        user_id = por_usuario.get(usuario.lower())
        if not user_id:
            error(f"la comision nombra a «{usuario}», que no esta entre las personas.")
            continue
        vigente = jobs.politica_vigente_de(user_id=user_id, job_type=tipo or "COMPOSTURA",
                                           branch=sucursal)
        if vigente and int(vigente["amount"]) == importe:
            registrar(f"                   ya vigente por ese importe: no se agrega version")
            continue
        if vigente and not motivo:
            error(f"«{usuario}» ya tiene {vigente['amount']} y cambiarlo pide un motivo.")
            continue
        jobs.definir_comision(user_id=user_id, amount=importe, branch=sucursal,
                              job_type=tipo, effective_from=rige or None,
                              reason=motivo, token=token)
    registrar()

    if errores:
        registrar(f"RESULTADO: FALLA ({len(errores)})")
        return 1
    if not args.confirmar:
        registrar("DRY-RUN: no se escribio nada. Repetir con --confirmar.")
        return 0

    # -- verificacion --------------------------------------------------------
    registrar("Verificacion")
    personas = admin.list_users(token)
    registrar(f"  {len(personas)} persona(s) en la base:")
    for u in personas:
        registrar(f"    {u.username:16} «{u.display_name}» {u.etiqueta_rol:14}"
                  f" {u.branch or 'TODAS':9} {'entra' if u.puede_entrar else 'no entra'}"
                  f" {'activa' if u.active else 'INACTIVA'}")
    politicas = jobs.politicas_de_comision(token=token)
    registrar(f"  {len(politicas)} politica(s) de comision vigente(s):")
    for pol in politicas:
        registrar(f"    {pol}")
    registrar()
    registrar("RESULTADO: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
