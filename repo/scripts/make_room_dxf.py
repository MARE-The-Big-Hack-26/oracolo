"""Genera un DXF della stanza da un elenco di misure (JSON). Serve quando non c'è il CAD.

    python scripts/make_room_dxf.py scenarios/stanza_esempio.json scenarios/stanza.dxf

Formato JSON (metri; origine a scelta, es. un angolo della stanza):
  {"perimetro": [x, y, larghezza, profondita],
   "ostacoli": [{"nome": "armadio", "x": 0.2, "y": 1.0, "w": 0.6, "d": 1.8, "altezza": 2.0}, ...]}
Ogni ostacolo diventa una polilinea chiusa sul layer ``<NOME>_H<altezza>``: l'importatore ne ricava l'altezza.
"""
import json
import re
import sys
from pathlib import Path

import ezdxf


def build(spec: dict, out: str) -> None:
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6  # metri
    msp = doc.modelspace()
    x, y, w, d = spec["perimetro"]
    doc.layers.add("PERIMETRO")
    msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + d), (x, y + d)], close=True, dxfattribs={"layer": "PERIMETRO"})
    for o in spec.get("ostacoli", []):
        nome = re.sub(r"[^A-Za-z0-9]+", "_", o.get("nome", "OSTACOLO")).upper()
        layer = f"{nome}_H{float(o['altezza']):.2f}"
        if layer not in doc.layers:
            doc.layers.add(layer)
        ox, oy, ow, od = o["x"], o["y"], o["w"], o["d"]
        msp.add_lwpolyline([(ox, oy), (ox + ow, oy), (ox + ow, oy + od), (ox, oy + od)], close=True, dxfattribs={"layer": layer})
    doc.saveas(out)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    build(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
    print("scritto", sys.argv[2])
