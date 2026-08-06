# Phase 5 Sprint 2 — Operations Center Foundation

This sprint replaces the Desktop Companion prototype with the permanent Operations Center shell approved from the Tarkov-inspired design concept.

## Implemented

- Modern dark, translucent panel system with olive, amber, muted blue, and danger accents.
- Bundled and darkened operator background derived from the approved reference image.
- Persistent navigation for Dashboard, Live Raid, Markers, Reviews, PPE, Media, Tasks, Maps, and Settings.
- Dashboard status hierarchy for lifecycle, active raid, objectives, OBS, PPE, automatic log rules, review queue, and media availability.
- Clear Start Raid, End Raid, and Abort Raid controls with descriptive secondary text.
- Live marker history showing time, label, stable type, and source.
- Activity Log showing raid lifecycle changes, OBS state changes, marker triggers, Stream Deck sources, PPE changes, automatic log-rule changes, warnings, and errors.
- Dedicated Live Raid and Markers pages with native quick-marker actions.
- Embedded Raid Review workspace through Qt WebEngine, with browser fallback when WebEngine is unavailable.
- Recent review list and review-queue summary on the dashboard.
- Service and API settings page.
- Version alignment to `0.8.0`.

## Data behavior

The desktop remains a thin client. It polls the existing local API and does not duplicate backend authority. Timeline events are read from `/api/raids/{raid_id}/timeline`, so markers created by the desktop, Stream Deck plugin, marker helper, or another local caller appear in the same interface.

## Field validation

1. Start the Operations Center and confirm the local service reaches **SERVICE ONLINE**.
2. Start a raid and verify map, character, objective, raid ID, session timer, and OBS state.
3. Trigger markers from both the desktop and Stream Deck.
4. Confirm each marker appears in **Live Markers** and **Activity Log** with the correct source.
5. End the raid and confirm the Reviews page opens.
6. Complete and finalize the raid in the embedded review workspace.
7. Confirm recent reviews and the queue count refresh on the dashboard.

## Deferred to Sprint 3+

- Asynchronous End Raid media finalization and progress jobs.
- Native media clip and screenshot generation.
- Full native Qt replacement for every HTML review control.
- Dynamic map art, scoring cards, and advanced review analytics.
