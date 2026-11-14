"""Allineamento CAD <-> video con ancore ArUco a terra (id 10-17, DICT_4X4_50).

Si incollano 3-4 marker a terra in punti NOTI del CAD (coordinate in metri nella planimetria
normalizzata, origine (0,0)). Servono a due cose:

1. calibrazione automatica, senza clic sul video: dai 4 angoli di ogni marker visibile si ricava
   l'omografia pixel -> metri (minimi quadrati su 12-16 punti, quindi l'errore residuo è una misura
   vera). La posizione della camera (x, y, altezza) NON si stima: si indica una volta (JSON o pannello)
   oppure si riusa quella della calibrazione precedente (una stima da un solo piano è inaffidabile:
   misurata, sbaglia di decine di cm anche con 0,5 px di rumore);
2. controllo continuo: con la calibrazione attiva si riproiettano le ancore viste e si confronta con
   le coordinate attese. Errore piccolo = CAD e video coincidono; errore grande = camera spostata o
   ruotata (o coordinate sbagliate) -> la mappa non è più affidabile -> ``NON_COINCIDE`` -> health 0 -> FERMA.

Stati: OK (>=3 ancore viste, errore <= OK_RMS_M) | DEGRADATO (ancore coperte o errore medio) |
NON_COINCIDE (errore > BAD_RMS_M per alcuni frame di fila).
Le SOGLIE sono ipotesi non ancora tarate su video reale. Questo controllo vede solo le ancore: non
verifica che il resto del CAD (scaffali, muri) sia disegnato giusto. Prototipo, non un sistema certificato.

Convenzione di posa: il lato SUPERIORE del marker (quello in alto quando il marker è letto dritto)
punta verso +Y della planimetria; ``rot_deg`` ruota in senso antiorario.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .calib import Calibration

MIN_ANCHORS = 3          # ancore viste per poter dire OK / calibrare
WINDOW_S = 2.0           # le ancore viste negli ultimi 2 s contano (coperture brevi non fanno scattare nulla)
OK_RMS_M = 0.10          # errore medio sugli angoli delle ancore: sotto = coincidono (IPOTESI)
BAD_RMS_M = 0.25         # sopra = non coincidono (IPOTESI)
BAD_FRAMES = 3           # frame consecutivi sopra BAD_RMS_M prima di dichiarare NON_COINCIDE
CONF = {"OK": 1.0, "DEGRADATO": 0.6, "NON_COINCIDE": 0.0}  # health: <0.3 il motore ferma, 0.3-0.7 rallenta


# --------------------------------------------------------------------------------------------------
# configurazione delle ancore
# --------------------------------------------------------------------------------------------------
@dataclass
class AnchorSet:
    size_m: float                                   # lato del quadrato NERO del marker
    anchors: dict = field(default_factory=dict)     # id -> (x, y, rot_deg): centro in metri nella planimetria
    camera: tuple | None = None                     # (x, y, h) misurata, facoltativa

    def corners_world(self, mid: int) -> np.ndarray:
        """Angoli attesi (alto-sx, alto-dx, basso-dx, basso-sx) in metri, come li ordina ArUco."""
        x, y, rot = self.anchors[mid]
        h = self.size_m / 2
        a = math.radians(rot)
        ca, sa = math.cos(a), math.sin(a)
        return np.array([[x + ca * px - sa * py, y + sa * px + ca * py] for px, py in ((-h, h), (h, h), (h, -h), (-h, -h))])

    @classmethod
    def from_dict(cls, d: dict, forbidden_ids=(0,)) -> "AnchorSet":
        try:
            size = float(d.get("size_m", 0.20))
            raw = d["anchors"]
            items = raw.items() if isinstance(raw, dict) else [(a["id"], a) for a in raw]
            anchors = {}
            for key, v in items:
                mid = int(key)
                if isinstance(v, (list, tuple)):
                    x, y, rot = float(v[0]), float(v[1]), float(v[2]) if len(v) > 2 else 0.0
                else:
                    x, y, rot = float(v["x"]), float(v["y"]), float(v.get("rot_deg", 0.0))
                if mid in anchors:
                    raise ValueError(f"ancora {mid} ripetuta")
                anchors[mid] = (x, y, rot)
            cam = d.get("camera")
            camera = None if not cam else (float(cam["x"]), float(cam["y"]), float(cam["h"]))
        except (KeyError, TypeError, IndexError) as e:
            raise ValueError(f"JSON ancore non valido (atteso size_m e anchors con id -> x, y): {e!r}") from None
        if not (0.03 <= size <= 2.0):
            raise ValueError(f"lato del marker {size} m non plausibile (0,03-2 m)")
        if len(anchors) < MIN_ANCHORS:
            raise ValueError(f"servono almeno {MIN_ANCHORS} ancore (meglio 4-8: id 10-17)")
        for mid in anchors:
            if mid in forbidden_ids or not (0 <= mid < 50):
                raise ValueError(f"id {mid} non valido (DICT_4X4_50; 0 è il muletto): usare 10-17")
        if camera is not None and not (0.2 <= camera[2] <= 20):
            raise ValueError("altezza camera non plausibile")
        a = cls(size, anchors, camera)
        pts = np.array([[v[0], v[1]] for v in anchors.values()])
        if _collinearity(pts) < 0.05:
            raise ValueError("le ancore sono (quasi) allineate: mettile in punti sparsi, non su una riga")
        return a

    def to_dict(self) -> dict:
        d = {"size_m": self.size_m,
             "anchors": {str(i): {"x": v[0], "y": v[1], "rot_deg": v[2]} for i, v in sorted(self.anchors.items())}}
        if self.camera:
            d["camera"] = {"x": self.camera[0], "y": self.camera[1], "h": self.camera[2]}
        return d

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path) -> "AnchorSet":
        return cls.from_dict(json.loads(Path(path).read_text()))

    def outside(self, bounds) -> list:
        """Id delle ancore il cui centro cade fuori dal perimetro (probabile errore di coordinate)."""
        from shapely.geometry import Point  # noqa: PLC0415
        return [i for i, v in self.anchors.items() if not bounds.buffer(0.05).contains(Point(v[0], v[1]))]


def _collinearity(pts: np.ndarray) -> float:
    """~0 se i punti stanno su una retta, ~0.3-1 se sono sparsi (rapporto tra i due assi principali)."""
    c = pts - pts.mean(axis=0)
    s = np.linalg.svd(c, compute_uv=False)
    return float(s[-1] / s[0]) if s[0] > 1e-9 else 0.0


# --------------------------------------------------------------------------------------------------
# geometria
# --------------------------------------------------------------------------------------------------
def _to_world(H: np.ndarray, pts: np.ndarray) -> np.ndarray:
    p = np.hstack([pts, np.ones((len(pts), 1))]) @ H.T
    with np.errstate(divide="ignore", invalid="ignore"):
        return p[:, :2] / p[:, 2:3]


def reprojection_rms(H: np.ndarray, corners_by_id: dict, anchors: AnchorSet) -> tuple:
    """(rms in metri sugli angoli, errore per id). ``corners_by_id``: pixel nello spazio di H."""
    per, sq, n = {}, 0.0, 0
    for mid, c in corners_by_id.items():
        w = _to_world(H, np.asarray(c, float))
        e = np.linalg.norm(w - anchors.corners_world(mid), axis=1)
        e = np.where(np.isfinite(e), e, 1e3)
        per[mid] = float(np.sqrt(np.mean(e ** 2)))
        sq += float(np.sum(e ** 2))
        n += len(e)
    return (math.sqrt(sq / n) if n else float("inf")), per


# --------------------------------------------------------------------------------------------------
# monitor
# --------------------------------------------------------------------------------------------------
class AlignmentMonitor:
    def __init__(self, anchors: AnchorSet, window: float = WINDOW_S):
        self.anchors = anchors
        self.window = window
        self._hist = {}      # id -> (t, angoli 4x2 in pixel del frame, (larghezza, altezza) del frame)
        self._bad = 0

    def observe(self, t: float, seen: dict, frame_size) -> None:
        for mid, c in (seen or {}).items():
            if mid in self.anchors.anchors:
                self._hist[mid] = (t, np.asarray(c, float), (int(frame_size[0]), int(frame_size[1])))

    def _recent(self, t: float) -> dict:
        self._hist = {i: v for i, v in self._hist.items() if t - v[0] <= self.window}
        return self._hist

    def pending(self, t: float) -> dict:
        """Stato prima della calibrazione: quante ancore si vedono e se bastano per calibrare."""
        n = len(self._recent(t))
        return {"status": "SENZA_CALIBRAZIONE", "n_seen": n, "n_anchors": len(self.anchors.anchors),
                "ids_seen": sorted(self._hist), "ready": n >= MIN_ANCHORS, "confidence": 1.0,
                "message": (f"Ancore viste: {n}/{len(self.anchors.anchors)}. " +
                            ("Premi «Calibra da ancore» (o calibra a mano)." if n >= MIN_ANCHORS else
                             f"Ne servono almeno {MIN_ANCHORS} visibili."))}

    def evaluate(self, t: float, cal: Calibration) -> dict:
        rec = self._recent(t)
        n_all = len(self.anchors.anchors)
        base = {"n_seen": len(rec), "n_anchors": n_all, "ids_seen": sorted(rec), "rms_m": None}
        if not rec:
            self._bad = 0
            return {**base, "status": "DEGRADATO", "confidence": CONF["DEGRADATO"],
                    "message": f"Ancore non visibili (0/{n_all}): non posso verificare che il CAD coincida con il video."}
        corners = {i: v[1] * (cal.image_size[0] / v[2][0]) for i, v in rec.items()}
        rms, per = reprojection_rms(cal.H, corners, self.anchors)
        base.update({"rms_m": round(rms, 3), "per_anchor_m": {str(i): round(e, 3) for i, e in per.items()}})
        if rms > BAD_RMS_M:
            self._bad += 1
            if self._bad >= BAD_FRAMES:
                return {**base, "status": "NON_COINCIDE", "confidence": CONF["NON_COINCIDE"],
                        "message": f"CAD non coincide con il video: le ancore risultano spostate di {rms * 100:.0f} cm "
                                   "(camera mossa o coordinate sbagliate). Ricalibra."}
        else:
            self._bad = 0
        if len(rec) < MIN_ANCHORS:
            return {**base, "status": "DEGRADATO", "confidence": CONF["DEGRADATO"],
                    "message": f"Ancore coperte: ne vedo {len(rec)}/{n_all}, ne servono {MIN_ANCHORS} per verificare."}
        if rms > OK_RMS_M:
            return {**base, "status": "DEGRADATO", "confidence": CONF["DEGRADATO"],
                    "message": f"Allineamento incerto: errore sulle ancore {rms * 100:.0f} cm."}
        return {**base, "status": "OK", "confidence": CONF["OK"],
                "message": f"CAD e video coincidono (errore sulle ancore {rms * 100:.1f} cm, {len(rec)}/{n_all} viste)."}

    # ---- calibrazione automatica -------------------------------------------------------------------
    def calibrate(self, t: float, fallback: Calibration | None = None, camera: tuple | None = None) -> tuple:
        """(Calibration, info) dalle ancore viste negli ultimi secondi. ValueError con messaggio chiaro se non si può.
        ``camera`` = (x, y, h) indicata dall'utente; altrimenti quella del JSON; altrimenti quella di ``fallback``."""
        rec = self._recent(t)
        n_all = len(self.anchors.anchors)
        if len(rec) < MIN_ANCHORS:
            raise ValueError(f"Vedo {len(rec)} ancore su {n_all}: ne servono almeno {MIN_ANCHORS} visibili e ferme.")
        sizes = {v[2] for v in rec.values()}
        if len(sizes) != 1:
            raise ValueError("Le ancore sono state viste con risoluzioni diverse del video: riprova.")
        fw, fh = next(iter(sizes))
        ids = sorted(rec)
        centers = np.array([[self.anchors.anchors[i][0], self.anchors.anchors[i][1]] for i in ids])
        if _collinearity(centers) < 0.05:
            raise ValueError("Le ancore visibili sono quasi allineate: serve che se ne vedano almeno 3 in punti sparsi.")
        img = np.vstack([rec[i][1] for i in ids])
        wor = np.vstack([self.anchors.corners_world(i) for i in ids])
        if camera is not None:
            cam, src = camera, "indicata nel pannello"
        elif self.anchors.camera:
            cam, src = self.anchors.camera, "indicata nel JSON delle ancore"
        elif fallback is not None:
            cam, src = (fallback.cam_xy[0], fallback.cam_xy[1], fallback.cam_h), "dalla calibrazione precedente"
        else:
            raise ValueError("Indica dove sta la camera (x, y in metri sulla planimetria e altezza da terra): "
                             "non si può ricavare dalle ancore in modo affidabile.")
        if not (0.2 <= cam[2] <= 20):
            raise ValueError(f"Altezza della camera {cam[2]} m non plausibile.")
        cal = Calibration.from_pairs(img.tolist(), wor.tolist(), (fw, fh), (cam[0], cam[1]), cam[2])
        info = {"ids": ids, "rms_m": round(cal.rms_m, 4), "cam": [round(cam[0], 3), round(cam[1], 3), round(cam[2], 3)],
                "cam_source": src}
        if cal.rms_m > BAD_RMS_M:
            raise ValueError(f"Le ancore non sono coerenti con le coordinate (errore {cal.rms_m * 100:.0f} cm): "
                             "controlla coordinate, lato del marker e orientamento.")
        return cal, info
