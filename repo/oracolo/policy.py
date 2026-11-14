"""Politica di velocità: dalla fisica ai livelli di pericolo.

Idea unica per tutte le minacce (persona vista o persona possibile in zona cieca):
il tempo che la minaccia impiega a raggiungere la traiettoria della macchina
(TTR, time-to-reach) deve essere maggiore del tempo che la macchina impiega a
fermarsi. Con decelerazione ``a`` e latenza totale ``T`` (sensing + decisione +
comunicazione + attuazione):

    tempo di arresto da velocità v      T + v/a
    condizione di sicurezza             T + v/a <= TTR
    velocità sicura al punto            v_safe = max(0, a * (TTR - T))

Per arrivare a quel punto la macchina deve poter rallentare in tempo (curva di
frenata): a distanza s dal punto, con margine m,

    v_limit(s) = -a*T + sqrt( (a*T)^2 + 2*a*(s - m) + v_safe^2 )

Il limite finale è il minimo su tutti i punti del percorso in avanti. I livelli
(NORMALE, ATTENZIONE, RALLENTA, FERMA) derivano dal rapporto limite/v_max, non
da soglie arbitrarie su distanze.

AVVERTENZA: i parametri sono ipotesi dichiarate (vedi VehicleParams). Questo è
un prototipo di ricerca, non una funzione di sicurezza certificata.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

LEVEL_NAMES = ["NORMALE", "ATTENZIONE", "RALLENTA", "FERMA"]


@dataclass
class VehicleParams:
    v_max: float = 2.2  # m/s (circa 8 km/h)
    a_brake: float = 1.5  # m/s^2, decelerazione di arresto
    t_sys: float = 0.25  # s, sensing + decisione + comunicazione
    t_act: float = 0.15  # s, ritardo di attuazione della macchina
    margin: float = 0.5  # m, margine di arresto
    half_width: float = 0.6  # m
    horizon: float = 12.0  # m di percorso guardati in avanti
    max_frame_age: float = 0.30  # s oltre cui il sensore è considerato fermo

    @property
    def T(self) -> float:
        return self.t_sys + self.t_act


@dataclass
class PedParams:
    v_walk: float = 1.5  # m/s, ipotesi prudente di velocità massima di camminata
    radius: float = 0.3  # m


@dataclass
class Decision:
    limit: float
    level: int
    cause: str
    binding_s: float | None = None
    ttr_min: float | None = None
    sight_distance: float | None = None
    details: dict = field(default_factory=dict)

    @property
    def level_name(self) -> str:
        return LEVEL_NAMES[self.level]


def stopping_distance(v: float, p: VehicleParams) -> float:
    return v * p.T + v * v / (2.0 * p.a_brake)


def stopping_time(v: float, p: VehicleParams) -> float:
    return p.T + v / p.a_brake


def v_safe_from_ttr(ttr, p: VehicleParams):
    """Velocità massima con cui la macchina si ferma prima che la minaccia arrivi."""
    return np.maximum(0.0, p.a_brake * (np.asarray(ttr, dtype=float) - p.T))


def v_limit_at_distance(s, v_safe, p: VehicleParams):
    """Curva di frenata: velocità massima a distanza s per essere a v_safe al punto."""
    s = np.asarray(s, dtype=float)
    vs = np.minimum(np.asarray(v_safe, dtype=float), p.v_max * 4.0)
    aT = p.a_brake * p.T
    sm = s - p.margin
    body = np.sqrt(aT * aT + 2.0 * p.a_brake * np.maximum(sm, 0.0) + vs * vs) - aT
    return np.where(sm > 0, body, vs)


def v_from_sight_distance(d: float, p: VehicleParams) -> float:
    """Velocità massima per fermarsi entro d (ostacolo fermo oltre la zona cieca)."""
    return float(v_limit_at_distance(d, 0.0, p))


def level_from_limit(limit: float, v_max: float) -> int:
    r = limit / v_max
    if r < 0.05:
        return 3
    if r < 0.60:
        return 2
    if r < 0.95:
        return 1
    return 0


CAUSES = {0: "nessuno", 1: "osservato", 2: "persona_nascosta", 3: "zona_non_osservata"}


def compute_decision(
    s,
    pts,
    observed,
    d_conf,
    d_unk,
    p: VehicleParams,
    ped: PedParams,
    health: float = 1.0,
    frame_age: float = 0.0,
) -> Decision:
    """s: distanze lungo il percorso (n,), pts: punti (n,2), observed: [(pos, speed)],
    d_conf / d_unk: distanze dei punti da persona nascosta / zona sconosciuta (n,) o None."""
    s = np.asarray(s, dtype=float)
    pts = np.asarray(pts, dtype=float)
    n = len(s)
    contact = ped.radius + p.half_width
    ttr = np.full(n, np.inf)
    cause = np.zeros(n, dtype=int)

    def _merge(tt, cid):
        upd = tt < ttr
        ttr[upd] = tt[upd]
        cause[upd] = cid

    for pos, spd in observed:
        v = max(ped.v_walk, 1.2 * float(spd))
        d = np.hypot(pts[:, 0] - pos[0], pts[:, 1] - pos[1])
        _merge(np.maximum(0.0, d - contact) / v, 1)
    if d_conf is not None:
        _merge(np.maximum(0.0, np.asarray(d_conf) - contact) / ped.v_walk, 2)
    if d_unk is not None:
        _merge(np.maximum(0.0, np.asarray(d_unk) - contact) / ped.v_walk, 3)

    v_safe = v_safe_from_ttr(ttr, p)
    v_lim = v_limit_at_distance(s, v_safe, p)
    k = int(np.argmin(v_lim)) if n else 0
    limit = float(min(p.v_max, v_lim[k])) if n else p.v_max
    c = CAUSES[int(cause[k])] if limit < p.v_max - 1e-9 else "nessuno"

    zero = np.where(ttr <= 0.0)[0]
    sight = float(s[zero[0]]) if len(zero) else float(s[-1]) if n else None

    # affidabilità: se non posso garantire, vado verso lo stato sicuro
    if frame_age > p.max_frame_age:
        limit, c = 0.0, "affidabilita_persa"
    elif health < 0.3:
        limit, c = 0.0, "affidabilita_persa"
    elif health < 0.7:
        limit = min(limit, p.v_max * (health - 0.3) / 0.4)
        c = "scena_degradata" if limit < p.v_max - 1e-9 else c

    level = level_from_limit(limit, p.v_max)
    if level == 0:
        c = "nessuno"  # a livello NORMALE non c'è nulla da segnalare
    return Decision(
        limit=limit,
        level=level,
        cause=c,
        binding_s=float(s[k]) if n else None,
        ttr_min=float(ttr[k]) if n and np.isfinite(ttr[k]) else None,
        sight_distance=sight,
    )
