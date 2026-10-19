import os

import matplotlib

matplotlib.use("Agg")

from elements import Detector, ElectricField, MagneticField, Wall
from simulator import ParticleSimulator2D, ParticleSource
import visualization


def _sim():
    sim = ParticleSimulator2D(ParticleSource(x=0, y=0.5, px=1.0))
    sim.add_element(Wall(5, 0, 6, 1))
    sim.add_element(Detector(2, 0, 3, 1, id="A"))
    sim.add_element(MagneticField(0, 2, 1, 3, bz=1.0))
    sim.add_element(MagneticField(1, 2, 2, 3, bz=-1.0))
    sim.add_element(ElectricField(3, 2, 4, 3, ex=1.0, ey=1.0))
    return sim


def test_savefig_and_animate_write_files(tmp_path, monkeypatch):
    monkeypatch.setattr(visualization, "FIGURES_DIR", str(tmp_path))
    sim = _sim()
    result = sim.simulate(T=6.0, n_steps=60, N=3)
    assert not result.alive[-1].any()
    png = sim.savefig("config.png", result)
    gif = sim.animate(result, "anim.gif", fps=10, stride=5)
    assert os.path.getsize(png) > 0
    assert os.path.getsize(gif) > 0


def test_electric_arrows_have_fixed_length():
    from matplotlib import pyplot as plt

    lengths = []
    for ex in (1.0, 100.0):
        fig, ax = plt.subplots()
        visualization._draw_electric(ElectricField(0, 0, 2, 2, ex=ex, ey=0.0), ax)
        quiver = ax.collections[-1]
        lengths.append(float(abs(quiver.U[0])))
        plt.close(fig)
    assert lengths[0] == lengths[1] > 0
