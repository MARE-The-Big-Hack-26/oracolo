"""Server live: riceve i frame dell'iPhone, elabora, serve pannello e calibrazione.

    GET  /            pannello (Mac): video con CAD sovrapposto + mappa dall'alto + livello
    GET  /camera      pagina da aprire sull'iPhone: invia i frame della camera
    GET  /calibrate   calibrazione: coppie di punti video <-> mappa
    POST /frame       JPEG dall'iPhone
    GET  /video.mjpg  video annotato (MJPEG)
    GET  /state       stato JSON     GET /scene  planimetria + campo visivo + camera
    GET  /snapshot.jpg ultimo frame grezzo      POST /calib  salva la calibrazione
    GET/POST /anchors  ancore ArUco a terra (id 10-13, coordinate nel CAD)    POST /calib_anchors  calibra dalle ancore
    POST /dxf         carica un DXF (corpo = file): normalizzazione + nuova planimetria (solo DXF, non DWG)
Solo libreria standard (+ OpenCV, NumPy già in uso).
"""
from __future__ import annotations

import json
import ssl
import tempfile
import threading
import time
from urllib.parse import unquote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np

from ..cab import CAUSE_IT
from ..cad import save_dxf, scene_from_spec
from ..cad_norm import normalize_dxf
from .align import AnchorSet
from .calib import Calibration
from .pipeline import json_state
from .viz import draw_overlay

WEB = Path(__file__).parent / "web"
MAX_DXF_BYTES = 20 * 1024 * 1024


