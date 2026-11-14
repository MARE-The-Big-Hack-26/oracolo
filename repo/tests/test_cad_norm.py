"""Normalizzazione del CAD: DXF 'sporco' -> stanza in metri con origine (0,0)."""
import subprocess
import sys
from pathlib import Path

import ezdxf
import pytest

from oracolo.cad import load_dxf, save_dxf
from oracolo.cad_norm import normalize_dxf

ROOT = Path(__file__).resolve().parent.parent
REALISTIC = ROOT / "scenarios" / "magazzino_realistico_mm.dxf"


def rect(msp, layer, x0, y0, x1, y1, k=1.0):
    msp.add_lwpolyline([(x0 * k, y0 * k), (x1 * k, y0 * k), (x1 * k, y1 * k), (x0 * k, y1 * k)], close=True,
                       dxfattribs={"layer": layer})


def new_doc(insunits=6):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = insunits
    return doc, doc.modelspace()


def test_realistic_dxf_is_normalized():
    scene, rep = normalize_dxf(REALISTIC)
    assert rep["ok"] and not rep["errors"]
    assert scene.bounds.bounds == pytest.approx((0, 0, 24, 14))
    heights = sorted(round(o.height, 2) for o in scene.occluders)
    assert heights == [1.2] * 2 + [2.8] * 4 + [4.0] * 6
    assert rep["stats"]["origin_offset_m"] == pytest.approx((152.0, 87.0))
    assert rep["stats"]["unit_m"] == 0.001
    layers = " ".join(rep["stats"]["layers"]).upper()
    assert "DOOR" not in layers and "FURNITURE" not in layers and "DIM" not in layers and "TEXT" not in layers
    for o in scene.occluders:  # tutto dentro il perimetro
        assert scene.bounds.buffer(0.01).contains(o.poly)
    assert rep["warnings"], "gli avvisi (layer ignorati, oggetti minuscoli) devono esserci sempre"


def test_normalized_scene_roundtrips_through_save_dxf(tmp_path):
    scene, _ = normalize_dxf(REALISTIC)
    out = tmp_path / "std.dxf"
    save_dxf(scene, out)
    again, info = load_dxf(out)
    assert again.bounds.bounds == pytest.approx((0, 0, 24, 14))
    assert len(again.occluders) == 12


def test_real_cad_without_height_in_layer_names_uses_default(tmp_path):
    doc, msp = new_doc()
    rect(msp, "A-WALL", 0, 0, 30, 20)
    rect(msp, "RACKS", 5, 5, 6, 15)
    rect(msp, "RACKS", 10, 5, 11, 15)
    rect(msp, "COLONNE", 20, 10, 20.5, 10.5)
    p = tmp_path / "a.dxf"
    doc.saveas(p)
    scene, rep = normalize_dxf(p, default_height=2.5)
    assert rep["ok"] and len(scene.occluders) == 3
    assert {o.height for o in scene.occluders} == {2.5}
    assert any("default" in w or "usata 2.5" in w for w in rep["warnings"])


def test_perimeter_found_by_shape_not_by_layer_name(tmp_path):
    doc, msp = new_doc()
    rect(msp, "0", 100, 200, 120, 210)       # layer '0': nessun nome utile
    rect(msp, "0", 102, 202, 104, 206)
    rect(msp, "0", 110, 203, 112, 207)
    p = tmp_path / "b.dxf"
    doc.saveas(p)
    scene, rep = normalize_dxf(p)
    assert rep["stats"]["perimeter_source"] == "forma"
    assert scene.bounds.bounds == pytest.approx((0, 0, 20, 10))
    assert len(scene.occluders) == 2


def test_double_wall_outline_uses_inner_and_drops_outer(tmp_path):
    doc, msp = new_doc()
    rect(msp, "MURI", 0, 0, 20.4, 10.4)       # esterno
    rect(msp, "MURI", 0.2, 0.2, 20.2, 10.2)   # interno
    rect(msp, "ARREDI", 5, 3, 6, 5)
    p = tmp_path / "c.dxf"
    doc.saveas(p)
    scene, rep = normalize_dxf(p)
    assert scene.bounds.bounds == pytest.approx((0, 0, 20, 10))
    assert len(scene.occluders) == 1


