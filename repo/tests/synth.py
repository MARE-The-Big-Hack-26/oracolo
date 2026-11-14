"""Camera sintetica (pinhole) per provare la pipeline senza iPhone: stanza 5x4 m, camera a 2,2 m di altezza."""
import math

import cv2
import numpy as np

W, H = 1280, 720
K = np.array([[700.0, 0, W / 2], [0, 700.0, H / 2], [0, 0, 1]])
CAM = np.array([2.5, -0.6, 2.2])  # sul bordo della stanza, poco fuori: la pipeline la riporta dentro
TARGET = np.array([2.5, 2.2, 0.0])


def _pose():
    f = (TARGET - CAM) / np.linalg.norm(TARGET - CAM)
    r = np.cross(f, [0, 0, 1.0]); r /= np.linalg.norm(r)
    d = np.cross(f, r)
    R = np.stack([r, d, f])
    return R, -R @ CAM


R, T = _pose()


def project(pts):
    """punti 3D (N,3) o (3,) -> pixel (N,2)"""
    p = np.atleast_2d(np.asarray(pts, float))
    c = (R @ p.T).T + T
    uv = (K @ c.T).T
    return uv[:, :2] / uv[:, 2:3]


def aruco_img(mid=0, px=200):
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    m = cv2.aruco.generateImageMarker(d, mid, px)
    out = np.full((px + 2 * (px // 4), px + 2 * (px // 4)), 255, np.uint8)
    q = px // 4
    out[q:q + px, q:q + px] = m
    return out


def render_frame(vehicle=None, floor=True):
    """vehicle = (x, y, heading) del centro del marker (a 0,45 m da terra). Marker 20 cm con bordo bianco."""
    img = np.full((H, W, 3), 90, np.uint8)
    if floor:  # un minimo di texture per la nitidezza
        for gx in range(0, 6):
            a, b = project([[gx, 1.0, 0]])[0], project([[gx, 4, 0]])[0]
            cv2.line(img, tuple(int(v) for v in a), tuple(int(v) for v in b), (160, 160, 160), 2)
    if vehicle is not None:
        x, y, h = vehicle
        f = np.array([math.cos(h), math.sin(h)]); r = np.array([f[1], -f[0]])
        s = 0.125  # mezzo lato incluso il bordo bianco (marker 20 cm + 5 cm di bordo)
        c = np.array([x, y])
        corners = [c + s * f - s * r, c + s * f + s * r, c - s * f + s * r, c - s * f - s * r]
        dst = project([[p[0], p[1], 0.45] for p in corners]).astype(np.float32)
        m = aruco_img()
        sz = m.shape[0]
        src = np.float32([[0, 0], [sz, 0], [sz, sz], [0, sz]])
        M = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(cv2.cvtColor(m, cv2.COLOR_GRAY2BGR), M, (W, H))
        mask = cv2.warpPerspective(np.full((sz, sz), 255, np.uint8), M, (W, H))
        img[mask > 0] = warped[mask > 0]
    return img


def floor_pairs():
    """4 punti a terra (mappa) e i loro pixel."""
    world = [(1.0, 1.4), (4.0, 1.4), (4.0, 3.5), (1.0, 3.5)]
    img = project([[x, y, 0] for x, y in world])
    return img.tolist(), [list(w) for w in world]
