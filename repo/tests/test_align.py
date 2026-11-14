"""Allineamento CAD <-> video con ancore ArUco a terra (camera sintetica, nessun hardware)."""
import json
import time
import urllib.error
import urllib.request

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from oracolo.cad import scene_from_spec  # noqa: E402
from oracolo.vision.align import AnchorSet, reprojection_rms  # noqa: E402
from oracolo.vision.detectors import NoPersonDetector  # noqa: E402
from oracolo.vision.pipeline import LivePipeline  # noqa: E402
from oracolo.vision.server import LiveApp, serve  # noqa: E402
from tests import synth  # noqa: E402

CAMERA = (2.5, -0.6, 2.2)  # = tests.synth.CAM
VEH = (2.5, 1.2, 1.5708)


def anchors(black=0.20):
    return AnchorSet(black, {i: (x, y, 0.0) for i, (x, y) in synth.ANCHOR_POS.items()})


def make_pipe(anchor_set="default", calib=None):
    scene = scene_from_spec({"perimetro": [0, 0, 5, 4]})
    a = anchors() if anchor_set == "default" else anchor_set
    return LivePipeline(scene, calib, person_detector=NoPersonDetector(), anchors=a)


def feed(pipe, t, n, ids=(10, 11, 12, 13), vehicle=VEH, dt=0.1):
    st = None
    for _ in range(n):
        st = pipe.process(synth.render_with_anchors(vehicle, ids=ids), t)
        t += dt
    return st, t


def move_camera(monkeypatch, cam, target):
    cam = np.array(cam, float)
    f = np.array(target, float) - cam
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1.0])
    r /= np.linalg.norm(r)
    R = np.stack([r, np.cross(f, r), f])
    monkeypatch.setattr(synth, "R", R)
    monkeypatch.setattr(synth, "T", -R @ cam)


@pytest.fixture()
def calibrated():
    pipe = make_pipe()
    st, t = feed(pipe, 0.0, 6)
    cal, info = pipe.calibrate_from_anchors(t, camera=CAMERA)
    pipe.set_calibration(cal)
    return pipe, t, info


# ---- configurazione ------------------------------------------------------------------------------------
def test_anchorset_json_roundtrip_and_shorthand(tmp_path):
    a = anchors()
    a.save(tmp_path / "a.json")
    b = AnchorSet.load(tmp_path / "a.json")
    assert b.size_m == 0.2 and b.anchors == a.anchors and b.camera is None
    c = AnchorSet.from_dict({"size_m": 0.15, "anchors": {"10": [1, 1], "11": [4, 1, 90], "12": [4, 3]},
                             "camera": {"x": 2.5, "y": -0.6, "h": 2.2}})
    assert c.anchors[11] == (4.0, 1.0, 90.0) and c.camera == (2.5, -0.6, 2.2)


@pytest.mark.parametrize("bad", [
    {"size_m": 0.2, "anchors": {"10": [1, 1], "11": [4, 1]}},                      # meno di 3
    {"size_m": 0.2, "anchors": {"10": [1, 1], "11": [2, 1], "12": [3, 1]}},       # allineate
    {"size_m": 0.2, "anchors": {"0": [1, 1], "11": [4, 1], "12": [4, 3]}},        # id 0 = muletto
    {"size_m": 5.0, "anchors": {"10": [1, 1], "11": [4, 1], "12": [4, 3]}},       # lato implausibile
    {"size_m": 0.2},                                                              # manca anchors
])
def test_anchorset_rejects_bad_config(bad):
    with pytest.raises(ValueError):
        AnchorSet.from_dict(bad)


def test_anchor_corners_follow_convention():
    a = AnchorSet(0.2, {10: (2.0, 3.0, 0.0), 11: (2.0, 3.0, 90.0), 12: (0, 0, 0)})
    assert a.corners_world(10) == pytest.approx(np.array([[1.9, 3.1], [2.1, 3.1], [2.1, 2.9], [1.9, 2.9]]))
    # ruotato di 90° antiorario: il lato superiore guarda verso -X
    assert a.corners_world(11)[0] == pytest.approx([1.9, 2.9])


# ---- calibrazione automatica ---------------------------------------------------------------------------
def test_auto_calibration_from_anchors_places_the_chair(calibrated):
    pipe, t, info = calibrated
    assert info["rms_m"] < 0.03 and info["ids"] == [10, 11, 12, 13] and info["cam_source"] == "indicata nel pannello"
    st, _ = feed(pipe, t, 8)
    assert st["calibrated"] and st["align"]["status"] == "OK" and st["align"]["rms_m"] < 0.03
    assert st["health"] == 1.0
    assert st["vehicle"]["xy"] == pytest.approx([2.5, 1.2], abs=0.2)  # muletto posizionato col CAD, senza clic


