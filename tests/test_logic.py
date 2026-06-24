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


def test_owner_private_via_context_and_bio_not_quiet():
    # private_time-Szenario + bio_sleep → PRIVATE; quiet_mode allein NICHT (FLEET-81:
    # Quiet ist Volume-Overlay, kein Owner — koppelte früher fälschlich → pause).
    assert _decide(_inp(context=C.CTX_PRIVATE))[0].audio_owner == C.AUDIO_OWNER_PRIVATE
    assert _decide(_inp(bio_sleep=True))[0].audio_owner == C.AUDIO_OWNER_PRIVATE
    # Quiet bei spielenden HomePods → Owner bleibt HOMEPODS (kein PRIVATE/pause).
    assert _decide(_inp(quiet_mode=True, homepods_state="playing"))[0].audio_owner == C.AUDIO_OWNER_HOMEPODS


def test_quiet_ducks_homepods_not_pause_fleet81():
    # FLEET-81: Tür auf (quiet) bei spielenden HomePods → ducken, NICHT stoppen.
    d, _ = _decide(_inp(quiet_mode=True, homepods_state="playing"))
    assert d.action != C.ACTION_PAUSE
    assert d.homepods_should_pause is False
    assert d.volume_policy == C.VOL_POLICY_DUCKED
    assert d.volume_target_homepods is not None and d.volume_target_homepods > 0.0


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


def test_volume_dayphase_baseline_denon():
    # Denon-Baseline (Lastenheft §6) ersetzt das alte flache night_offset.
    assert _decide(_inp(context=C.CTX_TV, day_state="late_night"))[0].volume_target_denon == 0.20
    assert _decide(_inp(context=C.CTX_TV, day_state="forenoon"))[0].volume_target_denon == 0.30


def test_volume_dayphase_baseline_homepods():
    # HomePods-Baseline pro Tagesphase.
    assert _decide(_inp(homepods_state="playing", day_state="afternoon"))[0].volume_target_homepods == 0.45
    assert _decide(_inp(homepods_state="playing", day_state="early_morning"))[0].volume_target_homepods == 0.25


def test_volume_unknown_dayphase_falls_back_to_base():
    # day_state=None → Fallback-Base (homepods_base 0.35 / denon_base 0.40).
    assert _decide(_inp(homepods_state="playing"))[0].volume_target_homepods == 0.35
    assert _decide(_inp(context=C.CTX_TV))[0].volume_target_denon == 0.40


def test_volume_opening_offset():
    # fenster_offset (R17) auf die Dayphase-Baseline: afternoon Denon 0.30 − 0.05.
    d, _ = _decide(_inp(context=C.CTX_TV, day_state="afternoon", opening_any_open=True))
    assert d.volume_target_denon == 0.25


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
    d, s = _decide(_inp())
    assert d.volume_policy == C.VOL_POLICY_IDLE
    assert d.volume_target_homepods == 0.0
    assert d.volume_target_denon == 0.0
    # Frisches Idle ohne Vorlauf → kein Stick.
    assert s.last_hp_media_target is None


# ------------------------------------------------ FLEET-153: HomePods-Idle-Sticky
def test_volume_idle_sticky_holds_last_homepods_media():
    # Tick 1: HomePods spielen → MEDIA-Target 0.35, Stick gesetzt.
    d1, s1 = _decide(_inp(homepods_state="playing"))
    assert d1.volume_policy == C.VOL_POLICY_MEDIA
    assert d1.volume_target_homepods == 0.35
    assert s1.last_hp_media_target == 0.35
    # Tick 2: Playback-Lücke (owner none) → Target bleibt sticky statt 0.0 zu
    # kollabieren → Apply rampt nicht runter/hoch (FLEET-153).
    d2, s2 = _decide(_inp(), state=s1)
    assert d2.volume_policy == C.VOL_POLICY_IDLE
    assert d2.volume_target_homepods == 0.35
    assert d2.volume_reason == "idle_sticky_homepods"
    assert s2.last_hp_media_target == 0.35


