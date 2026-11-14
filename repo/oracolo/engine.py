"""Oracle: l'API unica del motore, usata dal simulatore e dalla pipeline reale.

    oracle = Oracle(scene)
    decision = oracle.step(t, seen, vis_mask, s, pts, health, frame_age)

``seen``: id -> ((x, y), speed) delle persone viste ora.
``vis_mask``: maschera della griglia (Fog.mask_from_poly) dell'unione dei sensori.
``s, pts``: percorso della macchina in avanti (distanze e punti), campionato ogni ~0,25 m.
"""
from __future__ import annotations

from .fog import Fog
from .policy import Decision, PedParams, VehicleParams, compute_decision


class Oracle:
    def __init__(
        self,
        scene,
        params: VehicleParams | None = None,
        ped: PedParams | None = None,
        use_fog: bool = True,
        res: float = 0.2,
        ttl: float = 30.0,
        ghost_ttl: float = 20.0,
    ):
        self.scene = scene
        self.p = params or VehicleParams()
        self.ped = ped or PedParams()
        self.use_fog = use_fog
        self.fog = Fog(scene, res=res, ped_speed=self.ped.v_walk, ttl=ttl, ghost_ttl=ghost_ttl)

    def step(self, t, seen, vis_mask, s, pts, health=1.0, frame_age=0.0) -> Decision:
        self.fog.observe(t, vis_mask, {pid: pos for pid, (pos, _) in seen.items()})
        observed = [(pos, spd) for _, (pos, spd) in seen.items()]
        d_conf = d_unk = None
        if self.use_fog:
            dc, du = self.fog.distances()
            d_conf = self.fog.sample(dc, pts)
            d_unk = self.fog.sample(du, pts)
        return compute_decision(
            s, pts, observed, d_conf, d_unk, self.p, self.ped, health=health, frame_age=frame_age
        )
