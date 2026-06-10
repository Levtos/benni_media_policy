"""Lädt die HA-freien Dateien (const.py, logic.py) als synthetisches Paket.

logic.py nutzt `from .const import ...`, was über das synthetische Paket
`bmp_pure_pkg` auf die geladene const.py auflöst (Muster wie media_state).
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_DIR = os.path.join(ROOT, "custom_components", "benni_media_policy")

pkg_name = "bmp_pure_pkg"
pkg = types.ModuleType(pkg_name)
pkg.__path__ = [PKG_DIR]
sys.modules[pkg_name] = pkg


def _load(modname: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        f"{pkg_name}.{modname}", os.path.join(PKG_DIR, filename)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"{pkg_name}.{modname}"] = mod
    spec.loader.exec_module(mod)
    return mod


const = _load("const", "const.py")
logic = _load("logic", "logic.py")

sys.modules["bmp_const"] = const
sys.modules["bmp_logic"] = logic
