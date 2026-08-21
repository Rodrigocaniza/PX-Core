"""Dry run V1-010 recalculado con las decisiones humanas del 2026-08-19.

Cambia respecto del plan anterior, que queda obsoleto:
  - Hilo, Tornillo, Plaqueta y Par de patillas pasan a SERVICIO_NO_STOCKEABLE
  - los 775 ausentes se retiran del catalogo activo, compensando su stock antes
  - 000010 no recibe ningun ajuste: Asuncion sigue pendiente y Pilar conserva sus 10
  - 000037 no se toca: va entero al slice 013
"""
import hashlib, json, pickle, sqlite3, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(r"c:\Users\Striker\Desktop\Proyecto X\PX-Core\.worktrees\optica-conciliacion-010")
sys.path.insert(0, str(RAIZ))
W = Path(r"C:\Users\Striker\AppData\Local\Temp\claude\c--Users-Striker-Desktop-Proyecto-X-PX-Core\55fef905-3b6d-44f0-bf35-8b120350484f\scratchpad\m010")

from modulos.caja_diaria.config import resolve_data_paths
from modulos.comercial.application.comercial_controller import build_comercial_controller
from modulos.comercial.domain.models import (
    ArticleNature, Destination, StockMovement, StockMovementKind)

d = pickle.load(open(W / "comparacion.pkl", "rb"))
COR, ANT, CAT, LEDGER, clases = d["COR"], d["ANT"], d["CAT"], d["LEDGER"], d["clases"]

ACTOR = "COMMAND_CENTER/BC-OPTICA-CONCILIACION-INVENTARIO-CORREGIDO-V1-010"
MOTIVO = "ERROR_INVENTARIO"
CORTE = "2026-08-19"
#: Decision 1: los cuatro conceptos de compostura no son inventario fisico.
A_SERVICIO = {"2000056": "Par de patillas", "2000070": "Hilo",
              "2000071": "Tornillo", "2000072": "Plaqueta"}
#: Decision 3 y limpia-cristal de obsequio: fuera de todo ajuste en esta mision.
INTOCABLES = {"000010", "000037"}

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
    r = dict(art=q("select count(*) from articles"),
             activos=q("select count(*) from articles where active=1"),
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
             efec=q("select count(*) from event_effects ee left join domain_events de on de.event_id=ee.event_id where de.event_id is null"))
    c.close(); return r

real = Path(resolve_data_paths().database)
copia = W / "dryrun010b.sqlite3"
sha_antes = hashlib.sha256(real.read_bytes()).hexdigest()
reg("DRY RUN V1-010 RECALCULADO -- con las decisiones humanas del 2026-08-19")
reg(f"base productiva : {real}")
reg(f"sha256 antes    : {sha_antes}")
copiar(real, copia)
antes = foto(copia)
reg(f"antes           : {antes['art']} articulos ({antes['activos']} activos), "
    f"{antes['mov']} movimientos, ASU {antes['asu']} / PIL {antes['pil']}")
reg()

# ---------------- alcance ----------------
def _variantes(canon):
    pre, sep, num = canon.rpartition("-")
    base = num if sep else canon
    salida = set()
    for cand in {base.lstrip("0"), "0" + base, base.zfill(13), base.zfill(12), base.zfill(11)}:
        if cand and cand != base:
            salida.add(pre + sep + cand if sep else cand)
    return salida

# El archivo corregido normaliza algunos codigos de barra a 13 digitos con un
# cero adelante. Un codigo que «desaparece» y otro que «aparece» con el mismo
# numero rellenado son el mismo articulo renumerado, no una baja y un alta.
_aus = {k for k, v in clases["REMOVED_OR_NOT_PRESENT"]}
_nue = {k for k, v in clases["NEW_ARTICLE"]}
RENUMERADOS = {}
for suc, canon in sorted(_aus):
    for v in _variantes(canon):
        if (suc, v) in _nue:
            RENUMERADOS[(suc, canon)] = v
            break

nuevos = [(k, v) for k, v in clases["NEW_ARTICLE"]
          if k[1] not in CAT and k not in {(s, n) for (s, _), n in RENUMERADOS.items()}]
