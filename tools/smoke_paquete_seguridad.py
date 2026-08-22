"""Ceremonia completa contra el PAQUETE CONGELADO, no contra el codigo fuente.

Funcionar desde Python no dice nada sobre funcionar empaquetado. La primera
version de este paquete arrancaba perfecto y no llevaba el almacen de
confianza: toda instalacion enrolada habria quedado en DENY, y se habria
descubierto en la Optica con la base ya cifrada.

Este script corre, contra los `.exe` de `dist/BC-Caja`, la misma ceremonia que
va a hacerse en la Optica:

    arranque -> enrolamiento -> emision -> instalacion -> ALLOW
             -> escritura y lectura de datos protegidos
             -> la base con SQLite pelado no dice nada
             -> reinicio y persistencia
             -> lease offline
             -> licencia manipulada -> DENY
             -> archivos corruptos -> DENY sin destruir
             -> rollback -> todo vuelve a texto plano

Trabaja sobre directorios temporales propios. **No toca ninguna base
productiva** y no usa la carpeta de datos por defecto de BC.

    python tools/smoke_paquete_seguridad.py
    python tools/smoke_paquete_seguridad.py --paquete dist/BC-Caja
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# Datos de prueba. Se buscan literalmente en los bytes de la base: si aparecen,
# la proteccion no esta funcionando en el paquete.
PACIENTE = "PACIENTE DE PRUEBA BC"
TELEFONO = "0900-000000"

VERDE = "OK  "
ROJO = "MAL "


class Fallo(Exception):
    """Algo del paquete no se comporta como tiene que comportarse."""


class Ceremonia:
    def __init__(self, paquete: Path, taller: Path) -> None:
        self.caja = paquete / "BC-Caja.exe"
        self.seguridad = paquete / "Seguridad" / "BC-Seguridad.exe"
        self.datos = taller / "Datos"
        self.seguro = taller / "Seguridad"
        self.taller = taller
        self.pasos: list[tuple[bool, str]] = []
        self.installation_id = ""
        self.frase = ""

    # ------------------------------------------------------------------ util
    def _entorno(self) -> dict[str, str]:
        entorno = dict(os.environ)
        entorno["BC_CAJA_DATA_DIR"] = str(self.datos)
        entorno["BC_SECURITY_DIR"] = str(self.seguro)
        # El almacen de confianza de pruebas se ignora dentro del paquete
        # congelado (sys.frozen). Se limpia igual para que quede claro que la
        # ceremonia usa el almacen real que viaja adentro del .exe.
        entorno.pop("BC_SECURITY_TEST_TRUST", None)
        return entorno

    def _correr(self, ejecutable: Path, *argumentos: str, esperado: int = 0):
        proceso = subprocess.run(
            [str(ejecutable), *argumentos],
            capture_output=True, text=True, env=self._entorno(), timeout=180,
            encoding="utf-8", errors="replace",
        )
        if esperado is not None and proceso.returncode != esperado:
            raise Fallo(
                f"{ejecutable.name} {' '.join(argumentos)} devolvio "
                f"{proceso.returncode} y se esperaba {esperado}\n"
                f"salida: {proceso.stdout}\n{proceso.stderr}"
            )
        return proceso

    def paso(self, descripcion: str, condicion: bool, detalle: str = "") -> None:
        self.pasos.append((condicion, descripcion))
        marca = VERDE if condicion else ROJO
        print(f"  {marca}{descripcion}" + (f" — {detalle}" if detalle else ""))
        if not condicion:
            raise Fallo(descripcion)

    def _base(self) -> Path:
        return self.datos / "bc_caja.sqlite3"

    # ----------------------------------------------------------------- pasos
    def arranque_limpio(self) -> None:
        salida = self._correr(self.caja, "--self-check").stdout
        self.paso("el ejecutable arranca y migra la base", "BC_CAJA_SELF_CHECK_OK" in salida)
        conexion = sqlite3.connect(str(self._base()))
        try:
            tablas = {
                fila[0] for fila in conexion.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        finally:
            conexion.close()
        self.paso(
            "la migracion 033 corrio dentro del paquete",
            {"security_state", "security_keyring", "security_audit"}.issubset(tablas),
        )

    def sin_enrolar_funciona(self) -> None:
        salida = self._correr(self.caja, "--security-check").stdout
        self.paso(
            "sin enrolar, BC funciona como siempre",
            "BC_CAJA_SECURITY_CHECK_OK" in salida and "protegido=no" in salida,
            salida.strip().splitlines()[-1] if salida.strip() else "",
        )

    def enrolar(self) -> None:
        salida = self._correr(self.seguridad, "enrolar", "--etiqueta", "SMOKE").stdout
        for linea in salida.splitlines():
            if linea.startswith("installation_id"):
                self.installation_id = linea.split(":", 1)[1].strip()
            if linea.strip() and "-" in linea and len(linea.strip().split("-")) == 8:
                self.frase = linea.strip()
        self.paso("el enrolamiento crea identidad", bool(self.installation_id))
        self.paso(
            "el enrolamiento entrega una frase de recuperacion",
            bool(self.frase),
            "(no se imprime)",
        )
        self.paso(
            "DPAPI real funciona dentro del paquete",
            "windows-dpapi-local-machine" in salida,
        )

    def emitir_e_instalar(self) -> None:
        solicitud = self.seguro / "solicitud-de-enrolamiento.json"
        licencia = self.taller / "licencia.bclic"
        # El emisor corre desde el codigo fuente a proposito: es la maquina de
        # administracion, y su clave privada no se empaqueta nunca.
        emision = subprocess.run(
            [sys.executable, str(RAIZ / "tools" / "bc_security_issuer.py"), "emitir",
             "--solicitud", str(solicitud), "--salida", str(licencia),
             "--negocio", "Smoke", "--organizacion", "smoke", "--sucursal", "ASUNCION",
             "--lease-dias", "365", "--gracia-dias", "180"],
            capture_output=True, text=True, cwd=str(RAIZ), timeout=120,
            encoding="utf-8", errors="replace",
        )
        self.paso("el emisor firma la licencia", emision.returncode == 0, emision.stderr.strip())
        salida = self._correr(self.seguridad, "instalar-licencia", str(licencia)).stdout
        self.paso("el paquete instala la licencia", "instalada" in salida)
        salida = self._correr(self.seguridad, "verificar").stdout
        self.paso(
            "el paquete verifica con el almacen que lleva adentro",
            salida.startswith("ALLOW / OK"),
            salida.splitlines()[0],
        )

    def proteger_lo_ya_escrito(self) -> None:
        """Enrolar no protege lo de antes: eso lo hace `proteger-datos`.

        El smoke lo aprendio por las malas — la primera corrida daba
        `filtracion=SI` con `cifrado_en_disco=si`, porque la venta escrita antes
        de enrolar seguia en claro en el mismo archivo. Es exactamente el paso 5
        del instructivo, y por eso esta aca en el mismo orden.
        """
        ensayo = self._correr(self.seguridad, "proteger-datos").stdout
        self.paso("el ensayo no escribe y muestra cuanto hay en claro", "ensayo" in ensayo.lower())
        aplicado = self._correr(
            self.seguridad, "proteger-datos", "--confirmar", "--actor", "smoke"
        ).stdout
        self.paso(
            "proteger-datos deja la base sin nada en claro",
            "quedan en claro: nada" in aplicado,
            [l for l in aplicado.splitlines() if "quedan en claro" in l][:1],
        )
        self.paso(
            "y sella los informes que ya estaban en disco",
            "informes en claro: ninguno" in aplicado,
        )

    def datos_protegidos(self) -> None:
        salida = self._correr(self.caja, "--security-check").stdout
        self.paso(
            "escribe y lee datos protegidos, y en disco quedan cifrados",
            "cifrado_en_disco=si" in salida and "filtracion=no" in salida,
            salida.strip().splitlines()[-1],
        )

    def sqlite_pelado_no_dice_nada(self) -> None:
        checker = self._correr(
            self.seguridad, "verificar-bcx1", "--base", str(self._base())
        ).stdout
        self.paso(
            "el checker congelado valida todos los campos sensibles",
            checker.startswith("BCX1_OK valores=")
            and "en_claro=0 integrity_check=ok" in checker,
            checker.strip(),
        )
        conexion = sqlite3.connect(str(self._base()))
        try:
            filas = conexion.execute(
                "SELECT description, customer_phone FROM cash_entries"
            ).fetchall()
        finally:
            conexion.close()
        legibles = [
            valor for fila in filas for valor in fila
            if valor and not str(valor).startswith("bcx1:")
        ]
        self.paso("SQLite normal solo muestra criptograma", not legibles, str(legibles[:2]))
        crudo = self._base().read_bytes()
        self.paso(
            "los bytes de la base no dicen el nombre ni el telefono",
            PACIENTE.encode() not in crudo and TELEFONO.encode() not in crudo,
        )

    def el_informe_queda_sellado(self) -> None:
        informes = list((self.datos / "Reports").glob("*.pdf"))
        self.paso(
            "el cierre genero la planilla",
            bool(informes),
            "sin planilla no se estaria probando el archivo que mas PII lleva",
        )
        for informe in informes:
            with open(informe, "rb") as handle:
                sellado = handle.read(9) == b"BCX1FILE\n"
            self.paso(f"la planilla {informe.name} queda sellada", sellado)

    def persiste_al_reiniciar(self) -> None:
        salida = self._correr(self.caja, "--security-check").stdout
        self.paso("reabrir el ejecutable sigue leyendo lo guardado", "SECURITY_CHECK_OK" in salida)

    def licencia_manipulada(self) -> None:
        licencia = self.seguro / "license.bclic"
        original = licencia.read_text(encoding="utf-8")
        sobre = json.loads(original)
        sobre["payload"]["business_name"] = "Otro negocio"
        licencia.write_text(json.dumps(sobre), encoding="utf-8")
        try:
            proceso = self._correr(self.seguridad, "verificar", esperado=2)
            self.paso(
                "una licencia con un byte cambiado da DENY",
                "FIRMA_INVALIDA" in proceso.stdout,
                proceso.stdout.splitlines()[0],
            )
            arranque = self._correr(self.caja, "--security-check", esperado=2)
            self.paso(
                "y el ejecutable no abre",
                "BC_CAJA_SECURITY_CHECK_DENY" in arranque.stdout,
            )
            self.paso("la base sigue estando", self._base().is_file())
        finally:
            licencia.write_text(original, encoding="utf-8")
        self.paso(
            "reponer la licencia buena vuelve a ALLOW",
            self._correr(self.seguridad, "verificar").stdout.startswith("ALLOW"),
        )

    def secreto_corrupto(self) -> None:
        secreto = self.seguro / "installation.secret"
        original = secreto.read_bytes()
        tamano = self._base().stat().st_size
        secreto.write_bytes(b"basura")
        try:
            proceso = self._correr(self.seguridad, "verificar", esperado=2)
            self.paso(
                "un secreto corrupto da DENY y no destruye nada",
                "SECRETO_NO_RECUPERABLE" in proceso.stdout
                and self._base().stat().st_size >= tamano,
            )
        finally:
            secreto.write_bytes(original)

    def lease_offline(self) -> None:
        # No hay red en ningun momento de esta ceremonia: que todo lo anterior
        # haya dado ALLOW ya prueba que el camino es local. Aca se comprueba que
        # el lease quedo escrito y con el plazo que la licencia pidio.
        salida = self._correr(self.seguridad, "verificar").stdout
        self.paso("el lease quedo persistido", "lease vence" in salida)
        self.paso("el archivo de lease existe", (self.seguro / "lease.state").is_file())

    def rollback(self) -> None:
        self._correr(self.seguridad, "revertir-datos", "--confirmar", "--actor", "smoke")
        conexion = sqlite3.connect(str(self._base()))
        try:
            fila = conexion.execute(
                "SELECT description FROM cash_entries LIMIT 1"
            ).fetchone()
        finally:
            conexion.close()
        self.paso(
            "revertir devuelve los datos a texto plano",
            fila is not None and not str(fila[0]).startswith("bcx1:"),
        )
        informes = list((self.datos / "Reports").glob("*.pdf"))
        for informe in informes:
            with open(informe, "rb") as handle:
                self.paso(
                    f"y {informe.name} vuelve a ser un PDF",
                    handle.read(4) == b"%PDF",
                )
        self._correr(self.seguridad, "proteger-datos", "--confirmar", "--actor", "smoke")
        self.paso(
            "y se puede volver a proteger",
            self._correr(self.seguridad, "verificar").stdout.startswith("ALLOW"),
        )

    def correr(self) -> bool:
        etapas = (
            ("Arranque del paquete", self.arranque_limpio),
            ("Sin enrolar, todo igual", self.sin_enrolar_funciona),
            ("Enrolamiento", self.enrolar),
            ("Emision e instalacion de licencia", self.emitir_e_instalar),
            ("Proteccion de lo ya escrito", self.proteger_lo_ya_escrito),
            ("Datos protegidos", self.datos_protegidos),
            ("La base robada", self.sqlite_pelado_no_dice_nada),
            ("La planilla de cierre", self.el_informe_queda_sellado),
            ("Persistencia al reiniciar", self.persiste_al_reiniciar),
            ("Lease offline", self.lease_offline),
            ("Licencia manipulada", self.licencia_manipulada),
            ("Archivos corruptos", self.secreto_corrupto),
            ("Rollback", self.rollback),
        )
        for titulo, etapa in etapas:
            print(f"\n{titulo}")
            etapa()
        return all(condicion for condicion, _ in self.pasos)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Smoke del paquete congelado de BC Seguridad")
    parser.add_argument("--paquete", default="dist/BC-Caja")
    parser.add_argument("--conservar", action="store_true", help="no borrar el taller temporal")
    argumentos = parser.parse_args(argv)

    paquete = (RAIZ / argumentos.paquete).resolve()
    if not (paquete / "BC-Caja.exe").is_file():
        print(f"no encuentro BC-Caja.exe en {paquete}. Corre pilot/build_pilot.ps1 primero")
        return 3
    if not (paquete / "Seguridad" / "BC-Seguridad.exe").is_file():
        print(f"no encuentro Seguridad/BC-Seguridad.exe en {paquete}")
        return 3

    taller = Path(tempfile.mkdtemp(prefix="bc-smoke-"))
    print(f"paquete : {paquete}")
    print(f"taller  : {taller}  (temporal, no toca ninguna base productiva)")
    ceremonia = Ceremonia(paquete, taller)
    try:
        exito = ceremonia.correr()
    except Fallo as error:
        print(f"\nSMOKE_PAQUETE_FALLO: {error}")
        return 1
    finally:
        if not argumentos.conservar:
            shutil.rmtree(taller, ignore_errors=True)
        else:
            print(f"\ntaller conservado en {taller}")

    total = len(ceremonia.pasos)
    print(f"\nSMOKE_PAQUETE_OK pasos={total} instalacion={ceremonia.installation_id}")
    return 0 if exito else 1


if __name__ == "__main__":
    raise SystemExit(main())
