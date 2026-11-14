import math

from oracolo.vision.tracker import PersonTracker, VehicleTracker


def test_id_stabile_e_velocita():
    tr = PersonTracker()
    ids = set()
    sp = 0.0
    for i in range(20):
        t = i * 0.1
        out = tr.update(t, [(1.0 + 1.0 * t, 2.0, 0.9)])
        ids |= {o.id for o in out}
        sp = out[0].speed
    assert ids == {1}
    assert abs(sp - 1.0) < 0.15


def test_due_persone_non_si_scambiano():
    tr = PersonTracker()
    for i in range(15):
        t = i * 0.1
        out = tr.update(t, [(1.0 + t, 1.0, 0.9), (4.0 - t, 1.3, 0.9)])
    a = next(o for o in out if o.xy[0] < 2.6 or o.id == 1)
    assert {o.id for o in out} == {1, 2}


def test_salto_grande_crea_nuova_identita():
    tr = PersonTracker()
    tr.update(0.0, [(1.0, 1.0, 0.9)])
    out = tr.update(0.1, [(4.0, 3.0, 0.9)])
    assert out[0].id == 2


def test_traccia_scade():
    tr = PersonTracker(max_miss=0.5)
    tr.update(0.0, [(1.0, 1.0, 0.9)])
    tr.update(0.3, [])
    assert tr.tracks
    tr.update(0.9, [])
    assert not tr.tracks


def test_muletto_velocita_e_direzione():
    vt = VehicleTracker()
    for i in range(20):
        t = i * 0.1
        vt.update(t, (1.0, 1.0 + 1.0 * t), marker_heading=0.0)  # marker dice 0 rad ma si muove a +y
    p = vt.pose(1.9)
    assert abs(p.speed - 1.0) < 0.15
    assert abs(p.heading - math.pi / 2) < 0.1 and p.tracked


def test_muletto_fermo_usa_il_marker_e_si_perde():
    vt = VehicleTracker(lost_after=1.0)
    for i in range(10):
        vt.update(i * 0.1, (2.0, 2.0), marker_heading=1.2)
    p = vt.pose(0.95)
    assert p.speed < 0.05 and abs(p.heading - 1.2) < 1e-6
    assert vt.pose(3.0).tracked is False
