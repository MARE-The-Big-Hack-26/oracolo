"""Pipeline live con camera fissa (iPhone su treppiede) -> pannello sul Mac.

    PYTHONPATH=. python scripts/run_camera.py
    -> si parte SENZA planimetria: nel pannello si sceglie «Carica DXF» (solo DXF) oppure «Disegna planimetria»
    -> ripiego da terminale:  --dxf percorso/del/file.dxf   (i file in scenarios/ sono solo esempi)
    -> sul Mac:   https://localhost:8443/            (pannello)
    -> sull'iPhone: https://<IP-del-Mac>:8443/camera   (accetta l'avviso del certificato, premi Avvia)
    -> prima volta: https://localhost:8443/calibrate

Sorgenti alternative (piano B): --source video:clip.mp4 [--loop]   --source cam:0
"""
import argparse
import sys
import threading
import time
from pathlib import Path

import cv2

from shapely.geometry import box

from oracolo.cad_norm import normalize_dxf
from oracolo.geometry import Scene
from oracolo.policy import PedParams, VehicleParams
from oracolo.vision.calib import Calibration
from oracolo.vision.certs import ensure_cert, lan_ip, start_tunnel
from oracolo.vision.detectors import MarkerDetector, build_person_detector
from oracolo.vision.pipeline import LivePipeline
from oracolo.vision.server import LiveApp, serve

ap = argparse.ArgumentParser()
ap.add_argument("--dxf", default=None,
                help="(facoltativo) planimetria DXF da caricare subito; senza, la si sceglie nel pannello: Carica DXF o Disegna")
ap.add_argument("--room-file", default="planimetria.dxf",
                help="dove si salva la planimetria (caricata o disegnata) in formato standard; non sovrascrive --dxf")
ap.add_argument("--calib", default="calib.json")
ap.add_argument("--anchors", default="anchors.json",
                help="ancore ArUco a terra (id 10-17) con le coordinate nel CAD; si impostano anche da /calibrate")
ap.add_argument("--source", default="stream", help="stream | video:PERCORSO | cam:INDICE")
ap.add_argument("--detector", default="auto",
                help="auto | yolo[:pose|11n|11s] | rfdetr[:nano|small|base] | hog | none")
ap.add_argument("--port", type=int, default=8443)
ap.add_argument("--http", action="store_true", help="senza HTTPS (solo prove sul Mac: l'iPhone richiede HTTPS)")
ap.add_argument("--no-tunnel", action="store_true", help="usa solo LAN locale senza tunnel HTTPS pubblico")
ap.add_argument("--certs", default="certs")
ap.add_argument("--marker-id", type=int, default=0)
ap.add_argument("--marker-h", type=float, default=0.45, help="quota del marker sulla sedia (m)")
ap.add_argument("--default-height", type=float, default=3.0, help="altezza (m) degli ostacoli senza suffisso _H")
ap.add_argument("--lines-as-walls", action="store_true", help="DXF di scansione LiDAR: LINE/polilinee aperte = muri")
ap.add_argument("--profile", default="sedia", choices=["sedia", "magazzino"],
                help="sedia: parametri in scala per la demo con la sedia; magazzino: carrello reale (8 km/h)")
ap.add_argument("--loop", action="store_true")
a = ap.parse_args()

if a.dxf:
    if not Path(a.dxf).exists():
        sys.exit(f"DXF non trovato: {a.dxf}")
    scene, rep = normalize_dxf(a.dxf, default_height=a.default_height, lines_as_walls=a.lines_as_walls)
    if scene is None:
        sys.exit("DXF non utilizzabile:\n  - " + "\n  - ".join(rep["errors"]))
    st = rep["stats"]
    print(f"Planimetria: {a.dxf}  ostacoli={st['occluders']}  dimensioni={st['size_m'][0]}x{st['size_m'][1]} m")
    for w in rep["warnings"]:
        print("  avviso:", w)
