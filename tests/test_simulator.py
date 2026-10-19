import numpy as np
import pytest

from elements import Detector, MagneticField, Wall
from simulator import ParticleSimulator2D, ParticleSource


def test_free_particle_moves_in_straight_line():
    sim = ParticleSimulator2D(ParticleSource(x=0, y=0, px=1.0, py=0.5))
    res = sim.simulate(T=2.0, n_steps=100, N=1)
    assert res.alive.all()
    assert res.positions.shape == (101, 1, 2)
    np.testing.assert_allclose(res.positions[-1, 0], [2.0, 1.0])
    np.testing.assert_allclose(res.momenta[-1, 0], [1.0, 0.5])
    assert res.events == []


def test_uniform_magnetic_field_gives_circular_orbit():
    q, m, v, bz = 1.0, 2.0, 1.0, 0.5
    sim = ParticleSimulator2D(ParticleSource(x=0, y=0, px=m * v, py=0, charge=q, mass=m))
    sim.add_element(MagneticField(-100, -100, 100, 100, bz=bz))
    radius = m * v / (q * bz)
    period = 2 * np.pi * radius / v
    res = sim.simulate(T=period, n_steps=2000, N=1)
    # Bz > 0 with vx > 0 gives Fy < 0: centre is at (0, -radius).
    r = np.linalg.norm(res.positions[:, 0] - [0, -radius], axis=1)
    np.testing.assert_allclose(r, radius, rtol=1e-5)
    energy = np.sum(res.momenta[:, 0] ** 2, axis=1) / (2 * m)
    np.testing.assert_allclose(energy, energy[0], rtol=1e-6)
    np.testing.assert_allclose(res.positions[-1, 0], [0, 0], atol=1e-4)


def test_wall_kills_and_truncates_track():
    sim = ParticleSimulator2D(ParticleSource(x=0, y=0, px=1.0))
    sim.add_element(Wall(2, -1, 3, 1))
    res = sim.simulate(T=10.0, n_steps=1000, N=1)
    assert not res.alive[-1, 0]
    assert len(res.times) < 1001
    assert 2.0 <= res.positions[-1, 0, 0] <= 2.02
    assert np.all(res.positions[:-1, 0, 0] < 2.0)


def test_detector_crossing_gives_single_event_with_duration():
    sim = ParticleSimulator2D(ParticleSource(x=0, y=0, px=2.0))
    sim.add_element(Detector(1, -1, 2, 1, id="A"))
    res = sim.simulate(T=5.0, n_steps=1000, N=1)
    assert len(res.events) == 1
    ev = res.events[0]
    assert ev.detector_id == "A" and ev.particle == 0
    assert ev.time == pytest.approx(0.5, abs=0.01)
    assert ev.duration == pytest.approx(0.5, abs=0.01)


def test_separated_crossings_give_separate_events():
    sim = ParticleSimulator2D(ParticleSource(x=0, y=0, px=1.0))
    sim.add_element(Detector(1, -1, 2, 1, id="A"))
    sim.add_element(Detector(3, -1, 4, 1, id="B"))
    sim.add_element(Detector(5, -1, 6, 1, id="C"))
    res = sim.simulate(T=10.0, n_steps=1000, N=1)
    assert [e.detector_id for e in res.events] == ["A", "B", "C"]
    assert [e.time for e in res.events] == pytest.approx([1.0, 3.0, 5.0], abs=0.011)


def test_event_still_open_at_end_is_closed():
    sim = ParticleSimulator2D(ParticleSource(x=0, y=0, px=1.0))
    sim.add_element(Detector(1, -1, 20, 1, id="A"))
    res = sim.simulate(T=3.0, n_steps=300, N=1)
    assert len(res.events) == 1
    assert res.events[0].duration == pytest.approx(2.0, abs=0.01)


