import type {
  DataLabel,
  DroneState,
  FloodCell,
  LivePolicyProposal,
  MissionEvent,
  MissionPhase,
  MissionSnapshot,
  VictimHypothesis,
} from "./types";

const missionId = "mula-mutha-guided-demo";
const scenario = "Pune Mula-Mutha flood response replay";

const floodCells: FloodCell[] = [
  { id: "f01", x: 3, y: 3, probability: 0.72, uncertainty: 0.3 },
  { id: "f02", x: 4, y: 3, probability: 0.81, uncertainty: 0.22 },
  { id: "f03", x: 5, y: 3, probability: 0.86, uncertainty: 0.17 },
  { id: "f04", x: 3, y: 4, probability: 0.88, uncertainty: 0.14 },
  { id: "f05", x: 4, y: 4, probability: 0.93, uncertainty: 0.09 },
  { id: "f06", x: 5, y: 4, probability: 0.9, uncertainty: 0.11 },
  { id: "f07", x: 6, y: 4, probability: 0.78, uncertainty: 0.24 },
  { id: "f08", x: 4, y: 5, probability: 0.84, uncertainty: 0.18 },
  { id: "f09", x: 5, y: 5, probability: 0.89, uncertainty: 0.13 },
  { id: "f10", x: 6, y: 5, probability: 0.76, uncertainty: 0.27 },
  { id: "f11", x: 5, y: 6, probability: 0.79, uncertainty: 0.23 },
  { id: "f12", x: 6, y: 6, probability: 0.68, uncertainty: 0.36 },
  { id: "f13", x: 7, y: 6, probability: 0.61, uncertainty: 0.42 },
  { id: "f14", x: 6, y: 7, probability: 0.73, uncertainty: 0.31 },
];

const baseDrones: DroneState[] = [
  drone("drone_0", "hold", 1, 11, 96, 0.99, "ready at launch point"),
  drone("drone_1", "hold", 2, 11, 94, 0.98, "ready at launch point"),
  drone("drone_2", "hold", 3, 11, 91, 0.98, "thermal payload ready"),
  drone("drone_3", "hold", 4, 11, 89, 0.97, "relay payload ready"),
  drone("drone_4", "hold", 5, 11, 93, 0.99, "aid package secured"),
  drone("drone_5", "hold", 6, 11, 90, 0.97, "route scan ready"),
  drone("drone_6", "hold", 7, 11, 95, 0.99, "mesh radio ready"),
  drone("drone_7", "hold", 8, 11, 87, 0.96, "reserve aircraft ready"),
];

const launchedDrones: DroneState[] = [
  drone("drone_0", "search", 2, 7, 91, 0.95, "sweeping western sector"),
  drone("drone_1", "search", 4, 6, 89, 0.93, "confirming flood edge"),
  drone("drone_2", "search", 7, 5, 85, 0.88, "thermal confirmation pass"),
  drone("drone_3", "relay", 3, 9, 85, 0.97, "southern mesh anchor"),
  drone("drone_4", "aid_drop", 5, 9, 89, 0.94, "holding aid package"),
  drone("drone_5", "search", 9, 7, 86, 0.84, "scanning access routes"),
  drone("drone_6", "relay", 8, 9, 91, 0.96, "eastern mesh anchor"),
  drone("drone_7", "return", 10, 10, 75, 0.81, "preserving battery reserve"),
];

const coordinatedDrones: DroneState[] = [
  drone("drone_0", "search", 2, 5, 86, 0.94, "maintaining visual sweep"),
  drone("drone_1", "search", 4, 5, 84, 0.92, "clearing approach corridor"),
  drone("drone_2", "search", 7, 6, 80, 0.89, "victim signal confirmed"),
  drone("drone_3", "relay", 3, 8, 81, 0.98, "mesh anchor stable"),
  drone("drone_4", "aid_drop", 6, 8, 84, 0.95, "positioned at safe standoff"),
  drone("drone_5", "search", 9, 6, 81, 0.86, "alternate route verified"),
  drone("drone_6", "relay", 8, 8, 87, 0.97, "handoff link stable"),
  drone("drone_7", "return", 11, 11, 70, 0.8, "returned to reserve"),
];

const finalDrones: DroneState[] = coordinatedDrones.map((item) =>
  item.id === "drone_4"
    ? { ...item, x: 7, y: 7, battery: 79, status: "aid package delivered" }
    : { ...item, status: item.role === "return" ? item.status : "holding recovery corridor" },
);

const victimHypotheses: VictimHypothesis[] = [
  { id: "victim_alpha", x: 7, y: 7, confidence: 0.91, status: "confirmed" },
  { id: "victim_beta", x: 2, y: 4, confidence: 0.58, status: "unconfirmed" },
  { id: "victim_gamma", x: 9, y: 5, confidence: 0.46, status: "unconfirmed" },
];

const relayLinks: Array<[string, string]> = [
  ["drone_0", "drone_3"],
  ["drone_3", "drone_6"],
  ["drone_4", "drone_6"],
  ["drone_5", "drone_6"],
];

