# Changelog

## 0.1.0 — scaffold

- Step-1-Scaffold: lauffähiges, leeres Skeleton der Integration.
- Profil-Hub (benni/eltern) + Auto-Bind (Override ▶ Profil-Map ▶ leer); benni-Profil
  bindet media_state-Entities vor (Konsum-Vertrag via Entity-State).
- Single-Instance Config-Flow (unique_id `benni_media_policy_singleton`) + Options-Menü-Gerüst.
- DataUpdateCoordinator (event-driven, kein Polling) mit HA-freier `logic.decide()`-Stub;
  Apply gated an `apply_enabled` (Default False = Shadow-safe).
- Entity-Roster (Sensoren + Binary-Sensoren) aus `coordinator.data`, stabile Defaults.
- WebSocket-Command `benni_media_policy/get_status` + Vanilla-Debug-Panel.
- Smoke-Tests grün. **Keine Fachlogik portiert.**
