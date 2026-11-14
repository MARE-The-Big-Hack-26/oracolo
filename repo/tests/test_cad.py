import ezdxf
import pytest

from oracolo.cad import _layer_height, load_dxf, save_dxf, scene_from_spec


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


def test_scene_from_spec_irregolare_corridoio_e_roundtrip_dxf(tmp_path):
    l_bounds = [[0, 0], [6, 0], [6, 2], [2, 2], [2, 6], [0, 6]]
    l_obs = [[0.4, 0.4], [1.6, 0.4], [1.6, 0.8], [0.8, 0.8], [0.8, 1.6], [0.4, 1.6]]
    tri = [[3.0, 0.3], [4.2, 0.3], [3.6, 1.4]]
    sc = scene_from_spec({
        "bounds": l_bounds,
        "obstacles": [
            {"name": "scaffale_L", "coords": l_obs, "height": 1.9},
            {"name": "pilastro", "polygon": tri, "height": 2.4},
            {"name": "divisorio", "wall": {"points": [[0.5, 3.0], [1.5, 4.5]], "width": 0.2}, "height": 2.1},
        ],
    })
    assert sc.bounds.area == pytest.approx(20.0)
    assert len(sc.bounds.exterior.coords) == 7
    assert len(sc.occluders) == 3
    assert sc.occluders[0].poly.area == pytest.approx(0.8)
    assert len(sc.occluders[0].poly.exterior.coords) == 7

    dxf = tmp_path / "l_room.dxf"
    save_dxf(sc, dxf)
    reloaded, _ = load_dxf(dxf)
    assert reloaded.bounds.area == pytest.approx(sc.bounds.area)
    assert len(reloaded.bounds.exterior.coords) == len(sc.bounds.exterior.coords)
    assert sorted(round(o.poly.area, 3) for o in reloaded.occluders) == sorted(round(o.poly.area, 3) for o in sc.occluders)

    corridor = scene_from_spec({"corridor": {"points": [[0, 0], [4, 0], [4, 4]], "width": 2.0}})
    assert corridor.bounds.area == pytest.approx(16.0)
    assert len(corridor.bounds.exterior.coords) == 7
