import pytest
import numpy as np

from elements import Detector, ElectricField, MagneticField, Quadrupole, Wall


def test_corners_normalized_in_any_order():
    w = Wall(5, 6, 1, 2)
    assert (w.xmin, w.xmax, w.ymin, w.ymax) == (1, 5, 2, 6)
    assert w.contains((1, 2)) and w.contains((5, 6))
    assert not w.contains((0.9, 3)) and not w.contains((3, 6.1))


def test_wall_kills_only_inside():
    w = Wall(0, 0, 1, 1)
    assert w.interact((0.5, 0.5), (1, 0), 1, 1)[1]
    assert not w.interact((2, 2), (1, 0), 1, 1)[1]


def test_magnetic_force_perpendicular_with_correct_sign():
    b = MagneticField(0, 0, 1, 1, bz=2.0)
    accel, killed, detected = b.interact((0.5, 0.5), (3.0, 0.0), charge=2.0, mass=1.5)
    v = np.array([2.0, 0.0])
    # F = q v x B = q (vy Bz, -vx Bz)
    np.testing.assert_allclose(accel, 2.0 / 1.5 * np.array([0.0, -4.0]))
    assert np.isclose(accel @ v, 0.0)
    assert not killed and not detected
    assert np.all(b.interact((2, 2), (3.0, 0.0), 2.0, 1.5)[0] == 0)


def test_electric_field_constant_acceleration():
    e = ElectricField(0, 0, 1, 1, ex=1.0, ey=-2.0)
    accel, _, _ = e.interact((0.5, 0.5), (0, 0), charge=3.0, mass=2.0)
    np.testing.assert_allclose(accel, [1.5, -3.0])
    assert np.all(e.interact((5, 5), (0, 0), 3.0, 2.0)[0] == 0)


def test_detector_detects_inside_only():
    d = Detector(0, 0, 1, 1, id="d1")
    assert d.interact((0.5, 0.5), (1, 0), 1, 1)[2]
    assert not d.interact((5, 5), (1, 0), 1, 1)[2]
    assert not d.interact((0.5, 0.5), (1, 0), 1, 1)[1]


def test_elements_accept_batches_of_particles():
    pos = np.array([[0.5, 0.5], [5.0, 5.0], [0.2, 0.9]])
    mom = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 2.0]])
    np.testing.assert_array_equal(Wall(0, 0, 1, 1).interact(pos, mom, 1, 1)[1], [True, False, True])
    np.testing.assert_array_equal(Detector(0, 0, 1, 1).interact(pos, mom, 1, 1)[2], [True, False, True])
    accel = MagneticField(0, 0, 1, 1, bz=1.0).interact(pos, mom, 1, 1)[0]
    np.testing.assert_allclose(accel, [[0, -1], [0, 0], [2, 0]])
    accel = ElectricField(0, 0, 1, 1, ex=1.0, ey=2.0).interact(pos, mom, 2, 1)[0]
    np.testing.assert_allclose(accel, [[2, 4], [0, 0], [2, 4]])
    prev = np.array([[-1, 0.5], [4, 5], [0.2, 0.9]])
    np.testing.assert_array_equal(Detector(0, 0, 1, 1).crosses(prev, pos), [True, False, True])


def test_crosses_segment_through_rectangle():
    d = Detector(1, 1, 2, 2, id="d")
    assert d.crosses((0, 1.5), (3, 1.5))        # straight through, no endpoint inside
    assert d.crosses((0, 0), (3, 3))            # diagonal through
    assert d.crosses((1.5, 1.5), (5, 5))        # starts inside
    assert not d.crosses((0, 0), (3, 0.5))      # passes below
    assert not d.crosses((0, 2.5), (3, 2.5))    # passes above
    assert not d.crosses((2.5, 0), (2.5, 3))    # vertical line to the right
    assert d.crosses((1.5, 0), (1.5, 3))        # vertical line through


def test_detector_detects_skipped_crossing():
    d = Detector(1, 0, 1.1, 1, id="d")
    assert d.interact((2, 0.5), (1, 0), 1, 1, prev_pos=(0, 0.5))[2]
    assert not d.interact((2, 0.5), (1, 0), 1, 1)[2]


def test_quadrupole_field_is_linear_across_beam():
    q = Quadrupole(0, 0, 4, 2, strength=3.0, dir_x=1.0, dir_y=0.0)
    assert q.bz((2, 1)) == 0
    assert q.bz((1, 2)) == pytest.approx(3.0)       # top edge, left of the beam
    assert q.bz((3, 0)) == pytest.approx(-3.0)      # bottom edge, right of the beam
    assert q.bz((2, 1.5)) == pytest.approx(1.5)
    assert q.bz((2, 0.5)) == pytest.approx(-1.5)


def test_quadrupole_follows_direction_vector():
    q = Quadrupole(0, 0, 4, 2, strength=1.0, dir_x=0.0, dir_y=1.0)
    assert q.bz((2, 0.3)) == 0                      # on the centre line x = 2
    assert q.bz((0, 1)) == pytest.approx(1.0)       # left of a beam moving +y
    assert q.bz((4, 1)) == pytest.approx(-1.0)
    reversed_beam = Quadrupole(0, 0, 4, 2, strength=1.0, dir_x=0.0, dir_y=-1.0)
    assert reversed_beam.bz((0, 1)) == pytest.approx(-1.0)


def test_quadrupole_focuses_toward_axis():
    q = Quadrupole(0, -1, 2, 1, strength=2.0, dir_x=1.0, dir_y=0.0)
    mom = np.array([1.0, 0.0])
    for offset in (0.5, -0.5):
        accel, killed, detected = q.interact((1, offset), mom, charge=1.0, mass=1.0)
        assert accel[0] == 0 and np.sign(accel[1]) == -np.sign(offset)
        assert abs(accel[1]) == pytest.approx(2.0 * abs(offset))
        assert not killed and not detected
    assert np.all(q.interact((5, 5), mom, 1.0, 1.0)[0] == 0)
