"""Dataclass introspection used to build generic property dialogs for any element."""
import dataclasses
from dataclasses import MISSING

from elements import Detector, DetectorArray, ElectricField, MagneticField, Quadrupole, Wall

ELEMENT_TYPES = [Wall, MagneticField, Quadrupole, ElectricField, Detector, DetectorArray]


def editable_fields(cls):
    return [f for f in dataclasses.fields(cls) if f.init]


def initial_values(obj_or_cls, overrides=None):
    """Field values as strings: from an instance, or from class defaults with overrides."""
    overrides = overrides or {}
    is_instance = not isinstance(obj_or_cls, type)
    cls = type(obj_or_cls) if is_instance else obj_or_cls
    values = {}
    for f in editable_fields(cls):
        if f.name in overrides:
            values[f.name] = str(overrides[f.name])
        elif is_instance:
            values[f.name] = str(getattr(obj_or_cls, f.name))
        elif f.default is not MISSING:
            values[f.name] = str(f.default)
        else:
            values[f.name] = ""
    return values


def parse_values(cls, strings):
    """Convert entry strings back to typed values. Raises ValueError on bad input."""
    values = {}
    for f in editable_fields(cls):
        text = strings[f.name].strip()
        if f.type in (float, "float"):
            try:
                values[f.name] = float(text)
            except ValueError:
                raise ValueError(f"{f.name}: {text!r} is not a number")
        elif f.type in (int, "int"):
            try:
                values[f.name] = int(text)
            except ValueError:
                raise ValueError(f"{f.name}: {text!r} is not an integer")
        else:
            values[f.name] = text
    return values
