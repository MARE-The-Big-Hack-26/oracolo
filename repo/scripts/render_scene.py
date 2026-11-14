"""Genera il video della demo (planimetria + cabina). Uso: python scripts/render_scene.py out/demo.mp4 [--mode oracolo] [--dxf file.dxf]"""
import argparse
import os

from oracolo.render import render_video
from oracolo.warehouse import warehouse_scenario

ap = argparse.ArgumentParser()
ap.add_argument("out", nargs="?", default="out/demo.mp4")
ap.add_argument("--mode", default="oracolo", choices=["none", "static_zone", "reactive", "oracolo"])
ap.add_argument("--dxf", default=None)
a = ap.parse_args()
os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
res, path = render_video(warehouse_scenario(a.dxf), a.out, a.mode)
print(f"{path}: collisione={res.collision} distanza minima={res.min_dist:.2f} m transito={res.t_end:.1f} s")