# ASU-101814 nunca entro al catalogo: la 008 lo rechazo por no tener descripcion.
# No es una baja, es una fila que nunca fue un articulo.
NUNCA_EXISTIERON = {(s, c) for (s, c), _ in clases["REMOVED_OR_NOT_PRESENT"] if c not in CAT}
ausentes = [(k, v) for k, v in clases["REMOVED_OR_NOT_PRESENT"]
            if k not in RENUMERADOS and k not in NUNCA_EXISTIERON]
ajustes = [(k, LEDGER[k], n["stock"], n)
           for k, a, n in clases["QUANTITY_CHANGED"]
           if k in LEDGER and n["stock"] != LEDGER[k] and COR[k]["sku"] not in INTOCABLES]
excluidos = [(k, LEDGER.get(k), COR[k]["stock"]) for k, a, n in clases["QUANTITY_CHANGED"]
             if COR[k]["sku"] in INTOCABLES]

reg("== alcance ==")
reg(f"  altas                        : {len(nuevos)} registros")
reg(f"  retiros por ausencia         : {len(ausentes)}")
reg(f"  ajustes de cantidad          : {len(ajustes)}")
reg(f"  cambios de naturaleza        : {len(A_SERVICIO)}")
reg(f"  renumerados (mismo codigo con cero adelante): {len(RENUMERADOS)}")
for k, v in sorted(RENUMERADOS.items()):
    reg(f"      {k[0]:9} {k[1]} -> {v}: mismo articulo, NO se da de baja ni de alta")
reg(f"  filas que nunca fueron articulo: {len(NUNCA_EXISTIERON)} {sorted(NUNCA_EXISTIERON)}")
reg(f"  excluidos por decision humana: {len(excluidos)}")
for k, prod, cor in sorted(excluidos):
    reg(f"      {k[0]:9} {COR[k]['sku']:>8} {COR[k]['nombre'][:26]:28} "
        f"produccion={prod} corregido={cor} -> SIN AJUSTE")
reg()

