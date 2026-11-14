"""Contratto degli eventi tra visione e motore.

La visione (camera, tracking) produce ``FrameEvent``; il motore non sa nulla di
OpenCV. In questo modo il motore si prova con il simulatore o con clip registrate
prima che la scena fisica sia pronta.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Observation:
    id: int
    x: float  # metri nel sistema della planimetria
    y: float
    conf: float = 1.0
    kind: str = "pedestrian"  # pedestrian | vehicle
    source: str = "cam0"


@dataclass
class FrameEvent:
    t: float  # secondi, monotono
    observations: list = field(default_factory=list)
    sensor_health: float = 1.0  # 0..1 (nitidezza, luminosità, ecc.)
    frame_age: float = 0.0  # secondi tra acquisizione del frame e ora

    def to_dict(self) -> dict:
        d = asdict(self)
        return d
