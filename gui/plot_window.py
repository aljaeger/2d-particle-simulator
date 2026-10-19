import tkinter as tk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector

from visualization import axis_limits, detector_color, draw_elements

DEFAULT_DOMAIN = (0.0, 10.0, 0.0, 10.0)


class PlotWindow:
    def __init__(self, root, sim, on_element_click):
        self.sim = sim
        self.on_element_click = on_element_click
        self.top = tk.Toplevel(root)
        self.top.title("Simulation")
        self.top.protocol("WM_DELETE_WINDOW", root.destroy)
        self.fig = Figure(figsize=(6, 6))
        self.ax = self.fig.add_subplot()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.top)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.artists = {}
        self._rect_callback = None
        self.redraw_elements()

    def redraw_elements(self):
        self.ax.cla()
        self.artists = draw_elements(self.sim, self.ax)
        self.tracks = []
        self.particles, = self.ax.plot([], [], "ko", markersize=4)
        xmin, xmax, ymin, ymax = axis_limits(self.sim)
        self.ax.set_xlim(min(xmin, DEFAULT_DOMAIN[0]), max(xmax, DEFAULT_DOMAIN[1]))
        self.ax.set_ylim(min(ymin, DEFAULT_DOMAIN[2]), max(ymax, DEFAULT_DOMAIN[3]))
        self.ax.set_aspect("equal")
        self.selector = RectangleSelector(self.ax, self._on_select, useblit=True, button=[1], interactive=False)
        self.selector.set_active(False)
        self.canvas.draw_idle()

    def update_particles(self, track, alive, counts, scales=None, visible=True):
        """track has shape (steps, N, 2); counts maps detector id -> count shown as intensity,
        saturating near ten, or scaled linearly to scales[id] when given."""
        n_particles = track.shape[1]
        while len(self.tracks) < n_particles:
            self.tracks.append(self.ax.plot([], [], "k-", linewidth=0.8)[0])
        for p, line in enumerate(self.tracks):
            if p < n_particles:
                line.set_data(track[:, p, 0], track[:, p, 1])
            else:
                line.set_data([], [])
        pos = track[-1]
        self.particles.set_data(pos[alive, 0], pos[alive, 1])
        self.particles.set_visible(visible)
        for line in self.tracks:
            line.set_visible(visible)
        for det in self.sim.detectors:
            scale = scales.get(det.id) if scales else None
            self.artists[id(det)].set_facecolor(detector_color(counts.get(det.id, 0), scale))
        self.canvas.draw_idle()

    def start_rectangle(self, callback):
        self._rect_callback = callback
        self.selector.set_active(True)

    def _on_select(self, eclick, erelease):
        self.selector.set_active(False)
        callback, self._rect_callback = self._rect_callback, None
        coords = (eclick.xdata, eclick.ydata, erelease.xdata, erelease.ydata)
        if callback and None not in coords:
            callback(coords)

    def _on_click(self, event):
        if self.selector.active or event.inaxes != self.ax:
            return
        for el in reversed(self.sim.elements):
            if el.contains((event.xdata, event.ydata)):
                self.on_element_click(el)
                return
