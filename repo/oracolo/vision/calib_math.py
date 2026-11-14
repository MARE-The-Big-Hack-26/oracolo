"""Solver matematici per calibrazione camera (PnP 3D, focale, distorsione radiale)."""
from __future__ import annotations

import math

import cv2
import numpy as np


def make_K(f: float, w: float, h: float) -> np.ndarray:
    return np.array([[f, 0.0, w / 2.0], [0.0, f, h / 2.0], [0.0, 0.0, 1.0]], dtype=np.float64)


def undistort(pts: np.ndarray, K: np.ndarray | None, k1: float) -> np.ndarray:
    if K is None or abs(k1) < 1e-7:
        return pts
    dist = np.array([k1, 0.0, 0.0, 0.0], dtype=np.float64)
    return cv2.undistortPoints(pts.reshape(-1, 1, 2), K, dist, P=K).reshape(-1, 2)


def distort_norm_pts(uv_undist: np.ndarray, K: np.ndarray, k1: float) -> np.ndarray:
    if abs(k1) < 1e-7:
        return uv_undist
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    xn = (uv_undist[:, 0] - cx) / fx
    yn = (uv_undist[:, 1] - cy) / fy
    s = 1.0 + k1 * (xn * xn + yn * yn)
    return np.column_stack([cx + fx * xn * s, cy + fy * yn * s])


def golden_min(fn, lo: float, hi: float, iters: int = 14) -> tuple[float, float]:
    phi = (math.sqrt(5.0) - 1.0) / 2.0
    c, d = hi - phi * (hi - lo), lo + phi * (hi - lo)
    fc, fd = fn(c), fn(d)
    for _ in range(iters):
        if fc < fd:
            hi, d, fd = d, c, fc
            c = hi - phi * (hi - lo)
            fc = fn(c)
        else:
            lo, c, fc = c, d, fd
            d = lo + phi * (hi - lo)
            fd = fn(d)
    return (c, fc) if fc < fd else (d, fd)


def _eval_pnp(wor3: np.ndarray, img: np.ndarray, K: np.ndarray, k1: float):
    dist = np.array([k1, 0.0, 0.0, 0.0], dtype=np.float64) if abs(k1) > 1e-7 else None
    ok, rvec, tvec = cv2.solvePnP(wor3, img, K, dist, flags=cv2.SOLVEPNP_SQPNP)
    if not ok:
        return None
    ok, rvec, tvec = cv2.solvePnP(wor3, img, K, dist, rvec, tvec, True, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        return None
    R, _ = cv2.Rodrigues(rvec)
    cam = -R.T @ tvec.ravel()
    z_cam = (R @ wor3.T + tvec)[2]
    if not np.isfinite(cam).all() or cam[2] < 0.15 or np.any(z_cam <= 0.05):
        return None
    proj, _ = cv2.projectPoints(wor3, rvec, tvec, K, dist)
    err = np.linalg.norm(proj.reshape(-1, 2) - img, axis=1)
    return float(np.sqrt(np.mean(err ** 2))), rvec, tvec, cam, R


def solve_pnp_auto(img: np.ndarray, wor3: np.ndarray, image_size: tuple[int, int], fit_distortion: bool):
    w, h = float(image_size[0]), float(image_size[1])
    best = None
    for fov in (45.0, 55.0, 65.0, 75.0, 85.0, 95.0, 105.0):
        f = (w / 2.0) / math.tan(math.radians(fov) / 2.0)
        res = _eval_pnp(wor3, img, make_K(f, w, h), 0.0)
        if res is not None and (best is None or res[0] < best[0]):
            best = (res[0], f, res[1], res[2], res[3], res[4])
    if best is None:
        return None

    def obj_f(f_val: float, k1_val: float) -> float:
        res = _eval_pnp(wor3, img, make_K(f_val, w, h), k1_val)
        return res[0] if res is not None else 1e9

    f_best, _ = golden_min(lambda fv: obj_f(fv, 0.0), max(w * 0.25, best[1] * 0.7), min(w * 3.0, best[1] * 1.4))
    k1_best = 0.0
    if fit_distortion and len(img) >= 6:
        k1_cand, err_k = golden_min(lambda kv: obj_f(f_best, kv), -0.35, 0.35)
        if err_k < obj_f(f_best, 0.0) * 0.96:
            k1_best = k1_cand
            f_best, _ = golden_min(lambda fv: obj_f(fv, k1_best), max(w * 0.25, f_best * 0.8), min(w * 3.0, f_best * 1.25))
    res = _eval_pnp(wor3, img, make_K(f_best, w, h), k1_best)
    if res is None:
        return None
    return make_K(f_best, w, h), k1_best, res[1], res[2], res[3], res[4]


def _estimate_f_from_H(H_w2i: np.ndarray, w: float, h: float) -> float:
    A = np.array([[1.0, 0.0, -w / 2.0], [0.0, 1.0, -h / 2.0], [0.0, 0.0, 1.0]]) @ H_w2i
    denom = A[2, 0] * A[2, 1]
    if abs(denom) > 1e-12:
        f2 = -(A[0, 0] * A[0, 1] + A[1, 0] * A[1, 1]) / denom
        if f2 > 0:
            return float(np.clip(math.sqrt(f2), w * 0.3, w * 2.5))
    return w * 0.85


def _planar_px_rms(img: np.ndarray, wor2: np.ndarray, H: np.ndarray, K: np.ndarray | None, k1: float) -> float:
    p = (np.linalg.inv(H) @ np.column_stack([wor2, np.ones(len(wor2))]).T).T
    if np.any(np.abs(p[:, 2]) < 1e-9):
        return 1e9
    uv = p[:, :2] / p[:, 2:3]
    if K is not None and abs(k1) > 1e-7:
        uv = distort_norm_pts(uv, K, k1)
    return float(np.sqrt(np.mean(np.sum((uv - img) ** 2, axis=1))))


def refine_planar_k1(img: np.ndarray, wor2: np.ndarray, image_size: tuple[int, int], H0: np.ndarray):
    w, h = float(image_size[0]), float(image_size[1])
    K = make_K(_estimate_f_from_H(np.linalg.inv(H0), w, h), w, h)
    base_rms = _planar_px_rms(img, wor2, H0, None, 0.0)

    def obj_k(kv: float) -> float:
        Hk, _ = cv2.findHomography(undistort(img, K, kv), wor2, 0)
        return _planar_px_rms(img, wor2, Hk, K, kv) if Hk is not None else 1e9

    k1_best, rms_k = golden_min(obj_k, -0.35, 0.35, iters=12)
    if rms_k < base_rms * 0.94 and rms_k < base_rms - 0.35:
        Hk, _ = cv2.findHomography(undistort(img, K, k1_best), wor2, 0)
        if Hk is not None:
            return K, float(k1_best), Hk
    return None, 0.0, H0
