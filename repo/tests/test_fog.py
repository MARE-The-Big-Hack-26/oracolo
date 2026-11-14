import numpy as np
from shapely.geometry import box

from oracolo.fog import PERSONA_NASCOSTA, SCONOSCIUTO, VISIBILE, Fog
from oracolo.geometry import Occluder, Scene, visibility_polygon


def make():
    sc = Scene(box(0, 0, 20, 6), [Occluder("muro", box(8, 0, 9, 4), 3.0)])
    fog = Fog(sc, res=0.25, ped_speed=1.5, ghost_ttl=5.0)
    vis = fog.mask_from_poly(visibility_polygon((2, 2), sc, eye_h=2.0))
    return sc, fog, vis


def cell(fog, x, y):
    return int((y - fog.miny) / fog.res), int((x - fog.minx) / fog.res)


def test_initial_hidden_is_unknown_and_visible_is_visible():
    sc, fog, vis = make()
    fog.observe(0.0, vis, {})
    st = fog.state_map(0.0)
    assert st[cell(fog, 4, 2)] == VISIBILE
    assert st[cell(fog, 12, 1)] == SCONOSCIUTO  # dietro il muro, mai visto


def test_lost_pedestrian_creates_ghost_that_spreads_then_reconciles():
    sc, fog, vis = make()
    fog.observe(0.0, vis, {7: (7.8, 2.0)})  # visibile, vicino al muro
    # sparisce dietro il muro
    fog.observe(0.05, vis, {})
    assert 7 in fog.ghosts or fog.state_map(0.05)[cell(fog, 7.8, 2.0)] == VISIBILE
    # forzo la scomparsa in zona nascosta: persona vista a (9.5, 1) (nascosta?) -> uso posizione realmente nascosta
    sc2, fog2, vis2 = make()
    fog2.prev_seen = {5: (10.0, 1.0)}  # ultima posizione nota, ora nascosta
    fog2.t_prev = 0.0
    fog2.observe(0.05, vis2, {})
    assert 5 in fog2.ghosts
    r0 = fog2.ghosts[5]["grid"].sum()
    for k in range(2, 40):
        fog2.observe(0.05 * k, vis2, {})
    assert fog2.ghosts[5]["grid"].sum() > r0  # il fronte avanza
    st = fog2.state_map(2.0)
    assert (st == PERSONA_NASCOSTA).any()
    # riappare: riconciliato
    fog2.observe(2.1, vis2, {5: (4.0, 2.0)})
    assert 5 not in fog2.ghosts
    assert any(e[1] == "riconciliato" for e in fog2.events)


def test_ghost_expires_into_unreconciled():
    sc, fog, vis = make()
    fog.prev_seen = {9: (10.0, 1.0)}
    fog.t_prev = 0.0
    fog.observe(0.05, vis, {})
    assert 9 in fog.ghosts
    fog.observe(6.0, vis, {})
    assert 9 not in fog.ghosts
    assert any(e[1] == "non_riconciliato" for e in fog.events)


def test_cleared_region_gets_recontaminated_from_unknown():
    sc, fog, vis = make()
    fog.observe(0.0, vis, {})
    # un sensore a bordo ripulisce una zona dietro il muro
    vis_b = fog.mask_from_poly(visibility_polygon((12, 2), sc, eye_h=2.0))
    fog.observe(0.05, vis | vis_b, {})
    c = cell(fog, 12, 2)
    assert fog.state_map(0.05)[c] == VISIBILE
    # il sensore a bordo si allontana: la zona torna nascosta ma resta libera per un po'
    for k in range(2, 6):
        fog.observe(0.05 * k, vis, {})
    c_far = cell(fog, 14, 2)
    st_early = fog.state_map(0.3)[c_far]
    # il fronte dallo sconosciuto la raggiunge col tempo
    for k in range(6, 200):
        fog.observe(0.05 * k, vis, {})
    st_late = fog.state_map(10.0)[c_far]
    assert st_late == SCONOSCIUTO
    assert st_early in (2, SCONOSCIUTO, VISIBILE)
