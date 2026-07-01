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
    AUDIO_SCENARIO_LABELS,
    BIO_SLEEP_VALUES,
    BOOST_BLOCK_ACTIVITIES,
    CONF_ACTIVITY_STATE,
    CONF_APPLY_ENABLED,
    CONF_AWAY_GATE,
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
    CONF_PRESENCE_STATE,
    CONF_PROFILE,
    CONF_QUIET_MODE,
    CONF_RADIO_STATION,
    CONF_WAKE_NEEDED,
    CONF_VOL_ACTIVE_MIN,
    CONF_VOL_BOOST_OFFSET,
    CONF_VOL_DENON_BASE,
    CONF_VOL_DENON_MAX,
    CONF_VOL_DUCKED_TARGET,
    CONF_VOL_HOMEPODS_BASE,
    CONF_VOL_HOMEPODS_MAX,
    CONF_VOL_OPENING_OFFSET,
    CONF_GRIND_DENON_OFFSET,
    CORE_OPENINGS_MASTER_ENTITY,
    CORE_OPENINGS_MEDIA_ATTRIBUTE,
    DAY_PHASES,
    DEFAULT_APPLY_ENABLED,
    DEFAULT_PROFILE,
    DENON_BASELINES,
    DOMAIN,
    HOMEPODS_BASELINES,
    MUSIC_ENUM_BOOST,
    NUDGE_MAX,
    NUDGE_MIN,
    PROFILE_PREFILL,
    PROFILES,
    VOL_SETTING_DEFAULTS,
    WATCH_KEYS,
)
from .storage import make_matrix_store

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
        # R21/R22 Laufzeit-Steuerung (RAM, fail-safe: Reset bei HA-Neustart).
        self._manual_nudge: float = 0.0
        self._boost_suppressed: bool = False
        self._boost_suppress_track: str | None = None  # Track, für den R22 gilt
        # FLEET-102 Stage B: persistenter Volume-Matrix-Override (Store).
        self._matrix_store = make_matrix_store(hass, entry.entry_id)
        self._matrix_override: dict[str, Any] = {}

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
        """VolumeSettings (= Volume-Matrix): Skalare aus den Options, Tabellen
        (base/scenario/activity) aus dem persistenten Store-Override über die
        Defaults gemerged (Stage B)."""
        def _f(key: str) -> float:
            raw = self._opts.get(key, VOL_SETTING_DEFAULTS[key])
            try:
                return float(raw)
            except (TypeError, ValueError):
                return VOL_SETTING_DEFAULTS[key]

        ov = self._matrix_override or {}
        def _tbl(dim: str, device: str, default: dict) -> dict:
            sub = (ov.get(dim) or {}).get(device) or {}
            merged = dict(default)
            for k, v in sub.items():
                try:
                    merged[k] = round(float(v), 3)
                except (TypeError, ValueError):
                    continue
            return merged

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
            base_homepods=_tbl("base", "homepods", HOMEPODS_BASELINES),
            base_denon=_tbl("base", "denon", DENON_BASELINES),
            scenario_off_homepods=_tbl("scenario_off", "homepods", {}),
            scenario_off_denon=_tbl("scenario_off", "denon", {}),
            activity_off_homepods=_tbl("activity_off", "homepods", {}),
            activity_off_denon=_tbl("activity_off", "denon", {}),
        )

    def matrix(self) -> dict[str, Any]:
        """FLEET-102: effektive Volume-Matrix + Kataloge + persistenter Override.
        Quelle = settings() (Config-Skalare + Default-Tabellen ⊕ Store-Override).
        `catalog` listet die editierbaren Zeilen (Tagesphasen/Szenarien/Aktivitäten);
        Aktivitäten sind offen-keyed (Enum lebt in core_state) — bekannte als Start."""
        s = self.settings()
        return {
            "catalog": {
                "dayphases": list(DAY_PHASES),
                "scenarios": list(AUDIO_SCENARIO_LABELS.keys()),
                "scenario_labels": dict(AUDIO_SCENARIO_LABELS),
                "activities": list(BOOST_BLOCK_ACTIVITIES),
                "devices": ["homepods", "denon"],
            },
            "base": {"homepods": dict(s.base_homepods), "denon": dict(s.base_denon)},
            "scenario_off": {
                "homepods": dict(s.scenario_off_homepods),
                "denon": dict(s.scenario_off_denon),
            },
            "activity_off": {
                "homepods": dict(s.activity_off_homepods),
                "denon": dict(s.activity_off_denon),
            },
            "scalars": {
                "homepods_base": s.homepods_base, "denon_base": s.denon_base,
                "ducked_target": s.ducked_target,
                "homepods_max": s.homepods_max, "denon_max": s.denon_max,
                "active_min": s.active_min,
                "opening_offset": s.opening_offset, "boost_offset": s.boost_offset,
                "grind_denon_offset": s.grind_denon_offset,
            },
            "override": self._matrix_override or {},
        }

    # ----- FLEET-102 Stage B: Matrix-Persistenz (Store) -----
    async def async_load_matrix(self) -> None:
        """Override aus dem Store laden (Setup). Fehlt/kaputt → {} (= Defaults)."""
        try:
            stored = await self._matrix_store.async_load()
        except Exception:  # noqa: BLE001 — fail-safe auf Defaults
            stored = None
        self._matrix_override = stored if isinstance(stored, dict) else {}

    async def async_set_matrix(self, patch: dict[str, Any]) -> dict[str, Any]:
        """Partiellen Matrix-Override mergen, persistieren, neu rechnen. Nur die
        Tabellen-Dimensionen (base/scenario_off/activity_off) × Gerät; Werte als
        float geclamped auf [0,1] (base) bzw. [-1,1] (offsets). Gibt die neue
        effektive Matrix zurück. Merge/Clamp = pure logic.apply_matrix_patch."""
        self._matrix_override = logic.apply_matrix_patch(
            self._matrix_override or {}, patch if isinstance(patch, dict) else {}
        )
        await self._matrix_store.async_save(self._matrix_override)
        self.async_set_updated_data(self._compute())
        return self.matrix()

    async def async_reset_matrix(self) -> dict[str, Any]:
        """Kompletten Override verwerfen → zurück auf Code-Defaults."""
        self._matrix_override = {}
        await self._matrix_store.async_save({})
        self.async_set_updated_data(self._compute())
        return self.matrix()

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

    def _homepods_track(self) -> str | None:
        """Track-Identität des HomePods-Players (R22 Track-Change-Erkennung)."""
        return self._attr(CONF_HOMEPODS, "media_content_id") or self._attr(
            CONF_HOMEPODS, "media_title"
        )

    def _opening_any_not_closed(self) -> bool:
        if self._entity_id(CONF_OPENING) == CORE_OPENINGS_MASTER_ENTITY:
            return _bool(self._attr(CONF_OPENING, CORE_OPENINGS_MEDIA_ATTRIBUTE))
        return _bool(self._state(CONF_OPENING))

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
            presence_state=self._state(CONF_PRESENCE_STATE),
            presence_degraded=bool(self._entity_id(CONF_PRESENCE_STATE))
            and self._state(CONF_PRESENCE_STATE) is None,
            away_gate=_opt_bool(self._state(CONF_AWAY_GATE)),
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
            opening_any_open=self._opening_any_not_closed(),
            local_minute_of_day=self._local_minute_of_day(),
            manual_playback_active=_bool(self._state(CONF_MANUAL_PLAYBACK)),
            planned_radio_active=_bool(self._state(CONF_PLANNED_RADIO)),
            radio_station=self._state(CONF_RADIO_STATION),
            media_stop_latch=_opt_bool(self._state(CONF_MEDIA_STOP_LATCH)),
            wake_needed=_opt_bool(self._state(CONF_WAKE_NEEDED)),
            manual_nudge=self._manual_nudge,
            boost_suppressed=self._boost_suppressed,
        )

    def _compute(self) -> dict[str, Any]:
        # R22: Boost-Reset gilt nur für den aktuell geboosteten Track. Sperre hebt
        # sich auf bei (a) Trackwechsel (media_content_id/title ändert sich) oder
        # (b) Verlassen des Boost-Enums — fail-safe, falls der Player keinen Titel
        # liefert.
        if self._boost_suppressed:
            track = self._homepods_track()
            enum_left = _opt_int(self._state(CONF_HOMEPODS_MUSIC_ENUM)) != MUSIC_ENUM_BOOST
            track_changed = track != self._boost_suppress_track
            if enum_left or track_changed:
                self._boost_suppressed = False
                self._boost_suppress_track = None
        decision, self._orch_state = logic.decide(
            self._build_inputs(), self._orch_state, self.settings()
        )
        self._last_debug = decision.debug()
        return decision.as_dict()

    def debug(self) -> dict[str, Any]:
        return getattr(self, "_last_debug", {})

    def status(self) -> dict[str, Any]:
        """Reicher Snapshot fürs Cockpit (benni_media-Umbrella bevorzugt status()):
        Decision + Reasons (mit Severity) + Volume-Formel-Breakdown. Read-only."""
        dbg = dict(getattr(self, "_last_debug", {}) or {})
        if not dbg:
            return {}
        inp = self._build_inputs()
        dbg["volume_formula"] = logic.volume_breakdown(
            inp, dbg.get("audio_owner", "none"), bool(dbg.get("is_grind", False)),
            self.settings(), dbg.get("audio_scenario"),
        )
        dbg["reasons"] = logic.structured_reasons(dbg)
        dbg["bindings"] = self.bindings()
        dbg["nudge"] = {
            "manual_nudge": round(self._manual_nudge, 3),
            "boost_suppressed": self._boost_suppressed,
            "min": NUDGE_MIN,
            "max": NUDGE_MAX,
            "boost_active": bool(dbg.get("track_boost_applied", False)),
        }
        return dbg

    async def _async_update_data(self) -> dict[str, Any]:
        return self._compute()

    # ----- service surface -----
    async def async_set_apply_enabled(self, value: bool) -> None:
        """Apply zur Laufzeit an/aus. Schreibt in die Options → Reload-Listener."""
        new_options = {**self.entry.options, CONF_APPLY_ENABLED: bool(value)}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)

    @callback
    def async_nudge_volume(self, delta: float) -> float:
        """R21: manuellen Nudge-Offset um delta verschieben (geklammert)."""
        self._manual_nudge = round(
            min(NUDGE_MAX, max(NUDGE_MIN, self._manual_nudge + float(delta))), 3
        )
        self.async_set_updated_data(self._compute())
        return self._manual_nudge

    @callback
    def async_reset_nudge(self) -> None:
        """R21: Nudge-Offset auf 0 zurücksetzen."""
        self._manual_nudge = 0.0
        self.async_set_updated_data(self._compute())

    @callback
    def async_reset_boost(self) -> None:
        """R22: Track-Boost für den aktuell laufenden Track unterdrücken."""
        self._boost_suppressed = True
        self._boost_suppress_track = self._homepods_track()
        self.async_set_updated_data(self._compute())
