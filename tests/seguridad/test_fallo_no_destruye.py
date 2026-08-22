"""Que pasa si la instalacion se corta por la mitad.

La mision pide poder afirmar —no suponer— que un fallo durante el enrolamiento
o durante la proteccion de datos **no destruye la base**. Las pruebas J cubren
los archivos perdidos o corruptos *antes* de arrancar; estas cubren el momento
exacto en que la Optica esta mirando: la herramienta ya empezo a escribir y algo
revienta.

Se inyecta el fallo a proposito. Un control que nunca vio fallar el camino que
dice proteger no es un control.
"""

from __future__ import annotations

import sqlite3

import pytest

from modulos.seguridad.application import data_migration, enrollment
from modulos.seguridad.application.field_protection import FieldCipher, looks_protected
from modulos.seguridad.errors import AlreadyEnrolledError, SealedStoreError

from .conftest import enrolar


class CifradorQueRevienta:
    """Un cifrador real que falla a la N-esima llamada, y no antes.

    Delega en el `FieldCipher` de produccion para que lo que se escriba antes
    del fallo sea criptograma de verdad: si la transaccion no volviera atras,
    la base quedaria mitad cifrada y la prueba lo veria.
    """

    def __init__(self, real: FieldCipher, fallar_en: int):
        self._real = real
        self._fallar_en = fallar_en
        self.llamadas = 0

    @property
    def dek_id(self) -> str:
        return self._real.dek_id

    def protect(self, table, column, value):
        self.llamadas += 1
        if self.llamadas >= self._fallar_en:
            raise RuntimeError("se corto la luz en el medio")
        return self._real.protect(table, column, value)

    def reveal(self, table, column, value):
        self.llamadas += 1
        if self.llamadas >= self._fallar_en:
            raise RuntimeError("se corto la luz en el medio")
        return self._real.reveal(table, column, value)


