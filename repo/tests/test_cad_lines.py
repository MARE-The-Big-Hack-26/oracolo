import ezdxf

from oracolo.cad import load_dxf


def test_muri_a_segmenti(tmp_path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    for a, b in [((0, 0), (5, 0)), ((5, 0), (5, 4)), ((5, 4), (0, 4)), ((0, 4), (0, 0))]:
        msp.add_line(a, b, dxfattribs={"layer": "WALLS"})
    doc.layers.add("ARMADIO_H2.0")
    msp.add_lwpolyline([(1, 1), (2, 1), (2, 2), (1, 2)], close=True, dxfattribs={"layer": "ARMADIO_H2.0"})
    p = tmp_path / "scan.dxf"
    doc.saveas(p)
    scene, info = load_dxf(p, lines_as_walls=True)
    minx, miny, maxx, maxy = scene.bounds.bounds
    assert abs(minx + 0.05) < 0.1 and abs(maxx - 5.05) < 0.1  # i muri sottili stanno sul bordo
    assert info["occluders"] == 5
    assert any(o.height == 2.0 for o in scene.occluders)