def test_resaving_anchors_keeps_the_markers_already_seen():
    """Il pulsante «Calibra da ancore» risalva prima le ancore: non deve azzerare ciò che si è appena visto."""
    pipe = make_pipe()
    _, t = feed(pipe, 0.0, 4)
    pipe.set_anchors(anchors())
    assert pipe.process(synth.render_with_anchors(VEH), t)["align"]["n_seen"] == 4
    pipe.calibrate_from_anchors(t, camera=CAMERA)  # non solleva


def test_before_calibration_reports_anchors_ready():
    pipe = make_pipe()
    st, _ = feed(pipe, 0.0, 4)
    assert not st["calibrated"] and st["align"]["status"] == "SENZA_CALIBRAZIONE"
    assert st["align"]["ready"] and st["align"]["n_seen"] == 4


def test_calibration_needs_three_visible_anchors_and_camera_position():
    pipe = make_pipe()
    _, t = feed(pipe, 0.0, 4, ids=(10, 11))
    with pytest.raises(ValueError, match="almeno 3"):
        pipe.calibrate_from_anchors(t, camera=CAMERA)
    pipe2 = make_pipe()
    _, t = feed(pipe2, 0.0, 4)
    with pytest.raises(ValueError, match="dove sta la camera"):  # niente stima automatica della camera: inaffidabile
        pipe2.calibrate_from_anchors(t)


def test_camera_position_from_json_or_previous_calibration():
    a = AnchorSet.from_dict({**anchors().to_dict(), "camera": {"x": 2.5, "y": -0.6, "h": 2.2}})
    pipe = make_pipe(a)
    _, t = feed(pipe, 0.0, 4)
    cal, info = pipe.calibrate_from_anchors(t)
    assert info["cam_source"] == "indicata nel JSON delle ancore" and info["cam"] == [2.5, -0.6, 2.2]
    pipe.set_calibration(cal)
    a2 = anchors()
    pipe.set_anchors(a2)
    _, t = feed(pipe, t, 4)
    assert pipe.calibrate_from_anchors(t)[1]["cam_source"] == "dalla calibrazione precedente"


# ---- controllo continuo --------------------------------------------------------------------------------
def test_manual_calibration_stays_an_alternative_and_is_checked_by_anchors():
    img, world = synth.floor_pairs()
    from oracolo.vision.calib import Calibration
    cal = Calibration.from_pairs(img, world, [synth.W, synth.H], [2.5, -0.6], 2.2)
    pipe = make_pipe(calib=cal)
    st, _ = feed(pipe, 0.0, 6)
    assert st["calibrated"] and st["align"]["status"] == "OK"


def test_moved_camera_is_not_coincident_and_commands_stop(calibrated, monkeypatch):
    pipe, t, _ = calibrated
    st, t = feed(pipe, t, 6)
    assert st["align"]["status"] == "OK"
    move_camera(monkeypatch, (2.9, -0.6, 2.2), (2.5, 2.2, 0.0))  # treppiede urtato: 40 cm di lato
    states = []
    for _ in range(6):
        st, t = feed(pipe, t, 1)
        states.append(st["align"]["status"])
    assert states[-1] == "NON_COINCIDE" and "OK" not in states      # mai OK; scatta dopo pochi frame, non al primo
    assert st["align"]["rms_m"] > 0.25 and "non coincide" in st["align"]["message"]
    assert st["health"] == 0.0
    assert st["decision"]["level"] == 3 and st["decision"]["cause"] == "affidabilita_persa"  # FERMA


def test_camera_back_in_place_recovers(calibrated, monkeypatch):
    pipe, t, _ = calibrated
    with monkeypatch.context() as m:
        move_camera(m, (2.9, -0.6, 2.2), (2.5, 2.2, 0.0))
        st, t = feed(pipe, t, 6)
        assert st["align"]["status"] == "NON_COINCIDE"
    st, t = feed(pipe, t, 25)  # camera rimessa a posto: dopo la finestra (2 s) torna OK
    assert st["align"]["status"] == "OK"


