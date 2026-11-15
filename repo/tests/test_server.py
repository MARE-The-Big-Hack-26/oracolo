import json
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")

from oracolo.cad import load_dxf  # noqa: E402
from oracolo.vision.calib import Calibration  # noqa: E402
from oracolo.vision.certs import ensure_cert  # noqa: E402
from oracolo.vision.detectors import NoPersonDetector  # noqa: E402
from oracolo.vision.pipeline import LivePipeline  # noqa: E402
from oracolo.vision.server import LiveApp, serve  # noqa: E402
from tests import synth  # noqa: E402


def _jpeg(frame):
    ok, buf = cv2.imencode(".jpg", frame)
    return buf.tobytes()


def _req(url, data=None, ctx=None):
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    return urllib.request.urlopen(req, timeout=5, context=ctx)


@pytest.fixture()
def live(tmp_path):
    dxf = Path(__file__).resolve().parent.parent / "scenarios" / "stanza.dxf"
    scene, _ = load_dxf(dxf)
    pipe = LivePipeline(scene, None, person_detector=NoPersonDetector())
    app = LiveApp(pipe, tmp_path / "calib.json")
    httpd = serve(app, "127.0.0.1", 0)
    yield app, f"http://127.0.0.1:{httpd.server_address[1]}"
    app.running = False
    httpd.shutdown()


def test_flusso_completo(live):
    app, base = live
    for page in ("/", "/camera", "/calibrate", "/room", "/cab", "/muletto"):
        assert b"<html" in _req(base + page).read()
    assert b"OrbitControls" in _req(base + "/room.js").read()
    assert b"SENSORE MULETTO" in _req(base + "/cab").read()
    assert b"FAIL-SAFE" in _req(base + "/cab.js").read()
    assert _req(base + "/qr.png").read().startswith(b"\x89PNG")
    assert _req(base + "/cab_qr.png").read().startswith(b"\x89PNG")
    scene_json = json.loads(_req(base + "/scene").read())
    assert scene_json["calibrated"] is False
    assert scene_json["cab_url"].endswith("/cab")
    # frame -> snapshot disponibile
    frame = synth.render_frame((2.5, 1.2, 1.5708))
    assert _req(base + "/frame", _jpeg(frame)).status == 204
    assert len(_req(base + "/snapshot.jpg").read()) > 1000
    # calibrazione dalla UI
    img, world = synth.floor_pairs()
    body = json.dumps({"img": img, "world": world, "image_size": [synth.W, synth.H], "cam_xy": [2.5, -0.6], "cam_h": 2.2}).encode()
    out = json.loads(_req(base + "/calib", body).read())
    assert out["ok"] and out["rms_m"] < 0.01
    assert json.loads(_req(base + "/scene").read())["calibrated"] is True
    # ora i frame producono uno stato con il muletto
    st = {}
    for _ in range(30):
        _req(base + "/frame", _jpeg(frame))
        time.sleep(0.1)
        st = json.loads(_req(base + "/state").read())
        if st.get("vehicle"):
            break
    assert st["vehicle"]["tracked"] and st["decision"] is not None
    # video annotato
    r = _req(base + "/video.mjpg")
    assert b"--frame" in r.read(64)


def test_calibrazione_non_valida(live):
    app, base = live
    try:
        _req(base + "/calib", json.dumps({"img": [[0, 0]], "world": [[0, 0]], "image_size": [10, 10], "cam_xy": [0, 0], "cam_h": 2}).encode())
        assert False, "doveva rifiutare"
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_https_con_certificato_autofirmato(tmp_path):
    dxf = Path(__file__).resolve().parent.parent / "scenarios" / "stanza.dxf"
    scene, _ = load_dxf(dxf)
    app = LiveApp(LivePipeline(scene, None, person_detector=NoPersonDetector()), tmp_path / "c.json")
    cert, key = ensure_cert(tmp_path / "certs")
    httpd = serve(app, "127.0.0.1", 0, cert, key)
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        r = _req(f"https://127.0.0.1:{httpd.server_address[1]}/camera", ctx=ctx)
        assert b"getUserMedia" in r.read()
    finally:
        app.running = False
        httpd.shutdown()


