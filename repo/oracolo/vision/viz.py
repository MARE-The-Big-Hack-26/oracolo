"""Disegno sopra il video: CAD proiettato, zone non osservate, persone, muletto, livello."""
from __future__ import annotations

import math

import cv2
import numpy as np

from ..policy import LEVEL_NAMES
from .calib import overlay_vertices
from .calib_math import distort_norm_pts

LEVEL_BGR = [(58, 138, 27), (0, 137, 181), (16, 106, 204), (30, 38, 179)]
OCC_BGR = (0, 165, 255)
_STATIC_CACHE: dict[tuple, dict] = {}


def _static_proj(calib, scene, fw: int, fh: int, Hinv: np.ndarray, k: float) -> dict:
    key = (id(calib), id(scene), fw, fh, float(k))
    cached = _STATIC_CACHE.get(key)
    if cached is not None:
        return cached
    if len(_STATIC_CACHE) >= 4:
        _STATIC_CACHE.clear()
    polys = [(_proj_poly(Hinv, calib, np.asarray(scene.bounds.exterior.coords)[:, :2], 0.0, k, closed=True), (255, 255, 255), 2)]
    for o in scene.occluders:
        if o.poly.geom_type != "Polygon":
            continue
        pts = np.asarray(o.poly.exterior.coords)[:, :2]
        polys.append((_proj_poly(Hinv, calib, pts, 0.0, k, closed=True), OCC_BGR, 2))
        if o.height > 0.05:
            polys.append((_proj_poly(Hinv, calib, pts, o.height, k, closed=True), (233, 180, 86), 1))
    out = {"polys": [p for p in polys if len(p[0]) >= 3], "fog_quads": None}
    _STATIC_CACHE[key] = out
    return out


def _fog_quads(cache_entry: dict, calib, Hinv: np.ndarray, k: float, fdat: dict, shape: tuple[int, int]) -> tuple:
    ny, nx = shape
    fkey = (nx, ny, fdat["minx"], fdat["miny"], fdat["res"])
    if cache_entry["fog_quads"] is not None and cache_entry["fog_quads"][0] == fkey:
        return cache_entry["fog_quads"]
    _, _, minx, miny, res = fkey
    ix, iy = np.meshgrid(np.arange(nx), np.arange(ny))
    x0 = (minx + ix * res).ravel()
    y0 = (miny + iy * res).ravel()
    corners = np.stack([
        np.column_stack([x0, y0]), np.column_stack([x0 + res, y0]),
        np.column_stack([x0 + res, y0 + res]), np.column_stack([x0, y0 + res]),
    ], axis=1)
    w = corners[:, :, 0] * Hinv[2, 0] + corners[:, :, 1] * Hinv[2, 1] + Hinv[2, 2]
    keep = (w >= 0.12).all(axis=1)
    lv = _look_vec(calib)
    if lv is not None:
        cxy, u_look = lv
        keep &= (((corners - cxy) @ u_look) >= 0.05).all(axis=1)
    quads = np.empty((ny * nx, 4, 2), dtype=np.int32)
    quads.fill(-1)
    if keep.any():
        flat = corners[keep].reshape(-1, 2)
        denom = flat @ Hinv[2, :2] + Hinv[2, 2]
        uv = np.column_stack([(flat @ Hinv[0, :2] + Hinv[0, 2]) / denom, (flat @ Hinv[1, :2] + Hinv[1, 2]) / denom])
        if getattr(calib, "K", None) is not None and abs(getattr(calib, "k1", 0.0)) > 1e-7:
            uv = distort_norm_pts(uv, calib.K, calib.k1)
        quads[keep] = np.clip(np.rint(uv / k), -4096, 4096).astype(np.int32).reshape(-1, 4, 2)
    quads = quads.reshape(ny, nx, 4, 2)
    cache_entry["fog_quads"] = (fkey, quads, keep.reshape(ny, nx))
    return cache_entry["fog_quads"]


def _pill(img, text: str, org: tuple[int, int], bg: tuple[int, int, int], fg=(255, 255, 255), scale: float = 0.5):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    x, y = max(4, org[0]), max(th + 8, org[1])
    cv2.rectangle(img, (x - 4, y - th - 5), (x + tw + 6, y + 4), bg, -1)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, fg, 1, cv2.LINE_AA)


def _ref_point(calib) -> np.ndarray:
    if getattr(calib, "world_pts", None):
        return np.mean(np.asarray(calib.world_pts, dtype=np.float64), axis=0)[:2]
    return np.asarray(calib.to_world(calib.image_size[0] / 2.0, calib.image_size[1] - 1.0), dtype=np.float64)


