"""Scene di esempio e caricamento/salvataggio JSON.

Il formato JSON è quello da compilare per il modellino fisico: misurate la
planimetria (in metri equivalenti, con scala dichiarata) e scrivete gli ostacoli.
"""
from __future__ import annotations

import json

from shapely.geometry import Polygon, box

from .geometry import Occluder, Scene


def t_junction() -> Scene:
    """Corsia principale (y 0..3,5) con un incrocio cieco a x 9,5..12,5 e scaffali alti 3 m."""
    bounds = box(0, 0, 20, 12)
    occ = [
        Occluder("scaffale_sx", box(0, 3.5, 9.5, 11.5), 3.0),
        Occluder("scaffale_dx", box(12.5, 3.5, 20, 11.5), 3.0),
    ]
    return Scene(bounds, occ)


def scene_to_dict(scene: Scene, scale_note: str = "") -> dict:
    return {
        "scale_note": scale_note,
        "bounds": [list(c) for c in scene.bounds.exterior.coords[:-1]],
        "occluders": [
            {"name": o.name, "height": o.height, "polygon": [list(c) for c in o.poly.exterior.coords[:-1]]}
            for o in scene.occluders
        ],
    }


def scene_from_dict(d: dict) -> Scene:
    bounds = Polygon(d["bounds"])
    occ = [Occluder(o["name"], Polygon(o["polygon"]), float(o["height"])) for o in d["occluders"]]
    return Scene(bounds, occ)


def save_scene(scene: Scene, path: str, scale_note: str = "") -> None:
    with open(path, "w") as f:
        json.dump(scene_to_dict(scene, scale_note), f, indent=2)


def load_scene(path: str) -> Scene:
    with open(path) as f:
        return scene_from_dict(json.load(f))
