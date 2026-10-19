from dataclasses import dataclass

import numpy as np


@dataclass
class Element:
    """Rectangular element defined by two opposing corners, given in any order.

    Positions and momenta are arrays of shape (..., 2) so any number of particles can be
    evaluated at once; results have the leading shape (...)."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def xmin(self):
        return min(self.x0, self.x1)

    @property
    def xmax(self):
        return max(self.x0, self.x1)

    @property
    def ymin(self):
        return min(self.y0, self.y1)

    @property
    def ymax(self):
        return max(self.y0, self.y1)

    def contains(self, pos):
        pos = np.asarray(pos, dtype=float)
        x, y = pos[..., 0], pos[..., 1]
        return (self.xmin <= x) & (x <= self.xmax) & (self.ymin <= y) & (y <= self.ymax)

    def crosses(self, p0, p1):
        """True where the segment p0 -> p1 passes through the rectangle (slab clipping)."""
        p0, p1 = np.asarray(p0, dtype=float), np.asarray(p1, dtype=float)
        d = p1 - p0
        t0, t1 = np.zeros(p0.shape[:-1]), np.ones(p0.shape[:-1])
        for axis, (lo, hi) in enumerate(((self.xmin, self.xmax), (self.ymin, self.ymax))):
            parallel = d[..., axis] == 0
            inside = (lo <= p0[..., axis]) & (p0[..., axis] <= hi)
            with np.errstate(divide="ignore", invalid="ignore"):
                ta = (lo - p0[..., axis]) / d[..., axis]
                tb = (hi - p0[..., axis]) / d[..., axis]
            t0 = np.where(parallel, np.where(inside, t0, 1.0), np.maximum(t0, np.minimum(ta, tb)))
            t1 = np.where(parallel, np.where(inside, t1, 0.0), np.minimum(t1, np.maximum(ta, tb)))
        return t0 <= t1

    def interact(self, pos, mom, charge, mass, prev_pos=None):
        """Return (acceleration, killed, detected) for particles at pos with momentum mom.

        prev_pos is the position before the last step, when known."""
        pos = np.asarray(pos, dtype=float)
        none = np.zeros(pos.shape[:-1], dtype=bool)
        return np.zeros_like(pos), none, none
