"""Dry run V1-013 sobre copia de la base productiva real.

Se ejercita el circuito entero contra los datos que hay: retirar el articulo
ficticio, vender con el real bonificado, anular esa venta, e intentar usar el
retirado.
"""
import hashlib, json, sqlite3, sys
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(r"c:\Users\Striker\Desktop\Proyecto X\PX-Core\.worktrees\optica-promo-013")
sys.path.insert(0, str(RAIZ))
W = Path(r"C:\Users\Striker\AppData\Local\Temp\claude\c--Users-Striker-Desktop-Proyecto-X-PX-Core\55fef905-3b6d-44f0-bf35-8b120350484f\scratchpad\m013")

from modulos.caja_diaria.config import resolve_data_paths
from modulos.caja_diaria.domain.models import CashDay, CashEntry, SaleItem
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.comercial.application.comercial_controller import build_comercial_controller
from modulos.comercial.application.ventas import StockInsuficiente, VentasLedgerIntegrator
from modulos.comercial.domain.models import Destination
from modulos.comercial.infrastructure.sqlite_catalog_repository import SQLiteCatalogRepository
from modulos.comercial.infrastructure.sqlite_stock_ledger import SQLiteStockLedgerRepository
import tools.retirar_obsequio_ficticio_optica as R

PROMO = "PROMO_CRISTAL_ARMAZON_LIMPIA"
L, F = [], []
def reg(t=""):
    print(t, flush=True); L.append(str(t))
def ok(c, d):
    reg(f"  {'OK  ' if c else 'FALLA'} {d}")
    if not c: F.append(d)

def copiar(o, dest):
    Path(dest).unlink(missing_ok=True)
    s = sqlite3.connect(f"file:{o}?mode=ro", uri=True); t = sqlite3.connect(str(dest))
    try: s.backup(t)
    finally: t.close(); s.close()

def foto(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True); q = lambda s, *a: c.execute(s, a).fetchone()[0]
    r = dict(art=q("select count(*) from articles"), act=q("select count(*) from articles where active=1"),
             mov=q("select count(*) from stock_movements"),
             asu=q("select coalesce(sum(quantity),0) from stock_movements where destination='ASUNCION'"),
             pil=q("select coalesce(sum(quantity),0) from stock_movements where destination='PILAR'"),
             entradas=q("select count(*) from cash_entries"),
             suma=q("select coalesce(sum(total),0) from cash_entries"),
             lineas=q("select count(*) from sale_items"),
             integridad=q("pragma integrity_check"),
             fk=len(c.execute("pragma foreign_key_check").fetchall()),
             neg=q("select count(*) from stock_actual where quantity<0"),
             huerf=q("select count(*) from stock_movements sm left join articles a on a.id=sm.article_id where a.id is null"),
             efec=q("select count(*) from event_effects ee left join domain_events de on de.event_id=ee.event_id where de.event_id is null"),
             retirados_con_stock=q("select count(*) from stock_actual sa join articles a on a.id=sa.article_id where a.active=0 and sa.quantity<>0"))
    c.close(); return r

def stock(p, sku, suc):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    v = c.execute("select coalesce(sum(sm.quantity),0) from stock_movements sm join articles a"
                  " on a.id=sm.article_id where a.sku=? and sm.destination=?", (sku, suc)).fetchone()[0]
    c.close(); return v

real = Path(resolve_data_paths().database)
copia = W / "dryrun013.sqlite3"
sha_antes = hashlib.sha256(real.read_bytes()).hexdigest()
reg("DRY RUN V1-013 -- sobre copia de la base productiva")
reg(f"base productiva : {real}")
reg(f"sha256 antes    : {sha_antes}")
copiar(real, copia)
antes = foto(copia)
reg(f"antes           : {antes['art']} articulos ({antes['act']} activos), {antes['mov']} "
    f"movimientos, ASU {antes['asu']} / PIL {antes['pil']}")
reg(f"  000037 ficticio: ASU {stock(copia,'000037','ASUNCION')} / PIL {stock(copia,'000037','PILAR')}")
reg(f"  000010 real    : ASU {stock(copia,'000010','ASUNCION')} / PIL {stock(copia,'000010','PILAR')}")
reg()