ctrl = build_comercial_controller(copia)
cuando = datetime(2026, 8, 19, 21, 0, 0, tzinfo=timezone.utc)
try:
    # ---------------- 1. altas ----------------
    reg("== 1. altas del inventario corregido ==")
    por_canonico = {}
    for (suc, canon), v in nuevos:
        por_canonico.setdefault(canon, []).append((suc, v))
    creados = {}
    for canon, apar in sorted(por_canonico.items()):
        v = max((x[1] for x in apar), key=lambda y: len(y["nombre"]))
        servicio = v["categoria"].lower().startswith("compostura")
        nat = ArticleNature.SERVICIO_NO_STOCKEABLE if servicio else ArticleNature.PRODUCTO_STOCKEABLE
        origen = "; ".join(f"{s}=Inventario {'PC' if s == 'ASUNCION' else 'P2'}.xls fila {x['fila']}"
                           for s, x in apar)
        art = ctrl.guardar_articulo(sku=canon, name=v["nombre"], nature=nat, actor=ACTOR,
                                    notes=f"alta por conciliacion V1-010 @{CORTE}; origen {origen}",
                                    sale_price=int(v["precio"]) if v["precio"].isdigit() else None)
        for suc, x in apar:
            creados[(suc, canon)] = (art.id, nat, x)
    reg(f"    {len(por_canonico)} articulos de {len(nuevos)} registros "
        f"({len(nuevos) - len(por_canonico)} SKU globales consolidados)")
    tras = foto(copia)
    ok(tras["art"] == antes["art"] + len(por_canonico), f"{len(por_canonico)} articulos creados")
    ok(tras["mov"] == antes["mov"], "el catalogo no creo una sola unidad")
    stockeables = [(k, v) for k, v in creados.items()
                   if v[1] is ArticleNature.PRODUCTO_STOCKEABLE and v[2]["stock"]]
    hecho = ctrl.cargar_stock_inicial(
        [(v[0], k[0], v[2]["stock"]) for k, v in stockeables], actor=ACTOR,
        origen=f"Alta por conciliacion contra el inventario corregido del {CORTE}",
        run_id=f"conciliacion-altas-{CORTE.replace('-', '')}", momento=cuando)
    unidades_altas = sum(v[2]["stock"] for k, v in stockeables)
    reg(f"    stock inicial: {hecho.rows_imported} lineas, {unidades_altas} unidades")
    reg()

    # ---------------- 2. cambios de naturaleza ----------------
    reg("== 2. cambios de naturaleza (decision 1) ==")
    for sku, nombre in sorted(A_SERVICIO.items()):
        a = ctrl.articulo_por_sku(sku)
        previa = a.nature.value
        stock_previo = sqlite3.connect(f"file:{copia}?mode=ro", uri=True).execute(
            "select coalesce(sum(quantity),0) from stock_movements where article_id=?",
            (a.id,)).fetchone()[0]
        ok(stock_previo == 0, f"{sku} {nombre}: 0 unidades, no hay stock que compensar")
        ctrl.guardar_articulo(
            article_id=a.id, sku=a.sku, name=a.name,
            nature=ArticleNature.SERVICIO_NO_STOCKEABLE, actor=ACTOR,
            notes=(f"{a.notes} || NATURE_CORRECTION V1-010: {previa} -> SERVICIO_NO_STOCKEABLE "
                   f"por definicion operativa. Es un concepto de compostura, no inventario "
                   f"fisico controlado. Las cifras de la fuente "
                   f"({ANT.get(('PILAR', sku), {}).get('stock')} el 2026-08-10, "
                   f"{COR.get(('PILAR', sku), {}).get('stock')} el {CORTE}) quedan solo como "
                   f"evidencia historica: eran centinelas, no conteos. No requiere conteo"))
        ok(ctrl.articulo_por_sku(sku).nature.value == "SERVICIO_NO_STOCKEABLE",
           f"{sku}: {previa} -> SERVICIO_NO_STOCKEABLE")
    reg()

    # ---------------- 3. retiros ----------------
    reg("== 3. retiros por ausencia en el corregido (decision 2) ==")
    con_stock, sin_stock, sigue_vivo = [], [], []
    conn = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
    ausentes_por_sucursal = {k for k, v in ausentes}
    for (suc, canon), v in ausentes:
        art_id = CAT[canon]["id"]
        q = conn.execute("select coalesce(sum(quantity),0) from stock_movements"
                         " where article_id=? and destination=?", (art_id, suc)).fetchone()[0]
        ventas = conn.execute("select count(*) from sale_items where article_id=? or lens_article_id=?",
                              (art_id, art_id)).fetchone()[0]
        # El articulo sigue vivo si la OTRA sucursal lo tiene y no lo declaro ausente.
        otras = dict(conn.execute("select destination, sum(quantity) from stock_movements"
                                  " where article_id=? and destination<>? group by destination",
                                  (art_id, suc)))
        vivo_en_otra = any(cant > 0 and (dest, canon) not in ausentes_por_sucursal
                           for dest, cant in otras.items())
        if vivo_en_otra or ventas:
            sigue_vivo.append((suc, canon, q, v, otras, ventas))
        (con_stock if q > 0 else sin_stock).append((suc, canon, q, v))
    conn.close()
    reg(f"    ausentes reales identificados : {len(ausentes)}")
    reg(f"    con stock en su sucursal      : {len(con_stock)}  ({sum(x[2] for x in con_stock)} unidades)")
    reg(f"    sin stock, solo se deprecian  : {len(sin_stock)}")
    reg(f"    siguen vivos en la otra sucursal o tienen venta: {len(sigue_vivo)}")
    for x in sigue_vivo:
        reg(f"        {x[0]:9} {x[1]:>14} otras={x[4]} ventas={x[5]} -> se compensa "
            f"{x[0]} pero el articulo NO se retira")

    comp = Counter()
    for suc, canon, q, v in con_stock:
        ctrl.ledger.registrar(StockMovement(
            article_id=CAT[canon]["id"], destination=Destination(suc),
            kind=StockMovementKind.AJUSTE_NEGATIVO, quantity=q, actor=ACTOR,
            occurred_at=cuando, reason_code=MOTIVO,
            note=(f"RECONCILIACION_INVENTARIO_CORREGIDO / ARTICULO_RETIRADO. "
                  f"El articulo no aparece en Inventario "
                  f"{'PC' if suc == 'ASUNCION' else 'P2'}.xls del {CORTE}. "
                  f"Stock que dejaba V1-008: {q}. Se lleva a cero antes de retirarlo del "
                  f"catalogo activo. El movimiento original de V1-008 no se toca"),
            document_kind="CONCILIACION_INVENTARIO",
            document_id=f"retiro-{CORTE.replace('-', '')}",
            idempotency_key=f"RETIRO:{CORTE}:{canon}:{suc}"))
        comp[suc] += q
    reg(f"    compensado: ASUNCION {comp['ASUNCION']} unidades, PILAR {comp['PILAR']} unidades")

    # Solo se retira el articulo que queda sin stock en NINGUNA sucursal y sin
    # ventas. El producto ya lo impide -- desactivar algo con stock lo sacaria de
    # las busquedas dejando unidades que nadie mira -- y esa guarda es correcta.
    no_retirables = {x[1] for x in sigue_vivo}
    retirados = set()
    for suc, canon, q, v in con_stock + sin_stock:
        if canon in retirados or canon in no_retirables: continue
        ctrl.desactivar_articulo(
            CAT[canon]["id"], actor=ACTOR,
            motivo=(f"CORRECTED_SOURCE_ABSENCE -> RETIRE_FROM_ACTIVE_CATALOG. No aparece en "
                    f"el inventario corregido del {CORTE}. Estaba en la fuente anterior "
                    f"({'PC - Inventario.xlsx' if suc == 'ASUNCION' else 'P2 - Inventario.xlsx'} "
                    f"fila {v['fila']}) con stock {v['stock']}. Se conserva la historia"))
        retirados.add(canon)
    reg(f"    retirados del catalogo activo : {len(retirados)} articulos")
    reg(f"    NO retirados por seguir vivos : {len(no_retirables)}")
    reg()

    # ---------------- 4. ajustes de cantidad ----------------
    reg("== 4. ajustes de cantidad de los que si siguen ==")
    pos = neg = 0
    for (suc, canon), actual, corregido, v in ajustes:
        delta = corregido - actual
        kind = StockMovementKind.AJUSTE_POSITIVO if delta > 0 else StockMovementKind.AJUSTE_NEGATIVO
        ctrl.ledger.registrar(StockMovement(
            article_id=CAT[canon]["id"], destination=Destination(suc), kind=kind,
            quantity=abs(delta), actor=ACTOR, occurred_at=cuando, reason_code=MOTIVO,
            note=(f"RECONCILIACION_INVENTARIO_CORREGIDO. Inventario "
                  f"{'PC' if suc == 'ASUNCION' else 'P2'}.xls del {CORTE} fila {v['fila']}. "
                  f"Stock del sistema: {actual}. Corregido: {corregido}. Delta: {delta:+}"),
            document_kind="CONCILIACION_INVENTARIO",
            document_id=f"conciliacion-{CORTE.replace('-', '')}",
            idempotency_key=f"CONCILIACION:{CORTE}:{canon}:{suc}"))
        pos += max(delta, 0); neg += max(-delta, 0)
    reg(f"    AJUSTE_POSITIVO: {pos} unidades ({sum(1 for x in ajustes if x[2] > x[1])} articulos)")
    reg(f"    AJUSTE_NEGATIVO: {neg} unidades ({sum(1 for x in ajustes if x[2] < x[1])} articulos)")