def test_volume_idle_sticky_cleared_on_denon_path():
    # HomePods spielen → Stick 0.35.
    _d1, s1 = _decide(_inp(homepods_state="playing"))
    assert s1.last_hp_media_target == 0.35
    # Echter Pfadwechsel auf Denon/TV → Stick gelöscht (HomePods verlassen den Pfad).
    _d2, s2 = _decide(_inp(context=C.CTX_TV), state=s1)
    assert s2.last_hp_media_target is None
    # Folgendes Idle → HomePods 0.0 (nicht ihr Pfad), kein Schein-Stick.
    d3, _s3 = _decide(_inp(), state=s2)
    assert d3.volume_policy == C.VOL_POLICY_IDLE
    assert d3.volume_target_homepods == 0.0


# --------------------------------------------------- FLEET-102 Volume-Matrix (A)
def test_matrix_default_base_tables_match_consts():
    # Default-Matrix = die bisherigen Konstanten (verhaltensgleich).
    s = L.VolumeSettings()
    assert s.base_homepods == C.HOMEPODS_BASELINES
    assert s.base_denon == C.DENON_BASELINES
    assert s.scenario_off_homepods == {} and s.activity_off_homepods == {}


def test_matrix_custom_base_changes_target():
    # Per-Tagesphase-Base aus der Matrix steuert das Target (das eigentliche 102).
    s = L.VolumeSettings(base_homepods={**C.HOMEPODS_BASELINES, "afternoon": 0.50})
    d, _ = _decide(_inp(homepods_state="playing", day_state="afternoon"), settings=s)
    assert d.volume_target_homepods == 0.50  # Default wäre 0.45


def test_matrix_scenario_offset_applies():
    # Szenario-Offset (heute tot, 0.0) wird aus der Matrix gezogen und wirkt.
    s = L.VolumeSettings(scenario_off_homepods={C.AUDIO_SCENARIO_MUSIC: 0.10})
    d, _ = _decide(_inp(homepods_state="playing"), settings=s)  # Fallback-Base 0.35
    assert d.volume_target_homepods == 0.45
    # Nicht-passendes Szenario → kein Offset (.get-Default 0.0).
    s2 = L.VolumeSettings(scenario_off_homepods={C.AUDIO_SCENARIO_TV: 0.10})
    d2, _ = _decide(_inp(homepods_state="playing"), settings=s2)
    assert d2.volume_target_homepods == 0.35


def test_matrix_activity_offset_applies():
    # Aktivitäts-Offset (heute tot, 0.0) wird aus der Matrix gezogen und wirkt.
    s = L.VolumeSettings(activity_off_homepods={"relax": -0.05})
    d, _ = _decide(_inp(homepods_state="playing", activity_context="relax"), settings=s)
    assert d.volume_target_homepods == 0.30  # 0.35 - 0.05


def test_matrix_patch_sets_and_clamps():
    ov = L.apply_matrix_patch({}, {"base": {"homepods": {"afternoon": 0.50}}})
    assert ov == {"base": {"homepods": {"afternoon": 0.50}}}
    # base clamp [0,1], offsets clamp [-1,1].
    ov = L.apply_matrix_patch(ov, {
        "base": {"homepods": {"forenoon": 2.0}},
        "scenario_off": {"denon": {"music": -5.0}},
    })
    assert ov["base"]["homepods"]["forenoon"] == 1.0
    assert ov["scenario_off"]["denon"]["music"] == -1.0
    # Bestehender Wert bleibt (Merge, kein Replace).
    assert ov["base"]["homepods"]["afternoon"] == 0.50


def test_matrix_patch_none_deletes_cell_and_prunes():
    ov = L.apply_matrix_patch({}, {"base": {"homepods": {"afternoon": 0.50}}})
    ov = L.apply_matrix_patch(ov, {"base": {"homepods": {"afternoon": None}}})
    assert ov == {}  # leere Maps werden geprunt → kein Müll im Store


def test_matrix_patch_ignores_garbage():
    ov = L.apply_matrix_patch(
        {}, {"base": {"homepods": {"afternoon": "laut", "forenoon": 0.4}},
             "bogus_dim": {"x": 1}, "scenario_off": "nope"}
    )
    assert ov == {"base": {"homepods": {"forenoon": 0.4}}}  # nur valide Zelle bleibt


def test_matrix_patch_does_not_mutate_input():
    src = {"base": {"homepods": {"afternoon": 0.50}}}
    L.apply_matrix_patch(src, {"base": {"homepods": {"afternoon": 0.20}}})
    assert src["base"]["homepods"]["afternoon"] == 0.50  # Eingabe unverändert


