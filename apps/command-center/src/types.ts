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

