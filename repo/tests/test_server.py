import json
import ssl
import time
import urllib.request
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")

from oracolo.cad import load_dxf  # noqa: E402
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
    for page in ("/", "/camera", "/calibrate", "/room"):
        assert b"<html" in _req(base + page).read()
    assert b"OrbitControls" in _req(base + "/room.js").read()
    assert _req(base + "/qr.png").read().startswith(b"\x89PNG")
    assert json.loads(_req(base + "/scene").read())["calibrated"] is False
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
    app = LiveApp(LivePipeline(scene, None), tmp_path / "c.json")
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


def test_frame_fermi_comando_di_arresto(live):
    app, base = live
    app.stale_after = 0.4
    img, world = synth.floor_pairs()
    body = json.dumps({"img": img, "world": world, "image_size": [synth.W, synth.H], "cam_xy": [2.5, -0.6], "cam_h": 2.2}).encode()
    _req(base + "/calib", body)
    frame = synth.render_frame((2.5, 1.2, 1.5708))
    for _ in range(10):
        _req(base + "/frame", _jpeg(frame))
        time.sleep(0.1)
    st = json.loads(_req(base + "/state").read())
    assert not st.get("stale")
    time.sleep(0.8)  # l'iPhone smette di inviare
    st = json.loads(_req(base + "/state").read())
    assert st["stale"] and st["decision"]["level"] == 3 and st["decision"]["cause"] == "affidabilita_persa"


def test_https_connessione_muta_non_blocca_il_server(tmp_path):
    """Un client che apre il socket e non parla (Safari lo fa) non deve bloccare gli altri."""
    import socket
    dxf = Path(__file__).resolve().parent.parent / "scenarios" / "stanza.dxf"
    scene, _ = load_dxf(dxf)
    app = LiveApp(LivePipeline(scene, None), tmp_path / "c.json")
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
