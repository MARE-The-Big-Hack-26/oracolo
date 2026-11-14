import json
import time
import urllib.request

from oracolo.cab import PAGE, CabServer
from oracolo.machine import MachineCommand


def get(url):
    with urllib.request.urlopen(url, timeout=3) as r:
        return r.read().decode()


def test_cab_server_serves_page_and_state():
    srv = CabServer(host="127.0.0.1", port=0).start()
    try:
        base = f"http://127.0.0.1:{srv.port}"
        assert "Cabina carrello" in get(base + "/")
        assert json.loads(get(base + "/state")) == {}
        srv.push(MachineCommand(7, 1.0, 0.8, 2, cause="zona_non_osservata", ttl=0.25))
        s = json.loads(get(base + "/state"))
        assert s["seq"] == 7 and s["level"] == 2 and s["speed_limit"] == 0.8
        assert "ignoto" in s["cause_it"]
    finally:
        srv.stop()


def test_page_contains_failsafe_watchdog():
    # la pagina (cioè l'iPhone) va in STOP da sola se non arrivano comandi nuovi
    assert "NESSUN COMANDO VALIDO" in PAGE and "age>ttl" in PAGE