def _cargar_venta(pc, sufijo: str = "1") -> None:
    """Una venta por el camino de produccion, igual que en las pruebas F."""
    from modulos.caja_diaria.domain.models import CashDay, CashEntry
    from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

    repositorio = SQLiteCashDayRepository(pc.database)
    try:
        dia = CashDay.open(date="2026-03-04", unit="PC", opening_cash=0)
        dia.id = f"dia-{sufijo}"
        dia.add_entry(
            CashEntry(
                id=f"venta-{sufijo}",
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


def _valores(pc) -> list[list]:
    conexion = sqlite3.connect(str(pc.database))
    try:
        filas = conexion.execute(
            "SELECT customer_document, customer_phone, observations, prescription_doctor,"
            " source_reference, description FROM cash_entries ORDER BY id"
        ).fetchall()
    finally:
        conexion.close()
    return [list(f) for f in filas]


def _disparador(pc):
    conexion = sqlite3.connect(str(pc.database))
    try:
        fila = conexion.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger'"
            " AND name='sale_items_de_venta_integrada_sin_update'"
        ).fetchone()
    finally:
        conexion.close()
    return fila[0] if fila else None


# ==========================================================================
class TestUnFalloAlProtegerNoDestruyeLaBase:
    def test_si_revienta_a_la_mitad_no_queda_nada_cifrado(self, instalacion_valida):
        """Ni un valor a medio camino: o esta todo en claro, o esta todo cifrado."""
        pc = instalacion_valida["pc"]
        _cargar_venta(pc)
        antes = _valores(pc)

        cifrador = CifradorQueRevienta(instalacion_valida["cifrador"], fallar_en=3)
        with pytest.raises(RuntimeError):
            data_migration.protect(pc.database, cifrador)

        assert cifrador.llamadas >= 3, "el fallo tiene que haber ocurrido despues de cifrar algo"
        assert _valores(pc) == antes, "la base no volvio al estado exacto que tenia"
        for fila in _valores(pc):
            for valor in fila:
                if valor:
                    assert not looks_protected(valor)

    def test_el_disparador_de_stock_vuelve_aunque_el_cifrado_falle(self, instalacion_valida):
        """Se suspende para cifrar; si el cifrado revienta tiene que volver igual."""
        pc = instalacion_valida["pc"]
        _cargar_venta(pc)
        antes = _disparador(pc)
        assert antes is not None

        with pytest.raises(RuntimeError):
            data_migration.protect(
                pc.database, CifradorQueRevienta(instalacion_valida["cifrador"], fallar_en=2)
            )

        assert _disparador(pc) == antes

    def test_despues_del_fallo_bc_sigue_abriendo_y_leyendo(self, instalacion_valida):
        """Lo que la Optica ve al dia siguiente: la Caja funciona como ayer."""
        from modulos.caja_diaria.infrastructure.sqlite_repository import (
            SQLiteCashDayRepository,
        )

        pc = instalacion_valida["pc"]
        _cargar_venta(pc)
        with pytest.raises(RuntimeError):
            data_migration.protect(
                pc.database, CifradorQueRevienta(instalacion_valida["cifrador"], fallar_en=3)
            )

        repositorio = SQLiteCashDayRepository(pc.database)
        try:
            entrada = repositorio.get("dia-1").entries[0]
        finally:
            repositorio.close()
        assert entrada.customer_phone == "0981-123456"
        assert entrada.description == "MARIA GONZALEZ"

    def test_reintentar_despues_del_fallo_termina_el_trabajo(self, instalacion_valida):
        """El fallo no deja la base en un estado del que no se pueda salir."""
        pc = instalacion_valida["pc"]
        _cargar_venta(pc)
        with pytest.raises(RuntimeError):
            data_migration.protect(
                pc.database, CifradorQueRevienta(instalacion_valida["cifrador"], fallar_en=3)
            )

        data_migration.protect(pc.database, instalacion_valida["cifrador"])
        assert data_migration.plaintext_leftovers(pc.database) == {}


# ==========================================================================
class TestUnFalloAlRevertirTampocoDestruye:
    def test_si_revienta_al_revertir_los_datos_siguen_cifrados_y_legibles(
        self, instalacion_valida
    ):
        pc = instalacion_valida["pc"]
        cifrador = instalacion_valida["cifrador"]
        _cargar_venta(pc)
        data_migration.protect(pc.database, cifrador)
        cifrado = _valores(pc)

        with pytest.raises(RuntimeError):
            data_migration.rollback(pc.database, CifradorQueRevienta(cifrador, fallar_en=3))

        assert _valores(pc) == cifrado
        # y el camino de vuelta sigue existiendo
        data_migration.rollback(pc.database, cifrador)
        conexion = sqlite3.connect(str(pc.database))
        try:
            telefono = conexion.execute(
                "SELECT customer_phone FROM cash_entries WHERE id='venta-1'"
            ).fetchone()[0]
        finally:
            conexion.close()
        assert telefono == "0981-123456"


# ==========================================================================
class SelladorQueNoDevuelveLoMismo:
    """Sella y abre otra cosa. Es el DPAPI de una PC que empezo a fallar."""

    name = "sellador-averiado"

    def seal(self, payload: bytes, entropy: bytes) -> bytes:
        return b"sellado::" + payload

    def open(self, sealed: bytes, entropy: bytes) -> bytes:
        return b"cualquier otra cosa"


class TestUnFalloAlEnrolarNoDestruyeNada:
    def test_un_sellado_que_no_reabre_aborta_antes_de_escribir(self, pc_a):
        """Una instalacion muerta se descubre ahora, no con la base ya cifrada."""
        _cargar_venta(pc_a)
        base_antes = pc_a.database.read_bytes()

        with pytest.raises(SealedStoreError):
            enrollment.enroll(
                pc_a.paths, SelladorQueNoDevuelveLoMismo(), pc_a.fingerprint, label="rota"
            )

        assert not pc_a.paths.secret.exists(), "quedo un secreto que no se puede abrir"
        assert not pc_a.paths.identity.exists()
        assert not enrollment.is_enrolled(pc_a.paths)
        assert pc_a.database.read_bytes() == base_antes, "el enrolamiento toco la base"

    def test_enrolar_dos_veces_no_pisa_la_identidad_ni_la_base(self, pc_a):
        """Re-enrolar invalida la clave de datos: no puede pasar por accidente."""
        _cargar_venta(pc_a)
        enrolar(pc_a, etiqueta="la buena")
        secreto_antes = pc_a.paths.secret.read_bytes()
        identidad_antes = pc_a.paths.identity.read_bytes()
        base_antes = pc_a.database.read_bytes()

        with pytest.raises(AlreadyEnrolledError):
            enrolar(pc_a, etiqueta="la de encima")

        assert pc_a.paths.secret.read_bytes() == secreto_antes
        assert pc_a.paths.identity.read_bytes() == identidad_antes
        assert pc_a.database.read_bytes() == base_antes

    def test_enrolar_no_abre_la_base_en_ningun_momento(self, pc_a):
        """El paso de enrolar es reversible porque no toca datos."""
        _cargar_venta(pc_a)
        antes = pc_a.database.read_bytes()
        enrolar(pc_a, etiqueta="Optica - Caja 1")
        assert pc_a.database.read_bytes() == antes
