"""Browser side of the simulator: owns the simulator and particle state like gui.app.App does,
but speaks plain dicts/JSON so it can be driven from JavaScript through Pyodide."""
import json
import os
import tempfile

import numpy as np

from elements import Detector, DetectorArray, ElectricField, MagneticField, Quadrupole
from gui.config import load_config, save_config
from gui.fields import ELEMENT_TYPES, initial_values, parse_values
from simulator import ParticleSimulator2D, ParticleSource, detectors_of

TYPES = {cls.__name__: cls for cls in ELEMENT_TYPES}
DEFAULT_DOMAIN = (0.0, 10.0, 0.0, 10.0)
GRID_N = 5


def _rect(el):
    return {"xmin": el.xmin, "xmax": el.xmax, "ymin": el.ymin, "ymax": el.ymax}


def _grid(el):
    xs = np.linspace(el.xmin, el.xmax, GRID_N + 2)[1:-1]
    ys = np.linspace(el.ymin, el.ymax, GRID_N + 2)[1:-1]
    X, Y = np.meshgrid(xs, ys)
    return np.stack([X.ravel(), Y.ravel()], axis=-1)


def element_spec(el, index):
    spec = {"type": type(el).__name__, "index": index, **_rect(el)}
    if isinstance(el, Detector):
        spec["id"] = el.id
    elif isinstance(el, DetectorArray):
        spec["cells"] = [{"id": c.id, **_rect(c)} for c in el.cells]
    elif isinstance(el, MagneticField):
        spec["grid"] = _grid(el).tolist()
        spec["sign"] = -1 if el.bz < 0 else 1
    elif isinstance(el, Quadrupole):
        points = _grid(el)
        b = el.bz(points) / abs(el.strength) if el.strength else np.zeros(len(points))
        spec["markers"] = np.column_stack([points, b]).tolist()
    elif isinstance(el, ElectricField):
        norm = np.hypot(el.ex, el.ey)
        if norm:
            length = 0.7 * min(el.xmax - el.xmin, el.ymax - el.ymin) / (GRID_N + 1)
            spec["grid"] = _grid(el).tolist()
            spec["dx"], spec["dy"] = length * el.ex / norm, length * el.ey / norm
    return spec


