import numpy as np
from shapely.geometry import LineString

from oracolo.machine import InProcessBus, MachineCommand, UdpReceiver, UdpSender, VirtualMachine
from oracolo.policy import VehicleParams, stopping_distance

P = VehicleParams()
PATH = LineString([(0, 0), (200, 0)])


class Driver:
    """Controllore simulato: tempo e numero di sequenza persistono tra le chiamate."""

    def __init__(self, machine, bus, dt=0.05, ttl=0.25):
        self.m, self.bus, self.dt, self.ttl = machine, bus, dt, ttl
        self.t, self.seq = 0.0, 0

    def run(self, seconds, limit_fn):
        end = self.t + seconds
        while self.t < end:
            lim = limit_fn(self.t)
            if lim is not None:  # None = il controllore smette di inviare
                self.seq += 1
                self.bus.send(MachineCommand(self.seq, self.t, lim, 0 if lim >= P.v_max else 2, ttl=self.ttl), self.t)
            for c in self.bus.poll(self.t):
                self.m.receive(c, self.t)
            self.m.step(self.t, self.dt)
            self.t += self.dt
        return self.t


def test_machine_obeys_speed_limit():
    m, bus = VirtualMachine(PATH, P), InProcessBus()
    Driver(m, bus).run(8.0, lambda t: 1.0)
    assert abs(m.v - 1.0) < 0.05


def test_watchdog_stops_machine_when_commands_stop_arriving():
    m, bus = VirtualMachine(PATH, P), InProcessBus()
    d = Driver(m, bus)
    d.run(5.0, lambda t: P.v_max)
    s_cut = m.s
    v_cut = m.v
    d.run(3.0, lambda t: None)  # link interrotto
    assert m.v == 0.0 and m.watchdog_trips == 1
    # si ferma entro la distanza di arresto (TTL incluso)
    assert (m.s - s_cut) <= stopping_distance(v_cut, P) + v_cut * 0.25 + 0.05


def test_total_message_loss_is_failsafe():
    m, bus = VirtualMachine(PATH, P), InProcessBus(drop=1.0)
    Driver(m, bus).run(3.0, lambda t: P.v_max)
    assert m.v == 0.0 and m.s == 0.0  # non parte mai senza comandi validi


def test_old_commands_do_not_override_new_ones():
    m = VirtualMachine(PATH, P)
    m.receive(MachineCommand(5, 0.0, 0.5, 2), 0.0)
    m.receive(MachineCommand(3, 0.0, 2.0, 0), 0.0)  # fuori ordine, più vecchio
    for k in range(40):
        m.receive(MachineCommand(6 + k, 0.0, 0.5, 2), k * 0.05)
        m.step(k * 0.05, 0.05)
    assert m.v <= 0.55


def test_jitter_and_delay_still_stop_in_time_after_stop_command():
    m, bus = VirtualMachine(PATH, P), InProcessBus(delay=0.08, jitter=0.05, drop=0.2, seed=3)
    d = Driver(m, bus)
    d.run(6.0, lambda t: P.v_max)
    s0, v0 = m.s, m.v
    d.run(4.0, lambda t: 0.0)
    assert m.v == 0.0
    # con ritardo e perdita la distanza di arresto cresce: resta comunque limitata
    assert m.s - s0 < stopping_distance(v0, P) + v0 * (0.08 + 0.05 + 0.25) + 0.5


def test_udp_roundtrip():
    rx = UdpReceiver(port=9611)
    tx = UdpSender(port=9611)
    tx.send(MachineCommand(1, 0.0, 1.2, 1, cause="test"))
    import time

    time.sleep(0.05)
    got = rx.poll()
    assert len(got) == 1 and got[0].speed_limit == 1.2 and got[0].cause == "test"
