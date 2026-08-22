"""Los contratos que sostienen todo lo demas.

Estas pruebas no ejercen un flujo: verifican propiedades estructurales que, si
se rompen, vacian de contenido a las pruebas de aceptacion. Son las que van a
fallar el dia que alguien agregue, con la mejor intencion, una consulta que
filtra por una columna cifrada o una clave privada al repositorio.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from modulos.seguridad import trust
from modulos.seguridad.application.field_protection import PROTECTED_COLUMNS
from modulos.seguridad.errors import SecurityError, TrustStoreError
from modulos.seguridad.infrastructure import security_db

RAIZ = Path(__file__).resolve().parents[2]
MIGRACION_033 = (
    RAIZ / "modulos" / "caja_diaria" / "infrastructure" / "migrations" / "033_security_v1.sql"
)


def _fuentes_de_produccion() -> list[Path]:
    return [
        archivo
        for archivo in (RAIZ / "modulos").rglob("*.py")
        if "__pycache__" not in archivo.parts
    ]


# ==========================================================================
class TestElEmisorNoViajaConElCliente:
    def test_ningun_modulo_del_cliente_importa_el_emisor(self):
        """Si el cliente importara el emisor, la clave privada tendria un camino.

        No lo tiene hoy, y esta prueba es lo que impide que lo tenga manana.
        """
        culpables = []
        for archivo in _fuentes_de_produccion():
            if "seguridad" in archivo.parts and "issuer" in archivo.parts:
                continue
            texto = archivo.read_text(encoding="utf-8")
            if re.search(r"^\s*from .*issuer import|^\s*import .*\.issuer", texto, re.MULTILINE):
                culpables.append(str(archivo.relative_to(RAIZ)))
        assert culpables == []

    def test_el_entrypoint_de_bc_caja_no_alcanza_al_emisor(self):
        entrypoint = (RAIZ / "bc_caja.py").read_text(encoding="utf-8")
        assert "issuer" not in entrypoint

    def test_no_hay_clave_privada_en_el_repositorio(self):
        """Ni una clave privada, ni el archivo sellado del emisor."""
        sospechosos = list(RAIZ.rglob("*issuer*.key.json")) + list(RAIZ.rglob("*.pem"))
        sospechosos = [ruta for ruta in sospechosos if ".git" not in ruta.parts]
        assert sospechosos == []

    def test_el_almacen_que_viaja_solo_tiene_claves_publicas(self):
        documento = trust.BUILTIN_TRUST_FILE.read_text(encoding="utf-8")
        for palabra in ("private", "privada", "sealed_private_key", "secret"):
            assert palabra not in documento.lower()
        almacen = trust.load({})
        assert almacen.source == "builtin"
        for emisor in almacen.issuers:
            assert len(emisor.public_key) == 32


# ==========================================================================
class TestElAlmacenDeConfianzaNoSeAmpliaDesdeElDisco:
    def test_en_produccion_solo_manda_el_almacen_del_paquete(self, tmp_path, monkeypatch):
        """El ataque: dejar la clave publica propia al lado del ejecutable."""
        propio = tmp_path / "mio.json"
        propio.write_text('{"format": "bc.trust.v1", "issuers": []}', encoding="utf-8")
        monkeypatch.setattr(trust, "_frozen", lambda: True)
        almacen = trust.load({trust.TEST_TRUST_ENV: str(propio)})
        assert almacen.source == "builtin"

    def test_fuera_del_paquete_la_puerta_de_pruebas_existe(self, tmp_path, monkeypatch):
        """Se declara como es: en desarrollo la variable si se respeta."""
        from modulos.seguridad.issuer import issuer as issuer_module

        clave = issuer_module.generate("solo pruebas")
        propio = tmp_path / "mio.json"
        import json

        propio.write_text(json.dumps(issuer_module.trust_document([clave])), encoding="utf-8")
        monkeypatch.setattr(trust, "_frozen", lambda: False)
        almacen = trust.load({trust.TEST_TRUST_ENV: str(propio)})
        assert almacen.source.startswith("test:")

    def test_un_key_id_declarado_que_no_corresponde_se_rechaza(self):
        from modulos.seguridad.canonical import b64u_encode
        from modulos.seguridad.crypto.primitives import (
            generate_signing_key,
            public_key_bytes,
        )

        publica = public_key_bytes(generate_signing_key().public_key())
        with pytest.raises(TrustStoreError):
            trust.parse(
                {
                    "format": "bc.trust.v1",
                    "issuers": [
                        {"key_id": "0" * 16, "public_key": b64u_encode(publica), "active": True}
                    ],
                },
                source="prueba",
            )

    def test_un_almacen_vacio_se_rechaza(self):
        with pytest.raises(TrustStoreError):
            trust.parse({"format": "bc.trust.v1", "issuers": []}, source="prueba")


# ==========================================================================
class TestLaMigracion033EsAditivaEstricta:
    def _sql_sin_comentarios(self) -> str:
        lineas = [
            linea
            for linea in MIGRACION_033.read_text(encoding="utf-8").splitlines()
            if not linea.strip().startswith("--")
        ]
        return "\n".join(lineas).upper()

    def test_no_altera_ni_borra_ni_actualiza_nada(self):
        # Se buscan SENTENCIAS, no palabras: `BEFORE UPDATE ON` es la definicion
        # de un disparador y no reescribe nada. Buscar la palabra suelta habria
        # dado un rojo falso y el arreglo natural habria sido aflojar la prueba.
        sql = self._sql_sin_comentarios()
        prohibidas = re.findall(
            r"(?m)^\s*(ALTER\s+TABLE|UPDATE\b|DELETE\s+FROM|DROP\s+TABLE|DROP\s+INDEX|"
            r"DROP\s+TRIGGER|INSERT\s+INTO)",
            sql,
        )
        assert prohibidas == [], prohibidas

    def test_no_nombra_ninguna_tabla_de_historia_economica(self):
        sql = self._sql_sin_comentarios()
        for tabla in (
            "CASH_ENTRIES", "CASH_DAYS", "SALE_ITEMS", "ORDERS", "STOCK_MOVEMENTS",
            "ARTICLES", "PURCHASES", "SERVICE_JOBS", "SERVICE_JOB_COMMISSIONS",
            "TRACKED_WORKS", "DOMAIN_EVENTS",
        ):
            assert tabla not in sql, tabla

    def test_solo_crea_cosas_que_no_existen(self):
        sql = self._sql_sin_comentarios()
        creaciones = re.findall(r"CREATE\s+(?:UNIQUE\s+)?(TABLE|INDEX|TRIGGER)\s+(\S+)", sql)
        assert creaciones, "la migracion tiene que crear algo"
        for _tipo, siguiente in creaciones:
            assert siguiente == "IF", "toda creacion tiene que ser IF NOT EXISTS"

    def test_aplicarla_no_cambia_ni_una_fila_de_negocio(self, tmp_path):
        """Se corre la cadena entera y se comprueba que las tres tablas quedan vacias."""
        import sqlite3

        from modulos.caja_diaria.infrastructure.sqlite_repository import (
            SQLiteCashDayRepository,
        )

        base = tmp_path / "bc.sqlite3"
        repositorio = SQLiteCashDayRepository(base)
        repositorio.close()
        conexion = sqlite3.connect(str(base))
        for tabla in ("security_state", "security_keyring", "security_audit"):
            assert conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0] == 0
        conexion.close()

    def test_la_033_es_la_ultima_de_la_cadena(self):
        migraciones = sorted(MIGRACION_033.parent.glob("*.sql"))
        assert migraciones[-1].name == "033_security_v1.sql"
        assert migraciones[-2].name.startswith("032")


# ==========================================================================
class TestNingunaColumnaProtegidaSeComparaEnSQL:
    """El defecto silencioso mas peligroso de esta capa.

    Un `WHERE customer_phone = ?` sobre datos cifrados no da error: devuelve
    cero filas, siempre, sin decir nada. Aparece meses despues como "a veces no
    encuentra al cliente". Se busca estaticamente en todo el codigo de
    produccion.
    """

    COMPARACION = r"(?:=|<>|!=|\bLIKE\b|\bIN\b|\bGLOB\b)"

    def _columnas(self):
        for tabla, columnas in PROTECTED_COLUMNS.items():
            for columna in columnas:
                yield tabla, columna

    def test_ninguna_comparacion_en_sql_de_produccion(self):
        hallazgos = []
        for archivo in _fuentes_de_produccion():
            if "seguridad" in archivo.parts:
                continue  # la propia capa las nombra para protegerlas
            texto = archivo.read_text(encoding="utf-8")
            for _tabla, columna in self._columnas():
                patron = rf"\b{re.escape(columna)}\b\s*{self.COMPARACION}\s*\?"
                for coincidencia in re.finditer(patron, texto, re.IGNORECASE):
                    linea = texto[: coincidencia.start()].count("\n") + 1
                    hallazgos.append(f"{archivo.relative_to(RAIZ)}:{linea} {columna}")
        assert hallazgos == [], (
            "estas comparaciones devolverian cero filas en silencio sobre datos "
            f"protegidos: {hallazgos}"
        )

    def test_ninguna_ordena_ni_agrupa_por_columna_protegida(self):
        hallazgos = []
        for archivo in _fuentes_de_produccion():
            if "seguridad" in archivo.parts:
                continue
            texto = archivo.read_text(encoding="utf-8")
            for clausula in ("ORDER BY", "GROUP BY"):
                for coincidencia in re.finditer(
                    rf"{clausula}\s+([^\n;\"']+)", texto, re.IGNORECASE
                ):
                    fragmento = coincidencia.group(1)
                    for _tabla, columna in self._columnas():
                        if re.search(rf"\b{re.escape(columna)}\b", fragmento, re.IGNORECASE):
                            linea = texto[: coincidencia.start()].count("\n") + 1
                            hallazgos.append(f"{archivo.relative_to(RAIZ)}:{linea} {columna}")
        assert hallazgos == []

    def test_el_registro_no_incluye_columnas_que_no_existen(self):
        """Un nombre mal escrito en el registro protegeria nada, en silencio."""
        import sqlite3
        import tempfile

        from modulos.caja_diaria.infrastructure.sqlite_repository import (
            SQLiteCashDayRepository,
        )

        with tempfile.TemporaryDirectory() as carpeta:
            base = Path(carpeta) / "bc.sqlite3"
            repositorio = SQLiteCashDayRepository(base)
            repositorio.close()
            conexion = sqlite3.connect(str(base))
            for tabla, columnas in PROTECTED_COLUMNS.items():
                reales = {fila[1] for fila in conexion.execute(f"PRAGMA table_info({tabla})")}
                assert reales, f"{tabla} no existe en el esquema"
                faltan = set(columnas) - reales
                assert not faltan, f"{tabla}: {faltan}"
            conexion.close()


# ==========================================================================
class TestNoHaySecretosEnElCodigoNiEnLaBitacora:
    def test_no_hay_contrasenas_ni_claves_cableadas(self):
        """Lo que la mision prohibe explicito: password hardcodeado, AES key fija."""
        sospechas = []
        patrones = (
            r"password\s*=\s*[\"'][^\"']{4,}[\"']",
            r"passphrase\s*=\s*[\"'][^\"']{4,}[\"']",
            r"AES_KEY\s*=",
            r"SECRET_KEY\s*=\s*[\"']",
        )
        for archivo in (RAIZ / "modulos" / "seguridad").rglob("*.py"):
            texto = archivo.read_text(encoding="utf-8")
            for patron in patrones:
                if re.search(patron, texto, re.IGNORECASE):
                    sospechas.append(f"{archivo.name}: {patron}")
        assert sospechas == []

    def test_toda_clave_sale_del_csprng_o_de_un_kdf(self):
        """Ni un `random` en la capa: `random` no es criptografico."""
        for archivo in (RAIZ / "modulos" / "seguridad").rglob("*.py"):
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Import):
                    assert all(alias.name != "random" for alias in nodo.names), archivo.name
                if isinstance(nodo, ast.ImportFrom):
                    assert nodo.module != "random", archivo.name

    @pytest.mark.parametrize(
        "campo",
        ["clave", "secret", "dek", "passphrase", "private_key", "mac", "firma", "seed"],
    )
    def test_la_bitacora_rechaza_campos_que_parecen_material(self, tmp_path, campo):
        from modulos.seguridad.infrastructure.security_db import _reject_secrets

        with pytest.raises(SecurityError):
            _reject_secrets({campo: "lo que sea"})

    @pytest.mark.parametrize("campo", ["dek_id", "issuer_key_id", "license_id", "installation_id"])
    def test_la_bitacora_si_acepta_identificadores(self, campo):
        from modulos.seguridad.infrastructure.security_db import _reject_secrets

        assert _reject_secrets({campo: "abc"}) == {campo: "abc"}

    def test_una_decision_no_lleva_material_a_la_auditoria(self, instalacion_valida, confianza):
        from modulos.seguridad.application import verifier

        pc = instalacion_valida["pc"]
        decision = verifier.authorize(pc.contexto(trust=confianza))
        detalle = str(decision.audit_details())
        assert instalacion_valida["cifrador"].key.hex() not in detalle
        assert instalacion_valida["frase"] not in detalle
        for componente in pc.fingerprint.components.values():
            assert componente not in detalle

    def test_la_huella_nunca_se_guarda_en_crudo(self, instalacion_valida):
        pc = instalacion_valida["pc"]
        for archivo in pc.paths.root.iterdir():
            if not archivo.is_file():
                continue
            contenido = archivo.read_text(encoding="utf-8", errors="ignore")
            for componente in pc.fingerprint.components.values():
                assert componente not in contenido, f"{archivo.name} filtra {componente}"


# ==========================================================================
class TestLaCapaNoDependeDelDominio:
    def test_seguridad_no_importa_caja_ni_comercial(self):
        """La direccion de la dependencia es lo que la hace transversal."""
        culpables = []
        for archivo in (RAIZ / "modulos" / "seguridad").rglob("*.py"):
            texto = archivo.read_text(encoding="utf-8")
            for prohibido in ("caja_diaria", "comercial", "gestion_central"):
                if prohibido in texto:
                    culpables.append(f"{archivo.name} -> {prohibido}")
        assert culpables == []

    def test_los_eventos_de_auditoria_tienen_nombres_estables(self):
        """Se buscan en produccion meses despues; renombrarlos rompe la historia."""
        assert security_db.EVENT_AUTHORIZATION == "VALIDACION"
        assert security_db.EVENT_ENROLLED == "ENROLAMIENTO"
        assert security_db.EVENT_DATA_PROTECTED == "DATOS_PROTEGIDOS"
        assert security_db.EVENT_DATA_ROLLBACK == "DATOS_REVERTIDOS"
        assert security_db.EVENT_REVOCATION_INSTALLED == "REVOCACION_INSTALADA"
