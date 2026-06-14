import type { ActiveModelManifest, ProofSummary } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function fetchActiveModels(): Promise<ActiveModelManifest | null> {
  return fetchJson<ActiveModelManifest>("/api/models/active");
}

export async function fetchLatestProof(): Promise<ProofSummary | null> {
  return fetchJson<ProofSummary>("/api/proof/latest");
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
