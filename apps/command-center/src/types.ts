export type DataLabel = "live" | "delayed" | "simulated" | "replay" | "model_generated";

export interface DroneState {
  id: string;
  role: "search" | "relay" | "aid_drop" | "return" | "hold";
  x: number;
  y: number;
  battery: number;
  linkQuality: number;
  status: string;
}

export interface FloodCell {
  id: string;
  x: number;
  y: number;
  probability: number;
  uncertainty: number;
}

export interface VictimHypothesis {
  id: string;
  x: number;
  y: number;
  confidence: number;
  status: "unconfirmed" | "confirmed" | "aided";
}

export interface MissionEvent {
  id: string;
  time: string;
  label: DataLabel;
  message: string;
}

export interface MissionSnapshot {
  missionId: string;
  scenario: string;
  simulationOnly: boolean;
  confidence: number;
  sourceLabels: DataLabel[];
  drones: DroneState[];
  floodCells: FloodCell[];
  victims: VictimHypothesis[];
  relayLinks: Array<[string, string]>;
  events: MissionEvent[];
  proposedAction: {
    summary: string;
    confidence: number;
    requiresHumanApproval: boolean;
    shieldStatus: "allowed" | "replaced" | "rejected";
  };
}

export interface ActiveModelManifest {
  policy_alias: string;
  policy_artifact: string;
  perception_alias: string;
  perception_artifact: string;
  promoted_at: string;
  proof_run_id: string;
  simulation_only: boolean;
}

export interface ProofSummary {
  passed?: boolean;
  source?: string;
  reason?: string;
  simulation_only: boolean;
  active_models?: ActiveModelManifest;
  readme_summary?: string;
}
