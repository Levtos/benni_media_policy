# FLEET-212 Media Away Gate / Music Baseline Handoff

Datum: 2026-07-01

Owner laut Fleet-Matrix: Claude Code (`media_policy`, `media_apply`, `media_state`, `benni_media`).
Codex hat diese Hotfix-Kette mit Benni-Freigabe als Release-/Bugfix-Einsatz bearbeitet.

## Kurzfassung

Die Away-Gate-Kette wurde released und danach ein Folgefehler in der Musik-Baseline behoben.

- `benni_media_state v0.9.0`: liefert `presence_state` und `away_gate`.
- `benni_media_policy v0.12.1`: blockiert Musik-Baseline, Resume, Volume-Apply und Subwoofer bei Away/unknown presence.
- `benni_media_apply v0.14.6`: pausiert HomePods, schaltet Denon/Subwoofer aus und blockiert Radio-Restart/Wake bei Away.
- `benni_media v0.6.2`: UX-Fix, damit die Overview bei realem Idle/Off nicht mehr die Policy-Baseline `Musik · <Sender>` als aktuell laufendes Szenario anzeigt.
- `benni_media_policy v0.12.2`: eigentlicher Hoerbarkeits-Hotfix. Bei `zuhause`, gewaehltem Radiosender und idle HomePods erzeugt die Policy wieder `action=start_radio` und ein hoerbares HomePods-Target.

## Warum der zweite Hotfix noetig war

Benni hat nach dem UX-Fix korrekt hinterfragt, dass Musik weiterhin nicht hoerbar lief, weil das Volume auf `0` stand. Der Raw-Dump zeigte:

- `presence_state = zuhause`
- `away_gate = false`
- `state.context = idle`
- `policy.audio_owner = none`
- `policy.audio_scenario = music`
- `policy.audio_scenario_detail = gayfm`
- `policy.volume_policy = idle`
- `policy.volume_target_homepods = 0`
- `apply.plan.homepods_action = none`
- HomePods waren `idle`, Volume `0`; Denon/Subwoofer waren aus.

Das war kein Apply-Ausfuehrungsfehler: `benni_media_apply` bekam keinen Auftrag, weil die Policy nur die Desired-Audio-Baseline (`music/gayfm`) ausdrueckte, aber keinen aktiven Start-/Volume-Intent fuer die Home-Baseline lieferte.

Fix in `benni_media_policy v0.12.2`:

- `audio_owner` bleibt beobachtete Wahrheit (`none`, solange HomePods nicht spielen).
- Neue interne Policy-Ableitung `music_baseline_active` aktiviert nur den Sollpfad.
- Wenn `zuhause`, Sender vorhanden, keine Away/unknown presence, kein Manual-Stop, keine konkurrierende Medienlogik: `action=start_radio`, `volume_policy=media`, `volume_target_homepods=<Dayphase-Baseline>`, `volume_target_denon=0`.
- Away/unknown presence und Manual-Stop blockieren weiterhin.

Konkreter Simulationsoutput fuer `zuhause + gayfm + HomePods idle + afternoon`:

```text
action=start_radio
volume_policy=media
volume_target_homepods=0.45
volume_target_denon=0.0
audio_owner=none
audio_scenario=music
audio_scenario_detail=gayfm
```

## Releases / PRs

- `benni_media_state v0.9.0`
  - PR: https://github.com/Levtos/benni_media_state/pull/7
  - Release: https://github.com/Levtos/benni_media_state/releases/tag/v0.9.0
  - Merge: `b25ee56a111723cfe14df0298b91d6efcb2531d6`

- `benni_media_policy v0.12.1`
  - PR: https://github.com/Levtos/benni_media_policy/pull/10
  - Release: https://github.com/Levtos/benni_media_policy/releases/tag/v0.12.1
  - Merge: `4bb6936ed82524ef4ebb2fa5cf3c939d3c09e453`

