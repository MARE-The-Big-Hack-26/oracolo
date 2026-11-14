"""Server live: riceve i frame dell'iPhone, elabora, serve pannello e calibrazione.

    GET  /            pannello (Mac): video con CAD sovrapposto + mappa dall'alto + livello
    GET  /camera      pagina da aprire sull'iPhone: invia i frame della camera
    GET  /calibrate   calibrazione: coppie di punti video <-> mappa
    POST /frame       JPEG dall'iPhone
    GET  /video.mjpg  video annotato (MJPEG)
    GET  /state       stato JSON     GET /scene  planimetria + campo visivo + camera
    GET  /snapshot.jpg ultimo frame grezzo      POST /calib  salva la calibrazione
    GET/POST /anchors  ancore ArUco a terra (id 10-17, coordinate nel CAD)    POST /calib_anchors  calibra dalle ancore
    POST /dxf         carica un DXF (corpo = file): normalizzazione + nuova planimetria (solo DXF, non DWG)
Solo libreria standard (+ OpenCV, NumPy già in uso).
"""
from __future__ import annotations

import json
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import unquote

import cv2
import numpy as np

from ..cab import CAUSE_IT
from ..cad import save_dxf, scene_from_spec
from ..cad_norm import normalize_dxf
from .align import AnchorSet
from .calib import Calibration
from .certs import build_ssl_context
from .http_handler import WEB, QuietServer, make_handler
from .pipeline import json_state
from .viz import draw_overlay, overlay_polys


