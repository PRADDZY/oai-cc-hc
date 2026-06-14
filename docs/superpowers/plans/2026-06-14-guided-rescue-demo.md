# Guided Rescue Demo Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resilient 60-90 second guided rescue visualization with autoplay, presenter controls, animated swarm state, and one live policy checkpoint.

**Architecture:** Keep scenario data deterministic and separate from playback state. A small React hook advances immutable phase snapshots, while the existing API module provides proof data and a new mission-proposal call. The page renders the current phase and degrades to a labeled scripted proposal if the live call fails.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, CSS animations, Cloudflare Worker API

---

## Chunk 1: Scenario Engine

### Task 1: Define Guided Scenario Data

**Files:**
- Create: `apps/command-center/src/scenario.ts`
- Modify: `apps/command-center/src/types.ts`
- Test: `apps/command-center/src/scenario.test.ts`

- [ ] Define `MissionPhase`, `PlaybackSpeed`, `LivePolicyProposal`, and phase-view types.
- [ ] Add eight immutable phase snapshots covering detect, flood spread, victims, launch,
  policy, shield, approval, and rescue.
- [ ] Add deterministic drone paths, flood reveal order, victim status changes, relay links,
  phase duration, headline, and operator guidance.
- [ ] Test phase order, total normal duration, and final aided-victim state.
- [ ] Run `npm --prefix apps/command-center test -- --run`.

### Task 2: Implement Playback State

**Files:**
- Create: `apps/command-center/src/useMissionPlayback.ts`
- Test: `apps/command-center/src/useMissionPlayback.test.tsx`

- [ ] Implement autoplay with `setTimeout`, speed multiplier, pause/resume, next, restart,
  and bounded phase index.
- [ ] Freeze the scripted demo-operator countdown while paused.
- [ ] Support immediate approval and a safe-hold override that pauses until Next/Restart.
- [ ] Expose progress, elapsed label, current phase, and completion state.
- [ ] Test timer progression and all controls with fake timers.

## Chunk 2: Live Policy And Visual Interface

### Task 3: Add Live Policy Request

**Files:**
- Modify: `apps/command-center/src/api.ts`
- Modify: `apps/command-center/src/types.ts`
- Test: `apps/command-center/src/api.test.ts`

- [ ] Add `requestMissionProposal(missionId, observation, signal)` using the existing
  Worker mission-proposal route.
- [ ] Validate action, confidence, source, and safety fields before accepting the payload.
- [ ] Treat `cloudflare-fallback`, `modal-fallback`, malformed, non-2xx, aborted, and
  network responses as unavailable.
- [ ] Test request URL, JSON body, successful parsing, malformed data, and failure behavior.

### Task 4: Replace Static Page With Guided Stage

**Files:**
- Modify: `apps/command-center/src/App.tsx`
- Modify: `apps/command-center/src/App.test.tsx`

- [ ] Wire `useMissionPlayback` into the page.
- [ ] Request the live policy once per playback run when entering the policy phase.
- [ ] Abort and ignore late responses after restart or unmount.
- [ ] Render mission clock, phase headline, progress rail, and presenter controls.
- [ ] Render current flood cells, victims, drone positions, roles, links, and trajectories.
- [ ] Render phase-specific right-rail content and compact proof drawer.
- [ ] Render live advisory source/confidence/service-reported safety or labeled fallback.
- [ ] Keep the guided sequence deterministic regardless of the advisory action.
- [ ] Use native `details`/`summary` for keyboard-accessible proof disclosure.
- [ ] Render final rescued-state metrics and restart call to action.
- [ ] Test progression, controls, live proposal, duplicate prevention, restart cancellation,
  fallback, approved rescue, and safe held outcome.

### Task 5: Build The Command-Center Motion System

**Files:**
- Modify: `apps/command-center/src/styles.css`

- [ ] Establish an industrial emergency-operations visual system with map-first hierarchy.
- [ ] Add flood reveal, victim pulse, drone movement, relay link, scan sweep, and phase
  transition animations.
- [ ] Add responsive desktop presentation and mobile stacking.
- [ ] Respect `prefers-reduced-motion`.
- [ ] Keep focus states and contrast accessible.
- [ ] Verify the layout at desktop and narrow mobile widths.

## Chunk 3: Verification And Deployment

### Task 6: Verify Locally

**Files:**
- Test: `apps/command-center/src/*.test.ts*`

- [ ] Run `npm --prefix apps/command-center test -- --run`.
- [ ] Run `npm --prefix apps/command-center run build`.
- [ ] Run `npm --prefix apps/worker run typecheck`.
- [ ] Run `npm --prefix apps/worker run test`.

### Task 7: Deploy And Capture Proof

**Files:**
- Update generated evidence under: `proof/`

- [ ] Build with `VITE_API_BASE_URL` set to the deployed Worker URL.
- [ ] Deploy `apps/command-center/dist` to Cloudflare Pages.
- [ ] Run `scripts/check_live_deploy.ps1`.
- [ ] Verify the stable Pages URL, Worker health, trained models, proof gate, and mission
  proposal route.
- [ ] Record the deployment URL and evidence JSON.
- [ ] Commit and push when `.git` write access is available.