const events: MissionEvent[] = [
  event("e01", "00:00", "replay", "Sentinel-1 replay frame received for the Mula-Mutha corridor."),
  event("e02", "00:08", "model_generated", "Flood belief expands across fourteen high-risk cells."),
  event("e03", "00:18", "model_generated", "Thermal and visual cues confirm victim_alpha."),
  event("e04", "00:27", "simulated", "Eight-drone swarm launches with search, relay, aid, and reserve roles."),
  event("e05", "00:37", "model_generated", "RL orchestrator requested for advisory route coordination."),
  event("e06", "00:47", "simulated", "Service-reported safety metadata marks the proposal as approval-gated."),
  event("e07", "00:55", "simulated", "Scripted demo operator gate opens for five seconds."),
  event("e08", "01:00", "simulated", "Approved aid route completes without breaking relay continuity."),
];

export const scriptedPolicyProposal: LivePolicyProposal = {
  source: "scripted-demo-fallback",
  simulation_only: true,
  proposal: {
    mission_id: missionId,
    drone_id: "drone_4",
    action: "aid_drop",
    parameters: {
      route: "relay_preserving_standoff",
      target: "victim_alpha",
      approval_required: true,
    },
    confidence: 0.71,
    coordination_message: [0.82, 0.91, 0.74, 0.88],
  },
  safety: {
    status: "replaced",
    executed_action: "aid_drop",
    reason_code: "low_link_route_replaced_by_relay_preserving_approach",
    shield_status: true,
  },
};

export const guidedScenario: MissionPhase[] = [
  phase(
    "satellite-intake",
    "Sentinel-1 replay acquired",
    "01 / DETECT",
    "A delayed radar frame enters the command center. It is explicitly presented as a Sen1Floods11-based replay, not a live emergency feed.",
    8_000,
    mission({
      confidence: 0.43,
      drones: baseDrones,
      floodCount: 0,
      victimMode: "none",
      eventCount: 1,
      actionSummary: "Awaiting flood perception.",
      actionConfidence: 0.43,
      shieldStatus: "allowed",
    }),
    "Establish provenance before the model contributes any interpretation.",
    "replay",
  ),
  phase(
    "flood-belief",
    "Flood belief expands",
    "02 / PERCEIVE",
    "The perception model reveals connected flood cells in confidence order while uncertainty remains visible at the boundary.",
    10_000,
    mission({
      confidence: 0.72,
      drones: baseDrones,
      floodCount: 14,
      victimMode: "none",
      eventCount: 2,
      actionSummary: "Map high-confidence flood extent.",
      actionConfidence: 0.72,
      shieldStatus: "allowed",
    }),
    "Convert satellite pixels into an uncertainty-aware operational map.",
    "model_generated",
  ),
  phase(
    "victim-triage",
    "Victim signal confirmed",
    "03 / TRIAGE",
    "Three hypotheses are ranked. Thermal and visual agreement confirms victim_alpha while weaker signals remain unconfirmed.",
    9_000,
    mission({
      confidence: 0.78,
      drones: baseDrones,
      floodCount: 14,
      victimMode: "confirmed",
      eventCount: 3,
      actionSummary: "Prioritize victim_alpha and retain uncertainty on secondary signals.",
      actionConfidence: 0.78,
      shieldStatus: "allowed",
    }),
    "Focus scarce swarm capacity without treating every weak signal as fact.",
    "model_generated",
  ),
  phase(
    "swarm-launch",
    "Swarm roles self-organize",
    "04 / DEPLOY",
    "Eight aircraft launch into search, relay, aid, hold, and return responsibilities. The low-reserve aircraft returns before entering the hazard zone.",
    10_000,
    mission({
      confidence: 0.82,
      drones: launchedDrones,
      floodCount: 14,
      victimMode: "confirmed",
      eventCount: 4,
      relayLinks,
      actionSummary: "Establish a relay-backed search and aid corridor.",
      actionConfidence: 0.82,
      shieldStatus: "allowed",
    }),
    "Demonstrate coordinated roles rather than eight independently piloted drones.",
    "simulated",
  ),
  phase(
    "policy-handoff",
    "RL orchestrator proposes a route",
    "05 / COORDINATE",
    "The frontend requests one live advisory proposal. The deterministic scenario continues even if the service responds with search guidance or a labeled fallback.",
    10_000,
    mission({
      confidence: scriptedPolicyProposal.proposal.confidence,
      drones: coordinatedDrones,
      floodCount: 14,
      victimMode: "confirmed",
      eventCount: 5,
      relayLinks,
      actionSummary: "Maintain two relay anchors while drone_4 approaches victim_alpha.",
      actionConfidence: scriptedPolicyProposal.proposal.confidence,
      shieldStatus: scriptedPolicyProposal.safety.status,
    }),
    "Use the trained policy as real-time advisory intelligence without surrendering operator control.",
    "model_generated",
  ),
  phase(
    "safety-review",
    "Proposal is constrained",
    "06 / SAFETY",
    "Service-reported simulation metadata replaces a weak-link approach with a relay-preserving route. This is evidence from the simulation service, not flight certification.",
    8_000,
    mission({
      confidence: 0.76,
      drones: coordinatedDrones,
      floodCount: 14,
      victimMode: "confirmed",
      eventCount: 6,
      relayLinks,
      actionSummary: "Use relay-preserving approach; require human approval.",
      actionConfidence: 0.76,
      shieldStatus: "replaced",
    }),
    "Make constraints and intervention visible before any simulated execution.",
    "simulated",
  ),
  phase(
    "operator-approval",
    "Operator decision required",
    "07 / AUTHORIZE",
    "The guided run starts a five-second scripted demo-operator countdown. A presenter can approve immediately or override to a safe hold.",
    5_000,
    mission({
      confidence: 0.76,
      drones: coordinatedDrones,
      floodCount: 14,
      victimMode: "confirmed",
      eventCount: 7,
      relayLinks,
      actionSummary: "Approve aid delivery or hold the swarm safely.",
      actionConfidence: 0.76,
      shieldStatus: "replaced",
    }),
    "Keep the consequential decision legible and under human control.",
    "simulated",
  ),
  phase(
    "aid-delivery",
    "Aid reaches victim_alpha",
    "08 / RESOLVE",
    "Following approval, drone_4 completes the simulated delivery while relay anchors preserve communication and the remaining swarm holds the recovery corridor.",
    13_000,
    mission({
      confidence: 0.88,
      drones: finalDrones,
      floodCount: 14,
      victimMode: "aided",
      eventCount: 8,
      relayLinks,
      actionSummary: "Aid delivered; transition swarm to recovery hold.",
      actionConfidence: 0.88,
      shieldStatus: "allowed",
      requiresHumanApproval: false,
    }),
    "Close the detect-plan-approve-rescue loop with measurable mission outcomes.",
    "simulated",
  ),
];

