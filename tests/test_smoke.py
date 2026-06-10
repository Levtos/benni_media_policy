"""Smoke-Test: HA-freie logic.py lädt + decide() liefert stabile Defaults."""
from __future__ import annotations

import bmp_logic as logic


def test_logic_imports():
    assert hasattr(logic, "decide")
    assert hasattr(logic, "Inputs")
    assert hasattr(logic, "PolicyDecision")
    assert hasattr(logic, "OrchestratorState")
    assert hasattr(logic, "VolumeSettings")


def test_decide_defaults():
    d, state = logic.decide(logic.Inputs(), logic.OrchestratorState())
    assert isinstance(d, logic.PolicyDecision)
    assert isinstance(state, logic.OrchestratorState)
    data = d.as_dict()
    # Roster vollständig + Shadow-safe Defaults.
    for key in (
        "volume_target_homepods", "volume_target_denon", "audio_owner", "action",
        "volume_policy", "subwoofer_allowed", "homepods_should_pause",
        "homepods_resume_allowed", "volume_apply_allowed",
    ):
        assert key in data
    assert "quiet_mode" not in data  # lebt in media_state (FLEET-31)
    assert data["audio_owner"] == "none"
    assert data["action"] == "none"
    # Keine Speaker konfiguriert → volume blocked, apply nicht erlaubt.
    assert data["volume_policy"] == "blocked"
    assert data["volume_apply_allowed"] is False
    assert data["subwoofer_allowed"] is False
