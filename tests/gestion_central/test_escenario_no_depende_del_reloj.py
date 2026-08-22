"""El escenario del piloto sintético tiene que ser el mismo a cualquier hora.

`GESTION-CENTRAL-NO-DETERMINISTA` decía que las pruebas de UI dependen de
`bootstrap_synthetic_pilot()`. Lo que faltaba era el por qué: ese bootstrap
sembraba `source_updated_at=utc_now()`, y `refresh_alerts` levanta `LATE_OPEN`
cuando la caja sigue abierta y **la hora de ese timestamp** es 22 o más. Corrida
la suite entre las 22:00 y las 23:59 UTC —las 18:00 y las 20:00 en Paraguay, una
hora perfectamente normal para correr pruebas— aparecían cuatro alertas que a
las 21:00 no existen, y dos pruebas de UI se caían sin que nada hubiera cambiado.

Acá hay dos cosas distintas y conviene no mezclarlas:

1. Que la regla `LATE_OPEN` dependa de la hora es **lo que la regla hace**. No
   tenía ni una prueba, así que nadie la había mirado nunca: la primera de
   abajo la deja escrita, incluida la pregunta de en qué huso lee esa hora, que
   está anotada como finding y no se resolvió acá.
2. Que las **pruebas** dependan de la hora del reloj de pared es un defecto. La
   segunda lo fija: el escenario que arman los fixtures de UI es uno solo.
"""

from datetime import datetime, timezone

import modulos.gestion_central.service as modulo
from tests.gestion_central.conftest import INSTANTE
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import CentralManagementService


def sembrado(tmp_path, cuando):
    servicio = CentralManagementService(CentralRepository(tmp_path / f"c{cuando.hour}.sqlite3"))
    servicio.bootstrap_synthetic_pilot(source_updated_at=cuando)
    return servicio


def test_late_open_se_levanta_a_las_22_y_no_antes(tmp_path):
    """La regla que nadie había probado, escrita tal como se comporta hoy.

    Las cuatro cajas del piloto quedan OPEN, así que la única variable es la
    hora. Que el corte sea a las 22 **de la hora que traiga el timestamp** es
    justamente lo que quedó anotado como `LATE-OPEN-LEE-LA-HORA-SIN-HUSO`: si el
    snapshot viene en UTC, en Paraguay salta a las 19:00. Esta prueba no arregla
    eso —es decisión de negocio— pero deja de ser invisible.
    """
    con_alerta = {hora for hora in range(24)
                  if any(a.kind == "LATE_OPEN" for a in
                         sembrado(tmp_path, INSTANTE.replace(hour=hora)).repository.alerts())}
    assert con_alerta == {22, 23}


def test_el_escenario_de_los_fixtures_de_ui_es_uno_solo(tmp_path):
    """Sembrado en el instante fijo, el escenario no mira el reloj de pared.

    Antes esto no se podía ni preguntar: el bootstrap tomaba `utc_now()` por
    dentro y no había forma de fijarlo desde afuera sin parchear el módulo.
    """
    kinds = sorted(a.kind for a in sembrado(tmp_path, INSTANTE).repository.alerts())
    assert kinds == []


def test_la_hora_por_defecto_sigue_siendo_el_reloj(tmp_path):
    """La costura no cambia el piloto: sin argumento, sigue usando `utc_now()`.

    Se compara contra el `utc_now` del propio módulo y no contra
    `datetime.now()`: si alguien fija el reloj para probar otra cosa, esta
    prueba tiene que seguir preguntando lo mismo —«¿usó el reloj del módulo?»—
    y no romperse por estar mirando un reloj distinto del que se fijó.
    """
    servicio = CentralManagementService(CentralRepository(tmp_path / "defecto.sqlite3"))
    servicio.bootstrap_synthetic_pilot()
    with servicio.repository.connection() as con:
        sembrados = [f[0] for f in con.execute("SELECT source_updated_at FROM cash_snapshots")]
    assert sembrados, "el bootstrap tiene que haber sembrado algo"
    reloj_del_modulo = modulo.utc_now()
    for marca in sembrados:
        assert abs((reloj_del_modulo - datetime.fromisoformat(marca)).total_seconds()) < 300