def test_http_e_https_sulla_stessa_porta(tmp_path):
    dxf = Path(__file__).resolve().parent.parent / "scenarios" / "stanza.dxf"
    scene, _ = load_dxf(dxf)
    app = LiveApp(LivePipeline(scene, None, person_detector=NoPersonDetector()), tmp_path / "c.json")
    cert, key = ensure_cert(tmp_path / "certs")
    httpd = serve(app, "127.0.0.1", 0, cert, key)
    port = httpd.server_address[1]
    try:
        assert b"getUserMedia" in _req(f"http://127.0.0.1:{port}/camera").read()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        assert b"getUserMedia" in _req(f"https://127.0.0.1:{port}/camera", ctx=ctx).read()
    finally:
        app.running = False
        httpd.shutdown()


def test_frame_fermi_comando_di_arresto(live):
    app, base = live
    app.stale_after = 0.4
    img, world = synth.floor_pairs()
    body = json.dumps({"img": img, "world": world, "image_size": [synth.W, synth.H], "cam_xy": [2.5, -0.6], "cam_h": 2.2}).encode()
    _req(base + "/calib", body)
    frame = synth.render_frame((2.5, 1.2, 1.5708))
    _req(base + "/frame", _jpeg(frame))
    st = {}
    for _ in range(50):
        time.sleep(0.05)
        st = json.loads(_req(base + "/state").read())
        if st.get("calibrated"):
            break
    assert st.get("calibrated") and not st.get("stale")
    time.sleep(0.8)  # l'iPhone smette di inviare
    st = json.loads(_req(base + "/state").read())
    assert st["stale"] and st["decision"]["level"] == 3 and st["decision"]["cause"] == "affidabilita_persa"


def test_https_connessione_muta_non_blocca_il_server(tmp_path):
    """Un client che apre il socket e non parla (Safari lo fa) non deve bloccare gli altri."""
    import socket
    dxf = Path(__file__).resolve().parent.parent / "scenarios" / "stanza.dxf"
    scene, _ = load_dxf(dxf)
    app = LiveApp(LivePipeline(scene, None, person_detector=NoPersonDetector()), tmp_path / "c.json")
    cert, key = ensure_cert(tmp_path / "certs")
    httpd = serve(app, "127.0.0.1", 0, cert, key)
    port = httpd.server_address[1]
    mute = socket.create_connection(("127.0.0.1", port))
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        r = _req(f"https://127.0.0.1:{port}/camera", ctx=ctx)
        assert b"getUserMedia" in r.read()
    finally:
        mute.close()
        app.running = False
        httpd.shutdown()


def test_editor_planimetria_e_ostacoli(tmp_path):
    dxf_out = tmp_path / "stanza.dxf"
    dxf_init = Path(__file__).resolve().parent.parent / "scenarios" / "stanza.dxf"
    scene, _ = load_dxf(dxf_init)
    app = LiveApp(LivePipeline(scene, None, person_detector=NoPersonDetector()), tmp_path / "calib.json", dxf_path=dxf_out)
    httpd = serve(app, "127.0.0.1", 0)
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        payload = {
            "bounds": [[0.0, 0.0], [6.5, 0.0], [6.5, 4.5], [0.0, 4.5]],
            "obstacles": [
                {"name": "pianoforte", "x": 0.5, "y": 1.0, "w": 1.4, "d": 0.65, "height": 1.1},
                {"name": "armadio", "x": 4.0, "y": 2.5, "w": 1.2, "d": 0.6, "height": 2.2},
            ],
        }
        res = json.loads(_req(base + "/scene", json.dumps(payload).encode()).read())
        assert res["ok"] and res["occluders"] == 2 and res["bounds_m"] == [0.0, 0.0, 6.5, 4.5]
        sc = json.loads(_req(base + "/scene").read())
        assert len(sc["occluders"]) == 2
        assert sc["occluders"][0]["height"] == pytest.approx(1.1)
        assert sc["occluders"][1]["height"] == pytest.approx(2.2)
        reloaded, info = load_dxf(dxf_out)
        assert info["bounds_m"] == pytest.approx((0.0, 0.0, 6.5, 4.5))
        assert sorted(o.height for o in reloaded.occluders) == pytest.approx([1.1, 2.2])
        try:
            _req(base + "/scene", json.dumps({"bounds": [[0, 0], [4, 0], [4, 3], [0, 3]], "obstacles": [{"x": 0, "y": 0, "w": -1, "d": 1, "height": 1.5}]}).encode())
            assert False, "doveva rifiutare larghezza negativa"
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        app.running = False
        httpd.shutdown()


