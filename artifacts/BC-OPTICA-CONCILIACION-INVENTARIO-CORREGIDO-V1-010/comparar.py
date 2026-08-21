"""Paso 2: comparacion corregido vs anterior vs catalogo vs ledger productivo."""
import json, pickle, re, sqlite3, sys, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

W = Path(r"C:\Users\Striker\AppData\Local\Temp\claude\c--Users-Striker-Desktop-Proyecto-X-PX-Core\55fef905-3b6d-44f0-bf35-8b120350484f\scratchpad\m010")
REAL = Path(r"C:\Users\Striker\AppData\Local\BC\Caja\bc_caja.sqlite3")
d = pickle.load(open(W / "perfil.pkl", "rb"))
nuevo, viejo = d["nuevo"], d["viejo"]
NUEVO = {"PC": "ASUNCION", "P2": "PILAR"}
PREFIJO = {"ASUNCION": "ASU", "PILAR": "PIL"}
SKU_RE = re.compile(r"^\s*(\d{4,})\s*(.*)$")

out = []
def reg(t=""):
    out.append(str(t))

def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def es_global(sku):
    if 11 <= len(sku) <= 13: return True
    if len(sku) == 6 and sku.startswith("00"): return True
    if len(sku) == 7 and sku.startswith("2000"): return True
    return False

def canonico(sku, sucursal):
    return sku if es_global(sku) else f"{PREFIJO[sucursal]}-{sku}"

def desc(articulo):
    m = SKU_RE.match(articulo)
    return m.group(2).strip() if m else articulo

# --- indexar corregido y anterior por (sucursal, sku canonico) ---
COR, ANT = {}, {}
for tag in ("PC", "P2"):
    suc = NUEVO[tag]
    for f in nuevo[tag]["filas"]:
        sku = f["cod_barra"] or (SKU_RE.match(f["articulo"]).group(1) if SKU_RE.match(f["articulo"]) else "")
        if not sku: continue
        COR[(suc, canonico(sku, suc))] = dict(
            sku=sku, nombre=desc(f["articulo"]), categoria=f["categoria"], marca=f["marca"],
            stock=int(float(f["stock"])) if f["stock"] else None,
            costo=f["costo"], precio=f["precio"], fila=f["n"])
    for f in viejo[tag]:
        m = SKU_RE.match(f["articulo"])
        if not m: continue
        sku = m.group(1)
        ANT[(suc, canonico(sku, suc))] = dict(
            sku=sku, nombre=m.group(2).strip(), categoria=f["categoria"], marca=f["marca"],
            stock=int(f["stock"]) if f["stock"].isdigit() else None, fila=f["n"])

# --- catalogo y ledger productivos ---
c = sqlite3.connect(f"file:{REAL}?mode=ro", uri=True); c.row_factory = sqlite3.Row
CAT = {}
for fila in c.execute("""select a.sku, a.name, a.nature, coalesce(ac.name,'') cat,
                                coalesce(b.name,'') marca, a.id
                         from articles a
                         left join article_categories ac on ac.id=a.category_id
                         left join brands b on b.id=a.brand_id"""):
    CAT[fila["sku"]] = dict(nombre=fila["name"], nature=fila["nature"], categoria=fila["cat"],
                            marca=fila["marca"], id=fila["id"])
LEDGER = {}
for fila in c.execute("""select a.sku, sm.destination, sum(sm.quantity) q
                         from stock_movements sm join articles a on a.id=sm.article_id
                         group by a.sku, sm.destination"""):
    LEDGER[(fila["destination"], fila["sku"])] = fila["q"]
PEND = {}
for fila in c.execute("""select a.sku, al.details_json from admin_audit_log al
                         join articles a on a.id=al.target_id
                         where al.action='STOCK_INITIAL_PENDING_PHYSICAL_VERIFICATION'"""):
    j = json.loads(fila["details_json"])
    PEND[(j["sucursal"], fila["sku"])] = j
c.close()

