"""Rilevatori: marker ArUco (il muletto) e persone.

Il muletto simulato è una sedia con un marker ArUco sopra: identità e orientamento certi,
anche con poca luce. Le persone si rilevano con ``yolo`` (YOLO11-Pose / YOLO11,
consigliato su Apple Silicon), ``rfdetr`` (RF-DETR, Apache 2.0) oppure ``hog``
(OpenCV, nessun download, qualità media). Il motore non dipende da nessuno di questi.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


TAG_DIR = Path(__file__).resolve().parent / "tags"


class TagMatcher:
    """Riconosce un cartello 'a disegno' NON ArUco (il foglio del lavoratore stampato da noi).

    Cerca quadrati scuri, li raddrizza e li confronta con un modello (correlazione normalizzata) nelle
    4 rotazioni: la persona può girarsi. Non dà identità crittografica come ArUco: soglia ``thr`` da tarare in aula.
    """

    def __init__(self, template_path=None, thr: float = 0.55, size: int = 96, height: float = 1.2):
        path = Path(template_path) if template_path else TAG_DIR / "lavoratore.png"
        t = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if t is None:
            raise FileNotFoundError(f"modello del cartello non trovato: {path}")
        t = cv2.resize(t, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32)
        self.size, self.thr, self.height = size, thr, height
        self.rots = [np.rot90(t, k) for k in range(4)]
        self.rots = [cv2.GaussianBlur(np.ascontiguousarray(r), (0, 0), 2) for r in self.rots]  # tollera piccoli errori di angolo
        self.last_score = 0.0

    def _score(self, patch) -> float:
        """patch = quadrato raddrizzato con ~8% di margine: cerca il modello con piccoli spostamenti e scale."""
        p = cv2.GaussianBlur(patch.astype(np.float32), (0, 0), 2)
        best = -1.0
        for r in self.rots:
            for sc in (0.9, 1.0, 1.1):
                n = int(round(self.size * sc))
                t = cv2.resize(r, (n, n), interpolation=cv2.INTER_AREA)
                if n > p.shape[0]:
                    continue
                best = max(best, float(cv2.matchTemplate(p, t, cv2.TM_CCOEFF_NORMED).max()))
        return best

    def detect(self, frame, skip_pts=()) -> list:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        H, W = gray.shape
        s = min(1.0, 1280 / W)
        g = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else gray
        g = cv2.GaussianBlur(g, (5, 5), 0)
        out, best = [], 0.0
        area_img = g.shape[0] * g.shape[1]
        seen_cen = []
        for T in (55, 80, 105):  # soglie diverse: il nero del cartello dipende dalla luce
            dark = cv2.morphologyEx(((g < T) * 255).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))  # chiude le pieghe
            cnts, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in cnts:
                a = cv2.contourArea(c)
                if a < 0.0015 * area_img or a > 0.5 * area_img:
                    continue
                hull = cv2.convexHull(c)
                peri = cv2.arcLength(hull, True)
                quad = cv2.approxPolyDP(hull, 0.04 * peri, True)
                if len(quad) != 4 or cv2.contourArea(quad) < 0.85 * a:
                    continue
                q = quad.reshape(4, 2).astype(np.float32)
                cen = q.mean(axis=0) / s
                if any(np.hypot(cen[0] - c0[0], cen[1] - c0[1]) < 20 for c0 in seen_cen):
                    continue
                if any(cv2.pointPolygonTest(np.asarray(p, np.float32), (float(cen[0]), float(cen[1])), False) >= 0
                       for p in skip_pts):
                    continue  # è un marker ArUco (ancora, muletto): non è il cartello
                idx = np.argsort(q[:, 1]); top, bot = q[idx[:2]], q[idx[2:]]  # ordine: alto-sx, alto-dx, basso-dx, basso-sx
                q = np.float32([top[np.argmin(top[:, 0])], top[np.argmax(top[:, 0])],
                                bot[np.argmax(bot[:, 0])], bot[np.argmin(bot[:, 0])]])
                m = int(self.size * 0.08)
                S = self.size + 2 * m
                M = cv2.getPerspectiveTransform(q, np.float32([[m, m], [m + self.size, m], [m + self.size, m + self.size], [m, m + self.size]]))
                sc = self._score(cv2.warpPerspective(g, M, (S, S), borderMode=cv2.BORDER_REPLICATE))
                best = max(best, sc)
                if sc >= self.thr:
                    seen_cen.append(cen)
                    x1, y1 = q.min(axis=0) / s
                    x2, y2 = q.max(axis=0) / s
                    out.append((sc, Det("person", (float(x1), float(y1), float(x2), float(y2)), min(1.0, sc),
                                        (float(cen[0]), float(cen[1])), self.height)))
        self.last_score = best
        return [d for _, d in sorted(out, key=lambda t: -t[0])]


class MarkerDetector:
    """Marker ArUco del muletto. Il lato SUPERIORE del marker deve guardare il davanti della sedia."""

    def __init__(self, marker_id: int = 0, dictionary: str = "DICT_4X4_50", height: float = 0.45,
                 worker_ids=range(1, 10), worker_height: float = 1.2, tag: "TagMatcher | None" = None):
        d = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary))
        # marker "lavoratore": ID 1-9, indossato al petto -> persona certa (le ancore usano 10-17, il muletto 0)
        self.worker_ids = set(worker_ids) - {marker_id}
        self.worker_height = worker_height
        self.tag = tag  # cartello a disegno (non ArUco) del lavoratore
        self.workers = []  # Det("person") dei marker lavoratore dell'ultimo frame
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        params.cornerRefinementWinSize = 5
        params.cornerRefinementMaxIterations = 30
        params.detectInvertedMarker = False
        self._det = cv2.aruco.ArucoDetector(d, params)
        self.marker_id = marker_id
        self.height = height
        self.seen = {}  # id -> angoli 4x2 (pixel) di TUTTI i marker dell'ultimo frame: le ancore a terra usano questi

    def detect(self, frame, gray=None) -> list:
        if gray is None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        corners, ids, _ = self._det.detectMarkers(gray)
        out = []
        self.seen = {} if ids is None else {int(i): c[0].astype(float) for c, i in zip(corners, ids.flatten())}
        self.workers = []
        if self.tag is not None:
            skip = [c[0] for c in corners]
            self.workers.extend(self.tag.detect(frame, skip))
        if ids is None:
            return out
        for c, i in zip(corners, ids.flatten()):
            if int(i) in self.worker_ids:
                c = c[0].astype(float)
                x1, y1 = c.min(axis=0)
                x2, y2 = c.max(axis=0)
                cen = c.mean(axis=0)
                self.workers.append(Det("person", (x1, y1, x2, y2), 1.0, (float(cen[0]), float(cen[1])),
                                        self.worker_height))
                continue
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


def _best_device() -> str:
    """Seleziona il backend migliore disponibile (mps su Apple Silicon, altrimenti cuda/cpu)."""
    import torch  # noqa: PLC0415

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class YoloPersonDetector:
    """YOLO11 / YOLO11-Pose (Ultralytics). Con varianti ``pose`` stima le caviglie per il punto a terra."""

    _WEIGHTS = {
        "pose": "yolo11n-pose.pt",
        "11n-pose": "yolo11n-pose.pt",
        "11s-pose": "yolo11s-pose.pt",
        "11n": "yolo11n.pt",
        "nano": "yolo11n.pt",
        "11s": "yolo11s.pt",
        "small": "yolo11s.pt",
        "v8n": "yolov8n.pt",
    }

    def __init__(self, variant: str = "pose", threshold: float = 0.35, device: str | None = None):
        from ultralytics import YOLO  # noqa: PLC0415

        key = (variant or "pose").lower()
        if key in self._WEIGHTS:
            weights = self._WEIGHTS[key]
        elif key.endswith(".pt"):
            weights = variant
        elif key.startswith("yolo"):
            weights = f"{variant}.pt"
        else:
            weights = f"yolo{variant}.pt"
        self.weights = weights
        self.model = YOLO(weights)
        self.threshold = threshold
        self.device = device or _best_device()
        # Warmup per evitare il blocco sul primo frame live (compilazione grafi MPS/CUDA)
        dummy = np.zeros((512, 512, 3), dtype=np.uint8)
        self.model.predict(dummy, classes=[0], conf=self.threshold, iou=0.5, imgsz=512, device=self.device, verbose=False)

    def detect(self, frame) -> list:
        import torch  # noqa: PLC0415

        with torch.inference_mode():
            res = self.model.predict(
                frame, classes=[0], conf=self.threshold, iou=0.5, imgsz=512, device=self.device, verbose=False
            )[0]
        if res.boxes is None or len(res.boxes) == 0:
            return []
        H = frame.shape[0]
        xyxy_arr = res.boxes.xyxy.cpu().numpy()
        confs = res.boxes.conf.cpu().numpy()
        kpts = None
        if res.keypoints is not None and res.keypoints.data is not None and len(res.keypoints.data) == len(xyxy_arr):
            kpts = res.keypoints.data.cpu().numpy()
        out = []
        for i, (xyxy, conf) in enumerate(zip(xyxy_arr, confs)):
            x1, y1, x2, y2 = [float(v) for v in xyxy]
            foot = ((x1 + x2) / 2, y2)
            truncated = y2 >= H - 3
            if kpts is not None and kpts.ndim == 3 and kpts.shape[1] >= 17:
                ankles = [(float(kx), float(ky)) for kx, ky, kc in (kpts[i, 15], kpts[i, 16])
                          if float(kc) >= 0.28 and float(kx) > 0 and float(ky) > 0]
                if ankles:
                    foot = (float(np.mean([a[0] for a in ankles])), float(np.max([a[1] for a in ankles])))
                    truncated = foot[1] >= H - 3
                else:
                    truncated = True
            out.append(Det("person", (x1, y1, x2, y2), float(conf), foot, 0.0, None, bool(truncated)))
        return out


class RfDetrPersonDetector:
    """RF-DETR (Apache 2.0). Richiede ``pip install rfdetr`` (porta con sé PyTorch)."""

    def __init__(self, size: str = "nano", threshold: float = 0.4):
        import rfdetr  # noqa: PLC0415 (import tardivo: dipendenza opzionale)

        cls = {"nano": "RFDETRNano", "small": "RFDETRSmall", "base": "RFDETRBase"}[size]
        self.model = getattr(rfdetr, cls)()
        self.threshold = threshold
        self._person_ids = self._resolve_person_ids()
        try:
            self.model.optimize_for_inference()
        except Exception:  # noqa: BLE001 (non tutte le versioni/piattaforme lo supportano)
            pass

    def _resolve_person_ids(self) -> set[int]:
        names = getattr(self.model, "class_names", None)
        if isinstance(names, dict):
            ids = {int(k) for k, v in names.items() if str(v).lower() == "person"}
            if ids:
                return ids
        elif isinstance(names, (list, tuple)):
            ids = {i for i, v in enumerate(names) if str(v).lower() == "person"}
            if ids:
                return ids
        return {0, 1}

    def detect(self, frame) -> list:
        from PIL import Image  # noqa: PLC0415

        rgb = Image.fromarray(frame[:, :, ::-1])
        dets = self.model.predict(rgb, threshold=self.threshold)
        H = frame.shape[0]
        out = []
        for xyxy, cid, conf in zip(dets.xyxy, dets.class_id, dets.confidence):
            if int(cid) not in self._person_ids:
                continue
            x1, y1, x2, y2 = [float(v) for v in xyxy]
            out.append(Det("person", (x1, y1, x2, y2), float(conf), ((x1 + x2) / 2, y2), 0.0, None, y2 >= H - 3))
        return out


class NoPersonDetector:
    def detect(self, frame) -> list:
        return []


def build_person_detector(name: str):
    name = (name or "auto").lower()
    if name in ("none", "off"):
        return NoPersonDetector()
    if name == "auto":
        for factory in (lambda: YoloPersonDetector("pose"), lambda: RfDetrPersonDetector("nano")):
            try:
                return factory()
            except Exception:  # noqa: BLE001
                continue
        return HogPersonDetector()
    if name == "hog":
        return HogPersonDetector()
    if name == "yolo" or name.startswith("yolo:"):
        variant = name.split(":", 1)[1] if ":" in name else "pose"
        return YoloPersonDetector(variant)
    if name == "rfdetr" or name.startswith("rfdetr:"):
        size = name.split(":", 1)[1] if ":" in name else "nano"
        return RfDetrPersonDetector(size)
    raise ValueError(f"rilevatore sconosciuto: {name} (auto | yolo[:pose|11n|11s] | rfdetr[:nano|small|base] | hog | none)")