def test_volume_idle_sticky_resume_no_change():
    # Stick auf 0.35, dann Resume auf identischem Pfad → gleiches Target, kein Ramp.
    _d1, s1 = _decide(_inp(homepods_state="playing"))
    _d2, s2 = _decide(_inp(), state=s1)                       # sticky idle 0.35
    d3, _s3 = _decide(_inp(homepods_state="playing"), state=s2)
    assert d3.volume_policy == C.VOL_POLICY_MEDIA
    assert d3.volume_target_homepods == 0.35  # unverändert → Apply-No-op


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
    # gaming_default (kein Grind, kein PC) verdrängt HomePods.
    d, _ = _decide(_inp(context=C.CTX_GAMING, subcontext="gaming_default",
                        homepods_state="playing"))
    assert d.homepods_should_pause is True
    assert d.action == C.ACTION_PAUSE


# --------------------------------------------------- PC-Gaming (FLEET-101)
def test_pc_gaming_flag():
    d, _ = _decide(_inp(context=C.CTX_GAMING, device=C.DEV_PC))
    assert d.is_pc_gaming is True


def test_pc_gaming_does_not_pause_homepods():
    # FLEET-101: PC-Gaming → Game-Audio im Headset, Raum-Musik läuft weiter.
    d, _ = _decide(_inp(context=C.CTX_GAMING, device=C.DEV_PC,
                        subcontext="gaming_default", homepods_state="playing"))
    assert d.homepods_should_pause is False
    assert d.action != C.ACTION_PAUSE


def test_pc_gaming_homepods_normal_denon_off():
    d, _ = _decide(_inp(context=C.CTX_GAMING, device=C.DEV_PC,
                        subcontext="gaming_default"))
    assert d.volume_target_homepods == 0.35   # normale Musik-Baseline
    assert d.volume_target_denon == 0.0        # Denon aus
    assert d.volume_policy == C.VOL_POLICY_MEDIA
    assert d.volume_reason == "pc_gaming_homepods_denon_off"


def test_pc_gaming_headset_still_plays_music():
    # Robust gegen Title-Classifier-Headset-Bugs (FLEET-97): am Device gebunden,
    # nicht am headset-Enum → auch im gaming_headset-Subcontext läuft Musik weiter.
    d, _ = _decide(_inp(context=C.CTX_GAMING, device=C.DEV_PC,
                        subcontext="gaming_headset", headset_active=True,
                        homepods_state="playing"))
    assert d.is_pc_gaming is True
    assert d.homepods_should_pause is False
    assert d.volume_target_homepods == 0.35
    assert d.volume_target_denon == 0.0


def test_pc_grind_pc_routing_wins_denon_off():
    # PC + grind: PC-Gaming-Routing übersteuert die Grind-Denon-Kulisse.
    d, _ = _decide(_inp(context=C.CTX_GAMING, device=C.DEV_PC,
                        subcontext=C.SUB_GAME_GRIND))
    assert d.is_pc_gaming is True
    assert d.is_grind is True
    assert d.volume_target_homepods == 0.35
    assert d.volume_target_denon == 0.0   # NICHT Grind-Kulisse (0.28)


def test_ps5_gaming_still_pauses_regression():
    # Regression-Guard: PS5 bleibt unverändert (verdrängt HomePods).
    d, _ = _decide(_inp(context=C.CTX_GAMING, device="ps5",
                        subcontext="gaming_default", homepods_state="playing"))
    assert d.is_pc_gaming is False
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
    d, _ = _decide(_inp(context=C.CTX_TV, entertainment_active=True, denon_active=True,
                        day_state="afternoon"))
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
                        opening_any_open=True, day_state="afternoon"))
    # device==denon → denon_path True → window allein blockt nicht mehr.
    assert d.denon_audio_path is True
    assert d.subwoofer_allowed is True


# ----------------------------------------- R-§6 Subwoofer-Dayphase-Fenster (FLEET-39)
def _sub_inp(**kw):
    base = dict(context=C.CTX_TV, entertainment_active=True, denon_active=True)
    base.update(kw)
    return _inp(**base)


def test_subwoofer_off_outside_dayphase_window():
    # late_night ∉ erlaubte Phasen → aus, trotz Entertainment + Denon-Path.
    d, _ = _decide(_sub_inp(day_state="late_night"))
    assert d.subwoofer_allowed is False
    assert d.subwoofer_block_reason == "dayphase_window"


