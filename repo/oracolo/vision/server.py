"""Server live: riceve i frame dell'iPhone, elabora, serve pannello e calibrazione.

    GET  /            pannello (Mac): video con CAD sovrapposto + mappa dall'alto + livello
    GET  /camera      pagina da aprire sull'iPhone: invia i frame della camera
    GET  /calibrate   calibrazione: coppie di punti video <-> mappa
    POST /frame       JPEG dall'iPhone
    GET  /video.mjpg  video annotato (MJPEG)
    GET  /state       stato JSON     GET /scene  planimetria + campo visivo + camera
    GET  /snapshot.jpg ultimo frame grezzo      POST /calib  salva la calibrazione
Solo libreria standard (+ OpenCV, NumPy già in uso).
"""
from __future__ import annotations

import json
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np

from ..cab import CAUSE_IT
from .calib import Calibration
from .pipeline import json_state
from .viz import draw_overlay

WEB = Path(__file__).parent / "web"


class LiveApp:
    def __init__(self, pipeline, calib_path="calib.json", jpeg_quality: int = 70, max_width: int = 960,
                 stale_after: float = 0.6):
        self.pipe = pipeline
        self.calib_path = Path(calib_path)
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


def make_handler(app: LiveApp, camera_url: str):
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
            if path == "/state":
                return self._send(200, app.current_state(), "application/json")
            if path == "/scene":
                info = app.pipe.scene_info()
                info["camera_url"] = camera_url
                return self._send(200, json.dumps(info).encode(), "application/json")
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
