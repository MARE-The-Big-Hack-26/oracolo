"""Calibrazione camera fissa: omografia pavimento <-> immagine e posa 3D (PnP + distorsione).

Si cliccano almeno 4 punti riconoscibili nel video (a terra Z=0 o in quota Z>0, es. cima
di un mobile) e gli stessi punti sulla planimetria. Con punti 3D (o >=5 punti a terra)
il sistema stima automaticamente posizione/altezza camera, focale e distorsione radiale.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import MultiPoint, Polygon

from .calib_math import distort_norm_pts, refine_planar_k1, solve_pnp_auto, undistort


@dataclass
class Calibration:
    H: np.ndarray  # 3x3, pixel undistorted -> metri sul pavimento
    image_size: tuple  # (larghezza, altezza) del frame usato per calibrare
    cam_xy: tuple  # posizione della camera sulla planimetria (m)
    cam_h: float  # altezza della camera da terra (m)
    img_pts: list = field(default_factory=list)
    world_pts: list = field(default_factory=list)
    rms_m: float = 0.0  # errore medio di riproiezione a terra (m)
    K: np.ndarray | None = None
    rvec: np.ndarray | None = None
    tvec: np.ndarray | None = None
    k1: float = 0.0
    rms_px: float = 0.0
    point_errors_px: list = field(default_factory=list)
    cam_dir: float | None = None  # direzione orizzontale (gradi, -180..180); None = stimata da H
    cam_fov: float = 75.0  # apertura orizzontale iPhone (gradi)

    # ---- costruzione ---------------------------------------------------------------------
    @classmethod
    def from_pairs(cls, img_pts, world_pts, image_size, cam_xy, cam_h,
                   fit_distortion: bool = True, auto_cam: bool = False) -> "Calibration":
        img = np.asarray(img_pts, dtype=np.float64)
        wor3 = np.array([[float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0] for p in world_pts], dtype=np.float64)
        if len(img) < 4 or len(img) != len(wor3):
            raise ValueError("servono almeno 4 coppie di punti (immagine, mappa)")
        sz = (int(image_size[0]), int(image_size[1]))
        has_3d = bool(np.any(np.abs(wor3[:, 2]) > 1e-4))
        K, k1, rvec, tvec = None, 0.0, None, None
        cxy, ch = (float(cam_xy[0]), float(cam_xy[1])), float(cam_h)

        if has_3d:
            pnp = solve_pnp_auto(img, wor3, sz, fit_distortion)
            if pnp is None:
                raise ValueError("punti 3D non validi: posa camera non risolvibile")
            K, k1, rvec, tvec, cam, R = pnp
            H_w2i = K @ np.column_stack([R[:, 0], R[:, 1], tvec.ravel()])
            H = np.linalg.inv(H_w2i)
            cxy, ch = (float(cam[0]), float(cam[1])), float(cam[2])
        else:
            H, _ = cv2.findHomography(img, wor3[:, :2], 0)
            if H is None:
                raise ValueError("punti non validi: non formano una corrispondenza stabile (non allinearli)")
            if fit_distortion and len(img) >= 5:
                K, k1, H = refine_planar_k1(img, wor3[:, :2], sz, H)
            if auto_cam and len(img) >= 5:
                pnp = solve_pnp_auto(img, wor3, sz, fit_distortion)
                if pnp is not None and 0.3 <= pnp[4][2] <= 8.0:
                    cxy, ch = (float(pnp[4][0]), float(pnp[4][1])), float(pnp[4][2])

        cal = cls(H=H, image_size=sz, cam_xy=cxy, cam_h=ch, img_pts=img.tolist(),
                  world_pts=wor3.tolist(), K=K, rvec=rvec, tvec=tvec, k1=k1)
        proj_w = np.array([cal.to_world(u, v, height=z) for (u, v), z in zip(img, wor3[:, 2])])
        cal.rms_m = float(np.sqrt(np.mean(np.sum((proj_w - wor3[:, :2]) ** 2, axis=1))))
        proj_px = np.array([cal.to_image(x, y, z) for x, y, z in wor3])
        errs_px = np.linalg.norm(proj_px - img, axis=1)
        cal.point_errors_px = [round(float(e), 2) for e in errs_px]
        cal.rms_px = float(np.sqrt(np.mean(errs_px ** 2)))
        return cal

    # ---- trasformazioni ------------------------------------------------------------------
    def to_world(self, u: float, v: float, height: float = 0.0) -> tuple:
        """Pixel -> metri. ``height``: quota (m) del punto cliccato; 0 = a terra."""
        if self.K is not None and abs(self.k1) > 1e-7:
            uv = undistort(np.array([[u, v]], dtype=np.float64), self.K, self.k1)[0]
            u, v = float(uv[0]), float(uv[1])
        p = self.H @ np.array([u, v, 1.0])
        if abs(p[2]) < 1e-12:
            return (float("nan"), float("nan"))
        x, y = p[0] / p[2], p[1] / p[2]
        if height > 0 and self.cam_h > height * 1.05:
            k = (self.cam_h - height) / self.cam_h
            cx, cy = self.cam_xy
            x, y = cx + (x - cx) * k, cy + (y - cy) * k
        return (float(x), float(y))

    def to_image(self, x: float, y: float, z: float = 0.0) -> tuple:
        """Metri 3D -> pixel (nell'immagine di calibrazione)."""
        if self.K is not None and self.rvec is not None and self.tvec is not None:
            dist = np.array([self.k1, 0.0, 0.0, 0.0], dtype=np.float64) if abs(self.k1) > 1e-7 else None
            proj, _ = cv2.projectPoints(np.array([[[float(x), float(y), float(z)]]], dtype=np.float64),
                                        self.rvec, self.tvec, self.K, dist)
            return (float(proj[0, 0, 0]), float(proj[0, 0, 1]))
        if z > 0.0 and self.cam_h > 0.2:
            zz = min(float(z), self.cam_h * 0.85)
            s = self.cam_h / (self.cam_h - zz)
            cx, cy = self.cam_xy
            x, y = cx + (x - cx) * s, cy + (y - cy) * s
        p = np.linalg.inv(self.H) @ np.array([x, y, 1.0])
        uv = np.array([[p[0] / p[2], p[1] / p[2]]], dtype=np.float64)
        if self.K is not None and abs(self.k1) > 1e-7:
            uv = distort_norm_pts(uv, self.K, self.k1)
        return (float(uv[0, 0]), float(uv[0, 1]))

    def project_visible(self, x: float, y: float, z: float = 0.0) -> tuple[float, float] | None:
        """Proietta un punto 3D se davanti alla camera e vicino al frame."""
        if self.K is not None and self.rvec is not None and self.tvec is not None:
            R, _ = cv2.Rodrigues(self.rvec)
            z_cam = float((R @ np.array([float(x), float(y), float(z)], dtype=np.float64) + self.tvec.ravel())[2])
            if z_cam <= 0.15:
                return None
        else:
            px, py = float(x), float(y)
            if z > 0.0 and self.cam_h > 0.2:
                zz = min(float(z), self.cam_h * 0.85)
                s = self.cam_h / (self.cam_h - zz)
                cx, cy = self.cam_xy
                px, py = cx + (px - cx) * s, cy + (py - cy) * s
            Hinv = np.linalg.inv(self.H)
            if self.world_pts:
                ref = np.mean(np.asarray(self.world_pts, dtype=np.float64)[:, :2], axis=0)
                w_ref = float((Hinv @ np.array([ref[0], ref[1], 1.0]))[2])
                if abs(w_ref) > 1e-12:
                    Hinv = Hinv / w_ref
            p = Hinv @ np.array([px, py, 1.0])
            if p[2] <= 0.05:
                return None
        u, v = self.to_image(x, y, z)
        w, h = self.image_size
        if not (math.isfinite(u) and math.isfinite(v)):
            return None
        if -80.0 <= u <= w + 80.0 and -80.0 <= v <= h + 80.0:
            return (round(u, 1), round(v, 1))
        return None

    def fov_deg(self) -> float | None:
        if self.K is None or self.K[0, 0] <= 0:
            return None
        return round(math.degrees(2.0 * math.atan(self.image_size[0] / (2.0 * self.K[0, 0]))), 1)

    def view_cone(self) -> tuple[float, float]:
        """Ritorna (direzione_gradi, fov_gradi) stimati dall'omografia o impostati manualmente."""
        fov = float(np.clip(self.cam_fov, 20.0, 360.0))
        if self.cam_dir is not None and np.isfinite(self.cam_dir):
            return (round(float(((self.cam_dir + 180.0) % 360.0) - 180.0), 1), round(fov, 1))
        w, h = self.image_size
        cx, cy = self.cam_xy
        ref = (self.H @ np.array([w / 2.0, h - 1.0, 1.0]))[2]
        sign = 1.0 if ref >= 0 else -1.0

        def _ground(u: float, v: float):
            if self.K is not None and abs(self.k1) > 1e-7:
                uv = undistort(np.array([[u, v]], dtype=np.float64), self.K, self.k1)[0]
                u, v = float(uv[0]), float(uv[1])
            p = self.H @ np.array([u, v, 1.0])
            return (float(p[0] / p[2]), float(p[1] / p[2])) if p[2] * sign > 1e-9 else None

        c_pt = _ground(w * 0.5, h * 0.8)
        if c_pt is None and self.world_pts:
            arr = np.asarray(self.world_pts, dtype=np.float64)
            c_pt = (float(arr[:, 0].mean()), float(arr[:, 1].mean()))
        dir_deg = float(np.degrees(np.arctan2(c_pt[1] - cy, c_pt[0] - cx))) if c_pt is not None else 0.0
        l_pt, r_pt = _ground(0.0, h * 0.85), _ground(float(w), h * 0.85)
        if self.cam_fov == 75.0:
            kd = self.fov_deg()
            if kd is not None:
                fov = float(np.clip(kd, 35.0, 120.0))
            elif l_pt is not None and r_pt is not None:
                a_l, a_r = np.arctan2(l_pt[1] - cy, l_pt[0] - cx), np.arctan2(r_pt[1] - cy, r_pt[0] - cx)
                span = abs(((a_l - a_r + np.pi) % (2 * np.pi)) - np.pi)
                if np.degrees(span) >= 25.0:
                    fov = float(np.clip(np.degrees(span), 35.0, 120.0))
        return (round(dir_deg, 1), round(fov, 1))

    def footprint(self, bounds: Polygon, n: int = 40) -> Polygon:
        """Parte del pavimento inquadrata dalla camera, limitata ai confini della stanza."""
        w, h = self.image_size
        t = np.linspace(0, 1, n)
        border = np.vstack([
            np.column_stack([t * w, np.zeros(n)]), np.column_stack([np.full(n, w), t * h]),
            np.column_stack([(1 - t) * w, np.full(n, h)]), np.column_stack([np.zeros(n), (1 - t) * h]),
        ])
        if self.K is not None and abs(self.k1) > 1e-7:
            border = undistort(border, self.K, self.k1)
        ref = (self.H @ np.array([w / 2, h - 1.0, 1.0]))[2]
        sign = 1.0 if ref >= 0 else -1.0
        pts = []
        diag = float(np.hypot(*np.ptp(np.asarray(bounds.exterior.coords), axis=0)))
        cx, cy = self.cam_xy
        for u, v in border:
            p = self.H @ np.array([u, v, 1.0])
            if p[2] * sign <= 1e-9:
                continue
            x, y = p[0] / p[2], p[1] / p[2]
            r = np.hypot(x - cx, y - cy)
            if r > 5 * diag:
                x, y = cx + (x - cx) * 5 * diag / r, cy + (y - cy) * 5 * diag / r
            pts.append((x, y))
        if len(pts) < 3:
            return bounds
        hull = MultiPoint(pts).convex_hull
        out = hull.intersection(bounds) if hull.geom_type == "Polygon" else bounds
        return out if (out.geom_type in ("Polygon", "MultiPolygon") and not out.is_empty) else bounds

    # ---- salvataggio ---------------------------------------------------------------------
    def to_dict(self) -> dict:
        d = {
            "H": np.asarray(self.H).tolist(), "image_size": list(self.image_size),
            "cam_xy": list(self.cam_xy), "cam_h": self.cam_h,
            "img_pts": self.img_pts, "world_pts": self.world_pts,
            "rms_m": self.rms_m, "k1": self.k1, "rms_px": self.rms_px,
            "point_errors_px": self.point_errors_px, "cam_dir": self.cam_dir, "cam_fov": self.cam_fov,
        }
        if self.K is not None:
            d["K"] = np.asarray(self.K).tolist()
        if self.rvec is not None and self.tvec is not None:
            d["rvec"] = np.asarray(self.rvec).ravel().tolist()
            d["tvec"] = np.asarray(self.tvec).ravel().tolist()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Calibration":
        K = np.array(d["K"], dtype=np.float64) if d.get("K") is not None else None
        rvec = np.array(d["rvec"], dtype=np.float64).reshape(3, 1) if d.get("rvec") is not None else None
        tvec = np.array(d["tvec"], dtype=np.float64).reshape(3, 1) if d.get("tvec") is not None else None
        return cls(
            H=np.array(d["H"], dtype=np.float64), image_size=tuple(d["image_size"]),
            cam_xy=tuple(d["cam_xy"]), cam_h=float(d["cam_h"]),
            img_pts=d.get("img_pts", []), world_pts=d.get("world_pts", []),
            rms_m=float(d.get("rms_m", 0.0)), K=K, rvec=rvec, tvec=tvec,
            k1=float(d.get("k1", 0.0)), rms_px=float(d.get("rms_px", 0.0)),
            point_errors_px=d.get("point_errors_px", []),
            cam_dir=d.get("cam_dir"), cam_fov=float(d.get("cam_fov", 75.0)),
        )

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path) -> "Calibration":
        return cls.from_dict(json.loads(Path(path).read_text()))


