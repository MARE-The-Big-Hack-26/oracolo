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
from concurrent.futures import ThreadPoolExecutor
import math

import cv2
import numpy as np
import shapely
from shapely.ops import nearest_points
from shapely.geometry import Point

from ..cab import CAUSE_IT
from ..engine import Oracle
from ..geometry import scene_shadows, visibility_polygon
from ..policy import LEVEL_NAMES, PedParams, VehicleParams
from .align import AlignmentMonitor
from .detectors import MarkerDetector, NoPersonDetector
from .tracker import PersonTracker, VehicleTracker
from .viz import overlay_polys


NOT_VERIFIED = {"status": "NON_VERIFICATO", "confidence": 1.0,
                "message": "Nessuna ancora a terra configurata: non verifico che il CAD coincida con il video."}


def frame_health(frame, gray=None) -> float:
    """1 = immagine buona; scende con luce estrema o immagine sfocata/coperta."""
    if gray is None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    sub = gray[::2, ::2] if gray.shape[0] >= 120 and gray.shape[1] >= 120 else gray
    mean = float(sub.mean())
    lap = float(cv2.Laplacian(sub, cv2.CV_64F).var())
    h = 0.4 if (mean < 25 or mean > 245) else 1.0
    return min(h, 0.5) if lap < 2.0 else h


