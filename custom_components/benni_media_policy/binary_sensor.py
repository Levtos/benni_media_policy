"""Binary-Sensor-Plattform: Subwoofer-Allowed, Quiet-Mode, HomePods-Pause/Resume,
Volume-Apply-Allowed."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .entities import BINARY_SENSORS, MediaPolicyEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(MediaPolicyBinarySensor(coord, entry, desc) for desc in BINARY_SENSORS)


class MediaPolicyBinarySensor(MediaPolicyEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool:
        return bool(self._value)
