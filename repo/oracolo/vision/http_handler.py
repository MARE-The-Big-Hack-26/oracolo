"""Trasporto HTTP/HTTPS e routing per il server live Oracolo."""
from __future__ import annotations

import json
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2

from .certs import maybe_wrap_tls

WEB = Path(__file__).parent / "web"
MAX_DXF_BYTES = 20 * 1024 * 1024
_PAGES = {"/": "panel.html", "/panel": "panel.html", "/camera": "camera.html", "/calibrate": "calibrate.html", "/room": "room.html"}
SAMPLES_DIR = Path(__file__).parent / "samples"
# planimetrie di prova incluse: l'utente le sceglie dal pannello senza avere un DXF. nome -> (file, titolo)
SAMPLES = {
    "aula": ("aula_studio_prova.dxf", "Aula 9,9 × 9 m, 4 tavoli (prova)"),
    "magazzino": ("magazzino_prova.dxf", "Magazzino 24 × 14 m, scaffali e pilastri (prova, file con «sporco» da pulire)"),
}
_JS = ("/room.js", "/room_cam.js", "/calibrate.js", "/anchors.js", "/dxfload.js")


def make_handler(app, camera_url: str = "", ssl_ctx: ssl.SSLContext | None = None):
    if camera_url and not app.camera_url:
        app.camera_url = camera_url

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):  # accetta sia HTTP (localhost / tunnel) sia HTTPS diretto sulla stessa porta
            self.request = maybe_wrap_tls(self.request, ssl_ctx)
            super().setup()

        def log_message(self, *a):  # silenzio
            pass

        def _send(self, code, body: bytes, ctype="text/plain; charset=utf-8", extra=None):
            self.send_response(code)
            if code != 204:
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if code != 204 and body:
                self.wfile.write(body)

        def _read_body(self) -> bytes:
            if "chunked" in self.headers.get("Transfer-Encoding", "").lower():
                chunks = []
                while True:
                    line = self.rfile.readline().split(b";", 1)[0].strip()
                    size = int(line, 16) if line else 0
                    if size == 0:
                        while self.rfile.readline() not in (b"\r\n", b"\n", b""):
                            pass
                        return b"".join(chunks)
                    chunks.append(self.rfile.read(size))
                    self.rfile.read(2)
            n = int(self.headers.get("Content-Length", "0"))
            return self.rfile.read(n) if n else b""

        def _json_post(self, fn, body: bytes):
            try:
                return self._send(200, json.dumps(fn(json.loads(body or b"{}"))).encode(), "application/json")
            except (ValueError, KeyError, TypeError, cv2.error) as e:
                return self._send(400, json.dumps({"ok": False, "error": str(e)}).encode(), "application/json")

        def do_GET(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in _PAGES:
                return self._send(200, (WEB / _PAGES[path]).read_bytes(), "text/html; charset=utf-8")
            if path in _JS:
                return self._send(200, (WEB / path.lstrip("/")).read_bytes(), "application/javascript; charset=utf-8")
            if path == "/state":
                return self._send(200, app.current_state(), "application/json")
            if path == "/scene":
                info = app.pipe.scene_info()
                info["camera_url"] = app.camera_url or camera_url
                info["no_scene"] = not app.scene_loaded
                info["cad"] = app.cad_report
                return self._send(200, json.dumps(info).encode(), "application/json")
            if path == "/samples":
                out = [{"name": k, "title": t} for k, (_, t) in SAMPLES.items()]
                return self._send(200, json.dumps(out).encode(), "application/json")
            if path == "/anchors":
                a = app.pipe.anchors
                out = {"anchors": None if a is None else a.to_dict(), "error": app.anchors_error,
                       "align": json.loads(app.current_state()).get("align")}
                return self._send(200, json.dumps(out).encode(), "application/json")
            if path == "/qr.png":
                return self._send(200, app.qr_png(camera_url), "image/png")
            if path == "/snapshot.jpg":
                return self._send(200, app.snapshot, "image/jpeg") if app.snapshot else self._send(404, b"nessun frame ricevuto")
            if path == "/video.mjpg":
                return self._mjpeg()
            return self._send(404, b"non trovato")

        def _mjpeg(self):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if not app.annot and app.snapshot:
                app._refresh_annot()
            ver = 0
            try:
                while app.running:
                    with app.cond:
                        app.cond.wait_for(lambda: app.annot_ver != ver or not app.running, timeout=1.0)
                        if not app.running:
                            break
                        if app.annot_ver == ver:
                            continue
                        ver, jpg = app.annot_ver, app.annot
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpg))
                    self.wfile.write(jpg + b"\r\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ssl.SSLError, OSError):
                pass

        def do_POST(self):  # noqa: N802
            if self.path == "/dxf" and "chunked" not in self.headers.get("Transfer-Encoding", "").lower():
                if int(self.headers.get("Content-Length", "0")) > MAX_DXF_BYTES:
                    self.close_connection = True
                    out = {"ok": False, "errors": [f"File troppo grande (> {MAX_DXF_BYTES // 2**20} MB)."], "warnings": [], "stats": {}}
                    return self._send(413, json.dumps(out).encode(), "application/json")
            body = self._read_body()
            if self.path == "/frame":
                app.push_jpeg(body)
                return self._send(204, b"")
            if self.path == "/calib":
                return self._json_post(app.apply_calibration, body)
            if self.path == "/anchors":
                return self._json_post(app.apply_anchors, body)
            if self.path == "/calib_anchors":
                return self._json_post(app.calibrate_from_anchors, body)
            if self.path == "/dxf":
                if len(body) > MAX_DXF_BYTES:
                    out = {"ok": False, "errors": [f"File troppo grande (> {MAX_DXF_BYTES // 2**20} MB)."], "warnings": [], "stats": {}}
                    return self._send(413, json.dumps(out).encode(), "application/json")
                out = app.apply_dxf(body, self.headers.get("X-Filename", ""))
                return self._send(200 if out["ok"] else 400, json.dumps(out, default=str).encode(), "application/json")
            if self.path == "/sample":
                try:
                    name = json.loads(body or b"{}").get("name", "")
                except ValueError:
                    name = ""
                if name not in SAMPLES:  # solo nomi della lista: nessun percorso arbitrario
                    return self._send(400, json.dumps({"ok": False, "errors": ["Planimetria di prova sconosciuta."],
                                                       "warnings": [], "stats": {}}).encode(), "application/json")
                fname = SAMPLES[name][0]
                out = app.apply_dxf((SAMPLES_DIR / fname).read_bytes(), fname)
                out["sample"] = name
                return self._send(200 if out["ok"] else 400, json.dumps(out, default=str).encode(), "application/json")
            if self.path == "/scene":
                return self._json_post(app.apply_scene, body)
            return self._send(404, b"non trovato")

    return H


class QuietServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):  # handshake TLS rifiutati ecc.: nessun rumore
        pass
