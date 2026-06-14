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

export interface WorkerHealth {
  status?: string;
  service?: string;
  modal_configured?: boolean;
  simulation_only?: boolean;
}

export interface EvalSummary {
  episodes?: number;
  lives_aided_safely_mean?: number;
  rescue_rate_mean?: number;
  coverage_mean?: number;
  communication_continuity_mean?: number;
  safety_failures?: number;
}

export interface ReleaseGateProof {
  passed?: boolean;
  reasons?: string[];
  safety_failures?: number;
  comparison?: Record<string, unknown>;
}

export interface ProofBundle {
  proof_type?: string;
  run_id?: string;
  generated_at?: string;
  git_sha?: string;
  simulation_only?: boolean;
  trained_result?: boolean;
  payload?: ProofPayload;
}

export interface ProofPayload {
  passed?: boolean;
  modal_app?: string;
  active_models?: ActiveModelManifest;
  proofs?: {
    perception?: ProofBundle & {
      payload?: {
        event_held_out_iou?: number;
        event_held_out_f1?: number;
        calibration_ece?: number;
        artifact_id?: string;
      };
    };
    rl?: ProofBundle & {
      payload?: {
        stage?: string;
        eval_seeds?: number[];
        candidate?: EvalSummary;
        baseline?: EvalSummary;
        release_gate?: ReleaseGateProof;
        artifact_id?: string;
      };
    };
  };
  readme_summary?: string;
}

export interface ProofSummary {
  passed?: boolean;
  source?: string;
  reason?: string;
  simulation_only?: boolean;
  active_models?: ActiveModelManifest;
  readme_summary?: string;
  payload?: ProofPayload;
  proofs?: ProofPayload["proofs"];
  modal_app?: string;
}
