# Changelog

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