def test_editor_camera_e_anteprima_calibrazione(tmp_path):
    dxf_out = tmp_path / "stanza.dxf"
    calib_out = tmp_path / "calib.json"
    dxf_init = Path(__file__).resolve().parent.parent / "scenarios" / "stanza.dxf"
    scene, _ = load_dxf(dxf_init)
    app = LiveApp(LivePipeline(scene, None, person_detector=NoPersonDetector()), calib_out, dxf_path=dxf_out)
    httpd = serve(app, "127.0.0.1", 0)
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        payload = {
            "bounds": [[0.0, 0.0], [5.0, 0.0], [5.0, 4.0], [0.0, 4.0]],
            "obstacles": [{"name": "scaffale", "x": 1.0, "y": 1.5, "w": 0.5, "d": 1.2, "height": 1.6}],
            "cam": {"xy": [4.2, 0.5], "h": 2.05},
        }
        assert json.loads(_req(base + "/scene", json.dumps(payload).encode()).read())["ok"]
        sc = json.loads(_req(base + "/scene").read())
        assert sc["cam"]["xy"] == pytest.approx([4.2, 0.5]) and sc["cam"]["h"] == pytest.approx(2.05)

        img, world = synth.floor_pairs()
        cal_res = json.loads(_req(base + "/calib", json.dumps({
            "img": img, "world": world, "image_size": [synth.W, synth.H], "cam_xy": [2.5, -0.6], "cam_h": 2.2,
        }).encode()).read())
        assert cal_res["ok"] and "bounds" in cal_res["overlay"] and len(cal_res["overlay"]["occluders"]) == 1
        sc2 = json.loads(_req(base + "/scene").read())
        assert len(sc2["calib"]["img_pts"]) == 4 and "overlay" in sc2["calib"]

        assert json.loads(_req(base + "/scene", json.dumps(payload).encode()).read())["ok"]
        reloaded_cal = Calibration.load(calib_out)
        assert reloaded_cal.cam_xy == pytest.approx((4.2, 0.5)) and reloaded_cal.cam_h == pytest.approx(2.05)
    finally:
        app.running = False
        httpd.shutdown()


