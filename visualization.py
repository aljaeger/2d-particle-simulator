import os

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Rectangle

from elements import Detector, DetectorArray, ElectricField, MagneticField, Quadrupole, Wall

FIGURES_DIR = "figures"
GRID_N = 5


def detector_color(counts, scale=None):
    """Grey when idle, otherwise green whose opacity grows with counts: saturating around ten
    particles, or linearly up to `scale` when given."""
    if counts == 0:
        return (0.5, 0.5, 0.5, 0.3)
    level = min(counts / scale, 1.0) if scale else 1 - 0.7 ** counts
    return (0.0, 0.6, 0.0, 0.3 + 0.7 * level)


def _rect(el, **kwargs):
    return Rectangle((el.xmin, el.ymin), el.xmax - el.xmin, el.ymax - el.ymin, **kwargs)


def _grid(el):
    xs = np.linspace(el.xmin, el.xmax, GRID_N + 2)[1:-1]
    ys = np.linspace(el.ymin, el.ymax, GRID_N + 2)[1:-1]
    return np.meshgrid(xs, ys)


def _draw_wall(el, ax):
    return ax.add_patch(_rect(el, facecolor="black", edgecolor="black"))


def _draw_detector(el, ax):
    return ax.add_patch(_rect(el, facecolor=detector_color(el.counts), edgecolor="black"))


def _draw_magnetic(el, ax):
    patch = ax.add_patch(_rect(el, facecolor="red", edgecolor="red", alpha=0.2))
    X, Y = _grid(el)
    if el.bz < 0:
        ax.plot(X.ravel(), Y.ravel(), "x", color="red", markersize=6)
    else:
        ax.plot(X.ravel(), Y.ravel(), "o", color="red", markerfacecolor="none", markersize=8)
        ax.plot(X.ravel(), Y.ravel(), ".", color="red", markersize=3)
    return patch


def _draw_quadrupole(el, ax):
    patch = ax.add_patch(_rect(el, facecolor="darkorange", edgecolor="darkorange", alpha=0.2))
    X, Y = _grid(el)
    bz = el.bz(np.stack([X.ravel(), Y.ravel()], axis=-1))
    for x, y, b in zip(X.ravel(), Y.ravel(), bz):
        size = 8 * abs(b) / abs(el.strength) if el.strength else 0
        if b < 0:
            ax.plot(x, y, "x", color="darkorange", markersize=size)
        elif b > 0:
            ax.plot(x, y, "o", color="darkorange", markerfacecolor="none", markersize=size)
            ax.plot(x, y, ".", color="darkorange", markersize=size / 3)
    return patch


def _draw_electric(el, ax):
    patch = ax.add_patch(_rect(el, facecolor="blue", edgecolor="blue", alpha=0.2))
    norm = np.hypot(el.ex, el.ey)
    if norm == 0:
        return patch
    X, Y = _grid(el)
    length = 0.7 * min(el.xmax - el.xmin, el.ymax - el.ymin) / (GRID_N + 1)
    dx, dy = length * el.ex / norm, length * el.ey / norm
    ax.quiver(X - dx / 2, Y - dy / 2, np.full(X.shape, dx), np.full(Y.shape, dy),
              angles="xy", scale_units="xy", scale=1, color="blue", width=0.004)
    return patch


def _draw_generic(el, ax):
    return ax.add_patch(_rect(el, facecolor="grey", edgecolor="black", alpha=0.3))


_DRAWERS = {
    Wall: _draw_wall,
    Detector: _draw_detector,
    MagneticField: _draw_magnetic,
    Quadrupole: _draw_quadrupole,
    ElectricField: _draw_electric,
}


def draw_elements(sim, ax):
    """Draw every element and the source. Returns {id(element): patch}."""
    artists = {}
    for el in sim.elements:
        if isinstance(el, DetectorArray):
            for cell in el.cells:
                artists[id(cell)] = _draw_detector(cell, ax)
            artists[id(el)] = ax.add_patch(_rect(el, fill=False, edgecolor="black", linewidth=1.5))
        else:
            artists[id(el)] = _DRAWERS.get(type(el), _draw_generic)(el, ax)
    ax.plot(sim.source.x, sim.source.y, marker="*", color="black", markersize=10)
    return artists


def axis_limits(sim, result=None, margin=0.05):
    xs = [sim.source.x]
    ys = [sim.source.y]
    for el in sim.elements:
        xs += [el.xmin, el.xmax]
        ys += [el.ymin, el.ymax]
    if result is not None and len(result.positions):
        xs += [result.positions[..., 0].min(), result.positions[..., 0].max()]
        ys += [result.positions[..., 1].min(), result.positions[..., 1].max()]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    pad = margin * max(xmax - xmin, ymax - ymin, 1.0)
    return xmin - pad, xmax + pad, ymin - pad, ymax + pad


def _setup_axes(ax, sim, result=None):
    xmin, xmax, ymin, ymax = axis_limits(sim, result)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_xlabel("x")
    ax.set_ylabel("y")


def _figure_path(filename):
    os.makedirs(FIGURES_DIR, exist_ok=True)
    return os.path.join(FIGURES_DIR, filename)


def savefig(sim, filename, result=None):
    fig, ax = plt.subplots()
    draw_elements(sim, ax)
    if result is not None:
        for p in range(result.positions.shape[1]):
            ax.plot(result.positions[:, p, 0], result.positions[:, p, 1], "k-", linewidth=0.8)
    _setup_axes(ax, sim, result)
    path = _figure_path(filename)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def animate(sim, result, filename, fps=30, stride=1):
    fig, ax = plt.subplots()
    artists = draw_elements(sim, ax)
    _setup_axes(ax, sim, result)
    positions, alive = result.positions, result.alive
    n_particles = positions.shape[1]
    tracks = [ax.plot([], [], "k-", linewidth=0.8)[0] for _ in range(n_particles)]
    particles, = ax.plot([], [], "ko", markersize=4)
    detectors = sim.detectors
    counts = {d.id: [int((d.crosses(positions[max(i - 1, 0)], positions[i]) & alive[i]).sum())
                     for i in range(len(positions))] for d in detectors}
    frames = list(range(0, len(result.times), stride))
    if frames[-1] != len(result.times) - 1:
        frames.append(len(result.times) - 1)

    def update(i):
        for p, track in enumerate(tracks):
            track.set_data(positions[: i + 1, p, 0], positions[: i + 1, p, 1])
        particles.set_data(positions[i, alive[i], 0], positions[i, alive[i], 1])
        for d in detectors:
            artists[id(d)].set_facecolor(detector_color(counts[d.id][i]))
        return [*tracks, particles, *(artists[id(d)] for d in detectors)]

    anim = FuncAnimation(fig, update, frames=frames, blit=True)
    path = _figure_path(filename)
    anim.save(path, writer=PillowWriter(fps=fps))
    plt.close(fig)
    return path
