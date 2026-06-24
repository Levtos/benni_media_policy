"""WebSocket-API für das Media-Policy-Panel.

`benni_media_policy/get_status` liefert `coordinator.data` als dict (plus Profil,
Bindings, apply_enabled) — die rohe Debug-Maske für das Vanilla-Panel.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    PROFILE_LABELS,
    WS_GET_MATRIX,
    WS_GET_STATUS,
    WS_NUDGE_VOLUME,
    WS_RESET_BOOST,
    WS_RESET_MATRIX,
    WS_RESET_NUDGE,
    WS_SET_MATRIX,
)


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

    @websocket_api.websocket_command({vol.Required("type"): WS_GET_MATRIX})
    @websocket_api.async_response
    async def ws_get_matrix(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Media Policy not loaded")
            return
        connection.send_result(msg["id"], coord.matrix())

    @websocket_api.websocket_command(
        {
            vol.Required("type"): WS_SET_MATRIX,
            vol.Required("patch"): dict,
        }
    )
    @websocket_api.async_response
    async def ws_set_matrix(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Media Policy not loaded")
            return
        result = await coord.async_set_matrix(msg["patch"])
        connection.send_result(msg["id"], result)

    @websocket_api.websocket_command({vol.Required("type"): WS_RESET_MATRIX})
    @websocket_api.async_response
    async def ws_reset_matrix(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Media Policy not loaded")
            return
        result = await coord.async_reset_matrix()
        connection.send_result(msg["id"], result)

    @websocket_api.websocket_command(
        {
            vol.Required("type"): WS_NUDGE_VOLUME,
            vol.Required("delta"): vol.Coerce(float),
        }
    )
    @websocket_api.async_response
    async def ws_nudge_volume(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Media Policy not loaded")
            return
        value = coord.async_nudge_volume(msg["delta"])
        connection.send_result(msg["id"], {"manual_nudge": value})

    @websocket_api.websocket_command({vol.Required("type"): WS_RESET_NUDGE})
    @websocket_api.async_response
    async def ws_reset_nudge(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Media Policy not loaded")
            return
        coord.async_reset_nudge()
        connection.send_result(msg["id"], {"manual_nudge": 0.0})

    @websocket_api.websocket_command({vol.Required("type"): WS_RESET_BOOST})
    @websocket_api.async_response
    async def ws_reset_boost(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Media Policy not loaded")
            return
        coord.async_reset_boost()
        connection.send_result(msg["id"], {"boost_suppressed": True})

    websocket_api.async_register_command(hass, ws_get_status)
    websocket_api.async_register_command(hass, ws_get_matrix)
    websocket_api.async_register_command(hass, ws_set_matrix)
    websocket_api.async_register_command(hass, ws_reset_matrix)
    websocket_api.async_register_command(hass, ws_nudge_volume)
    websocket_api.async_register_command(hass, ws_reset_nudge)
    websocket_api.async_register_command(hass, ws_reset_boost)