finally:
    ctrl.close()

reg()
despues = foto(copia)
reg("== resultado ==")
reg(f"  articulos      : {antes['art']} -> {despues['art']}")
reg(f"  activos        : {antes['activos']} -> {despues['activos']}")
reg(f"  movimientos    : {antes['mov']} -> {despues['mov']}")
reg(f"  stock ASUNCION : {antes['asu']} -> {despues['asu']}")
reg(f"  stock PILAR    : {antes['pil']} -> {despues['pil']}")
reg()

reg("== limpia cristal, verificacion explicita ==")
c = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
q = lambda s, *a: c.execute(s, a).fetchone()[0]
asu10 = q("select coalesce(sum(sm.quantity),0) from stock_movements sm join articles a"
          " on a.id=sm.article_id where a.sku='000010' and sm.destination='ASUNCION'")
pil10 = q("select coalesce(sum(sm.quantity),0) from stock_movements sm join articles a"
          " on a.id=sm.article_id where a.sku='000010' and sm.destination='PILAR'")
ok(asu10 == 0, f"000010 ASUNCION sigue sin unidades y sin ajuste ({asu10})")
ok(q("select count(*) from admin_audit_log al join articles a on a.id=al.target_id"
     " where a.sku='000010' and al.action='STOCK_INITIAL_PENDING_PHYSICAL_VERIFICATION'") == 1,
   "000010 ASUNCION conserva su pendiente")
