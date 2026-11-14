import numpy as np

from oracolo.policy import (
    PedParams,
    VehicleParams,
    compute_decision,
    level_from_limit,
    stopping_distance,
    stopping_time,
    v_from_sight_distance,
    v_limit_at_distance,
    v_safe_from_ttr,
)

P = VehicleParams()


def test_stopping_distance_and_time():
    assert abs(stopping_distance(2.0, P) - (2.0 * 0.4 + 4.0 / 3.0)) < 1e-9
    assert abs(stopping_time(1.5, P) - (0.4 + 1.0)) < 1e-9


def test_v_safe_zero_when_ttr_shorter_than_latency():
    assert v_safe_from_ttr(0.3, P) == 0.0
    assert v_safe_from_ttr(1.4, P) == P.a_brake * (1.4 - P.T)


def test_v_safe_matches_bruteforce_braking():
    """Una minaccia emerge a distanza w dal punto P, lo raggiunge in ttr = w/vp.
    Con v <= v_safe la macchina, anche nel caso peggiore, si ferma entro ttr."""
    a, T = P.a_brake, P.T
    for ttr in (0.8, 1.2, 2.0, 3.5):
        v = float(v_safe_from_ttr(ttr, P))
        # tempo di arresto massimo = T + v/a
        assert T + v / a <= ttr + 1e-9
        # leggermente sopra: tempo di arresto oltre ttr
        v_hi = v * 1.05 + 1e-3
        assert T + v_hi / a > ttr


def test_braking_curve_reaches_v_safe_at_point():
    a, T = P.a_brake, P.T
    for s in (1.0, 3.0, 6.0, 10.0):
        for vs in (0.0, 0.5, 1.2):
            v = float(v_limit_at_distance(s, vs, P))
            # simulo: viaggio v per T, poi freno
            d_react = v * T
            d_brake_avail = (s - P.margin) - d_react
            v_at_point_sq = max(0.0, v * v - 2 * a * max(d_brake_avail, 0.0))
            assert v_at_point_sq ** 0.5 <= vs + 1e-6


def test_sight_distance_formula():
    for d in (1.0, 2.5, 6.0):
        v = v_from_sight_distance(d, P)
        assert stopping_distance(v, P) <= (d - P.margin) + 1e-9


def test_levels_monotonic():
    lv = [level_from_limit(x, 2.2) for x in (2.2, 1.9, 1.0, 0.2, 0.0)]
    assert lv == [0, 1, 2, 2, 3]


def test_no_threats_gives_normal():
    s = np.arange(0, 12.1, 0.25)
    pts = np.column_stack([s, np.zeros_like(s)])
    d = compute_decision(s, pts, [], None, None, P, PedParams())
    assert d.level == 0 and d.limit == P.v_max and d.cause == "nessuno"


def test_hidden_zone_near_path_slows_down_before_arrival():
    s = np.arange(0, 12.1, 0.25)
    pts = np.column_stack([s, np.zeros_like(s)])
    d_unk = np.full_like(s, 50.0)
    d_unk[s > 2] = 2.0  # zona sconosciuta a 2 m dal percorso oltre s=2
    d = compute_decision(s, pts, [], None, d_unk, P, PedParams())
    assert d.limit < P.v_max
    assert d.cause == "zona_non_osservata"
    assert d.binding_s is not None and d.binding_s >= 2
    # la stessa zona 8 m più avanti non obbliga ancora a rallentare: c'è spazio per frenare
    d_far = np.full_like(s, 50.0)
    d_far[s > 8] = 2.0
    assert compute_decision(s, pts, [], None, d_far, P, PedParams()).limit == P.v_max


def test_observed_pedestrian_on_path_stops():
    s = np.arange(0, 12.1, 0.25)
    pts = np.column_stack([s, np.zeros_like(s)])
    # pedone a 1,2 m davanti: non c'è margine, ferma
    d = compute_decision(s, pts, [((1.2, 0.2), 0.0)], None, None, P, PedParams())
    assert d.level == 3 and d.limit == 0.0 and d.cause == "osservato"
    # pedone a 3 m: rallenta (si può ancora fermare in tempo), non ferma del tutto
    d3 = compute_decision(s, pts, [((3.0, 0.2), 0.0)], None, None, P, PedParams())
    assert 0.0 < d3.limit < P.v_max and d3.cause == "osservato"


def test_stale_frame_or_low_health_fails_safe():
    s = np.arange(0, 12.1, 0.25)
    pts = np.column_stack([s, np.zeros_like(s)])
    d1 = compute_decision(s, pts, [], None, None, P, PedParams(), frame_age=0.6)
    assert d1.limit == 0.0 and d1.cause == "affidabilita_persa"
    d2 = compute_decision(s, pts, [], None, None, P, PedParams(), health=0.1)
    assert d2.limit == 0.0
    d3 = compute_decision(s, pts, [], None, None, P, PedParams(), health=0.5)
    assert 0.0 < d3.limit < P.v_max and d3.cause == "scena_degradata"
