"""Import della planimetria CAD (DXF) -> Scene.

Convenzioni sui layer (nomi senza distinzione tra maiuscole e minuscole):
  PERIMETRO / MURI / BOUNDS   polilinea chiusa = contorno del magazzino
  qualsiasi altro layer       polilinee chiuse (e cerchi) = ostacoli che coprono la vista
                              (scaffali, pareti, pilastri, carichi)
  ..._H3.0 o ..._H3000        altezza dell'ostacolo nel nome del layer (>= 20 -> millimetri,
                              altrimenti metri). Senza suffisso: ``default_height``.
  LINE / polilinee aperte      ignorate, salvo ``lines_as_walls=True``: muri disegnati a segmenti
                              (tipico delle scansioni LiDAR) -> ostacoli sottili (``wall_width``)
  layer in ``ignore_layers``  ignorati (quote, testi, arredo a terra)
Unità: dal valore INSUNITS del file (mm, cm, m); si può forzare con ``unit``.
Se non c'è un perimetro, si usa il rettangolo che racchiude tutto.
"""
from __future__ import annotations

import re

import ezdxf
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from .geometry import Occluder, Scene

_UNIT_TO_M = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0}  # pollici, piedi, mm, cm, m
_PERIM = ("perimetro", "muri", "bounds", "perimeter")


def _layer_height(name: str, default: float) -> float:
    matches = re.findall(r"_H(\d+(?:[.,]\d+)?)", name, re.IGNORECASE)
    if not matches:
        return default
    v = float(matches[-1].replace(",", "."))
    return v / 1000.0 if v >= 20 else v


def _clean_poly(poly: Polygon) -> Polygon:
    if not poly.is_valid or poly.area <= 0:
        poly = poly.buffer(0)
    if poly.geom_type in ("MultiPolygon", "GeometryCollection"):
        polys = [g for g in poly.geoms if g.geom_type == "Polygon" and not g.is_empty and g.area > 0]
        poly = max(polys, key=lambda g: g.area, default=Polygon())
    return poly


def _polyline_poly(spec_obj: dict, default_width: float = 0.15) -> Polygon:
    pts = [(float(p[0]), float(p[1])) for p in spec_obj.get("points", [])]
    width = float(spec_obj.get("width", default_width))
    if len(pts) < 2 or width <= 0:
        raise ValueError("Spezzata non valida (servono almeno 2 punti e width > 0)")
    return _clean_poly(LineString(pts).buffer(width / 2.0, cap_style=2, join_style=2))


def _poly_from_entity(e, k: float, wall_width: float = 0.10, lines_as_walls: bool = False):
    t = e.dxftype()
    if t == "LINE":
        if not lines_as_walls:
            return None
        a, b = e.dxf.start, e.dxf.end
        if (a.x, a.y) == (b.x, b.y):
            return None
        return LineString([(a.x * k, a.y * k), (b.x * k, b.y * k)]).buffer(wall_width / 2, cap_style=2)
    if t == "LWPOLYLINE":
        pts = [(x * k, y * k) for x, y, *_ in e.get_points()]
        closed = e.closed
    elif t == "POLYLINE":
        pts = [(v.dxf.location.x * k, v.dxf.location.y * k) for v in e.vertices]
        closed = e.is_closed
    elif t == "CIRCLE":
        c = e.dxf.center
        return Point(c.x * k, c.y * k).buffer(e.dxf.radius * k, 16)
    else:
        return None
    if len(pts) >= 2 and not closed:  # polilinea aperta = muro sottile (solo se richiesto)
        return LineString(pts).buffer(wall_width / 2, cap_style=2) if lines_as_walls else None
    if len(pts) < 3:
        return None
    return _clean_poly(Polygon(pts))


