"""Las pruebas de aceptacion A a L que la mision exige, una por una.

Cada clase lleva la letra en el nombre para que la trazabilidad entre lo pedido
y lo probado no dependa de que alguien mantenga una tabla aparte.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import timedelta

import pytest

from modulos.seguridad import bootstrap, runtime
from modulos.seguridad.application import data_migration, enrollment, keyring, verifier
from modulos.seguridad.application.field_protection import FieldCipher, looks_protected
from modulos.seguridad.domain import decisions
from modulos.seguridad.errors import SealedStoreError, SecurityError
from modulos.seguridad.infrastructure import security_db

from .conftest import ahora, emitir_para, enrolar


def _clonar(origen, destino) -> None:
    """Copia la instalacion entera de una PC a otra: archivos de seguridad y base.

    Es literalmente lo que hace alguien con un pendrive.
    """
    destino.paths.root.mkdir(parents=True, exist_ok=True)
    for archivo in origen.paths.root.iterdir():
        if archivo.is_file():
            shutil.copy2(archivo, destino.paths.root / archivo.name)
    destino.database.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen.database, destino.database)


# ==========================================================================
class TestA_InstalacionCorrectaPermite:
    def test_la_instalacion_legitima_arranca(self, instalacion_valida, confianza):
        decision = verifier.authorize(instalacion_valida["pc"].contexto(trust=confianza))
        assert decision.outcome == decisions.ALLOW
        assert decision.reason == decisions.REASON_OK
        assert decision.allowed

    def test_la_licencia_dice_que_puede_hacer(self, instalacion_valida, confianza):
        decision = verifier.authorize(instalacion_valida["pc"].contexto(trust=confianza))
        assert decision.allows("bc.caja")
        assert decision.allows("bc.sync")
        assert not decision.allows("bc.inexistente")

    def test_el_arranque_deja_el_cifrador_activo(self, instalacion_valida, confianza):
        pc = instalacion_valida["pc"]
        arranque = bootstrap.arrancar(pc.contexto(trust=confianza))
        assert arranque.allowed
        assert arranque.data_protected
        assert runtime.cipher_for(pc.database) is not None

    def test_sin_enrolar_bc_funciona_como_siempre(self, pc_a, confianza):
        """La condicion para poder instalar esto sin cortar la operacion."""
        arranque = bootstrap.arrancar(pc_a.contexto(trust=confianza))
        assert not arranque.enrolled
        assert arranque.allowed
        assert arranque.cipher is None
        assert runtime.cipher_for(pc_a.database) is None


# ==========================================================================
class TestB_CarpetaCopiadaAOtraMaquinaDeniega:
    def test_la_misma_carpeta_en_otra_pc_no_arranca(self, instalacion_valida, pc_b, confianza):
        _clonar(instalacion_valida["pc"], pc_b)
        decision = verifier.authorize(pc_b.contexto(trust=confianza))
        assert decision.outcome == decisions.DENY
        assert decision.reason == decisions.REASON_BINDING_MISMATCH

    def test_aunque_falsifique_la_huella_el_secreto_no_abre(
        self, instalacion_valida, pc_b, confianza
    ):
        """La barrera dura no es la huella: es el sellado del sistema operativo.

        Se le da a la PC B la huella exacta de la PC A —que es lo mejor que
        podria conseguir quien falsifique nombre de equipo, serial y MachineGuid—
        y aun asi el secreto sellado no se recupera.
        """
        pc_a = instalacion_valida["pc"]
        _clonar(pc_a, pc_b)
        pc_b.fingerprint = pc_a.fingerprint  # huella clonada, hardware distinto
        decision = verifier.authorize(pc_b.contexto(trust=confianza))
        assert decision.outcome == decisions.DENY
        assert decision.reason == decisions.REASON_SECRET_UNAVAILABLE

    def test_el_clon_no_puede_leer_los_datos_del_clonado(
        self, instalacion_valida, pc_b, confianza
    ):
        pc_a = instalacion_valida["pc"]
        cifrador = instalacion_valida["cifrador"]
        data_migration.protect(pc_a.database, cifrador)
        _clonar(pc_a, pc_b)
        pc_b.fingerprint = pc_a.fingerprint
        with pytest.raises(SealedStoreError):
            enrollment.open_secret(pc_b.paths, pc_b.sealer, pc_b.fingerprint)

    def test_llevarse_solo_la_base_tampoco_sirve(self, instalacion_valida, pc_b, confianza):
        """El pendrive con un unico archivo adentro: `bc_caja.sqlite3`.

        Sin este control BC habria abierto tranquilo —la PC B no esta enrolada,
        asi que la capa "no aplica"— mostrando criptograma en pantalla y, peor,
        guardando lo nuevo en claro al lado de lo viejo cifrado. Eso arruina la
        base copiada sin que nadie se entere hasta mucho despues.
        """
        pc_a = instalacion_valida["pc"]
        data_migration.protect(pc_a.database, instalacion_valida["cifrador"])
        pc_b.database.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pc_a.database, pc_b.database)

        arranque = bootstrap.arrancar(pc_b.contexto(trust=confianza))
        assert not arranque.allowed
        assert arranque.decision.reason == decisions.REASON_NOT_ENROLLED
        assert runtime.cipher_for(pc_b.database) is None
        assert "otra instalacion" in arranque.message

    def test_el_intento_de_clon_queda_en_la_bitacora(self, instalacion_valida, pc_b, confianza):
        _clonar(instalacion_valida["pc"], pc_b)
        verifier.authorize(pc_b.contexto(trust=confianza))
        eventos = security_db.read_audit(pc_b.database)
        assert any(
            fila["event"] == security_db.EVENT_AUTHORIZATION
            and fila["reason"] == decisions.REASON_BINDING_MISMATCH
            for fila in eventos
        )

    def test_cambiar_un_disco_no_deja_a_la_optica_sin_caja(self, instalacion_valida, confianza):
        """Tolerancia deliberada: un componente secundario puede cambiar."""
        pc = instalacion_valida["pc"]
        componentes = dict(pc.fingerprint.components)
        componentes["volume_serial"] = "vol-disco-nuevo"
        pc.fingerprint = type(pc.fingerprint)(componentes)
        decision = verifier.authorize(pc.contexto(trust=confianza))
        assert decision.outcome == decisions.ALLOW
        assert "volume_serial" in decision.evidence["componentes_difieren"]

    def test_cambiar_todos_los_secundarios_ya_es_otra_maquina(
        self, instalacion_valida, confianza
    ):
        pc = instalacion_valida["pc"]
        componentes = dict(pc.fingerprint.components)
        componentes["volume_serial"] = "otro-disco"
        componentes["windows_install"] = "otro-windows"
        componentes["computer_name"] = "OTRO-EQUIPO"
        pc.fingerprint = type(pc.fingerprint)(componentes)
        decision = verifier.authorize(pc.contexto(trust=confianza))
        assert decision.outcome == decisions.DENY
        assert decision.reason == decisions.REASON_BINDING_MISMATCH


# ==========================================================================
class TestC_LicenciaModificadaDeniega:
    @pytest.mark.parametrize(
        "campo, valor",
        [
            ("business_name", "Otra Optica"),
            ("branch_id", "PILAR"),
            ("lease_days", 3650),
            ("grace_days", 3650),
            ("secondary_required", 0),
        ],
    )
    def test_cambiar_un_campo_invalida_la_firma(
        self, instalacion_valida, confianza, campo, valor
    ):
        pc = instalacion_valida["pc"]
        sobre = json.loads(pc.paths.license.read_text(encoding="utf-8"))
        sobre["payload"][campo] = valor
        pc.paths.license.write_text(json.dumps(sobre), encoding="utf-8")
        decision = verifier.authorize(pc.contexto(trust=confianza))
        assert decision.outcome == decisions.DENY
        assert decision.reason == decisions.REASON_BAD_SIGNATURE

    def test_cambiar_el_binding_a_la_maquina_del_ladron_no_alcanza(
        self, instalacion_valida, pc_b, confianza
    ):
        """El ataque obvio: reescribir el binding con la huella de la PC nueva."""
        pc_a = instalacion_valida["pc"]
        _clonar(pc_a, pc_b)
        sobre = json.loads(pc_b.paths.license.read_text(encoding="utf-8"))
        sobre["payload"]["binding"] = pc_b.fingerprint.hashed(
            sobre["payload"]["installation_id"]
        )
        pc_b.paths.license.write_text(json.dumps(sobre), encoding="utf-8")
        decision = verifier.authorize(pc_b.contexto(trust=confianza))
        assert decision.outcome == decisions.DENY
        assert decision.reason == decisions.REASON_BAD_SIGNATURE

    def test_un_byte_de_la_firma_alcanza(self, instalacion_valida, confianza):
        pc = instalacion_valida["pc"]
        sobre = json.loads(pc.paths.license.read_text(encoding="utf-8"))
        firma = list(sobre["signature"])
        firma[0] = "A" if firma[0] != "A" else "B"
        sobre["signature"] = "".join(firma)
        pc.paths.license.write_text(json.dumps(sobre), encoding="utf-8")
        decision = verifier.authorize(pc.contexto(trust=confianza))
        assert decision.outcome == decisions.DENY
        assert decision.reason == decisions.REASON_BAD_SIGNATURE

    def test_una_licencia_firmada_por_otro_emisor_no_sirve(
        self, instalacion_valida, confianza
    ):
        """Firmarse la licencia uno mismo no funciona: la clave publica no esta."""
        from modulos.seguridad.issuer import issuer as issuer_module

        pc = instalacion_valida["pc"]
        impostor = issuer_module.generate("emisor falso")
        solicitud = enrollment.EnrollmentRequest.from_document(
            json.loads((pc.paths.root / "solicitud.json").read_text(encoding="utf-8"))
            if (pc.paths.root / "solicitud.json").is_file()
            else instalacion_valida["solicitud"].to_document()
        )
        falsa = emitir_para(impostor, solicitud)
        pc.paths.license.write_text(json.dumps(falsa.to_envelope()), encoding="utf-8")
        decision = verifier.authorize(pc.contexto(trust=confianza))
        assert decision.outcome == decisions.DENY
        assert decision.reason == decisions.REASON_UNKNOWN_ISSUER


# ==========================================================================
class TestD_LicenciaDeOtraInstalacionDeniega:
    def test_una_licencia_valida_pero_ajena_no_sirve(
        self, instalacion_valida, pc_b, emisor, confianza
    ):
        pc_a = instalacion_valida["pc"]
        _identidad_b, solicitud_b = enrolar(pc_b, etiqueta="pc-b")
        licencia_de_b = emitir_para(emisor, solicitud_b, license_id="lic-b")
        pc_a.paths.license.write_text(
            json.dumps(licencia_de_b.to_envelope()), encoding="utf-8"
        )
        decision = verifier.authorize(pc_a.contexto(trust=confianza))
        assert decision.outcome == decisions.DENY
        assert decision.reason == decisions.REASON_INSTALLATION_MISMATCH

    def test_instalar_una_licencia_ajena_se_rechaza_de_entrada(
        self, instalacion_valida, pc_b, emisor, confianza
    ):
        """Se rechaza al instalar, no al arrancar: la buena no se pierde."""
        pc_a = instalacion_valida["pc"]
        _identidad_b, solicitud_b = enrolar(pc_b, etiqueta="pc-b")
        ajena = emitir_para(emisor, solicitud_b, license_id="lic-b")
        antes = pc_a.paths.license.read_bytes()
        with pytest.raises(SecurityError):
            verifier.install_license(pc_a.contexto(trust=confianza), ajena.to_envelope())
        assert pc_a.paths.license.read_bytes() == antes


# ==========================================================================
class TestE_BlobLocalCopiadoNoEntregaElSecreto:
    def test_copiar_el_secreto_sellado_a_otra_pc_no_lo_recupera(
        self, instalacion_valida, pc_b
    ):
        pc_a = instalacion_valida["pc"]
        pc_b.paths.ensure()
        (pc_b.paths.secret).write_bytes(pc_a.paths.secret.read_bytes())
        (pc_b.paths.identity).write_bytes(pc_a.paths.identity.read_bytes())
        with pytest.raises(SealedStoreError):
            enrollment.open_secret(pc_b.paths, pc_b.sealer, pc_a.fingerprint)

    def test_el_secreto_en_claro_nunca_esta_en_disco(self, instalacion_valida):
        pc = instalacion_valida["pc"]
        secreto = enrollment.open_secret(pc.paths, pc.sealer, pc.fingerprint)
        for archivo in pc.paths.root.iterdir():
            if archivo.is_file():
                assert secreto.raw not in archivo.read_bytes(), archivo.name

    def test_el_secreto_no_se_imprime_ni_por_accidente(self, instalacion_valida):
        pc = instalacion_valida["pc"]
        secreto = enrollment.open_secret(pc.paths, pc.sealer, pc.fingerprint)
        assert "oculto" in repr(secreto)
        assert secreto.raw.hex() not in repr(secreto)

    def test_la_entropia_equivocada_tampoco_lo_abre(self, instalacion_valida, pc_b):
        """Mismo sellador, entropia distinta: no abre."""
        pc = instalacion_valida["pc"]
        sellado = pc.paths.secret.read_bytes()
        from modulos.seguridad.canonical import b64u_decode

        with pytest.raises(SealedStoreError):
            pc.sealer.open(b64u_decode(sellado.decode("ascii")), b"entropia-equivocada")


# ==========================================================================
class TestF_BaseRobadaNoRevelaDatosSensibles:
    def _cargar_venta(self, pc):
        """Una venta real, escrita por el repositorio de produccion.

        Se usa el camino de siempre —`CashDay.open` y `add_entry`— para que lo
        que se guarde pase por las mismas validaciones y los mismos INSERT que
        usa la Caja. Cifrar tiene que funcionar sobre el camino real, no sobre
        uno paralelo armado para la prueba.
        """
        from modulos.caja_diaria.domain.models import CashDay, CashEntry
        from modulos.caja_diaria.infrastructure.sqlite_repository import (
            SQLiteCashDayRepository,
        )

        repositorio = SQLiteCashDayRepository(pc.database)
        try:
            dia = CashDay.open(date="2026-03-04", unit="PC", opening_cash=0)
            dia.id = "dia-1"
            dia.add_entry(
                CashEntry(
                    id="venta-1",
                    description="MARIA GONZALEZ",
                    total=250000,
                    cash=250000,
                    customer_document="4.567.890",
                    customer_phone="0981-123456",
                    observations="miopia; control en seis meses",
                    prescription_doctor="DRA. BENITEZ",
                )
            )
            repositorio.save(dia)
        finally:
            repositorio.close()

    def test_los_datos_del_paciente_no_se_leen_con_sqlite_normal(self, instalacion_valida):
        pc = instalacion_valida["pc"]
        runtime.activate(pc.database, instalacion_valida["cifrador"])
        self._cargar_venta(pc)
        runtime.clear()

        # Lo que ve quien se lleva el archivo: SQLite pelado, sin BC.
        conexion = sqlite3.connect(str(pc.database))
        fila = conexion.execute(
            "SELECT description, customer_document, customer_phone, observations,"
            " prescription_doctor FROM cash_entries WHERE id='venta-1'"
        ).fetchone()
        conexion.close()
        for valor in fila:
            assert looks_protected(valor), valor
        crudo = pc.database.read_bytes()
        for secreto in (b"MARIA GONZALEZ", b"0981-123456", b"4.567.890", b"DRA. BENITEZ", b"miopia"):
            assert secreto not in crudo, secreto

    def test_bc_los_sigue_leyendo_igual_que_siempre(self, instalacion_valida):
        from modulos.caja_diaria.infrastructure.sqlite_repository import (
            SQLiteCashDayRepository,
        )

        pc = instalacion_valida["pc"]
        runtime.activate(pc.database, instalacion_valida["cifrador"])
        self._cargar_venta(pc)
        repositorio = SQLiteCashDayRepository(pc.database)
        try:
            dia = repositorio.get("dia-1")
        finally:
            repositorio.close()
        entrada = dia.entries[0]
        assert entrada.description == "MARIA GONZALEZ"
        assert entrada.customer_phone == "0981-123456"
        assert entrada.observations == "miopia; control en seis meses"

    def test_un_respaldo_robado_tampoco_los_revela(self, instalacion_valida, tmp_path):
        from modulos.caja_diaria.infrastructure.sqlite_repository import (
            SQLiteCashDayRepository,
        )

        pc = instalacion_valida["pc"]
        runtime.activate(pc.database, instalacion_valida["cifrador"])
        self._cargar_venta(pc)
        repositorio = SQLiteCashDayRepository(pc.database)
        try:
            respaldo = repositorio.backup_to(tmp_path / "robado.sqlite3")
        finally:
            repositorio.close()
        runtime.clear()
        assert b"MARIA GONZALEZ" not in respaldo.read_bytes()

    def test_la_clave_de_datos_no_esta_en_claro_al_lado_de_la_base(self, instalacion_valida):
        pc = instalacion_valida["pc"]
        clave = instalacion_valida["cifrador"].key
        assert clave not in pc.database.read_bytes()
        for wrap in security_db.active_wraps(pc.database):
            assert clave not in wrap.wrapped_dek

    def test_migrar_datos_ya_cargados_los_protege(self, instalacion_valida):
        pc = instalacion_valida["pc"]
        self._cargar_venta(pc)  # sin cifrador: quedan en claro, como hoy
        antes = data_migration.survey(pc.database)
        assert antes["cash_entries.customer_phone"]["en_claro"] == 1

        data_migration.protect(pc.database, instalacion_valida["cifrador"])
        assert data_migration.plaintext_leftovers(pc.database) == {}

    def test_migrar_dos_veces_no_cifra_dos_veces(self, instalacion_valida):
        pc = instalacion_valida["pc"]
        self._cargar_venta(pc)
        cifrador = instalacion_valida["cifrador"]
        primero = data_migration.protect(pc.database, cifrador)
        segundo = data_migration.protect(pc.database, cifrador)
        assert primero.total > 0
        assert segundo.total == 0
        runtime.activate(pc.database, cifrador)
        from modulos.caja_diaria.infrastructure.sqlite_repository import (
            SQLiteCashDayRepository,
        )

        repositorio = SQLiteCashDayRepository(pc.database)
        try:
            assert repositorio.get("dia-1").entries[0].customer_phone == "0981-123456"
        finally:
            repositorio.close()

    def test_el_disparador_de_stock_vuelve_intacto(self, instalacion_valida):
        """La migracion lo suspende; tiene que quedar exactamente como estaba."""
        pc = instalacion_valida["pc"]
        conexion = sqlite3.connect(str(pc.database))
        antes = conexion.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger'"
            " AND name='sale_items_de_venta_integrada_sin_update'"
        ).fetchone()
        conexion.close()

        data_migration.protect(pc.database, instalacion_valida["cifrador"])

        conexion = sqlite3.connect(str(pc.database))
        despues = conexion.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger'"
            " AND name='sale_items_de_venta_integrada_sin_update'"
        ).fetchone()
        conexion.close()
        assert antes is not None and despues is not None
        assert antes[0] == despues[0]


# ==========================================================================
class TestG_LeaseValidoOfflinePermite:
    def test_sin_internet_y_dentro_del_lease_abre(self, instalacion_valida, confianza):
        pc = instalacion_valida["pc"]
        # No hay nada que contactar: todo el camino es local por diseno.
        for dias in (0, 1, 10, 29):
            decision = verifier.authorize(
                pc.contexto(trust=confianza, ahora=ahora() + timedelta(days=dias))
            )
            assert decision.outcome == decisions.ALLOW, dias

    def test_el_lease_se_persiste_en_la_base_y_en_el_archivo(
        self, instalacion_valida, confianza
    ):
        pc = instalacion_valida["pc"]
        verifier.authorize(pc.contexto(trust=confianza))
        assert pc.paths.lease.is_file()
        secreto = enrollment.open_secret(pc.paths, pc.sealer, pc.fingerprint)
        guardado = security_db.read_state(
            pc.database, security_db.STATE_LEASE, secreto.lease_key()
        )
        assert guardado is not None

    def test_borrar_el_archivo_de_lease_no_lo_resetea(self, instalacion_valida, confianza):
        pc = instalacion_valida["pc"]
        verifier.authorize(pc.contexto(trust=confianza))
        pc.paths.lease.unlink()
        decision = verifier.authorize(
            pc.contexto(trust=confianza, ahora=ahora() + timedelta(days=5))
        )
        # El lease sigue contando desde la primera validacion, no desde ahora.
        assert decision.lease_expires_at <= ahora() + timedelta(days=30, seconds=5)

    def test_atrasar_el_reloj_no_devuelve_tiempo_de_lease(self, instalacion_valida, confianza):
        pc = instalacion_valida["pc"]
        futuro = ahora() + timedelta(days=40)
        verifier.authorize(pc.contexto(trust=confianza, ahora=futuro))
        # Se atrasa el reloj de la maquina para "volver" a estar dentro del lease.
        decision = verifier.authorize(pc.contexto(trust=confianza, ahora=ahora()))
        assert decision.outcome != decisions.ALLOW or decision.reason == decisions.REASON_CLOCK_ROLLBACK
        assert decision.evidence.get("reloj") == decisions.REASON_CLOCK_ROLLBACK


# ==========================================================================
class TestH_LeaseVencidoPoliticaSegura:
    def test_vencido_pero_en_gracia_sigue_abriendo_con_aviso(
        self, instalacion_valida, confianza
    ):
        pc = instalacion_valida["pc"]
        verifier.authorize(pc.contexto(trust=confianza))
        arranque = bootstrap.arrancar(
            pc.contexto(trust=confianza, ahora=ahora() + timedelta(days=35))
        )
        assert arranque.decision.outcome == decisions.ALLOW_GRACE
        assert arranque.allowed
        assert arranque.degraded
        assert "renovar" in arranque.message

    def test_pasada_la_gracia_deja_de_abrir(self, instalacion_valida, confianza):
        pc = instalacion_valida["pc"]
        verifier.authorize(pc.contexto(trust=confianza))
        decision = verifier.authorize(
            pc.contexto(trust=confianza, ahora=ahora() + timedelta(days=60))
        )
        assert decision.outcome == decisions.DENY
        assert decision.reason == decisions.REASON_LEASE_EXPIRED

    def test_un_lease_vencido_no_toca_la_base(self, instalacion_valida, confianza):
        """Denegar es cerrar la puerta, no demoler. Es lo que sostiene el rollback."""
        pc = instalacion_valida["pc"]
        verifier.authorize(pc.contexto(trust=confianza))
        antes = pc.database.stat().st_size
        filas_antes = sqlite3.connect(str(pc.database)).execute(
            "SELECT count(*) FROM security_keyring"
        ).fetchone()[0]
        verifier.authorize(pc.contexto(trust=confianza, ahora=ahora() + timedelta(days=90)))
        assert pc.database.is_file()
        assert pc.database.stat().st_size >= antes
        filas_despues = sqlite3.connect(str(pc.database)).execute(
            "SELECT count(*) FROM security_keyring"
        ).fetchone()[0]
        assert filas_despues == filas_antes

    def test_reponer_la_licencia_renueva_el_lease(self, instalacion_valida, emisor, confianza):
        pc = instalacion_valida["pc"]
        verifier.authorize(pc.contexto(trust=confianza))
        vencido = ahora() + timedelta(days=60)
        assert verifier.authorize(
            pc.contexto(trust=confianza, ahora=vencido)
        ).outcome == decisions.DENY

        nueva = emitir_para(emisor, instalacion_valida["solicitud"], license_id="lic-2")
        verifier.install_license(pc.contexto(trust=confianza), nueva.to_envelope())
        decision = verifier.authorize(pc.contexto(trust=confianza, ahora=vencido))
        assert decision.outcome == decisions.ALLOW

    def test_una_licencia_con_vencimiento_absoluto_vence(
        self, pc_a, emisor, confianza
    ):
        _identidad, solicitud = enrolar(pc_a)
        firmada = emitir_para(emisor, solicitud, valid_days=1)
        verifier.install_license(pc_a.contexto(trust=confianza), firmada.to_envelope())
        assert verifier.authorize(pc_a.contexto(trust=confianza)).outcome == decisions.ALLOW
        decision = verifier.authorize(
            pc_a.contexto(trust=confianza, ahora=ahora() + timedelta(days=3))
        )
        assert decision.outcome == decisions.DENY
        assert decision.reason == decisions.REASON_EXPIRED


# ==========================================================================
class TestI_InstalacionRevocadaDeniega:
    def _revocar(self, emisor, instalacion_id, serial=1):
        from modulos.seguridad.issuer import issuer as issuer_module

        return issuer_module.issue_revocations(
            emisor,
            serial=serial,
            revoked_installations=[instalacion_id],
            reasons={instalacion_id: "equipo dado de baja"},
        )

    def test_una_instalacion_revocada_deja_de_abrir(
        self, instalacion_valida, emisor, confianza
    ):
        pc = instalacion_valida["pc"]
        identificador = instalacion_valida["solicitud"].installation_id
        assert verifier.authorize(pc.contexto(trust=confianza)).outcome == decisions.ALLOW
        verifier.install_revocations(
            pc.contexto(trust=confianza), self._revocar(emisor, identificador).to_envelope()
        )
        decision = verifier.authorize(pc.contexto(trust=confianza))
        assert decision.outcome == decisions.DENY
        assert decision.reason == decisions.REASON_REVOKED
        assert decision.detail == "equipo dado de baja"

    def test_borrar_el_archivo_de_revocacion_no_desrevoca(
        self, instalacion_valida, emisor, confianza
    ):
        pc = instalacion_valida["pc"]
        identificador = instalacion_valida["solicitud"].installation_id
        verifier.install_revocations(
            pc.contexto(trust=confianza), self._revocar(emisor, identificador).to_envelope()
        )
        verifier.authorize(pc.contexto(trust=confianza))
        pc.paths.revocations.unlink()
        decision = verifier.authorize(pc.contexto(trust=confianza))
        assert decision.outcome == decisions.DENY
        assert decision.reason == decisions.REASON_REVOKED

    def test_reponer_una_lista_vieja_no_desrevoca(self, instalacion_valida, emisor, confianza):
        pc = instalacion_valida["pc"]
        identificador = instalacion_valida["solicitud"].installation_id
        from modulos.seguridad.issuer import issuer as issuer_module

        vieja = issuer_module.issue_revocations(emisor, serial=1)
        verifier.install_revocations(pc.contexto(trust=confianza), vieja.to_envelope())
        verifier.install_revocations(
            pc.contexto(trust=confianza),
            self._revocar(emisor, identificador, serial=2).to_envelope(),
        )
        with pytest.raises(SecurityError):
            verifier.install_revocations(pc.contexto(trust=confianza), vieja.to_envelope())

    def test_una_lista_de_revocacion_sin_firmar_no_se_aplica(
        self, instalacion_valida, confianza
    ):
        from modulos.seguridad.issuer import issuer as issuer_module

        pc = instalacion_valida["pc"]
        impostor = issuer_module.generate("emisor falso")
        falsa = issuer_module.issue_revocations(impostor, serial=9, revoked_installations=["x"])
        with pytest.raises(SecurityError):
            verifier.install_revocations(pc.contexto(trust=confianza), falsa.to_envelope())

    def test_una_lista_mas_nueva_puede_deshacer_una_revocacion_equivocada(
        self, instalacion_valida, emisor, confianza
    ):
        """Revocar por error tiene que ser reversible.

        La revocacion se persiste para que borrar el archivo no la deshaga, y
        eso mismo la volveria eterna si nada pudiera levantarla. Lo que la
        levanta es una lista **mas nueva** —serial mayor— firmada por el
        emisor, que es la misma autoridad que la habia impuesto. Sin este
        camino, un error de tipeo del administrador mataba una instalacion sin
        vuelta, y la unica salida habria sido re-enrolar y perder la clave de
        datos.
        """
        from modulos.seguridad.issuer import issuer as issuer_module

        pc = instalacion_valida["pc"]
        identificador = instalacion_valida["solicitud"].installation_id
        verifier.install_revocations(
            pc.contexto(trust=confianza), self._revocar(emisor, identificador).to_envelope()
        )
        assert verifier.authorize(pc.contexto(trust=confianza)).reason == decisions.REASON_REVOKED

        levantada = issuer_module.issue_revocations(emisor, serial=2)
        verifier.install_revocations(pc.contexto(trust=confianza), levantada.to_envelope())
        decision = verifier.authorize(pc.contexto(trust=confianza))
        assert decision.outcome == decisions.ALLOW

    def test_la_revocacion_queda_auditada(self, instalacion_valida, emisor, confianza):
        pc = instalacion_valida["pc"]
        identificador = instalacion_valida["solicitud"].installation_id
        verifier.install_revocations(
            pc.contexto(trust=confianza), self._revocar(emisor, identificador).to_envelope()
        )
        verifier.authorize(pc.contexto(trust=confianza))
        eventos = security_db.read_audit(pc.database)
        assert any(fila["event"] == security_db.EVENT_REVOCATION_INSTALLED for fila in eventos)
        assert any(fila["reason"] == decisions.REASON_REVOKED for fila in eventos)


# ==========================================================================
class TestJ_ArchivosPerdidosOCorruptosFallanSinDestruir:
    def test_sin_licencia_deniega_y_no_borra_nada(self, instalacion_valida, confianza):
        pc = instalacion_valida["pc"]
        tamano = pc.database.stat().st_size
        pc.paths.license.unlink()
        decision = verifier.authorize(pc.contexto(trust=confianza))
        assert decision.reason == decisions.REASON_NO_LICENSE
        assert pc.database.stat().st_size == tamano

    def test_una_licencia_ilegible_deniega_y_no_borra_nada(self, instalacion_valida, confianza):
        pc = instalacion_valida["pc"]
        pc.paths.license.write_text("{esto no es json", encoding="utf-8")
        decision = verifier.authorize(pc.contexto(trust=confianza))
        assert decision.reason == decisions.REASON_LICENSE_UNREADABLE
        assert pc.database.is_file()

    def test_un_secreto_corrupto_deniega_y_no_borra_nada(self, instalacion_valida, confianza):
        pc = instalacion_valida["pc"]
        pc.paths.secret.write_bytes(b"basura")
        decision = verifier.authorize(pc.contexto(trust=confianza))
        assert decision.reason == decisions.REASON_SECRET_UNAVAILABLE
        assert pc.database.is_file()

    def test_un_lease_editado_a_mano_se_descarta_sin_romper(
        self, instalacion_valida, confianza
    ):
        pc = instalacion_valida["pc"]
        verifier.authorize(pc.contexto(trust=confianza))
        sobre = json.loads(pc.paths.lease.read_text(encoding="utf-8"))
        sobre["payload"]["lease_expires_at"] = "2099-01-01T00:00:00+00:00"
        pc.paths.lease.write_text(json.dumps(sobre), encoding="utf-8")
        decision = verifier.authorize(pc.contexto(trust=confianza))
        # No se le cree al lease editado: se arranca uno nuevo, y no hereda 2099.
        assert decision.lease_expires_at < ahora() + timedelta(days=31)

    def test_sin_clave_de_datos_pero_con_datos_cifrados_no_abre_en_claro(
        self, instalacion_valida, confianza
    ):
        """El peor de los fallos posibles: abrir y empezar a guardar en claro."""
        pc = instalacion_valida["pc"]
        data_migration.protect(pc.database, instalacion_valida["cifrador"])
        conexion = sqlite3.connect(str(pc.database))
        conexion.execute("UPDATE security_keyring SET active=0 WHERE wrap_kind='installation'")
        conexion.commit()
        conexion.close()
        arranque = bootstrap.arrancar(pc.contexto(trust=confianza))
        assert not arranque.allowed
        assert arranque.decision.reason == decisions.REASON_SECRET_UNAVAILABLE
        assert runtime.cipher_for(pc.database) is None

    def test_la_bitacora_de_seguridad_no_se_puede_reescribir_ni_borrar(
        self, instalacion_valida, confianza
    ):
        pc = instalacion_valida["pc"]
        verifier.authorize(pc.contexto(trust=confianza))
        conexion = sqlite3.connect(str(pc.database))
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("UPDATE security_audit SET outcome='ALLOW'")
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("DELETE FROM security_audit")
        conexion.close()

    def test_el_llavero_no_se_puede_borrar(self, instalacion_valida):
        pc = instalacion_valida["pc"]
        conexion = sqlite3.connect(str(pc.database))
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("DELETE FROM security_keyring")
        conexion.close()


# ==========================================================================
class TestK_RollbackRestauraElEstadoPrevio:
    def _venta(self, pc):
        TestF_BaseRobadaNoRevelaDatosSensibles()._cargar_venta(pc)

    def test_revertir_devuelve_los_datos_a_texto_plano(self, instalacion_valida):
        pc = instalacion_valida["pc"]
        cifrador = instalacion_valida["cifrador"]
        self._venta(pc)
        antes = sqlite3.connect(str(pc.database)).execute(
            "SELECT description, customer_phone, observations FROM cash_entries WHERE id='venta-1'"
        ).fetchone()

        data_migration.protect(pc.database, cifrador)
        data_migration.rollback(pc.database, cifrador)

        despues = sqlite3.connect(str(pc.database)).execute(
            "SELECT description, customer_phone, observations FROM cash_entries WHERE id='venta-1'"
        ).fetchone()
        assert despues == antes

    def test_despues_de_revertir_bc_funciona_sin_la_capa(self, instalacion_valida):
        from modulos.caja_diaria.infrastructure.sqlite_repository import (
            SQLiteCashDayRepository,
        )

        pc = instalacion_valida["pc"]
        cifrador = instalacion_valida["cifrador"]
        self._venta(pc)
        data_migration.protect(pc.database, cifrador)
        data_migration.rollback(pc.database, cifrador)
        runtime.clear()  # como si la capa no estuviera instalada

        repositorio = SQLiteCashDayRepository(pc.database)
        try:
            assert repositorio.get("dia-1").entries[0].description == "MARIA GONZALEZ"
        finally:
            repositorio.close()

    def test_el_ida_y_vuelta_queda_auditado(self, instalacion_valida):
        pc = instalacion_valida["pc"]
        cifrador = instalacion_valida["cifrador"]
        self._venta(pc)
        data_migration.protect(pc.database, cifrador)
        data_migration.rollback(pc.database, cifrador)
        eventos = {fila["event"] for fila in security_db.read_audit(pc.database)}
        assert security_db.EVENT_DATA_PROTECTED in eventos
        assert security_db.EVENT_DATA_ROLLBACK in eventos

    def test_la_frase_de_recuperacion_abre_la_base_en_otra_pc(
        self, instalacion_valida, pc_b
    ):
        """El camino real de recuperacion: la PC murio, la base sobrevivio."""
        pc_a = instalacion_valida["pc"]
        self._venta(pc_a)
        data_migration.protect(pc_a.database, instalacion_valida["cifrador"])
        pc_b.database.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pc_a.database, pc_b.database)

        _identidad, _solicitud = enrolar(pc_b, etiqueta="pc-b nueva")
        secreto_b = enrollment.open_secret(pc_b.paths, pc_b.sealer, pc_b.fingerprint)
        clave = keyring.open_with_recovery(pc_b.database, instalacion_valida["frase"])
        keyring.rewrap_for_installation(pc_b.database, clave, secreto_b)

        recuperada = keyring.open_with_installation(pc_b.database, secreto_b)
        cifrador_b = FieldCipher(key=recuperada.raw, dek_id=recuperada.dek_id)
        runtime.activate(pc_b.database, cifrador_b)
        from modulos.caja_diaria.infrastructure.sqlite_repository import (
            SQLiteCashDayRepository,
        )

        repositorio = SQLiteCashDayRepository(pc_b.database)
        try:
            assert repositorio.get("dia-1").entries[0].customer_phone == "0981-123456"
        finally:
            repositorio.close()

    def test_una_frase_equivocada_no_abre(self, instalacion_valida):
        pc = instalacion_valida["pc"]
        with pytest.raises(SecurityError):
            keyring.open_with_recovery(pc.database, "AAAAA-BBBBB-CCCCC-DDDDD")

    def test_la_frase_tolera_como_la_escribio_una_persona(self, instalacion_valida):
        pc = instalacion_valida["pc"]
        frase = instalacion_valida["frase"]
        maltratada = f"  {frase.lower().replace('-', ' ')}  "
        clave = keyring.open_with_recovery(pc.database, maltratada)
        assert clave.raw == instalacion_valida["cifrador"].key
