"""Smoke-Test: HA-freie logic.py lädt + decide() liefert stabile Defaults."""
from __future__ import annotations

import bmp_logic as logic
import bmp_const as const


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


def test_opening_prefill_and_migrations_use_master_contract():
    prefill = const.PROFILE_PREFILL[const.PROFILE_BENNI]

    assert prefill[const.CONF_OPENING] == const.CORE_OPENINGS_MASTER_ENTITY
    assert prefill[const.CONF_DENON_ACTIVE] == "sensor.benni_master_denon"
    assert (
        const.LEGACY_ENTITY_MAP["sensor.benni_device_living_avr"]
        == "sensor.benni_master_denon"
    )
    assert (
        const.LEGACY_ENTITY_MAP["binary_sensor.living_denon_plug_power_active_atomic"]
        == "sensor.benni_master_denon"
    )
    assert (
        const.LEGACY_ENTITY_MAP["sensor.benni_combined_opening_any_open_or_tilted"]
        == const.CORE_OPENINGS_MASTER_ENTITY
    )
    assert (
        const.LEGACY_ENTITY_MAP["binary_sensor.opening_any_open_combined"]
        == const.CORE_OPENINGS_MASTER_ENTITY
    )


def test_media_presence_and_away_gate_use_system_slugs():
    """FLEET-260: presence_state/away_gate binden auf die live system_-Slugs."""
    prefill = const.PROFILE_PREFILL[const.PROFILE_BENNI]

    # Default-PREFILL zeigt auf die live existierenden system_-Slugs.
    assert (
        prefill[const.CONF_PRESENCE_STATE]
        == "sensor.system_benni_media_state_presence_state"
    )
    assert (
        prefill[const.CONF_AWAY_GATE]
        == "binary_sensor.system_benni_media_state_away_gate"
    )

    # Legacy clean-Slugs werden auf die system_-Slugs repointet.
    assert (
        const.LEGACY_ENTITY_MAP["sensor.benni_media_state_presence_state"]
        == "sensor.system_benni_media_state_presence_state"
    )
    assert (
        const.LEGACY_ENTITY_MAP["binary_sensor.benni_media_state_away_gate"]
        == "binary_sensor.system_benni_media_state_away_gate"
    )

    # Domain bleibt korrekt (sensor bleibt sensor, binary_sensor bleibt binary_sensor).
    assert prefill[const.CONF_PRESENCE_STATE].startswith("sensor.")
    assert prefill[const.CONF_AWAY_GATE].startswith("binary_sensor.")


def test_migration_repoints_only_known_legacy_values():
    """Der value-basierte Repoint fasst nur bekannte Legacy-IDs an (keine gültigen)."""
    m = const.LEGACY_ENTITY_MAP
    # bekannte Legacy-IDs → gemappt
    assert "sensor.benni_media_state_presence_state" in m
    assert "binary_sensor.benni_media_state_away_gate" in m
    # eine explizit gesetzte, gültige Fremd-Entity bleibt unberührt (nicht in der Map)
    assert "sensor.custom_presence_state" not in m
    assert "sensor.system_benni_media_state_presence_state" not in m  # kein Selbst-Loop
