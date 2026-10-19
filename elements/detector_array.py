from dataclasses import dataclass, field

import numpy as np

from .base import Element
from .detector import Detector


@dataclass
class DetectorArray(Element):
    """A box tiled with nx by ny independent detectors. Cell (i, j) counts column i from the
    left and row j from the bottom and has id f"{id}_{i}_{j}"."""

    nx: int = 4
    ny: int = 4
    id: str = "array"
    _cells: list = field(default=None, init=False, repr=False, compare=False)
    _cells_key: tuple = field(default=None, init=False, repr=False, compare=False)

    @property
    def cells(self):
        key = (self.x0, self.y0, self.x1, self.y1, self.nx, self.ny, self.id)
        if key != self._cells_key:
            xs = np.linspace(self.xmin, self.xmax, self.nx + 1)
            ys = np.linspace(self.ymin, self.ymax, self.ny + 1)
            self._cells = [Detector(xs[i], ys[j], xs[i + 1], ys[j + 1], id=f"{self.id}_{i}_{j}")
                           for j in range(self.ny) for i in range(self.nx)]
            self._cells_key = key
        return self._cells
