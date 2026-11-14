"""Genera i marker ArUco da stampare per le ANCORE a terra (id 10-13, DICT_4X4_50) a misura esatta.

    python scripts/make_anchor_markers.py                       # A3, quadrato nero 20 cm, id 10-13 -> ../markers/
    python scripts/make_anchor_markers.py --paper A4 --black-cm 15

Stampare al 100% (nessun «adatta alla pagina»), su carta opaca, incollare PIATTO a terra. DOPO la stampa
misurare il quadrato NERO con un righello e, se serve, correggere «lato del quadrato nero» nel pannello.
Il lato SUPERIORE (freccia +Y sulla pagina) va rivolto verso +Y della planimetria.
Il bordo bianco (1 cella = lato/6) fa parte del marker: non ritagliarlo.
"""
import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

DPI = 300
PAPER_CM = {"A4": (21.0, 29.7), "A3": (29.7, 42.0)}
ap = argparse.ArgumentParser()
ap.add_argument("--ids", type=int, nargs="+", default=[10, 11, 12, 13])
ap.add_argument("--black-cm", type=float, default=20.0, help="lato del quadrato nero (consigliato 20; minimo 15)")
ap.add_argument("--paper", choices=sorted(PAPER_CM), default="A3")
ap.add_argument("--fill", action="store_true",
                help="marker il più grande possibile per la larghezza della pagina (bordo bianco ~0,8 celle), senza testo di istruzioni")
ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent.parent / "markers"))
a = ap.parse_args()

pw, ph = PAPER_CM[a.paper]
if a.fill:  # nero = (larghezza - 0,4 cm di tolleranza) * 6 / 7,5: bordo bianco di ~0,8 celle per parte
    a.black_cm = int((pw - 0.4) * 6 / 7.5 * 10) / 10
total_cm = a.black_cm * 8 / 6  # nero + bordo bianco di 1 cella (lato/6) per parte
if not a.fill and total_cm > pw - 0.5:
    raise SystemExit(f"{a.black_cm} cm + bordo bianco = {total_cm:.1f} cm non entra nel lato corto di {a.paper} ({pw} cm): "
                     f"usare {'--paper A3' if a.paper == 'A4' else 'un lato minore'} (A4: massimo ~15 cm).")
px_page = (round(pw / 2.54 * DPI), round(ph / 2.54 * DPI))
side = round(a.black_cm / 2.54 * DPI / 6) * 6          # multiplo di 6: celle di pixel interi
real_cm = side / DPI * 2.54
cell = side // 6
d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
for mid in a.ids:
    page = np.full((px_page[1], px_page[0]), 255, np.uint8)
    m = cv2.aruco.generateImageMarker(d, mid, side)
    x0, y0 = (px_page[0] - side) // 2, int(px_page[1] * 0.12)
    if a.fill:
        y0 = (px_page[1] - side) // 2
    page[y0:y0 + side, x0:x0 + side] = m
    if a.fill:  # solo id e freccia +Y piccoli, lontani dal marker (nelle fasce libere sopra e sotto)
        font = cv2.FONT_HERSHEY_SIMPLEX
        ax = px_page[0] // 2
        cv2.arrowedLine(page, (ax, int(px_page[1] * 0.075)), (ax, int(px_page[1] * 0.03)), 0, 6, tipLength=0.4)
        cv2.putText(page, f"id {mid}   +Y", (x0, int(px_page[1] * 0.965)), font, 1.4, 0, 3, cv2.LINE_AA)
        name = f"marker_ancora_ID{mid}_pagina_piena_{a.paper}"
        cv2.imwrite(str(out / f"{name}.png"), page)
        Image.fromarray(((page > 127) * 255).astype(np.uint8)).convert("1").save(out / f"{name}.pdf", resolution=DPI)
        continue
    ty = y0 + side + cell + 60
    font, sc, th = cv2.FONT_HERSHEY_SIMPLEX, 2.2, 5
    for i, line in enumerate((f"ANCORA ArUco id {mid}  (4x4_50)", f"lato quadrato NERO = {real_cm:.1f} cm  -  stampa al 100%",
                              "lato SUPERIORE (freccia) verso +Y della planimetria")):
        cv2.putText(page, line, (x0 - cell // 2, ty + i * 110), font, sc if i == 0 else 1.5, 0, th if i == 0 else 3, cv2.LINE_AA)
    ax = px_page[0] // 2  # freccia +Y sopra il marker
    cv2.arrowedLine(page, (ax, y0 - 40), (ax, max(40, y0 - 40 - cell)), 0, 14, tipLength=0.4)
    cv2.putText(page, "+Y", (ax + 40, y0 - 70), font, 2.2, 0, 5, cv2.LINE_AA)
    cv2.imwrite(str(out / f"marker_ancora_ID{mid}_{int(round(a.black_cm))}cm_{a.paper}.png"), page)
    Image.fromarray(((page > 127) * 255).astype(np.uint8)).convert("1").save(
        out / f"marker_ancora_ID{mid}_{int(round(a.black_cm))}cm_{a.paper}.pdf", resolution=DPI)
print(f"{len(a.ids)} marker in {out}  (nero {real_cm:.2f} cm su {a.paper}, {DPI} dpi)")