class LiveApp:
    def __init__(self, pipeline, calib_path="calib.json", jpeg_quality: int = 70, max_width: int = 960,
                 stale_after: float = 0.6, dxf_path=None, scene_loaded: bool = True,
                 anchors_path=None):
        self.pipe = pipeline
        self.calib_path = Path(calib_path)
        self.dxf_path = Path(dxf_path) if dxf_path else None
        self.q, self.max_width = jpeg_quality, max_width
        self.cond = threading.Condition()
        self._raw = None  # (t_recv, jpeg bytes | ndarray)
        self._raw_ver = 0
        self.snapshot = b""
        self.annot = b""
        self.annot_ver = 0
        self.state_obj = {"calibrated": False}
        self.last_done = None
        self.stale_after = stale_after  # s senza frame nuovi -> arresto (fail-safe)
        self.fps = 0.0
        self.latency = 0.0
        self.running = True
        self.n_frames = 0
        self.lock_pipe = threading.Lock()
        self.last_error = ""
        # planimetria: all'avvio senza --dxf non c'è ancora (si sceglie «Carica DXF» o «Disegna»)
        self.scene_loaded = scene_loaded
        self.cad_report = None
        self.default_height = 3.0
        self.lines_as_walls = False
        self.anchors_path = Path(anchors_path) if anchors_path else None
        self.anchors_error = ""
        if self.anchors_path is not None and self.anchors_path.exists():
            try:
                self.pipe.set_anchors(AnchorSet.load(self.anchors_path))
            except (ValueError, OSError) as e:
                self.anchors_error = f"{self.anchors_path}: {e}"

    # ---- ingresso frame ------------------------------------------------------------------
    def push_jpeg(self, data: bytes) -> None:
        with self.cond:
            self._raw = (time.monotonic(), data)
            self._raw_ver += 1
            self.snapshot = data
            self.cond.notify_all()

    def push_frame(self, frame) -> None:
        with self.cond:
            self._raw = (time.monotonic(), frame)
            self._raw_ver += 1
            self.cond.notify_all()

    # ---- elaborazione --------------------------------------------------------------------
    def worker(self) -> None:
        seen_ver, t_prev = 0, None
        while self.running:
            with self.cond:
                self.cond.wait_for(lambda: self._raw_ver != seen_ver or not self.running, timeout=1.0)
                if self._raw_ver == seen_ver:
                    continue
                seen_ver = self._raw_ver
                t_recv, raw = self._raw
            try:
                frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR) if isinstance(raw, (bytes, bytearray)) else raw
                if frame is None:
                    continue
                if not isinstance(raw, (bytes, bytearray)):
                    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if ok:
                        self.snapshot = buf.tobytes()
                with self.lock_pipe:
                    t0 = time.monotonic()
                    state = self.pipe.process(frame, t_recv, frame_age=max(0.0, t0 - t_recv))
                    img = draw_overlay(frame, self.pipe.calib, self.pipe.scene, state, self.max_width)
                done = time.monotonic()
                self.latency = done - t_recv
                if t_prev is not None:
                    self.fps = 0.8 * self.fps + 0.2 / max(done - t_prev, 1e-3)
                t_prev = done
                self.n_frames += 1
                state["fps"] = round(self.fps, 1)
                state["latency"] = round(self.latency, 3)
                ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, self.q])
                with self.cond:
                    self.state_obj = json_state(state)
                    self.last_done = time.monotonic()
                    if ok:
                        self.annot = buf.tobytes()
                        self.annot_ver += 1
                    self.cond.notify_all()
            except Exception as e:  # noqa: BLE001 (un frame difettoso non deve fermare il server)
                self.last_error = repr(e)

    def current_state(self) -> bytes:
        """Stato per la UI. Se i frame smettono di arrivare il comando diventa FERMA (come il watchdog della macchina)."""
        st = dict(self.state_obj)
        if not self.scene_loaded:  # nessuna planimetria scelta: niente calibrazione né comando
            st.update({"no_scene": True, "calibrated": False})
            st.pop("decision", None)
            st["age"] = None
            return json.dumps(st).encode()
        age = None if self.last_done is None else time.monotonic() - self.last_done
        st["age"] = None if age is None else round(age, 2)
        if st.get("calibrated") and age is not None and age > self.stale_after:
            st["stale"] = True
            st["decision"] = {"limit": 0.0, "level": 3, "level_name": "FERMA", "cause": "affidabilita_persa",
                              "cause_it": CAUSE_IT["affidabilita_persa"]}
        return json.dumps(st).encode()

    # ---- calibrazione --------------------------------------------------------------------
    def apply_calibration(self, body: dict) -> dict:
        cal = Calibration.from_pairs(body["img"], body["world"], body["image_size"], body["cam_xy"], body["cam_h"])
        cal.save(self.calib_path)
        with self.lock_pipe:
            self.pipe.set_calibration(cal)
        return {"ok": True, "rms_m": round(cal.rms_m, 3)}

    def apply_scene(self, body: dict) -> dict:
        scene = scene_from_spec(body)
        if self.dxf_path is not None:
            save_dxf(scene, self.dxf_path)
        with self.lock_pipe:
            self.pipe.set_scene(scene)
        self.scene_loaded = True
        self.cad_report = {"source": "editor", "filename": "", "ok": True, "errors": [], "warnings": [],
                           "stats": {"occluders": len(scene.occluders), "size_m": [round(v, 3) for v in scene.bounds.bounds[2:]]}}
        return {"ok": True, "occluders": len(scene.occluders), "bounds_m": [round(v, 3) for v in scene.bounds.bounds]}

    # ---- ancore a terra ------------------------------------------------------------------
    def apply_anchors(self, body: dict) -> dict:
        if body.get("clear"):
            with self.lock_pipe:
                self.pipe.set_anchors(None)
            if self.anchors_path is not None and self.anchors_path.exists():
                self.anchors_path.unlink()
            return {"ok": True, "anchors": None, "warnings": []}
        a = AnchorSet.from_dict(body, forbidden_ids=(self.pipe.marker.marker_id,))
        warnings = []
        out = a.outside(self.pipe.scene.bounds)
        if out:
            warnings.append(f"Ancore fuori dal perimetro della planimetria: {out}. Controlla le coordinate.")
        if self.anchors_path is not None:
            a.save(self.anchors_path)
        with self.lock_pipe:
            self.pipe.set_anchors(a)
        return {"ok": True, "anchors": a.to_dict(), "warnings": warnings}

    def calibrate_from_anchors(self, body: dict) -> dict:
        cam = body.get("camera") if isinstance(body, dict) else None
        camera = None if not cam else (float(cam["x"]), float(cam["y"]), float(cam["h"]))
        with self.lock_pipe:
            cal, info = self.pipe.calibrate_from_anchors(time.monotonic(), camera)  # ValueError -> 400
            cal.save(self.calib_path)
            self.pipe.set_calibration(cal)
        return {"ok": True, **info}

    def apply_dxf(self, data: bytes, filename: str = "") -> dict:
        """Importa un DXF: normalizza (metri, origine, ostacoli) e sostituisce la planimetria. Se non è
        utilizzabile la planimetria attuale resta quella di prima e si ritornano gli errori."""
        name = Path(unquote(filename)).name[:80]
        if not data:
            return {"ok": False, "errors": ["File vuoto."], "warnings": [], "stats": {}}
        if data[:2] == b"AC" and data[2:6].isdigit():
            return {"ok": False, "errors": ["Questo è un DWG: non è supportato. Esporta il disegno come DXF."],
                    "warnings": [], "stats": {}}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "upload.dxf"
            path.write_bytes(data)
            scene, rep = normalize_dxf(path, default_height=self.default_height, lines_as_walls=self.lines_as_walls)
        if scene is None:
            return rep
        if self.dxf_path is not None:  # copia in formato standard (metri, origine 0,0)
            try:
                save_dxf(scene, self.dxf_path)
            except OSError as e:
                rep["warnings"].append(f"Planimetria normalizzata non salvata su disco ({e}).")
        with self.lock_pipe:
            self.pipe.set_scene(scene)
        self.scene_loaded = True
        rep.update({"source": "dxf", "filename": name})
        self.cad_report = rep
        return rep


