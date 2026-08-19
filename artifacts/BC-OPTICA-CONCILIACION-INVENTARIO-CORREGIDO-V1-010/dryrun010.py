"""Paso 6: dry run de la conciliacion, sobre copia de la base productiva.

Se aplica SOLO lo que la evidencia resuelve sin decision humana:
  - los 40 ajustes de cantidad, como AJUSTE_POSITIVO / AJUSTE_NEGATIVO
  - los articulos nuevos del corregido
  - la correccion de naturaleza de 2000056, revocada por definicion del negocio

Todo lo demas queda declarado como excepcion y NO se toca.
"""
import hashlib, json, pickle, sqlite3, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

RAIZ = Path(r"c:\Users\Striker\Desktop\Proyecto X\PX-Core\.worktrees\optica-conciliacion-010")
sys.path.insert(0, str(RAIZ))
W = Path(r"C:\Users\Striker\AppData\Local\Temp\claude\c--Users-Striker-Desktop-Proyecto-X-PX-Core\55fef905-3b6d-44f0-bf35-8b120350484f\scratchpad\m010")

from modulos.caja_diaria.config import resolve_data_paths
from modulos.comercial.application.comercial_controller import build_comercial_controller
from modulos.comercial.domain.models import (
    Article, ArticleNature, Destination, StockMovement, StockMovementKind)

d = pickle.load(open(W / "comparacion.pkl", "rb"))
COR, ANT, CAT, LEDGER, PEND, clases = d["COR"], d["ANT"], d["CAT"], d["LEDGER"], d["PEND"], d["clases"]

ACTOR = "COMMAND_CENTER/BC-OPTICA-CONCILIACION-INVENTARIO-CORREGIDO-V1-010"
MOTIVO = "ERROR_INVENTARIO"   # el codigo canonico que ya existe para «Error de inventario»
CORTE = "2026-08-19"
SERVICIOS_POR_DEFINICION = {"2000056"}   # regla C: la pieza es el servicio de colocarla

L, F = [], []
def reg(t=""):
    print(t, flush=True); L.append(str(t))
def ok(c, dsc):
    reg(f"  {'OK  ' if c else 'FALLA'} {dsc}")
    if not c: F.append(dsc)

def copiar(o, dest):
    Path(dest).unlink(missing_ok=True)
    s = sqlite3.connect(f"file:{o}?mode=ro", uri=True); t = sqlite3.connect(str(dest))
    try: s.backup(t)
    finally: t.close(); s.close()

def foto(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True); q = lambda s, *a: c.execute(s, a).fetchone()[0]
    r = dict(art=q("select count(*) from articles"), mov=q("select count(*) from stock_movements"),
             asu=q("select coalesce(sum(quantity),0) from stock_movements where destination='ASUNCION'"),
             pil=q("select coalesce(sum(quantity),0) from stock_movements where destination='PILAR'"),
             inicial=q("select count(*) from stock_movements where reason_code='INVENTARIO_INICIAL'"),
             entradas=q("select count(*) from cash_entries"),
             suma=q("select coalesce(sum(total),0) from cash_entries"),
             lineas=q("select count(*) from sale_items"),
             integridad=q("pragma integrity_check"),
             fk=len(c.execute("pragma foreign_key_check").fetchall()),
             neg=q("select count(*) from stock_actual where quantity<0"),
             huerf=q("select count(*) from stock_movements sm left join articles a on a.id=sm.article_id where a.id is null"),
             efec=q("select count(*) from event_effects ee left join domain_events de on de.event_id=ee.event_id where de.event_id is null"))
    c.close(); return r

real = Path(resolve_data_paths().database)
copia = W / "dryrun010.sqlite3"
sha_antes = hashlib.sha256(real.read_bytes()).hexdigest()
reg("DRY RUN -- CONCILIACION CON LOS INVENTARIOS CORREGIDOS")
reg(f"base productiva : {real}")
reg(f"sha256 antes    : {sha_antes}")
copiar(real, copia)
antes = foto(copia)
reg(f"antes           : {antes['art']} articulos, {antes['mov']} movimientos, "
    f"ASU {antes['asu']} / PIL {antes['pil']}")
reg()

