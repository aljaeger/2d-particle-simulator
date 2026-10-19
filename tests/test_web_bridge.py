import json

import pytest

from elements import Detector, DetectorArray, MagneticField, Wall
from gui.fields import ELEMENT_TYPES
from simulator import ParticleSimulator2D, ParticleSource
from web.bridge import Bridge, call


def make_bridge():
    sim = ParticleSimulator2D(ParticleSource(x=1.0, y=5.0, px=1.0), seed=0)
    sim.add_element(Wall(8, 0, 9, 10))
    sim.add_element(Detector(4, 4, 5, 6, id="d1"))
    sim.add_element(DetectorArray(6, 4, 7, 6, nx=2, ny=1, id="a1"))
    sim.add_element(MagneticField(2, 2, 3, 3, bz=-1))
    return Bridge(sim)


def test_element_types_match_gui():
    assert Bridge().element_types() == [cls.__name__ for cls in ELEMENT_TYPES]


def test_scene_lists_elements_with_array_cells():
    scene = make_bridge().scene()
    assert scene["source"] == [1.0, 5.0]
    assert scene["xlim"] == [0.0, 10.0] and scene["ylim"] == [-0.5, 10.5]
    types = [e["type"] for e in scene["elements"]]
    assert types == ["Wall", "Detector", "DetectorArray", "MagneticField"]
    assert [c["id"] for c in scene["elements"][2]["cells"]] == ["a1_0_0", "a1_1_0"]
    assert scene["elements"][3]["sign"] == -1 and len(scene["elements"][3]["grid"]) == 25


def test_step_returns_frames_and_detects():
    b = make_bridge()
    b.resample(3)
    r = b.step(5, 0.1, 1000)
    assert len(r["frames"]) == 5 and r["step"] == 5 and not r["done"]
    assert all(len(frame) == 3 for frame in r["frames"])
    total = 0
    while not r["done"]:
        r = b.step(50, 0.1, 1000)
        total += len(r["frames"])
    assert r["alive"] == [False, False, False]
    assert r["cumulative"]["d1"] == 3 and r["scales"]["d1"] == 3
    assert b.step(5, 0.1, 1000)["frames"] == []
    assert b.reset()["step"] == 0 and b.cumulative == {}


def test_add_update_delete_and_duplicate_ids():
    b = make_bridge()
    values = b.new_element_values("Detector", [0.5, 1.5, 2.5, 3.5])
    assert values == {"x0": "0.5", "y0": "1.5", "x1": "2.5", "y1": "3.5", "id": "detector_1"}
    assert b.add_element("Detector", {**values, "id": "d1"}) == "duplicate detector id 'd1'"
    assert b.add_element("Detector", {**values, "x0": "abc"}) == "x0: 'abc' is not a number"
    assert b.add_element("Detector", values) is None
    assert b.element_values(4) == values
    assert b.update_element(4, {**values, "id": "a1_0_0"}) == "duplicate detector id 'a1_0_0'"
    assert b.update_element(2, {**b.element_values(2), "id": "detector"}) == "detector id prefix 'detector' already in use"
    assert b.update_element(4, {**values, "x0": "7"}) is None
    assert b.sim.elements[4].x0 == 7.0
    b.delete_element(4)
    assert len(b.sim.elements) == 4
    assert b.set_source({**b.source_values(), "px": "2"}) is None
    assert b.sim.source.px == 2.0


def test_config_roundtrip():
    b = make_bridge()
    text = b.save_config({"T": 5.0, "N": 3})
    other = Bridge()
    assert other.load_config(text) == {"T": 5.0, "N": 3}
    assert other.sim.elements == b.sim.elements and other.sim.source == b.sim.source


def test_call_speaks_json():
    assert json.loads(call("element_types")) == [cls.__name__ for cls in ELEMENT_TYPES]
    r = json.loads(call("step", json.dumps([2, 0.01, 10])))
    assert len(r["frames"]) == 2
    with pytest.raises(AttributeError):
        call("no_such_function")
