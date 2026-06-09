# benni_media_policy

Audio-/Volume-Policy (L2) als eigenständige HACS-Custom-Integration.

Entscheidet **Audio-Owner** (pause/resume/radio) + **Volume/Ducking/Subwoofer**.
Konsumiert den Feeder
[`benni_media_state`](https://github.com/Levtos/benni_media_state) **ausschließlich
über Entity-State** (kein Python-Import). Apply ist **gated** (Shadow-safe,
Default aus) — wie `benni_light_policy`.

**Status:** `0.1.0` — Step-1-Scaffold. Lauffähiges, leeres Skeleton (Hub +
Auto-Bind + WS-Contract + Vanilla-Debug-Panel). **Keine Fachlogik portiert.**

## Schicht

L2 Policy — Teil des `benni_*`-Fleets. Entsteht im 1→2-Split aus
`bennis_toolbox/.../benni_media_context/` (Feeder `benni_media_state` + diese Policy).

## Entity-Roster (vorläufig — finalisiert das Lastenheft in Step 3)

| Entity | Bedeutung |
| --- | --- |
| `sensor.benni_media_policy_volume_target_homepods` | Ziel-Lautstärke HomePods |
| `sensor.benni_media_policy_volume_target_denon` | Ziel-Lautstärke Denon |
| `sensor.benni_media_policy_audio_owner` | aktueller Audio-Owner |
| `sensor.benni_media_policy_action` | nächste Aktion (pause/resume/radio/none) |
| `sensor.benni_media_policy_volume_policy` | aktive Volume-Policy |
| `binary_sensor.benni_media_policy_subwoofer_allowed` | Subwoofer erlaubt |
| `binary_sensor.benni_media_policy_homepods_should_pause` | HomePods sollen pausieren |
| `binary_sensor.benni_media_policy_homepods_resume_allowed` | Resume erlaubt |
| `binary_sensor.benni_media_policy_volume_apply_allowed` | Apply erlaubt (Gate) |

> Der Entity-Präfix folgt dem **Profil** (Device-Name, `has_entity_name`):
> Route Benni → `…benni_media_policy_*`, Route Eltern → `…eltern_media_policy_*`.
> (Quiet-Mode lebt in `benni_media_state` — L1, FLEET-31 — und wird hier nur konsumiert.)

## WebSocket

`benni_media_policy/get_status` → `{ profile, profile_label, apply_enabled, bindings, data }`.

## Roadmap

- **Step 1 (hier):** Scaffold. ✅
- **Step 2:** Policy-Logik aus `benni_media_context` (orchestrator / volume_orchestrator) extrahieren.
- **Step 3:** Reviewtes Lastenheft (Verhaltens-Spec, B2-Fix, Konsum-Vertrag) einarbeiten.

Siehe `FAHRPLAN.md`.
