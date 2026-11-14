"""Benchmark in simulazione sul magazzino (CAD) per diverse posizioni delle camere fisse.

    python -m oracolo.bench --runs 30

Stampa tabelle Markdown da incollare nel README. Sono numeri di SIMULAZIONE (identità dei
pedoni perfetta, nessun rumore del sensore): vanno dichiarati come tali e affiancati
ai risultati sulle clip reali.
Collisione = contatto con il mezzo IN MOTO (v > 0,15 m/s); lo sfioramento con il mezzo fermo si conta a parte.
"""
from __future__ import annotations

import argparse

import numpy as np

from .sim import MODES, run_scenario
from .warehouse import coverage, warehouse_scenario

CONFIGS = {
    "1 camera a fine corsia": [(1.0, 9.75)],
    "1 camera sull'incrocio": [(10.5, 9.75)],
    "2 camere sugli incroci": [(10.5, 9.75), (20.5, 9.75)],
    "3 camere": [(1.0, 9.75), (10.5, 9.75), (20.5, 9.75)],
}


def cases(n: int, seed: int = 1):
    rng = np.random.default_rng(seed)
    return [((float(rng.uniform(-2.5, 1.5)), float(rng.uniform(1.5, 6.0))), float(rng.uniform(1.2, 1.8))) for _ in range(n)]


def run_batch(n: int = 30, seed: int = 1, configs=None, modes=MODES, bus_kwargs=None) -> list:
    rows = []
    cs = cases(n, seed)
    for name, cams in (configs or CONFIGS).items():
        cov = coverage(warehouse_scenario().scene, cams)
        for mode in modes:
            res = [run_scenario(warehouse_scenario(ped_dt=pd, ped_speed=sp, cameras=cams), mode, bus_kwargs=bus_kwargs)
                   for pd, sp in cs]
            rows.append({"config": name, "coverage": cov, "mode": mode, "runs": n,
                         "collisions": int(sum(r.collision for r in res)),
                         "touches": int(sum(r.touch for r in res)),
                         "min_dist_m": float(min(r.min_dist for r in res)),
                         "mean_transit_s": float(np.mean([r.t_end for r in res]))})
    return rows


def to_markdown(rows: list) -> str:
    head = ("| Camere fisse | Copertura | Modalità | Collisioni | Sfioramenti (mezzo fermo) | Transito medio |\n"
            "|---|---|---|---|---|---|\n")
    body = [f"| {r['config']} | {r['coverage'] * 100:.0f}% | {r['mode']} | {r['collisions']}/{r['runs']} | "
            f"{r['touches']} | {r['mean_transit_s']:.1f} s |" for r in rows]
    return head + "\n".join(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    print(to_markdown(run_batch(a.runs, a.seed)))


if __name__ == "__main__":
    main()
