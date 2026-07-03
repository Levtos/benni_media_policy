# Changelog

## 0.15.1 - audio_owner: Schlaf ≠ private_stack (FLEET-221)

- **`bio_sleep` bekommt einen eigenen Owner `sleep`** statt `private_stack`.
  Bisher teilten sich Schlaf und Privat-Session (context/stash) das Label
  `AUDIO_OWNER_PRIVATE = "private_stack"` → über Nacht stand `audio_owner` auf
  `private_stack`, obwohl keine Stash-/Private-Session lief (nur `bio_state=sleep`
  ab dem Zubettgehen). Das führte in die Irre.
- **Reine Benennung, kein Verhaltens-Impact:** Sleep verdrängt weiter die
  HomePods (`competes_with_homepods` enthält jetzt `AUDIO_OWNER_SLEEP`), das
  Szenario bleibt `off` und die Volume-Policy `muted` (R25). Cockpit/Umbrella
  zeigen jetzt `sleep` statt `private_stack` im Schlaf.
- `owner_reason` für Schlaf = `"sleep"` (vorher `"private_time"`). 92 Tests grün.

## 0.15.0 - Musik-Baseline entfernt (Wurzel-Kur statt Recovery-Hack)

- **Debouncte Musik-Baseline komplett raus** (`music_baseline_candidate`,
  `homepods_stably_idle`, der 30 s-Coordinator-Debounce + One-Shot-Timer, das
  `music_baseline_active`-Debug-Feld). Ihr einziger Zweck war, den nach
  HA-Neustart abgerissenen HomePods-Stream zurückzuholen. Dieser Abriss ist seit
  **media_apply v0.15.2** am Ursprung weg: Apply pausiert nicht mehr auf
  `presence_unknown` (Reload-Flap) → der Stream überlebt Neustarts, es gibt
  nichts mehr zu „recovern".
- **Warum raus statt lassen:** die Baseline war am Morgen eine **zweite**
  `start_radio`-Quelle neben der Wake-Sequenz → beide feuerten quasi gleichzeitig
  auf Music Assistant → Playback-Lock-Contention (MA-Timeout, ~30 s idle↔playing-
  Flapperei = kaputte Weckmusik). Ohne Baseline feuert nur noch die Wake-Sequenz.
- **Verhalten jetzt:** Musik startet ausschließlich über echte Trigger — Wecken
  (R23), Heimkehr-Resume (`pre_pause_mode`), TV-aus-Resume. Kalt-Idle zuhause
  startet NICHT von selbst (kam real nie vor — immer über einen Trigger).
- `decide_action`/`decide_volume`/`volume_breakdown` verlieren den
  `music_baseline`-Parameter; WS-`status`/`debug` das `music_baseline_active`-Feld
  (von Umbrella/Apply/Frontend nicht konsumiert → kein Contract-Bruch). 91 Tests
  grün.

## 0.14.1 - manual_stop nur noch explizit (Stream-Abriss ≠ Stopp)

- **Kritischer Fix zur Baseline (v0.14.0).** `manual_stop` wurde aus jedem
  `playing→idle` ohne konkurrierenden Stack abgeleitet — also auch aus einem
  **Stream-Abriss** (HA-Neustart, MA-Reconnect, Netz-Blip). Das setzte
  `manual_stop=true`, was die Baseline-Recovery blockierte → ein abgerissener
  Stream kam NIE zurück (live: nach Deploy-Restart `manual_stop` stuck, Musik
  tot bis zum Wecken). Ein Abriss ist nicht von einer User-Pause unterscheidbar
  (beide → `idle`).
- Fix: `manual_stop` kommt **nur noch vom expliziten User-Stopp**
  (`media_stop_latch`), nicht aus der `playing→idle`-Ableitung. Stream-Abriss →
  kein manual_stop → Baseline holt zurück. Echter Stopp → `input_boolean.
  media_stop_latch` setzen.
