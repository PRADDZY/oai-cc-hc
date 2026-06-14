# Guided Rescue Demo Design

## Goal

Turn the Cloudflare command center from a static proof dashboard into a 60-90 second
guided visual rescue scenario that can run reliably during a live pitch.

## Experience

The demo autoplays through eight phases:

1. Sentinel-1 flood intelligence arrives.
2. The flood belief grid expands across affected cells.
3. Victim hypotheses appear and become confirmed.
4. Eight drones launch and assume search, relay, aid, hold, and return roles.
5. The frontend requests a live advisory policy proposal through the Cloudflare Worker.
6. The service-reported safety metadata is visualized without claiming flight validation.
7. A visible operator gate records manual approval, safe hold, or an explicitly scripted
   demo-operator confirmation.
8. Aid reaches the confirmed victim and the mission resolves with outcome metrics.

The presenter can pause, resume, step forward, restart, and change playback speed.

## Visual Direction

The interface remains an industrial emergency command center, but the animated map is
the dominant surface. Flood cells reveal in waves, victim signals pulse, drone markers
move between cells, relay links connect the swarm, and the active event is highlighted.

The right rail changes with the current phase instead of displaying every proof detail
at once. Training evidence remains available in a compact proof drawer and final mission
summary.

## Architecture

- `scenario.ts` defines immutable phase snapshots, timing, map entities, and copy.
- `useMissionPlayback.ts` owns autoplay, pause, step, restart, speed, and phase changes.
- `api.ts` sends the policy request to the existing Worker mission-proposal endpoint.
- `App.tsx` composes the stage, map, controls, phase panel, roster, timeline, and proof.
- `styles.css` implements map motion, markers, relay links, phase transitions, and
  responsive layout without adding a runtime animation dependency.

## Live Policy Handoff

The scenario is deterministic except at the policy phase. At that phase the frontend
calls:

`POST /api/missions/<mission-id>/proposals`

The returned action, confidence, coordination vector, and safety metadata update the
scenario panel as advisory evidence. The guided rescue sequence remains deterministic;
a `search` proposal is presented as route-planning guidance rather than silently changed
into an aid action. A short timeout, malformed payload, `cloudflare-fallback`, or
`modal-fallback` response uses the existing scripted proposal, clearly labeled as a
resilient demo fallback.

Each playback run makes at most one request. Restart aborts the request and ignores late
responses from the previous run.

In autoplay, the approval phase displays a five-second "scripted demo operator" countdown.
Pause freezes the countdown. Approve advances immediately. Override records a safe hold
and pauses the scenario until the presenter uses Next or Restart. Next after an override
ends in a safe held outcome; it never displays aid delivery without approval.

## Safety And Truthfulness

- The interface always labels the scenario as simulation-only.
- Satellite data is described as a replay based on Sen1Floods11 training/evaluation data,
  not a live operational feed.
- Human approval is represented as manual input or an explicitly scripted demo operator,
  not autonomous real-world execution.
- Returned safety metadata is labeled as service-reported simulation output, not an
  operational flight-control guarantee.

## Testing

Tests cover:

- initial phase and autoplay progression;
- pause, next, speed, and restart controls;
- map/victim/drone changes across phases;
- live policy response rendering;
- failed, malformed, late, duplicate, and Cloudflare-fallback policy handling;
- manual approval, scripted demo approval, and safe-hold override behavior;
- final aided-victim and mission-complete state;
- existing Worker proof and active model rendering;
- reduced-motion behavior, keyboard-accessible proof disclosure, and mobile layout.

## Success Criteria

- A judge can understand the full detect-plan-approve-rescue loop without narration.
- The demo completes in 60-90 seconds at normal speed.
- The presenter can recover instantly with pause or restart.
- A backend outage does not break the visual sequence.
- The deployed Pages URL works on desktop and remains usable on mobile.