class LiveApp:
    def __init__(self, pipeline, calib_path="calib.json", jpeg_quality: int = 70, max_width: int = 960,
                 stale_after: float = 1.5, dxf_path=None, scene_loaded: bool = True,
                 anchors_path=None):
        self.pipe, self.calib_path = pipeline, Path(calib_path)
        self.dxf_path = Path(dxf_path) if dxf_path else None
        self.q, self.max_width, self.stale_after = jpeg_quality, max_width, stale_after
        self.cond, self.lock_pipe = threading.Condition(), threading.Lock()
        self._raw, self._raw_ver, self.last_done = None, 0, None
        self.snapshot, self.annot, self.annot_ver = b"", b"", 0
        self.state_obj = {"calibrated": False}
        self.fps, self.latency, self.n_frames, self.running = 0.0, 0.0, 0, True
        self.last_error, self.camera_url = "", ""
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
        with self.lock_pipe:
            self._sync_state_from_scene()
        self._qr_cache: tuple[str | None, bytes] = (None, b"")

    # ---- ingresso frame ------------------------------------------------------------------
    def push_jpeg(self, data: bytes) -> None:
        self.push_frame(data)

    def push_frame(self, frame) -> None:
        with self.cond:
            self._raw = (time.monotonic(), frame)
            self._raw_ver += 1
            if isinstance(frame, (bytes, bytearray)):
                self.snapshot = frame
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
                self._set_annot(img, state)
            except Exception as e:  # noqa: BLE001 (un frame difettoso non deve fermare il server)
                self.last_error = repr(e)

    def _set_annot(self, img, state: dict | None = None) -> None:
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, self.q])
        with self.cond:
            if state is not None:
                self.state_obj = json_state(state)
                self.last_done = time.monotonic()
            if ok:
                self.annot = buf.tobytes()
                self.annot_ver += 1
            if ok or state is not None:
                self.cond.notify_all()

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

    def qr_png(self, fallback: str = "") -> bytes:
        url = self.camera_url or fallback
        if self._qr_cache[0] != url:
            qr = cv2.QRCodeEncoder.create().encode(url or "/camera")
            padded = cv2.copyMakeBorder(qr, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=255)
            img = cv2.resize(padded, (0, 0), fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
            ok, buf = cv2.imencode(".png", img)
            self._qr_cache = (url, buf.tobytes() if ok else b"")
        return self._qr_cache[1]

    def _sync_state_from_scene(self) -> None:
        _, fog_dict = self.pipe.fog_payload()
        with self.cond:
            self.state_obj = {**self.state_obj, "version": self.pipe.version, "calibrated": self.pipe.calib is not None, "fog": fog_dict}
            if self._raw is not None:
                self._raw_ver += 1
            self.cond.notify_all()

    def _refresh_annot(self) -> None:
        raw = self.snapshot
        if not raw:
            return
        frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return
        with self.lock_pipe:
            st = {**self.state_obj, "_fog": self.pipe.fog_payload()[0]}
            img = draw_overlay(frame, self.pipe.calib, self.pipe.scene, st, self.max_width)
        self._set_annot(img)

    # ---- calibrazione --------------------------------------------------------------------
    def apply_calibration(self, body: dict) -> dict:
        cam_xy = body["cam_xy"] if body.get("cam_xy") is not None else self.pipe.cam_spec["xy"]
        cam_h = body["cam_h"] if body.get("cam_h") is not None else self.pipe.cam_spec["h"]
        cal = Calibration.from_pairs(
            body["img"], body["world"], body["image_size"], cam_xy, cam_h,
            fit_distortion=bool(body.get("fit_distortion", True)),
            auto_cam=bool(body.get("auto_cam", False)),
        )
        if body.get("cam_dir") is not None:
            cal.cam_dir = float(body["cam_dir"])
        if body.get("cam_fov") is not None:
            cal.cam_fov = float(body["cam_fov"])
        cal.save(self.calib_path)
        with self.lock_pipe:
            self.pipe.set_calibration(cal)
            fov = self.pipe.scene_info()["fov"]
            overlay = overlay_polys(cal, self.pipe.scene)
            self._sync_state_from_scene()
        self._refresh_annot()
        return {
            "ok": True, "rms_m": round(cal.rms_m, 3), "rms_px": round(cal.rms_px, 2),
            "point_errors_px": cal.point_errors_px, "cam_xy": [round(v, 3) for v in cal.cam_xy],
            "cam_h": round(cal.cam_h, 3), "k1": round(cal.k1, 4), "fov_deg": cal.fov_deg(),
            "overlay": overlay, "fov": fov,
        }

    def apply_scene(self, body: dict) -> dict:
        scene = scene_from_spec(body)
        if self.dxf_path is not None:
            save_dxf(scene, self.dxf_path)
        cam = body.get("cam")
        with self.lock_pipe:
            self.pipe.set_scene(scene)
            if isinstance(cam, dict) and "xy" in cam and "h" in cam:
                self.pipe.set_cam_spec(cam["xy"], cam["h"], cam.get("dir"), cam.get("fov"))
                if self.pipe.calib is not None:
                    self.pipe.calib.save(self.calib_path)
            info = self.pipe.scene_info()
            self._sync_state_from_scene()
        self.scene_loaded = True
        self.cad_report = {"source": "editor", "filename": "", "ok": True, "errors": [], "warnings": [],
                           "stats": {"occluders": len(scene.occluders), "size_m": [round(v, 3) for v in scene.bounds.bounds[2:]]}}
        self._refresh_annot()
        return {"ok": True, "occluders": len(scene.occluders), "bounds_m": [round(v, 3) for v in scene.bounds.bounds],
                "fov": info["fov"], "shadows": info["shadows"]}

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
            self._sync_state_from_scene()
        self._refresh_annot()
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
            self._sync_state_from_scene()
        self.scene_loaded = True
        rep.update({"source": "dxf", "filename": name})
        self.cad_report = rep
        self._refresh_annot()
        return rep


def serve(app: LiveApp, host="0.0.0.0", port=8443, certfile=None, keyfile=None, camera_url="") -> QuietServer:
    if camera_url:
        app.camera_url = camera_url
    ctx = build_ssl_context(certfile, keyfile)
    httpd = QuietServer((host, port), make_handler(app, camera_url, ssl_ctx=ctx))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    threading.Thread(target=app.worker, daemon=True).start()
    return httpd