# --- clasificacion ---
SENTINELA = lambda q: q is not None and (q >= 9000 or 890 <= q <= 1000)
clases = defaultdict(list)
todas = sorted(set(COR) | set(ANT))
for clave in todas:
    suc, canon = clave
    a, n = ANT.get(clave), COR.get(clave)
    if n and not a:
        clases["NEW_ARTICLE"].append((clave, n))
        continue
    if a and not n:
        clases["REMOVED_OR_NOT_PRESENT"].append((clave, a))
        continue
    if a["stock"] != n["stock"]:
        clases["QUANTITY_CHANGED"].append((clave, a, n))
    else:
        clases["UNCHANGED"].append((clave, n))
    if norm(a["nombre"]) != norm(n["nombre"]):
        clases["DESCRIPTION_CHANGED"].append((clave, a["nombre"], n["nombre"]))
    if norm(a["categoria"]) != norm(n["categoria"]):
        clases["CATEGORY_CHANGED"].append((clave, a["categoria"], n["categoria"]))
    if norm(a["marca"]) != norm(n["marca"]):
        clases["BRAND_CHANGED"].append((clave, a["marca"], n["marca"]))
for clave, n in [(k, v) for k, v in COR.items()]:
    if SENTINELA(n["stock"]):
        clases["SOURCE_SENTINEL"].append((clave, n))

reg("=" * 78)
reg("PASO 2 -- COMPARACION")
reg("=" * 78)
reg(f"  universo (sucursal, sku canonico): {len(todas)}")
for k in ("UNCHANGED", "QUANTITY_CHANGED", "NEW_ARTICLE", "REMOVED_OR_NOT_PRESENT",
          "DESCRIPTION_CHANGED", "CATEGORY_CHANGED", "BRAND_CHANGED", "SOURCE_SENTINEL"):
    reg(f"  {k:26} {len(clases[k]):>6}")
reg()

reg("-- QUE SIGNIFICA 'AUSENTE DEL ARCHIVO CORREGIDO' --")
reg(f"  filas con stock <= 0 en el corregido: PC=0, P2=0")
reg(f"  filas con stock <= 0 en el anterior : PC=0, P2=0")
reg("  Los dos informes listan SOLO lo que el sistema viejo cree que tiene stock > 0.")
reg("  Por lo tanto 'ausente' significa 'el sistema viejo dice stock 0', NO 'no existe'")
reg("  y NO es una afirmacion fisica.")
reg()
faltantes = clases["REMOVED_OR_NOT_PRESENT"]
por_suc = Counter(k[0] for k, _ in faltantes)
reg(f"  ausentes por sucursal: {dict(por_suc)}")
cats = Counter(v["categoria"] or "(sin cat)" for _, v in faltantes)
reg(f"  categorias de los ausentes: {dict(cats.most_common(8))}")
stocks = Counter(v["stock"] for _, v in faltantes)
reg(f"  stock que tenian en el anterior: {dict(sorted(stocks.items())[:8])}")
reg(f"  unidades que representaban: {sum(v['stock'] or 0 for _, v in faltantes)}")
reg()

reg("-- NUEVOS --")
por_suc = Counter(k[0] for k, _ in clases["NEW_ARTICLE"])
reg(f"  por sucursal: {dict(por_suc)}")
cats = Counter(v["categoria"] or "(sin cat)" for _, v in clases["NEW_ARTICLE"])
reg(f"  categorias: {dict(cats.most_common(10))}")
reg("  muestra:")
for clave, v in clases["NEW_ARTICLE"][:10]:
    reg(f"    {clave[0]:9} {clave[1]:>14} {v['nombre'][:34]:36} cat={v['categoria'][:16]:18} stock={v['stock']}")
reg()