def test_subwoofer_off_early_morning():
    d, _ = _decide(_sub_inp(day_state="early_morning"))
    assert d.subwoofer_allowed is False
    assert d.subwoofer_block_reason == "dayphase_window"


def test_subwoofer_off_late_morning_before_0900():
    # Erlaubte Phase, aber Wanduhr < 09:00 (Sommer-Fall) → Floor blockt.
    d, _ = _decide(_sub_inp(day_state="late_morning", local_minute_of_day=8 * 60 + 30))
    assert d.subwoofer_allowed is False
    assert d.subwoofer_block_reason == "before_0900"


def test_subwoofer_on_late_morning_at_0900():
    d, _ = _decide(_sub_inp(day_state="late_morning", local_minute_of_day=9 * 60))
    assert d.subwoofer_allowed is True


def test_subwoofer_unknown_time_allows_in_phase():
    # Lokalzeit unbekannt → Phase reicht (kein Floor-Block).
    d, _ = _decide(_sub_inp(day_state="afternoon", local_minute_of_day=None))
    assert d.subwoofer_allowed is True


def test_subwoofer_all_allowed_phases_on():
    for ph in ("late_morning", "forenoon", "afternoon", "early_evening", "late_evening"):
        d, _ = _decide(_sub_inp(day_state=ph, local_minute_of_day=12 * 60))
        assert d.subwoofer_allowed is True, ph


# ------------------------------------------------- R18 Track-Boost / R19 Mute
def test_track_boost_adds_offset():
    # Musik-Enum 1 (boost) → HomePods-Ziel + boost_offset (0.45 + 0.15).
    d, _ = _decide(_inp(homepods_state="playing", day_state="afternoon",
                        homepods_music_enum=C.MUSIC_ENUM_BOOST))
    assert d.track_boost_applied is True
    assert d.volume_target_homepods == 0.60


def test_track_boost_blocked_in_work_home():
    d, _ = _decide(_inp(homepods_state="playing", day_state="afternoon",
                        homepods_music_enum=C.MUSIC_ENUM_BOOST,
                        activity_context="work_home"))
    assert d.track_boost_applied is False
    assert d.volume_target_homepods == 0.45  # ohne Boost


def test_track_boost_blocked_in_quiet():
    # Quiet → Ducked-Zweig, Boost greift strukturell nicht.
    d, _ = _decide(_inp(homepods_state="playing", day_state="afternoon",
                        quiet_mode=True, homepods_music_enum=C.MUSIC_ENUM_BOOST))
    assert d.track_boost_applied is False
    assert d.volume_policy == C.VOL_POLICY_DUCKED


def test_music_mute_forces_zero():
    # Musik-Enum 2 (mute) → HomePods hart auf 0, übersteuert die Formel.
    d, _ = _decide(_inp(homepods_state="playing", day_state="afternoon",
                        homepods_music_enum=C.MUSIC_ENUM_MUTE))
    assert d.music_muted is True
    assert d.volume_target_homepods == 0.0


def test_music_mute_does_not_touch_denon_in_grind():
    # Grind: HomePods gemutet (0), Denon-Kulisse unberührt (Baseline + Grind-Offset).
    d, _ = _decide(_inp(context=C.CTX_GAMING, subcontext=C.SUB_GAME_GRIND,
                        day_state="afternoon", homepods_music_enum=C.MUSIC_ENUM_MUTE))
    assert d.volume_target_homepods == 0.0
    assert d.volume_target_denon == 0.18  # 0.30 - 0.12


# ----------------------------------------------------- R21/R22 Nudge + Boost-Reset
def test_manual_nudge_raises_homepods():
    base = _decide(_inp(homepods_state="playing", day_state="afternoon"))[0]
    d, _ = _decide(_inp(homepods_state="playing", day_state="afternoon",
                        manual_nudge=0.10))
    assert d.volume_target_homepods == round(base.volume_target_homepods + 0.10, 3)


def test_manual_nudge_negative_lowers_homepods():
    d, _ = _decide(_inp(homepods_state="playing", day_state="afternoon",
                        manual_nudge=-0.30))
    assert d.volume_target_homepods == 0.15  # 0.45 - 0.30


def test_manual_nudge_raises_denon():
    base = _decide(_inp(context=C.CTX_TV, day_state="afternoon"))[0]
    d, _ = _decide(_inp(context=C.CTX_TV, day_state="afternoon", manual_nudge=0.10))
    assert d.volume_target_denon == round(base.volume_target_denon + 0.10, 3)


