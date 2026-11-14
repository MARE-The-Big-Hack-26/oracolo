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
    m = re.search(r"_H(\d+(?:[.,]\d+)?)", name, re.IGNORECASE)
    if not m:
        return default
    v = float(m.group(1).replace(",", "."))
    return v / 1000.0 if v >= 20 else v


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
    poly = Polygon(pts)
    return poly if poly.is_valid and poly.area > 0 else poly.buffer(0)


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
