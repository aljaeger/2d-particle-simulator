from dataclasses import dataclass, field

import numpy as np

from elements import Detector, DetectorArray, Element


def detectors_of(element):
    if isinstance(element, DetectorArray):
        return element.cells
    return [element] if isinstance(element, Detector) else []


@dataclass
class ParticleSource:
    x: float = 0.0
    y: float = 0.0
    px: float = 1.0
    py: float = 0.0
    sigma_px: float = 0.0
    sigma_py: float = 0.0
    charge: float = 1.0
    mass: float = 1.0

    def sample(self, rng, n=1):
        """Sample n particles. Returns positions and momenta of shape (n, 2)."""
        pos = np.tile([self.x, self.y], (n, 1)).astype(float)
        mom = np.column_stack([
            rng.normal(self.px, self.sigma_px, n),
            rng.normal(self.py, self.sigma_py, n),
        ])
        return pos, mom


@dataclass
class DetectionEvent:
    time: float
    detector_id: str
    duration: float
    particle: int


@dataclass
class SimulationResult:
    """times (n,), positions and momenta (n, N, 2), alive (n, N) for N particles over n steps."""

    times: np.ndarray
    positions: np.ndarray
    momenta: np.ndarray
    alive: np.ndarray
    events: list = field(default_factory=list)


class ParticleSimulator2D:
    def __init__(self, source=None, seed=None):
        self.source = source if source is not None else ParticleSource()
        self.elements = []
        self.rng = np.random.default_rng(seed)

    def add_element(self, element: Element):
        existing = {d.id for d in self.detectors}
        for det in detectors_of(element):
            if det.id in existing:
                raise ValueError(f"duplicate detector id {det.id!r}")
        self.elements.append(element)

    @property
    def detectors(self):
        """Every detector, with array cells expanded."""
        return [d for e in self.elements for d in detectors_of(e)]

    def acceleration(self, pos, mom):
        q, m = self.source.charge, self.source.mass
        accel = np.zeros_like(pos)
        for element in self.elements:
            accel += element.interact(pos, mom, q, m)[0]
        return accel

    def step(self, pos, mom, dt, prev_pos=None, alive=None):
        """Advance all particles one time step.

        Returns (alive, pos, mom, {detector_id: detected (N,) bool}). Detection covers the
        segment prev_pos -> pos so thin detectors are not skipped; dead particles stay put
        and are not detected. Each detector's counts is set to its number of detections."""
        pos, mom = np.asarray(pos, dtype=float), np.asarray(mom, dtype=float)
        if alive is None:
            alive = np.ones(len(pos), dtype=bool)
        q, m = self.source.charge, self.source.mass
        killed = np.zeros(len(pos), dtype=bool)
        for element in self.elements:
            killed |= element.interact(pos, mom, q, m, prev_pos)[1]
        detected = {det.id: det.interact(pos, mom, q, m, prev_pos)[2] for det in self.detectors}
        alive = alive & ~killed
        detections = {}
        for element in self.detectors:
            detections[element.id] = detected[element.id] & alive
            element.counts = int(detections[element.id].sum())

        def deriv(x, p):
            return p / m, m * self.acceleration(x, p)

        k1x, k1p = deriv(pos, mom)
        k2x, k2p = deriv(pos + 0.5 * dt * k1x, mom + 0.5 * dt * k1p)
        k3x, k3p = deriv(pos + 0.5 * dt * k2x, mom + 0.5 * dt * k2p)
        k4x, k4p = deriv(pos + dt * k3x, mom + dt * k3p)
        new_pos = pos + dt / 6 * (k1x + 2 * k2x + 2 * k3x + k4x)
        new_mom = mom + dt / 6 * (k1p + 2 * k2p + 2 * k3p + k4p)
        moving = alive[:, None]
        return alive, np.where(moving, new_pos, pos), np.where(moving, new_mom, mom), detections

    def simulate(self, T=10.0, n_steps=1000, N=10, initial=None):
        dt = T / n_steps
        pos, mom = initial if initial is not None else self.source.sample(self.rng, N)
        pos, mom = np.array(pos, dtype=float), np.array(mom, dtype=float)
        alive = np.ones(len(pos), dtype=bool)

        times, positions, momenta, alives, events = [], [], [], [], []
        active = {}
        prev_pos = None
        for i in range(n_steps + 1):
            t = i * dt
            times.append(t)
            positions.append(pos)
            momenta.append(mom)
            alive, new_pos, new_mom, detections = self.step(pos, mom, dt, prev_pos, alive)
            alives.append(alive)
            prev_pos, pos, mom = pos, new_pos, new_mom
            for det_id, detected in detections.items():
                for p in range(len(detected)):
                    key = (p, det_id)
                    if detected[p] and key not in active:
                        active[key] = t
                    elif not detected[p] and key in active:
                        start = active.pop(key)
                        events.append(DetectionEvent(start, det_id, t - start, p))
            if not alive.any():
                break
        for (p, det_id), start in active.items():
            events.append(DetectionEvent(start, det_id, t - start, p))
        return SimulationResult(np.array(times), np.array(positions), np.array(momenta), np.array(alives), events)

    def savefig(self, filename, result=None):
        import visualization
        return visualization.savefig(self, filename, result)

    def animate(self, result, filename, **kwargs):
        import visualization
        return visualization.animate(self, result, filename, **kwargs)