def test_stanza_irregolare_corridoio_e_forme(tmp_path):
    from shapely.geometry import Point
    dxf_out = tmp_path / "stanza_irregolare.dxf"
    dxf_init = Path(__file__).resolve().parent.parent / "scenarios" / "stanza.dxf"
    scene, _ = load_dxf(dxf_init)
    pipe = LivePipeline(scene, None, person_detector=NoPersonDetector())
    app = LiveApp(pipe, tmp_path / "calib.json", dxf_path=dxf_out)
    httpd = serve(app, "127.0.0.1", 0)
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        l_room = [[0.0, 0.0], [6.0, 0.0], [6.0, 2.0], [2.0, 2.0], [2.0, 6.0], [0.0, 6.0]]
        payload = {
            "bounds": l_room,
            "obstacles": [
                {"name": "triangolo", "coords": [[0.4, 0.4], [1.4, 0.4], [0.9, 1.3]], "height": 1.2},
                {"name": "scaffale_L", "coords": [[2.5, 0.3], [4.5, 0.3], [4.5, 0.8], [3.0, 0.8], [3.0, 1.6], [2.5, 1.6]], "height": 1.9},
                {"name": "muro_obliquo", "coords": [[0.3, 3.0], [1.6, 4.3], [1.5, 4.4], [0.2, 3.1]], "height": 2.2},
            ],
            "cam": {"xy": [5.0, 5.0], "h": 2.1},
        }
        res = json.loads(_req(base + "/scene", json.dumps(payload).encode()).read())
        assert res["ok"] and res["occluders"] == 3 and res["bounds_m"] == [0.0, 0.0, 6.0, 6.0]
        sc = json.loads(_req(base + "/scene").read())
        assert len(sc["bounds"]) == 7
        assert len(sc["occluders"][1]["coords"]) == 7

        img, world = synth.floor_pairs()
        cal_res = json.loads(_req(base + "/calib", json.dumps({
            "img": img, "world": world, "image_size": [synth.W, synth.H], "cam_xy": [5.0, 5.0], "cam_h": 2.2,
        }).encode()).read())
        assert cal_res["ok"]
        assert pipe.scene.bounds.contains(Point(pipe.cam_xy))
        assert pipe.vis_poly is not None and not pipe.vis_poly.is_empty

        corr_res = json.loads(_req(base + "/scene", json.dumps({
            "corridor": {"points": [[0.0, 1.0], [5.0, 1.0], [5.0, 5.0]], "width": 1.6},
            "obstacles": [],
        }).encode()).read())
        assert corr_res["ok"] and corr_res["occluders"] == 0
    finally:
        app.running = False
        httpd.shutdown()


def test_camera_move_updates_shadows_fov_and_fog(live):
    _, base = live
    base_scene = {"bounds": [[0.0, 0.0], [6.0, 0.0], [6.0, 4.0], [0.0, 4.0]],
                  "obstacles": [{"name": "scrivania", "x": 2.5, "y": 1.5, "w": 1.0, "d": 1.0, "height": 0.77}]}
    r1 = json.loads(_req(base + "/scene", json.dumps({**base_scene, "cam": {"xy": [1.0, 2.0], "h": 1.8}}).encode()).read())
    st1 = json.loads(_req(base + "/state").read())
    r2 = json.loads(_req(base + "/scene", json.dumps({**base_scene, "cam": {"xy": [5.0, 2.0], "h": 0.9}}).encode()).read())
    st2 = json.loads(_req(base + "/state").read())
    assert r1["shadows"] and r2["shadows"] and r1["shadows"] != r2["shadows"]
    assert r1["fov"] != r2["fov"] and st1["fog"]["b64"] != st2["fog"]["b64"]
    r3 = json.loads(_req(base + "/scene", json.dumps({**base_scene, "cam": {"xy": [1.5, 2.0], "h": 1.8, "dir": 0, "fov": 75}}).encode()).read())
    st3 = json.loads(_req(base + "/state").read())
    r4 = json.loads(_req(base + "/scene", json.dumps({**base_scene, "cam": {"xy": [1.5, 2.0], "h": 1.8, "dir": 180, "fov": 75}}).encode()).read())
    st4 = json.loads(_req(base + "/state").read())
    assert r3["shadows"] and not r4["shadows"]
    assert r3["fov"] != r4["fov"] and st3["fog"]["b64"] != st4["fog"]["b64"]


# ---- «Carica DXF» e avvio senza planimetria ------------------------------------------------------------
REALISTIC = Path(__file__).resolve().parent.parent / "scenarios" / "magazzino_realistico_mm.dxf"


