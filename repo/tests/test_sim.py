import numpy as np

from oracolo.bench import cases
from oracolo.sim import run_scenario, t_junction_scenario
from oracolo.warehouse import warehouse_scenario


def test_no_system_collides_at_the_blind_junction():
    assert run_scenario(t_junction_scenario(ped_t0=-1.0), "none").collision


def test_oracolo_avoids_the_collision_the_reactive_system_cannot():
    r = run_scenario(t_junction_scenario(ped_t0=-1.0), "oracolo")
    assert not r.collision and r.arrived


def test_t_junction_batch_oracolo_zero_collisions():
    rng = np.random.default_rng(1)
    cs = [(float(rng.uniform(-2.5, 1.5)), float(rng.uniform(1.2, 1.8))) for _ in range(16)]
    res = {m: [run_scenario(t_junction_scenario(t0, sp), m) for t0, sp in cs] for m in ("none", "reactive", "oracolo")}
    assert sum(r.collision for r in res["oracolo"]) == 0
    assert sum(r.collision for r in res["none"]) >= 1
    assert sum(r.collision for r in res["reactive"]) >= sum(r.collision for r in res["oracolo"])


def test_onboard_camera_makes_oracolo_faster_without_collisions():
    a = run_scenario(t_junction_scenario(ped_t0=-1.0, onboard=False), "oracolo")
    b = run_scenario(t_junction_scenario(ped_t0=-1.0, onboard=True), "oracolo")
    assert not b.collision and b.t_end < a.t_end - 1.0


def test_oracolo_is_failsafe_under_lossy_link():
    r = run_scenario(t_junction_scenario(ped_t0=-1.0), "oracolo",
                     bus_kwargs=dict(delay=0.05, jitter=0.03, drop=0.15, seed=7))
    assert not r.collision


def test_warehouse_oracolo_zero_collisions_on_random_cases():
    for pd, sp in cases(10, seed=3):
        assert not run_scenario(warehouse_scenario(ped_dt=pd, ped_speed=sp), "oracolo").collision
