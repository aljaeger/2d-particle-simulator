import pytest

from elements import Detector, MagneticField
from gui.fields import editable_fields, initial_values, parse_values
from simulator import ParticleSource


def test_editable_fields_skip_state():
    names = [f.name for f in editable_fields(Detector)]
    assert names == ["x0", "y0", "x1", "y1", "id"]


def test_initial_values_from_class_with_corner_overrides():
    values = initial_values(MagneticField, {"x0": 1, "y0": 2, "x1": 3, "y1": 4})
    assert values == {"x0": "1", "y0": "2", "x1": "3", "y1": "4", "bz": "1.0"}


def test_initial_values_from_instance():
    el = Detector(0, 0, 1, 1, id="A")
    assert initial_values(el) == {"x0": "0", "y0": "0", "x1": "1", "y1": "1", "id": "A"}


def test_parse_values_converts_types_and_rejects_bad_input():
    parsed = parse_values(MagneticField, {"x0": "1", "y0": "2", "x1": "3", "y1": "4", "bz": "-0.5"})
    assert parsed == {"x0": 1.0, "y0": 2.0, "x1": 3.0, "y1": 4.0, "bz": -0.5}
    assert MagneticField(**parsed).bz == -0.5
    with pytest.raises(ValueError, match="bz"):
        parse_values(MagneticField, {"x0": "1", "y0": "2", "x1": "3", "y1": "4", "bz": "abc"})


def test_parse_values_roundtrips_source():
    src = ParticleSource(x=1, y=2, px=3, py=4, sigma_px=0.1, charge=-1)
    assert ParticleSource(**parse_values(ParticleSource, initial_values(src))) == src
