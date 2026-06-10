"""WebSocket-API für das Media-Policy-Panel.

`benni_media_policy/get_status` liefert `coordinator.data` als dict (plus Profil,
Bindings, apply_enabled) — die rohe Debug-Maske für das Vanilla-Panel.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN, PROFILE_LABELS, WS_GET_STATUS


def _coordinator(hass: HomeAssistant):
    bucket = hass.data.get(DOMAIN) or {}
    for entry_bucket in bucket.values():
        if isinstance(entry_bucket, dict) and DATA_COORDINATOR in entry_bucket:
            return entry_bucket[DATA_COORDINATOR]
    return None


def _status(coord) -> dict[str, Any]:
    return {
        "profile": coord.profile,
        "profile_label": PROFILE_LABELS.get(coord.profile, coord.profile),
        "apply_enabled": coord.apply_enabled,
        "bindings": coord.bindings(),
        "data": dict(coord.data or {}),
        "debug": coord.debug(),
    }


def async_setup_websocket_api(hass: HomeAssistant) -> None:
    @websocket_api.websocket_command({vol.Required("type"): WS_GET_STATUS})
    @websocket_api.async_response
    async def ws_get_status(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Media Policy not loaded")
            return
        connection.send_result(msg["id"], _status(coord))

    websocket_api.async_register_command(hass, ws_get_status)