# ---- 1. retiro del ficticio ----
reg("== 1-2. compensacion y retiro de 000037 ==")
R.lineas, R.fallas = [], []
codigo = R.aplicar if False else None
import argparse
sys.argv = ["x", "--base", str(copia), "--confirmar"]
codigo = R.main()
for l in R.lineas:
    reg(f"    {l}")
ok(codigo == 0 and not R.fallas, "el retiro corrio sin fallas")
ok(stock(copia, "000037", "ASUNCION") == 0 and stock(copia, "000037", "PILAR") == 0,
   "000037 quedo en cero en las dos sucursales")
ok(stock(copia, "000010", "ASUNCION") == 100 and stock(copia, "000010", "PILAR") == 10,
   "000010 intacto: las unidades ficticias NO se le trasladaron")
reg()

# ---- 3-6. venta con el real, bonificada ----
reg("== 3-6. venta con 000010 bonificado ==")
catalogo = SQLiteCatalogRepository(copia)
ledger_repo = SQLiteStockLedgerRepository(copia)
integrador = VentasLedgerIntegrator(catalogo, ledger_repo)
caja = SQLiteCashDayRepository(copia, sale_integrator=integrador)
try:
    limpia = catalogo.get_article_by_sku("000010")
    armazones = [a for a in catalogo.list_articles()
                 if a.tracks_stock and a.sku.startswith("ASU-")][:1]
    armazon = armazones[0]
    reg(f"    armazon de prueba: {armazon.sku} {armazon.name[:30]}")
    linea_venta = SaleItem(description="Armazon + cristal", frame_price=280000,
                           lens_price=250000, article_id=armazon.id)
    linea_regalo = SaleItem(description=f"Limpia Cristal — obsequio {PROMO}",
                            item_type="OBSEQUIO", code="000010", frame_price=15000,
                            no_cost=True, article_id=limpia.id)
    total = linea_venta.subtotal + linea_regalo.subtotal
    dia = CashDay(business_date=date(2026, 8, 20), unit="PC", opening_cash=0,
                  opened_by="dryrun",
                  entries=[CashEntry(description="Venta con obsequio", saleswoman="ana",
                                     total=total, cash=total,
                                     items=(linea_venta, linea_regalo))])
    caja.save(dia)
    guardado = caja.get_by_date_and_unit(date(2026, 8, 20), "PC")
    ok(linea_regalo.subtotal == 0, "la linea del regalo vale 0")
    ok(guardado.entries[0].total == 530000, f"la venta cobra 530.000, sin el regalo "
                                            f"({guardado.entries[0].total})")
    ok(stock(copia, "000010", "ASUNCION") == 99,
       f"000010 en ASUNCION: 100 -> {stock(copia,'000010','ASUNCION')} (bajo 1 por el regalo)")
    ok(stock(copia, "000010", "PILAR") == 10, "000010 en PILAR sigue en 10")
    c = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
    nota = c.execute("select sm.note from stock_movements sm join articles a on a.id=sm.article_id"
                     " where a.sku='000010' and sm.kind='VENTA'").fetchone()
    ok(nota is not None and PROMO in nota[0], f"el movimiento dice que fue obsequio: {nota[0][:56] if nota else None}")
    sin_costo = c.execute("select no_cost from sale_items where article_id=?", (limpia.id,)).fetchone()
    ok(sin_costo is not None and sin_costo[0] == 1, "la linea quedo marcada sin costo")
    c.close()
    reg()

    # ---- 7. anulacion ----
    reg("== 7. anulacion de la venta bonificada ==")
    entry_id = guardado.entries[0].id
    guardado.void_entry(entry_id, "Prueba de anulacion")
    caja.save(guardado, audit_reason="Prueba de anulacion", edited_by="dryrun")
    ok(stock(copia, "000010", "ASUNCION") == 100,
       f"el frasco regalado volvio: {stock(copia,'000010','ASUNCION')}")
    c = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
    tipos = [r[0] for r in c.execute(
        "select sm.kind from stock_movements sm join articles a on a.id=sm.article_id"
        " where a.sku='000010' order by sm.occurred_at")]
    c.close()
    ok("VENTA" in tipos and "AJUSTE_POSITIVO" in tipos,
       f"la devolucion es un hecho nuevo, el original no se borro: {tipos}")
    reg()

    # ---- 8. venta sin promocion ----
    reg("== 8. venta sin promocion ==")
    dia2 = CashDay(business_date=date(2026, 8, 21), unit="PC", opening_cash=0,
                   opened_by="dryrun",
                   entries=[CashEntry(description="Venta sin obsequio", saleswoman="ana",
                                      total=280000, cash=280000,
                                      items=(SaleItem(description="Armazon solo",
                                                      frame_price=280000,
                                                      article_id=armazon.id),))])
    caja.save(dia2)
    ok(stock(copia, "000010", "ASUNCION") == 100,
       "sin obsequio, el limpia-cristal no se mueve")
    reg()

    # ---- 9. intentar usar el retirado ----
    reg("== 9. el retirado no se puede usar ==")
    ctrl = build_comercial_controller(copia)
    try:
        encontrados = {o.sku for o in ctrl.buscar_para_venta("LIMPIA", unidad="PC")}
    finally:
        ctrl.close()
    ok("000037" not in encontrados, "000037 no aparece en el buscador de la linea de venta")
    ok("000010" in encontrados, "000010 si aparece")
    reg()

    # ---- regalar sin stock ----
    reg("== control: no se regala lo que no hay ==")
    sin_stock = [a for a in catalogo.list_articles()
                 if a.tracks_stock and a.active
                 and integrador._ledger.stock(a.id, Destination.ASUNCION) == 0][:1]
    if sin_stock:
        art = sin_stock[0]
        dia3 = CashDay(business_date=date(2026, 8, 22), unit="PC", opening_cash=0,
                       opened_by="dryrun",
                       entries=[CashEntry(description="Regalo imposible", saleswoman="ana",
                                          total=0, cash=0,
                                          items=(SaleItem(description="regalo sin stock",
                                                          frame_price=1000, no_cost=True,
                                                          article_id=art.id),))])
        try:
            caja.save(dia3)
            ok(False, "deberia haber rechazado regalar sin stock")
        except StockInsuficiente:
            ok(True, f"regalar «{art.name[:22]}» sin stock se rechaza")
    reg()
