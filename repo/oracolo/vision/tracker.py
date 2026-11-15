"""Tracking in coordinate della planimetria: identità stabili per le persone, posa del muletto."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class Track:
    id: int
    xy: tuple
    speed: float
    conf: float
    age: int = 1  # frame in cui è stata vista
    last_t: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    raw_xy: tuple = (0.0, 0.0)


class PersonTracker:
    """Associazione greedy per distanza (con predizione di velocità); una traccia sparisce dopo ``max_miss`` s.

    Un'identità che salta (ID switch) crea una persona in più: il motore è prudente in quel caso.
    """

    def __init__(self, gate: float = 0.9, max_miss: float = 0.8, alpha: float = 0.55,
                 pos_alpha: float = 0.72, v_cap: float = 3.0):
        self.gate, self.max_miss, self.alpha, self.pos_alpha, self.v_cap = gate, max_miss, alpha, pos_alpha, v_cap
        self.tracks: dict = {}
        self._next = 1

    def update(self, t: float, meas: list) -> list:
        """``meas``: lista di (x, y, conf). Ritorna le tracce attive in questo istante (viste ora)."""
        pairs = []
        for tid, tr in self.tracks.items():
            dt = min(max(t - tr.last_t, 1e-3), 0.5)
            px, py = tr.xy[0] + tr.vx * dt, tr.xy[1] + tr.vy * dt
            for j, (x, y, _) in enumerate(meas):
                d = float(np.hypot(x - px, y - py))
                if d <= self.gate:
                    pairs.append((d, tid, j))
        pairs.sort()
        used_t, used_m, seen = set(), set(), []
        for _, tid, j in pairs:
            if tid in used_t or j in used_m:
                continue
            used_t.add(tid)
            used_m.add(j)
            x, y, c = meas[j]
            tr = self.tracks[tid]
            dt = max(t - tr.last_t, 1e-3)
            vx, vy = (x - tr.xy[0]) / dt, (y - tr.xy[1]) / dt
            sp = float(np.hypot(vx, vy))
            if sp <= self.v_cap:
                a_v = self.alpha if tr.age >= 2 else 0.75
                tr.vx = a_v * vx + (1 - a_v) * tr.vx
                tr.vy = a_v * vy + (1 - a_v) * tr.vy
            else:  # salto non plausibile: attenua senza azzerare la velocità stimata
                tr.vx *= 0.7
                tr.vy *= 0.7
            tr.speed = float(np.hypot(tr.vx, tr.vy)) if tr.age >= 2 else 0.0
            dt_p = min(dt, 0.35)
            pred_x, pred_y = tr.xy[0] + tr.vx * dt_p, tr.xy[1] + tr.vy * dt_p
            ap = self.pos_alpha
            tr.xy = (ap * x + (1 - ap) * pred_x, ap * y + (1 - ap) * pred_y)
            tr.raw_xy = (x, y)
            tr.conf, tr.last_t, tr.age = c, t, tr.age + 1
            seen.append(tr)
        for j, (x, y, c) in enumerate(meas):
            if j in used_m:
                continue
            tr = Track(self._next, (x, y), 0.0, c, 1, t, raw_xy=(x, y))
            self.tracks[self._next] = tr
            self._next += 1
            seen.append(tr)
        for tid in [k for k, tr in self.tracks.items() if t - tr.last_t > self.max_miss]:
            del self.tracks[tid]
        return seen


@dataclass
class VehiclePose:
    xy: tuple
    heading: float  # rad, sulla planimetria
    speed: float  # m/s misurata
    tracked: bool  # visto di recente


class VehicleTracker:
    """Posa del muletto (marker): filtro predittivo alpha-beta, velocità sugli ultimi ~0,20 s, direzione di marcia."""

    def __init__(self, alpha: float = 0.72, window: float = 0.20, lost_after: float = 1.0, v_heading: float = 0.25):
        self.alpha, self.window, self.lost_after, self.v_heading = alpha, window, lost_after, v_heading
        self.hist: deque = deque()
        self.xy: tuple | None = None
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.heading = 0.0
        self.last_t = -1e9
        self.speed = 0.0

    def update(self, t: float, xy, marker_heading: float):
        if self.xy is None or t - self.last_t > self.lost_after:
            self.xy = (float(xy[0]), float(xy[1]))
            self.vx = self.vy = 0.0
            self.speed = 0.0
            self.hist.clear()
        else:
            dt_p = min(max(t - self.last_t, 0.0), 0.35)
            pred_x = self.xy[0] + self.vx * dt_p
            pred_y = self.xy[1] + self.vy * dt_p
            a = self.alpha
            self.xy = (a * xy[0] + (1 - a) * pred_x, a * xy[1] + (1 - a) * pred_y)
        self.hist.append((t, self.xy))
        while self.hist and t - self.hist[0][0] > 0.6:
            self.hist.popleft()
        old = next((h for h in reversed(self.hist) if t - h[0] >= self.window), None)
        if old is not None:
            dt = t - old[0]
            dx, dy = self.xy[0] - old[1][0], self.xy[1] - old[1][1]
            self.vx, self.vy = dx / dt, dy / dt
            self.speed = float(np.hypot(self.vx, self.vy))
            moving = self.speed > self.v_heading
            self.heading = float(np.arctan2(dy, dx)) if moving else float(marker_heading)
        else:
            self.heading = float(marker_heading)
        self.last_t = t

    def pose(self, t: float) -> VehiclePose | None:
        if self.xy is None:
            return None
        return VehiclePose(self.xy, self.heading, self.speed, (t - self.last_t) <= self.lost_after)