def _look_vec(calib) -> tuple[np.ndarray, np.ndarray] | None:
    """Ritorna (cam_xy, versore_sguardo) sul pavimento per ritagliare ciò che sta dietro al treppiede."""
    if calib is None or getattr(calib, "cam_xy", None) is None:
        return None
    cxy = np.asarray(calib.cam_xy, dtype=np.float64)[:2]
    look = _ref_point(calib) - cxy
    norm = float(np.linalg.norm(look)) if np.all(np.isfinite(look)) else 0.0
    return (cxy, look / norm) if norm > 1e-6 else None


def _norm_hinv(calib) -> np.ndarray:
    """Restituisce H^-1 normalizzata così che i punti davanti alla camera abbiano w > 0."""
    Hinv = np.linalg.inv(calib.H)
    ref = _ref_point(calib)
    if math.isfinite(ref[0]) and math.isfinite(ref[1]):
        w_ref = float((Hinv @ np.array([ref[0], ref[1], 1.0]))[2])
        if abs(w_ref) > 1e-12:
            Hinv = Hinv / w_ref
    return Hinv


def _clip_half(P: np.ndarray, w: np.ndarray, closed: bool, eps: float) -> np.ndarray:
    min_pts = 3 if closed else 2
    if len(P) < min_pts:
        return np.zeros((0, 2), dtype=np.float64)
    out = []
    n = len(P)
    for i in (range(n) if closed else range(n - 1)):
        j = (i + 1) % n
        wi, wj = float(w[i]), float(w[j])
        in_i, in_j = wi >= eps, wj >= eps
        if in_i:
            out.append(P[i])
        if in_i != in_j:
            out.append(P[i] + ((eps - wi) / (wj - wi)) * (P[j] - P[i]))
    if not closed and w[-1] >= eps:
        out.append(P[-1])
    return np.asarray(out, dtype=np.float64) if len(out) >= min_pts else np.zeros((0, 2), dtype=np.float64)


def _clip_front(Hinv: np.ndarray, pts, closed: bool = True, eps: float = 0.12, calib=None) -> np.ndarray:
    """Ritaglia un poligono o una spezzata sul semipiano davanti alla camera e oltre l'orizzonte."""
    P = np.asarray(pts, dtype=np.float64)
    if P.ndim != 2 or len(P) == 0:
        return np.zeros((0, 2), dtype=np.float64)
    P = P[:, :2]
    if closed and len(P) >= 2 and np.allclose(P[0], P[-1]):
        P = P[:-1]
    P = _clip_half(P, P @ Hinv[2, :2] + Hinv[2, 2], closed, eps)
    lv = _look_vec(calib)
    if len(P) > 0 and lv is not None:
        cxy, u_look = lv
        P = _clip_half(P, (P - cxy) @ u_look, closed, 0.05)
    return P


def _project_clipped(Hinv: np.ndarray, pts, k: float, closed: bool = True, eps: float = 0.12, calib=None) -> np.ndarray:
    """Proietta punti 2D sul pavimento ritagliando ciò che sta dietro la camera o l'orizzonte."""
    c = _clip_front(Hinv, pts, closed=closed, eps=eps, calib=calib)
    if len(c) == 0:
        return np.zeros((0, 2), dtype=np.int32)
    denom = c @ Hinv[2, :2] + Hinv[2, 2]
    uv = np.column_stack([(c @ Hinv[0, :2] + Hinv[0, 2]) / denom, (c @ Hinv[1, :2] + Hinv[1, 2]) / denom])
    if calib is not None and getattr(calib, "K", None) is not None and abs(getattr(calib, "k1", 0.0)) > 1e-7:
        uv = distort_norm_pts(uv, calib.K, calib.k1)
    return np.clip(np.rint(uv / k), -4096, 4096).astype(np.int32)


def _subdivide(pts: np.ndarray, closed: bool, step: float = 0.35) -> np.ndarray:
    """Suddivide i segmenti lunghi affinché la distorsione radiale segua le curve reali."""
    out = []
    n = len(pts)
    for i in (range(n) if closed else range(n - 1)):
        a, b = pts[i], pts[(i + 1) % n]
        m = max(1, int(math.ceil(float(np.linalg.norm(b - a)) / step)))
        for s in range(m):
            out.append(a + (s / m) * (b - a))
    if not closed and n > 0:
        out.append(pts[-1])
    return np.asarray(out, dtype=np.float64)


