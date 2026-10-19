from elements import Detector, MagneticField, Wall
from gui.config import load_config, save_config
from simulator import ParticleSimulator2D, ParticleSource


def test_config_round_trip(tmp_path):
    path = tmp_path / "cfg.json"
    sim = ParticleSimulator2D(ParticleSource(x=1, y=2, px=0.5, sigma_py=0.1, charge=-1))
    sim.add_element(Wall(0, 0, 1, 1))
    sim.add_element(MagneticField(2, 2, 3, 3, bz=-0.5))
    sim.add_element(Detector(4, 4, 5, 5, id="D"))
    settings = {"T": 20.0, "n_steps": 500, "steps_per_frame": 3, "N": 4, "loop": True}
    save_config(sim, settings, path)

    source, elements, loaded = load_config(path)
    assert source == sim.source
    assert elements == sim.elements
    assert loaded == settings


def test_load_config_missing_file(tmp_path):
    assert load_config(tmp_path / "none.json") is None
