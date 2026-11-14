"""Mappa epistemica: cosa so, cosa ricordo, cosa non so (fog of war con contaminazione).

Griglia sull'area percorribile. Per ogni cella:

* VISIBILE            vista ora da almeno un sensore
* RICORDATO_LIBERO    non vista ora, vista libera di recente e nessun fronte di
                      contaminazione l'ha ancora raggiunta
* SCONOSCIUTO         mai vista, vista troppo tempo fa o raggiunta da cella sconosciuta
* PERSONA_NASCOSTA    raggiungibile da una persona vista entrare in zona cieca (fantasma)

Regola chiave: una cella nascosta può essere occupata se una persona ha potuto
raggiungerla camminando attraverso celle nascoste. Il fronte avanza a velocità
``ped_speed`` (contaminazione); le celle visibili vengono ripulite. Se una persona
rientra in vista, il suo fantasma viene riconciliato.

Il fronte usa un dilatazione 3x3 (conservativa: sulle diagonali è fino a 1,41 volte
più veloce della velocità reale).
"""
from __future__ import annotations

import numpy as np
import shapely
from scipy import ndimage

VISIBILE, RICORDATO_LIBERO, SCONOSCIUTO, PERSONA_NASCOSTA = 1, 2, 3, 4
STATE_NAMES = {
    0: "non_percorribile",
    VISIBILE: "visibile",
    RICORDATO_LIBERO: "ricordato_libero",
    SCONOSCIUTO: "sconosciuto",
    PERSONA_NASCOSTA: "persona_nascosta",
}


class Fog:
    def __init__(self, scene, res=0.2, ped_speed=1.5, ttl=30.0, ghost_ttl=20.0, ghost_radius=0.4):
        minx, miny, maxx, maxy = scene.bounds.bounds
        self.minx, self.miny, self.res = minx, miny, res
        self.nx = int(np.ceil((maxx - minx) / res))
        self.ny = int(np.ceil((maxy - miny) / res))
        xs = minx + (np.arange(self.nx) + 0.5) * res
        ys = miny + (np.arange(self.ny) + 0.5) * res
        self.X, self.Y = np.meshgrid(xs, ys)
        self.walk = shapely.contains_xy(scene.walkable(), self.X, self.Y)
        self.visible = np.zeros_like(self.walk)
        self.last_seen = np.full(self.walk.shape, -np.inf)
        self.unknown = self.walk.copy()
        self.ghosts: dict = {}
        self.prev_seen: dict = {}
        self.events: list = []
        self.ped_speed = ped_speed
        self.ttl = ttl
        self.ghost_ttl = ghost_ttl
        self.ghost_radius = ghost_radius
        self.t_prev = None
        self._acc = 0.0
        self._struct = np.ones((3, 3), bool)

    # -- utilità ---------------------------------------------------------
    def mask_from_poly(self, poly) -> np.ndarray:
        return shapely.contains_xy(poly, self.X, self.Y) & self.walk

    def _spread(self, grid, k, hidden):
        for _ in range(k):
            grid = ndimage.binary_dilation(grid, structure=self._struct) & hidden
        return grid

    def _disc(self, pos, r):
        return np.hypot(self.X - pos[0], self.Y - pos[1]) <= r

    def sample(self, arr, pts) -> np.ndarray:
        pts = np.asarray(pts)
        ix = np.clip(((pts[:, 0] - self.minx) / self.res).astype(int), 0, self.nx - 1)
        iy = np.clip(((pts[:, 1] - self.miny) / self.res).astype(int), 0, self.ny - 1)
        return arr[iy, ix]

    # -- aggiornamento ---------------------------------------------------
    def observe(self, t: float, vis_mask: np.ndarray, seen: dict) -> None:
        """``seen``: id -> (x, y) delle persone viste in questo frame."""
        dt = 0.0 if self.t_prev is None else max(0.0, t - self.t_prev)
        self.t_prev = t
        vis = vis_mask & self.walk
        hidden = self.walk & ~vis
        self.visible = vis

        self._acc += self.ped_speed * dt
        k = int(self._acc // self.res)
        self._acc -= k * self.res
        if k > 0:
            self.unknown = self._spread(self.unknown, k, hidden)
            for g in self.ghosts.values():
                g["grid"] = self._spread(g["grid"], k, hidden)

        self.unknown &= hidden
        for g in self.ghosts.values():
            g["grid"] &= hidden
        self.last_seen[vis] = t

        # memoria scaduta: la cella torna sconosciuta
        self.unknown |= hidden & ((t - self.last_seen) > self.ttl)

        # persone sparite dalla vista -> fantasma
        for pid, pos in self.prev_seen.items():
            if pid not in seen:
                grid = self._disc(pos, self.ghost_radius) & hidden
                if grid.any():
                    self.ghosts[pid] = {"grid": grid, "t_lost": t, "pos": tuple(pos)}
                    self.events.append((t, "entrato_in_zona_cieca", pid))

        # persone riapparse -> riconciliate
        for pid in seen:
            if pid in self.ghosts:
                del self.ghosts[pid]
                self.events.append((t, "riconciliato", pid))

        # fantasmi vecchi o vuoti
        for pid in list(self.ghosts):
            g = self.ghosts[pid]
            if not g["grid"].any():
                del self.ghosts[pid]
                self.events.append((t, "fantasma_svuotato", pid))
            elif t - g["t_lost"] > self.ghost_ttl:
                self.unknown |= g["grid"]
                del self.ghosts[pid]
                self.events.append((t, "non_riconciliato", pid))

        self.prev_seen = {pid: tuple(pos) for pid, pos in seen.items()}

    # -- interrogazione --------------------------------------------------
    def confirmed_mask(self) -> np.ndarray:
        out = np.zeros_like(self.walk)
        for g in self.ghosts.values():
            out |= g["grid"]
        return out

    def _edt(self, mask) -> np.ndarray:
        if not mask.any():
            return np.full(mask.shape, np.inf)
        return ndimage.distance_transform_edt(~mask) * self.res

    def distances(self):
        """(distanza da persona nascosta, distanza da zona sconosciuta) in metri, per cella."""
        conf = self.confirmed_mask()
        return self._edt(conf), self._edt(self.unknown & ~conf)

    def state_map(self, t: float) -> np.ndarray:
        s = np.zeros(self.walk.shape, int)
        s[self.walk] = RICORDATO_LIBERO
        s[self.unknown] = SCONOSCIUTO
        s[self.confirmed_mask()] = PERSONA_NASCOSTA
        s[self.visible] = VISIBILE
        return s

    def info_age(self, t: float) -> np.ndarray:
        """Secondi dall'ultima volta che la cella è stata vista (inf se mai)."""
        return t - self.last_seen