def _project_3d(calib, pts2d, z: float, k: float, closed: bool = True) -> np.ndarray | None:
    """Proietta un poligono/spezzata 3D alla quota z usando la posa (K, rvec, tvec, k1)."""
    if getattr(calib, "K", None) is None or getattr(calib, "rvec", None) is None or getattr(calib, "tvec", None) is None:
        return None
    P = np.asarray(pts2d, dtype=np.float64)
    if P.ndim != 2 or len(P) == 0:
        return np.zeros((0, 2), dtype=np.int32)
    P = P[:, :2]
    if closed and len(P) >= 2 and np.allclose(P[0], P[-1]):
        P = P[:-1]
    R, _ = cv2.Rodrigues(calib.rvec)
    t = calib.tvec.ravel()
    C = (R @ np.column_stack([P, np.full(len(P), float(z))]).T).T + t
    C_clip = _clip_half(C, C[:, 2], closed, 0.15)
    if len(C_clip) == 0:
        return np.zeros((0, 2), dtype=np.int32)
    if abs(getattr(calib, "k1", 0.0)) > 1e-4:
        C_clip = _subdivide(C_clip, closed=closed)
    dist = np.array([calib.k1, 0.0, 0.0, 0.0], dtype=np.float64) if abs(getattr(calib, "k1", 0.0)) > 1e-7 else None
    proj, _ = cv2.projectPoints(C_clip, np.zeros(3), np.zeros(3), calib.K, dist)
    return np.clip(np.rint(proj.reshape(-1, 2) / k), -4096, 4096).astype(np.int32)


def _pt_img(Hinv: np.ndarray, pt, k: float, eps: float = 0.05, calib=None) -> tuple[int, int] | None:
    p = Hinv @ np.array([float(pt[0]), float(pt[1]), 1.0])
    if p[2] < eps:
        return None
    uv = np.array([[p[0] / p[2], p[1] / p[2]]], dtype=np.float64)
    if calib is not None and getattr(calib, "K", None) is not None and abs(getattr(calib, "k1", 0.0)) > 1e-7:
        uv = distort_norm_pts(uv, calib.K, calib.k1)
    u = int(np.clip(round(uv[0, 0] / k), -4096, 4096))
    v = int(np.clip(round(uv[0, 1] / k), -4096, 4096))
    return (u, v)


def _top_poly_world(pts: np.ndarray, calib, height: float) -> np.ndarray | None:
    """Espande radialmente la base di un ostacolo alla quota top (proiezione sul pavimento)."""
    if height <= 0.05 or calib.cam_h <= 0.2:
        return None
    z = min(float(height), calib.cam_h * 0.85)
    s = calib.cam_h / (calib.cam_h - z)
    cx, cy = calib.cam_xy
    c = np.array([cx, cy], dtype=np.float64)
    return c + (pts[:, :2] - c) * s


def _proj_poly(Hinv: np.ndarray, calib, pts, z: float, k: float, closed: bool = True) -> np.ndarray:
    p3 = _project_3d(calib, pts, z, k, closed=closed)
    if p3 is not None:
        return p3
    if z > 0.0:
        pts = _top_poly_world(np.asarray(pts, dtype=np.float64)[:, :2], calib, z)
        if pts is None:
            return np.zeros((0, 2), dtype=np.int32)
    return _project_clipped(Hinv, pts, k, closed=closed, calib=calib)


def overlay_polys(calib, scene) -> dict:
    """Poligoni proiettati (coordinate pixel di calibrazione) per l'anteprima in /calibrate."""
    Hinv = _norm_hinv(calib)
    bounds_pts = np.asarray(scene.bounds.exterior.coords)[:, :2]
    occs = []
    for o in scene.occluders:
        if o.poly.geom_type != "Polygon":
            continue
        pts = np.asarray(o.poly.exterior.coords)[:, :2]
        top_pts = _proj_poly(Hinv, calib, pts, o.height, 1.0).tolist() if o.height > 0.05 else []
        occs.append({"name": o.name, "floor": _proj_poly(Hinv, calib, pts, 0.0, 1.0).tolist(), "top": top_pts})
    return {"bounds": _proj_poly(Hinv, calib, bounds_pts, 0.0, 1.0).tolist(), "occluders": occs, "vertices": overlay_vertices(calib, scene)}