def overlay_vertices(calib: Calibration, scene) -> list[dict]:
    """Vertici 3D del CAD proiettati sul frame per il drag diretto in /calibrate."""
    if calib is None or scene is None:
        return []
    raw = [(float(p[0]), float(p[1]), 0.0, "Muro (terra)") for p in list(scene.bounds.exterior.coords)[:-1]]
    for o in getattr(scene, "occluders", []):
        if o.poly.geom_type != "Polygon":
            continue
        nm = re.sub(r"(#\d+|_H[\d.,]+)$", "", o.name or "", flags=re.I).lower() or "ostacolo"
        pts = list(o.poly.exterior.coords)[:-1]
        for p in pts:
            raw.append((float(p[0]), float(p[1]), 0.0, f"{nm} (terra)"))
            if o.height > 0.05:
                raw.append((float(p[0]), float(p[1]), round(float(o.height), 3), f"{nm} (cima {o.height:.2f}m)"))
    seen, out = set(), []
    for x, y, z, label in raw:
        key = (round(x, 3), round(y, 3), round(z, 3))
        if key in seen:
            continue
        seen.add(key)
        uv = calib.project_visible(x, y, z)
        if uv is not None:
            out.append({"u": uv[0], "v": uv[1], "x": key[0], "y": key[1], "z": key[2], "label": label})
    return out
