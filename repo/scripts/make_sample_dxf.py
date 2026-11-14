"""Crea scenarios/magazzino.dxf: un magazzino d'esempio 30 x 20 m (disegno in mm).
Serve da prova dell'import: in produzione si usa il DXF vero del magazzino."""
import sys

import ezdxf

out = sys.argv[1] if len(sys.argv) > 1 else "scenarios/magazzino.dxf"
doc = ezdxf.new("R2010", setup=True)
doc.header["$INSUNITS"] = 4  # millimetri
msp = doc.modelspace()
for name in ("PERIMETRO", "SCAFFALI_H3000", "PILASTRI_H4000", "BANCALI_H1000"):
    doc.layers.add(name)


def rect(layer, x0, y0, x1, y1):
    msp.add_lwpolyline([(x0 * 1000, y0 * 1000), (x1 * 1000, y0 * 1000), (x1 * 1000, y1 * 1000), (x0 * 1000, y1 * 1000)],
                       close=True, dxfattribs={"layer": layer})


rect("PERIMETRO", 0, 0, 30, 20)
# corsia principale y 8..11,5; corsie trasversali a x 9..12 e 19..22
for (x0, x1) in [(1, 9), (12, 19), (22, 29)]:
    rect("SCAFFALI_H3000", x0, 1, x1, 8)
    rect("SCAFFALI_H3000", x0, 11.5, x1, 19)
msp.add_circle((10.5, 9.75 + 1.9), 0.0, dxfattribs={"layer": "PILASTRI_H4000"}) if False else None
rect("BANCALI_H1000", 24, 8.1, 25.2, 8.9)  # bancale basso a bordo corsia
doc.saveas(out)
print("scritto", out)
