"""El codec de columnas y el mapeo de parametros, en detalle.

Las pruebas de aceptacion miran el resultado; estas miran las decisiones que lo
producen, sobre todo las que son faciles de romper sin darse cuenta.
"""

from __future__ import annotations

import sqlite3

import pytest

from modulos.seguridad.application.field_protection import (
    PREFIX,
    FieldCipher,
    StatementNotUnderstood,
    is_protected,
    looks_protected,
    plan_parameters,
)
from modulos.seguridad.crypto.primitives import random_bytes
from modulos.seguridad.errors import DataProtectionError
from modulos.seguridad.infrastructure.protected_connection import open_protected


@pytest.fixture
def cifrador() -> FieldCipher:
    return FieldCipher(key=random_bytes(32), dek_id="dek-de-prueba")


# ==========================================================================
class TestElCodec:
    def test_ida_y_vuelta(self, cifrador):
        protegido = cifrador.protect("orders", "customer_name", "MARIA")
        assert looks_protected(protegido)
        assert cifrador.reveal("orders", "customer_name", protegido) == "MARIA"

    def test_la_cadena_vacia_no_se_cifra(self, cifrador):
        """Regla del negocio, no optimizacion.

        Varias tablas tienen `CHECK(length(trim(columna)) > 0)` y
        `CHECK(envelope <> '' OR customer_name <> '')`. Cifrar `''` daria un
        criptograma no vacio y esas reglas pasarian a aceptar filas que hoy
        rechazan, que es cambiar el negocio por un detalle de implementacion.
        """
        assert cifrador.protect("orders", "customer_name", "") == ""
        assert cifrador.protect("orders", "customer_name", None) is None

    def test_no_se_cifra_dos_veces(self, cifrador):
        una = cifrador.protect("orders", "customer_name", "MARIA")
        assert cifrador.protect("orders", "customer_name", una) == una

    def test_dos_cifrados_del_mismo_valor_son_distintos(self, cifrador):
        """Si fueran iguales, contar repeticiones diria quien viene mas seguido."""
        assert cifrador.protect("orders", "customer_name", "MARIA") != cifrador.protect(
            "orders", "customer_name", "MARIA"
        )

    def test_mover_un_valor_a_otra_columna_lo_vuelve_ilegible(self, cifrador):
        protegido = cifrador.protect("orders", "customer_name", "MARIA")
        with pytest.raises(DataProtectionError):
            cifrador.reveal("orders", "customer_phone", protegido)

    def test_mover_un_valor_a_otra_base_lo_vuelve_ilegible(self, cifrador):
        otra = FieldCipher(key=cifrador.key, dek_id="otra-dek")
        protegido = cifrador.protect("orders", "customer_name", "MARIA")
        with pytest.raises(DataProtectionError):
            otra.reveal("orders", "customer_name", protegido)

    def test_con_otra_clave_no_abre(self, cifrador):
        ajena = FieldCipher(key=random_bytes(32), dek_id=cifrador.dek_id)
        protegido = cifrador.protect("orders", "customer_name", "MARIA")
        with pytest.raises(DataProtectionError):
            ajena.reveal("orders", "customer_name", protegido)

    def test_un_criptograma_alterado_no_abre(self, cifrador):
        protegido = cifrador.protect("orders", "customer_name", "MARIA")
        roto = PREFIX + protegido[len(PREFIX) :][:-2] + "AA"
        with pytest.raises(DataProtectionError):
            cifrador.reveal("orders", "customer_name", roto)

    def test_una_columna_protegida_que_recibe_un_numero_rompe(self, cifrador):
        """Preferible romper que guardar el numero en claro por descuido."""
        with pytest.raises(DataProtectionError):
            cifrador.protect("orders", "customer_name", 42)

    def test_la_pista_de_columna_es_solo_una_optimizacion(self, cifrador):
        """El resultado no puede depender de que la pista sea correcta.

        La lectura pasa como pista el nombre de columna del resultado, que con
        un alias no es el real. Si el descifrado dependiera de eso, FactuFacil
        —que llama `cliente` a `description`— habria dejado de funcionar.
        """
        protegido = cifrador.protect("cash_entries", "description", "MARIA")
        assert cifrador.reveal_unknown_column(protegido) == "MARIA"
        assert cifrador.reveal_unknown_column(protegido, hint="description") == "MARIA"
        assert cifrador.reveal_unknown_column(protegido, hint="cliente") == "MARIA"
        assert cifrador.reveal_unknown_column(protegido, hint="customer_phone") == "MARIA"

    def test_descifrar_sin_saber_la_columna(self, cifrador):
        """Es lo que hace la lectura: el `row_factory` no sabe de que columna viene."""
        protegido = cifrador.protect("cash_entries", "observations", "miopia")
        assert cifrador.reveal_unknown_column(protegido) == "miopia"

    def test_los_acentos_sobreviven(self, cifrador):
        for valor in ("MARÍA GONZÁLEZ", "observación clínica", "Ñandutí"):
            protegido = cifrador.protect("orders", "customer_name", valor)
            assert cifrador.reveal("orders", "customer_name", protegido) == valor


