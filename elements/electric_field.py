from dataclasses import dataclass

import numpy as np

from .base import Element


@dataclass
class ElectricField(Element):
    ex: float = 0.0
    ey: float = 0.0

    def interact(self, pos, mom, charge, mass, prev_pos=None):
        pos = np.asarray(pos, dtype=float)
        inside = self.contains(pos)
        accel = charge / mass * np.array([self.ex, self.ey]) * inside[..., None]
        return accel, np.zeros_like(inside), np.zeros_like(inside)
