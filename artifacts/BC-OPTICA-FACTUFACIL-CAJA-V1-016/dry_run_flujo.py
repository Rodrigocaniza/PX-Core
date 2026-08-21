# -*- coding: utf-8 -*-
"""El flujo entero de FactuFacil sobre una base local ya migrada.

No es produccion: es una copia con la forma del dia de la Optica. Lo que se
comprueba es que el circuito completo funcione de punta a punta y que la caja
del dia salga igual que entro.
"""
import sqlite3
import sys
from pathlib import Path

BASE = Path(sys.argv[1])
RAIZ = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(RAIZ))

from modulos.caja_diaria.application.factufacil import (  # noqa: E402
    CARGADA, PARA_CARGAR, FactuFacilService,
)
from modulos.caja_diaria.infrastructure.sqlite_repository import (  # noqa: E402
    SQLiteCashDayRepository,
)

salida = []


def reg(t=""):
    print(t, flush=True)
    salida.append(t)


def ok(cond, texto):
    reg(f"  {'OK  ' if cond else 'FALLA'} {texto}")
    return bool(cond)


fallas = []


def chk(cond, texto):
    if not ok(cond, texto):
        fallas.append(texto)


def caja(base):
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        return c.execute(
            "SELECT COUNT(*), COALESCE(SUM(total),0), COALESCE(SUM(cash),0),"
            " COALESCE(SUM(revision),0) FROM cash_entries WHERE status='ACTIVE'"
        ).fetchone()
    finally:
        c.close()


reg("DRY-RUN FUNCIONAL -- FactuFacil en BC Caja")
reg(f"base: {BASE}")
reg("ADVERTENCIA: copia local. NO es la base productiva de la Optica.")
reg()

antes_caja = caja(BASE)
repo = SQLiteCashDayRepository(BASE)
ff = FactuFacilService(repo)
try:
    reg("== 1. lo que aparece para cargar ==")
    pendientes = ff.listar(estado=PARA_CARGAR)
    for f in pendientes:
        reg(f"  {f.fecha} | {f.sucursal:9s} | sobre {f.sobre:5s} | {f.cliente:18s}"
            f" | {f.vendedora:6s} | {f.total:>9,}".replace(",", "."))
    chk(len(pendientes) == 4, f"4 ventas para cargar (hay {len(pendientes)})")
    reg("      (5 entradas activas menos el gasto de nafta; la anulada ya no cuenta)")
    chk(all(f.estado == PARA_CARGAR for f in pendientes), "todas en PARA CARGAR")
    chk(not any(f.cliente == "Nafta" for f in pendientes), "el gasto no esta")
    chk(not any(f.cliente == "Carlos Benitez" for f in pendientes), "la anulada no esta")
    reg()

    reg("== 2. copiar los datos de una ==")
    elegida = [f for f in pendientes if f.sobre == "1001"][0]
    texto = ff.texto_para_copiar(elegida.cash_entry_id)
    for linea in texto.splitlines():
        reg(f"    {linea}")
    chk(ff.obtener(elegida.cash_entry_id) == elegida, "copiar no cambio la fila")
    chk("adición 2.00" in texto, "la receta va completa")
    reg()

    reg("== 3. marcarla como cargada ==")
    chk(ff.marcar_cargada(elegida.cash_entry_id, actor="rosa") is True, "se marco")
    chk(ff.marcar_cargada(elegida.cash_entry_id, actor="ana") is False,
        "marcarla de nuevo no hace nada")
    fila = ff.obtener(elegida.cash_entry_id)
    chk(fila.estado == CARGADA, f"quedo {fila.etiqueta_estado}")
    chk(fila.cargada_por == "rosa", f"la cargo {fila.cargada_por}")
    chk(bool(fila.cargada_el), f"a las {fila.cargada_el}")
    chk(len(ff.historial(elegida.cash_entry_id)) == 1, "una sola linea de historia")
    reg()

    reg("== 4. cambia de lista ==")
    chk(len(ff.listar(estado=PARA_CARGAR)) == 3, "quedan 3 para cargar")
    chk([f.sobre for f in ff.listar(estado=CARGADA)] == ["1001"], "1001 esta en cargadas")
    chk(ff.conteos() == {PARA_CARGAR: 3, CARGADA: 1}, f"chips: {ff.conteos()}")
    reg()

    reg("== 5. filtros ==")
    chk(len(ff.listar(sucursal="PILAR")) == 1, "por sucursal PILAR: 1")
    chk(len(ff.listar(sucursal="ASUNCION")) == 3, "por sucursal ASUNCION: 3")
    chk(len(ff.listar(desde="2026-08-19")) == 1, "desde el 19: 1")
    chk([f.cliente for f in ff.listar(sobre="1003")] == ["Ana Duarte"], "por sobre 1003")
    chk(len(ff.listar(vendedora="ana")) == 2, "por vendedora ana: 2")
    chk(len(ff.listar(cliente="Ayala")) == 1, "por cliente Ayala: 1")
    reg()

    reg("== 6. revertir ==")
    try:
        ff.revertir(elegida.cash_entry_id, actor="sol", motivo="")
        chk(False, "revertir sin motivo tendria que fallar")
    except Exception as error:
        chk("motivo" in str(error), f"sin motivo no se revierte: {error}")
    ff.revertir(elegida.cash_entry_id, actor="sol", motivo="se cargo el sobre equivocado")
    vuelta = ff.obtener(elegida.cash_entry_id)
    chk(vuelta.estado == PARA_CARGAR, "volvio a PARA CARGAR")
    historia = ff.historial(elegida.cash_entry_id)
    chk(len(historia) == 2, "la historia tiene las dos lineas")
    chk(historia[0]["actor"] == "rosa", "sigue diciendo que la cargo rosa")
    chk(historia[1]["reason"] == "se cargo el sobre equivocado", "y por que volvio")
    reg()

    reg("== 7. persistencia: se cierra y se vuelve a abrir ==")
    ff.marcar_cargada(elegida.cash_entry_id, actor="rosa")
finally:
    repo.close()

otro = SQLiteCashDayRepository(BASE)
try:
    ff2 = FactuFacilService(otro)
    fila = ff2.obtener(elegida.cash_entry_id)
    chk(fila.estado == CARGADA and fila.cargada_por == "rosa",
        "despues de reiniciar sigue cargada por rosa")
    chk(len(ff2.historial(elegida.cash_entry_id)) == 3, "y la historia entera esta")
finally:
    otro.close()
reg()

reg("== 8. la caja del dia, intacta ==")
despues_caja = caja(BASE)
chk(antes_caja == despues_caja,
    f"entradas/total/efectivo/revisiones: {antes_caja} -> {despues_caja}")
c = sqlite3.connect(f"file:{BASE}?mode=ro", uri=True)
try:
    chk(c.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "integrity_check ok")
    chk(len(c.execute("PRAGMA foreign_key_check").fetchall()) == 0, "FK 0")
finally:
    c.close()
reg()

reg("RESULTADO: " + ("PASS" if not fallas else f"FALLAS {fallas}"))
if len(sys.argv) > 3:
    Path(sys.argv[3]).write_text("\n".join(salida) + "\n", encoding="utf-8")
raise SystemExit(1 if fallas else 0)
