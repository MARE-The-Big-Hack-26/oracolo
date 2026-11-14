"""Geometria 2D/2.5D: poligoni di visibilità, linea di vista, distanza visibile.

Unità: metri. Nessuna dipendenza da OpenCV, testabile senza camera.

Convenzione 2.5D: ogni ostacolo (Occluder) ha un'altezza. Un ostacolo blocca la
vista tra un occhio a quota ``eye_h`` e un bersaglio a quota ``target_h`` solo se
la retta che li congiunge passa sotto la sua sommità.

Nel poligono di visibilità (che non conosce il bersaglio preciso) si usa una
regola CONSERVATIVA: un ostacolo blocca se è più alto del minimo tra occhio e
bersaglio. Più ombra = più prudenza.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union


@dataclass
class Occluder:
    name: str
    poly: Polygon
    height: float  # metri


@dataclass
class Scene:
    bounds: Polygon
    occluders: list = field(default_factory=list)

    def walkable(self):
        """Area percorribile: confini meno gli ostacoli."""
        if not self.occluders:
            return self.bounds
        return self.bounds.difference(unary_union([o.poly for o in self.occluders]))


@dataclass
class Agent:
    """Un punto di vista o un bersaglio (conducente, sensore, pedone)."""

    name: str
    xy: tuple
    eye_h: float = 1.5
    target_h: float = 1.0
    heading: float | None = None  # radianti; None = 360 gradi
    half_fov: float = np.pi  # semi-apertura, radianti


def _segments(polys) -> np.ndarray:
    segs = []
    for p in polys:
        rings = [p.exterior, *p.interiors]
        for r in rings:
            c = np.asarray(r.coords)
            segs.append(np.hstack([c[:-1], c[1:]]))
    return np.vstack(segs)


def _cast(origin, angles: np.ndarray, segs: np.ndarray) -> np.ndarray:
    """Distanza al primo segmento colpito, per ogni angolo (vettorizzato)."""
    ox, oy = origin
    dx = np.cos(angles)[:, None]
    dy = np.sin(angles)[:, None]
    x1, y1, x2, y2 = segs.T
    ex, ey = x2 - x1, y2 - y1
    denom = dx * ey - dy * ex
    wx, wy = x1 - ox, y1 - oy
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (wx * ey - wy * ex) / denom
        u = (wx * dy - wy * dx) / denom
    ok = (np.abs(denom) > 1e-12) & (t > 1e-9) & (u >= -1e-9) & (u <= 1 + 1e-9)
    return np.where(ok, t, np.inf).min(axis=1)


def _wedge(origin, heading, half_angle, radius, n=48) -> Polygon:
    a = np.linspace(heading - half_angle, heading + half_angle, n)
    pts = [tuple(origin)] + [
        (origin[0] + radius * np.cos(t), origin[1] + radius * np.sin(t)) for t in a
    ]
    return Polygon(pts)


def _scene_diag(scene: Scene) -> float:
    return float(np.hypot(*np.ptp(np.asarray(scene.bounds.exterior.coords), axis=0)))


def obstacle_shadow(origin, occ: Occluder, eye_h: float, target_h: float = 0.0, max_reach: float = 30.0) -> Polygon:
    """Ombra 2.5D proiettata a quota ``target_h`` da ``occ`` visto da ``origin`` a quota ``eye_h``."""
    if occ.height <= target_h or occ.poly.is_empty or occ.poly.geom_type != "Polygon":
        return Polygon()
    cx, cy = float(origin[0]), float(origin[1])
    ring = list(occ.poly.exterior.coords)[:-1]
    if len(ring) < 3:
        return Polygon()
    min_d = min(float(np.hypot(x - cx, y - cy)) for x, y in ring)
    inf_scale = max(float(max_reach), float(max_reach) / max(min_d, 0.05))
    s = inf_scale if (eye_h <= target_h or occ.height >= eye_h - 0.02) else min((eye_h - target_h) / (eye_h - occ.height), inf_scale)
    proj = [(cx + (x - cx) * s, cy + (y - cy) * s) for x, y in ring]
    parts = []
    p_poly = Polygon(proj)
    if not p_poly.is_valid:
        p_poly = p_poly.buffer(0)
    if not p_poly.is_empty and p_poly.area > 1e-9:
        parts.append(p_poly)
    for i in range(len(ring)):
        j = (i + 1) % len(ring)
        q = Polygon([ring[i], ring[j], proj[j], proj[i]])
        if not q.is_valid:
            q = q.buffer(0)
        if not q.is_empty and q.area > 1e-9:
            parts.append(q)
    if not parts:
        return Polygon()
    sh = unary_union(parts).difference(occ.poly)
    return sh if sh.is_valid else sh.buffer(0)


def scene_shadows(
    origin,
    scene: Scene,
    eye_h: float = 1.8,
    target_h: float = 0.0,
    heading: float | None = None,
    half_fov: float = np.pi,
) -> list[list[list[float]]]:
    """Anelli dei poligoni d'ombra 2.5D proiettati dagli ostacoli sull'area percorribile."""
    if not scene.occluders:
        return []
    reach = max(30.0, _scene_diag(scene) * 3.0)
    valid = [g for g in (obstacle_shadow(origin, o, eye_h, target_h, reach) for o in scene.occluders) if not g.is_empty]
    if not valid:
        return []
    area = scene.walkable()
    if heading is not None and half_fov < np.pi:
        area = area.intersection(_wedge(origin, heading, half_fov, reach))
    merged = unary_union(valid).intersection(area)
    if merged.is_empty:
        return []
    geoms = [merged] if merged.geom_type == "Polygon" else list(getattr(merged, "geoms", []))
    return [[[round(x, 3), round(y, 3)] for x, y in g.exterior.coords]
            for g in geoms if g.geom_type == "Polygon" and not g.is_empty and g.area > 1e-6]


def visibility_polygon(
    origin,
    scene: Scene,
    eye_h: float = 1.0,
    target_h: float = 1.0,
    heading: float | None = None,
    half_fov: float = np.pi,
    max_range: float | None = None,
    n_base: int = 360,
):
    """Poligono visibile da ``origin`` (algoritmo a raggi sui blocchi alti + ombre 2.5D)."""
    ox, oy = origin
    thr = min(eye_h, target_h)
    if eye_h > target_h:
        blockers = [o.poly for o in scene.occluders if o.height >= eye_h]
        partial = [o for o in scene.occluders if target_h < o.height < eye_h]
    else:
        blockers = [o.poly for o in scene.occluders if o.height > thr]
        partial = []
    segs = _segments([scene.bounds, *blockers])
    verts = segs[:, :2]
    base = np.arctan2(verts[:, 1] - oy, verts[:, 0] - ox)
    eps = 1e-6
    angles = np.sort(
        np.concatenate(
            [base - eps, base, base + eps, np.linspace(-np.pi, np.pi, n_base, endpoint=False)]
        )
    )
    t = _cast(origin, angles, segs)
    t = np.where(np.isfinite(t), t, 0.0)
    pts = np.column_stack([ox + t * np.cos(angles), oy + t * np.sin(angles)])
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if partial:
        reach = max(30.0, _scene_diag(scene) * 3.0)
        cuts = [g for g in ([obstacle_shadow(origin, o, eye_h, target_h, reach) for o in partial] + [o.poly for o in partial]) if not g.is_empty]
        if cuts:
            poly = poly.difference(unary_union(cuts))
            if not poly.is_valid:
                poly = poly.buffer(0)
    if max_range is not None:
        poly = poly.intersection(Point(origin).buffer(max_range, 48))
    if heading is not None and half_fov < np.pi:
        radius = max_range or (_scene_diag(scene) * 2)
        poly = poly.intersection(_wedge(origin, heading, half_fov, radius))
    return poly


def _coords_of(geom) -> np.ndarray:
    return shapely.get_coordinates(geom)


def line_of_sight(a, a_h: float, b, b_h: float, scene: Scene) -> bool:
    """Vista esatta 2.5D tra due punti a quote diverse."""
    seg = LineString([a, b])
    length = seg.length
    if length == 0:
        return True
    for o in scene.occluders:
        inter = seg.intersection(o.poly)
        if inter.is_empty:
            continue
        coords = _coords_of(inter)
        ts = [seg.project(Point(c)) / length for c in coords]
        t0, t1 = min(ts), max(ts)
        z0 = a_h + (b_h - a_h) * t0
        z1 = a_h + (b_h - a_h) * t1
        if min(z0, z1) < o.height:
            return False
    return True


def _in_fov(viewer: Agent, xy) -> bool:
    if viewer.heading is None or viewer.half_fov >= np.pi:
        return True
    ang = np.arctan2(xy[1] - viewer.xy[1], xy[0] - viewer.xy[0])
    d = (ang - viewer.heading + np.pi) % (2 * np.pi) - np.pi
    return abs(d) <= viewer.half_fov


def sees(viewer: Agent, target: Agent, scene: Scene) -> bool:
    if not _in_fov(viewer, target.xy):
        return False
    return line_of_sight(viewer.xy, viewer.eye_h, target.xy, target.target_h, scene)


def mutual_visibility(agents: list, scene: Scene) -> dict:
    """Matrice (a, b) -> bool: 'a vede b'. Mostra le asimmetrie di sguardo."""
    out = {}
    for a in agents:
        for b in agents:
            if a is not b:
                out[(a.name, b.name)] = sees(a, b, scene)
    return out


def classify_pair(a_sees_b: bool, b_sees_a: bool) -> str:
    if a_sees_b and b_sees_a:
        return "reciproca"
    if a_sees_b and not b_sees_a:
        return "solo_a_vede_b"
    if b_sees_a and not a_sees_b:
        return "solo_b_vede_a"
    return "cecita_reciproca"


def visible_distance_along(path: LineString, vis, step: float = 0.05) -> float:
    """Metri visibili lungo un percorso a partire dall'inizio, fino alla prima zona cieca."""
    n = int(path.length / step) + 1
    ds = np.linspace(0.0, path.length, n)
    pts = shapely.line_interpolate_point(path, ds)
    inside = shapely.covers(vis, pts)
    if inside.all():
        return float(path.length)
    return float(ds[int(np.argmin(inside))])
