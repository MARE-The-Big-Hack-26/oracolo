"""Rilevatori: marker ArUco (il muletto) e persone.

Il muletto simulato è una sedia con un marker ArUco sopra: identità e orientamento certi,
anche con poca luce. Le persone si rilevano con un modello: ``hog`` (OpenCV, nessun
download, qualità media: serve per provare) oppure ``rfdetr`` (RF-DETR, Apache 2.0,
consigliato; ``pip install rfdetr``). Il motore non dipende da nessuno dei due.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Det:
    kind: str  # "person" | "vehicle"
    box: tuple  # x1, y1, x2, y2 (pixel)
    conf: float
    foot: tuple  # punto di appoggio a terra (persone) o centro del marker (muletto), pixel
    height: float = 0.0  # quota (m) di ``foot``: 0 = a terra
    fwd: tuple | None = None  # muletto: punto davanti al centro del marker (pixel)
    truncated: bool = False  # persona tagliata dal bordo inferiore: i piedi non si vedono


class MarkerDetector:
    """Marker ArUco del muletto. Il lato SUPERIORE del marker deve guardare il davanti della sedia."""

    def __init__(self, marker_id: int = 0, dictionary: str = "DICT_4X4_50", height: float = 0.45):
        d = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary))
        self._det = cv2.aruco.ArucoDetector(d, cv2.aruco.DetectorParameters())
        self.marker_id = marker_id
        self.height = height

    def detect(self, frame) -> list:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        corners, ids, _ = self._det.detectMarkers(gray)
        out = []
        if ids is None:
            return out
        for c, i in zip(corners, ids.flatten()):
            if int(i) != self.marker_id:
                continue
            c = c[0].astype(float)  # 4x2: alto-sx, alto-dx, basso-dx, basso-sx
            center = c.mean(axis=0)
            fwd = center + 0.5 * ((c[0] + c[1]) / 2 - (c[2] + c[3]) / 2)
            x1, y1 = c.min(axis=0)
            x2, y2 = c.max(axis=0)
            out.append(Det("vehicle", (x1, y1, x2, y2), 1.0, (float(center[0]), float(center[1])), self.height,
                           (float(fwd[0]), float(fwd[1]))))
        return out


class HogPersonDetector:
    """Rilevatore persone di base (HOG + SVM di OpenCV): nessun file da scaricare."""

    def __init__(self, width: int = 640, min_weight: float = 0.6):
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        self.width, self.min_weight = width, min_weight

    def detect(self, frame) -> list:
        s = min(1.0, self.width / frame.shape[1])
        small = cv2.resize(frame, None, fx=s, fy=s) if s < 1.0 else frame
        rects, weights = self.hog.detectMultiScale(small, winStride=(8, 8), padding=(8, 8), scale=1.05)
        out = []
        if len(rects) == 0:
            return out
        boxes = [[int(x), int(y), int(w), int(h)] for x, y, w, h in rects]
        keep = cv2.dnn.NMSBoxes(boxes, [float(w) for w in np.ravel(weights)], self.min_weight, 0.4)
        H = frame.shape[0]
        for k in np.ravel(keep):
            x, y, w, h = boxes[int(k)]
            x1, y1, x2, y2 = x / s, y / s, (x + w) / s, (y + h) / s
            out.append(Det("person", (x1, y1, x2, y2), float(np.ravel(weights)[int(k)]),
                           ((x1 + x2) / 2, y2), 0.0, None, y2 >= H - 3))
        return out


class RfDetrPersonDetector:
    """RF-DETR (Apache 2.0). Richiede ``pip install rfdetr`` (porta con sé PyTorch)."""

    def __init__(self, size: str = "nano", threshold: float = 0.5):
        import rfdetr  # noqa: PLC0415 (import tardivo: dipendenza opzionale)

        cls = {"nano": "RFDETRNano", "small": "RFDETRSmall", "base": "RFDETRBase"}[size]
        self.model = getattr(rfdetr, cls)()
        self.threshold = threshold
        try:
            self.model.optimize_for_inference()
        except Exception:  # noqa: BLE001 (non tutte le versioni/piattaforme lo supportano)
            pass

    def detect(self, frame) -> list:
        from PIL import Image  # noqa: PLC0415

        rgb = Image.fromarray(frame[:, :, ::-1])
        dets = self.model.predict(rgb, threshold=self.threshold)
        H = frame.shape[0]
        out = []
        for xyxy, cid, conf in zip(dets.xyxy, dets.class_id, dets.confidence):
            if int(cid) != 1:  # COCO: 1 = person
                continue
            x1, y1, x2, y2 = [float(v) for v in xyxy]
            out.append(Det("person", (x1, y1, x2, y2), float(conf), ((x1 + x2) / 2, y2), 0.0, None, y2 >= H - 3))
        return out


class NoPersonDetector:
    def detect(self, frame) -> list:
        return []


def build_person_detector(name: str):
    name = (name or "hog").lower()
    if name in ("none", "off"):
        return NoPersonDetector()
    if name == "hog":
        return HogPersonDetector()
    if name.startswith("rfdetr"):
        size = name.split(":", 1)[1] if ":" in name else "nano"
        return RfDetrPersonDetector(size)
    raise ValueError(f"rilevatore sconosciuto: {name} (hog | rfdetr[:nano|small|base] | none)")
