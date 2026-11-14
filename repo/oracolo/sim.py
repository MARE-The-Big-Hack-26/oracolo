"""Simulatore a ciclo chiuso: persone, sensori, motore, bus, macchina virtuale.

Modalità:
  none         nessuna limitazione (macchina a velocità di crociera)
  static_zone  limite fisso in una zona attorno all'incrocio + stop se vede una persona vicina
  reactive     stessa fisica di Oracolo ma ragiona SOLO su ciò che vede (niente zone cieche)
  oracolo      fisica completa: persone viste + zone cieche (fantasmi e sconosciuto)

Assunzione dichiarata: nel simulatore l'identità delle persone è perfetta (tracking ideale).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import shapely
from shapely.geometry import LineString, Point

from .engine import Oracle
from .geometry import visibility_polygon
from .machine import InProcessBus, MachineCommand, VirtualMachine
from .policy import PedParams, VehicleParams
from .scenes import t_junction

MODES = ("none", "static_zone", "reactive", "oracolo")


@dataclass
class PedSpec:
    id: int
    path: list
    t0: float = 0.0
    speed: float = 1.4
    vanish_at_end: bool = True

    def __post_init__(self):
        self._line = LineString(self.path)

    def pos(self, t: float):
        d = max(0.0, (t - self.t0) * self.speed)
        if d >= self._line.length:
            return None if self.vanish_at_end else tuple(self.path[-1])
        pt = self._line.interpolate(d)
        return (pt.x, pt.y)


@dataclass
class SensorSpec:
    kind: str = "fixed"  # fixed | vehicle
    pos: tuple | None = None
    eye_h: float = 2.5
    half_fov_deg: float | None = None
    max_range: float | None = None


@dataclass
class Scenario:
    scene: object
    path: LineString
    peds: list
    sensors: list
    params: VehicleParams = field(default_factory=VehicleParams)
    ped_params: PedParams = field(default_factory=PedParams)
    dt: float = 0.05
    t_max: float = 40.0
    zone: tuple = (6.0, 15.0)  # intervallo di s per static_zone
    zones: list | None = None  # più intervalli di s (se presente ha la precedenza su zone)
    zone_speed: float = 1.39  # m/s (5 km/h)


@dataclass
class Result:
    mode: str
    collision: bool  # contatto con il mezzo IN MOTO (v > v_contatto)
    t_collision: float | None
    min_dist: float
    t_end: float
    arrived: bool
    avg_speed: float
    slow_time: float
    stop_time: float
    watchdog_trips: int
    levels: dict
    log: list = field(default_factory=list)
    touch: bool = False  # sfioramento con il mezzo fermo (non è una collisione, ma si dichiara)


def t_junction_scenario(ped_t0=-1.0, ped_speed=1.4, onboard=False, params=None) -> Scenario:
    scene = t_junction()
    path = LineString([(1.0, 1.75), (19.0, 1.75)])
    peds = [PedSpec(1, [(11.0, 10.5), (11.0, 0.3)], t0=ped_t0, speed=ped_speed)]
    sensors = [SensorSpec("fixed", (1.0, 1.75), eye_h=2.5)]
    if onboard:
        sensors.append(SensorSpec("vehicle", None, eye_h=1.2, half_fov_deg=90.0, max_range=15.0))
    return Scenario(scene, path, peds, sensors, params=params or VehicleParams())


def run_scenario(sc: Scenario, mode: str, bus_kwargs: dict | None = None, log: bool = False, hook=None) -> Result:
    assert mode in MODES
    p, pp, dt = sc.params, sc.ped_params, sc.dt
    machine = VirtualMachine(sc.path, p)
    bus = InProcessBus(**(bus_kwargs or {}))
    oracle = Oracle(sc.scene, p, pp, use_fog=(mode == "oracolo"))
    fog = oracle.fog

    fixed_polys, fixed_mask = [], np.zeros_like(fog.walk)
    for sp in sc.sensors:
        if sp.kind == "fixed":
            poly = visibility_polygon(
                sp.pos, sc.scene, eye_h=sp.eye_h, target_h=1.0,
                max_range=sp.max_range,
            )
            fixed_polys.append(poly)
            fixed_mask |= fog.mask_from_poly(poly)

    est: dict = {}
    t, seq = 0.0, 0
    collision, t_col, touch, min_dist = False, None, False, np.inf
    dist_travelled, slow_time, stop_time = 0.0, 0.0, 0.0
    levels = {0: 0, 1: 0, 2: 0, 3: 0}
    out_log = []
    contact = p.half_width + pp.radius

    while t < sc.t_max and not machine.arrived():
        vpos = machine.pos()
        polys = list(fixed_polys)
        mask = fixed_mask
        for sp in sc.sensors:
            if sp.kind == "vehicle":
                poly = visibility_polygon(
                    vpos, sc.scene, eye_h=sp.eye_h, target_h=1.0,
                    heading=machine.heading(),
                    half_fov=np.deg2rad(sp.half_fov_deg or 180.0),
                    max_range=sp.max_range,
                )
                polys.append(poly)
                mask = mask | fog.mask_from_poly(poly)

        truth = {}
        for ped in sc.peds:
            pos = ped.pos(t)
            if pos is not None:
                truth[ped.id] = pos
        seen = {}
        for pid, pos in truth.items():
            if any(shapely.covers(poly, Point(pos)) for poly in polys):
                if pid in est:
                    v_new = np.hypot(pos[0] - est[pid][0][0], pos[1] - est[pid][0][1]) / dt
                    spd = 0.5 * est[pid][1] + 0.5 * v_new
                else:
                    spd = 0.0
                est[pid] = (pos, spd)
                seen[pid] = (pos, spd)
        for pid in list(est):
            if pid not in seen:
                del est[pid]

        s_now = machine.s
        ahead = min(p.horizon, sc.path.length - s_now)
        ss = np.arange(0.0, ahead + 1e-9, 0.25)
        pts = np.array([[q.x, q.y] for q in shapely.line_interpolate_point(sc.path, s_now + ss)])

        if mode == "none":
            limit, level, cause = p.v_max, 0, "nessuno"
        elif mode == "static_zone":
            in_zone = any(a <= s_now <= b for a, b in (sc.zones or [sc.zone]))
            limit = sc.zone_speed if in_zone else p.v_max
            for pos, _ in seen.values():
                if np.hypot(pos[0] - vpos[0], pos[1] - vpos[1]) < 2.0:
                    limit = 0.0
            level = 0 if limit >= p.v_max else (3 if limit == 0 else 1)
            cause = "zona_fissa"
        else:
            d = oracle.step(t, seen, mask, ss, pts)
            limit, level, cause = d.limit, d.level, d.cause

        seq += 1
        bus.send(MachineCommand(seq=seq, t_sent=t, speed_limit=limit, level=level, cause=cause, ttl=0.25), t)
        for c in bus.poll(t):
            machine.receive(c, t)
        machine.step(t, dt)

        vpos = machine.pos()
        for pos in truth.values():
            d_ = float(np.hypot(pos[0] - vpos[0], pos[1] - vpos[1]))
            min_dist = min(min_dist, d_)
            if d_ < contact:
                if machine.v > 0.15:
                    if not collision:
                        collision, t_col = True, t
                else:
                    touch = True
        dist_travelled += machine.v * dt
        if machine.v < 0.95 * machine.cruise:
            slow_time += dt
        if machine.v < 0.05:
            stop_time += dt
        levels[level] += 1
        if log:
            out_log.append(
                {"t": round(t, 3), "s": round(machine.s, 3), "v": round(machine.v, 3), "limit": round(limit, 3),
                 "level": level, "cause": cause, "seen": list(seen), "truth": {k: [round(x, 2) for x in v] for k, v in truth.items()}}
            )
        if hook is not None:
            hook(t, oracle, machine, truth, limit, level, cause)
        t += dt

    return Result(
        mode=mode, collision=collision, t_collision=t_col, touch=touch, min_dist=float(min_dist), t_end=t,
        arrived=machine.arrived(), avg_speed=dist_travelled / max(t, 1e-9), slow_time=slow_time,
        stop_time=stop_time, watchdog_trips=machine.watchdog_trips, levels=levels, log=out_log,
    )
