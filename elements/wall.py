from dataclasses import dataclass

import numpy as np

from .base import Element


@dataclass
class Wall(Element):
    def interact(self, pos, mom, charge, mass, prev_pos=None):
        pos = np.asarray(pos, dtype=float)
        killed = self.contains(pos)
        return np.zeros_like(pos), killed, np.zeros_like(killed)
