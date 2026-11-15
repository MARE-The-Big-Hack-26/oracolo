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
    det = Scripted()
    det.people = [(2.5, 1.9)]
    pipe = LivePipeline(room, None, person_detector=det)
    st = pipe.process(synth.render_frame(None), 0.0)
    assert st["calibrated"] is False
    assert len(st["persons"]) == 1
    assert st["persons"][0]["xy"] is None
    assert st["persons"][0]["box"] is not None


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


def _frame_con_marker_lavoratore(mid, x, y, z=1.2, black=0.20):
    """Marker ArUco (ID ``mid``) orizzontale a quota ``z`` sopra (x, y): lo porta un lavoratore."""
    import numpy as np
    img = synth.render_frame(None)
    full, h = black * 1.5, black * 0.75
    corners = [(x - h, y + h), (x + h, y + h), (x + h, y - h), (x - h, y - h)]
    dst = synth.project([[cx, cy, z] for cx, cy in corners]).astype(np.float32)
    m = synth.aruco_img(mid)
    sz = m.shape[0]
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [sz, 0], [sz, sz], [0, sz]]), dst)
    warped = cv2.warpPerspective(cv2.cvtColor(m, cv2.COLOR_GRAY2BGR), M, (synth.W, synth.H))
    mask = cv2.warpPerspective(np.full((sz, sz), 255, np.uint8), M, (synth.W, synth.H))
    img[mask > 0] = warped[mask > 0]
    return img


def test_marker_lavoratore_e_una_persona_in_posizione_giusta(room):
    pipe = LivePipeline(room, _cal(), person_detector=NoPersonDetector(),
                        marker=MarkerDetector(0, worker_height=1.2))
    st = pipe.process(_frame_con_marker_lavoratore(1, 3.2, 2.4), 0.0)
    assert st["vehicle"] is None  # ID 1 non è il muletto
    assert len(st["persons"]) == 1
    x, y = st["persons"][0]["xy"]
    assert math.hypot(x - 3.2, y - 2.4) < 0.15


def test_marker_lavoratore_sostituisce_il_riquadro_della_persona(room):
    det = Scripted()
    det.people = [(3.2, 2.4)]
    pipe = LivePipeline(room, _cal(), person_detector=det, marker=MarkerDetector(0, worker_height=1.2))
    u, v = synth.project([[3.2, 2.4, 1.2]])[0]
    # il riquadro HOG contiene il centro del marker -> una sola persona, non due
    det.detect = lambda frame: [Det("person", (u - 40, v - 60, u + 40, v + 160), 0.9, (float(u), float(v + 160)), 0.0, None, False)]
    st = pipe.process(_frame_con_marker_lavoratore(1, 3.2, 2.4), 0.0)
    assert len(st["persons"]) == 1
    assert math.hypot(st["persons"][0]["xy"][0] - 3.2, st["persons"][0]["xy"][1] - 2.4) < 0.15


def test_marker_ancora_non_e_un_lavoratore(room):
    pipe = LivePipeline(room, _cal(), person_detector=NoPersonDetector())
    st = pipe.process(_frame_con_marker_lavoratore(10, 3.2, 2.4), 0.0)
    assert st["persons"] == []
