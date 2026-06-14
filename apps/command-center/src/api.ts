import type {
  ActiveModelManifest,
  LivePolicyProposal,
  MissionAction,
  ProofSummary,
  SafetyStatus,
  WorkerHealth,
} from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");
const FALLBACK_SOURCES = new Set(["cloudflare-fallback", "modal-fallback"]);
const MISSION_ACTIONS = new Set([
  "search",
  "relay",
  "aid_drop",
  "move",
  "hold",
  "return",
]);
const SAFETY_STATUSES = new Set(["allowed", "replaced", "rejected"]);

export type MissionProposalResponse = LivePolicyProposal;

export async function fetchHealth(): Promise<WorkerHealth | null> {
  return fetchJson<WorkerHealth>("/api/health");
}

export async function fetchActiveModels(): Promise<ActiveModelManifest | null> {
  return fetchJson<ActiveModelManifest>("/api/models/active");
}

export async function fetchLatestProof(): Promise<ProofSummary | null> {
  return fetchJson<ProofSummary>("/api/proof/latest");
}

export async function requestMissionProposal(
  missionId: string,
  observation: unknown,
  signal: AbortSignal,
): Promise<MissionProposalResponse | null> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/missions/${encodeURIComponent(missionId)}/proposals`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(observation),
        signal,
      },
    );
    if (!response.ok || signal.aborted) {
      return null;
    }

    const payload: unknown = await response.json();
    if (signal.aborted || !isMissionProposalResponse(payload)) {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`);
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

function isMissionProposalResponse(value: unknown): value is MissionProposalResponse {
  if (!isRecord(value) || !isValidSource(value.source)) {
    return false;
  }

  const proposal = value.proposal;
  const safety = value.safety;
  return (
    isRecord(proposal) &&
    isMissionAction(proposal.action) &&
    typeof proposal.confidence === "number" &&
    Number.isFinite(proposal.confidence) &&
    Array.isArray(proposal.coordination_message) &&
    proposal.coordination_message.length > 0 &&
    proposal.coordination_message.every(
      (item: unknown) => typeof item === "number" && Number.isFinite(item),
    ) &&
    isRecord(safety) &&
    isSafetyStatus(safety.status) &&
    isMissionAction(safety.executed_action) &&
    typeof safety.reason_code === "string" &&
    safety.reason_code.length > 0 &&
    typeof safety.shield_status === "boolean"
  );
}

function isValidSource(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && !FALLBACK_SOURCES.has(value);
}

function isMissionAction(value: unknown): value is MissionAction {
  return typeof value === "string" && MISSION_ACTIONS.has(value);
}

function isSafetyStatus(value: unknown): value is SafetyStatus {
  return typeof value === "string" && SAFETY_STATUSES.has(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
