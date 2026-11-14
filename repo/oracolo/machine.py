"""Comando verso la macchina e macchina virtuale (fail-safe).

Principio: la macchina marcia SOLO finché riceve comandi validi e freschi
(permissivo con TTL, come un watchdog). Un messaggio di "stop" perso non è un
problema: se i comandi smettono di arrivare, scade il TTL e la macchina va allo
stato sicuro da sola. In un impianto reale lo stop vero passa comunque da una
catena di sicurezza cablata e certificata (relè di sicurezza / PLC di sicurezza):
qui si simula solo il livello di comando.

Tre fedeltà di simulazione (docs/02-comando-macchina-costi.md):
  F0  InProcessBus + VirtualMachine nello stesso processo (con ritardo, jitter, perdita)
  F1  UdpSender / UdpReceiver: macchina in un altro processo, messaggi JSON
  F2  adattatori OPC UA / Modbus TCP (da aggiungere, stessa interfaccia)
"""
from __future__ import annotations

import json
import random
import socket
from dataclasses import asdict, dataclass

import numpy as np
from shapely.geometry import LineString

from .policy import VehicleParams


@dataclass
class MachineCommand:
    seq: int
    t_sent: float
    speed_limit: float  # m/s; 0 = fermo
    level: int  # 0..3
    cause: str = "nessuno"
    ttl: float = 0.25  # s di validità dal momento della ricezione

    @property
    def action(self) -> str:
        return ["RUN", "SLOW", "SLOW", "STOP"][self.level]

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(s: str) -> "MachineCommand":
        return MachineCommand(**json.loads(s))


class InProcessBus:
    """Canale simulato con ritardo, jitter e perdita di messaggi."""

    def __init__(self, delay=0.0, jitter=0.0, drop=0.0, seed=0):
        self.delay, self.jitter, self.drop = delay, jitter, drop
        self.rng = random.Random(seed)
        self.q: list = []
        self.sent = 0
        self.lost = 0

    def send(self, cmd: MachineCommand, t_now: float) -> None:
        self.sent += 1
        if self.rng.random() < self.drop:
            self.lost += 1
            return
        arrive = t_now + self.delay + self.rng.random() * self.jitter
        self.q.append((arrive, cmd))

    def poll(self, t_now: float) -> list:
        ready = sorted([x for x in self.q if x[0] <= t_now], key=lambda x: x[0])
        self.q = [x for x in self.q if x[0] > t_now]
        return [c for _, c in ready]


class UdpSender:
    def __init__(self, host="127.0.0.1", port=9500):
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, cmd: MachineCommand, t_now: float = 0.0) -> None:
        self.sock.sendto(cmd.to_json().encode(), self.addr)


class UdpReceiver:
    def __init__(self, host="127.0.0.1", port=9500):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.setblocking(False)

    def poll(self, t_now: float = 0.0) -> list:
        out = []
        while True:
            try:
                data, _ = self.sock.recvfrom(4096)
            except BlockingIOError:
                return out
            out.append(MachineCommand.from_json(data.decode()))


class VirtualMachine:
    """Macchina che segue un percorso e obbedisce ai comandi con TTL e ritardo di attuazione."""

    def __init__(self, path: LineString, params: VehicleParams, cruise: float | None = None, a_acc=0.8):
        self.path = path
        self.p = params
        self.cruise = params.v_max if cruise is None else cruise
        self.a_acc = a_acc
        self.s = 0.0
        self.v = 0.0
        self.cmd: MachineCommand | None = None
        self.rx_t = -np.inf
        self._pending: list = []  # (t_effettivo, cmd)
        self.watchdog_trips = 0
        self._tripped = False

    def receive(self, cmd: MachineCommand, t_now: float) -> None:
        self._pending.append((t_now + self.p.t_act, t_now, cmd))

    def _effective_limit(self, t: float) -> float:
        # applica i comandi la cui attuazione è maturata
        due = [x for x in self._pending if x[0] <= t]
        if due:
            self._pending = [x for x in self._pending if x[0] > t]
            for _, rx, cmd in sorted(due, key=lambda x: x[2].seq):
                if self.cmd is None or cmd.seq > self.cmd.seq:
                    self.cmd, self.rx_t = cmd, rx
        if self.cmd is None:
            return 0.0
        valid = (t - self.rx_t) <= self.cmd.ttl + self.p.t_act
        if not valid:
            if not self._tripped:
                self.watchdog_trips += 1
                self._tripped = True
            return 0.0
        self._tripped = False
        return self.cmd.speed_limit

    def step(self, t: float, dt: float) -> None:
        target = min(self.cruise, self._effective_limit(t))
        if self.v > target:
            self.v = max(target, self.v - self.p.a_brake * dt)
        else:
            self.v = min(target, self.v + self.a_acc * dt)
        self.s = min(self.path.length, self.s + self.v * dt)

    def pos(self) -> tuple:
        pt = self.path.interpolate(self.s)
        return (pt.x, pt.y)

    def heading(self) -> float:
        a = self.path.interpolate(max(0.0, self.s - 0.05))
        b = self.path.interpolate(min(self.path.length, self.s + 0.05))
        return float(np.arctan2(b.y - a.y, b.x - a.x))

    def arrived(self) -> bool:
        return self.s >= self.path.length - 1e-6
