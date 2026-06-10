"""Konstanten von benni_media_policy (L2 Policy / Media-Gehirn).

Eigenständige HA-Integration. Audio-Owner (pause/resume/radio) + Volume/Ducking/
Subwoofer. Konsumiert benni_media_state AUSSCHLIESSLICH über HA-Entity-State —
kein Cross-Modul-Python-Import (const wird KOPIERT, nicht importiert).

Phase 3 (FLEET-34): Lift von orchestrator.py + volume_orchestrator.py +
evaluate_subwoofer/_denon_audio_path aus bennis_toolbox/benni_media_context.
Owner-Bestimmung aus media_state-Context (kein Roh-Re-Derive). Pflicht-Delta
GRIND (Lastenheft v3.1 KH-5/R15/R16/§6): bei gaming_grind spielen HomePods
weiter (kein Pause), HomePods auf Normal-Niveau, Denon mit negativem Offset
(Kulisse), Subwoofer immer aus.

Apply-Gate-Doku: `apply_enabled` = globaler Shadow-Kill-Switch (Option);
`volume_apply_allowed` = pro Entscheidung (aus der Volume-Logik). Klar getrennt —
der Apply-Layer (benni_media_apply, FLEET-40) prüft BEIDE.

Lastenheft: einhornzentrale/docs/lastenhefte/reviewed/media/ (v3.1)
"""
from __future__ import annotations

from typing import Any, Final

DOMAIN: Final[str] = "benni_media_policy"
MODULE_ID: Final[str] = "media_policy"
NAME: Final[str] = "Benni Media Policy"

DATA_COORDINATOR: Final[str] = "coordinator"

STORAGE_VERSION: Final[int] = 1


def unique_id(entry_id: str, suffix: str) -> str:
    """Domain- + entry-scoped unique_id (core_state-Blaupause, kollisionsfrei)."""
    return f"{DOMAIN}_{entry_id}_{suffix}"


# --------------------------------------------------------------------------- #
# Profil-Hub (benni / eltern) + Auto-Bind: options ▶ data ▶ Profil-Map ▶ leer.
# --------------------------------------------------------------------------- #
CONF_PROFILE: Final[str] = "profile"
PROFILE_BENNI: Final[str] = "benni"
PROFILE_ELTERN: Final[str] = "eltern"
PROFILES: Final[list[str]] = [PROFILE_BENNI, PROFILE_ELTERN]
DEFAULT_PROFILE: Final[str] = PROFILE_BENNI
PROFILE_LABELS: Final[dict[str, str]] = {PROFILE_BENNI: "Benni", PROFILE_ELTERN: "Eltern"}

# --------------------------------------------------------------------------- #
# Context / Subcontext / Device (KOPIE aus media_context-Contract, kein Import).
# --------------------------------------------------------------------------- #
CTX_IDLE: Final = "idle"
CTX_TV: Final = "tv"
CTX_STREAMING: Final = "streaming"
CTX_GAMING: Final = "gaming"
CTX_PRIVATE: Final = "private_time"

SUB_GAME_GRIND: Final = "gaming_grind"

DEV_DENON: Final = "denon"

# --------------------------------------------------------------------------- #
# Audio-Owner / Action (Orchestrator-Lift).
# --------------------------------------------------------------------------- #
AUDIO_OWNER_NONE: Final = "none"
AUDIO_OWNER_HOMEPODS: Final = "homepods"
AUDIO_OWNER_TV_DENON: Final = "tv_denon"
AUDIO_OWNER_GAMING: Final = "gaming_stack"
AUDIO_OWNER_PRIVATE: Final = "private_stack"

ACTION_NONE: Final = "none"
ACTION_PAUSE: Final = "pause_homepods"
ACTION_RESUME: Final = "resume_homepods"
ACTION_START_RADIO: Final = "start_radio"

RESUME_MODE_MANUAL: Final = "manual"
RESUME_MODE_RADIO: Final = "radio"

BIO_SLEEP_VALUES: Final = ("sleep", "sleeping", "asleep")

# --------------------------------------------------------------------------- #
# Volume-Policy-Zustände (volume_orchestrator-Lift).
# --------------------------------------------------------------------------- #
VOL_POLICY_IDLE: Final = "idle"
VOL_POLICY_MEDIA: Final = "media"
VOL_POLICY_DUCKED: Final = "ducked"
VOL_POLICY_MUTED: Final = "muted"
VOL_POLICY_BLOCKED: Final = "blocked"

# Day-State-Werte mit Volume-Offset (sonst 0).
DAY_NIGHT_VALUES: Final = ("night", "late_night", "early_night")
DAY_EDGE_VALUES: Final = ("early_morning", "late_evening")