ok(pil10 == 10, f"000010 PILAR intacto en 10 ({pil10})")
o37 = dict(c.execute("select sm.destination, sum(sm.quantity) from stock_movements sm"
                     " join articles a on a.id=sm.article_id where a.sku='000037'"
                     " group by sm.destination"))
ok(o37 == {"ASUNCION": 210, "PILAR": 516}, f"000037 sin stock ficticio nuevo: {o37}")
ok(q("select active from articles where sku='000037'") == 1,
   "000037 sigue activo: su retiro es del slice 013")
reg()

reg("== estado final de los cuatro conceptos de compostura ==")
for sku in sorted(A_SERVICIO):
    nat = q("select nature from articles where sku=?", sku)
    st = q("select coalesce(sum(sm.quantity),0) from stock_movements sm join articles a"
           " on a.id=sm.article_id where a.sku=?", sku)
    pend = q("select count(*) from admin_audit_log al join articles a on a.id=al.target_id"
             " where a.sku=? and al.action='STOCK_INITIAL_PENDING_PHYSICAL_VERIFICATION'", sku)
    ok(nat == "SERVICIO_NO_STOCKEABLE" and st == 0,
       f"{sku} {A_SERVICIO[sku][:18]:20} {nat:24} stock={st} (pendiente de la 008 registrado: {pend})")
ok(q("""select count(*) from articles a left join article_categories ac on ac.id=a.category_id
        where a.nature='PRODUCTO_STOCKEABLE' and ac.name like 'Compostura%'""") == 0,
   "no queda ningun articulo de Compostura clasificado como producto")
reg()

reg("== invariantes ==")
ok(despues["integridad"] == "ok", f"integrity_check: {despues['integridad']}")
ok(despues["fk"] == 0, f"foreign_key_check: {despues['fk']}")
ok(despues["neg"] == 0, f"stock negativo: {despues['neg']}")
ok(despues["huerf"] == 0, f"huerfanos: {despues['huerf']}")
ok(despues["efec"] == 0, f"efectos sin hecho: {despues['efec']}")
reg("== Caja historica ==")
for k, e in (("entradas", 12), ("suma", 6400000), ("lineas", 10)):
    ok(despues[k] == antes[k] == e, f"{k}: {despues[k]}")
reg("== historia de V1-008 ==")
orig = q("select count(*) from stock_movements where document_id in (?,?)",
         "inventario-inicial-asuncion-20260803", "inventario-inicial-pilar-20260810")
uni = q("select coalesce(sum(quantity),0) from stock_movements where document_id in (?,?)",
        "inventario-inicial-asuncion-20260803", "inventario-inicial-pilar-20260810")
ok(orig == 3583 and uni == 8748, f"las dos corridas siguen enteras: {orig} movimientos, {uni} unidades")
ok(q("select count(*) from admin_audit_log where action='STOCK_INITIAL_PENDING_PHYSICAL_VERIFICATION'") == 5,
   "los 5 pendientes de la 008 siguen registrados")
c.close()
reg()
sha_desp = hashlib.sha256(real.read_bytes()).hexdigest()
reg(f"sha256 base productiva despues: {sha_desp}")
ok(sha_desp == sha_antes, "la base productiva quedo intacta")
reg()
reg(f"VEREDICTO: {'PASS' if not F else 'FALLA'} ({len(F)} fallas)")
for f in F: reg(f"  - {f}")
(W / "DRY_RUN_010B.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
json.dump(dict(altas=len(por_canonico), unidades_altas=unidades_altas,
               retirados=len(retirados), con_stock=len(con_stock),
               sin_stock=len(sin_stock), no_retirables=len(no_retirables),
               renumerados=len(RENUMERADOS), ausentes=len(ausentes),
               comp=dict(comp), ajustes=len(ajustes),
               pos=pos, neg=neg, antes=antes, despues=despues),
          open(W / "resumen010b.json", "w"), ensure_ascii=False, indent=1)
raise SystemExit(0 if not F else 1)
