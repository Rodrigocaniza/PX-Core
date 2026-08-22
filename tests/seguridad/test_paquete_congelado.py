"""Que el paquete congelado lleve todo lo que la capa necesita en ejecucion.

Esta prueba existe por un defecto real. El primer build de BC con seguridad
salio "bien": PyInstaller termino sin errores y el EXE arrancaba. Y no incluia
`modulos/seguridad/trusted_issuers.json`, porque no es codigo y PyInstaller no
lo ve. Un BC congelado sin almacen de confianza no puede verificar **ninguna**
licencia: toda instalacion enrolada queda en DENY. Se habria descubierto en la
Optica, el lunes, con la base ya cifrada.

La leccion, escrita como control: **funcionar desde Python no dice nada sobre
funcionar congelado.** Todo archivo que la capa de seguridad lea en ejecucion y
no sea un `.py` tiene que estar declarado en el script de build, y esta prueba
lo verifica leyendo los dos.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BUILD = RAIZ / "pilot" / "build_pilot.ps1"

# Archivos que la capa lee en ejecucion y que NO son codigo. Si se agrega uno,
# agregarlo aca y al build; si no, el paquete arranca y falla en la Optica.
RECURSOS_DE_EJECUCION = (
    "modulos/seguridad/trusted_issuers.json",
    "modulos/caja_diaria/infrastructure/migrations",
)


def _script() -> str:
    return BUILD.read_text(encoding="utf-8")


class TestElBuildDeclaraLosRecursosQueNoSonCodigo:
    @pytest.mark.parametrize("recurso", RECURSOS_DE_EJECUCION)
    def test_el_build_declara_todo_lo_que_la_capa_lee_en_ejecucion(self, recurso):
        script = _script()
        assert f'--add-data "{recurso};' in script, (
            f"{recurso} no esta en --add-data. PyInstaller no lo va a incluir y el "
            "paquete va a fallar recien en la PC de la Optica"
        )

    def test_los_recursos_declarados_existen_en_el_repositorio(self):
        for recurso in RECURSOS_DE_EJECUCION:
            assert (RAIZ / recurso).exists(), recurso

    def test_el_build_verifica_el_contenido_del_paquete(self):
        """El build tiene que romperse si falta algo, no dejarlo pasar."""
        script = _script()
        assert "BC_CAJA_PACKAGE_CONTENTS_OK" in script
        assert "el paquete no incluye" in script
        for esperado in (
            "modulos/seguridad/trusted_issuers.json",
            "033_security_v1.sql",
            "cryptography/hazmat/bindings/_rust.pyd",
        ):
            assert esperado in script, esperado


class TestElAlmacenDeConfianzaEsIndispensable:
    def test_sin_almacen_no_se_puede_verificar_nada(self, monkeypatch):
        """Documenta el modo de falla exacto que el defecto habria producido."""
        from modulos.seguridad import trust
        from modulos.seguridad.errors import TrustStoreError

        monkeypatch.setattr(trust, "BUILTIN_TRUST_FILE", Path("no-existe.json"))
        with pytest.raises(TrustStoreError):
            trust.load({})

    def test_el_almacen_del_paquete_se_lee_por_ruta_relativa_al_modulo(self):
        """Por eso hace falta empaquetarlo: no se resuelve contra el cwd.

        `Path(__file__).with_name(...)` dentro de un paquete congelado apunta a
        `_internal/modulos/seguridad/`, que es exactamente donde el `--add-data`
        lo deja. Si alguien cambiara esto por una ruta relativa al directorio de
        trabajo, BC dejaria de encontrarlo al ejecutarse desde otra carpeta.
        """
        from modulos.seguridad import trust

        fuente = (RAIZ / "modulos" / "seguridad" / "trust.py").read_text(encoding="utf-8")
        assert "Path(__file__).with_name" in fuente
        assert trust.BUILTIN_TRUST_FILE.is_file()


class TestLasDependenciasBinariasEstanDeclaradas:
    def test_cryptography_esta_en_requirements(self):
        requisitos = (RAIZ / "requirements.txt").read_text(encoding="utf-8")
        assert re.search(r"^cryptography[><=]", requisitos, re.MULTILINE), (
            "cryptography tiene que estar en requirements.txt: el paquete lo lleva "
            "porque esta declarado, no por casualidad"
        )

    def test_las_primitivas_salen_de_cryptography_y_no_de_otra_parte(self):
        """Si alguien la reemplaza por una implementacion propia, esto se pone rojo."""
        fuente = (
            RAIZ / "modulos" / "seguridad" / "crypto" / "primitives.py"
        ).read_text(encoding="utf-8")
        assert "from cryptography" in fuente
        for artesanal in ("def _aes(", "S_BOX", "def _ed25519_scalar", "0x6a09e667"):
            assert artesanal not in fuente, artesanal


class TestElInstructivoDeLaOpticaEsEjecutable:
    """Cada comando escrito en el instructivo tiene que parsear de verdad.

    Esta clase existe por un defecto que el smoke encontro: el instructivo pedia
    `proteger-datos --confirmar --actor "tu nombre"` y argparse contestaba
    `unrecognized arguments: --actor`, porque `--actor` estaba declarado solo
    antes del subcomando. Nadie escribe las opciones globales primero. Se
    corrigio el programa —ahora las acepta en los dos lugares— y se agrego este
    control, que lee el instructivo y prueba lo que dice.
    """

    INSTRUCTIVO = RAIZ / "docs" / "INSTALACION_SEGURIDAD_EN_LA_OPTICA.md"

    def _comandos_del_instructivo(self) -> list[list[str]]:
        import shlex

        comandos = []
        for linea in self.INSTRUCTIVO.read_text(encoding="utf-8").splitlines():
            limpia = linea.strip()
            if not limpia.startswith('Seguridad\\BC-Seguridad.exe'):
                continue
            limpia = limpia.split("#", 1)[0]
            partes = shlex.split(limpia.replace("\\", "/"))[1:]
            if partes:
                comandos.append(partes)
        return comandos

    def test_el_instructivo_muestra_comandos(self):
        assert len(self._comandos_del_instructivo()) >= 8, (
            "si esto baja, alguien reescribio el instructivo y esta prueba dejo de mirarlo"
        )

    def test_todos_los_comandos_del_instructivo_parsean(self):
        import sys as _sys

        _sys.path.insert(0, str(RAIZ))
        from tools.bc_security import construir_parser

        fallos = []
        for argumentos in self._comandos_del_instructivo():
            try:
                construir_parser().parse_args(argumentos)
            except SystemExit:
                fallos.append(" ".join(argumentos))
        assert fallos == [], f"el instructivo pide comandos que el programa rechaza: {fallos}"

    def test_las_opciones_globales_se_aceptan_despues_del_subcomando(self):
        import sys as _sys

        _sys.path.insert(0, str(RAIZ))
        from tools.bc_security import construir_parser

        despues = construir_parser().parse_args(
            ["proteger-datos", "--confirmar", "--actor", "Rodrigo", "--base", "x.sqlite3"]
        )
        antes = construir_parser().parse_args(
            ["--actor", "Rodrigo", "--base", "x.sqlite3", "proteger-datos", "--confirmar"]
        )
        assert despues.actor == antes.actor == "Rodrigo"
        assert despues.base == antes.base == "x.sqlite3"