- `benni_media_apply v0.14.6`
  - PR: https://github.com/Levtos/benni_media_apply/pull/15
  - Release: https://github.com/Levtos/benni_media_apply/releases/tag/v0.14.6
  - Merge: `8816f70993d498f908cec505b9940c372e29b3af`

- `benni_media v0.6.2`
  - PR: https://github.com/Levtos/benni_media/pull/5
  - Release: https://github.com/Levtos/benni_media/releases/tag/v0.6.2
  - Merge: `fc9f013b44e993194f23ad72b3d4244193291c21`

- `benni_media_policy v0.12.2`
  - PR: https://github.com/Levtos/benni_media_policy/pull/11
  - Release: https://github.com/Levtos/benni_media_policy/releases/tag/v0.12.2
  - Fix commit: `6b23c0c41d1c8ea5665aa9830f0130523f86b7b3`
  - Merge: `5ee3c6d0c5c53dd43d2b3d8a59e0b6c072024b79`

## Gates

- `benni_media_state v0.9.0`: `pytest` 51 passed, `compileall` green.
- `benni_media_policy v0.12.1`: `pytest` 87 passed, `compileall` green.
- `benni_media_apply v0.14.6`: `pytest` 105 passed, `compileall` green.
- `benni_media v0.6.2`: `compileall` green, `node --check custom_components/benni_media/frontend/app/main.js` green.
- `benni_media_policy v0.12.2`: `pytest` 88 passed, `compileall` green.
- `benni_media_apply` was rechecked after the v0.12.2 policy fix: `pytest` 105 passed, `compileall` green.

Ruff in `benni_media_policy` still reports existing repository style backlog (`I001`, broad `UP045` Optional-modernization). No GitHub status checks were configured on PR #11.

## Deploy / Reload

Benni macht Pull/Deploy/Reload/Restart selbst.

Recommended order if the full chain is not deployed yet:

1. `benni_media_state`
2. `benni_media_policy`
3. `benni_media_apply`
4. `benni_media`

If the Away-Gate chain is already deployed and only the latest baseline fix is missing:

1. `benni_media_policy`
2. `benni_media_apply`
3. `benni_media`

## Live Verification For Claude

After deploy/reload on Einhornzentrale (`192.168.178.106:8123`), verify these states from the Media cockpit or raw entities:

- Away case:
  - `sensor.system_benni_media_state_presence_state = abwesend` or away gate on.
  - `binary_sensor.system_benni_media_state_away_gate = on`.
  - Policy: `audio_scenario=off`, `volume_apply_allowed=false`, `homepods_should_pause=true` when HomePods are playing.
  - Apply: HomePods pause, Denon off, Subwoofer off; radio restart/wake suppressed.

- Home baseline case:
  - `presence_state = zuhause`
  - selected `input_select.media_radio_station = gayfm` or another valid station.
  - HomePods initially idle/paused/off-equivalent but configured.
  - Policy should show `action=start_radio`, `volume_policy=media`, `volume_target_homepods > 0`, `volume_target_denon=0`, `audio_owner=none`, `audio_scenario=music`.
  - Apply should execute `start_radio` and set/ramp HomePods volume.

- Manual stop guard:
  - If `media_stop_latch` is on, baseline must not restart.

## Plane / Fleet Board Status

Codex attempted to update/create the Plane FLEET card, but the Plane MCP returned HTTP 404 for both `list_projects` and `list_work_items` on 2026-07-01. This was not worked around silently.

When Plane access is restored, update or create a FLEET card in module `Integration (Owner)` / `media_policy` with:

- Title suggestion: `Media Away Gate follow-up: restore audible music baseline at home`
- Owner: Claude Code
- State: `Testing` until Benni/Claude live-verify on Einhornzentrale, then `Live`.
- Summary: Codex emergency hotfix released `benni_media_policy v0.12.2`; fixes `zuhause + station + idle HomePods` producing `action=none` and target `0`.
- Links: PR #11, release `v0.12.2`, this handoff file.
- Note: `benni_media_apply` did not need code changes; it already executes `start_radio` plus volume when Policy emits them.

