from oracolo.warehouse import DEFAULT_CAMERAS, coverage, warehouse_scenario
from oracolo.sim import run_scenario


def test_warehouse_loaded_from_cad():
    sc = warehouse_scenario()
    assert sc.scene.bounds.bounds == (0.0, 0.0, 30.0, 20.0)
    assert len(sc.scene.occluders) == 7


def test_more_cameras_more_coverage():
    sc = warehouse_scenario()
    c1 = coverage(sc.scene, [(1.0, 9.75)])
    c2 = coverage(sc.scene, DEFAULT_CAMERAS)
    assert 0.0 < c1 < c2 < 1.0


def test_no_system_collides_but_oracolo_does_not():
    assert run_scenario(warehouse_scenario(), "none").collision
    r = run_scenario(warehouse_scenario(), "oracolo")
    assert not r.collision and r.arrived


def test_single_camera_is_safe_but_slow():
    one = run_scenario(warehouse_scenario(cameras=[(1.0, 9.75)]), "oracolo")
    two = run_scenario(warehouse_scenario(), "oracolo")
    assert not one.collision
    assert one.t_end > two.t_end + 5  # meno copertura -> molto più lento