def _start_empty(tmp_path):
    from shapely.geometry import box

    from oracolo.geometry import Scene
    pipe = LivePipeline(Scene(box(0, 0, 5, 4), []), None, person_detector=NoPersonDetector())
    app = LiveApp(pipe, tmp_path / "calib.json", dxf_path=tmp_path / "planimetria.dxf", scene_loaded=False)
    httpd = serve(app, "127.0.0.1", 0)
    return app, httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def _post_dxf(base, data, name="x.dxf"):
    req = urllib.request.Request(base + "/dxf", data=data, method="POST", headers={"X-Filename": name})
    try:
        r = urllib.request.urlopen(req, timeout=5)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_avvio_senza_planimetria_poi_carica_dxf(tmp_path):
    app, httpd, base = _start_empty(tmp_path)
    try:
        st = json.loads(_req(base + "/state").read())
        assert st["no_scene"] is True and not st["calibrated"] and "decision" not in st
        assert json.loads(_req(base + "/scene").read())["no_scene"] is True

        code, rep = _post_dxf(base, REALISTIC.read_bytes(), "magazzino%20realistico.dxf")
        assert code == 200 and rep["ok"] and rep["stats"]["occluders"] == 12
        assert rep["warnings"] and rep["filename"] == "magazzino realistico.dxf"

        sc = json.loads(_req(base + "/scene").read())
        assert sc["no_scene"] is False and len(sc["occluders"]) == 12
        xs = [p[0] for p in sc["bounds"]]
        ys = [p[1] for p in sc["bounds"]]
        assert (min(xs), min(ys), max(xs), max(ys)) == (0.0, 0.0, 24.0, 14.0)
        assert sc["cad"]["stats"]["unit_m"] == 0.001
        assert "no_scene" not in json.loads(_req(base + "/state").read())

        reloaded, info = load_dxf(tmp_path / "planimetria.dxf")  # copia in formato standard
        assert info["bounds_m"] == pytest.approx((0, 0, 24, 14)) and len(reloaded.occluders) == 12
    finally:
        app.running = False
        httpd.shutdown()


def test_dxf_inutilizzabile_non_cambia_la_planimetria(tmp_path):
    app, httpd, base = _start_empty(tmp_path)
    try:
        _post_dxf(base, REALISTIC.read_bytes())
        for data in (b"", b"non e' un dxf", b"AC1032\x00\x00 finto dwg"):
            code, rep = _post_dxf(base, data)
            assert code == 400 and not rep["ok"] and rep["errors"]
        assert "DWG" in _post_dxf(base, b"AC1032\x00\x00 finto dwg")[1]["errors"][0]
        sc = json.loads(_req(base + "/scene").read())
        assert len(sc["occluders"]) == 12 and sc["no_scene"] is False
    finally:
        app.running = False
        httpd.shutdown()


def test_dxf_troppo_grande_rifiutato(tmp_path, monkeypatch):
    from oracolo.vision import http_handler
    monkeypatch.setattr(http_handler, "MAX_DXF_BYTES", 100)
    app, httpd, base = _start_empty(tmp_path)
    try:
        code, rep = _post_dxf(base, b"0" * 500)
        assert code == 413 and not rep["ok"]
    finally:
        app.running = False
        httpd.shutdown()


def test_editor_dopo_avvio_vuoto_sblocca_la_planimetria(tmp_path):
    app, httpd, base = _start_empty(tmp_path)
    try:
        payload = {"bounds": [[0, 0], [6, 0], [6, 4], [0, 4]], "obstacles": [{"x": 1, "y": 1, "w": 1, "d": 1, "height": 1.5}]}
        assert json.loads(_req(base + "/scene", json.dumps(payload).encode()).read())["ok"]
        assert "no_scene" not in json.loads(_req(base + "/state").read())
        assert json.loads(_req(base + "/scene").read())["cad"]["source"] == "editor"
    finally:
        app.running = False
        httpd.shutdown()
