"""Pipeline live: un frame -> persone e muletto in metri -> motore Oracolo -> livello e limite di velocità.

Convenzioni:
* La camera è fissa e calibrata (``Calibration``). Le persone si localizzano dai piedi (a terra);
  il muletto (sedia) dal marker ArUco, con correzione della quota del marker.
* Cosa vede la camera = visibilità geometrica dalla posizione della camera, ristretta
  all'inquadratura (impronta). Ciò che sta fuori campo o dietro un ostacolo è "non osservato".
* Il CONDUCENTE (chi spinge la sedia) è escluso: una persona vicina al muletto e non davanti
  a esso non è un pedone da proteggere.
* Il percorso del muletto è la retta nella direzione di marcia, fermata dal primo ostacolo.
"""
from __future__ import annotations

import base64
import math

import cv2
import numpy as np
import shapely
from shapely.ops import nearest_points
from shapely.geometry import Point

from ..cab import CAUSE_IT
from ..engine import Oracle
from ..geometry import visibility_polygon
from ..policy import LEVEL_NAMES, PedParams, VehicleParams
from .detectors import MarkerDetector, NoPersonDetector
from .tracker import PersonTracker, VehicleTracker


def frame_health(frame) -> float:
    """1 = immagine buona; scende con luce estrema o immagine sfocata/coperta."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    mean = float(gray.mean())
    lap = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    h = 1.0
    if mean < 25 or mean > 245:
        h = 0.4
    if lap < 2.0:
        h = min(h, 0.5)
    return h


class LivePipeline:
    def __init__(self, scene, calib=None, params: VehicleParams | None = None, ped: PedParams | None = None,
                 person_detector=None, marker: MarkerDetector | None = None, driver_radius: float = 1.3,
                 use_fog: bool = True):
        self.scene = scene
        self.p = params or VehicleParams()
        self.pp = ped or PedParams()
        self.persons = person_detector or NoPersonDetector()
        self.marker = marker or MarkerDetector()
        self.driver_radius = driver_radius
        self.use_fog = use_fog
        self._walkable = scene.walkable()
        self.calib = None
        self.version = 0  # cresce a ogni calibrazione: la UI ricarica la scena
        self.violations = 0
        self._over_since = None
        self._flag = False
        self.set_calibration(calib)

    # ---- calibrazione --------------------------------------------------------------------
    def set_calibration(self, calib) -> None:
        self.calib = calib
        self.version += 1
        self.oracle = Oracle(self.scene, self.p, self.pp, use_fog=self.use_fog)
        self.ptrack, self.vtrack = PersonTracker(), VehicleTracker()
        self.violations, self._over_since, self._flag = 0, None, False
        self.vis_poly, self.vis_mask, self.cam_xy = None, None, None
        if calib is not None:
            self.cam_xy = self._inside(calib.cam_xy)
            vis = visibility_polygon(self.cam_xy, self.scene, eye_h=calib.cam_h, target_h=1.0)
            self.vis_poly = vis.intersection(calib.footprint(self.scene.bounds))
            if self.vis_poly.is_empty:
                self.vis_poly = vis
            self.vis_mask = self.oracle.fog.mask_from_poly(self.vis_poly)

    def _inside(self, xy):
        pt = Point(xy)
        b = self.scene.bounds
        if b.contains(pt):
            return (float(xy[0]), float(xy[1]))
        q = nearest_points(b.exterior, pt)[0]
        c = b.centroid
        k = 0.05 / max(math.hypot(c.x - q.x, c.y - q.y), 1e-6)  # 5 cm verso l'interno
        return (q.x + (c.x - q.x) * k, q.y + (c.y - q.y) * k)

    # ---- elaborazione --------------------------------------------------------------------
    def _is_driver(self, xy, pose) -> bool:
        dx, dy = xy[0] - pose.xy[0], xy[1] - pose.xy[1]
        fwd = dx * math.cos(pose.heading) + dy * math.sin(pose.heading)
        return math.hypot(dx, dy) <= self.driver_radius and fwd <= 0.3

    def _path(self, pose):
        n = int(self.p.horizon / 0.25) + 1
        ss = np.arange(n) * 0.25
        d = np.array([math.cos(pose.heading), math.sin(pose.heading)])
        pts = np.array(pose.xy) + ss[:, None] * d
        ok = shapely.contains_xy(self._walkable, pts[:, 0], pts[:, 1])
        bad = np.where(~ok[1:])[0]
        cut = (int(bad[0]) + 1) if len(bad) else n
        cut = max(cut, 2)
        return ss[:cut], pts[:cut]

    def process(self, frame, t: float, frame_age: float = 0.0) -> dict:
        cal = self.calib
        state = {"t": round(t, 3), "calibrated": cal is not None, "version": self.version}
        if cal is None:
            return state
        fh, fw = frame.shape[:2]
        k = cal.image_size[0] / fw
        health = frame_health(frame)
        bounds_buf = self.scene.bounds.buffer(1.0)

        # muletto (sedia con marker)
        vd = self.marker.detect(frame)
        if vd:
            d = max(vd, key=lambda d: (d.box[2] - d.box[0]) * (d.box[3] - d.box[1]))
            c = cal.to_world(d.foot[0] * k, d.foot[1] * k, d.height)
            f = cal.to_world(d.fwd[0] * k, d.fwd[1] * k, d.height)
            if all(map(math.isfinite, (*c, *f))):
                self.vtrack.update(t, c, math.atan2(f[1] - c[1], f[0] - c[0]))
        pose = self.vtrack.pose(t)

        # persone
        meas, box_of, drivers = [], {}, []
        for d in self.persons.detect(frame):
            xy = cal.to_world(d.foot[0] * k, d.foot[1] * k, 0.0)
            if not all(map(math.isfinite, xy)) or not bounds_buf.contains(Point(xy)):
                continue
            if pose is not None and pose.tracked and self._is_driver(xy, pose):
                drivers.append([round(v, 1) for v in d.box])
                continue
            meas.append((xy[0], xy[1], d.conf))
            box_of[(xy[0], xy[1])] = d
        tracks = self.ptrack.update(t, meas)
        seen = {tr.id: (tr.xy, tr.speed) for tr in tracks}

        # motore
        decision = None
        if pose is not None and pose.tracked:
            ss, pts = self._path(pose)
            decision = self.oracle.step(t, seen, self.vis_mask, ss, pts, health, frame_age)
        else:
            self.oracle.fog.observe(t, self.vis_mask, {pid: pos for pid, (pos, _) in seen.items()})
            ss, pts = np.array([]), np.zeros((0, 2))

        # rispetto del comando: il muletto va oltre il limite per più di 0,5 s?
        if decision is not None and pose is not None:
            if pose.speed - decision.limit > 0.35:
                self._over_since = self._over_since if self._over_since is not None else t
                if t - self._over_since > 0.5 and not self._flag:
                    self.violations += 1
                    self._flag = True
            else:
                self._over_since, self._flag = None, False

        fog_grid = self.oracle.fog.state_map(t).astype(np.uint8)
        persons = []
        for tr in tracks:
            d = box_of.get(tr.xy)
            persons.append({"id": tr.id, "xy": [round(tr.xy[0], 2), round(tr.xy[1], 2)], "speed": round(tr.speed, 2),
                            "conf": round(float(tr.conf), 2),
                            "box": [round(v, 1) for v in d.box] if d is not None else None})
        state.update({
            "vehicle": None if pose is None else {"xy": [round(pose.xy[0], 2), round(pose.xy[1], 2)],
                                                 "heading": round(pose.heading, 3), "speed": round(pose.speed, 2),
                                                 "tracked": pose.tracked},
            "persons": persons, "drivers": drivers,
            "decision": None if decision is None else {
                "limit": round(decision.limit, 2), "level": decision.level, "level_name": LEVEL_NAMES[decision.level],
                "cause": decision.cause, "cause_it": CAUSE_IT.get(decision.cause, decision.cause)},
            "path": [[round(float(x), 2), round(float(y), 2)] for x, y in pts[::2]],
            "health": round(health, 2), "frame_age": round(frame_age, 3), "violations": self.violations,
            "fog": {"nx": int(fog_grid.shape[1]), "ny": int(fog_grid.shape[0]), "minx": self.oracle.fog.minx,
                    "miny": self.oracle.fog.miny, "res": self.oracle.fog.res,
                    "b64": base64.b64encode(fog_grid.tobytes()).decode("ascii")},
            "_fog": fog_grid,
        })
        return state

    def scene_info(self) -> dict:
        """Dati statici per la UI: confini, ostacoli, campo visivo e posizione della camera."""
        def ring(poly):
            return [[round(x, 3), round(y, 3)] for x, y in poly.exterior.coords]

        fov = None
        if self.vis_poly is not None:
            geom = self.vis_poly if self.vis_poly.geom_type == "Polygon" else max(self.vis_poly.geoms, key=lambda g: g.area)
            fov = ring(geom)
        return {
            "bounds": ring(self.scene.bounds),
            "occluders": [{"name": o.name, "height": o.height, "coords": ring(o.poly) if o.poly.geom_type == "Polygon" else []}
                          for o in self.scene.occluders],
            "fov": fov, "cam": None if self.calib is None else {"xy": list(self.cam_xy), "h": self.calib.cam_h},
            "calibrated": self.calib is not None, "version": self.version,
            "calib": None if self.calib is None else {"rms_m": round(self.calib.rms_m, 3), "image_size": list(self.calib.image_size)},
        }


def json_state(state: dict) -> dict:
    return {k: v for k, v in state.items() if not k.startswith("_")}
