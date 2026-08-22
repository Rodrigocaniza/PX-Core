"""Escaneo de canarios: ningun artefacto persistente de BC dice el nombre del paciente.

Las pruebas de aceptacion miran la base. Esta mira **todo lo que BC deja en
disco**, porque proteger la base y dejar al lado una carpeta de PDFs con la
misma informacion no protege a nadie — quien copia la carpeta se lleva lo
mismo, en un formato mas comodo de leer.

Como funciona: se carga un dia entero con valores canario —cadenas que no
existen en ninguna otra parte del sistema— se cierra la Caja por el camino
real, y despues se recorre **cada byte de cada archivo** que BC dejo bajo su
raiz de datos y bajo su carpeta de seguridad. Ningun canario puede aparecer.

Lo que esta prueba encontro cuando se escribio: la planilla de cierre
(`Reports/cierre-*.pdf`) llevaba nombre, telefono, receta y observaciones en
claro, en la misma carpeta que la base cifrada. Estaba desde antes de este
slice y no lo habia mirado nadie.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from modulos.seguridad import runtime
from modulos.seguridad.application import enrollment, keyring, verifier
from modulos.seguridad.application.field_protection import FieldCipher

from .conftest import emitir_para, enrolar

# Cadenas que no existen en ningun otro lugar del sistema. Si aparecen en un
# archivo, llegaron desde el dato que cargamos y no desde otra parte.
CANARIOS = {
    "nombre": "ZQXPACIENTE CANARIO",
    "telefono": "0999-CANARIO-771",
    "documento": "9.998.887-CNRY",
    "receta": "DRA ZQXCANARIO",
    "observacion": "ZQXOBSERVACION CLINICA CANARIO",
}

# El numero de sobre NO es canario y va en claro a proposito. No es un dato de
# la persona: es el identificador operativo del trabajo, el que se canta en el
# mostrador y por el que se busca. Cifrarlo romperia las dos busquedas por sobre
# —que son SQL— sin proteger a nadie. Queda documentado aca, que es donde
# alguien lo va a buscar si duda.
SOBRE_EN_CLARO = "ZQXSOBRE-1"

# Lo mismo, y por el mismo motivo: importes, fechas, sucursal, vendedora y
# estados van en claro. Son la contabilidad y la operacion, no la persona, y
# cifrarlos romperia totales, filtros y reportes.

# Extensiones que se leen como texto ademas de como bytes, para que un canario
# escrito en UTF-16 o con separadores no se escape del control.
_TEXTO = {".txt", ".json", ".log", ".csv", ".md"}


@pytest.fixture
def instalacion_protegida(pc_a, emisor, confianza):
    """PC enrolada, con licencia, clave de datos y el cifrador ACTIVO."""
    _identidad, solicitud = enrolar(pc_a)
    firmada = emitir_para(emisor, solicitud)
    verifier.install_license(pc_a.contexto(trust=confianza), firmada.to_envelope())
    secreto = enrollment.open_secret(pc_a.paths, pc_a.sealer, pc_a.fingerprint)
    clave, frase = keyring.create_data_key(pc_a.database, secreto)
    cifrador = FieldCipher(key=clave.raw, dek_id=clave.dek_id)
    runtime.activate(pc_a.database, cifrador)
    return {"pc": pc_a, "cifrador": cifrador, "frase": frase}


def _cerrar_un_dia_con_canarios(pc) -> Path:
    """Un dia completo por el camino real: apertura, venta, arqueo y cierre.

    Se usa el controlador de produccion —no un atajo— porque lo que se quiere
    ejercer es lo que va a correr en la Optica, incluida la generacion del PDF
    de cierre y la exportacion al TXT de movimientos.
    """
    from modulos.caja_diaria.bootstrap import build_cash_day_controller
    from modulos.caja_diaria.config import CashDataPaths

    raiz = pc.database.parent
    rutas = CashDataPaths(
        root=raiz, database=pc.database, backups=raiz / "Backups", logs=raiz / "Logs"
    ).ensure()
    controlador = build_cash_day_controller(data_paths=rutas)
    try:
        dia, _ = controlador.add_manual_entry(
            {
                "fecha": "04-03-2026", "unidad": "PC", "caja_inicial": "100000",
                "descripcion": CANARIOS["nombre"], "sobre": SOBRE_EN_CLARO,
                "arm_org": "", "cod": "", "armazon": "", "cristal": "",
                "laboratorio": "LAB", "receta_dr": CANARIOS["receta"],
                "total": "250000", "efectivo": "250000", "tarjeta_cheque": "",
                "ordenes": "", "cuotas": "", "saldo": "", "gastos": "",
                "vendedora": "VENDEDORA",
                # Los nombres son los del formulario legacy. Con las claves
                # equivocadas el valor se descarta en silencio y la prueba pasa
                # sin haber plantado nada: por eso mas abajo se verifica que lo
                # guardado sea lo que se quiso guardar.
                "cliente_documento": CANARIOS["documento"],
                "cliente_telefono": CANARIOS["telefono"],
                "notas": CANARIOS["observacion"],
            }
        )
        guardada = controlador.service.repository.get(dia.id).entries[0]
        plantados = {
            "nombre": guardada.description,
            "telefono": guardada.customer_phone,
            "documento": guardada.customer_document,
            "receta": guardada.prescription_doctor,
            "observacion": guardada.observations,
        }
        faltantes = [
            etiqueta for etiqueta, valor in CANARIOS.items() if plantados.get(etiqueta) != valor
        ]
        assert not faltantes, (
            f"la prueba no llego a plantar {faltantes}: sin eso el escaneo de mas "
            "abajo no estaria buscando nada y pasaria por vacio"
        )

        cerrado, _cuenta, _correo = controlador.admin.close_with_count(
            dia.id, {50_000: 7}, "Responsable", "cierre-canario"
        )
        # `close_with_count` cierra y genera la planilla. La exportacion al TXT
        # legacy y el respaldo local viven en otro camino del controlador; se
        # llaman aca a proposito para que el escaneo vea TODOS los archivos que
        # BC puede dejar en disco, no solo los de un flujo.
        controlador.movements_exporter.sync_closed_day(cerrado)
        controlador.backup_service.create_backup("cierre")
    finally:
        controlador.service.repository.close()
    return raiz


def _archivos_persistentes(*raices: Path) -> list[Path]:
    encontrados: list[Path] = []
    for raiz in raices:
        if not raiz.exists():
            continue
        for archivo in sorted(raiz.rglob("*")):
            if archivo.is_file():
                encontrados.append(archivo)
    return encontrados


def _canarios_en(archivo: Path) -> list[str]:
    """Busca los canarios en bytes y, si el archivo es de texto, tambien en UTF-16."""
    try:
        crudo = archivo.read_bytes()
    except OSError:  # pragma: no cover - archivo bloqueado por el sistema
        return []
    encontrados = []
    for etiqueta, valor in CANARIOS.items():
        if valor.encode("utf-8") in crudo:
            encontrados.append(etiqueta)
        elif archivo.suffix.lower() in _TEXTO and valor.encode("utf-16-le") in crudo:
            encontrados.append(etiqueta)
    return encontrados


class TestNingunArtefactoPersistenteExponePII:
    def test_ni_un_canario_en_ningun_archivo_de_bc(self, instalacion_protegida):
        pc = instalacion_protegida["pc"]
        raiz = _cerrar_un_dia_con_canarios(pc)
        runtime.clear()  # como quien se lleva los archivos y no tiene la clave

        fugas: dict[str, list[str]] = {}
        archivos = _archivos_persistentes(raiz, pc.paths.root)
        assert archivos, "la prueba no encontro ningun archivo: no estaria probando nada"
        for archivo in archivos:
            encontrados = _canarios_en(archivo)
            if encontrados:
                fugas[str(archivo.relative_to(raiz.parent))] = encontrados
        assert fugas == {}, f"artefactos de BC con datos del paciente en claro: {fugas}"

    def test_el_escaneo_detecta_de_verdad(self, instalacion_protegida, tmp_path):
        """Un control que no puede fallar no es un control.

        Se planta un canario a mano y se comprueba que el escaneo lo ve. Sin
        esto, la prueba de arriba pasaria igual si el buscador estuviera roto.
        """
        plantado = tmp_path / "fuga" / "informe.txt"
        plantado.parent.mkdir(parents=True, exist_ok=True)
        plantado.write_text(f"cliente: {CANARIOS['nombre']}", encoding="utf-8")
        assert _canarios_en(plantado) == ["nombre"]

    def test_el_wal_y_el_shm_tampoco_dicen_nada(self, instalacion_protegida):
        """El WAL guarda paginas recien escritas; si el cifrado fuera tardio, ahi se veria."""
        pc = instalacion_protegida["pc"]
        _cerrar_un_dia_con_canarios(pc)
        for sufijo in ("-wal", "-shm"):
            companero = pc.database.with_name(pc.database.name + sufijo)
            if companero.is_file():
                assert _canarios_en(companero) == [], companero.name

    def test_los_respaldos_de_la_base_tampoco(self, instalacion_protegida):
        pc = instalacion_protegida["pc"]
        raiz = _cerrar_un_dia_con_canarios(pc)
        respaldos = list((raiz / "Backups").glob("*.sqlite3"))
        assert respaldos, "el cierre tiene que haber dejado al menos un respaldo"
        for respaldo in respaldos:
            assert _canarios_en(respaldo) == [], respaldo.name

    def test_la_planilla_de_cierre_queda_sellada(self, instalacion_protegida):
        from modulos.seguridad.application import file_protection

        pc = instalacion_protegida["pc"]
        raiz = _cerrar_un_dia_con_canarios(pc)
        informes = list((raiz / "Reports").glob("*.pdf"))
        assert informes, "el cierre tiene que haber generado la planilla"
        for informe in informes:
            assert file_protection.is_sealed(informe), informe.name
            assert _canarios_en(informe) == []

    def test_pero_bc_la_sigue_pudiendo_abrir(self, instalacion_protegida):
        """Sellarla no puede significar perderla."""
        from modulos.seguridad.application import file_protection

        pc = instalacion_protegida["pc"]
        raiz = _cerrar_un_dia_con_canarios(pc)
        informe = next((raiz / "Reports").glob("*.pdf"))
        contenido = file_protection.read_maybe_sealed(
            instalacion_protegida["cifrador"], informe
        )
        assert contenido.startswith(b"%PDF"), "lo abierto tiene que ser el PDF original"
        assert CANARIOS["nombre"].encode("utf-8") in contenido or len(contenido) > 1000

    def test_sin_la_clave_el_informe_no_se_abre(self, instalacion_protegida):
        from modulos.seguridad.application import file_protection
        from modulos.seguridad.crypto.primitives import random_bytes
        from modulos.seguridad.errors import DataProtectionError

        pc = instalacion_protegida["pc"]
        raiz = _cerrar_un_dia_con_canarios(pc)
        informe = next((raiz / "Reports").glob("*.pdf"))
        ajeno = FieldCipher(key=random_bytes(32), dek_id="ajena")
        with pytest.raises(DataProtectionError):
            file_protection.read_maybe_sealed(ajeno, informe)
        with pytest.raises(DataProtectionError):
            file_protection.read_maybe_sealed(None, informe)


class TestMovimientosTxtNoLlevaDatosDePersonas:
    """`movimientos.txt` se audito columna por columna y **no lleva PII**.

    Es el puente al sistema legacy de Gestion y publica una sola linea por
    concepto y por dia con la forma
    `Tipo|Fecha|Origen|Destino|Importe|Si|BC_CAJA:<dia>:<concepto>`. No hay
    nombre, ni telefono, ni documento, ni receta, ni observacion: hay plata
    agregada del dia.

    Esta prueba fija esa forma. Existe para que el dia que alguien quiera
    agregarle "el cliente" a la linea del TXT —que es una idea razonable y
    tentadora— la prueba se ponga roja antes de que llegue a produccion.
    """

    def test_la_linea_exportada_solo_lleva_plata(self, instalacion_protegida):
        pc = instalacion_protegida["pc"]
        raiz = _cerrar_un_dia_con_canarios(pc)
        movimientos = raiz / "movimientos.txt"
        assert movimientos.is_file(), "el cierre tiene que haber exportado al TXT legacy"

        lineas = [
            linea for linea in movimientos.read_text(encoding="utf-8").splitlines()
            if linea.strip()
        ]
        assert lineas
        for linea in lineas:
            partes = linea.split("|")
            assert len(partes) == 7, linea
            tipo, fecha, origen, destino, importe, conciliado, marcador = partes
            assert tipo in {"Ingreso", "Egreso"}, tipo
            assert importe.isdigit(), importe
            assert conciliado in {"Si", "No"}
            assert marcador.startswith("BC_CAJA:"), marcador
            assert _canarios_en(movimientos) == []

    def test_el_exportador_no_conoce_ningun_campo_de_persona(self):
        """Barrido estatico: el modulo ni siquiera nombra las columnas del paciente."""
        fuente = (
            Path(__file__).resolve().parents[2]
            / "modulos" / "caja_diaria" / "infrastructure" / "movements_exporter.py"
        ).read_text(encoding="utf-8")
        for campo in (
            "customer_name", "customer_phone", "customer_document",
            "observations", "prescription_doctor", "description",
        ):
            assert campo not in fuente, campo


class TestLaBaseRobadaSigueSiendoIlegible:
    def test_sqlite_pelado_no_muestra_al_paciente(self, instalacion_protegida):
        pc = instalacion_protegida["pc"]
        _cerrar_un_dia_con_canarios(pc)
        runtime.clear()
        conexion = sqlite3.connect(str(pc.database))
        filas = conexion.execute(
            "SELECT description, customer_phone, customer_document, observations,"
            " prescription_doctor FROM cash_entries"
        ).fetchall()
        conexion.close()
        assert filas
        for fila in filas:
            for valor in fila:
                assert not any(canario in str(valor) for canario in CANARIOS.values())