# ==========================================================================
class TestElRegistro:
    def test_las_columnas_del_paciente_estan_dentro(self):
        assert is_protected("cash_entries", "customer_phone")
        assert is_protected("cash_entries", "description")
        assert is_protected("orders", "customer_document")
        assert is_protected("service_jobs", "observations")
        assert is_protected("tracked_works", "customer_name")

    def test_la_bitacora_de_revisiones_esta_dentro(self):
        """Guarda la entrada entera como JSON: sin esto, protegerla seria teatro."""
        assert is_protected("cash_entry_revisions", "snapshot_json")

    def test_el_dinero_y_los_estados_quedan_afuera(self):
        """Cifrar importes romperia totales, filtros y reportes sin proteger a nadie."""
        assert not is_protected("cash_entries", "total")
        assert not is_protected("cash_entries", "cash")
        assert not is_protected("cash_days", "closing_total")
        assert not is_protected("service_jobs", "status")

    def test_suppliers_queda_afuera_a_proposito(self):
        """Decision declarada: hay un UNIQUE sobre `document` (ver ADR-0005)."""
        assert not is_protected("suppliers", "document")


# ==========================================================================
class TestElMapeoDeParametros:
    def test_un_insert_simple(self):
        plan = plan_parameters(
            "INSERT INTO orders(id, customer_name, branch) VALUES (?,?,?)"
        )
        assert plan == [None, "customer_name", None]

    def test_un_insert_or_replace(self):
        plan = plan_parameters(
            "INSERT OR REPLACE INTO orders(id, customer_phone) VALUES (?,?)"
        )
        assert plan == [None, "customer_phone"]

    def test_un_update_simple(self):
        plan = plan_parameters(
            "UPDATE orders SET customer_name = ?, status = ? WHERE id = ?"
        )
        assert plan == ["customer_name", None, None]

    def test_una_tabla_sin_columnas_protegidas_no_cuesta_nada(self):
        assert plan_parameters("INSERT INTO cash_days(id, unit) VALUES (?,?)") == []
        assert plan_parameters("SELECT * FROM cash_days WHERE id = ?") == []

    def test_un_insert_desde_select_no_toca_nada(self):
        """Los valores ya vienen protegidos de la misma base."""
        assert plan_parameters(
            "INSERT INTO orders(id, customer_name) SELECT id, customer_name FROM orders"
        ) == []

    def test_comparar_una_columna_protegida_se_rechaza(self):
        with pytest.raises(StatementNotUnderstood):
            plan_parameters("UPDATE orders SET status = ? WHERE customer_phone = ?")

    def test_calcular_una_columna_protegida_en_sql_se_rechaza(self):
        with pytest.raises(StatementNotUnderstood):
            plan_parameters("UPDATE orders SET customer_name = upper(customer_name)")

    def test_un_insert_con_expresion_en_columna_protegida_se_rechaza(self):
        with pytest.raises(StatementNotUnderstood):
            plan_parameters(
                "INSERT INTO orders(id, customer_name) VALUES (?, coalesce(?,''))"
            )


