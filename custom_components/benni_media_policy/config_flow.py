"""Config- und Options-Flow für benni_media_policy.

Profil-Mechanik 1:1 aus benni_core_state (gelockte Blaupause):
- `user`: Profil-SelectSelector (benni/eltern).
- `entities`: Quell-/Target-Slots (media_state-Eingänge + eigene Geräte/Inputs),
  vorbefüllt mit der Profil-Map; gespeichert werden nur Abweichungen.
- `options`: Apply-Gate (Shadow) + Volume-Settings.
- Single-Instance; Auto-Bind lebt im Coordinator.

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
    CONF_GRIND_DENON_OFFSET,
    CONF_GRIND_HOMEPODS_OFFSET,
    CONF_HOMEPODS,
    CONF_PRIVATE_DENON_CAP,
    CONF_PROFILE,
    CONF_VOL_ACTIVE_MIN,
    CONF_VOL_BOOST_OFFSET,
    CONF_VOL_DENON_BASE,
    CONF_VOL_DENON_MAX,
    CONF_VOL_DUCKED_TARGET,
    CONF_VOL_HOMEPODS_BASE,
    CONF_VOL_HOMEPODS_MAX,
    CONF_VOL_OPENING_OFFSET_DENON,
    CONF_VOL_OPENING_OFFSET_HOMEPODS,
    DEFAULT_APPLY_ENABLED,
    DEFAULT_PROFILE,
    DOMAIN,
    ENTITY_SLOT_KEYS,
    LEGACY_ENTITY_MAP,
    NAME,
    PROFILE_LABELS,
    PROFILE_PREFILL,
    PROFILES,
    VOL_SETTING_DEFAULTS,
)

# --- Selektoren ---
_ENTITY = selector.EntitySelector(selector.EntitySelectorConfig())
_PLAYER = selector.EntitySelector(selector.EntitySelectorConfig(domain="media_player"))
_BOOL = selector.BooleanSelector()
_PLAYER_KEYS = (CONF_HOMEPODS, CONF_DENON)

SELECTORS: dict[str, Any] = {
    key: (_PLAYER if key in _PLAYER_KEYS else _ENTITY) for key in ENTITY_SLOT_KEYS
}

# Volume-Settings (signierte Floats; Offsets dürfen negativ sein).
# control#3: Fenster-/Grind-Offsets je Gerät + Private-Time-Denon-Cap editierbar.
_VOL_KEYS: tuple[str, ...] = (
    CONF_VOL_HOMEPODS_BASE, CONF_VOL_DENON_BASE, CONF_VOL_DUCKED_TARGET,
    CONF_VOL_HOMEPODS_MAX, CONF_VOL_DENON_MAX, CONF_VOL_ACTIVE_MIN,
    CONF_VOL_OPENING_OFFSET_HOMEPODS, CONF_VOL_OPENING_OFFSET_DENON,
    CONF_VOL_BOOST_OFFSET,
    CONF_GRIND_HOMEPODS_OFFSET, CONF_GRIND_DENON_OFFSET,
    CONF_PRIVATE_DENON_CAP,
)
_VOL_COERCE = vol.All(vol.Coerce(float), vol.Range(min=-1.0, max=1.0))


def _normalize_entity_id(value: Any) -> Any:
    if isinstance(value, str):
        return LEGACY_ENTITY_MAP.get(value, value)
    return value


def _entities_schema(defaults: dict[str, Any]) -> vol.Schema:
    fields: dict[Any, Any] = {}
    for key in ENTITY_SLOT_KEYS:
        d = defaults.get(key)
        marker = vol.Optional(key, default=d) if d else vol.Optional(key)
        fields[marker] = SELECTORS[key]
    return vol.Schema(fields)


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    fields: dict[Any, Any] = {
        vol.Optional(
            CONF_APPLY_ENABLED,
            default=bool(defaults.get(CONF_APPLY_ENABLED, DEFAULT_APPLY_ENABLED)),
        ): _BOOL,
    }
    for key in _VOL_KEYS:
        fields[vol.Optional(
            key, default=float(defaults.get(key, VOL_SETTING_DEFAULTS[key]))
        )] = _VOL_COERCE
    return vol.Schema(fields)


def _entity_overrides(profile: str, user_input: dict[str, Any]) -> dict[str, Any]:
    """Nur echte Abweichungen vom Profil-Map als Override speichern."""
    code = PROFILE_PREFILL.get(profile, {})
    out: dict[str, Any] = {}
    for key in ENTITY_SLOT_KEYS:
        v = _normalize_entity_id(user_input.get(key))
        if v and v != code.get(key):
            out[key] = v
    return out


def _override_or_map(profile: str, data: dict[str, Any]) -> dict[str, Any]:
    code = PROFILE_PREFILL.get(profile, {})
    out: dict[str, Any] = {}
    for key in ENTITY_SLOT_KEYS:
        v = _normalize_entity_id(data.get(key)) or code.get(key)
        if v:
            out[key] = v
    return out


def _profile_schema(default: str) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_PROFILE, default=default): selector.SelectSelector(
            selector.SelectSelectorConfig(
                mode=selector.SelectSelectorMode.LIST,
                options=[
                    selector.SelectOptionDict(value=p, label=PROFILE_LABELS[p])
                    for p in PROFILES
                ],
            )
        )
    })


class MediaPolicyConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 4

    def __init__(self) -> None:
        self._profile: str = DEFAULT_PROFILE
        self._entities: dict[str, Any] = {}

    def _prefill_defaults(self) -> dict[str, Any]:
        prefill = PROFILE_PREFILL.get(self._profile, {})
        return {
            key: eid
            for key, eid in prefill.items()
            if isinstance(eid, str) and self.hass.states.get(eid) is not None
        }

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=_profile_schema(DEFAULT_PROFILE),
            )
        self._profile = user_input[CONF_PROFILE]
        return await self.async_step_entities()

    async def async_step_entities(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="entities", data_schema=_entities_schema(self._prefill_defaults()),
            )
        self._entities = _entity_overrides(self._profile, user_input)
        return await self.async_step_options()

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="options", data_schema=_options_schema({}),
            )
        return self.async_create_entry(
            title=f"{NAME} ({PROFILE_LABELS[self._profile]})",
            data={CONF_PROFILE: self._profile, **self._entities},
            options=user_input,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MediaPolicyOptionsFlow()


class MediaPolicyOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(step_id="init", menu_options=["entities", "options"])

    async def async_step_entities(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        profile = self.config_entry.data.get(CONF_PROFILE, DEFAULT_PROFILE)
        if user_input is not None:
            overrides = _entity_overrides(profile, user_input)
            new_data = {
                k: v for k, v in self.config_entry.data.items()
                if k not in ENTITY_SLOT_KEYS
            }
            new_data.update(overrides)
            new_data[CONF_PROFILE] = profile
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data=dict(self.config_entry.options))
        return self.async_show_form(
            step_id="entities",
            data_schema=_entities_schema(_override_or_map(profile, self.config_entry.data)),
        )

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="options", data_schema=_options_schema(self.config_entry.options),
        )