def draw_overlay(frame, calib, scene, state: dict, max_width: int = 960):
    img = frame.copy()
    fh, fw = img.shape[:2]
    if calib is None:
        uncal_persons = state.get("persons", [])
        for pr in uncal_persons:
            if pr.get("box"):
                x1, y1, x2, y2 = [int(v) for v in pr["box"]]
                cv2.rectangle(img, (x1, y1), (x2, y2), (255, 160, 0), 2)
                lbl = f"P{pr['id']} ({pr.get('conf', 0):.0%})"
                cv2.putText(img, lbl, (x1, max(y1 - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 160, 0), 2)
            if pr.get("foot"):
                fx, fy = [int(v) for v in pr["foot"]]
                cv2.circle(img, (fx, fy), 5, (0, 255, 255), -1, cv2.LINE_AA)
        mb = state.get("uncalibrated_marker")
        if mb:
            x1, y1, x2, y2 = [int(v) for v in mb]
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 220, 0), 2)
            cv2.putText(img, "marker muletto", (x1, max(y1 - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 0), 2)
        cv2.putText(img, f"NON CALIBRATO: apri /calibrate  (persone rilevate: {len(uncal_persons)})",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 255), 2)
        return _fit(img, max_width)
    k = calib.image_size[0] / fw
    Hinv = _norm_hinv(calib)
    scache = _static_proj(calib, scene, fw, fh, Hinv, k)

    # zone non osservate / persona possibile (da mappa fog)
    fog = state.get("_fog")
    fdat = state.get("fog")
    if fog is not None and fdat is not None:
        _, quads_grid, keep_grid = _fog_quads(scache, calib, Hinv, k, fdat, fog.shape[:2])
        overlay = img.copy()
        drew = False
        for val, col in ((3, (0, 200, 255)), (4, (0, 0, 255))):
            mask = (fog == val) & keep_grid
            if mask.any():
                cv2.fillPoly(overlay, list(quads_grid[mask]), col)
                drew = True
        if drew:
            img = cv2.addWeighted(overlay, 0.28, img, 0.72, 0)

    # planimetria sopra il video (cache proiettata)
    for p, col_p, th in scache["polys"]:
        cv2.polylines(img, [p], True, col_p, th, cv2.LINE_AA)

    dec = state.get("decision")
    lv = dec["level"] if dec else 0
    col = LEVEL_BGR[lv]

    # percorso e muletto
    path = state.get("path") or []
    if len(path) >= 2:
        p = _project_clipped(Hinv, path, k, closed=False, calib=calib)
        if len(p) >= 2:
            cv2.polylines(img, [p], False, col, 4, cv2.LINE_AA)
    veh = state.get("vehicle")
    if veh:
        c = _pt_img(Hinv, veh["xy"], k, calib=calib)
        f = _pt_img(Hinv, [veh["xy"][0] + 0.55 * math.cos(veh["heading"]), veh["xy"][1] + 0.55 * math.sin(veh["heading"])], k, calib=calib)
        if c is not None:
            cv2.circle(img, c, 12, col if veh["tracked"] else (128, 128, 128), -1, cv2.LINE_AA)
            cv2.circle(img, c, 12, (255, 255, 255), 2, cv2.LINE_AA)
            if f is not None:
                cv2.arrowedLine(img, c, f, (255, 255, 255), 3, cv2.LINE_AA, tipLength=0.35)
            _pill(img, f"MULETTO {veh['speed']:.1f} m/s", (c[0] + 16, c[1] - 8), (15, 23, 42))

    # persone
    for pr in state.get("persons", []):
        if pr.get("box"):
            x1, y1, x2, y2 = [int(v) for v in pr["box"]]
            moving = pr.get("speed", 0.0) > 0.25
            bcol = (0, 215, 255) if moving else (255, 160, 0)
            cv2.rectangle(img, (x1, y1), (x2, y2), bcol, 2)
            _pill(img, f"P{pr['id']} {pr['speed']:.1f} m/s", (x1, y1 - 6), (15, 23, 42), bcol)
        if pr.get("foot"):
            fx, fy = [int(v) for v in pr["foot"]]
            cv2.circle(img, (fx, fy), 5, (0, 255, 255), -1, cv2.LINE_AA)
            if pr.get("xy") and (abs(pr.get("vx", 0.0)) + abs(pr.get("vy", 0.0))) > 0.25:
                tip = _pt_img(Hinv, [pr["xy"][0] + pr["vx"] * 0.6, pr["xy"][1] + pr["vy"] * 0.6], k, calib=calib)
                if tip is not None:
                    cv2.arrowedLine(img, (fx, fy), tip, (0, 255, 255), 2, cv2.LINE_AA, tipLength=0.3)
    for b in state.get("out_of_bounds", []):
        x1, y1, x2, y2 = [int(v) for v in b]
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 165, 255), 1)
        _pill(img, "fuori mappa", (x1, y1 - 6), (30, 41, 59), (0, 165, 255), 0.45)
    for b in state.get("drivers", []):
        x1, y1, x2, y2 = [int(v) for v in b]
        cv2.rectangle(img, (x1, y1), (x2, y2), (160, 160, 160), 1)
        _pill(img, "conducente", (x1, y1 - 6), (30, 41, 59), (200, 200, 200), 0.45)

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