export const heldMissionPhase: MissionPhase = phase(
  "mission-held",
  "Mission held safely",
  "08 / SAFE HOLD",
  "The operator declined simulated execution. No aid delivery is shown; aircraft maintain relay coverage and await a revised plan.",
  0,
  mission({
    confidence: 0.76,
    drones: coordinatedDrones.map((item) =>
      item.role === "return" ? item : { ...item, role: "hold", status: "operator hold" },
    ),
    floodCount: 14,
    victimMode: "confirmed",
    eventCount: 7,
    relayLinks,
    actionSummary: "Operator hold recorded; awaiting revised route.",
    actionConfidence: 0.76,
    shieldStatus: "rejected",
  }),
  "End in a truthful safe state when approval is withheld.",
  "simulated",
);

function drone(
  id: string,
  role: DroneState["role"],
  x: number,
  y: number,
  battery: number,
  linkQuality: number,
  status: string,
): DroneState {
  return { id, role, x, y, battery, linkQuality, status };
}

function event(
  id: string,
  time: string,
  label: DataLabel,
  message: string,
): MissionEvent {
  return { id, time, label, message };
}

function phase(
  id: string,
  title: string,
  kicker: string,
  narrative: string,
  durationMs: number,
  missionSnapshot: MissionSnapshot,
  objective: string,
  feedLabel: DataLabel,
): MissionPhase {
  return {
    id,
    title,
    kicker,
    narrative,
    durationMs,
    mission: missionSnapshot,
    objective,
    feedLabel,
  };
}

interface MissionOptions {
  confidence: number;
  drones: DroneState[];
  floodCount: number;
  victimMode: "none" | "confirmed" | "aided";
  eventCount: number;
  relayLinks?: Array<[string, string]>;
  actionSummary: string;
  actionConfidence: number;
  shieldStatus: MissionSnapshot["proposedAction"]["shieldStatus"];
  requiresHumanApproval?: boolean;
}

function mission(options: MissionOptions): MissionSnapshot {
  return {
    missionId,
    scenario,
    simulationOnly: true,
    confidence: options.confidence,
    sourceLabels: ["replay", "model_generated", "simulated"],
    drones: options.drones.map((item) => ({ ...item })),
    floodCells: floodCells.slice(0, options.floodCount).map((item) => ({ ...item })),
    victims: victimsFor(options.victimMode),
    relayLinks: (options.relayLinks ?? []).map(([from, to]) => [from, to]),
    events: events.slice(0, options.eventCount).map((item) => ({ ...item })),
    proposedAction: {
      summary: options.actionSummary,
      confidence: options.actionConfidence,
      requiresHumanApproval: options.requiresHumanApproval ?? true,
      shieldStatus: options.shieldStatus,
    },
  };
}

function victimsFor(mode: MissionOptions["victimMode"]): VictimHypothesis[] {
  if (mode === "none") {
    return [];
  }

  return victimHypotheses.map((victim) =>
    victim.id === "victim_alpha" && mode === "aided"
      ? { ...victim, status: "aided" }
      : { ...victim },
  );
}
