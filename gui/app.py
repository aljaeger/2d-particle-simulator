import queue
import threading
import tkinter as tk
from tkinter import messagebox

import matplotlib

matplotlib.use("TkAgg")

import numpy as np

from elements import Detector, DetectorArray
from gui.config import CONFIG_FILE, load_config, save_config
from gui.controls import Controls
from gui.element_dialog import edit_values
from gui.fields import initial_values
from gui.plot_window import PlotWindow
from simulator import ParticleSimulator2D, ParticleSource, detectors_of

POLL_MS = 33


class App:
    def __init__(self, sim, settings=None):
        self.sim = sim
        self.root = tk.Tk()
        self.controls = Controls(self.root, self)
        self.controls.apply_settings(settings or {})
        self.plot = PlotWindow(self.root, sim, self.edit_element)
        self.queue = queue.Queue(maxsize=1000)
        self.stop = threading.Event()
        self.worker = None
        self.resample()
        self.root.after(POLL_MS, self._poll)

    def run(self):
        self.root.mainloop()

    # --- particle state -------------------------------------------------
    def resample(self, keep_counts=False):
        self.initial = self.sim.source.sample(self.sim.rng, self.controls.n_particles())
        self.reset(keep_counts)

    def reset(self, keep_counts=False):
        self.pause()
        self.pos, self.mom = (np.array(v, dtype=float) for v in self.initial)
        self.step_index = 0
        self.alive = np.ones(len(self.pos), dtype=bool)
        self.track = [self.pos.copy()]
        self.counts = {}
        self.detected = {}
        if not keep_counts:
            self.cumulative = {}
        self._show()

    def _apply(self, alive, pos, mom, step_index, detections):
        self.alive, self.pos, self.mom, self.step_index = alive, pos, mom, step_index
        self.track.append(pos.copy())
        self.counts = {det_id: int(d.sum()) for det_id, d in detections.items()}
        for det_id, d in detections.items():
            new_hits = d & ~self.detected.get(det_id, np.zeros_like(d))
            self.cumulative[det_id] = self.cumulative.get(det_id, 0) + int(new_hits.sum())
        self.detected = detections

    def _show(self):
        visible = self.controls.particles_visible()
        if self.controls.cumulative_enabled():
            self.plot.update_particles(np.array(self.track), self.alive, self.cumulative,
                                       self._cumulative_scales(), visible)
        else:
            self.plot.update_particles(np.array(self.track), self.alive, self.counts, visible=visible)
        self.controls.set_status(
            f"step {self.step_index}  t={self.step_index * self._dt():.3f}  "
            f"alive {int(self.alive.sum())}/{len(self.alive)}")

    def _prev_pos(self):
        return self.track[-2] if len(self.track) > 1 else None

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

    def refresh(self):
        if hasattr(self, "track"):
            self._show()

    def _dt(self):
        T, n_steps, _ = self.controls.values()
        return T / n_steps

    def step(self):
        self.pause()
        _, n_steps, _ = self.controls.values()
        if not self.alive.any() or self.step_index >= n_steps:
            return
        alive, pos, mom, detections = self.sim.step(self.pos, self.mom, self._dt(), self._prev_pos(), self.alive)
        self._apply(alive, pos, mom, self.step_index + 1, detections)
        self._show()

    # --- play / pause (worker thread computes, main thread draws) -------
    def toggle_play(self):
        if self.worker is not None:
            self.pause()
        else:
            self.play()

    def play(self):
        if not self.alive.any():
            return
        self.stop.clear()
        T, n_steps, _ = self.controls.values()
        args = (self._prev_pos(), self.pos.copy(), self.mom.copy(), self.alive.copy(),
                self.step_index, T / n_steps, n_steps)
        self.worker = threading.Thread(target=self._run, args=args, daemon=True)
        self.worker.start()
        self.controls.set_playing(True)

    def _run(self, prev, pos, mom, alive, i, dt, n_steps):
        while alive.any() and i < n_steps and not self.stop.is_set():
            alive, new_pos, new_mom, detections = self.sim.step(pos, mom, dt, prev, alive)
            prev, pos, mom = pos, new_pos, new_mom
            i += 1
            while not self.stop.is_set():
                try:
                    self.queue.put((alive, pos, mom, i, detections), timeout=0.05)
                    break
                except queue.Full:
                    pass

    def pause(self):
        self.stop.set()
        if self.worker is not None:
            self.worker.join()
            self.worker = None
        while not self.queue.empty():
            self.queue.get_nowait()
        self.controls.set_playing(False)

    def _poll(self):
        _, _, steps_per_frame = self.controls.values()
        state = None
        for _ in range(steps_per_frame):
            try:
                state = self.queue.get_nowait()
            except queue.Empty:
                break
            self._apply(*state)
        if state is not None:
            self._show()
        if self.worker is not None and not self.worker.is_alive() and self.queue.empty():
            self.worker = None
            self.controls.set_playing(False)
            if self.controls.loop_enabled():
                self.resample(keep_counts=True)
                self.play()
        self.root.after(POLL_MS, self._poll)

    def _interrupt(self):
        """Pause for an edit; returns whether playback should resume afterwards."""
        was_playing = self.worker is not None
        self.pause()
        return was_playing

    def _resume(self, was_playing):
        if self.controls.loop_enabled() and not self.alive.any():
            self.resample(keep_counts=True)
        if was_playing or self.controls.loop_enabled():
            self.play()

    # --- element editing ------------------------------------------------
    def add_element(self, cls):
        self._was_playing = self._interrupt()
        self.controls.set_status(f"Drag a box for the {cls.__name__}")
        self.plot.start_rectangle(lambda corners: self._create_element(cls, corners))

    def _next_id(self, prefix):
        taken = {d.id for d in self.sim.detectors} | {e.id for e in self.sim.elements if isinstance(e, DetectorArray)}
        n = 1
        while f"{prefix}_{n}" in taken:
            n += 1
        return f"{prefix}_{n}"

    def _create_element(self, cls, corners):
        overrides = dict(zip(("x0", "y0", "x1", "y1"), corners))
        if cls is Detector:
            overrides["id"] = self._next_id("detector")
        elif cls is DetectorArray:
            overrides["id"] = self._next_id("array")
        values = initial_values(cls, overrides)
        result = edit_values(self.root, cls, values)
        if result:
            try:
                self.sim.add_element(cls(**result))
            except ValueError as exc:
                messagebox.showerror("Invalid element", str(exc))
        self.plot.redraw_elements()
        self._show()
        self._resume(self._was_playing)

    def edit_element(self, el):
        was_playing = self._interrupt()
        result = edit_values(self.root, type(el), initial_values(el), allow_delete=True)
        if result == "delete":
            self.sim.elements.remove(el)
        elif result:
            others = {d.id for e in self.sim.elements if e is not el for d in detectors_of(e)}
            if isinstance(el, Detector) and result["id"] in others:
                messagebox.showerror("Invalid element", f"duplicate detector id {result['id']!r}")
            elif isinstance(el, DetectorArray) and any(i.startswith(result["id"] + "_") for i in others):
                messagebox.showerror("Invalid element", f"detector id prefix {result['id']!r} already in use")
            else:
                for name, value in result.items():
                    setattr(el, name, value)
        self.plot.redraw_elements()
        self._show()
        self._resume(was_playing)

    def edit_source(self):
        was_playing = self._interrupt()
        result = edit_values(self.root, ParticleSource, initial_values(self.sim.source))
        if result:
            self.sim.source = ParticleSource(**result)
            self.plot.redraw_elements()
            self.resample()
        self._resume(was_playing)

    def save_config(self):
        save_config(self.sim, self.controls.settings())
        self.controls.set_status(f"Saved {CONFIG_FILE}; it loads at next start")


def main():
    sim = ParticleSimulator2D(ParticleSource(x=1.0, y=1.0, px=1.0, py=0.0))
    settings = None
    config = load_config()
    if config:
        sim.source, elements, settings = config
        for element in elements:
            sim.add_element(element)
    App(sim, settings).run()


if __name__ == "__main__":
    main()
