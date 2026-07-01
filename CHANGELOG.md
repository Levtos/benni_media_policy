# Changelog

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
