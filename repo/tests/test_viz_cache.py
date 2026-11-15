"""draw_overlay: i contorni statici sono in cache ma si aggiornano se calibrazione o scena cambiano."""
import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from oracolo.cad import scene_from_spec  # noqa: E402
from oracolo.vision import viz  # noqa: E402
from oracolo.vision.calib import Calibration  # noqa: E402
from tests import synth  # noqa: E402


def _setup():
    img, world = synth.floor_pairs()
    calib = Calibration.from_pairs(img, world, [synth.W, synth.H], [2.5, -0.6], 2.2)
    scene = scene_from_spec({"perimetro": [0, 0, 5, 4],
                             "obstacles": [{"name": "A", "x": 1.0, "y": 1.0, "w": 1.0, "d": 0.8, "height": 1.5}]})
    return calib, scene, synth.render_frame((2.5, 1.2, 1.5708))


def _draw(frame, calib, scene):
    return viz.draw_overlay(frame, calib, scene, {"persons": [], "decision": None}, 960)


def test_cache_riusata_e_identica():
    calib, scene, frame = _setup()
    viz._OUTLINE_CACHE.clear()
    a = _draw(frame, calib, scene)
    assert viz._OUTLINE_CACHE.get("lines")
    lines_obj = viz._OUTLINE_CACHE["lines"]
    b = _draw(frame, calib, scene)
    assert viz._OUTLINE_CACHE["lines"] is lines_obj  # nessun ricalcolo
    assert np.array_equal(a, b)


def test_cache_si_invalida_se_cambia_altezza_camera_in_place():
    calib, scene, frame = _setup()
    viz._OUTLINE_CACHE.clear()
    a = _draw(frame, calib, scene)
    calib.cam_h = 3.4  # la pipeline lo fa in place (set_camera_pose)
    b = _draw(frame, calib, scene)
    viz._OUTLINE_CACHE.clear()
    fresh = _draw(frame, calib, scene)
    assert np.array_equal(b, fresh)   # la cache non restituisce contorni vecchi
    assert not np.array_equal(a, b)   # e la quota dei bordi superiori e' davvero cambiata


def test_cache_si_invalida_se_cambia_scena():
    calib, scene, frame = _setup()
    viz._OUTLINE_CACHE.clear()
    a = _draw(frame, calib, scene)
    scene2 = scene_from_spec({"perimetro": [0, 0, 5, 4]})
    b = _draw(frame, calib, scene2)
    assert not np.array_equal(a, b)
