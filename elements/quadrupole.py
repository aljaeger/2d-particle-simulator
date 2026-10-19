from dataclasses import dataclass

import numpy as np

from .base import Element


@dataclass
class Quadrupole(Element):
    """Magnetic field Bz varying linearly across the beam: zero on the centre line along
    (dir_x, dir_y), +strength at the edge to the left of the beam and -strength to the right.
    Positive strength focuses positive charges travelling along the direction vector."""

    strength: float = 1.0
    dir_x: float = 1.0
    dir_y: float = 0.0

    def bz(self, pos):
        pos = np.asarray(pos, dtype=float)
        d = np.array([self.dir_x, self.dir_y]) / np.hypot(self.dir_x, self.dir_y)
        normal = np.array([-d[1], d[0]])
        centre = np.array([(self.xmin + self.xmax) / 2, (self.ymin + self.ymax) / 2])
        edge = abs(normal[0]) * (self.xmax - self.xmin) / 2 + abs(normal[1]) * (self.ymax - self.ymin) / 2
        return self.strength * ((pos - centre) @ normal) / edge

    def interact(self, pos, mom, charge, mass, prev_pos=None):
        pos, mom = np.asarray(pos, dtype=float), np.asarray(mom, dtype=float)
        inside = self.contains(pos)
        v = mom / mass
        bz = self.bz(pos) * inside
        accel = charge / mass * np.stack([v[..., 1] * bz, -v[..., 0] * bz], axis=-1)
        return accel, np.zeros_like(inside), np.zeros_like(inside)