def _qr_png(text: str) -> bytes:
    qr = cv2.QRCodeEncoder.create().encode(text or "/camera")
    padded = cv2.copyMakeBorder(qr, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=255)
    img = cv2.resize(padded, (0, 0), fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes() if ok else b""


def make_handler(app: LiveApp, camera_url: str):
    qr_bytes = _qr_png(camera_url)

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):  # handshake TLS nel thread della connessione, non nel ciclo accept()
            if isinstance(self.request, ssl.SSLSocket):
                self.request.settimeout(10)
                self.request.do_handshake()
                self.request.settimeout(None)
            super().setup()

        def log_message(self, *a):  # silenzio
            pass

        def _send(self, code, body: bytes, ctype="text/plain; charset=utf-8", extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _page(self, name):
            self._send(200, (WEB / name).read_bytes(), "text/html; charset=utf-8")

        def do_GET(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in ("/", "/panel"):
                return self._page("panel.html")
            if path == "/camera":
                return self._page("camera.html")
            if path == "/calibrate":
                return self._page("calibrate.html")
            if path == "/room":
                return self._page("room.html")
            if path in ("/room.js", "/dxfload.js"):
                return self._send(200, (WEB / path[1:]).read_bytes(), "application/javascript; charset=utf-8")
            if path == "/state":
                return self._send(200, app.current_state(), "application/json")
            if path == "/scene":
                info = app.pipe.scene_info()
                info["camera_url"] = camera_url
                info["no_scene"] = not app.scene_loaded
                info["cad"] = app.cad_report
                return self._send(200, json.dumps(info).encode(), "application/json")
            if path == "/anchors":
                a = app.pipe.anchors
                out = {"anchors": None if a is None else a.to_dict(), "error": app.anchors_error,
                       "align": json.loads(app.current_state()).get("align")}
                return self._send(200, json.dumps(out).encode(), "application/json")
            if path == "/qr.png":
                return self._send(200, qr_bytes, "image/png")
            if path == "/snapshot.jpg":
                if not app.snapshot:
                    return self._send(404, b"nessun frame ricevuto")
                return self._send(200, app.snapshot, "image/jpeg")
            if path == "/video.mjpg":
                return self._mjpeg()
            return self._send(404, b"non trovato")

        def _mjpeg(self):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            ver = 0
            try:
                while app.running:
                    with app.cond:
                        app.cond.wait_for(lambda: app.annot_ver != ver, timeout=2.0)
                        if app.annot_ver == ver:
                            continue
                        ver, jpg = app.annot_ver, app.annot
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpg))
                    self.wfile.write(jpg + b"\r\n")
            except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                pass

        def do_POST(self):  # noqa: N802
            n = int(self.headers.get("Content-Length", "0"))
            if self.path == "/dxf" and n > MAX_DXF_BYTES:
                self.close_connection = True  # corpo non letto: chiudere invece di desincronizzare la connessione
                out = {"ok": False, "errors": [f"File troppo grande (> {MAX_DXF_BYTES // 2**20} MB)."], "warnings": [], "stats": {}}
                return self._send(413, json.dumps(out).encode(), "application/json")
            body = self.rfile.read(n) if n else b""
            if self.path == "/frame":
                app.push_jpeg(body)
                return self._send(204, b"")
            if self.path == "/calib":
                try:
                    out = app.apply_calibration(json.loads(body))
                    return self._send(200, json.dumps(out).encode(), "application/json")
                except (ValueError, KeyError, cv2.error) as e:
                    return self._send(400, json.dumps({"ok": False, "error": str(e)}).encode(), "application/json")
            if self.path in ("/anchors", "/calib_anchors"):
                try:
                    data = json.loads(body or b"{}")
                    out = app.apply_anchors(data) if self.path == "/anchors" else app.calibrate_from_anchors(data)
                    return self._send(200, json.dumps(out).encode(), "application/json")
                except (ValueError, KeyError, TypeError, cv2.error) as e:
                    return self._send(400, json.dumps({"ok": False, "error": str(e)}).encode(), "application/json")
            if self.path == "/dxf":
                out = app.apply_dxf(body, self.headers.get("X-Filename", ""))
                return self._send(200 if out["ok"] else 400, json.dumps(out, default=str).encode(), "application/json")
            if self.path == "/scene":
                try:
                    out = app.apply_scene(json.loads(body))
                    return self._send(200, json.dumps(out).encode(), "application/json")
                except (ValueError, KeyError) as e:
                    return self._send(400, json.dumps({"ok": False, "error": str(e)}).encode(), "application/json")
            return self._send(404, b"non trovato")

    return H


class QuietServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):  # handshake TLS rifiutati ecc.: nessun rumore
        pass


def serve(app: LiveApp, host="0.0.0.0", port=8443, certfile=None, keyfile=None, camera_url="") -> QuietServer:
    httpd = QuietServer((host, port), make_handler(app, camera_url))
    if certfile:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile, keyfile)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True, do_handshake_on_connect=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    threading.Thread(target=app.worker, daemon=True).start()
    return httpd
