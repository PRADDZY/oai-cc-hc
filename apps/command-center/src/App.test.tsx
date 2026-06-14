import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const POLICY_PHASE_START_MS = 37_000;
const APPROVAL_PHASE_START_MS = 55_000;

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("Command center guided demo", () => {
  it("renders the animated mission shell with presenter controls and proof drawer", () => {
    mockFetch();

    render(<App />);

    expect(screen.getByText(/flood rescue \/ mission control/i)).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: /sentinel-1 replay acquired/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /pause/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /next phase/i })).toBeInTheDocument();
    expect(screen.getByText(/simulation replay \/ sen1floods11-based perception/i)).toBeInTheDocument();
    expect(screen.getByText(/training & deployment proof/i)).toBeInTheDocument();
    expect(screen.getAllByLabelText(/drone_\d/i)).toHaveLength(8);
    expect(document.querySelector(".mission-theater")).toBeInTheDocument();
  });

  it("requests one live advisory at the policy handoff and renders it", async () => {
    vi.useFakeTimers();
    const fetchMock = mockFetch();

    render(<App />);
    await advancePlayback(POLICY_PHASE_START_MS);

    expect(screen.getAllByRole("heading", { name: /rl orchestrator proposes a route/i }).length).toBeGreaterThan(0);
    expect(screen.getByText(/live modal advisory/i)).toBeInTheDocument();
    expect(screen.getByText("SEARCH")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/missions/mula-mutha-guided-demo/proposals",
      expect.objectContaining({ method: "POST" }),
    );
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).includes("/api/missions/")).length,
    ).toBe(1);
  });

  it("falls back to the scripted advisory when the service reports fallback mode", async () => {
    vi.useFakeTimers();
    mockFetch({ proposal: { ...validProposal(), source: "modal-fallback" } });

    render(<App />);
    await advancePlayback(POLICY_PHASE_START_MS);

    expect(screen.getByText(/resilient scripted advisory/i)).toBeInTheDocument();
    expect(screen.getByText("AID DROP")).toBeInTheDocument();
  });

  it("records safe hold without showing aided victim delivery", async () => {
    vi.useFakeTimers();
    mockFetch();

    render(<App />);
    await advancePlayback(APPROVAL_PHASE_START_MS);

    fireEvent.click(screen.getByRole("button", { name: /override to safe hold/i }));
    expect(screen.getByText(/decision recorded: held/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /next phase/i }));
    expect(screen.getByText(/safe hold engaged/i)).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: /mission held safely/i }).length).toBeGreaterThan(0);
    expect(screen.queryByText(/aid package delivered/i)).not.toBeInTheDocument();
  });
});

async function advancePlayback(ms: number) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
  await act(async () => {
    await Promise.resolve();
  });
}

function mockFetch(options: { proposal?: ReturnType<typeof validProposal> } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.endsWith("/api/health")) {
      return jsonResponse({
        status: "ok",
        service: "cloudflare-worker",
        modal_configured: true,
        simulation_only: true,
      });
    }

    if (url.endsWith("/api/models/active")) {
      return jsonResponse({
        policy_alias: "production",
        policy_artifact: "swarm-policy-modal-trained",
        perception_alias: "production",
        perception_artifact: "terramind-s1-modal-trained",
        promoted_at: "2026-06-14T10:00:00Z",
        proof_run_id: "modal-eval-proof",
        simulation_only: true,
      });
    }

    if (url.endsWith("/api/proof/latest")) {
      return jsonResponse({
        passed: true,
        simulation_only: true,
        payload: {
          passed: true,
          active_models: {
            policy_alias: "production",
            policy_artifact: "swarm-policy-modal-trained",
            perception_alias: "production",
            perception_artifact: "terramind-s1-modal-trained",
            promoted_at: "2026-06-14T10:00:00Z",
            proof_run_id: "modal-eval-proof",
            simulation_only: true,
          },
          proofs: {
            perception: {
              payload: {
                event_held_out_iou: 0.276872,
                event_held_out_f1: 0.433672,
              },
            },
            rl: {
              payload: {
                candidate: {
                  lives_aided_safely_mean: 1,
                  safety_failures: 0,
                },
                release_gate: {
                  passed: true,
                  safety_failures: 0,
                },
              },
            },
          },
        },
      });
    }

    if (url.includes("/api/missions/")) {
      return jsonResponse(options.proposal ?? validProposal());
    }

    return jsonResponse({}, 404);
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function validProposal() {
  return {
    source: "trained-modal-policy",
    simulation_only: true,
    proposal: {
      mission_id: "mula-mutha-guided-demo",
      drone_id: "drone_0",
      action: "search",
      parameters: { sector: "west-bank" },
      confidence: 0.708678,
      coordination_message: [0.75, 0.25, 0.4],
    },
    safety: {
      status: "allowed",
      executed_action: "search",
      reason_code: "trained_policy_safe_proposal",
      shield_status: true,
    },
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}