def test_duplicate_detector_id_rejected():
    sim = ParticleSimulator2D()
    sim.add_element(Detector(0, 0, 1, 1, id="A"))
    with pytest.raises(ValueError):
        sim.add_element(Detector(2, 2, 3, 3, id="A"))


def test_source_sampling():
    src = ParticleSource(x=1, y=2, px=3, py=4, sigma_px=0, sigma_py=0)
    pos, mom = src.sample(np.random.default_rng(0), 3)
    np.testing.assert_array_equal(pos, [[1, 2]] * 3)
    np.testing.assert_array_equal(mom, [[3, 4]] * 3)
    src = ParticleSource(px=0, py=0, sigma_px=1.0, sigma_py=1.0)
    _, mom = src.sample(np.random.default_rng(0), 500)
    assert mom.shape == (500, 2)
    assert abs(mom.mean()) < 0.2 and abs(mom.std() - 1.0) < 0.2


def test_many_particles_counted_per_detector():
    sim = ParticleSimulator2D(ParticleSource(x=0, y=0, px=1.0, sigma_py=0.3), seed=0)
    sim.add_element(Detector(1, -5, 2, 5, id="A"))
    sim.add_element(Wall(3, -5, 4, 0))
    res = sim.simulate(T=5.0, n_steps=500, N=10)
    assert res.positions.shape == (501, 10, 2)
    assert sorted(e.particle for e in res.events) == list(range(10))
    assert all(e.detector_id == "A" for e in res.events)
    # Particles heading down hit the wall and freeze; the rest survive and keep moving.
    went_down = res.momenta[0, :, 1] < 0
    np.testing.assert_array_equal(res.alive[-1], ~went_down)
    frozen = (res.positions[-1] == res.positions[-2]).all(axis=1)
    np.testing.assert_array_equal(frozen, went_down)


def test_step_reports_counts_on_detector():
    sim = ParticleSimulator2D(ParticleSource(x=0.5, y=0, px=1.0))
    sim.add_element(Detector(0, -1, 1, 1, id="A"))
    pos, mom = sim.source.sample(sim.rng, 4)
    alive, pos, mom, detections = sim.step(pos, mom, 0.1)
    assert detections["A"].tolist() == [True] * 4
    assert sim.detectors[0].counts == 4


def test_thin_detector_not_skipped_by_large_step():
    sim = ParticleSimulator2D(ParticleSource(x=0, y=0, px=1.0))
    sim.add_element(Detector(1.02, -1, 1.04, 1, id="thin"))
    res = sim.simulate(T=2.0, n_steps=20, N=1)       # dt = 0.1, detector is 0.02 wide
    assert len(res.events) == 1
    assert res.events[0].time == pytest.approx(1.1, abs=1e-9)
    assert res.events[0].duration == pytest.approx(0.1, abs=1e-9)


def test_detector_array_cells_and_events():
    from elements import DetectorArray

    arr = DetectorArray(2, 0, 4, 1, nx=4, ny=2, id="arr")
    assert len(arr.cells) == 8
    assert arr.cells[0].id == "arr_0_0" and (arr.cells[0].xmin, arr.cells[0].xmax) == (2.0, 2.5)
    assert arr.cells[-1].id == "arr_3_1" and (arr.cells[-1].ymin, arr.cells[-1].ymax) == (0.5, 1.0)
    arr.nx = 2
    assert len(arr.cells) == 4 and arr.cells[1].id == "arr_1_0"

    sim = ParticleSimulator2D(ParticleSource(x=0, y=0.75, px=1.0))
    sim.add_element(arr)
    assert [d.id for d in sim.detectors] == ["arr_0_0", "arr_1_0", "arr_0_1", "arr_1_1"]
    res = sim.simulate(T=5.0, n_steps=500, N=1)
    assert [e.detector_id for e in res.events] == ["arr_0_1", "arr_1_1"]
    with pytest.raises(ValueError):
        sim.add_element(Detector(0, 0, 1, 1, id="arr_0_0"))
