# FAHRPLAN — benni_media_policy

L2 Policy. Aus `bennis_toolbox/.../benni_media_context/` extrahiert (1→2-Split:
Feeder `benni_media_state` + diese Policy).

## Step 1 — Scaffold ✅ (0.1.0)

Lauffähiges, leeres Skeleton, Struktur gespiegelt von `benni_light_policy`:
Hub + Auto-Bind + WS-Contract + Vanilla-Panel. Apply gated (Shadow-safe).
**Keine Fachlogik.**

## Step 2 — Logik-Extraktion (offen)

- `decide()`-Body aus `benni_media_context` (orchestrator.py / volume_orchestrator.py)
  nach `logic.py` heben (HA-frei). Volume/Ducking/Subwoofer + Audio-Owner (pause/resume/radio).
- Inputs-Contract finalisieren; Eingänge aus media_state über Entity-State lesen.
- Pure-logic-Tests übernehmen/anpassen.

## Step 3 — Lastenheft (offen)

- Reviewtes Lastenheft einarbeiten: Verhaltens-Spec, Konsum-Vertrag
  media_policy → media_state (Entity-State), B2-Fix-Auswirkungen.
- Quiet/Private-Schichtgrenze: Detection bleibt ggf. in media_state, Policy nur Konsum.
- Entity-Roster finalisieren (aktuell vorläufig).
- Apply erst nach Verifikation aktivieren (`apply_enabled`).

## audio_scenario — Desired-Audio-Wahrheit ✅ (0.7.0, FLEET-85)

Neuer Sensor `sensor.<profil>_media_policy_audio_scenario`: die **immer aus der
Konstellation abgeleitete** Soll-Audio-Wahrheit, unabhängig vom beobachtbaren
Player-Zustand (idle/unavailable/playing). State = Enum
(`off`/`private`/`gaming`/`tv`/`music`), Attribute `audio_scenario_label`
(human-readable) + `audio_scenario_detail` (Sender/Plattform/Source).

**Kernregel (Benni):** kein Screen-/Sleep-Szenario aktiv → **Musik ist die
Baseline** (nicht „idle"). Fixt den Umbrella-„idle"-Bug: `owner == NONE`
(HomePods spielen gerade nicht) ⇒ `music`, nicht idle. Quiet bleibt ein
Volume-Overlay (kein Szenario — die Umbrella komponiert das Leise-Badge aus
`quiet_mode`). Sender-Detail aus `input_select.media_radio_station`
(`CONF_RADIO_STATION`). Pure-Logic `decide_audio_scenario`, 10 neue Tests.

Konsumenten: **FLEET-86** (Umbrella-Status zeigt audio_scenario statt
media_context), **FLEET-84** (media_apply converge-to-desired — re-assert Soll
bei Drift/Reconnect, zielt auf *aktuelles* audio_scenario, nie auf Snapshot).

## FLEET-212 / Media Away Gate Follow-up ✅ (0.12.1 / 0.12.2)

Away/unknown presence blockiert die Musik-Baseline, Resume, Volume-Apply und
Subwoofer-Policy. Der Folgefix `0.12.2` stellt sicher, dass die Musik-Baseline
bei `zuhause`, gewaehltem Radiosender und idle HomePods wieder aktiv startet
(`action=start_radio`, `volume_policy=media`, HomePods-Target > 0), ohne
`audio_owner` als beobachtete Wahrheit zu verfaelschen.

Claude-Handoff: `docs/fleet-212-media-away-gate-handoff.md`.

## Konsum-Vertrag

Konsumiert `benni_media_state` **nur über Entity-State** — nie per Python-Import.
Slug-Stabilität wahren.

## Verifikation

Lokal kein HA/dulwich → `py_compile` + pure-logic-Tests. Rest live auf
`einhornzentrale` (Canary); `haos_benni` (Prod) bleibt unangetastet.