reg("-- CANTIDAD CAMBIADA (muestra de las mayores) --")
cambios = sorted(clases["QUANTITY_CHANGED"], key=lambda x: -abs((x[2]["stock"] or 0) - (x[1]["stock"] or 0)))
for clave, a, n in cambios[:14]:
    reg(f"    {clave[0]:9} {clave[1]:>14} {n['nombre'][:28]:30} {a['stock']:>7} -> {n['stock']:>7}"
        f"  (delta {n['stock'] - a['stock']:+})  cat={n['categoria'][:14]}")
reg(f"    ... {len(cambios)} en total")
reg()

reg("-- CENTINELAS EN EL CORREGIDO --")
por_suc = Counter(k[0] for k, _ in clases["SOURCE_SENTINEL"])
reg(f"  por sucursal: {dict(por_suc)}")
cats = Counter(v["categoria"] for _, v in clases["SOURCE_SENTINEL"])
reg(f"  categorias: {dict(cats.most_common())}")
reg(f"  unidades que representan: {sum(v['stock'] for _, v in clases['SOURCE_SENTINEL'])}")
for clave, v in sorted(clases["SOURCE_SENTINEL"], key=lambda x: -x[1]["stock"])[:22]:
    reg(f"    {clave[0]:9} {clave[1]:>14} {v['nombre'][:32]:34} cat={v['categoria'][:14]:16} {v['stock']:>7}")
reg()

reg("-- LOS CINCO PENDIENTES, SEGUN EL CORREGIDO --")
for (suc, sku), j in sorted(PEND.items()):
    canon = canonico(sku, suc)
    n = COR.get((suc, canon))
    a = ANT.get((suc, canon))
    reg(f"  {suc:9} {sku:>8} {j['nombre'][:26]:28}")
    reg(f"      antes (008)  : {a['stock'] if a else 'ausente'}   (declaraba {j['source_reported_quantity']})")
    reg(f"      corregido    : {n['stock'] if n else 'AUSENTE del archivo corregido'}"
        + (f"   cat={n['categoria']}  precio={n['precio']}  costo={n['costo']}" if n else ""))
    reg(f"      en el ledger : {LEDGER.get((suc, canon), 0)}")
reg()

reg("-- LEDGER PRODUCTIVO vs CORREGIDO, para lo que hoy tiene stock --")
dif = []
for (suc, canon), q in sorted(LEDGER.items()):
    n = COR.get((suc, canon))
    if n is None:
        dif.append((suc, canon, q, None))
    elif n["stock"] != q:
        dif.append((suc, canon, q, n["stock"]))
reg(f"  articulos con stock en produccion: {len(LEDGER)}")
reg(f"  coinciden con el corregido       : {len(LEDGER) - len(dif)}")
reg(f"  difieren o no estan              : {len(dif)}")
sin_archivo = [x for x in dif if x[3] is None]
con_delta = [x for x in dif if x[3] is not None]
reg(f"      no estan en el corregido     : {len(sin_archivo)}  ({sum(x[2] for x in sin_archivo)} unidades en produccion)")
reg(f"      estan con otra cantidad      : {len(con_delta)}")
reg(f"      delta positivo (falta stock) : {sum(1 for x in con_delta if x[3] > x[2])}, "
    f"{sum(x[3]-x[2] for x in con_delta if x[3] > x[2])} unidades")
reg(f"      delta negativo (sobra stock) : {sum(1 for x in con_delta if x[3] < x[2])}, "
    f"{sum(x[2]-x[3] for x in con_delta if x[3] < x[2])} unidades")
reg("  mayores diferencias:")
for x in sorted(con_delta, key=lambda y: -abs(y[3]-y[2]))[:12]:
    nom = COR[(x[0], x[1])]["nombre"][:28]
    reg(f"    {x[0]:9} {x[1]:>14} {nom:30} produccion={x[2]:>7} corregido={x[3]:>7} delta={x[3]-x[2]:+}")

pickle.dump(dict(COR=COR, ANT=ANT, CAT=CAT, LEDGER=LEDGER, PEND=PEND, clases=dict(clases)),
            open(W / "comparacion.pkl", "wb"))
(W / "comparacion.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
