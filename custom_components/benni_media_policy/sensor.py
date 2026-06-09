"""Sensor-Plattform: Volume-Targets, Audio-Owner, Action, Volume-Policy."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .entities import SENSORS, MediaPolicyEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(MediaPolicySensor(coord, entry, desc) for desc in SENSORS)


class MediaPolicySensor(MediaPolicyEntity, SensorEntity):
    def __init__(self, coord, entry, desc):
        super().__init__(coord, entry, desc)
        if desc.unit:
            self._attr_native_unit_of_measurement = desc.unit

    @property
    def native_value(self):
        return self._value