# ---- que se aplica ----
ajustes = [(k, a, n) for k, a, n in clases["QUANTITY_CHANGED"]]
ajustes = [(k, LEDGER.get(k, 0), n["stock"], n) for k, a, n in ajustes if k in LEDGER]
# «Nuevo en el archivo» no es lo mismo que «nuevo en el catalogo». Un SKU global
# que antes solo aparecia en Pilar ya existe como articulo: lo que cambia es que
# ahora tambien se reporta en Asuncion. Los 9 Composturas de Asuncion son
# exactamente eso, y ya estan en el catalogo como servicios.
nuevos = [(k, v) for k, v in clases["NEW_ARTICLE"] if k[1] not in CAT]
ya_existen = [(k, v) for k, v in clases["NEW_ARTICLE"] if k[1] in CAT]
reg("== alcance del dry run ==")
reg(f"  ajustes de cantidad          : {len(ajustes)}")
reg(f"  articulos nuevos a crear     : {len(nuevos)}")
reg(f"  aparecen en la otra sucursal pero ya existen en el catalogo: {len(ya_existen)}")
for (suc, canon), v in sorted(ya_existen)[:12]:
    reg(f"      {suc:9} {canon:>14} {v['nombre'][:30]:32} "
        f"nature actual={CAT[canon]['nature']:24} stock declarado={v['stock']}")
reg(f"  correcciones de naturaleza   : {len(SERVICIOS_POR_DEFINICION)}")
reg(f"  NO se toca: 775 ausentes, los 4 pendientes de Pilar, 000010 de Asuncion,")
reg(f"             el SKU de obsequio 000037 y sus 726 unidades")
reg()

ctrl = build_comercial_controller(copia)
cuando = datetime(2026, 8, 19, 20, 0, 0, tzinfo=timezone.utc)
try:
    reg("== 1. articulos nuevos del corregido ==")
    por_cat = Counter()
    creados = {}
    # Un SKU global que aparece en las dos sucursales es UN articulo con stock en
    # los dos depositos, no dos articulos. Es la misma regla de identidad de la 008.
    por_canonico = {}
    for (suc, canon), v in nuevos:
        por_canonico.setdefault(canon, []).append((suc, v))
    reg(f"    de los {len(nuevos)} registros nuevos salen {len(por_canonico)} articulos: "
        f"{len(nuevos) - len(por_canonico)} son el mismo SKU global en las dos sucursales")
    for canon, apariciones in sorted(por_canonico.items()):
        v = max((x[1] for x in apariciones), key=lambda y: len(y["nombre"]))
        # Los Composturas son servicios: entran al catalogo sin stock.
        servicio = v["categoria"].lower().startswith("compostura")
        nat = (ArticleNature.SERVICIO_NO_STOCKEABLE if servicio
               else ArticleNature.PRODUCTO_STOCKEABLE)
        origen = "; ".join(
            f"{s}=Inventario {'PC' if s == 'ASUNCION' else 'P2'}.xls fila {x['fila']}"
            for s, x in apariciones)
        art = ctrl.guardar_articulo(
            sku=canon, name=v["nombre"], nature=nat, actor=ACTOR,
            notes=f"alta por conciliacion V1-010 @{CORTE}; origen {origen}",
            sale_price=int(v["precio"]) if v["precio"].isdigit() else None)
        for suc, x in apariciones:
            creados[(suc, canon)] = (art.id, nat, x)
        por_cat[(v["categoria"], nat.value)] += 1
    for k, c_ in sorted(por_cat.items()):
        reg(f"    {k[0][:26]:28} -> {k[1]:24} {c_:>4}")
    tras_altas = foto(copia)
    ok(tras_altas["art"] == antes["art"] + len(por_canonico),
       f"{len(por_canonico)} articulos creados de {len(nuevos)} registros")
    ok(tras_altas["mov"] == antes["mov"], "crear el catalogo no movio una sola unidad")
    reg()

    reg("== 2. stock inicial de los nuevos que si son stockeables ==")
    stockeables = [(k, v) for k, v in creados.items()
                   if v[1] is ArticleNature.PRODUCTO_STOCKEABLE and v[2]["stock"]]
    recuento = [(v[0], k[0], v[2]["stock"]) for k, v in stockeables]
    hecho = ctrl.cargar_stock_inicial(
        recuento, actor=ACTOR,
        origen=(f"Alta por conciliacion contra el inventario corregido del {CORTE}"),
        run_id=f"conciliacion-altas-{CORTE.replace('-', '')}", momento=cuando)
    reg(f"    {hecho.rows_imported} lineas, {sum(x[2] for x in recuento)} unidades")
    reg()

    reg("== 3. ajustes de cantidad ==")
    pos = neg = 0
    for (suc, canon), actual, corregido, v in ajustes:
        delta = corregido - actual
        if delta == 0: continue
        art_id = CAT[canon]["id"]
        kind = (StockMovementKind.AJUSTE_POSITIVO if delta > 0
                else StockMovementKind.AJUSTE_NEGATIVO)
        ctrl.ledger.registrar(StockMovement(
            article_id=art_id, destination=Destination(suc), kind=kind,
            quantity=abs(delta), actor=ACTOR, occurred_at=cuando,
            reason_code=MOTIVO,
            note=(f"Conciliacion contra Inventario {'PC' if suc == 'ASUNCION' else 'P2'}.xls "
                  f"del {CORTE}, fila {v['fila']}. Stock en el sistema: {actual}. "
                  f"Inventario corregido: {corregido}. Delta: {delta:+}"),
            document_kind="CONCILIACION_INVENTARIO",
            document_id=f"conciliacion-{CORTE.replace('-', '')}",
            idempotency_key=f"CONCILIACION:{CORTE}:{canon}:{suc}"))
        pos += delta if delta > 0 else 0
        neg += -delta if delta < 0 else 0
    reg(f"    AJUSTE_POSITIVO: {pos} unidades")
    reg(f"    AJUSTE_NEGATIVO: {neg} unidades")
    reg()

    reg("== 4. correccion de naturaleza revocada por el negocio ==")
    for sku in SERVICIOS_POR_DEFINICION:
        a = ctrl.articulo_por_sku(sku)
        antes_nat = a.nature.value
        ctrl.guardar_articulo(
            article_id=a.id, sku=a.sku, name=a.name,
            nature=ArticleNature.SERVICIO_NO_STOCKEABLE, actor=ACTOR,
            notes=(f"{a.notes} || NATURE_CORRECTION V1-010: de {antes_nat} a "
                   f"SERVICIO_NO_STOCKEABLE por definicion operativa del negocio. "
                   f"Las patillas son un servicio de reparacion, no un producto con stock. "
                   f"No requiere conteo fisico"))
        despues_nat = ctrl.articulo_por_sku(sku).nature.value
        ok(despues_nat == "SERVICIO_NO_STOCKEABLE",
           f"{sku}: {antes_nat} -> {despues_nat}")
        movs = sqlite3.connect(f"file:{copia}?mode=ro", uri=True).execute(
            "select count(*) from stock_movements sm join articles a on a.id=sm.article_id"
            " where a.sku=?", (sku,)).fetchone()[0]
        ok(movs == 0, f"{sku}: no habia stock que compensar ({movs} movimientos)")
