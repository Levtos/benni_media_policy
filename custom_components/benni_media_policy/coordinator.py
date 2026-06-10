"""Media-Policy-Coordinator (Single-Instance, event-driven).

DataUpdateCoordinator ohne Polling: rechnet bei State-Changes der gebundenen
Quell-Entities neu. Profil-Hub + Auto-Bind (options ▶ data ▶ Profil-Map).

Phase 3 (FLEET-34): baut die Inputs aus media_state (Entity-State) + eigenen
Roh-Inputs, hält den persistenten OrchestratorState über die Ticks (RAM, wie
Toolbox) und hydratisiert VolumeSettings aus den Options.

Apply-Gate: `apply_enabled` = globaler Shadow-Kill-Switch (Option, hier);
`volume_apply_allowed` = pro Entscheidung (aus der Logik). Getrennt — der
Apply-Layer (benni_media_apply) prüft beide.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import logic
from .const import (
    BIO_SLEEP_VALUES,
    CONF_ACTIVITY_STATE,
    CONF_APPLY_ENABLED,
    CONF_BIO_STATE,
    CONF_DAY_STATE,
    CONF_DENON,
    CONF_DENON_ACTIVE,
    CONF_ENTERTAINMENT_ACTIVE,
    CONF_HEADSET_ACTIVE,
    CONF_HOMEPODS,
    CONF_HOMEPODS_MUSIC_ENUM,
    CONF_MANUAL_PLAYBACK,
    CONF_MEDIA_CONTEXT,
    CONF_MEDIA_DEVICE,
    CONF_MEDIA_STOP_LATCH,
    CONF_MEDIA_SUBCONTEXT,
    CONF_OPENING,
    CONF_PLANNED_RADIO,
    CONF_PROFILE,
    CONF_QUIET_MODE,
    CONF_VOL_ACTIVE_MIN,
    CONF_VOL_BOOST_OFFSET,
    CONF_VOL_DENON_BASE,
    CONF_VOL_DENON_MAX,
    CONF_VOL_DUCKED_TARGET,
    CONF_VOL_HOMEPODS_BASE,
    CONF_VOL_HOMEPODS_MAX,
    CONF_VOL_OPENING_OFFSET,
    CONF_GRIND_DENON_OFFSET,
    DEFAULT_APPLY_ENABLED,
    DEFAULT_PROFILE,
    DOMAIN,
    PROFILE_PREFILL,
    PROFILES,
    VOL_SETTING_DEFAULTS,
    WATCH_KEYS,
)

_LOGGER = logging.getLogger(__name__)

_TRUE = frozenset({"on", "true", "1", "home", "active", "playing", "open"})


def _bool(s: str | None) -> bool:
    return s is not None and s.lower() in _TRUE


def _opt_bool(s: str | None) -> bool | None:
    if s is None:
        return None
    return s.lower() in _TRUE


def _opt_int(s: str | None) -> int | None:
    if s is None:
        return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


class MediaPolicyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Eine Instanz pro Config-Entry (Single-Instance-Modell)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.entry = entry
        profile = entry.data.get(CONF_PROFILE, DEFAULT_PROFILE)
        self._profile = profile if profile in PROFILES else DEFAULT_PROFILE
        self._unsub_state = None
        self._unsub_time = None
        self._orch_state = logic.OrchestratorState()

    # ----- profile / binding -----
    @property
    def profile(self) -> str:
        return self._profile

    @property
    def _opts(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    @property
    def apply_enabled(self) -> bool:
        return bool(self._opts.get(CONF_APPLY_ENABLED, DEFAULT_APPLY_ENABLED))

    def _entity_id(self, key: str) -> Any:
        """Auto-Bind (core_state-Blaupause): options ▶ data ▶ PROFILE_PREFILL[profile]."""
        return (
            self.entry.options.get(key)
            or self.entry.data.get(key)
            or PROFILE_PREFILL.get(self._profile, {}).get(key)
        )

    def _watched_entities(self) -> list[str]:
        ids: list[str] = []
        for key in WATCH_KEYS:
            val = self._entity_id(key)
            if isinstance(val, str) and val:
                ids.append(val)
            elif isinstance(val, (list, tuple)):
                ids.extend(e for e in val if isinstance(e, str) and e)
        return list(dict.fromkeys(ids))

    def bindings(self) -> dict[str, Any]:
        return {key: self._entity_id(key) for key in WATCH_KEYS}

    def settings(self) -> logic.VolumeSettings:
        """VolumeSettings aus den Options (Default je Key bei fehlend/ungültig)."""
        def _f(key: str) -> float:
            raw = self._opts.get(key, VOL_SETTING_DEFAULTS[key])
            try:
                return float(raw)
            except (TypeError, ValueError):
                return VOL_SETTING_DEFAULTS[key]
        return logic.VolumeSettings(
            homepods_base=_f(CONF_VOL_HOMEPODS_BASE),
            denon_base=_f(CONF_VOL_DENON_BASE),
            ducked_target=_f(CONF_VOL_DUCKED_TARGET),
            homepods_max=_f(CONF_VOL_HOMEPODS_MAX),
            denon_max=_f(CONF_VOL_DENON_MAX),
            active_min=_f(CONF_VOL_ACTIVE_MIN),
            opening_offset=_f(CONF_VOL_OPENING_OFFSET),
            boost_offset=_f(CONF_VOL_BOOST_OFFSET),
            grind_denon_offset=_f(CONF_GRIND_DENON_OFFSET),
        )

    # ----- lifecycle -----
    @callback
    def async_start(self) -> None:
        watched = self._watched_entities()
        if watched:
            self._unsub_state = async_track_state_change_event(
                self.hass, watched, self._on_state_change
            )
            self.entry.async_on_unload(self._unsub_state)
        # Subwoofer-09:00-Floor (FLEET-39): day_state ist solar/saisonal, also
        # feuert kein State-Change zwingend um 09:00 — eigener Wanduhr-Tick.
        self._unsub_time = async_track_time_change(
            self.hass, self._on_time_tick, hour=9, minute=0, second=0
        )
        self.entry.async_on_unload(self._unsub_time)

    @callback
    def _on_state_change(self, _event: Event) -> None:
        self.async_set_updated_data(self._compute())

    @callback
    def _on_time_tick(self, _now) -> None:
        self.async_set_updated_data(self._compute())

    # ----- reads -----
    def _state(self, key: str) -> str | None:
        eid = self._entity_id(key)
        if not eid:
            return None
        st = self.hass.states.get(eid)
        if st is None or st.state in ("unknown", "unavailable"):
            return None
        return st.state

    def _attr(self, key: str, attr: str) -> str | None:
        eid = self._entity_id(key)
        if not eid:
            return None
        st = self.hass.states.get(eid)
        if st is None:
            return None
        val = st.attributes.get(attr)
        return str(val) if val is not None else None

    def _local_minute_of_day(self) -> int:
        now = dt_util.now()   # HA-lokale Zeit (tz-aware)
        return now.hour * 60 + now.minute

    # ----- evaluation -----
    def _build_inputs(self) -> logic.Inputs:
        bio = self._state(CONF_BIO_STATE)
        return logic.Inputs(
            context=self._state(CONF_MEDIA_CONTEXT),
            subcontext=self._state(CONF_MEDIA_SUBCONTEXT),
            device=self._state(CONF_MEDIA_DEVICE),
            entertainment_active=_bool(self._state(CONF_ENTERTAINMENT_ACTIVE)),
            headset_active=_bool(self._state(CONF_HEADSET_ACTIVE)),
            quiet_mode=_bool(self._state(CONF_QUIET_MODE)),
            homepods_state=self._state(CONF_HOMEPODS),
            homepods_configured=bool(self._entity_id(CONF_HOMEPODS)),
            denon_configured=bool(self._entity_id(CONF_DENON)),
            denon_active=_bool(self._state(CONF_DENON_ACTIVE))
            or self._state(CONF_DENON) in ("on", "playing"),
            denon_source=self._attr(CONF_DENON, "source"),
            bio_state=bio,
            bio_sleep=bio is not None and bio.lower() in BIO_SLEEP_VALUES,
            day_state=self._state(CONF_DAY_STATE),
            activity_context=self._state(CONF_ACTIVITY_STATE),
            homepods_music_enum=_opt_int(self._state(CONF_HOMEPODS_MUSIC_ENUM)),
            opening_any_open=_bool(self._state(CONF_OPENING)),
            local_minute_of_day=self._local_minute_of_day(),
            manual_playback_active=_bool(self._state(CONF_MANUAL_PLAYBACK)),
            planned_radio_active=_bool(self._state(CONF_PLANNED_RADIO)),
            media_stop_latch=_opt_bool(self._state(CONF_MEDIA_STOP_LATCH)),
        )

    def _compute(self) -> dict[str, Any]:
        decision, self._orch_state = logic.decide(
            self._build_inputs(), self._orch_state, self.settings()
        )
        self._last_debug = decision.debug()
        return decision.as_dict()

    def debug(self) -> dict[str, Any]:
        return getattr(self, "_last_debug", {})

    async def _async_update_data(self) -> dict[str, Any]:
        return self._compute()

    # ----- service surface -----
    async def async_set_apply_enabled(self, value: bool) -> None:
        """Apply zur Laufzeit an/aus. Schreibt in die Options → Reload-Listener."""
        new_options = {**self.entry.options, CONF_APPLY_ENABLED: bool(value)}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
