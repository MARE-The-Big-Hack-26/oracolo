"""Rendering offline (matplotlib): vista della camera/planimetria + cabina del carrello.

Pannello sinistro: planimetria dal CAD con ciò che il sistema vede (verde), ricorda (grigio),
non sa (arancio), persona possibile nascosta (rosso), camere, carrello e persone.
Pannello destro: la schermata "cabina" che l'iPhone mostra al carrello (stessi colori e testi).
"""
from __future__ import annotations

import os
import shutil
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from matplotlib.patches import Polygon as MplPoly
from matplotlib.patches import Rectangle

from .cab import CAUSE_IT
from .policy import LEVEL_NAMES

CMAP = ListedColormap(["#ffffff00", "#cfe9d0", "#e4e4e4", "#f7c98b", "#e45757"])
LEVEL_COLORS = ["#1b8a3a", "#b58900", "#cc6a10", "#b3261e"]
SYMBOLS = ["▶", "△", "▼", "■"]


def draw_map(ax, scenario, fog, t, machine_xy, truth, level, trail=None):
    ax.clear()
    ext = [fog.minx, fog.minx + fog.nx * fog.res, fog.miny, fog.miny + fog.ny * fog.res]
    ax.imshow(fog.state_map(t), origin="lower", extent=ext, cmap=CMAP, vmin=0, vmax=4, interpolation="nearest")
    for o in scenario.scene.occluders:
        low = o.height < 1.5
        ax.add_patch(MplPoly(np.array(o.poly.exterior.coords), closed=True, fc="#b9b9b9" if low else "#4f4f4f",
                             ec="k", lw=0.8, zorder=3))
    xs, ys = scenario.path.xy
    ax.plot(xs, ys, "--", color="#335", lw=1, zorder=2)
    if trail:
        ax.plot([p[0] for p in trail], [p[1] for p in trail], "-", color=LEVEL_COLORS[level], lw=3, alpha=.5, zorder=4)
    for i, sp in enumerate(scenario.sensors):
        if sp.kind == "fixed":
            ax.plot(*sp.pos, marker="^", color="#0b3d91", ms=11, mec="w", zorder=7)
            ax.annotate(f"CAM {i + 1}", sp.pos, xytext=(0, 9), textcoords="offset points", ha="center",
                        fontsize=8, color="#0b3d91", weight="bold", zorder=8)
    for pid, (x, y) in (truth or {}).items():
        ax.plot(x, y, "o", color="#1f4fd8", ms=9, mec="w", zorder=6)
    hw = scenario.params.half_width
    ax.add_patch(Rectangle((machine_xy[0] - 0.9, machine_xy[1] - hw), 1.8, 2 * hw, fc=LEVEL_COLORS[level],
                           ec="k", lw=1.2, zorder=6))
    ax.set_aspect("equal")
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Camere fisse: cosa vedono, cosa non sanno", fontsize=11, loc="left")
    ax.legend(handles=[Patch(fc="#cfe9d0", label="visibile"), Patch(fc="#e4e4e4", label="ricordato libero"),
                       Patch(fc="#f7c98b", label="NON visibile (ignoto ≠ libero)"),
                       Patch(fc="#e45757", label="persona possibile qui")],
              loc="lower center", ncol=4, fontsize=7, frameon=False, bbox_to_anchor=(0.5, -0.08))


def draw_cab(ax, t, limit, level, cause, seq=None):
    ax.clear()
    ax.set_facecolor(LEVEL_COLORS[level])
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.text(0.5, 0.78, LEVEL_NAMES[level], ha="center", va="center", color="w", fontsize=30, weight="bold",
            transform=ax.transAxes)
    ax.text(0.5, 0.62, SYMBOLS[level], ha="center", va="center", color="w", fontsize=26, transform=ax.transAxes)
    ax.text(0.5, 0.44, f"{limit * 3.6:.1f} km/h", ha="center", va="center", color="w", fontsize=30, weight="bold",
            transform=ax.transAxes)
    ax.text(0.5, 0.22, CAUSE_IT.get(cause, cause), ha="center", va="center", color="w", fontsize=11,
            transform=ax.transAxes, wrap=True)
    ax.text(0.5, 0.04, f"cabina carrello (iPhone) · t={t:4.1f}s", ha="center", va="center", color="w",
            fontsize=8, alpha=.85, transform=ax.transAxes)


def render_video(scenario, out_path, mode="oracolo", every=3, fps=None, keep_frames=False, bus_kwargs=None):
    """Esegue lo scenario e scrive un mp4 (se c'è ffmpeg) o una cartella di PNG. Ritorna (risultato, percorso)."""
    from .sim import run_scenario

    frames_dir = os.path.splitext(out_path)[0] + "_frames"
    os.makedirs(frames_dir, exist_ok=True)
    fig = plt.figure(figsize=(13, 5.4), dpi=80)
    gs = fig.add_gridspec(1, 2, width_ratios=[3.1, 1], wspace=0.06)
    axm, axc = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    n, written, trail = [0], [], []

    def hook(t, oracle, machine, truth, limit, level, cause):
        n[0] += 1
        trail.append(machine.pos())
        if n[0] % every:
            return
        draw_map(axm, scenario, oracle.fog, t, machine.pos(), truth, level, trail)
        draw_cab(axc, t, limit, level, cause)
        f = f"{frames_dir}/f_{len(written):05d}.png"
        fig.savefig(f, facecolor="white")
        written.append(f)

    res = run_scenario(scenario, mode, bus_kwargs=bus_kwargs, hook=hook)
    plt.close(fig)
    fps = fps or round(1.0 / (scenario.dt * every))
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", f"{frames_dir}/f_%05d.png",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", out_path],
                       check=True)
        if not keep_frames:
            shutil.rmtree(frames_dir, ignore_errors=True)
        return res, out_path
    return res, frames_dir