class Bridge:
    def __init__(self, sim=None):
        self.sim = sim or ParticleSimulator2D(ParticleSource(x=1.0, y=1.0, px=1.0, py=0.0))
        self.cumulative = {}
        self.resample(10)

    def element_types(self):
        return list(TYPES)

    # --- particle state (mirrors gui.app.App) -----------------------------
    def resample(self, N, keep_counts=False):
        self.initial = self.sim.source.sample(self.sim.rng, N)
        return self.reset(keep_counts)

    def reset(self, keep_counts=False):
        self.pos, self.mom = (np.array(v, dtype=float) for v in self.initial)
        self.prev_pos = None
        self.step_index = 0
        self.alive = np.ones(len(self.pos), dtype=bool)
        self.counts = {}
        self.detected = {}
        if not keep_counts:
            self.cumulative = {}
        return self.state()

    def state(self):
        return {"step": self.step_index, "pos": self.pos.tolist(), "alive": self.alive.tolist(),
                "counts": self.counts, "cumulative": self.cumulative, "scales": self._cumulative_scales()}

    def step(self, k, dt, n_steps):
        """Advance up to k steps; returns the new positions per step plus the current state."""
        frames = []
        while len(frames) < k and self.alive.any() and self.step_index < n_steps:
            alive, pos, mom, detections = self.sim.step(self.pos, self.mom, dt, self.prev_pos, self.alive)
            self.prev_pos, self.pos, self.mom, self.alive = self.pos, pos, mom, alive
            self.step_index += 1
            self.counts = {det_id: int(d.sum()) for det_id, d in detections.items()}
            for det_id, d in detections.items():
                new_hits = d & ~self.detected.get(det_id, np.zeros_like(d))
                self.cumulative[det_id] = self.cumulative.get(det_id, 0) + int(new_hits.sum())
            self.detected = detections
            frames.append(pos.tolist())
        done = not self.alive.any() or self.step_index >= n_steps
        return {"frames": frames, "done": done, **self.state()}

    def _cumulative_scales(self):
        """Arrays normalise within themselves; standalone detectors against each other."""
        def peak(dets):
            return max((self.cumulative.get(d.id, 0) for d in dets), default=0) or 1

        singles = [e for e in self.sim.elements if isinstance(e, Detector)]
        scales = {d.id: peak(singles) for d in singles}
        for e in self.sim.elements:
            if isinstance(e, DetectorArray):
                scales.update({cell.id: peak(e.cells) for cell in e.cells})
        return scales

    # --- scene description for the canvas --------------------------------
    def scene(self):
        xs = [self.sim.source.x] + [v for e in self.sim.elements for v in (e.xmin, e.xmax)]
        ys = [self.sim.source.y] + [v for e in self.sim.elements for v in (e.ymin, e.ymax)]
        xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
        pad = 0.05 * max(xmax - xmin, ymax - ymin, 1.0)
        return {
            "xlim": [min(xmin - pad, DEFAULT_DOMAIN[0]), max(xmax + pad, DEFAULT_DOMAIN[1])],
            "ylim": [min(ymin - pad, DEFAULT_DOMAIN[2]), max(ymax + pad, DEFAULT_DOMAIN[3])],
            "source": [self.sim.source.x, self.sim.source.y],
            "elements": [element_spec(el, i) for i, el in enumerate(self.sim.elements)],
        }

    # --- element editing ---------------------------------------------------
    def _next_id(self, prefix):
        taken = {d.id for d in self.sim.detectors} | {e.id for e in self.sim.elements if isinstance(e, DetectorArray)}
        n = 1
        while f"{prefix}_{n}" in taken:
            n += 1
        return f"{prefix}_{n}"

    def new_element_values(self, type_name, corners):
        cls = TYPES[type_name]
        overrides = dict(zip(("x0", "y0", "x1", "y1"), corners))
        if cls is Detector:
            overrides["id"] = self._next_id("detector")
        elif cls is DetectorArray:
            overrides["id"] = self._next_id("array")
        return initial_values(cls, overrides)

    def element_values(self, index):
        return initial_values(self.sim.elements[index])

    def source_values(self):
        return initial_values(self.sim.source)

    def add_element(self, type_name, strings):
        """Returns an error message, or None on success."""
        cls = TYPES[type_name]
        try:
            self.sim.add_element(cls(**parse_values(cls, strings)))
        except ValueError as exc:
            return str(exc)

    def update_element(self, index, strings):
        el = self.sim.elements[index]
        try:
            values = parse_values(type(el), strings)
        except ValueError as exc:
            return str(exc)
        others = {d.id for e in self.sim.elements if e is not el for d in detectors_of(e)}
        if isinstance(el, Detector) and values["id"] in others:
            return f"duplicate detector id {values['id']!r}"
        if isinstance(el, DetectorArray) and any(i.startswith(values["id"] + "_") for i in others):
            return f"detector id prefix {values['id']!r} already in use"
        for name, value in values.items():
            setattr(el, name, value)

    def delete_element(self, index):
        del self.sim.elements[index]

    def set_source(self, strings):
        try:
            self.sim.source = ParticleSource(**parse_values(ParticleSource, strings))
        except ValueError as exc:
            return str(exc)

    # --- configuration files (reuses gui.config through a temporary file) --
    def load_config(self, text):
        """Replace source and elements from JSON text; returns the saved control settings."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write(text)
        try:
            source, elements, settings = load_config(f.name)
        finally:
            os.remove(f.name)
        self.sim.source = source
        self.sim.elements = []
        for element in elements:
            self.sim.add_element(element)
        return settings

    def save_config(self, settings):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            pass
        try:
            save_config(self.sim, settings, f.name)
            with open(f.name) as g:
                return g.read()
        finally:
            os.remove(f.name)


bridge = Bridge()


def call(name, args_json="[]"):
    """Single entry point for the worker: JSON argument list in, JSON result out."""
    result = getattr(bridge, name)(*json.loads(args_json))
    return json.dumps(result, default=float)