def test_boost_suppressed_disables_track_boost():
    # R22: gleicher Boost-Track, aber Boost-Reset aktiv → kein Offset.
    d, _ = _decide(_inp(homepods_state="playing", day_state="afternoon",
                        homepods_music_enum=C.MUSIC_ENUM_BOOST,
                        boost_suppressed=True))
    assert d.track_boost_applied is False
    assert d.volume_target_homepods == 0.45  # ohne Boost


def test_volume_breakdown_reports_nudge():
    bd = L.volume_breakdown(
        _inp(homepods_state="playing", day_state="afternoon", manual_nudge=0.10),
        C.AUDIO_OWNER_HOMEPODS, False, L.VolumeSettings(),
    )
    assert bd["homepods"]["manual_nudge"] == 0.10
    assert bd["denon"]["manual_nudge"] == 0.0  # spielt nicht → kein Nudge


# ----------------------------------------- audio_scenario / Desired-Audio (FLEET-85)
def test_scenario_idle_constellation_is_music_baseline():
    # Kein Owner, HomePods spielen nicht → trotzdem MUSIC (nicht idle). Der Fix.
    d, _ = _decide(_inp())
    assert d.audio_owner == C.AUDIO_OWNER_NONE
    assert d.audio_scenario == C.AUDIO_SCENARIO_MUSIC
    assert d.audio_scenario_label == "Musik"


def test_scenario_music_when_homepods_playing_with_station():
    d, _ = _decide(_inp(homepods_state="playing", radio_station="GAYFM"))
    assert d.audio_scenario == C.AUDIO_SCENARIO_MUSIC
    assert d.audio_scenario_detail == "GAYFM"


def test_scenario_station_detail_in_idle_baseline():
    # Auch in der Baseline (owner NONE) trägt der gewählte Sender ins Detail.
    d, _ = _decide(_inp(radio_station="  byte.fm  "))
    assert d.audio_scenario == C.AUDIO_SCENARIO_MUSIC
    assert d.audio_scenario_detail == "byte.fm"   # getrimmt


def test_scenario_tv_with_context_detail():
    d, _ = _decide(_inp(context=C.CTX_TV))
    assert d.audio_scenario == C.AUDIO_SCENARIO_TV
    assert d.audio_scenario_detail == C.CTX_TV
    d2, _ = _decide(_inp(context=C.CTX_STREAMING))
    assert d2.audio_scenario == C.AUDIO_SCENARIO_TV
    assert d2.audio_scenario_detail == C.CTX_STREAMING


def test_scenario_gaming_with_platform_detail():
    d, _ = _decide(_inp(context=C.CTX_GAMING, device="ps5"))
    assert d.audio_scenario == C.AUDIO_SCENARIO_GAMING
    assert d.audio_scenario_detail == "ps5"


def test_scenario_grind_is_gaming():
    d, _ = _decide(_inp(context=C.CTX_GAMING, subcontext=C.SUB_GAME_GRIND, device="ps5"))
    assert d.audio_scenario == C.AUDIO_SCENARIO_GAMING


def test_scenario_private_via_context():
    d, _ = _decide(_inp(context=C.CTX_PRIVATE))
    assert d.audio_scenario == C.AUDIO_SCENARIO_PRIVATE


def test_scenario_off_when_bio_sleep():
    # Sleep dominiert (R25) → off, auch wenn ein TV-Context anliegt.
    d, _ = _decide(_inp(bio_sleep=True, context=C.CTX_TV))
    assert d.audio_scenario == C.AUDIO_SCENARIO_OFF
    assert d.audio_scenario_label == "Aus"


def test_scenario_quiet_is_overlay_not_scenario():
    # Quiet ist ein Volume-Overlay → Szenario bleibt die Baseline (music), nicht „quiet".
    d, _ = _decide(_inp(quiet_mode=True, homepods_state="playing"))
    assert d.volume_policy == C.VOL_POLICY_DUCKED
    assert d.audio_scenario == C.AUDIO_SCENARIO_MUSIC


def test_scenario_exposed_in_as_dict():
    d, _ = _decide(_inp(homepods_state="playing", radio_station="GAYFM"))
    data = d.as_dict()
    assert data["audio_scenario"] == C.AUDIO_SCENARIO_MUSIC
    assert data["audio_scenario_label"] == "Musik"
    assert data["audio_scenario_detail"] == "GAYFM"
