"""Ricevitore "cabina": simula il sensore/controller montato sul carrello.

Gira sul Mac come piccolo server web; l'iPhone apre la pagina in Safari (stessa rete) e
fa da carrello: mostra livello, limite di velocità e causa. La logica fail-safe sta nella
pagina stessa: se non arriva un comando nuovo entro il TTL, la pagina va in STOP da sola,
come farebbe il controller reale (watchdog). Solo libreria standard, nessuna dipendenza.

    srv = CabServer(port=8000); srv.start(); srv.push(MachineCommand(...))
"""
from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .machine import MachineCommand

PAGE = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Cabina carrello</title><style>
html,body{margin:0;height:100%;font-family:-apple-system,Helvetica,Arial,sans-serif;color:#fff;background:#111}
#bg{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;transition:background .12s;text-align:center}
#lvl{font-size:16vw;font-weight:800;letter-spacing:.02em}
#sym{font-size:9vw;margin-top:-1vw}
#spd{font-size:13vw;font-weight:700;margin:2vh 0}
#cause{font-size:5vw;opacity:.95;padding:0 4vw}
#link{position:fixed;top:env(safe-area-inset-top,8px);left:8px;right:8px;font-size:3.6vw;opacity:.9;display:flex;justify-content:space-between}
</style></head><body><div id="bg"><div id="link"><span id="l1">in attesa…</span><span id="l2"></span></div>
<div id="lvl">—</div><div id="sym"></div><div id="spd"></div><div id="cause"></div></div>
<script>
const COL=["#1b8a3a","#b58900","#cc6a10","#b3261e"],NAME=["NORMALE","ATTENZIONE","RALLENTA","FERMA"],SYM=["▶","△","▼","■"];
let last=null,lastRx=0,lastSeq=-1;
async function poll(){try{const r=await fetch("/state?_="+Date.now(),{cache:"no-store"});const s=await r.json();
 if(s.seq!==undefined&&s.seq!==lastSeq){lastSeq=s.seq;last=s;lastRx=performance.now();}}catch(e){}}
function draw(){const now=performance.now();const bg=document.getElementById("bg");
 if(!last){return}
 const age=now-lastRx,ttl=(last.ttl||0.25)*1000+250;  // +250 ms: tolleranza di polling
 let lv=last.level,lim=last.speed_limit,why=last.cause_it;
 if(age>ttl){lv=3;lim=0;why="NESSUN COMANDO VALIDO → arresto automatico";}
 bg.style.background=COL[lv];
 document.getElementById("lvl").textContent=NAME[lv];document.getElementById("sym").textContent=SYM[lv];
 document.getElementById("spd").textContent=(lim*3.6).toFixed(1)+" km/h";
 document.getElementById("cause").textContent=why;
 document.getElementById("l1").textContent="seq "+last.seq;
 document.getElementById("l2").textContent="ultimo comando "+Math.round(age)+" ms fa";}
setInterval(poll,80);setInterval(draw,40);
</script></body></html>"""

CAUSE_IT = {
    "nessuno": "Via libera",
    "osservato": "Persona vista",
    "persona_nascosta": "Persona possibile dietro l'ostacolo",
    "zona_non_osservata": "Zona non visibile: ignoto ≠ libero",
    "affidabilita_persa": "Affidabilità persa",
    "scena_degradata": "Scena degradata",
    "zona_fissa": "Zona a velocità ridotta",
}


class CabServer:
    def __init__(self, host="0.0.0.0", port=8000):
        self.state: dict = {}
        self.lock = threading.Lock()
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.startswith("/state"):
                    with outer.lock:
                        body = json.dumps(outer.state).encode()
                    self._send(200, body, "application/json")
                else:
                    self._send(200, PAGE.encode(), "text/html; charset=utf-8")

        self.httpd = ThreadingHTTPServer((host, port), H)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()

    def push(self, cmd: MachineCommand) -> None:
        d = {
            "seq": cmd.seq, "t_sent": cmd.t_sent, "speed_limit": cmd.speed_limit, "level": cmd.level,
            "cause": cmd.cause, "cause_it": CAUSE_IT.get(cmd.cause, cmd.cause), "ttl": cmd.ttl,
        }
        with self.lock:
            self.state = d

    @staticmethod
    def local_ip() -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"
        finally:
            s.close()
