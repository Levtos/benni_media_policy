"""Entity-Basis + Roster-Beschreibungen für benni_media_policy.

Description-getrieben: das vorläufige Roster lebt hier als Daten (SENSORS /
BINARY_SENSORS); sensor.py / binary_sensor.py bauen daraus die Entities. Alle
lesen aus `coordinator.data` und liefern stabile Defaults.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_PROFILE,
    DEFAULT_PROFILE,
    DOMAIN,
    PROFILE_LABELS,
    UID_ACTION,
    UID_AUDIO_OWNER,
    UID_AUDIO_SCENARIO,
    UID_HOMEPODS_RESUME_ALLOWED,
    UID_HOMEPODS_SHOULD_PAUSE,
    UID_SUBWOOFER_ALLOWED,
    UID_VOLUME_APPLY_ALLOWED,
    UID_VOLUME_POLICY,
    UID_VOLUME_TARGET_DENON,
    UID_VOLUME_TARGET_HOMEPODS,
    unique_id,
)
from .coordinator import MediaPolicyCoordinator


@dataclass(frozen=True)
class FieldDesc:
    key: str            # Feld in coordinator.data
    uid: str            # unique_id-Suffix (auch object_id-Basis)
    name: str           # friendly name
    icon: str | None = None
    unit: str | None = None
    attr_keys: tuple[str, ...] = ()   # zusätzliche data-Felder als state-attributes


SENSORS: tuple[FieldDesc, ...] = (
    FieldDesc("volume_target_homepods", UID_VOLUME_TARGET_HOMEPODS, "Volume Target HomePods", "mdi:speaker", "%"),
    FieldDesc("volume_target_denon", UID_VOLUME_TARGET_DENON, "Volume Target Denon", "mdi:audio-video", "%"),
    FieldDesc("audio_owner", UID_AUDIO_OWNER, "Audio Owner", "mdi:account-music"),
    FieldDesc(
        "audio_scenario", UID_AUDIO_SCENARIO, "Audio Scenario", "mdi:music-circle",
        attr_keys=("audio_scenario_label", "audio_scenario_detail"),
    ),
    FieldDesc("action", UID_ACTION, "Action", "mdi:play-pause"),
    FieldDesc("volume_policy", UID_VOLUME_POLICY, "Volume Policy", "mdi:tune-variant"),
)

# quiet_mode entfernt → lebt in media_state (L1, FLEET-31), Policy konsumiert es.
BINARY_SENSORS: tuple[FieldDesc, ...] = (
    FieldDesc("subwoofer_allowed", UID_SUBWOOFER_ALLOWED, "Subwoofer Allowed", "mdi:speaker-wireless"),
    FieldDesc("homepods_should_pause", UID_HOMEPODS_SHOULD_PAUSE, "HomePods Should Pause", "mdi:pause-octagon"),
    FieldDesc("homepods_resume_allowed", UID_HOMEPODS_RESUME_ALLOWED, "HomePods Resume Allowed", "mdi:play-circle"),
    FieldDesc("volume_apply_allowed", UID_VOLUME_APPLY_ALLOWED, "Volume Apply Allowed", "mdi:lock-open-check"),
)


def device_info(entry: ConfigEntry) -> dict[str, Any]:
    # Der Device-Name bestimmt bei has_entity_name den Entity-Slug:
    #   "Benni Media Policy"  → sensor.benni_media_policy_*
    #   "Eltern Media Policy" → sensor.eltern_media_policy_*
    profile = entry.data.get(CONF_PROFILE, DEFAULT_PROFILE)
    label = PROFILE_LABELS.get(profile, "Benni")
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": f"{label} Media Policy",
        "manufacturer": "Benni",
        "model": f"Media Policy · {label}",
    }


class MediaPolicyEntity(CoordinatorEntity[MediaPolicyCoordinator]):
    """Gemeinsame Basis: liest aus coordinator.data via FieldDesc."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: MediaPolicyCoordinator, entry: ConfigEntry, desc: FieldDesc
    ) -> None:
        super().__init__(coordinator)
        self._desc = desc
        self._attr_unique_id = unique_id(entry.entry_id, desc.uid)
        self._attr_name = desc.name
        # Kein suggested_object_id: der Slug kommt aus dem profil-getriebenen
        # Device-Namen (has_entity_name) → <profil>_media_policy_<type>.
        if desc.icon:
            self._attr_icon = desc.icon
        self._attr_device_info = device_info(entry)

    @property
    def _value(self) -> Any:
        return (self.coordinator.data or {}).get(self._desc.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if not self._desc.attr_keys:
            return None
        data = self.coordinator.data or {}
        return {k: data.get(k) for k in self._desc.attr_keys}