- Prefill: `media_stop_latch_entity` → `input_boolean.media_stop_latch` (wie
  apply). **NICHT** auf die eigene `manual_stop`-Ausgabe binden — das war ein
  Selbst-Latch, der bis zum Wecken klebte. **Wer den Slot manuell auf
  `binary_sensor.system_benni_media_policy_manual_stop` gebunden hat, muss das
  in den Optionen entfernen/umhängen.**

## 0.14.0 - Debouncte Musik-Baseline (Restart/Dropout-Recovery)

- **Musik-Baseline wieder da, aber entkoppelt vom Churn.** Nach v0.13.0 (Baseline
  ganz raus) startete ein HA-Neustart die Musik nicht mehr wieder: der HomePod/
  MA-Stream reißt beim Neustart physisch ab, und ohne Baseline holte ihn nichts
  zurück (Benni musste manuell gayfm klicken). Jetzt: `music_baseline_candidate`
  startet den Radio-Stream, **aber nur wenn die HomePods stabil ≥30 s nicht
  spielen** (`homepods_stably_idle`, Coordinator-Debounce mit One-Shot-Timer).
  Der Restore-Flap (~10 s) und Track-/Sender-Gaps lösen ihn NICHT aus → kein
  Geflacker wie in Codex' Dauer-Level (v0.12.2).
