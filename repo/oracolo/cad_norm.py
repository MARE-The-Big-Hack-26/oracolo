"""Normalizzazione di un CAD (DXF) allo standard Oracolo.

Porta un DXF "sporco" (millimetri, origine lontana, layer con nomi propri, quote, testi, porte)
a una ``Scene`` in metri con il perimetro in (0, 0). NON usa OpenCV (è parte del motore).

Cosa fa, in ordine:
  1. unità: da INSUNITS se plausibile, altrimenti stima dalla dimensione (stanza 1-200 m) e avvisa;
  2. ignora layer di quote/testi/porte/finestre/tratteggi (per nome) ed entità non supportate;
  3. ostacolo = poligono chiuso (o cerchio) su un layer non ignorato; altezza dal suffisso ``_H``
     del layer, se manca ``default_height`` (prudente: ostacolo alto = più ombra);
  4. perimetro: poligono su un layer "muri/perimetro" oppure, per FORMA, il poligono più grande
     che contiene quasi tutti gli altri; contorno esterno di muri doppi scartato;
  5. scarta oggetti minuscoli e elementi sottili e corti attaccati al perimetro (porte/finestre);
  6. sposta tutto in modo che il perimetro parta da (0, 0).

Ritorna ``(scene | None, report)`` con ``report = {ok, errors, warnings, stats}``: gli avvisi ci sono sempre.
Limiti dichiarati: nessuna rotazione/raddrizzamento; ARC, SPLINE, HATCH e quote non sono letti.
Prototipo di ricerca: non è un controllo di conformità del CAD.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import ezdxf
from shapely import affinity
from shapely.geometry import Polygon, box

from .cad import _UNIT_TO_M, _layer_height, _poly_from_entity
from .geometry import Occluder, Scene

PLAUSIBLE_ROOM_M = (1.0, 200.0)   # lato massimo del perimetro
MIN_AREA_M2 = 0.10                # sotto: oggetto minuscolo (un pilastro 0,4x0,4 m = 0,16 m² resta)
DOOR_MAX_THICK_M = 0.30           # porta/finestra: sottile...
DOOR_MAX_LEN_M = 3.0              # ...e corta, attaccata al perimetro
UNIT_GUESS_ORDER = (1.0, 0.001, 0.01, 0.0254, 0.3048)  # m, mm, cm, pollici, piedi

_PERIM_TOKENS = {"perimetro", "perimeter", "bounds", "muri", "muro", "wall", "walls", "contorno", "confine", "outline"}
_IGNORE_TOKENS = {"door", "doors", "porta", "porte", "window", "windows", "finestra", "finestre", "text", "testo",
                  "testi", "title", "cartiglio", "grid", "axis", "assi", "defpoints", "dim", "dims", "quota"}
_IGNORE_PREFIX = ("dimen", "quot", "annot", "tratteg", "hatch")


def _tokens(layer: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", layer.lower()) if t]


def _is_perimeter_layer(layer: str) -> bool:
    return any(t in _PERIM_TOKENS for t in _tokens(layer))


def _is_ignored_layer(layer: str) -> bool:
    return any(t in _IGNORE_TOKENS or t.startswith(_IGNORE_PREFIX) for t in _tokens(layer))


def _has_height(layer: str) -> bool:
    return re.search(r"_H\d", layer, re.IGNORECASE) is not None


@dataclass
class _Item:
    layer: str
    poly: Polygon


def _walk(entities, layer_override=None, depth=0):
    """Entità del modelspace, con i blocchi (INSERT) espansi in coordinate mondo."""
    for e in entities:
        layer = e.dxf.layer if layer_override is None or e.dxf.layer != "0" else layer_override
        if e.dxftype() == "INSERT" and depth < 3:
            try:
                sub = list(e.virtual_entities())
            except Exception:  # noqa: BLE001 - blocco malformato: lo si salta
                continue
            yield from _walk(sub, layer_override=e.dxf.layer if layer == "0" else layer, depth=depth + 1)
        else:
            yield layer, e


def _pick_unit(header_unit, size_raw: float, forced):
    ok = lambda k: PLAUSIBLE_ROOM_M[0] <= size_raw * k <= PLAUSIBLE_ROOM_M[1]
    if forced:
        return forced, "forzata", None
    if header_unit and ok(header_unit):
        return header_unit, "INSUNITS", None
    for k in UNIT_GUESS_ORDER:
        if ok(k):
            why = (f"INSUNITS indica {header_unit} m/unità ma darebbe {size_raw * header_unit:.4g} m: "
                   if header_unit else "INSUNITS assente: ")
            return k, "stimata", why + f"assunto {k:g} m per unità del disegno ({size_raw * k:.3g} m) — verificare"
    return None, "nessuna", None


def _frac_inside(c: Polygon, others: list, tol: float = 0.05) -> float:
    if not others:
        return 1.0
    cb = c.buffer(tol)
    return sum(o.within(cb) for o in others) / len(others)


def _find_perimeter(items: list):
    """(item, sorgente, accettati). Prima i layer 'muri/perimetro', poi la forma."""
    named = [i for i in items if _is_perimeter_layer(i.layer)]
    for pool, source in ((named, "layer"), (items, "forma")):
        if not pool or (source == "forma" and named == items):
            continue
        acc = []
        for c in sorted(pool, key=lambda i: i.poly.area, reverse=True):
            # gli anelli che contengono già il candidato (muro esterno di una doppia linea) non contano
            others = [i.poly for i in items if i is not c and not i.poly.buffer(0.05).contains(c.poly)]
            if (others and _frac_inside(c.poly, others) >= 0.8) or (not others and c.poly.area >= 4.0):
                acc.append(c)
        if acc:
            # muri a doppia linea (esterno + interno): vale l'interno, cioè lo spazio libero
            best = acc[-1] if len(acc) > 1 and acc[-1].poly.area >= 0.5 * acc[0].poly.area else acc[0]
            return best, source
    return None, "nessuno"


def normalize_dxf(path, *, unit: float | None = None, default_height: float = 3.0, ignore_layers=(),
                  min_area: float = MIN_AREA_M2, lines_as_walls: bool = False, wall_width: float = 0.10):
    """Ritorna ``(Scene | None, report)``. ``unit`` = metri per unità del disegno (forza la stima)."""
    rep = {"ok": False, "errors": [], "warnings": [], "stats": {}}
    warn, err, st = rep["warnings"].append, rep["errors"].append, rep["stats"]
    try:
        doc = ezdxf.readfile(str(path))
    except (OSError, ezdxf.DXFError) as ex:
        err(f"File non leggibile come DXF ({type(ex).__name__}: {ex}). Servono file .dxf (non DWG).")
        return None, rep

    user_ign = {x.lower() for x in ignore_layers}
    dropped = Counter()
    ignored_layers = set()
    skipped_types = Counter()
    raw_entities = []
    for layer, e in _walk(doc.modelspace()):
        if layer.lower() in user_ign or _is_ignored_layer(layer):
            dropped["layer_ignorato"] += 1
            ignored_layers.add(layer)
            continue
        raw_entities.append((layer, e))

    # passata 1: dimensione nelle unità del disegno, per stimare l'unità
    probe = []
    for layer, e in raw_entities:
        p = _poly_from_entity(e, 1.0, 1e-6, lines_as_walls)
        if p is not None and not p.is_empty:
            probe.append(p)
    if not probe:
        err("Nessun poligono chiuso utilizzabile (solo linee, testi o quote?). "
            "Se è una scansione a segmenti usare lines_as_walls; altrimenti ridisegnare in /room.")
        return None, rep
    ref = probe if lines_as_walls else [max(probe, key=lambda p: p.area)]
    minx, miny, maxx, maxy = _bbox(ref)
    size_raw = max(maxx - minx, maxy - miny)
    header = doc.header.get("$INSUNITS", 0)
    k, unit_src, unit_msg = _pick_unit(_UNIT_TO_M.get(int(header)), size_raw, unit)
    if k is None:
        err(f"Dimensioni non plausibili per una stanza (1-200 m) con nessuna unità nota (lato massimo = {size_raw:.4g} unità).")
        return None, rep
    if unit_msg:
        warn(unit_msg)

    # passata 2: poligoni in metri
    items = []
    for layer, e in raw_entities:
        t = e.dxftype()
        p = _poly_from_entity(e, k, wall_width, lines_as_walls)
        if p is None or p.is_empty:
            if t not in ("LINE", "LWPOLYLINE", "POLYLINE", "CIRCLE", "INSERT"):
                skipped_types[t] += 1
            elif t == "LINE" or t in ("LWPOLYLINE", "POLYLINE"):
                skipped_types["linee/polilinee aperte"] += 1
            continue
        if p.geom_type != "Polygon":
            p = max(p.geoms, key=lambda g: g.area) if hasattr(p, "geoms") else p
        items.append(_Item(layer, p))
    if skipped_types:
        warn("Entità ignorate (non supportate o aperte): " + ", ".join(f"{n}={c}" for n, c in sorted(skipped_types.items())))

    big = [i for i in items if i.poly.area >= min_area]
    dropped["minuscoli"] = len(items) - len(big)
    items = big
    if ignored_layers:
        warn("Layer ignorati per nome (quote/testi/porte/finestre/tratteggi): " + ", ".join(sorted(ignored_layers)) +
             ". Se uno conteneva ostacoli veri, rinominarlo.")
    if dropped["minuscoli"]:
        warn(f"{dropped['minuscoli']} oggetti minuscoli (< {min_area:g} m²) scartati.")
    if not items:
        err("Dopo aver scartato gli oggetti minuscoli non resta nessun poligono.")
        return None, rep

    per, source = _find_perimeter(items)
    outer_ring = []
    if per is not None:
        outer_ring = [i for i in items if i is not per and i.poly.buffer(0.05).contains(per.poly)]
        dropped["contorno_esterno_muri"] = len(outer_ring)
        bounds = per.poly
    else:
        allb = _bbox([i.poly for i in items])
        m = 0.0 if lines_as_walls else 1.0
        bounds = box(allb[0] - m, allb[1] - m, allb[2] + m, allb[3] + m)
        warn("Perimetro non riconosciuto (nessun layer muri/perimetro e nessun poligono che contiene gli altri): "
             "uso il rettangolo che racchiude tutto" + ("" if lines_as_walls else " + 1 m") +
             ". Verificare che coincida con l'area reale.")
    if not bounds.is_valid:
        bounds = bounds.buffer(0)
    if bounds.geom_type != "Polygon":
        bounds = bounds.convex_hull
    bw = bounds.bounds
    room = max(bw[2] - bw[0], bw[3] - bw[1])
    if not (PLAUSIBLE_ROOM_M[0] <= room <= PLAUSIBLE_ROOM_M[1]):
        err(f"Stanza di {room:.3g} m: fuori dall'intervallo plausibile {PLAUSIBLE_ROOM_M[0]:g}-{PLAUSIBLE_ROOM_M[1]:g} m.")
        return None, rep

    occ, no_height_layers, door_like = [], set(), 0
    inner = bounds.buffer(0.05)
    for it in items:
        if it is per or it in outer_ring:
            continue
        poly = it.poly
        if not poly.within(inner):
            clipped = poly.intersection(bounds)
            if clipped.is_empty or clipped.area < min_area:
                dropped["fuori_perimetro"] += 1
                continue
            poly = max(clipped.geoms, key=lambda g: g.area) if hasattr(clipped, "geoms") else clipped
            if poly.geom_type != "Polygon":
                dropped["fuori_perimetro"] += 1
                continue
        if per is not None:
            sides = sorted(_rect_sides(poly))
            if sides[0] < DOOR_MAX_THICK_M and sides[1] < DOOR_MAX_LEN_M and poly.distance(bounds.exterior) < 0.30:
                door_like += 1
                continue
        if not _has_height(it.layer):
            no_height_layers.add(it.layer)
        occ.append((it.layer, poly, _layer_height(it.layer, default_height)))
    if door_like:
        dropped["porte_finestre_per_forma"] = door_like
        warn(f"{door_like} elementi sottili (<{DOOR_MAX_THICK_M:g} m) e corti (<{DOOR_MAX_LEN_M:g} m) attaccati al perimetro "
             "scartati come porte/finestre: se erano tramezzi, ridisegnarli o allungarli.")
    if dropped["fuori_perimetro"]:
        warn(f"{dropped['fuori_perimetro']} oggetti fuori dal perimetro scartati.")
    if no_height_layers:
        warn(f"Altezza non indicata nel nome del layer ({', '.join(sorted(no_height_layers))}): usata {default_height:g} m "
             "(prudente: più alto = più ombra). Per altezze vere usare layer del tipo NOME_H2800.")

    # origine in (0, 0)
    ox, oy = bw[0], bw[1]
    bounds = affinity.translate(bounds, -ox, -oy)
    occluders = [Occluder(f"{layer}#{n}", affinity.translate(p, -ox, -oy), h) for n, (layer, p, h) in enumerate(occ)]
    if not occluders:
        warn("Nessun ostacolo riconosciuto: la stanza risulta tutta visibile. Verificare i layer.")
    scene = Scene(bounds, occluders)
    per_layer = Counter(layer for layer, _, _ in occ)
    st.update({
        "unit_m": k, "unit_source": unit_src, "origin_offset_m": (round(ox, 4), round(oy, 4)),
        "bounds_m": tuple(round(v, 4) for v in bounds.bounds), "size_m": (round(bw[2] - bw[0], 3), round(bw[3] - bw[1], 3)),
        "perimeter_source": source, "perimeter_layer": per.layer if per else None,
        "occluders": len(occluders), "layers": dict(per_layer), "dropped": dict(dropped),
        "heights": sorted({round(o.height, 3) for o in occluders}),
    })
    rep["ok"] = True
    return scene, rep


def _bbox(polys):
    bs = [p.bounds for p in polys]
    return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))


def _rect_sides(poly: Polygon):
    """Lati del rettangolo minimo ruotato che racchiude il poligono."""
    c = list(poly.minimum_rotated_rectangle.exterior.coords)
    if len(c) < 4:
        return (0.0, 0.0)
    a = ((c[1][0] - c[0][0]) ** 2 + (c[1][1] - c[0][1]) ** 2) ** 0.5
    b = ((c[2][0] - c[1][0]) ** 2 + (c[2][1] - c[1][1]) ** 2) ** 0.5
    return (a, b)
