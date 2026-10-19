"""Save and load the GUI configuration (source, elements, control settings) as JSON."""
import dataclasses
import json
import os

from gui.fields import ELEMENT_TYPES
from simulator import ParticleSource

CONFIG_FILE = "gui_config.json"


def _fields(obj):
    return {f.name: getattr(obj, f.name) for f in dataclasses.fields(obj) if f.init}


def save_config(sim, settings, path=CONFIG_FILE):
    data = {
        "source": _fields(sim.source),
        "elements": [{"type": type(e).__name__, **_fields(e)} for e in sim.elements],
        "settings": settings,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=float)


def load_config(path=CONFIG_FILE):
    """Returns (source, elements, settings), or None when no saved configuration exists."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    types = {cls.__name__: cls for cls in ELEMENT_TYPES}
    elements = [types[d.pop("type")](**d) for d in data["elements"]]
    return ParticleSource(**data["source"]), elements, data.get("settings", {})
