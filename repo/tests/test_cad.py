import ezdxf
import pytest

from oracolo.cad import _layer_height, load_dxf


def make_dxf(path, insunits=4, k=1000):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = insunits
    doc.layers.add("PERIMETRO")
    doc.layers.add("SCAFFALI_H3000")
    doc.layers.add("BANCALI_H1.0")
    doc.layers.add("QUOTE")
    msp = doc.modelspace()
    r = lambda l, x0, y0, x1, y1: msp.add_lwpolyline(
        [(x0 * k, y0 * k), (x1 * k, y0 * k), (x1 * k, y1 * k), (x0 * k, y1 * k)], close=True, dxfattribs={"layer": l})
    r("PERIMETRO", 0, 0, 20, 10)
    r("SCAFFALI_H3000", 2, 2, 8, 4)
    r("BANCALI_H1.0", 10, 2, 11, 3)
    r("QUOTE", 0, 0, 1, 1)
    msp.add_line((0, 0), (5 * k, 5 * k), dxfattribs={"layer": "SCAFFALI_H3000"})  # entità non supportata: ignorata
    doc.saveas(path)


def test_layer_height_parsing():
    assert _layer_height("SCAFFALI_H3000", 9) == 3.0
    assert _layer_height("pallet_h1.2", 9) == 1.2
    assert _layer_height("MURI", 3.0) == 3.0


def test_load_dxf_mm(tmp_path):
    p = tmp_path / "w.dxf"
    make_dxf(str(p))
    scene, info = load_dxf(str(p), ignore_layers=["QUOTE"])
    assert info["unit_m"] == 0.001
    assert scene.bounds.bounds == pytest.approx((0, 0, 20, 10))
    assert len(scene.occluders) == 2
    heights = sorted(o.height for o in scene.occluders)
    assert heights == [1.0, 3.0]


def test_load_dxf_meters_and_default_bounds(tmp_path):
    p = tmp_path / "w2.dxf"
    make_dxf(str(p), insunits=6, k=1)
    scene, _ = load_dxf(str(p), ignore_layers=["QUOTE", "PERIMETRO"])
    assert scene.bounds.contains(scene.occluders[0].poly)  # perimetro dedotto dagli ostacoli
