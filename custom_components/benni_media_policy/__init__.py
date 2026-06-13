"""benni_media_policy — L2 Policy (eigene HACS-Integration).

Single-Instance: ein Config-Entry (Profil benni/eltern) entscheidet Audio-Owner +
Volume/Ducking/Subwoofer. Konsumiert benni_media_state über Entity-State (kein
Import). Apply ist gated (Shadow-safe). Step-1-Scaffold.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN, LEGACY_ENTITY_MAP
from .coordinator import MediaPolicyCoordinator
from .view import async_remove_view, async_setup_view
from .websocket_api import async_setup_websocket_api

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]
_WS_FLAG = "_ws_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coord = MediaPolicyCoordinator(hass, entry)
    await coord.async_config_entry_first_refresh()
    coord.async_start()

    data = hass.data.setdefault(DOMAIN, {})
    data[entry.entry_id] = {DATA_COORDINATOR: coord}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await async_setup_view(hass)
    if not data.get(_WS_FLAG):
        async_setup_websocket_api(hass)
        data[_WS_FLAG] = True

    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate retired entity IDs from earlier prefills."""
    changed = False
    data = dict(entry.data)
    options = dict(entry.options)
    for target in (data, options):
        for key, value in list(target.items()):
            if isinstance(value, str) and value in LEGACY_ENTITY_MAP:
                target[key] = LEGACY_ENTITY_MAP[value]
                changed = True

    if changed or entry.version < 2:
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            options=options,
            version=2,
        )
        _LOGGER.info("Migrated benni_media_policy entity bindings")
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not any(
            isinstance(b, dict) and DATA_COORDINATOR in b
            for b in hass.data[DOMAIN].values()
        ):
            async_remove_view(hass)
    return unloaded