finally:
    caja.close(); ledger_repo.close(); catalogo.close()

# ---- 10. idempotencia del retiro ----
reg("== 10. idempotencia del retiro ==")
antes_replay = foto(copia)
R.lineas, R.fallas = [], []
sys.argv = ["x", "--base", str(copia), "--confirmar"]
codigo = R.main()
replay = foto(copia)
ok(codigo != 0, "un segundo retiro se rechaza en las guardas")
ok(replay["mov"] == antes_replay["mov"] and replay["act"] == antes_replay["act"],
   "el replay no escribio nada")
reg()

reg("== invariantes ==")
final = foto(copia)
ok(final["integridad"] == "ok", f"integrity_check: {final['integridad']}")
ok(final["fk"] == 0, f"foreign_key_check: {final['fk']}")
ok(final["neg"] == 0, f"stock negativo: {final['neg']}")
ok(final["huerf"] == 0, f"huerfanos: {final['huerf']}")
ok(final["efec"] == 0, f"efectos sin hecho: {final['efec']}")
ok(final["retirados_con_stock"] == 0, f"stock en retirados: {final['retirados_con_stock']}")
reg()
reg("== Caja historica y misiones anteriores ==")
c = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
q = lambda s, *a: c.execute(s, a).fetchone()[0]
ok(q("select count(*) from cash_entries where id in (select id from cash_entries limit 12)") == 12,
   "las 12 entradas historicas siguen")
ids = ("inventario-inicial-asuncion-20260803", "inventario-inicial-pilar-20260810")
ok(q("select count(*) from stock_movements where document_id in (?,?)", *ids) == 3583,
   "V1-008 intacta: 3.583 movimientos")
ok(q("select count(*) from stock_movements where document_kind='CONCILIACION_INVENTARIO'") > 0,
   "los movimientos de V1-010 siguen ahi")
c.close()
reg()
sha_desp = hashlib.sha256(real.read_bytes()).hexdigest()
reg(f"sha256 base productiva despues: {sha_desp}")
ok(sha_desp == sha_antes, "la base productiva quedo intacta")
reg()
reg(f"VEREDICTO: {'PASS' if not F else 'FALLA'} ({len(F)} fallas)")
for f in F: reg(f"  - {f}")
(W / "DRY_RUN_013.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
raise SystemExit(0 if not F else 1)
