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

## Konsum-Vertrag

Konsumiert `benni_media_state` **nur über Entity-State** — nie per Python-Import.
Slug-Stabilität wahren.

## Verifikation

Lokal kein HA/dulwich → `py_compile` + pure-logic-Tests. Rest live auf
`einhornzentrale` (Canary); `haos_benni` (Prod) bleibt unangetastet.
