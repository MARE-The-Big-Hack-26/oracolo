import numpy as np
from shapely.geometry import LineString, Point, box

from oracolo.geometry import (
    Agent,
    Occluder,
    Scene,
    classify_pair,
    line_of_sight,
    mutual_visibility,
    obstacle_shadow,
    scene_shadows,
    visibility_polygon,
    visible_distance_along,
)
from oracolo.scenes import t_junction


def room_with_wall():
    # stanza 10x10, muro alto 3 m tra x=4..5, y=0..6
    return Scene(box(0, 0, 10, 10), [Occluder("muro", box(4, 0, 5, 6), 3.0)])


def test_point_behind_wall_is_hidden():
    sc = room_with_wall()
    vis = visibility_polygon((2, 3), sc, eye_h=1.5, target_h=1.0)
    assert vis.covers(Point(3, 3))
    assert not vis.covers(Point(8, 3))  # dietro il muro
    assert vis.covers(Point(5.5, 9))  # oltre l'estremità del muro


def test_visibility_area_is_symmetric_with_point_los():
    sc = room_with_wall()
    a, b = (2, 3), (8, 3)
    assert not line_of_sight(a, 1.5, b, 1.0, sc)
    assert not line_of_sight(b, 1.0, a, 1.5, sc)


def test_low_occluder_does_not_block_tall_target():
    sc = Scene(box(0, 0, 10, 10), [Occluder("pallet", box(4, 0, 7, 10), 1.0)])
    # occhio a 1,5 m, bersaglio a 1,7 m: la retta sta sempre sopra 1,0 m
    assert line_of_sight((2, 5), 1.5, (8, 5), 1.7, sc)
    # bersaglio basso (0,3 m): la retta scende sotto 1,0 m dentro il pallet -> bloccato
    assert not line_of_sight((2, 5), 1.5, (8, 5), 0.3, sc)


def test_asymmetric_sight_driver_vs_pedestrian():
    # il conducente è seduto basso (occhio 1,0 m), il carico alto 1,6 m davanti a lui;
    # il pedone in piedi (occhio 1,6 m) vede sopra un pallet da 1,2 m? No: dipende dalle quote.
    sc = Scene(box(0, 0, 10, 10), [Occluder("carico", box(3, 4, 4, 6), 1.6)])
    driver = Agent("conducente", (2, 5), eye_h=1.2, target_h=1.2)
    ped = Agent("pedone", (8, 5), eye_h=1.7, target_h=1.7)
    m = mutual_visibility([driver, ped], sc)
    # la retta parte a 1,2 m e arriva a 1,7 m: sotto 1,6 per metà del tratto -> bloccata in entrambe le direzioni
    assert m[("conducente", "pedone")] == m[("pedone", "conducente")]
    # ora il pedone si china (target 0.9) e vede il conducente che è alto 1,2? asimmetria sul bersaglio
    ped_low = Agent("pedone", (8, 5), eye_h=1.7, target_h=1.7)
    drv_high = Agent("conducente", (2, 5), eye_h=2.0, target_h=0.8)
    m2 = mutual_visibility([drv_high, ped_low], sc)
    assert m2[("conducente", "pedone")] is True or m2[("conducente", "pedone")] is np.True_
    assert not m2[("pedone", "conducente")]  # io vedo te, tu non vedi me
    assert classify_pair(m2[("conducente", "pedone")], m2[("pedone", "conducente")]) == "solo_a_vede_b"


def test_fov_limits_visibility():
    sc = room_with_wall()
    vis = visibility_polygon((2, 8), sc, eye_h=1.5, heading=0.0, half_fov=np.deg2rad(30), max_range=6)
    assert vis.covers(Point(5, 8))
    assert not vis.covers(Point(2, 3))  # fuori dal cono


def test_visible_distance_along_path_stops_at_blind_zone():
    sc = t_junction()
    vis = visibility_polygon((1.0, 1.75), sc, eye_h=2.5, target_h=1.0)
    # un percorso che sale lungo la corsia trasversale esce subito dalla vista
    path = LineString([(11.0, 2.0), (11.0, 10.0)])
    d = visible_distance_along(path, vis)
    assert 1.0 < d < 3.0
    # il percorso principale è tutto visibile
    main = LineString([(1.0, 1.75), (19.0, 1.75)])
    assert visible_distance_along(main, vis) == main.length


def test_junction_has_hidden_crossing_aisle():
    sc = t_junction()
    vis = visibility_polygon((1.0, 1.75), sc, eye_h=2.5, target_h=1.0)
    assert vis.covers(Point(15, 1.75))
    assert not vis.covers(Point(11, 9))


def test_low_obstacle_shadow_changes_with_camera_height_and_position():
    desk = Occluder("scrivania", box(4.0, 2.0, 5.0, 4.0), 0.77)
    sc = Scene(box(0, 0, 10, 6), [desk])
    sh_high = obstacle_shadow((2.0, 3.0), desk, eye_h=1.8, target_h=0.0)
    sh_low = obstacle_shadow((2.0, 3.0), desk, eye_h=0.9, target_h=0.0)
    assert sh_high.area > 0 and sh_low.area > sh_high.area * 3
    vis_high = visibility_polygon((2.0, 3.0), sc, eye_h=1.8, target_h=0.0)
    vis_low = visibility_polygon((2.0, 3.0), sc, eye_h=0.9, target_h=0.0)
    assert not vis_high.covers(Point(5.5, 3.0)) and vis_high.covers(Point(8.5, 3.0))
    assert not vis_low.covers(Point(8.5, 3.0))
    # spostando la camera dall'altro lato della scrivania, la zona d'ombra ruota
    vis_other = visibility_polygon((7.0, 3.0), sc, eye_h=0.9, target_h=0.0)
    assert vis_other.covers(Point(8.5, 3.0)) and not vis_other.covers(Point(2.5, 3.0))
    assert len(scene_shadows((2.0, 3.0), sc, eye_h=1.8, target_h=0.0)) >= 1


def test_directional_iphone_camera_shadows_and_fov():
    front = Occluder("davanti", box(6.0, 2.5, 7.0, 3.5), 1.0)
    back = Occluder("dietro", box(1.0, 2.5, 2.0, 3.5), 1.0)
    sc = Scene(box(0, 0, 10, 6), [front, back])
    hf = np.deg2rad(37.5)
    sh_fwd = scene_shadows((4.0, 3.0), sc, eye_h=1.8, target_h=0.0, heading=0.0, half_fov=hf)
    sh_bwd = scene_shadows((4.0, 3.0), sc, eye_h=1.8, target_h=0.0, heading=np.pi, half_fov=hf)
    assert sh_fwd and sh_bwd and sh_fwd != sh_bwd
    assert all(min(x for x, _ in ring) >= 5.5 for ring in sh_fwd)
    assert all(max(x for x, _ in ring) <= 2.5 for ring in sh_bwd)