# --------------------------------------------------------------------------- #
# Config-Keys — Eingänge aus benni_media_state (via Entity-State).
# --------------------------------------------------------------------------- #
CONF_MEDIA_CONTEXT: Final[str] = "media_context_entity"
CONF_MEDIA_SUBCONTEXT: Final[str] = "media_subcontext_entity"
CONF_MEDIA_DEVICE: Final[str] = "media_device_entity"
CONF_ENTERTAINMENT_ACTIVE: Final[str] = "entertainment_active_entity"
CONF_HEADSET_ACTIVE: Final[str] = "headset_active_entity"
CONF_QUIET_MODE: Final[str] = "quiet_mode_entity"

# Eigene Policy-Inputs (Roh-/Template-Entitäten — core_devices-Atomics später).
CONF_HOMEPODS: Final[str] = "homepods_player_entity"   # MA-Gruppe (1 Player)
CONF_DENON: Final[str] = "denon_player_entity"
CONF_DENON_ACTIVE: Final[str] = "denon_active_entity"  # Plug-Active (denon_audio_path)
CONF_SUBWOOFER: Final[str] = "subwoofer_entity"        # nur Target (Apply-Layer)
CONF_BIO_STATE: Final[str] = "bio_state_entity"
CONF_DAY_STATE: Final[str] = "day_state_entity"
CONF_OPENING: Final[str] = "opening_any_open_entity"   # Fenster/Tür offen → Offset
CONF_MANUAL_PLAYBACK: Final[str] = "manual_playback_entity"
CONF_PLANNED_RADIO: Final[str] = "planned_radio_entity"
CONF_MEDIA_STOP_LATCH: Final[str] = "media_stop_latch_entity"

# Keys, deren gebundene Entities der Coordinator beobachtet (event-driven).
WATCH_KEYS: Final[tuple[str, ...]] = (
    CONF_MEDIA_CONTEXT, CONF_MEDIA_SUBCONTEXT, CONF_MEDIA_DEVICE,
    CONF_ENTERTAINMENT_ACTIVE, CONF_HEADSET_ACTIVE, CONF_QUIET_MODE,
    CONF_HOMEPODS, CONF_DENON, CONF_DENON_ACTIVE,
    CONF_BIO_STATE, CONF_DAY_STATE, CONF_OPENING,
    CONF_MANUAL_PLAYBACK, CONF_PLANNED_RADIO, CONF_MEDIA_STOP_LATCH,
)

# Subwoofer ist nur ein Apply-Target (kein beobachteter Input).
ENTITY_SLOT_KEYS: Final[tuple[str, ...]] = WATCH_KEYS + (CONF_SUBWOOFER,)

# --------------------------------------------------------------------------- #
# Profil-Map (Auto-Bind). benni: media_state-Entities (Konsum-Vertrag) + Live-IDs
# der Einhornzentrale (aus produktivem Toolbox-Entry übernommen). Roh-/Template-
# Entitäten — core_devices-Atomics-Migration ist ein separater späterer Step.
# eltern leer (Anlage existiert noch nicht). Existenz-Filter regelt Fehlendes.
# --------------------------------------------------------------------------- #
PROFILE_PREFILL: Final[dict[str, dict[str, Any]]] = {
    PROFILE_BENNI: {
        # aus media_state (Feeder):
        CONF_MEDIA_CONTEXT: "sensor.benni_media_state_media_context",
        CONF_MEDIA_SUBCONTEXT: "sensor.benni_media_state_media_subcontext",
        CONF_MEDIA_DEVICE: "sensor.benni_media_state_media_device",
        CONF_ENTERTAINMENT_ACTIVE: "binary_sensor.benni_media_state_entertainment_active",
        CONF_HEADSET_ACTIVE: "binary_sensor.benni_media_state_headset_active",
        CONF_QUIET_MODE: "binary_sensor.benni_media_state_quiet_mode",
        # eigene Geräte/Inputs:
        CONF_HOMEPODS: "media_player.living_homepods_ma_group",
        CONF_DENON: "media_player.living_denon",
        CONF_DENON_ACTIVE: "binary_sensor.living_denon_plug_power_active_atomic",
        CONF_BIO_STATE: "sensor.benni_core_state_bio_state",
        CONF_DAY_STATE: "sensor.benni_core_day_state",
        CONF_OPENING: "binary_sensor.opening_any_open_combined",
        CONF_MANUAL_PLAYBACK: "binary_sensor.media_manual_playback_active",
        CONF_PLANNED_RADIO: "binary_sensor.media_radio_playing_planned_station",
    },
    PROFILE_ELTERN: {},
}

# --------------------------------------------------------------------------- #
# Options — Apply-Gate + Volume-Settings (volume_orchestrator-Lift + GRIND).
# --------------------------------------------------------------------------- #
CONF_APPLY_ENABLED: Final[str] = "apply_enabled"
DEFAULT_APPLY_ENABLED: Final[bool] = False   # Shadow-safe out of the box.