def test_covered_anchors_are_degraded_never_ok(calibrated):
    pipe, t, _ = calibrated
    st, t = feed(pipe, t, 6)
    assert st["align"]["status"] == "OK"
    st, t = feed(pipe, t, 3, ids=(10, 11, 12))  # 1 coperta: 3 bastano ancora
    assert st["align"]["status"] == "OK"
    t += 3.0  # più della finestra
    st, t = feed(pipe, t, 3, ids=(10, 11))
    assert st["align"]["status"] == "DEGRADATO" and st["align"]["n_seen"] == 2 and 0.3 <= st["health"] < 1.0
    assert "coperte" in st["align"]["message"]
    t += 3.0
    st, t = feed(pipe, t, 1, ids=())
    assert st["align"]["status"] == "DEGRADATO" and st["align"]["n_seen"] == 0


def test_short_occlusion_does_not_flicker(calibrated):
    pipe, t, _ = calibrated
    seen = []
    for ids in [(10, 11, 12, 13)] * 3 + [(10,)] * 5 + [(10, 11, 12, 13)] * 3:
        st, t = feed(pipe, t, 1, ids=ids)
        seen.append(st["align"]["status"])
    assert set(seen) == {"OK"}


def test_without_anchors_alignment_is_not_verified_and_nothing_changes():
    pipe = make_pipe(anchor_set=None)
    img, world = synth.floor_pairs()
    from oracolo.vision.calib import Calibration
    pipe.set_calibration(Calibration.from_pairs(img, world, [synth.W, synth.H], [2.5, -0.6], 2.2))
    st, _ = feed(pipe, 0.0, 6)
    assert st["align"]["status"] == "NON_VERIFICATO" and st["health"] == 1.0
    assert st["vehicle"]["xy"] == pytest.approx([2.5, 1.2], abs=0.2)
    with pytest.raises(ValueError):
        pipe.calibrate_from_anchors(0.0)


def test_known_limit_single_wrong_coordinate_is_not_caught():
    """Limite noto (docs/13): con 4 ancore l'omografia è quasi determinata dai soli centri, quindi una
    coordinata sbagliata di 1 m su UNA ancora non fa scattare l'allarme (errore ~8 cm). Serve il controllo
    visivo della sovrapposizione CAD-video, oppure >=5 ancore."""
    wrong = AnchorSet(0.2, {**{i: (x, y, 0.0) for i, (x, y) in synth.ANCHOR_POS.items()}, 12: (4.0, 2.5, 0.0)})
    pipe = make_pipe(wrong)
    _, t = feed(pipe, 0.0, 4)
    cal, info = pipe.calibrate_from_anchors(t, camera=CAMERA)
    assert info["rms_m"] < 0.15, "se questo fallisce il limite è cambiato: aggiornare docs/13"


def test_known_limit_small_camera_shift_stays_below_threshold(calibrated, monkeypatch):
    """Limite noto: una spinta del treppiede di ~5 cm (circa 1 grado) dà ~5 cm di errore sulle ancore, sotto OK_RMS_M."""
    pipe, t, _ = calibrated
    move_camera(monkeypatch, (2.55, -0.6, 2.2), (2.55, 2.2, 0.0))
    st, t = feed(pipe, t, 5)
    assert st["align"]["status"] == "OK" and 0.02 < st["align"]["rms_m"] < 0.10


def test_reprojection_rms_zero_for_exact_homography():
    a = anchors()
    pix = {i: synth.project([[x, y, 0] for x, y in a.corners_world(i)]) for i in a.anchors}
    H, _ = cv2.findHomography(np.vstack([pix[i] for i in a.anchors]), np.vstack([a.corners_world(i) for i in a.anchors]), 0)
    rms, per = reprojection_rms(H, pix, a)
    assert rms < 1e-6 and set(per) == set(a.anchors)


# ---- server --------------------------------------------------------------------------------------------
def _post(base, path, obj):
    req = urllib.request.Request(base + path, data=json.dumps(obj).encode(), method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=5)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _jpg(frame):
    return cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tobytes()