def load_dxf(path, unit: float | None = None, default_height: float = 3.0, ignore_layers=(), wall_width: float = 0.10,
             lines_as_walls: bool = False):
    """Ritorna (Scene, info). ``unit`` = metri per unità del disegno (es. 0.001 per mm)."""
    doc = ezdxf.readfile(path)
    k = unit if unit is not None else _UNIT_TO_M.get(int(doc.header.get("$INSUNITS", 6)), 1.0)
    ignore = {x.lower() for x in ignore_layers}
    bounds, occ, per_layer, has_lines = None, [], {}, False
    for e in doc.modelspace():
        layer = e.dxf.layer
        if layer.lower() in ignore:
            continue
        poly = _poly_from_entity(e, k, wall_width, lines_as_walls)
        if poly is None or poly.is_empty:
            continue
        if e.dxftype() == "LINE" or (e.dxftype() in ("LWPOLYLINE", "POLYLINE") and not (getattr(e, "closed", False) or getattr(e, "is_closed", False))):
            has_lines = True
        if layer.lower() in _PERIM:
            bounds = poly if bounds is None else unary_union([bounds, poly])
        else:
            occ.append(Occluder(f"{layer}#{len(occ)}", poly, _layer_height(layer, default_height)))
            per_layer[layer] = per_layer.get(layer, 0) + 1
    if bounds is None:
        allp = unary_union([o.poly for o in occ]) if occ else box(0, 0, 1, 1)
        minx, miny, maxx, maxy = allp.bounds
        m = 0.0 if has_lines else 1.0  # con muri a segmenti i confini sono i muri stessi
        bounds = box(minx - m, miny - m, maxx + m, maxy + m)
    elif bounds.geom_type != "Polygon":
        bounds = bounds.convex_hull
    info = {"unit_m": k, "bounds_m": bounds.bounds, "occluders": len(occ), "layers": per_layer}
    return Scene(bounds, occ), info


def scene_from_spec(spec: dict) -> Scene:
    """Costruisce una ``Scene`` da specifica JSON (perimetro/bounds/corridor + ostacoli)."""
    if "bounds" in spec and isinstance(spec["bounds"], (list, tuple)) and len(spec["bounds"]) >= 3:
        bounds = Polygon([(float(p[0]), float(p[1])) for p in spec["bounds"]])
    elif "corridor" in spec and isinstance(spec["corridor"], dict):
        bounds = _polyline_poly(spec["corridor"], default_width=1.8)
    elif "perimetro" in spec:
        x, y, w, d = (float(v) for v in spec["perimetro"])
        if w <= 0 or d <= 0:
            raise ValueError("Larghezza e lunghezza devono essere > 0")
        bounds = box(x, y, x + w, y + d)
    else:
        raise ValueError("Perimetro mancante")
    bounds = _clean_poly(bounds)
    if bounds.is_empty or bounds.area <= 0 or bounds.geom_type != "Polygon":
        raise ValueError("Perimetro non valido")

    occluders = []
    for i, o in enumerate(spec.get("obstacles", spec.get("ostacoli", []))):
        name = str(o.get("name") or o.get("nome") or f"ostacolo_{i + 1}").strip() or f"ostacolo_{i + 1}"
        height = float(o.get("height", o.get("altezza", 1.8)))
        if height <= 0:
            raise ValueError("L'altezza deve essere > 0")
        ring = o.get("coords") if "coords" in o else o.get("polygon")
        if isinstance(ring, (list, tuple)) and len(ring) >= 3:
            poly = _clean_poly(Polygon([(float(p[0]), float(p[1])) for p in ring]))
        elif isinstance(o.get("wall"), dict):
            poly = _polyline_poly(o["wall"], default_width=0.15)
        elif isinstance(o.get("points"), (list, tuple)):
            poly = _polyline_poly(o, default_width=0.15)
        elif "w" in o and "d" in o:
            x, y, w, d = float(o.get("x", 0.0)), float(o.get("y", 0.0)), float(o["w"]), float(o["d"])
            if w <= 0 or d <= 0:
                raise ValueError("Larghezza e lunghezza devono essere > 0")
            poly = box(x, y, x + w, y + d)
        else:
            raise ValueError("Ostacolo senza dimensioni valide")
        if poly.is_empty or poly.area <= 0 or poly.geom_type != "Polygon":
            raise ValueError("Ostacolo non valido")
        occluders.append(Occluder(name, poly, height))
    return Scene(bounds, occluders)


def save_dxf(scene: Scene, path) -> None:
    """Salva una ``Scene`` in DXF (metri) con layer PERIMETRO e <NOME>_H<altezza>."""
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6  # metri
    msp = doc.modelspace()
    if "PERIMETRO" not in doc.layers:
        doc.layers.add("PERIMETRO")
    msp.add_lwpolyline(list(scene.bounds.exterior.coords)[:-1], close=True, dxfattribs={"layer": "PERIMETRO"})
    for o in scene.occluders:
        raw = re.sub(r"#\d+$", "", o.name)
        raw = re.sub(r"(?:_H\d+(?:[.,_]\d+)?)+$", "", raw, flags=re.IGNORECASE)
        base = re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_").upper() or "OSTACOLO"
        layer = f"{base}_H{float(o.height):.2f}"
        if layer not in doc.layers:
            doc.layers.add(layer)
        msp.add_lwpolyline(list(o.poly.exterior.coords)[:-1], close=True, dxfattribs={"layer": layer})
    doc.saveas(path)
