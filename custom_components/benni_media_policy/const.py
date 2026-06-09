"""Konstanten von benni_media_policy (L2 Policy).

Eigenständige HA-Integration (eigene Domain). Audio-Owner (pause/resume/radio) +
Volume/Ducking/Subwoofer. Konsumiert benni_media_state AUSSCHLIESSLICH über
HA-Entity-State — kein Cross-Modul-Python-Import.

Step-1-Scaffold: Struktur gespiegelt von benni_light_policy (Hub + Auto-Bind +
WS-Contract + Vanilla-Panel). Apply ist gated (Shadow-safe, Default aus).
Fachlogik folgt in Step 2/3.

Lastenheft (Step 3): einhornzentrale/docs/lastenhefte/reviewed/media/
"""
from __future__ import annotations

from typing import Any, Final

DOMAIN: Final[str] = "benni_media_policy"
MODULE_ID: Final[str] = "media_policy"
NAME: Final[str] = "Benni Media Policy"

DATA_COORDINATOR: Final[str] = "coordinator"

STORAGE_VERSION: Final[int] = 1

SINGLETON_UNIQUE_ID: Final[str] = f"{DOMAIN}_singleton"


def unique_id(*parts: str) -> str:
    return "_".join((DOMAIN, *parts))


# --------------------------------------------------------------------------- #
# Profil-Hub (benni / eltern) + Auto-Bind: Override ▶ Profil-Map ▶ leer.
# --------------------------------------------------------------------------- #
CONF_PROFILE: Final[str] = "profile"
PROFILE_BENNI: Final[str] = "benni"
PROFILE_ELTERN: Final[str] = "eltern"
PROFILES: Final[tuple[str, ...]] = (PROFILE_BENNI, PROFILE_ELTERN)
DEFAULT_PROFILE: Final[str] = PROFILE_BENNI
PROFILE_LABELS: Final[dict[str, str]] = {PROFILE_BENNI: "Benni", PROFILE_ELTERN: "Eltern"}

# --------------------------------------------------------------------------- #
# Config-Keys (vorläufig — finalisiert das Lastenheft in Step 3).
# Konsum aus benni_media_state läuft NUR über Entity-State (diese Entity-IDs).
# --------------------------------------------------------------------------- #
# Eingänge aus benni_media_state (Feeder):
CONF_MEDIA_CONTEXT: Final[str] = "media_context_entity"
CONF_MEDIA_DEVICE: Final[str] = "media_device_entity"
CONF_ENTERTAINMENT_ACTIVE: Final[str] = "entertainment_active_entity"
CONF_HEADSET_ACTIVE: Final[str] = "headset_active_entity"
# Eigene Policy-Targets (Audio-Geräte):
CONF_HOMEPODS: Final[str] = "homepod_entities"     # HomePods (mehrere)
CONF_DENON: Final[str] = "denon_entity"            # Denon/AVR
CONF_SUBWOOFER: Final[str] = "subwoofer_entity"    # Subwoofer

# Keys, deren gebundene Entities der Coordinator beobachtet (event-driven).
WATCH_KEYS: Final[tuple[str, ...]] = (
    CONF_MEDIA_CONTEXT,
    CONF_MEDIA_DEVICE,
    CONF_ENTERTAINMENT_ACTIVE,
    CONF_HEADSET_ACTIVE,
    CONF_HOMEPODS,
    CONF_DENON,
)

# --------------------------------------------------------------------------- #
# Profil-Map (Auto-Bind). Für benni werden die benni_media_state-Entities
# vorbelegt (Konsum-Vertrag via Entity-State). eltern bekommt später eine
# eigene media_state-Instanz → vorläufig leer (fällt sauber auf "leer" zurück).
# Greift nur, wenn die Entity in HA existiert.
# TODO(step3-lastenheft): Konsum-Vertrag media_policy -> media_state via Entity-State festklopfen
# --------------------------------------------------------------------------- #
PROFILE_PREFILL: Final[dict[str, dict[str, Any]]] = {
    PROFILE_BENNI: {
        CONF_MEDIA_CONTEXT: "sensor.benni_media_state_media_context",
        CONF_MEDIA_DEVICE: "sensor.benni_media_state_media_device",
        CONF_ENTERTAINMENT_ACTIVE: "binary_sensor.benni_media_state_entertainment_active",
        CONF_HEADSET_ACTIVE: "binary_sensor.benni_media_state_headset_active",
    },
    PROFILE_ELTERN: {},
}

# --------------------------------------------------------------------------- #
# Options.
# --------------------------------------------------------------------------- #
CONF_APPLY_ENABLED: Final[str] = "apply_enabled"
DEFAULT_APPLY_ENABLED: Final[bool] = False   # Shadow-safe out of the box.

# --------------------------------------------------------------------------- #
# Default-data (bis die Logik existiert — Step 2). Spiegelt das Entity-Roster.
# --------------------------------------------------------------------------- #
DEFAULT_DATA: Final[dict[str, Any]] = {
    "volume_target_homepods": None,
    "volume_target_denon": None,
    "audio_owner": None,
    "action": "none",
    "volume_policy": None,
    "subwoofer_allowed": False,
    "quiet_mode": False,
    "homepods_should_pause": False,
    "homepods_resume_allowed": False,
    "volume_apply_allowed": False,
}

# --------------------------------------------------------------------------- #
# Output-Entity-Roster (vorläufig). uid = unique_id-Suffix = object_id-Basis,
# key = Feld in data.
# --------------------------------------------------------------------------- #
# sensors
UID_VOLUME_TARGET_HOMEPODS: Final[str] = "volume_target_homepods"
UID_VOLUME_TARGET_DENON: Final[str] = "volume_target_denon"
UID_AUDIO_OWNER: Final[str] = "audio_owner"
UID_ACTION: Final[str] = "action"
UID_VOLUME_POLICY: Final[str] = "volume_policy"
# binary_sensors
UID_SUBWOOFER_ALLOWED: Final[str] = "subwoofer_allowed"
UID_QUIET_MODE: Final[str] = "quiet_mode"
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
