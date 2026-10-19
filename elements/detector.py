from dataclasses import dataclass, field

import numpy as np

from .base import Element


@dataclass
class Detector(Element):
    id: str = "detector"
    counts: int = field(default=0, init=False)

    def interact(self, pos, mom, charge, mass, prev_pos=None):
        pos = np.asarray(pos, dtype=float)
        detected = self.contains(pos) if prev_pos is None else self.crosses(prev_pos, pos)
        return np.zeros_like(pos), np.zeros_like(detected), detected
