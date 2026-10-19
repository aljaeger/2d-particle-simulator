from dataclasses import dataclass

import numpy as np

from .base import Element


@dataclass
class MagneticField(Element):
    bz: float = 1.0

    def interact(self, pos, mom, charge, mass, prev_pos=None):
        pos, mom = np.asarray(pos, dtype=float), np.asarray(mom, dtype=float)
        inside = self.contains(pos)
        v = mom / mass
        accel = charge / mass * self.bz * np.stack([v[..., 1], -v[..., 0]], axis=-1) * inside[..., None]
        return accel, np.zeros_like(inside), np.zeros_like(inside)
