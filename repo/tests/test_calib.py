import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from oracolo.scenes import t_junction  # noqa: E402
from oracolo.vision.calib import Calibration  # noqa: E402
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