finally:
    ctrl.close()

reg()
despues = foto(copia)
reg("== resultado ==")
reg(f"  articulos : {antes['art']} -> {despues['art']}")
reg(f"  movimientos: {antes['mov']} -> {despues['mov']}")
reg(f"  ASUNCION  : {antes['asu']} -> {despues['asu']}")
reg(f"  PILAR     : {antes['pil']} -> {despues['pil']}")
ok(despues["inicial"] > antes["inicial"],
   f"movimientos INVENTARIO_INICIAL: {antes['inicial']} -> {despues['inicial']} "
   f"(los de la 008 intactos, mas los de las altas)")
reg()
reg("== invariantes ==")
ok(despues["integridad"] == "ok", f"integrity_check: {despues['integridad']}")
ok(despues["fk"] == 0, f"foreign_key_check: {despues['fk']}")
ok(despues["neg"] == 0, f"stock negativo: {despues['neg']}")
ok(despues["huerf"] == 0, f"huerfanos: {despues['huerf']}")
ok(despues["efec"] == 0, f"efectos sin hecho: {despues['efec']}")
reg()
reg("== Caja historica ==")
for k, e in (("entradas", 12), ("suma", 6400000), ("lineas", 10)):
    ok(despues[k] == antes[k] == e, f"{k}: {despues[k]}")
reg()
reg("== historia de la 008 intacta ==")
c = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
# Las altas nuevas tambien entran por CARGA_INICIAL, asi que contar por
# document_kind mezcla las dos cosas. Lo que hay que verificar es que las DOS
# corridas de la 008 sigan enteras, identificadas por su document_id.
originales = c.execute(
    "select count(*) from stock_movements where document_id in (?,?)",
    ("inventario-inicial-asuncion-20260803", "inventario-inicial-pilar-20260810")).fetchone()[0]
ok(originales == 3583,
   f"las dos corridas de la 008 siguen enteras: {originales} movimientos, ninguno borrado")
unidades_008 = c.execute(
    "select coalesce(sum(quantity),0) from stock_movements where document_id in (?,?)",
    ("inventario-inicial-asuncion-20260803", "inventario-inicial-pilar-20260810")).fetchone()[0]
ok(unidades_008 == 8748, f"y sus 8.748 unidades tampoco se tocaron ({unidades_008})")
ok(c.execute("select count(*) from admin_audit_log where action='STOCK_INITIAL_PENDING_PHYSICAL_VERIFICATION'").fetchone()[0] == 5,
   "los 5 pendientes de la 008 siguen registrados")
c.close()
reg()
sha_desp = hashlib.sha256(real.read_bytes()).hexdigest()
reg(f"sha256 base productiva despues: {sha_desp}")
ok(sha_desp == sha_antes, "la base productiva quedo intacta")
reg()
reg(f"VEREDICTO: {'PASS' if not F else 'FALLA'} ({len(F)} fallas)")
for f in F: reg(f"  - {f}")
(W / "DRY_RUN_010.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
raise SystemExit(0 if not F else 1)
