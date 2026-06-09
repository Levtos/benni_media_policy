"""Config- und Options-Flow für benni_media_policy.

Single-Instance via unique_id `<domain>_singleton`. Profil-Hub-Schritt zuerst
(benni/eltern), dann Quell-/Target-Bindings (Auto-Prefill aus der Profil-Map),
dann Optionen (Apply gated, Default Shadow). Options-Flow als Menü-Gerüst.

HA erkennt den Config-Flow nur unter `config_flow.py` (Pflicht-Modulname).
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_APPLY_ENABLED,
    CONF_DENON,
    CONF_ENTERTAINMENT_ACTIVE,
    CONF_HEADSET_ACTIVE,
    CONF_HOMEPODS,
    CONF_MEDIA_CONTEXT,
    CONF_MEDIA_DEVICE,
    CONF_PROFILE,
    CONF_SUBWOOFER,
    DEFAULT_APPLY_ENABLED,
    DEFAULT_PROFILE,
    DOMAIN,
    NAME,
    PROFILE_LABELS,
    PROFILE_PREFILL,
    PROFILES,
    SINGLETON_UNIQUE_ID,
    WATCH_KEYS,
)

# --- Selektoren (ungefiltert) ---
_ENTITY = selector.EntitySelector(selector.EntitySelectorConfig())
_PLAYERS = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="media_player", multiple=True)
)
_PLAYER = selector.EntitySelector(selector.EntitySelectorConfig(domain="media_player"))
_BOOL = selector.BooleanSelector()

SELECTORS: dict[str, Any] = {
    CONF_MEDIA_CONTEXT: _ENTITY,
    CONF_MEDIA_DEVICE: _ENTITY,
    CONF_ENTERTAINMENT_ACTIVE: _ENTITY,
    CONF_HEADSET_ACTIVE: _ENTITY,
    CONF_HOMEPODS: _PLAYERS,
    CONF_DENON: _PLAYER,
    CONF_SUBWOOFER: _ENTITY,
}

OPTIONS_MENU = ("sources", "options")


def _profile_schema(default: str = DEFAULT_PROFILE) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_PROFILE, default=default): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value=p, label=PROFILE_LABELS[p])
                    for p in PROFILES
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
    })


def _exists(hass, eid: str) -> bool:
    return bool(eid) and hass.states.get(eid) is not None


def _sources_schema(profile: str, defaults: dict[str, Any], hass) -> vol.Schema:
    """Quell-/Target-Bindings. Auto-Prefill aus der Profil-Map (Override ▶ Map ▶
    leer), jeweils nur wenn die Entity in HA existiert."""
    prefill = PROFILE_PREFILL.get(profile, {})
    fields: dict[Any, Any] = {}
    for key in WATCH_KEYS + (CONF_SUBWOOFER,):
        default = defaults.get(key)
        if default in (None, "", []):
            cand = prefill.get(key)
            if isinstance(cand, str) and _exists(hass, cand):
                default = cand
            elif isinstance(cand, (list, tuple)):
                present = [e for e in cand if _exists(hass, e)]
                default = present or None
        if default in (None, "", []):
            fields[vol.Optional(key)] = SELECTORS[key]
        else:
            fields[vol.Optional(key, default=default)] = SELECTORS[key]
    return vol.Schema(fields)


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Optional(
            CONF_APPLY_ENABLED,
            default=bool(defaults.get(CONF_APPLY_ENABLED, DEFAULT_APPLY_ENABLED)),
        ): _BOOL,
    })


class MediaPolicyConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        await self.async_set_unique_id(SINGLETON_UNIQUE_ID)
        self._abort_if_unique_id_configured()
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            profile = user_input.get(CONF_PROFILE, DEFAULT_PROFILE)
            self._data[CONF_PROFILE] = profile if profile in PROFILES else DEFAULT_PROFILE
            return await self.async_step_sources()
        return self.async_show_form(step_id="user", data_schema=_profile_schema())

    async def async_step_sources(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_options()
        return self.async_show_form(
            step_id="sources",
            data_schema=_sources_schema(self._data[CONF_PROFILE], self._data, self.hass),
        )

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title=f"{NAME} ({PROFILE_LABELS[self._data[CONF_PROFILE]]})",
                data=self._data,
            )
        return self.async_show_form(
            step_id="options", data_schema=_options_schema(self._data)
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return MediaPolicyOptionsFlow(entry)


class MediaPolicyOptionsFlow(OptionsFlow):
    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    def _defaults(self) -> dict[str, Any]:
        return {**self._entry.data, **self._entry.options}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(step_id="init", menu_options=list(OPTIONS_MENU))

    async def async_step_sources(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data={**self._entry.options, **user_input})
        defaults = self._defaults()
        profile = defaults.get(CONF_PROFILE, DEFAULT_PROFILE)
        return self.async_show_form(
            step_id="sources",
            data_schema=_sources_schema(profile, defaults, self.hass),
        )

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data={**self._entry.options, **user_input})
        return self.async_show_form(
            step_id="options", data_schema=_options_schema(self._defaults())
        )