# ==========================================================================
class TestLaConexionProtegida:
    def _base(self, tmp_path, cipher):
        ruta = tmp_path / "prueba.sqlite3"
        conexion = open_protected(str(ruta), cipher)
        conexion.row_factory = sqlite3.Row
        conexion.execute(
            "CREATE TABLE IF NOT EXISTS orders("
            " id TEXT PRIMARY KEY, customer_name TEXT, branch TEXT)"
        )
        return conexion

    def test_escribe_cifrado_y_lee_en_claro(self, tmp_path, cifrador):
        conexion = self._base(tmp_path, cifrador)
        conexion.execute(
            "INSERT INTO orders(id, customer_name, branch) VALUES (?,?,?)",
            ("1", "MARIA", "ASUNCION"),
        )
        conexion.commit()
        fila = conexion.execute("SELECT * FROM orders WHERE id='1'").fetchone()
        assert fila["customer_name"] == "MARIA"
        conexion.close()

        crudo = sqlite3.connect(str(tmp_path / "prueba.sqlite3"))
        guardado = crudo.execute("SELECT customer_name FROM orders").fetchone()[0]
        crudo.close()
        assert looks_protected(guardado)

    def test_sin_cifrador_se_comporta_como_sqlite3(self, tmp_path):
        conexion = self._base(tmp_path, None)
        conexion.execute(
            "INSERT INTO orders(id, customer_name, branch) VALUES (?,?,?)",
            ("1", "MARIA", "ASUNCION"),
        )
        conexion.commit()
        assert conexion.execute("SELECT customer_name FROM orders").fetchone()[0] == "MARIA"
        conexion.close()
        crudo = sqlite3.connect(str(tmp_path / "prueba.sqlite3"))
        assert crudo.execute("SELECT customer_name FROM orders").fetchone()[0] == "MARIA"
        crudo.close()

    def test_executemany_tambien_cifra(self, tmp_path, cifrador):
        conexion = self._base(tmp_path, cifrador)
        conexion.executemany(
            "INSERT INTO orders(id, customer_name, branch) VALUES (?,?,?)",
            [("1", "MARIA", "A"), ("2", "JOSE", "B")],
        )
        conexion.commit()
        nombres = {fila["customer_name"] for fila in conexion.execute("SELECT * FROM orders")}
        assert nombres == {"MARIA", "JOSE"}
        conexion.close()

    def test_el_row_factory_declarado_sigue_siendo_el_que_se_asigno(self, tmp_path, cifrador):
        conexion = self._base(tmp_path, cifrador)
        assert conexion.row_factory is sqlite3.Row
        conexion.close()

    def test_funciona_sin_row_factory(self, tmp_path, cifrador):
        ruta = tmp_path / "sin_factory.sqlite3"
        conexion = open_protected(str(ruta), cifrador)
        conexion.execute("CREATE TABLE orders(id TEXT PRIMARY KEY, customer_name TEXT)")
        conexion.execute("INSERT INTO orders(id, customer_name) VALUES (?,?)", ("1", "MARIA"))
        conexion.commit()
        assert conexion.execute("SELECT customer_name FROM orders").fetchone()[0] == "MARIA"
        conexion.close()

    def test_una_columna_con_alias_tambien_se_descifra(self, tmp_path, cifrador):
        conexion = self._base(tmp_path, cifrador)
        conexion.execute("INSERT INTO orders(id, customer_name) VALUES (?,?)", ("1", "MARIA"))
        conexion.commit()
        fila = conexion.execute(
            "SELECT customer_name AS cliente FROM orders WHERE id='1'"
        ).fetchone()
        assert fila["cliente"] == "MARIA"
        conexion.close()

    def test_un_valor_de_otra_base_no_se_lee_en_silencio(self, tmp_path, cifrador):
        """Leer criptograma ajeno tiene que romper, no devolver el criptograma."""
        conexion = self._base(tmp_path, cifrador)
        ajeno = FieldCipher(key=random_bytes(32), dek_id="ajena").protect(
            "orders", "customer_name", "MARIA"
        )
        conexion.execute("INSERT INTO orders(id, customer_name) VALUES (?,?)", ("1", ajeno))
        conexion.commit()
        with pytest.raises(DataProtectionError):
            conexion.execute("SELECT customer_name FROM orders").fetchone()
        conexion.close()