def test_unnamed_door_on_perimeter_dropped_but_long_partition_kept(tmp_path):
    doc, msp = new_doc()
    rect(msp, "MURI", 0, 0, 20, 10)
    rect(msp, "XYZ", 8, 0, 9.5, 0.15)         # porta senza nome parlante: sottile, corta, sul muro
    rect(msp, "XYZ", 0, 5, 8, 5.15)           # tramezzo lungo: ostacolo vero
    rect(msp, "XYZ", 12, 3, 13, 4)
    p = tmp_path / "d.dxf"
    doc.saveas(p)
    scene, rep = normalize_dxf(p)
    assert len(scene.occluders) == 2
    assert rep["stats"]["dropped"]["porte_finestre_per_forma"] == 1
    assert any("porte/finestre" in w for w in rep["warnings"])


@pytest.mark.parametrize("insunits", [0, 6])
def test_unit_is_guessed_when_header_missing_or_wrong(tmp_path, insunits):
    doc, msp = new_doc(insunits)
    rect(msp, "MURI", 0, 0, 24, 14, k=1000)   # coordinate in mm
    rect(msp, "SCAFFALI", 5, 3, 6.2, 9, k=1000)
    p = tmp_path / "e.dxf"
    doc.saveas(p)
    scene, rep = normalize_dxf(p)
    assert rep["ok"] and rep["stats"]["unit_m"] == 0.001 and rep["stats"]["unit_source"] == "stimata"
    assert scene.bounds.bounds == pytest.approx((0, 0, 24, 14))
    assert any("verificare" in w for w in rep["warnings"])


def test_no_perimeter_falls_back_to_bbox_with_warning(tmp_path):
    doc, msp = new_doc()
    rect(msp, "SCAFFALI", 5, 3, 6, 9)
    rect(msp, "SCAFFALI", 10, 3, 11, 9)
    p = tmp_path / "f.dxf"
    doc.saveas(p)
    scene, rep = normalize_dxf(p)
    assert rep["ok"] and rep["stats"]["perimeter_source"] == "nessuno"
    assert any("Perimetro non riconosciuto" in w for w in rep["warnings"])
    assert scene.bounds.bounds == pytest.approx((0, 0, 8, 8))  # bbox 6x6 + 1 m per lato


def test_blocks_are_expanded(tmp_path):
    doc, msp = new_doc()
    blk = doc.blocks.new("SCAFFALE")
    blk.add_lwpolyline([(0, 0), (1, 0), (1, 6), (0, 6)], close=True, dxfattribs={"layer": "0"})
    rect(msp, "MURI", 0, 0, 20, 10)
    msp.add_blockref("SCAFFALE", (5, 2), dxfattribs={"layer": "SCAFFALI"})
    msp.add_blockref("SCAFFALE", (9, 2), dxfattribs={"layer": "SCAFFALI"})
    p = tmp_path / "g.dxf"
    doc.saveas(p)
    scene, rep = normalize_dxf(p)
    assert len(scene.occluders) == 2
    assert scene.occluders[0].poly.bounds == pytest.approx((5, 2, 6, 8))


def test_unusable_files_report_errors_not_exceptions(tmp_path):
    doc, msp = new_doc()
    msp.add_text("solo testo", dxfattribs={"layer": "TESTO"})
    p = tmp_path / "h.dxf"
    doc.saveas(p)
    scene, rep = normalize_dxf(p)
    assert scene is None and not rep["ok"] and rep["errors"]
    bad = tmp_path / "x.dxf"
    bad.write_bytes(b"non e' un dxf")
    scene, rep = normalize_dxf(bad)
    assert scene is None and rep["errors"]
    scene, rep = normalize_dxf(tmp_path / "manca.dxf")
    assert scene is None and rep["errors"]


def test_implausible_size_is_an_error(tmp_path):
    doc, msp = new_doc()
    rect(msp, "MURI", 0, 0, 0.3, 0.2)
    rect(msp, "A", 0.05, 0.05, 0.2, 0.1)
    p = tmp_path / "i.dxf"
    doc.saveas(p)
    scene, rep = normalize_dxf(p, unit=1.0)
    assert scene is None and not rep["ok"]


def test_engine_module_does_not_import_opencv():
    code = "import sys; import oracolo.cad_norm; assert 'cv2' not in sys.modules, 'cv2 importato'"
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                       env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"})
    assert r.returncode == 0, r.stderr