CONF_VOL_HOMEPODS_BASE: Final[str] = "volume_homepods_base"
CONF_VOL_DENON_BASE: Final[str] = "volume_denon_base"
CONF_VOL_DUCKED_TARGET: Final[str] = "volume_ducked_target"
CONF_VOL_HOMEPODS_MAX: Final[str] = "volume_homepods_max"
CONF_VOL_DENON_MAX: Final[str] = "volume_denon_max"
CONF_VOL_ACTIVE_MIN: Final[str] = "volume_active_min"
CONF_VOL_NIGHT_OFFSET: Final[str] = "volume_night_offset"
CONF_VOL_EDGE_DAY_OFFSET: Final[str] = "volume_edge_day_offset"
CONF_VOL_OPENING_OFFSET: Final[str] = "volume_opening_offset"
CONF_GRIND_DENON_OFFSET: Final[str] = "grind_denon_offset"

DEFAULT_VOL_HOMEPODS_BASE: Final = 0.35
DEFAULT_VOL_DENON_BASE: Final = 0.40
DEFAULT_VOL_DUCKED_TARGET: Final = 0.15
DEFAULT_VOL_HOMEPODS_MAX: Final = 0.65
DEFAULT_VOL_DENON_MAX: Final = 0.70
DEFAULT_VOL_ACTIVE_MIN: Final = 0.05
DEFAULT_VOL_NIGHT_OFFSET: Final = -0.10
DEFAULT_VOL_EDGE_DAY_OFFSET: Final = -0.05
DEFAULT_VOL_OPENING_OFFSET: Final = -0.05
# GRIND-Delta (R15/R16/§6): Denon als Hintergrund-Kulisse, −0.10…−0.15.
DEFAULT_GRIND_DENON_OFFSET: Final = -0.12

VOL_SETTING_DEFAULTS: Final[dict[str, float]] = {
    CONF_VOL_HOMEPODS_BASE: DEFAULT_VOL_HOMEPODS_BASE,
    CONF_VOL_DENON_BASE: DEFAULT_VOL_DENON_BASE,
    CONF_VOL_DUCKED_TARGET: DEFAULT_VOL_DUCKED_TARGET,
    CONF_VOL_HOMEPODS_MAX: DEFAULT_VOL_HOMEPODS_MAX,
    CONF_VOL_DENON_MAX: DEFAULT_VOL_DENON_MAX,
    CONF_VOL_ACTIVE_MIN: DEFAULT_VOL_ACTIVE_MIN,
    CONF_VOL_NIGHT_OFFSET: DEFAULT_VOL_NIGHT_OFFSET,
    CONF_VOL_EDGE_DAY_OFFSET: DEFAULT_VOL_EDGE_DAY_OFFSET,
    CONF_VOL_OPENING_OFFSET: DEFAULT_VOL_OPENING_OFFSET,
    CONF_GRIND_DENON_OFFSET: DEFAULT_GRIND_DENON_OFFSET,
}

# --------------------------------------------------------------------------- #
# Default-data. Spiegelt das Entity-Roster (= PolicyDecision.as_dict()).
# quiet_mode lebt in media_state (L1, FLEET-31) — hier nur konsumiert.
# --------------------------------------------------------------------------- #
DEFAULT_DATA: Final[dict[str, Any]] = {
    "volume_target_homepods": None,
    "volume_target_denon": None,
    "audio_owner": AUDIO_OWNER_NONE,
    "action": ACTION_NONE,
    "volume_policy": VOL_POLICY_IDLE,
    "subwoofer_allowed": False,
    "homepods_should_pause": False,
    "homepods_resume_allowed": False,
    "volume_apply_allowed": False,
}

# --------------------------------------------------------------------------- #
# Output-Entity-Roster. uid = unique_id-Suffix = object_id-Basis, key = data-Feld.
# --------------------------------------------------------------------------- #
UID_VOLUME_TARGET_HOMEPODS: Final[str] = "volume_target_homepods"
UID_VOLUME_TARGET_DENON: Final[str] = "volume_target_denon"
UID_AUDIO_OWNER: Final[str] = "audio_owner"
UID_ACTION: Final[str] = "action"
UID_VOLUME_POLICY: Final[str] = "volume_policy"
UID_SUBWOOFER_ALLOWED: Final[str] = "subwoofer_allowed"
UID_HOMEPODS_SHOULD_PAUSE: Final[str] = "homepods_should_pause"
UID_HOMEPODS_RESUME_ALLOWED: Final[str] = "homepods_resume_allowed"
UID_VOLUME_APPLY_ALLOWED: Final[str] = "volume_apply_allowed"

# --------------------------------------------------------------------------- #
# Panel / WebSocket-API (Vanilla, kein Build-Step).
# --------------------------------------------------------------------------- #
PANEL_URL_PATH: Final[str] = "benni_media_policy"
PANEL_TITLE: Final[str] = "Media Policy"
PANEL_ICON: Final[str] = "mdi:volume-high"
FRONTEND_DIR_URL: Final[str] = "/benni_media_policy_app"
FRONTEND_ENTRY: Final[str] = f"{FRONTEND_DIR_URL}/main.js"
PANEL_ELEMENT: Final[str] = "bmp-app"

WS_GET_STATUS: Final[str] = f"{DOMAIN}/get_status"
