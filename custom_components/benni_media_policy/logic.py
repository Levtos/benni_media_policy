"""HA-freie Policy-Engine für benni_media_policy (L2 / Media-Gehirn).

Phase 3 (FLEET-34): Lift + Adaption von orchestrator.py (Audio-Owner,
pause/resume/radio) + volume_orchestrator.py (Volume-Policy, Ducking, Offsets) +
evaluate_subwoofer/_denon_audio_path aus bennis_toolbox/benni_media_context.

Adaption ggü. dem Toolbox-Original (verbindlich per Board):
- **Owner aus media_state-Context**, nicht Roh-Re-Derive: der Context kodiert
  Geräte-Priorität + B2-Gaming-Gate bereits (media_state). owner = f(context,
  quiet, bio_sleep, homepods_playing).
- **Pflicht-Delta GRIND** (v3.1 KH-5/R15/R16/§6): bei subcontext == gaming_grind
  1. HomePods werden NICHT pausiert (Grind hat HomePods-Anteil → spielen weiter),
  2. Volume: HomePods auf Normal-Niveau, Denon mit negativem Offset (Kulisse),
  3. Subwoofer IMMER aus (R16 übersteuert die Sub-Policy).

Gating klar getrennt: `volume_apply_allowed` = pro Entscheidung (hier). Der
globale `apply_enabled`-Shadow-Switch lebt als Option im Coordinator; der
Apply-Layer (benni_media_apply) prüft BEIDE.

Keine HA-Imports. Der Coordinator macht das Entity-State-Plumbing + hält den
persistenten OrchestratorState über die Ticks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .const import (
    ACTION_NONE,
    ACTION_PAUSE,
    ACTION_RESUME,
    ACTION_START_RADIO,
    AUDIO_OWNER_GAMING,
    AUDIO_OWNER_HOMEPODS,
    AUDIO_OWNER_NONE,
    AUDIO_OWNER_PRIVATE,
    AUDIO_OWNER_TV_DENON,
    CTX_GAMING,
    CTX_PRIVATE,
    CTX_STREAMING,
    CTX_TV,
    DAY_EDGE_VALUES,
    DAY_NIGHT_VALUES,
    DEFAULT_GRIND_DENON_OFFSET,
    DEFAULT_VOL_ACTIVE_MIN,
    DEFAULT_VOL_DENON_BASE,
    DEFAULT_VOL_DENON_MAX,
    DEFAULT_VOL_DUCKED_TARGET,
    DEFAULT_VOL_EDGE_DAY_OFFSET,
    DEFAULT_VOL_HOMEPODS_BASE,
    DEFAULT_VOL_HOMEPODS_MAX,
    DEFAULT_VOL_NIGHT_OFFSET,
    DEFAULT_VOL_OPENING_OFFSET,
    DEV_DENON,
    RESUME_MODE_MANUAL,
    RESUME_MODE_RADIO,
    SUB_GAME_GRIND,
    VOL_POLICY_BLOCKED,
    VOL_POLICY_DUCKED,
    VOL_POLICY_IDLE,
    VOL_POLICY_MEDIA,
    VOL_POLICY_MUTED,
)


# --------------------------------------------------------------------------- #
# Inputs / persistenter Zustand / Settings
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Inputs:
    """Snapshot der Policy-Eingänge. None = unknown/nicht gebunden."""

    # aus media_state (Entity-State):
    context: Optional[str] = None
    subcontext: Optional[str] = None
    device: Optional[str] = None
    entertainment_active: bool = False
    headset_active: bool = False
    quiet_mode: bool = False
    # eigene Inputs:
    homepods_state: Optional[str] = None      # "playing"/"paused"/"idle"/…
    homepods_configured: bool = False
    denon_configured: bool = False
    denon_active: bool = False                # Plug-Active (denon_audio_path)
    denon_source: Optional[str] = None        # Denon-Player source-Attribut
    bio_state: Optional[str] = None
    bio_sleep: bool = False
    day_state: Optional[str] = None
    opening_any_open: bool = False
    manual_playback_active: bool = False
    planned_radio_active: bool = False
    media_stop_latch: Optional[bool] = None   # None = nicht konfiguriert


@dataclass
class OrchestratorState:
    """Persistenter Zustand zwischen Coordinator-Ticks (RAM, wie Toolbox)."""

    auto_paused: bool = False
    pre_pause_mode: Optional[str] = None
    manual_stop: bool = False
    last_homepods_playing: bool = False
    last_competes: bool = False
    last_planned_radio_active: bool = False
    last_manual_playback_active: bool = False


@dataclass(frozen=True)
class VolumeSettings:
    homepods_base: float = DEFAULT_VOL_HOMEPODS_BASE
    denon_base: float = DEFAULT_VOL_DENON_BASE
    ducked_target: float = DEFAULT_VOL_DUCKED_TARGET
    homepods_max: float = DEFAULT_VOL_HOMEPODS_MAX
    denon_max: float = DEFAULT_VOL_DENON_MAX
    active_min: float = DEFAULT_VOL_ACTIVE_MIN
    night_offset: float = DEFAULT_VOL_NIGHT_OFFSET
    edge_day_offset: float = DEFAULT_VOL_EDGE_DAY_OFFSET
    opening_offset: float = DEFAULT_VOL_OPENING_OFFSET
    grind_denon_offset: float = DEFAULT_GRIND_DENON_OFFSET


@dataclass
class PolicyDecision:
    """Entscheidung. Spiegelt das Entity-Roster + Debug-Felder."""

    # Roster (Output-Entities):
    volume_target_homepods: Optional[float] = None
    volume_target_denon: Optional[float] = None
    audio_owner: str = AUDIO_OWNER_NONE
    action: str = ACTION_NONE
    volume_policy: str = VOL_POLICY_IDLE
    subwoofer_allowed: bool = False
    homepods_should_pause: bool = False
    homepods_resume_allowed: bool = False
    volume_apply_allowed: bool = False
    # Debug (nur im WS-Status / nicht als eigene Entity):
    owner_reason: str = "idle"
    action_reason: str = "idle"
    volume_reason: str = "idle"
    subwoofer_block_reason: Optional[str] = None
    denon_audio_path: bool = False
    is_grind: bool = False
    active_reasons: list = field(default_factory=list)

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

    def debug(self) -> dict[str, Any]:
        return {
            **self.as_dict(),
            "owner_reason": self.owner_reason,
            "action_reason": self.action_reason,
            "volume_reason": self.volume_reason,
            "subwoofer_block_reason": self.subwoofer_block_reason,
            "denon_audio_path": self.denon_audio_path,
            "is_grind": self.is_grind,
            "active_reasons": list(self.active_reasons),
        }


# --------------------------------------------------------------------------- #
# Owner (aus media_state-Context, kein Roh-Re-Derive)
# --------------------------------------------------------------------------- #
def decide_owner(inp: Inputs) -> tuple[str, str]:
    """audio_owner + Label aus dem Context. Priorität wie Lastenheft:
    private_time > gaming > streaming/tv > homepods > none."""
    if inp.quiet_mode or inp.bio_sleep or inp.context == CTX_PRIVATE:
        return AUDIO_OWNER_PRIVATE, "private_time"
    if inp.context == CTX_GAMING:
        return AUDIO_OWNER_GAMING, f"gaming_{inp.device or 'unknown'}"
    if inp.context in (CTX_STREAMING, CTX_TV):
        return AUDIO_OWNER_TV_DENON, ("streaming" if inp.context == CTX_STREAMING else "tv")
    if inp.homepods_state == "playing":
        return AUDIO_OWNER_HOMEPODS, "homepods_only"
    return AUDIO_OWNER_NONE, "idle"


def is_grind(inp: Inputs) -> bool:
    """GRIND-Delta gilt nur im Gaming-Context mit subcontext == gaming_grind."""
    return inp.context == CTX_GAMING and inp.subcontext == SUB_GAME_GRIND


def competes_with_homepods(owner: str, grind: bool) -> bool:
    """Stack, der die HomePods verdrängt. GRIND hat HomePods-Anteil (R15) →
    konkurriert NICHT, HomePods spielen weiter."""
    if grind:
        return False
    return owner in (AUDIO_OWNER_PRIVATE, AUDIO_OWNER_GAMING, AUDIO_OWNER_TV_DENON)


# --------------------------------------------------------------------------- #
# Audio-Action-Zustandsmaschine (Orchestrator-Lift; competes statt other_stack)
# --------------------------------------------------------------------------- #
def decide_action(
    inp: Inputs, owner: str, competes: bool, state: OrchestratorState
) -> tuple[str, bool, bool, str, OrchestratorState]:
    """Return (action, should_pause, resume_allowed, reason, new_state)."""
    new_state = OrchestratorState(
        auto_paused=state.auto_paused,
        pre_pause_mode=state.pre_pause_mode,
        manual_stop=state.manual_stop,
        last_homepods_playing=state.last_homepods_playing,
        last_competes=state.last_competes,
        last_planned_radio_active=state.last_planned_radio_active,
        last_manual_playback_active=state.last_manual_playback_active,
    )
    homepods_playing = inp.homepods_state == "playing"
    homepods_missing = not inp.homepods_configured

    # ---- Persistente Übergänge (auf Basis des vorigen Ticks) ----
    if state.last_homepods_playing and not homepods_playing:
        if state.last_competes or competes:
            # Auto-Pause: ein höher-priorer Stack hat das Audio gezogen.
            new_state.auto_paused = True
            new_state.manual_stop = False
            if state.last_planned_radio_active:
                new_state.pre_pause_mode = RESUME_MODE_RADIO
            elif state.last_manual_playback_active:
                new_state.pre_pause_mode = RESUME_MODE_MANUAL
            else:
                new_state.pre_pause_mode = None
        else:
            # Kein konkurrierender Stack → User hat selbst gestoppt.
            new_state.manual_stop = True
            new_state.auto_paused = False
            new_state.pre_pause_mode = None
    elif homepods_playing and not state.last_homepods_playing:
        new_state.auto_paused = False
        new_state.manual_stop = False
        new_state.pre_pause_mode = None

    # Externer media_stop_latch übersteuert die interne manual_stop-Buchführung.
    if inp.media_stop_latch is True:
        new_state.manual_stop = True
    elif inp.media_stop_latch is False and not state.last_homepods_playing:
        new_state.manual_stop = False

    # ---- Action / reason ----
    reason = "idle"
    action = ACTION_NONE
    should_pause = False
    resume_allowed = False

    if homepods_missing:
        reason = "homepods_entity_missing"
    elif competes and homepods_playing:
        action = ACTION_PAUSE
        should_pause = True
        reason = "competing_stack_pause_homepods"
    elif competes:
        reason = "competing_stack_active"
    else:
        # Kein konkurrierender Stack (oder GRIND) → Resume/Radio prüfen.
        if inp.bio_sleep:
            reason = "bio_sleep_blocks_resume"
        elif new_state.manual_stop:
            reason = "manual_stop_blocks_resume"
        elif not new_state.auto_paused:
            reason = "no_auto_pause"
        else:
            mode = new_state.pre_pause_mode
            if mode == RESUME_MODE_RADIO:
                action = ACTION_START_RADIO
                resume_allowed = True
                reason = "post_entertainment_start_radio"
            elif mode == RESUME_MODE_MANUAL:
                action = ACTION_RESUME
                resume_allowed = True
                reason = "post_entertainment_resume_music"
            else:
                reason = "no_resume_candidate"

    # ---- Buchführung für den nächsten Tick ----
    new_state.last_homepods_playing = homepods_playing
    new_state.last_competes = competes
    new_state.last_planned_radio_active = inp.planned_radio_active
    new_state.last_manual_playback_active = inp.manual_playback_active

    return action, should_pause, resume_allowed, reason, new_state


# --------------------------------------------------------------------------- #
# Volume (volume_orchestrator-Lift + GRIND-Delta)
# --------------------------------------------------------------------------- #
def _day_offset(day_state: Optional[str], s: VolumeSettings) -> float:
    if day_state in DAY_NIGHT_VALUES:
        return s.night_offset
    if day_state in DAY_EDGE_VALUES:
        return s.edge_day_offset
    return 0.0


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _final_target(base: float, *, day_off: float, open_off: float,
                  active_min: float, hard_max: float) -> float:
    target = base + day_off + open_off
    target = max(target, active_min)
    return round(_clamp(target, 0.0, hard_max), 3)


def decide_volume(
    inp: Inputs, owner: str, grind: bool, s: VolumeSettings
) -> tuple[str, Optional[float], Optional[float], bool, str]:
    """Return (policy, homepods_target, denon_target, apply_allowed, reason)."""
    # 1. Blocked: keine adressierbaren Speaker.
    if not inp.homepods_configured and not inp.denon_configured:
        return VOL_POLICY_BLOCKED, None, None, False, "no_speakers_configured"

    # 2. Muted: bio sleep.
    if inp.bio_sleep:
        return VOL_POLICY_MUTED, None, None, False, "bio_sleep_muted"

    # ---- Base-Routing ----
    if grind:
        # GRIND-Delta: HomePods Normal-Niveau, Denon Kulisse (negativer Offset).
        base_hp = s.homepods_base
        base_dn = max(0.0, s.denon_base + s.grind_denon_offset)
    elif owner == AUDIO_OWNER_HOMEPODS:
        base_hp, base_dn = s.homepods_base, 0.0
    elif owner in (AUDIO_OWNER_TV_DENON, AUDIO_OWNER_GAMING, AUDIO_OWNER_PRIVATE):
        base_hp, base_dn = 0.0, s.denon_base
    else:  # NONE
        base_hp, base_dn = 0.0, 0.0

    day_off = _day_offset(inp.day_state, s)
    open_off = s.opening_offset if inp.opening_any_open else 0.0

    # 3. Ducked: quiet mode (hart auf ducked_target für aktive Seite[n]).
    if inp.quiet_mode:
        hp = dn = None
        if inp.homepods_configured:
            hp = round(_clamp(s.ducked_target, 0.0, s.homepods_max), 3) if base_hp > 0 else 0.0
        if inp.denon_configured:
            dn = round(_clamp(s.ducked_target, 0.0, s.denon_max), 3) if base_dn > 0 else 0.0
        return VOL_POLICY_DUCKED, hp, dn, True, "quiet_mode_ducked"

    # 4. Idle: kein Owner und kein Grind.
    if owner == AUDIO_OWNER_NONE and not grind:
        hp = 0.0 if inp.homepods_configured else None
        dn = 0.0 if inp.denon_configured else None
        return VOL_POLICY_IDLE, hp, dn, True, "idle_no_owner"

    # 5. Media: normales Routing mit Offsets/Clamps.
    hp = dn = None
    if inp.homepods_configured:
        hp = _final_target(base_hp, day_off=day_off, open_off=open_off,
                           active_min=s.active_min, hard_max=s.homepods_max) if base_hp > 0 else 0.0
    if inp.denon_configured:
        dn = _final_target(base_dn, day_off=day_off, open_off=open_off,
                           active_min=s.active_min, hard_max=s.denon_max) if base_dn > 0 else 0.0
    reason = "grind_homepods_denon_kulisse" if grind else f"owner_{owner}"
    return VOL_POLICY_MEDIA, hp, dn, True, reason


# --------------------------------------------------------------------------- #
# Subwoofer (evaluate_subwoofer-Lift + R16 GRIND-Override)
# --------------------------------------------------------------------------- #
def denon_audio_path(inp: Inputs) -> bool:
    """Audio läuft gerade über den Denon (Plug-Active ODER primäres Gerät Denon
    ODER Denon-Player-source nicht leer)."""
    if inp.denon_active:
        return True
    if inp.device == DEV_DENON:
        return True
    src = (inp.denon_source or "").strip().lower()
    return bool(src and src not in ("", "off", "standby"))


def evaluate_subwoofer(inp: Inputs, grind: bool, denon_path: bool) -> tuple[bool, Optional[str]]:
    # R16: bei gaming_grind IMMER aus (übersteuert die Sub-Policy).
    if grind:
        return False, "grind_r16"
    if inp.quiet_mode:
        return False, "quiet_mode"
    if not inp.entertainment_active:
        return False, "no_entertainment"
    if inp.headset_active:
        return False, "headset_active"
    if inp.opening_any_open and not denon_path:
        return False, "window_open_no_denon_path"
    return True, None


# --------------------------------------------------------------------------- #
# Master-Entscheidung
# --------------------------------------------------------------------------- #
def decide(
    inp: Inputs, state: OrchestratorState, settings: Optional[VolumeSettings] = None
) -> tuple[PolicyDecision, OrchestratorState]:
    """Berechnet die Policy-Entscheidung + den nächsten persistenten Zustand."""
    if settings is None:
        settings = VolumeSettings()
    d = PolicyDecision()
    reasons: list[str] = []

    grind = is_grind(inp)
    d.is_grind = grind

    owner, owner_label = decide_owner(inp)
    d.audio_owner = owner
    d.owner_reason = owner_label
    reasons.append(f"owner:{owner_label}")

    competes = competes_with_homepods(owner, grind)
    action, should_pause, resume_allowed, action_reason, new_state = decide_action(
        inp, owner, competes, state
    )
    d.action = action
    d.homepods_should_pause = should_pause
    d.homepods_resume_allowed = resume_allowed
    d.action_reason = action_reason
    reasons.append(f"action:{action_reason}")

    policy, hp, dn, apply_allowed, vol_reason = decide_volume(inp, owner, grind, settings)
    d.volume_policy = policy
    d.volume_target_homepods = hp
    d.volume_target_denon = dn
    d.volume_apply_allowed = apply_allowed
    d.volume_reason = vol_reason
    reasons.append(f"volume:{vol_reason}")

    d.denon_audio_path = denon_audio_path(inp)
    allowed, block = evaluate_subwoofer(inp, grind, d.denon_audio_path)
    d.subwoofer_allowed = allowed
    d.subwoofer_block_reason = block
    if block:
        reasons.append(f"sub_off:{block}")

    d.active_reasons = reasons
    return d, new_state
