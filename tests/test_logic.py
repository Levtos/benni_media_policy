"""Pure-logic-Tests für den Policy-Lift (Phase 3, FLEET-34).

Deckt ab: Owner aus Context, GRIND-Pflicht-Delta (R15/R16/§6), Action-
Zustandsmaschine (pause/auto-pause/resume/radio/manual-stop), Volume-Routing +
Offsets + Ducking + Muted + Blocked, Subwoofer-Policy.
"""
from __future__ import annotations

import bmp_const as C
import bmp_logic as L


def _inp(**kw):
    base = dict(homepods_configured=True, denon_configured=True)
    base.update(kw)
    return L.Inputs(**base)


def _decide(inp, state=None, settings=None):
    return L.decide(inp, state or L.OrchestratorState(), settings)


# ------------------------------------------------------------------- Owner
def test_owner_idle():
    d, _ = _decide(_inp())
    assert d.audio_owner == C.AUDIO_OWNER_NONE


def test_owner_homepods_when_playing():
    d, _ = _decide(_inp(homepods_state="playing"))
    assert d.audio_owner == C.AUDIO_OWNER_HOMEPODS


def test_owner_tv_denon_for_streaming_and_tv():
    assert _decide(_inp(context=C.CTX_STREAMING))[0].audio_owner == C.AUDIO_OWNER_TV_DENON
    assert _decide(_inp(context=C.CTX_TV))[0].audio_owner == C.AUDIO_OWNER_TV_DENON


def test_owner_gaming():
    d, _ = _decide(_inp(context=C.CTX_GAMING, device="ps5"))
    assert d.audio_owner == C.AUDIO_OWNER_GAMING


def test_owner_private_via_context_quiet_bio():
    assert _decide(_inp(context=C.CTX_PRIVATE))[0].audio_owner == C.AUDIO_OWNER_PRIVATE
    assert _decide(_inp(quiet_mode=True))[0].audio_owner == C.AUDIO_OWNER_PRIVATE
    assert _decide(_inp(bio_sleep=True))[0].audio_owner == C.AUDIO_OWNER_PRIVATE


# -------------------------------------------------------------- Volume base
def test_volume_homepods_owner():
    d, _ = _decide(_inp(homepods_state="playing"))
    assert d.volume_policy == C.VOL_POLICY_MEDIA
    assert d.volume_target_homepods == 0.35
    assert d.volume_target_denon == 0.0


def test_volume_tv_denon_owner():
    d, _ = _decide(_inp(context=C.CTX_TV))
    assert d.volume_target_denon == 0.40
    assert d.volume_target_homepods == 0.0


def test_volume_night_offset():
    d, _ = _decide(_inp(context=C.CTX_TV, day_state="late_night"))
    assert d.volume_target_denon == 0.30  # 0.40 - 0.10


def test_volume_opening_offset():
    d, _ = _decide(_inp(context=C.CTX_TV, opening_any_open=True))
    assert d.volume_target_denon == 0.35  # 0.40 - 0.05


def test_volume_blocked_no_speakers():
    d, _ = _decide(_inp(homepods_configured=False, denon_configured=False, context=C.CTX_TV))
    assert d.volume_policy == C.VOL_POLICY_BLOCKED
    assert d.volume_apply_allowed is False


def test_volume_muted_bio_sleep():
    d, _ = _decide(_inp(bio_sleep=True, context=C.CTX_TV))
    assert d.volume_policy == C.VOL_POLICY_MUTED
    assert d.volume_target_homepods is None
    assert d.volume_target_denon is None
    assert d.volume_apply_allowed is False


def test_volume_ducked_quiet():
    d, _ = _decide(_inp(quiet_mode=True, context=C.CTX_TV))
    assert d.volume_policy == C.VOL_POLICY_DUCKED
    assert d.volume_target_denon == 0.15  # ducked target
    assert d.volume_target_homepods == 0.0
    assert d.volume_apply_allowed is True


def test_volume_idle_zeros():
    d, _ = _decide(_inp())
    assert d.volume_policy == C.VOL_POLICY_IDLE
    assert d.volume_target_homepods == 0.0
    assert d.volume_target_denon == 0.0


# ------------------------------------------------------ GRIND Pflicht-Delta
def test_grind_flag():
    d, _ = _decide(_inp(context=C.CTX_GAMING, subcontext=C.SUB_GAME_GRIND))
    assert d.is_grind is True


def test_grind_homepods_play_denon_kulisse():
    d, _ = _decide(_inp(context=C.CTX_GAMING, subcontext=C.SUB_GAME_GRIND))
    # HomePods auf Normal-Niveau, Denon Basis + negativer Offset.
    assert d.volume_target_homepods == 0.35
    assert d.volume_target_denon == 0.28  # 0.40 - 0.12
    assert d.volume_policy == C.VOL_POLICY_MEDIA


