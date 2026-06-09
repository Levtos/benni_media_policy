"""HA-freie Policy-Engine für benni_media_policy (L2 Policy).

Strikt HA-frei und voll testbar (keine homeassistant-Imports, keine relativen
Imports). Entscheidet Audio-Owner + Volume/Ducking/Subwoofer. Apply ist gated.

Step-1-Scaffold: nur Signatur-Form + stabile Defaults. Der echte Body wird in
Step 2 aus bennis_toolbox/.../benni_media_context/ (orchestrator.py /
volume_orchestrator.py) extrahiert.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_ACTION = "none"


@dataclass(frozen=True)
class Inputs:
    """Snapshot der Policy-Inputs für eine Entscheidung. None = unknown.

    Eingänge aus benni_media_state kommen über Entity-State (NICHT per Import).
    Vorläufig — das Feld-Set wird in Step 2/3 finalisiert.
    """

    media_context: str | None = None
    media_device: str | None = None
    entertainment_active: bool | None = None
    headset_active: bool | None = None
    # Quiet wird aus media_state (L1, FLEET-31) konsumiert — hier nur Eingang.
    quiet_mode: bool | None = None
    # TODO(phase3): um die echten Policy-Inputs erweitern (Volume-Profile, Owner-Arbitrierung)


@dataclass
class PolicyDecision:
    """Entscheidung. Spiegelt das Entity-Roster (vorläufig)."""

    volume_target_homepods: int | None = None
    volume_target_denon: int | None = None
    audio_owner: str | None = None
    action: str = DEFAULT_ACTION
    volume_policy: str | None = None
    subwoofer_allowed: bool = False
    homepods_should_pause: bool = False
    homepods_resume_allowed: bool = False
    volume_apply_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "volume_target_homepods": self.volume_target_homepods,
            "volume_target_denon": self.volume_target_denon,
            "audio_owner": self.audio_owner,
            "action": self.action,
            "volume_policy": self.volume_policy,
            "subwoofer_allowed": self.subwoofer_allowed,
            "homepods_should_pause": self.homepods_should_pause,
            "homepods_resume_allowed": self.homepods_resume_allowed,
            "volume_apply_allowed": self.volume_apply_allowed,
        }


def decide(inputs: Inputs, *, apply_enabled: bool = False) -> PolicyDecision:
    """Entscheidet Audio-Owner + Volume/Ducking/Subwoofer.

    `apply_enabled` gated nur `volume_apply_allowed` (Shadow-safe), ohne die
    übrige Entscheidung zu verändern — wie das gated-Apply-Pattern in light_policy.

    Step 1: liefert stabile Defaults, damit die Policy lädt und Panel/Entities
    eine Payload haben. Noch kein Verhalten.
    """
    # TODO(phase3): decide()-Body aus benni_media_context (orchestrator/volume_orchestrator) extrahieren
    # TODO(phase4): Konsum-Vertrag media_policy -> media_state via Entity-State final verdrahten
    # TODO(phase3): B2 — gaming-Detection bleibt in media_state; Policy konsumiert nur
    return PolicyDecision()
