# 2D Particle Simulator

A two-dimensional simulator for charged particles moving through rectangular elements: absorbing
walls, dipole and quadrupole magnetic fields, electric fields and detectors. Particles are
integrated with RK4 in dimensionless units (charge and mass default to 1). The project has three
layers that build on each other:

| Layer | Files | What it does |
|---|---|---|
| Simulation | `simulator.py`, `elements/` | `ParticleSimulator2D` with a `ParticleSource`, a list of elements and `simulate()` |
| Visualization | `visualization.py`, `demo.py` | Configuration plots and animated GIFs in `figures/` |
| Interactive | `gui/` (tkinter + matplotlib), `web/` (Pyodide in the browser) | Drag elements into place, edit them, play and step the simulation |

## Setup

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/pytest

## Simulation

```python
from elements import Detector, MagneticField, Wall
from simulator import ParticleSimulator2D, ParticleSource

sim = ParticleSimulator2D(ParticleSource(x=0, y=2, px=1.0, sigma_py=0.05), seed=1)
sim.add_element(MagneticField(6, 0, 10, 4, bz=-0.5))
sim.add_element(Detector(7.5, 4, 8.5, 5, id="D1"))
sim.add_element(Wall(0, 9.5, 10, 10))

result = sim.simulate(T=20.0, n_steps=2000, N=10)
result.positions          # (steps, N, 2) tracks
result.alive              # (steps, N) survival mask
result.events             # DetectionEvent(time, detector_id, duration, particle)
```

Every element is a dataclass defined by two opposing corners plus its own parameters, and
implements `interact(pos, mom, charge, mass, prev_pos)` returning the acceleration, whether the
particle is killed and whether it is detected. Detection uses the segment from the previous
position, so thin detectors are not skipped by large steps.

| Element | Parameters |
|---|---|
| `Wall` | none; absorbs particles |
| `MagneticField` | `bz` |
| `Quadrupole` | `strength`, `dir_x`, `dir_y`; `Bz` grows linearly across the beam direction |
| `ElectricField` | `ex`, `ey` |
| `Detector` | `id`; reports `counts` of particles crossing it |
| `DetectorArray` | `nx`, `ny`, `id`; a grid of detectors named `id_i_j` |

## Visualization

    .venv/bin/python demo.py

writes `figures/demo_config.png` and `figures/demo.gif`. Walls are black, detectors grey turning
green with occupancy, magnetic fields red with dots or crosses for the field direction,
quadrupoles orange, electric fields blue with normalized arrows. `sim.savefig(name, result)` and
`sim.animate(result, name)` do the same for any configuration.

## Interactive interface

    .venv/bin/python -m gui.app

opens a control window and a plot window. Add an element by pressing its button and dragging a
box; a dialog built from the element's dataclass fields sets the remaining parameters. Click an
element to edit or delete it. Play, Step, Reset and Resample drive the particles, Loop restarts
automatically when all particles are dead, and the display can show instantaneous or cumulative
detector counts. "Save configuration" writes `gui_config.json`, which is loaded as the default at
the next start. The integration runs in a worker thread so the window stays responsive.

tkinter is part of the system Python (`sudo apt install python3-tk` on Debian/Ubuntu), and a
display is required.

`web/` is a browser version of the same interface running the Python physics through Pyodide;
see `web/README.md`.

## Adding an element type

Create a dataclass in `elements/` inheriting from `Element`, override `interact()`, export it in
`elements/__init__.py` and list it in `ELEMENT_TYPES` in `gui/fields.py`. The dialog, config
save/load and the "Add" button follow automatically; add a drawer in `visualization.py` for a
custom look, otherwise it is drawn as a grey rectangle.
