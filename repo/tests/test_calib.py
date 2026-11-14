import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from shapely.geometry import box  # noqa: E402

from oracolo.geometry import Occluder, Scene  # noqa: E402
from oracolo.scenes import t_junction  # noqa: E402
from oracolo.vision.calib import Calibration  # noqa: E402
from oracolo.vision.viz import draw_overlay, overlay_polys  # noqa: E402
from tests import synth  # noqa: E402


def _cal():
    img, world = synth.floor_pairs()
    return Calibration.from_pairs(img, world, (synth.W, synth.H), (2.5, -0.6), 2.2)


def test_omografia_recupera_punti_a_terra():
    cal = _cal()
    assert cal.rms_m < 1e-3
    for x, y in [(1.5, 2.0), (3.3, 1.7), (3.8, 3.0)]:
        u, v = synth.project([[x, y, 0]])[0]
        wx, wy = cal.to_world(u, v)
        assert abs(wx - x) < 5e-3 and abs(wy - y) < 5e-3


def test_correzione_quota_marker():
    cal = _cal()
    x, y = 3.0, 2.4
    u, v = synth.project([[x, y, 0.45]])[0]
    senza = cal.to_world(u, v, 0.0)
    con = cal.to_world(u, v, 0.45)
    assert np.hypot(senza[0] - x, senza[1] - y) > 0.3  # la parallasse è grande se non si corregge
    assert np.hypot(con[0] - x, con[1] - y) < 0.02


def test_roundtrip_immagine():
    cal = _cal()
    u, v = cal.to_image(2.0, 2.0)
    wx, wy = cal.to_world(u, v)
    assert abs(wx - 2.0) < 1e-6 and abs(wy - 2.0) < 1e-6


def test_footprint_dentro_i_confini():
    cal = _cal()
    scene = t_junction()
    from shapely.geometry import box
    b = box(0, 0, 5, 4)
    fp = cal.footprint(b)
    assert fp.within(b.buffer(1e-6)) and fp.area > 3.0
    assert fp.contains(__import__("shapely.geometry", fromlist=["Point"]).Point(2.5, 2.0))


def test_salvataggio(tmp_path):
    cal = _cal()
    p = tmp_path / "c.json"
    cal.save(p)
    c2 = Calibration.load(p)
    assert np.allclose(c2.H, cal.H) and c2.cam_xy == cal.cam_xy and c2.image_size == cal.image_size


def test_servono_4_punti():
    with pytest.raises(ValueError):
        Calibration.from_pairs([[0, 0], [1, 0], [1, 1]], [[0, 0], [1, 0], [1, 1]], (100, 100), (0, 0), 2.0)


def test_clipping_poligoni_dietro_camera():
    cal = _cal()
    scene = Scene(
        box(0.0, -3.0, 5.0, 4.0),
        [
            Occluder("dietro", box(1.0, -2.5, 3.0, -1.5), 1.2),
            Occluder("a_cavallo", box(1.5, -1.5, 2.5, 2.0), 0.8),
        ],
    )
    ov = overlay_polys(cal, scene)
    assert len(ov["bounds"]) >= 3
    assert ov["occluders"][0]["floor"] == []
    assert len(ov["occluders"][1]["floor"]) >= 3
    all_pts = ov["bounds"] + ov["occluders"][1]["floor"] + ov["occluders"][1]["top"]
    assert all(-4096 <= u <= 4096 and -4096 <= v <= 4096 for u, v in all_pts)
    fog = np.full((14, 10), 3, dtype=np.uint8)
    state = {"fog": {"minx": 0.0, "miny": -3.0, "res": 0.5}, "_fog": fog, "persons": [], "drivers": [], "out_of_bounds": []}
    out = draw_overlay(np.zeros((synth.H, synth.W, 3), dtype=np.uint8), cal, scene, state)
    assert out.shape[1] <= 960


def test_calibrazione_3d_pnp_recupera_posa_camera():
    wor3 = [
        [1.0, 1.4, 0.0], [4.0, 1.4, 0.0], [4.0, 3.5, 0.0], [1.0, 3.5, 0.0],
        [1.2, 2.0, 0.8], [3.8, 2.8, 1.2],
    ]
    img = synth.project(wor3)
    cal = Calibration.from_pairs(img, wor3, (synth.W, synth.H), (0.0, 0.0), 1.0)
    assert cal.rms_px < 0.5 and cal.rms_m < 0.01
    assert np.hypot(cal.cam_xy[0] - synth.CAM[0], cal.cam_xy[1] - synth.CAM[1]) < 0.05
    assert abs(cal.cam_h - synth.CAM[2]) < 0.05
    u, v = cal.to_image(2.5, 2.5, 0.75)
    u_ref, v_ref = synth.project([[2.5, 2.5, 0.75]])[0]
    assert np.hypot(u - u_ref, v - v_ref) < 1.0


def test_calibrazione_3d_con_distorsione_radiale():
    wor3 = np.array([
        [0.5, 1.0, 0.0], [4.5, 1.0, 0.0], [4.5, 3.8, 0.0], [0.5, 3.8, 0.0],
        [1.2, 1.8, 0.75], [3.8, 2.2, 0.85], [2.5, 3.4, 1.4],
    ], dtype=np.float64)
    rvec, _ = cv2.Rodrigues(synth.R)
    dist_true = np.array([-0.18, 0.0, 0.0, 0.0], dtype=np.float64)
    img_dist, _ = cv2.projectPoints(wor3, rvec, synth.T.reshape(3, 1), synth.K, dist_true)
    cal = Calibration.from_pairs(img_dist.reshape(-1, 2), wor3.tolist(), (synth.W, synth.H), (0.0, 0.0), 1.0)
    assert cal.rms_px < 1.0
    assert abs(cal.k1 - (-0.18)) < 0.03