else:
    scene, rep = Scene(box(0, 0, 5, 4), []), None  # segnaposto finché non si sceglie nel pannello
    print("Planimetria: nessuna. Nel pannello scegli «Carica DXF» oppure «Disegna planimetria».")

calib = Calibration.load(a.calib) if Path(a.calib).exists() else None
print("Calibrazione:", f"caricata da {a.calib} (errore {calib.rms_m * 100:.1f} cm)" if calib else "assente: apri /calibrate")

PROFILES = {
    # sedia spinta a mano: ~1 m/s, ingombro 0,6 m, area di prova di pochi metri
    "sedia": VehicleParams(v_max=1.0, a_brake=1.2, t_sys=0.4, t_act=0.1, margin=0.3, half_width=0.3, horizon=3.0, max_frame_age=1.2),
    "magazzino": VehicleParams(max_frame_age=1.2),
}
person_det = build_person_detector(a.detector)
det_desc = f"{type(person_det).__name__}" + (f" ({person_det.weights}, {person_det.device})" if hasattr(person_det, "weights") else "")
print(f"Rilevatore persone: {det_desc}")
pipe = LivePipeline(scene, calib, params=PROFILES[a.profile], ped=PedParams(v_walk=1.3, radius=0.3),
                    person_detector=person_det,
                    marker=MarkerDetector(a.marker_id, height=a.marker_h))
ip = lan_ip()
lan_cam_url = f"{'http' if a.http else 'https'}://{ip}:{a.port}/camera"
app = LiveApp(pipe, a.calib, dxf_path=a.room_file, scene_loaded=bool(a.dxf), anchors_path=a.anchors)
app.default_height, app.lines_as_walls = a.default_height, a.lines_as_walls
if rep is not None:
    app.cad_report = {**rep, "source": "dxf", "filename": Path(a.dxf).name}
print("Ancore a terra:", "caricate da " + a.anchors if pipe.anchors is not None else
      "nessuna (allineamento CAD-video non verificato): impostale da /calibrate")
if app.anchors_error:
    print("  ATTENZIONE: ancore non lette:", app.anchors_error)
cert, key = (None, None) if a.http else ensure_cert(a.certs)
serve(app, "0.0.0.0", a.port, cert, key, lan_cam_url)

tunnel_url, _tunnel_proc = (None, None)
if not a.http and not a.no_tunnel:
    print("Avvio tunnel HTTPS sicuro (nessun avviso certificato su iPhone/Mac)...")
    tunnel_url, _tunnel_proc = start_tunnel(a.port)
    if tunnel_url:
        app.camera_url = f"{tunnel_url}/camera"


def capture(kind: str, arg: str):
    cap = cv2.VideoCapture(int(arg) if kind == "cam" else arg)
    if not cap.isOpened():
        print(f"ERRORE: impossibile aprire la sorgente {kind}:{arg}")
        return
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    dt = 1.0 / min(max(fps, 5.0), 30.0)
    while True:
        t0 = time.monotonic()
        ok, frame = cap.read()
        if not ok:
            if kind == "video" and a.loop:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            time.sleep(0.5)
            continue
        app.push_frame(frame)
        time.sleep(max(0.0, dt - (time.monotonic() - t0)))


if a.source != "stream":
    kind, _, arg = a.source.partition(":")
    threading.Thread(target=capture, args=(kind, arg), daemon=True).start()

print(f"\nPannello (Mac):  http://localhost:{a.port}/   (nessun avviso certificato)")
print(f"Planimetria:     http://localhost:{a.port}/room")
print(f"Calibrazione:    http://localhost:{a.port}/calibrate")
if tunnel_url:
    print(f"iPhone (HTTPS sicuro):   {tunnel_url}/camera")
    print(f"Pannello remoto (HTTPS): {tunnel_url}/")
    print(f"Fallback LAN locale:     {lan_cam_url}")
else:
    print(f"iPhone (LAN):            {lan_cam_url}")
print("(Ctrl+C per fermare)")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    app.running = False
    if _tunnel_proc is not None and _tunnel_proc.poll() is None:
        _tunnel_proc.terminate()
