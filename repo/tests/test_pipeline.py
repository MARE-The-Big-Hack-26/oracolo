import math

import pytest

cv2 = pytest.importorskip("cv2")

from oracolo.cad import load_dxf  # noqa: E402
from oracolo.vision.calib import Calibration  # noqa: E402
from oracolo.vision.detectors import Det, MarkerDetector, NoPersonDetector  # noqa: E402
from oracolo.vision.pipeline import LivePipeline, frame_health  # noqa: E402
from tests import synth  # noqa: E402


@pytest.fixture(scope="module")
def room():
    from pathlib import Path
    dxf = Path(__file__).resolve().parent.parent / "scenarios" / "stanza.dxf"
    scene, _ = load_dxf(dxf)
    return scene


def _cal():
    img, world = synth.floor_pairs()
    return Calibration.from_pairs(img, world, (synth.W, synth.H), (2.5, -0.6), 2.2)


class Scripted:
    """Rilevatore di persone 'finto': posizioni note in metri -> riquadri nell'immagine."""

    def __init__(self):
        self.people = []

    def detect(self, frame):
        out = []
        for x, y in self.people:
            u, v = synth.project([[x, y, 0]])[0]
            out.append(Det("person", (u - 40, v - 160, u + 40, v), 0.9, (float(u), float(v)), 0.0, None, False))
        return out


def test_muletto_posizione_e_direzione(room):
    pipe = LivePipeline(room, _cal(), person_detector=NoPersonDetector())
    st = pipe.process(synth.render_frame((2.5, 1.2, math.pi / 2)), 0.0)
    v = st["vehicle"]
    assert v is not None and v["tracked"]
    assert math.hypot(v["xy"][0] - 2.5, v["xy"][1] - 1.2) < 0.06  # corretto per la quota del marker
    assert abs(v["heading"] - math.pi / 2) < 0.12
    assert st["decision"] is not None and st["decision"]["limit"] <= pipe.p.v_max


def test_senza_marker_nessun_comando(room):
    pipe = LivePipeline(room, _cal(), person_detector=NoPersonDetector())
    st = pipe.process(synth.render_frame(None), 0.0)
    assert st["vehicle"] is None and st["decision"] is None


def test_persona_davanti_rallenta_o_ferma(room):
    det = Scripted()
    pipe = LivePipeline(room, _cal(), person_detector=det)
    base = pipe.process(synth.render_frame((2.5, 1.2, math.pi / 2)), 0.0)
    det.people = [(2.5, 1.9)]  # 0,7 m davanti al muletto, sulla traiettoria
    st = pipe.process(synth.render_frame((2.5, 1.2, math.pi / 2)), 0.1)
    assert len(st["persons"]) == 1
    assert st["decision"]["level"] >= 2 and st["decision"]["limit"] < base["decision"]["limit"] + 1e-9


def test_conducente_dietro_il_muletto_e_escluso(room):
    det = Scripted()
    det.people = [(2.5, 0.65)]  # dietro la sedia (che guarda verso +y)
    pipe = LivePipeline(room, _cal(), person_detector=det)
    st = pipe.process(synth.render_frame((2.5, 1.2, math.pi / 2)), 0.0)
    assert st["persons"] == [] and len(st["drivers"]) == 1


def test_velocita_misurata_del_muletto(room):
    pipe = LivePipeline(room, _cal(), person_detector=NoPersonDetector())
    st = None
    for i in range(15):
        t = i * 0.1
        st = pipe.process(synth.render_frame((2.5, 1.0 + 0.8 * t, math.pi / 2)), t)
    assert abs(st["vehicle"]["speed"] - 0.8) < 0.2


def test_stato_senza_calibrazione(room):
    pipe = LivePipeline(room, None)
    st = pipe.process(synth.render_frame(None), 0.0)
    assert st["calibrated"] is False


def test_marker_detector_ignora_altri_id():
    import numpy as np
    img = np.full((400, 400, 3), 255, np.uint8)
    m = synth.aruco_img(mid=5)
    img[50:50 + m.shape[0], 50:50 + m.shape[1]] = m[:, :, None]
    assert MarkerDetector(marker_id=0).detect(img) == []
    assert len(MarkerDetector(marker_id=5).detect(img)) == 1


def test_frame_health():
    import numpy as np
    assert frame_health(synth.render_frame(None)) == 1.0
    assert frame_health(np.zeros((100, 100, 3), np.uint8)) < 0.7
