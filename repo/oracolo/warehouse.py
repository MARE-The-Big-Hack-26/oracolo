"""Scenario "magazzino": planimetria CAD + UNA camera fissa + carrello + persone.

Workflow reale: si importa il CAD, si indica dove è montata la camera fissa; la camera
vede carrelli, persone e zone d'ombra; ogni carrello riceve il comando (limite di
velocità + livello) e rallenta o si ferma.

Ipotesi dichiarata: la posizione del carrello è nota al sistema (tracciata dalla camera
quando lo vede; altrimenti stimata dall'odometria del carrello).
"""
from __future__ import annotations

from pathlib import Path

from shapely.geometry import LineString

from .cad import load_dxf
from .policy import VehicleParams
from .sim import PedSpec, Scenario, SensorSpec

DEFAULT_DXF = Path(__file__).resolve().parent.parent / "scenarios" / "magazzino.dxf"
DEFAULT_CAMERAS = [(10.5, 9.75), (20.5, 9.75)]  # due camere fisse sopra gli incroci


def warehouse_scenario(
    dxf_path=None,
    cam_h=4.0,
    ped_dt=(-0.5, 3.5),
    ped_speed=1.4,
    params: VehicleParams | None = None,
    cameras=None,
) -> Scenario:
    scene, info = load_dxf(dxf_path or DEFAULT_DXF)
    path = LineString([(1.5, 9.75), (28.5, 9.75)])
    peds = [
        PedSpec(1, [(10.5, 18.0), (10.5, 2.0)], t0=ped_dt[0], speed=ped_speed),  # esce dalla corsia a x=10,5
        PedSpec(2, [(20.5, 2.0), (20.5, 18.0)], t0=ped_dt[1], speed=ped_speed),  # esce dalla corsia a x=20,5
    ]
    cams = cameras or DEFAULT_CAMERAS
    sensors = [SensorSpec("fixed", tuple(c), eye_h=cam_h) for c in cams]
    # baseline "zona fissa": limitazione a 5 km/h attorno ai due incroci (s = x - 1,5)
    return Scenario(scene, path, peds, sensors, params=params or VehicleParams(), t_max=60.0,
                    zones=[(5.5, 11.0), (15.5, 21.0)])


def coverage(scene, cams, cam_h=4.0, res=0.25) -> float:
    """Quota di area percorribile vista da almeno una camera (0..1). Aiuta a scegliere dove montarle."""
    import numpy as np

    from .fog import Fog
    from .geometry import visibility_polygon

    fog = Fog(scene, res=res)
    m = np.zeros_like(fog.walk)
    for c in cams:
        m |= fog.mask_from_poly(visibility_polygon(c, scene, eye_h=cam_h, target_h=1.0))
    return float((m & fog.walk).sum() / fog.walk.sum())