class LivePipeline:
    def __init__(self, scene, calib=None, params: VehicleParams | None = None, ped: PedParams | None = None,
                 person_detector=None, marker: MarkerDetector | None = None, driver_radius: float = 1.3,
                 use_fog: bool = True, anchors=None):
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
        self._custom_cone = False
        self.cam_spec = {"xy": [4.5, 1.1], "h": 1.8, "dir": self._default_dir((4.5, 1.1)), "fov": 75.0}
        self._det_pool = ThreadPoolExecutor(max_workers=2)
        self.anchors, self.align = None, None
        self.set_anchors(anchors)
        self.set_calibration(calib)

    # ---- ancore e allineamento CAD-video -------------------------------------------------
    def set_anchors(self, anchors) -> None:
        """Ancore ArUco a terra (``align.AnchorSet``) o None. Senza ancore l'allineamento non è verificabile."""
        old = self.align
        self.anchors = anchors
        self.align = AlignmentMonitor(anchors) if anchors is not None else None
        if old is not None and self.align is not None:  # risalvare le coordinate non deve far perdere le ancore già viste
            self.align._hist = {i: v for i, v in old._hist.items() if i in anchors.anchors}

    def calibrate_from_anchors(self, t: float, camera=None):
        """(Calibration, info) dalle ancore viste di recente; ValueError se non basta. Non la applica."""
        if self.align is None:
            raise ValueError("Nessuna ancora configurata.")
        return self.align.calibrate(t, fallback=self.calib, camera=camera)

    # ---- calibrazione --------------------------------------------------------------------
    def _default_dir(self, xy) -> float:
        c = self.scene.bounds.centroid
        return round(math.degrees(math.atan2(c.y - xy[1], c.x - xy[0])), 1)

    def _cone_rad(self) -> tuple[float, float]:
        return math.radians(float(self.cam_spec.get("dir", 0.0))), math.radians(float(self.cam_spec.get("fov", 75.0))) / 2.0

    def set_scene(self, scene) -> None:
        self.scene = scene
        self._walkable = scene.walkable()
        self.set_calibration(self.calib)

    def _refresh_visibility(self) -> None:
        raw_xy = self.calib.cam_xy if self.calib is not None else self.cam_spec["xy"]
        cam_h = float(self.calib.cam_h if self.calib is not None else self.cam_spec["h"])
        self.cam_xy = self._inside(raw_xy)
        if not self._custom_cone and self.calib is None:
            self.cam_spec["dir"] = self._default_dir(self.cam_xy)
        heading, half_fov = self._cone_rad()
        if self.calib is not None and not self._custom_cone:
            vis = visibility_polygon(self.cam_xy, self.scene, eye_h=cam_h, target_h=0.0)
            inter = vis.intersection(self.calib.footprint(self.scene.bounds))
            if not inter.is_empty and (inter.covers(Point(self.cam_xy)) or inter.area > 0.5):
                vis = inter
        else:
            vis = visibility_polygon(self.cam_xy, self.scene, eye_h=cam_h, target_h=0.0, heading=heading, half_fov=half_fov)
        self.vis_poly = vis
        self.vis_mask = self.oracle.fog.mask_from_poly(self.vis_poly)
        prev_t = self.oracle.fog.t_prev
        self.oracle.fog.observe(0.0 if prev_t is None else prev_t, self.vis_mask, {})
        if prev_t is None:
            self.oracle.fog.t_prev = None
            self.oracle.fog.last_seen[self.oracle.fog.visible] = -np.inf

    def set_calibration(self, calib) -> None:
        self.calib = calib
        self.version += 1
        self.oracle = Oracle(self.scene, self.p, self.pp, use_fog=self.use_fog)
        self.ptrack, self.vtrack = PersonTracker(), VehicleTracker()
        self.violations, self._over_since, self._flag = 0, None, False
        if calib is not None:
            d_deg, f_deg = calib.view_cone()
            self._custom_cone = calib.cam_dir is not None
            self.cam_spec = {"xy": list(calib.cam_xy), "h": float(calib.cam_h), "dir": d_deg, "fov": f_deg}
        elif "dir" not in self.cam_spec:
            self.cam_spec["dir"], self.cam_spec["fov"] = self._default_dir(self.cam_spec["xy"]), 75.0
        self._refresh_visibility()

    def set_cam_spec(self, xy, h, dir_deg=None, fov_deg=None) -> None:
        x, y, h_val = float(xy[0]), float(xy[1]), float(h)
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(h_val) and h_val > 0.1):
            raise ValueError("Posizione o altezza camera non valida (h > 0.1 m)")
        d_val = self.cam_spec.get("dir", self._default_dir((x, y)))
        if dir_deg is not None and math.isfinite(float(dir_deg)):
            d_val, self._custom_cone = round(((float(dir_deg) + 180.0) % 360.0) - 180.0, 1), True
        elif not self._custom_cone:
            d_val = self._default_dir((x, y))
        f_val = float(self.cam_spec.get("fov", 75.0))
        if fov_deg is not None and math.isfinite(float(fov_deg)):
            f_val, self._custom_cone = round(max(20.0, min(360.0, float(fov_deg))), 1), True
        self.cam_spec = {"xy": [round(x, 3), round(y, 3)], "h": round(h_val, 3), "dir": d_val, "fov": f_val}
        if self.calib is not None:
            self.calib.cam_xy, self.calib.cam_h = (x, y), h_val
            if self._custom_cone:
                self.calib.cam_dir, self.calib.cam_fov = d_val, f_val
            self.set_calibration(self.calib)
        else:
            self.version += 1
            self._refresh_visibility()

    def _inside(self, xy):
        pt = Point(xy)
        b = self.scene.bounds
        if b.contains(pt):
            return (float(xy[0]), float(xy[1]))
        inner = b.buffer(-0.05)
        if not inner.is_empty:
            q = nearest_points(inner, pt)[0]
            return (float(q.x), float(q.y))
        rp = b.representative_point()
        return (float(rp.x), float(rp.y))

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
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        health = frame_health(frame, gray=gray)
        fut_p = self._det_pool.submit(self.persons.detect, frame)
        vd = self.marker.detect(frame, gray=gray) if isinstance(self.marker, MarkerDetector) else self.marker.detect(frame)
        raw_persons = fut_p.result()
        if self.align is not None:
            self.align.observe(t, self.marker.seen, (frame.shape[1], frame.shape[0]))
        if cal is None:
            state["align"] = self.align.pending(t) if self.align is not None else NOT_VERIFIED
            state["health"] = round(health, 2)
            state["frame_age"] = round(frame_age, 3)
            state["persons"] = [
                {"id": i + 1, "xy": None, "speed": 0.0, "conf": round(float(d.conf), 2),
                 "box": [round(v, 1) for v in d.box], "foot": [round(float(d.foot[0]), 1), round(float(d.foot[1]), 1)]}
                for i, d in enumerate(raw_persons)
            ]
            best_m = max(vd, key=lambda d: (d.box[2] - d.box[0]) * (d.box[3] - d.box[1])) if vd else None
            state["uncalibrated_marker"] = [round(v, 1) for v in best_m.box] if best_m else None
            return state
        fh, fw = frame.shape[:2]
        k = cal.image_size[0] / fw
        # CAD <-> video: con le ancore si riproietta e si confronta; se non coincidono health scende (0 = FERMA)
        al = self.align.evaluate(t, cal) if self.align is not None else NOT_VERIFIED
        health = min(health, al["confidence"])
        state["align"] = al
        bounds_buf = self.scene.bounds.buffer(1.5)

        # muletto (sedia con marker)
        if vd:
            d = max(vd, key=lambda d: (d.box[2] - d.box[0]) * (d.box[3] - d.box[1]))
            c = cal.to_world(d.foot[0] * k, d.foot[1] * k, d.height)
            f = cal.to_world(d.fwd[0] * k, d.fwd[1] * k, d.height)
            if all(map(math.isfinite, (*c, *f))):
                self.vtrack.update(t, c, math.atan2(f[1] - c[1], f[0] - c[0]))
        pose = self.vtrack.pose(t)

        # persone
        meas, box_of, drivers, out_of_bounds = [], {}, [], []
        for d in raw_persons:
            xy = cal.to_world(d.foot[0] * k, d.foot[1] * k, 0.0)
            if not all(map(math.isfinite, xy)):
                continue
            if not bounds_buf.contains(Point(xy)):
                out_of_bounds.append([round(v, 1) for v in d.box])
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

        fog_grid, fog_dict = self.fog_payload(t)
        persons = []
        for tr in tracks:
            d = box_of.get(tr.raw_xy) or box_of.get(tr.xy)
            persons.append({"id": tr.id, "xy": [round(tr.xy[0], 2), round(tr.xy[1], 2)], "speed": round(tr.speed, 2),
                            "vx": round(tr.vx, 2), "vy": round(tr.vy, 2),
                            "conf": round(float(tr.conf), 2),
                            "box": [round(v, 1) for v in d.box] if d is not None else None,
                            "foot": [round(float(d.foot[0]), 1), round(float(d.foot[1]), 1)] if d is not None else None})
        state.update({
            "vehicle": None if pose is None else {"xy": [round(pose.xy[0], 2), round(pose.xy[1], 2)],
                                                 "heading": round(pose.heading, 3), "speed": round(pose.speed, 2),
                                                 "tracked": pose.tracked},
            "persons": persons, "drivers": drivers, "out_of_bounds": out_of_bounds,
            "decision": None if decision is None else {
                "limit": round(decision.limit, 2), "level": decision.level, "level_name": LEVEL_NAMES[decision.level],
                "cause": decision.cause, "cause_it": CAUSE_IT.get(decision.cause, decision.cause)},
            "path": [[round(float(x), 2), round(float(y), 2)] for x, y in pts[::2]],
            "health": round(health, 2), "frame_age": round(frame_age, 3), "violations": self.violations,
            "fog": fog_dict, "_fog": fog_grid,
        })
        return state

    def fog_payload(self, t: float | None = None) -> tuple[np.ndarray, dict]:
        """Griglia fog (uint8) e payload JSON serializzabile per la UI."""
        ts = (self.oracle.fog.t_prev or 0.0) if t is None else t
        fog_grid = self.oracle.fog.state_map(ts).astype(np.uint8)
        return fog_grid, {
            "nx": int(fog_grid.shape[1]), "ny": int(fog_grid.shape[0]),
            "minx": self.oracle.fog.minx, "miny": self.oracle.fog.miny, "res": self.oracle.fog.res,
            "b64": base64.b64encode(fog_grid.tobytes()).decode("ascii"),
        }

    def scene_info(self) -> dict:
        """Dati statici per la UI: confini, ostacoli, campo visivo e posizione della camera."""
        def ring(poly):
            return [[round(x, 3), round(y, 3)] for x, y in poly.exterior.coords]

        fov, vp = None, self.vis_poly
        if vp is not None and not vp.is_empty:
            polys = [vp] if vp.geom_type == "Polygon" else [g for g in getattr(vp, "geoms", []) if g.geom_type == "Polygon" and not g.is_empty]
            if polys:
                fov = ring(max(polys, key=lambda g: g.area))
        cam_xy = list(self.cam_xy) if self.cam_xy is not None else list(self.cam_spec["xy"])
        cam_h = float(self.calib.cam_h if self.calib is not None else self.cam_spec["h"])
        heading, half_fov = self._cone_rad()
        return {
            "bounds": ring(self.scene.bounds),
            "occluders": [{"name": o.name, "height": o.height, "coords": ring(o.poly) if o.poly.geom_type == "Polygon" else []}
                          for o in self.scene.occluders],
            "fov": fov,
            "shadows": scene_shadows(cam_xy, self.scene, eye_h=cam_h, target_h=0.0, heading=heading, half_fov=half_fov),
            "cam": {"xy": cam_xy, "h": cam_h, "dir": float(self.cam_spec.get("dir", 0.0)), "fov": float(self.cam_spec.get("fov", 75.0))},
            "calibrated": self.calib is not None, "version": self.version,
            "anchors": None if self.anchors is None else self.anchors.to_dict(),
            "calib": None if self.calib is None else {
                "rms_m": round(self.calib.rms_m, 3),
                "rms_px": round(self.calib.rms_px, 2),
                "point_errors_px": self.calib.point_errors_px,
                "k1": round(self.calib.k1, 4),
                "fov_deg": self.calib.fov_deg(),
                "image_size": list(self.calib.image_size),
                "img_pts": self.calib.img_pts,
                "world_pts": self.calib.world_pts,
                "overlay": overlay_polys(self.calib, self.scene),
            },
        }


def json_state(state: dict) -> dict:
    return {k: v for k, v in state.items() if not k.startswith("_")}