def test_server_anchors_flow(tmp_path):
    scene = scene_from_spec({"perimetro": [0, 0, 5, 4]})
    app = LiveApp(LivePipeline(scene, None, person_detector=NoPersonDetector()), tmp_path / "calib.json",
                  anchors_path=tmp_path / "anchors.json")
    httpd = serve(app, "127.0.0.1", 0)
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        assert json.loads(urllib.request.urlopen(base + "/anchors").read())["anchors"] is None
        code, out = _post(base, "/anchors", {"size_m": 0.2, "anchors": {"10": [1, 1]}})
        assert code == 400 and not out["ok"]
        body = {"size_m": 0.2, "anchors": {str(i): [x, y] for i, (x, y) in synth.ANCHOR_POS.items()}}
        code, out = _post(base, "/anchors", body)
        assert code == 200 and out["ok"] and not out["warnings"] and (tmp_path / "anchors.json").exists()
        assert len(json.loads(urllib.request.urlopen(base + "/scene").read())["anchors"]["anchors"]) == 4

        code, out = _post(base, "/calib_anchors", {"camera": {"x": 2.5, "y": -0.6, "h": 2.2}})
        assert code == 400 and "almeno 3" in out["error"]  # ancora nessun frame
        for _ in range(8):
            app.push_jpeg(_jpg(synth.render_with_anchors(VEH)))
            time.sleep(0.1)
        assert _post(base, "/anchors", body)[0] == 200  # come fa il pulsante «Calibra da ancore» (salva e poi calibra)
        code, out = _post(base, "/calib_anchors", {"camera": {"x": 2.5, "y": -0.6, "h": 2.2}})
        assert code == 200 and out["ok"] and out["rms_m"] < 0.05 and (tmp_path / "calib.json").exists()
        for _ in range(10):
            app.push_jpeg(_jpg(synth.render_with_anchors(VEH)))
            time.sleep(0.1)
        st = json.loads(urllib.request.urlopen(base + "/state").read())
        assert st["calibrated"] and st["align"]["status"] == "OK"

        code, out = _post(base, "/anchors", {"size_m": 0.2, "anchors": {"10": [1, 1], "11": [9, 1], "12": [4, 3]}})
        assert code == 200 and out["warnings"] and "fuori dal perimetro" in out["warnings"][0]
        code, out = _post(base, "/anchors", {"clear": True})
        assert code == 200 and not (tmp_path / "anchors.json").exists()
    finally:
        app.running = False
        httpd.shutdown()


def test_server_loads_saved_anchors_at_startup(tmp_path):
    anchors().save(tmp_path / "anchors.json")
    scene = scene_from_spec({"perimetro": [0, 0, 5, 4]})
    app = LiveApp(LivePipeline(scene, None, person_detector=NoPersonDetector()), tmp_path / "c.json",
                  anchors_path=tmp_path / "anchors.json")
    assert app.pipe.anchors is not None and not app.anchors_error
    (tmp_path / "rotto.json").write_text("{non json")
    app2 = LiveApp(LivePipeline(scene, None, person_detector=NoPersonDetector()), tmp_path / "c.json",
                   anchors_path=tmp_path / "rotto.json")
    assert app2.pipe.anchors is None and app2.anchors_error


def test_marker_print_script_makes_detectable_exact_size_markers(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run([sys.executable, "-I", str(root / "scripts" / "make_anchor_markers.py"), "--ids", "12", "--paper", "A4",
                        "--black-cm", "15", "--out", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    img = cv2.imread(str(tmp_path / "marker_ancora_ID12_15cm_A4.png"), 0)
    assert img.shape == (3508, 2480) and (tmp_path / "marker_ancora_ID12_15cm_A4.pdf").exists()
    det = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))
    corners, ids, _ = det.detectMarkers(cv2.resize(img, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA))
    assert ids is not None and ids.ravel().tolist() == [12]
    side_px = float(np.linalg.norm(corners[0][0][0] - corners[0][0][1])) * 4
    assert side_px / 300 * 2.54 == pytest.approx(15.0, abs=0.1)  # 300 dpi: il quadrato nero misura 15 cm
    bad = subprocess.run([sys.executable, "-I", str(root / "scripts" / "make_anchor_markers.py"), "--paper", "A4",
                          "--black-cm", "20", "--out", str(tmp_path)], capture_output=True, text=True)
    assert bad.returncode != 0 and "non entra" in (bad.stderr + bad.stdout)


def test_script_marker_pagina_piena(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run([sys.executable, "-I", str(root / "scripts" / "make_anchor_markers.py"), "--ids", "10", "17", "--paper", "A4",
                        "--fill", "--out", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    det = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))
    for mid in (10, 17):
        img = cv2.imread(str(tmp_path / f"marker_ancora_ID{mid}_pagina_piena_A4.png"), 0)
        corners, ids, _ = det.detectMarkers(cv2.resize(img, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA))
        assert ids is not None and ids.ravel().tolist() == [mid]
        side_cm = float(np.linalg.norm(corners[0][0][0] - corners[0][0][1])) * 4 / 300 * 2.54
        assert 16.0 < side_cm < 16.8  # A4: il nero è il più grande possibile per la larghezza della pagina
