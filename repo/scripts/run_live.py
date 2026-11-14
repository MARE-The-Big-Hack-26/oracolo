"""Demo in tempo reale: il Mac simula la camera fissa + Oracolo e INVIA i comandi all'iPhone.

    python scripts/run_live.py                 # server sulla porta 8000
    -> sull'iPhone (stessa rete Wi-Fi) apri Safari su  http://<IP-del-Mac>:8000
    python scripts/run_live.py --cut-at 7      # a t=7 s smette di inviare: l'iPhone va in STOP da solo
    python scripts/run_live.py --loop          # ripete all'infinito (per provare/registrare)
"""
import argparse
import time

from oracolo.cab import CabServer
from oracolo.machine import MachineCommand
from oracolo.sim import run_scenario
from oracolo.vision.certs import start_tunnel
from oracolo.warehouse import warehouse_scenario

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8000)
ap.add_argument("--mode", default="oracolo", choices=["none", "static_zone", "reactive", "oracolo"])
ap.add_argument("--dxf", default=None, help="file DXF del magazzino (default: esempio)")
ap.add_argument("--cut-at", type=float, default=None, help="secondi dopo cui il collegamento Mac→iPhone si interrompe")
ap.add_argument("--loop", action="store_true")
ap.add_argument("--speed", type=float, default=1.0, help="1 = tempo reale")
ap.add_argument("--no-tunnel", action="store_true", help="usa solo LAN locale senza tunnel HTTPS pubblico")
a = ap.parse_args()

srv = CabServer(port=a.port).start()
tunnel_url, _tunnel_proc = (None, None)
if not a.no_tunnel:
    print("Avvio tunnel HTTPS sicuro...")
    tunnel_url, _tunnel_proc = start_tunnel(srv.port)
if tunnel_url:
    print(f"Cabina pronta (HTTPS sicuro, qualsiasi dispositivo): {tunnel_url}")
print(f"Cabina pronta (LAN locale, stessa rete Wi-Fi): http://{CabServer.local_ip()}:{srv.port}")
seq = [0]

try:
    while True:
        sc = warehouse_scenario(a.dxf)
        t0 = time.monotonic()

        def hook(t, oracle, machine, truth, limit, level, cause):
            wait = t0 + t / a.speed - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            if a.cut_at is not None and t >= a.cut_at:
                return  # collegamento interrotto: nessun comando
            seq[0] += 1
            srv.push(MachineCommand(seq[0], t, limit, level, cause, ttl=0.25))

        res = run_scenario(sc, a.mode, hook=hook)
        print(f"fine: collisione={res.collision}  distanza minima={res.min_dist:.2f} m  transito={res.t_end:.1f} s")
        if not a.loop:
            time.sleep(3)
            break
        time.sleep(2)
finally:
    if _tunnel_proc is not None and _tunnel_proc.poll() is None:
        _tunnel_proc.terminate()
