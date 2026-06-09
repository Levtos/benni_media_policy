"""Smoke-Test: HA-freie logic.py lädt + decide()-Stub aufrufbar.

Lädt logic.py direkt per Pfad (logic.py ist strikt HA-frei, keine relativen Imports).
"""
from __future__ import annotations

import importlib.util
import os
import sys

DOMAIN = "benni_media_policy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGIC_PATH = os.path.join(ROOT, "custom_components", DOMAIN, "logic.py")


def _load_logic():
    name = f"{DOMAIN}_logic"
    spec = importlib.util.spec_from_file_location(name, LOGIC_PATH)
    mod = importlib.util.module_from_spec(spec)
    # In sys.modules registrieren, bevor exec läuft — sonst kann @dataclass die
    # Typ-Auflösung (sys.modules[cls.__module__]) nicht durchführen (Py 3.13).
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_logic_imports():
    logic = _load_logic()
    assert hasattr(logic, "decide")
    assert hasattr(logic, "Inputs")
    assert hasattr(logic, "PolicyDecision")


def test_decide_stub_returns_defaults():
    logic = _load_logic()
    result = logic.decide(logic.Inputs())
    assert isinstance(result, logic.PolicyDecision)
    data = result.as_dict()
    assert isinstance(data, dict)
    # Stabile Defaults (Shadow-safe).
    assert data["action"] == "none"
    assert data["volume_apply_allowed"] is False
    assert data["subwoofer_allowed"] is False
    for key in (
        "volume_target_homepods", "volume_target_denon", "audio_owner", "action",
        "volume_policy", "subwoofer_allowed", "quiet_mode", "homepods_should_pause",
        "homepods_resume_allowed", "volume_apply_allowed",
    ):
        assert key in data


def test_apply_enabled_input_accepted():
    logic = _load_logic()
    # apply_enabled ist ein reines Gating-Argument; Stub bleibt Shadow-safe.
    result = logic.decide(logic.Inputs(), apply_enabled=True)
    assert result.as_dict()["volume_apply_allowed"] is False