- **Nur wenn Musik spielen darf:** `owner == none` schließt TV/Gaming/Denon aus
  (Benni: „nicht bei TV"); away/sleep/quiet/manual-stop/unknown-Presence blocken
  weiter. Nur im `not auto_paused`-Zweig → der away/TV-`pre_pause_mode`-Resume
  (sofort, v0.13.0) behält Vorrang; die Baseline fängt nur den Fall OHNE
  Erinnerung ab (Kalt-Idle / Restart-Abriss).
- Volume startet hörbar (kein erster Tick auf 0). `music_baseline_active` wieder
  als Debug-Feld.

## 0.13.1 - unknown-Presence hält, statt zu pausieren

- **Reload/Restart-Pause-Bug behoben.** Bei einem Reload flappt `presence_state`
  kurz auf `unknown` (media_state-Startup-Transiente). `unknown` war noch ein
  Hard-Block → `pause_homepods` → Musik ging aus und kam (mangels Resume-
  Erinnerung bei unknown) nicht zurück. Live gesehen nach dem v0.13.0-Deploy.
- Fix: `unknown`/degraded ist **kein Block** mehr. Es hält nur Auto-Start/Resume
  zurück (`presence_holds_resume`: wir wissen nicht, ob zuhause), fasst aber
  **laufende Musik nicht an** (kein Pause, kein Volume-0). Nur echtes `abwesend`
  /away_gate blockt weiterhin hart. Defensiv-korrekt: unbekannt ≠ weg.

## 0.13.0 - Presence als Trigger (Dauer-Baseline entfernt)

- **`music_baseline_active` komplett entfernt.** Der in 0.12.2 eingeführte
  Dauer-Level („HomePods zuhause idle → dauernd `start_radio` fordern") war die
  Wurzel des Radio-Restart-Churns beim HA-Boot: er zwang Apply, den im
  Restore-Fenster ohnehin anlaufenden Stream neu zu starten. Kein Auto-Start
  mehr bei jedem Idle-Tick.
- **Presence-away = konkurrierender Stack wie der TV.** Statt des alten
  Hard-Blocks (der `auto_paused`/`pre_pause_mode` löschte und damit die
  Resume-Erinnerung zerstörte — genau das erzwang den Baseline-Hack) pausiert
  Away jetzt MIT erhaltener Resume-Erinnerung. Heimkehr löst das Resume über die
  bestehende Maschinerie aus (`start_radio`/`resume`, EINE Flanke), Volume via
  sticky `last_hp_media_target` (FLEET-153). „Semantisch dieselbe Logik wie
  Wake/TV-aus, nur ein anderer Triggerpunkt."
- Netto: Musik läuft über echte Trigger (Wake, TV-aus, Heimkehr), nicht als
  Dauer-Forderung. Macht den Apply-Startup-Guard (v0.14.7–0.14.9) langfristig
  überflüssig. `unknown`/degraded Presence hält weiterhin ohne Resume-Kandidat.

## 0.12.2 - Music Baseline Home Restore

- Start the HomePods radio baseline again when presence is home, a station is
  selected, and no higher-priority media stack or manual stop is active.
- Keep `audio_owner` observational while using a separate music-baseline intent
  for the `start_radio` action and audible HomePods target volume.
- Preserve Away/unknown-presence blocking for music baseline, resume, volume
  apply, and subwoofer policy.

## 0.12.1 - FLEET-212: Media Away Gate Fix

- Consume `sensor.benni_media_state_presence_state` and
  `binary_sensor.benni_media_state_away_gate`.
- Treat Away/unknown presence as a highest-priority media block so the music
  baseline, resume, volume apply, and subwoofer policy do not keep audio alive.
- Emit a HomePods pause decision when Away is active and HomePods are playing.

## 0.9.1 - Master ReBind

- Repointed the Benni Denon active-source default from
  `sensor.benni_device_living_avr` to `sensor.benni_master_denon`.
- Migrates saved Denon active-source bindings from the retired Atomic/Device
  IDs to the Denon master during setup and ConfigEntry migration.
- Normalizes legacy entity IDs in the options flow so old Denon IDs do not stay
  stored as manual overrides.

## 0.8.2 - FLEET-94

- Force existing ConfigEntry source migrations for the openings master on setup and via config entry version 3.

## 0.8.1 - FLEET-94

- Rebind opening offset input to the Core Devices openings master.
- Read `any_not_closed` from `sensor.benni_combined_openings` so tilted openings still apply the media volume offset.
- Migrate previous opening combined bindings to the master entity.

## 0.4.1 — FLEET-54 Core Day-State Prefill

- `day_state_entity` im Benni-Prefill zeigt jetzt auf
  `sensor.benni_combined_context_day_state` statt auf den nicht existierenden
  `sensor.benni_core_day_state`.
- Bestehende ConfigEntries migrieren den alten Slot automatisch.

## 0.1.0 — scaffold

### Realign (Step 1.5 — gelockte Profil-Mechanik, FLEET-33 / FLEET-31)

- Device-Name **profil-getrieben** (`{label} Media Policy`) → Entity-Slug
  `<profil>_media_policy_*` (benni/eltern), `suggested_object_id` entfernt.
- Profil-Config + Auto-Bind 1:1 aus `benni_core_state`: Add-Flow `user`
  (Profil-Select) → `entities` (Override-only-Storage) → `options` (Apply),
  `coordinator._entity_id` (options ▶ data ▶ PROFILE_PREFILL[profile]),
  Existenz-Filter im Prefill.
- unique_id domain+entry-scoped; Single-Instance via `_async_current_entries()`.
- WS `get_status` um `profile` / `profile_label` ergänzt.
- `PROFILE_PREFILL[benni]` → `sensor.benni_media_state_*`, `[eltern]` vorerst
  leer (zeigt später auf `eltern_media_state_*`); keine harten Fallback-Slugs,
  Existenz-Filter regelt die Deploy-Reihenfolge.
- **Quiet entfernt:** `quiet_mode` lebt jetzt in `benni_media_state` (L1,
  FLEET-31) und wird hier nur konsumiert (Input-Slot).
- Apply bleibt gated (Shadow-safe); event-driven Coordinator beibehalten.


- Step-1-Scaffold: lauffähiges, leeres Skeleton der Integration.
- Profil-Hub (benni/eltern) + Auto-Bind (Override ▶ Profil-Map ▶ leer); benni-Profil
  bindet media_state-Entities vor (Konsum-Vertrag via Entity-State).
- Single-Instance Config-Flow (unique_id `benni_media_policy_singleton`) + Options-Menü-Gerüst.
- DataUpdateCoordinator (event-driven, kein Polling) mit HA-freier `logic.decide()`-Stub;
  Apply gated an `apply_enabled` (Default False = Shadow-safe).
- Entity-Roster (Sensoren + Binary-Sensoren) aus `coordinator.data`, stabile Defaults.
- WebSocket-Command `benni_media_policy/get_status` + Vanilla-Debug-Panel.
- Smoke-Tests grün. **Keine Fachlogik portiert.**
