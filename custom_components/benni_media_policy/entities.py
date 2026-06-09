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
    DOMAIN,
    NAME,
    UID_ACTION,
    UID_AUDIO_OWNER,
    UID_HOMEPODS_RESUME_ALLOWED,
    UID_HOMEPODS_SHOULD_PAUSE,
    UID_QUIET_MODE,
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


SENSORS: tuple[FieldDesc, ...] = (
    FieldDesc("volume_target_homepods", UID_VOLUME_TARGET_HOMEPODS, "Volume Target HomePods", "mdi:speaker", "%"),
    FieldDesc("volume_target_denon", UID_VOLUME_TARGET_DENON, "Volume Target Denon", "mdi:audio-video", "%"),
    FieldDesc("audio_owner", UID_AUDIO_OWNER, "Audio Owner", "mdi:account-music"),
    FieldDesc("action", UID_ACTION, "Action", "mdi:play-pause"),
    FieldDesc("volume_policy", UID_VOLUME_POLICY, "Volume Policy", "mdi:tune-variant"),
)

BINARY_SENSORS: tuple[FieldDesc, ...] = (
    FieldDesc("subwoofer_allowed", UID_SUBWOOFER_ALLOWED, "Subwoofer Allowed", "mdi:speaker-wireless"),
    FieldDesc("quiet_mode", UID_QUIET_MODE, "Quiet Mode", "mdi:volume-low"),
    FieldDesc("homepods_should_pause", UID_HOMEPODS_SHOULD_PAUSE, "HomePods Should Pause", "mdi:pause-octagon"),
    FieldDesc("homepods_resume_allowed", UID_HOMEPODS_RESUME_ALLOWED, "HomePods Resume Allowed", "mdi:play-circle"),
    FieldDesc("volume_apply_allowed", UID_VOLUME_APPLY_ALLOWED, "Volume Apply Allowed", "mdi:lock-open-check"),
)


def device_info(entry: ConfigEntry) -> dict[str, Any]:
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": NAME,
        "manufacturer": "Benni",
        "model": "Media Policy (Audio-Owner)",
    }


class MediaPolicyEntity(CoordinatorEntity[MediaPolicyCoordinator]):
    """Gemeinsame Basis: liest aus coordinator.data via FieldDesc."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: MediaPolicyCoordinator, entry: ConfigEntry, desc: FieldDesc
    ) -> None:
        super().__init__(coordinator)
        self._desc = desc
        self._attr_unique_id = unique_id(desc.uid)
        self._attr_name = desc.name
        self._attr_suggested_object_id = unique_id(desc.uid)
        if desc.icon:
            self._attr_icon = desc.icon
        self._attr_device_info = device_info(entry)

    @property
    def _value(self) -> Any:
        return (self.coordinator.data or {}).get(self._desc.key)