def test_grind_does_not_pause_homepods():
    # Grind hat HomePods-Anteil (R15) → kein Pause, auch wenn HomePods spielen.
    d, _ = _decide(_inp(context=C.CTX_GAMING, subcontext=C.SUB_GAME_GRIND,
                        homepods_state="playing"))
    assert d.homepods_should_pause is False
    assert d.action == C.ACTION_NONE


def test_grind_subwoofer_always_off():
    d, _ = _decide(_inp(context=C.CTX_GAMING, subcontext=C.SUB_GAME_GRIND,
                        entertainment_active=True, denon_active=True))
    assert d.subwoofer_allowed is False
    assert d.subwoofer_block_reason == "grind_r16"


def test_non_grind_gaming_pauses_homepods():
    # gaming_default (kein Grind) verdrängt HomePods.
    d, _ = _decide(_inp(context=C.CTX_GAMING, subcontext="gaming_default",
                        homepods_state="playing"))
    assert d.homepods_should_pause is True
    assert d.action == C.ACTION_PAUSE


# ----------------------------------------------------- Action-Zustandsmaschine
def test_pause_when_competing_stack_and_playing():
    d, _ = _decide(_inp(context=C.CTX_TV, homepods_state="playing"))
    assert d.action == C.ACTION_PAUSE
    assert d.homepods_should_pause is True


def test_radio_resume_after_entertainment():
    # tick1: HomePods spielen + Radio geplant, TV (competing).
    d1, s1 = _decide(_inp(context=C.CTX_TV, homepods_state="playing",
                          planned_radio_active=True))
    # tick2: HomePods gestoppt (vom TV-Stack gezogen).
    d2, s2 = _decide(_inp(context=C.CTX_TV, homepods_state="paused"), s1)
    assert s2.auto_paused is True
    assert s2.pre_pause_mode == C.RESUME_MODE_RADIO
    # tick3: TV aus → kein competing stack → Radio-Resume.
    d3, s3 = _decide(_inp(homepods_state="paused"), s2)
    assert d3.action == C.ACTION_START_RADIO
    assert d3.homepods_resume_allowed is True


def test_manual_stop_blocks_resume():
    # tick1: HomePods spielen, kein competing stack (owner homepods).
    d1, s1 = _decide(_inp(homepods_state="playing"))
    # tick2: User stoppt selbst (kein competing stack).
    d2, s2 = _decide(_inp(homepods_state="idle"), s1)
    assert s2.manual_stop is True
    assert d2.action == C.ACTION_NONE
    assert d2.homepods_resume_allowed is False


def test_media_stop_latch_forces_manual_stop():
    d, s = _decide(_inp(homepods_state="idle", media_stop_latch=True))
    assert s.manual_stop is True


def test_homepods_missing_blocks_action():
    d, _ = _decide(_inp(homepods_configured=False, denon_configured=True,
                        context=C.CTX_TV))
    assert d.action == C.ACTION_NONE
    assert d.action_reason == "homepods_entity_missing"


# ------------------------------------------------------------- Subwoofer
def test_subwoofer_on_with_entertainment_and_denon_path():
    d, _ = _decide(_inp(context=C.CTX_TV, entertainment_active=True, denon_active=True))
    assert d.subwoofer_allowed is True


def test_subwoofer_off_no_entertainment():
    d, _ = _decide(_inp(entertainment_active=False))
    assert d.subwoofer_allowed is False
    assert d.subwoofer_block_reason == "no_entertainment"


def test_subwoofer_off_headset():
    d, _ = _decide(_inp(context=C.CTX_GAMING, subcontext="gaming_headset",
                        entertainment_active=True, headset_active=True, denon_active=True))
    assert d.subwoofer_allowed is False
    assert d.subwoofer_block_reason == "headset_active"


def test_subwoofer_off_quiet():
    d, _ = _decide(_inp(quiet_mode=True, entertainment_active=True, denon_active=True))
    assert d.subwoofer_allowed is False
    assert d.subwoofer_block_reason == "quiet_mode"


def test_subwoofer_off_window_no_denon_path():
    d, _ = _decide(_inp(context=C.CTX_STREAMING, entertainment_active=True,
                        opening_any_open=True, denon_active=False, device="appletv"))
    assert d.subwoofer_allowed is False
    assert d.subwoofer_block_reason == "window_open_no_denon_path"


def test_denon_audio_path_via_device():
    d, _ = _decide(_inp(context=C.CTX_TV, entertainment_active=True, device=C.DEV_DENON,
                        opening_any_open=True))
    # device==denon → denon_path True → window allein blockt nicht mehr.
    assert d.denon_audio_path is True
    assert d.subwoofer_allowed is True
