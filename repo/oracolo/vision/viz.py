"""Disegno sopra il video: CAD proiettato, zone non osservate, persone, muletto, livello."""
from __future__ import annotations

import math

import cv2
import numpy as np

from ..policy import LEVEL_NAMES

LEVEL_BGR = [(58, 138, 27), (0, 137, 181), (16, 106, 204), (30, 38, 179)]
OCC_BGR = (0, 165, 255)


def _to_img(calib, pts, k):
    Hinv = np.linalg.inv(calib.H)
    a = np.asarray(pts, dtype=np.float64).reshape(-1, 1, 2)
    out = cv2.perspectiveTransform(a, Hinv).reshape(-1, 2) / k
    return out


def draw_overlay(frame, calib, scene, state: dict, max_width: int = 960):
    img = frame.copy()
    fh, fw = img.shape[:2]
    if calib is None:
        cv2.putText(img, "NON CALIBRATO: apri /calibrate", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        return _fit(img, max_width)
    k = calib.image_size[0] / fw

    # zone non osservate / persona possibile (da mappa fog)
    fog = state.get("_fog")
    fdat = state.get("fog")
    if fog is not None and fdat is not None:
        res, minx, miny = fdat["res"], fdat["minx"], fdat["miny"]
        overlay = img.copy()
        for val, col in ((3, (0, 200, 255)), (4, (0, 0, 255))):
            iy, ix = np.nonzero(fog == val)
            if len(ix) == 0:
                continue
            x0, y0 = minx + ix * res, miny + iy * res
            corners = np.stack([np.column_stack([x0, y0]), np.column_stack([x0 + res, y0]),
                                np.column_stack([x0 + res, y0 + res]), np.column_stack([x0, y0 + res])], axis=1)
            quad = _to_img(calib, corners.reshape(-1, 2), k).reshape(-1, 4, 2).astype(np.int32)
            for q in quad:
                cv2.fillConvexPoly(overlay, q, col)
        img = cv2.addWeighted(overlay, 0.30, img, 0.70, 0)

    # planimetria sopra il video
    def poly(pts, col, th):
        p = _to_img(calib, pts, k).astype(np.int32)
        cv2.polylines(img, [p], True, col, th, cv2.LINE_AA)

    poly(np.asarray(scene.bounds.exterior.coords)[:, :2], (255, 255, 255), 2)
    for o in scene.occluders:
        if o.poly.geom_type == "Polygon":
            poly(np.asarray(o.poly.exterior.coords)[:, :2], OCC_BGR, 2)

    dec = state.get("decision")
    lv = dec["level"] if dec else 0
    col = LEVEL_BGR[lv]

    # percorso e muletto
    path = state.get("path") or []
    if len(path) >= 2:
        p = _to_img(calib, path, k).astype(np.int32)
        cv2.polylines(img, [p], False, col, 4, cv2.LINE_AA)
    veh = state.get("vehicle")
    if veh:
        c = _to_img(calib, [veh["xy"]], k)[0]
        f = _to_img(calib, [[veh["xy"][0] + 0.5 * math.cos(veh["heading"]), veh["xy"][1] + 0.5 * math.sin(veh["heading"])]], k)[0]
        cv2.circle(img, (int(c[0]), int(c[1])), 12, col if veh["tracked"] else (128, 128, 128), -1, cv2.LINE_AA)
        cv2.arrowedLine(img, (int(c[0]), int(c[1])), (int(f[0]), int(f[1])), (255, 255, 255), 3, cv2.LINE_AA, tipLength=0.35)

    # persone
    for pr in state.get("persons", []):
        if pr.get("box"):
            x1, y1, x2, y2 = [int(v) for v in pr["box"]]
            cv2.rectangle(img, (x1, y1), (x2, y2), (255, 160, 0), 2)
            cv2.putText(img, f"P{pr['id']} {pr['speed']:.1f}m/s", (x1, max(y1 - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 160, 0), 2)
    for b in state.get("drivers", []):
        x1, y1, x2, y2 = [int(v) for v in b]
        cv2.rectangle(img, (x1, y1), (x2, y2), (160, 160, 160), 1)
        cv2.putText(img, "conducente", (x1, max(y1 - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)

    # banner
    cv2.rectangle(img, (0, 0), (fw, 54), col, -1)
    if dec:
        txt = f"{LEVEL_NAMES[lv]}   {dec['limit'] * 3.6:.1f} km/h   {dec['cause']}"
    else:
        txt = "MULETTO NON RILEVATO (marker non visibile)"
    cv2.putText(img, txt, (14, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
    return _fit(img, max_width)


def _fit(img, max_width):
    h, w = img.shape[:2]
    if w > max_width:
        s = max_width / w
        img = cv2.resize(img, (max_width, int(h * s)), interpolation=cv2.INTER_AREA)
    return img
