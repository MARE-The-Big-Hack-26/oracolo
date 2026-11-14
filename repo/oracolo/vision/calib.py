"""Calibrazione camera fissa: omografia pavimento <-> immagine.

Si cliccano almeno 4 punti A TERRA riconoscibili nel video e gli stessi punti sulla
planimetria (angoli della stanza, base di un mobile). Da quelle coppie si ricava
l'omografia H (pixel -> metri sul pavimento). Si indica anche dove sta la camera sulla
mappa e a che altezza: servono a (1) correggere la parallasse di oggetti sopraelevati
(il marker sul sedile sta a ~0,45 m, non a terra) e (2) calcolare cosa vede la camera.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import MultiPoint, Polygon


@dataclass
class Calibration:
    H: np.ndarray  # 3x3, pixel -> metri sul pavimento
    image_size: tuple  # (larghezza, altezza) del frame usato per calibrare
    cam_xy: tuple  # posizione della camera sulla planimetria (m)
    cam_h: float  # altezza della camera da terra (m)
    img_pts: list = field(default_factory=list)
    world_pts: list = field(default_factory=list)
    rms_m: float = 0.0  # errore medio di riproiezione sui punti cliccati (m)

    # ---- costruzione ---------------------------------------------------------------------
    @classmethod
    def from_pairs(cls, img_pts, world_pts, image_size, cam_xy, cam_h) -> "Calibration":
        img = np.asarray(img_pts, dtype=np.float64)
        wor = np.asarray(world_pts, dtype=np.float64)
        if len(img) < 4 or len(img) != len(wor):
            raise ValueError("servono almeno 4 coppie di punti (immagine, mappa)")
        H, _ = cv2.findHomography(img, wor, 0)
        if H is None:
            raise ValueError("punti non validi: non formano una corrispondenza stabile (non allinearli)")
        cal = cls(H=H, image_size=(int(image_size[0]), int(image_size[1])), cam_xy=(float(cam_xy[0]), float(cam_xy[1])),
                  cam_h=float(cam_h), img_pts=img.tolist(), world_pts=wor.tolist())
        proj = np.array([cal.to_world(u, v) for u, v in img])
        cal.rms_m = float(np.sqrt(np.mean(np.sum((proj - wor) ** 2, axis=1))))
        return cal

    # ---- trasformazioni ------------------------------------------------------------------
    def to_world(self, u: float, v: float, height: float = 0.0) -> tuple:
        """Pixel -> metri. ``height``: quota (m) del punto cliccato; 0 = a terra.

        Un punto in quota proietta sul pavimento più lontano dalla camera di quello reale:
        il raggio dalla camera (altezza H) lo incontra a distanza d*H/(H-h). Si corregge
        riportando il punto verso la camera di (H-h)/H.
        """
        p = self.H @ np.array([u, v, 1.0])
        if abs(p[2]) < 1e-12:
            return (float("nan"), float("nan"))
        x, y = p[0] / p[2], p[1] / p[2]
        if height > 0 and self.cam_h > height * 1.05:
            k = (self.cam_h - height) / self.cam_h
            cx, cy = self.cam_xy
            x, y = cx + (x - cx) * k, cy + (y - cy) * k
        return (float(x), float(y))

    def to_image(self, x: float, y: float) -> tuple:
        """Metri sul pavimento -> pixel (nell'immagine di calibrazione)."""
        p = np.linalg.inv(self.H) @ np.array([x, y, 1.0])
        return (float(p[0] / p[2]), float(p[1] / p[2]))

    def footprint(self, bounds: Polygon, n: int = 40) -> Polygon:
        """Parte del pavimento inquadrata dalla camera, limitata ai confini della stanza."""
        w, h = self.image_size
        t = np.linspace(0, 1, n)
        border = np.vstack([
            np.column_stack([t * w, np.zeros(n)]), np.column_stack([np.full(n, w), t * h]),
            np.column_stack([(1 - t) * w, np.full(n, h)]), np.column_stack([np.zeros(n), (1 - t) * h]),
        ])
        ref = (self.H @ np.array([w / 2, h - 1.0, 1.0]))[2]
        sign = 1.0 if ref >= 0 else -1.0
        pts = []
        diag = float(np.hypot(*np.ptp(np.asarray(bounds.exterior.coords), axis=0)))
        cx, cy = self.cam_xy
        for u, v in border:
            p = self.H @ np.array([u, v, 1.0])
            if p[2] * sign <= 1e-9:
                continue  # sopra l'orizzonte: non incontra il pavimento
            x, y = p[0] / p[2], p[1] / p[2]
            r = np.hypot(x - cx, y - cy)
            if r > 5 * diag:  # punti quasi all'orizzonte: si tronca mantenendo la direzione
                x, y = cx + (x - cx) * 5 * diag / r, cy + (y - cy) * 5 * diag / r
            pts.append((x, y))
        if len(pts) < 3:
            return bounds
        hull = MultiPoint(pts).convex_hull
        out = hull.intersection(bounds) if hull.geom_type == "Polygon" else bounds
        return out if (out.geom_type == "Polygon" and not out.is_empty) else bounds

    # ---- salvataggio ---------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {"H": np.asarray(self.H).tolist(), "image_size": list(self.image_size), "cam_xy": list(self.cam_xy),
                "cam_h": self.cam_h, "img_pts": self.img_pts, "world_pts": self.world_pts, "rms_m": self.rms_m}

    @classmethod
    def from_dict(cls, d: dict) -> "Calibration":
        return cls(H=np.array(d["H"], dtype=np.float64), image_size=tuple(d["image_size"]), cam_xy=tuple(d["cam_xy"]),
                   cam_h=float(d["cam_h"]), img_pts=d.get("img_pts", []), world_pts=d.get("world_pts", []),
                   rms_m=float(d.get("rms_m", 0.0)))

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path) -> "Calibration":
        return cls.from_dict(json.loads(Path(path).read_text()))
