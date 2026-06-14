import type { MissionSnapshot } from "./types";

export const demoMission: MissionSnapshot = {
  missionId: "mula-mutha-demo",
  scenario: "Pune Mula-Mutha urban flood",
  simulationOnly: true,
  confidence: 0.74,
  sourceLabels: ["simulated", "delayed", "model_generated"],
  drones: [
    { id: "drone_0", role: "search", x: 2, y: 2, battery: 84, linkQuality: 0.94, status: "sector sweep" },
    { id: "drone_1", role: "relay", x: 5, y: 3, battery: 79, linkQuality: 0.91, status: "mesh anchor" },
    { id: "drone_2", role: "search", x: 7, y: 5, battery: 66, linkQuality: 0.72, status: "thermal pass" },
    { id: "drone_3", role: "hold", x: 10, y: 4, battery: 42, linkQuality: 0.38, status: "shield hold" },
    { id: "drone_4", role: "aid_drop", x: 4, y: 8, battery: 88, linkQuality: 0.88, status: "awaiting approval" },
    { id: "drone_5", role: "search", x: 8, y: 9, battery: 73, linkQuality: 0.81, status: "road scan" },
    { id: "drone_6", role: "relay", x: 1, y: 7, battery: 91, linkQuality: 0.96, status: "uplink stable" },
    { id: "drone_7", role: "return", x: 11, y: 10, battery: 21, linkQuality: 0.51, status: "battery reserve" },
  ],
  floodCells: [
    { id: "f1", x: 3, y: 4, probability: 0.88, uncertainty: 0.18 },
    { id: "f2", x: 4, y: 4, probability: 0.92, uncertainty: 0.12 },
    { id: "f3", x: 5, y: 5, probability: 0.77, uncertainty: 0.28 },
    { id: "f4", x: 6, y: 6, probability: 0.69, uncertainty: 0.35 },
    { id: "f5", x: 4, y: 7, probability: 0.82, uncertainty: 0.22 },
    { id: "f6", x: 9, y: 7, probability: 0.63, uncertainty: 0.41 },
  ],
  victims: [
    { id: "v1", x: 4, y: 8, confidence: 0.81, status: "confirmed" },
    { id: "v2", x: 8, y: 6, confidence: 0.58, status: "unconfirmed" },
    { id: "v3", x: 2, y: 5, confidence: 0.43, status: "unconfirmed" },
  ],
  relayLinks: [
    ["drone_0", "drone_1"],
    ["drone_1", "drone_6"],
    ["drone_4", "drone_6"],
  ],
  events: [
    { id: "e1", time: "12:00:00", label: "simulated", message: "Mission replay started with 8 active drones." },
    { id: "e2", time: "12:00:06", label: "delayed", message: "Sentinel-1 flood prior refreshed; confidence decays after 3h." },
    { id: "e3", time: "12:00:11", label: "model_generated", message: "Policy proposes aid drop at v1; shield requires human approval." },
    { id: "e4", time: "12:00:15", label: "simulated", message: "Drone_7 replaced with return due to battery reserve." },
  ],
  proposedAction: {
    summary: "Approve aid drop only after operator confirms v1 safe zone.",
    confidence: 0.67,
    requiresHumanApproval: true,
    shieldStatus: "replaced",
  },
};

