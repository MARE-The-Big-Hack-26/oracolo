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
    for page in ("/", "/camera", "/calibrate"):
        assert b"<html" in _req(base + page).read()
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
