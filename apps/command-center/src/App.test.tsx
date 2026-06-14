import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Command center", () => {
  it("shows simulation and provenance labels", () => {
    render(<App />);

    expect(screen.getAllByText(/simulation only/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/model generated/i).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/local map fallback/i)).toBeInTheDocument();
  });

  it("renders all eight drones and the approval gate", () => {
    render(<App />);

    const roster = screen.getByRole("heading", { name: /swarm roster/i }).closest("section");
    expect(roster).not.toBeNull();
    expect(within(roster!).getAllByText(/^drone_\d$/i)).toHaveLength(8);
    expect(screen.getByText(/human approval required/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /approve after visual confirmation/i }),
    ).toBeInTheDocument();
  });

  it("displays live Worker status, active models, and eval metrics", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
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
            policy_artifact: "swarm-policy-smoke-live",
            perception_alias: "production",
            perception_artifact: "terramind-s1-smoke-live",
            promoted_at: "2026-06-14T10:00:00Z",
            proof_run_id: "rl-training-live",
            simulation_only: true,
          });
        }
        if (url.endsWith("/api/proof/latest")) {
          return jsonResponse({
            passed: true,
            modal_app: "flood-rescue-inference",
            simulation_only: true,
            readme_summary: "Modal produced simulation-only training/evaluation proof.",
            active_models: {
              policy_alias: "production",
              policy_artifact: "swarm-policy-smoke-live",
              perception_alias: "production",
              perception_artifact: "terramind-s1-smoke-live",
              promoted_at: "2026-06-14T10:00:00Z",
              proof_run_id: "rl-training-live",
              simulation_only: true,
            },
            proofs: {
              perception: {
                payload: {
                  event_held_out_iou: 0.68,
                  event_held_out_f1: 0.77,
                  calibration_ece: 0.04,
                },
              },
              rl: {
                payload: {
                  candidate: {
                    lives_aided_safely_mean: 2.5,
                    rescue_rate_mean: 0.84,
                    coverage_mean: 0.72,
                    communication_continuity_mean: 0.91,
                    safety_failures: 0,
                  },
                  release_gate: {
                    passed: true,
                    safety_failures: 0,
                    reasons: [],
                  },
                },
              },
            },
          });
        }
        return jsonResponse({}, 404);
      }),
    );

    render(<App />);

    expect(await screen.findByText(/modal proof gate passed/i)).toBeInTheDocument();
    expect(screen.getByText(/worker ok/i)).toBeInTheDocument();
    expect(screen.getByText(/modal configured/i)).toBeInTheDocument();
    expect(screen.getByText("swarm-policy-smoke-live")).toBeInTheDocument();
    expect(screen.getByText("terramind-s1-smoke-live")).toBeInTheDocument();
    const metrics = screen.getByLabelText(/evaluation metrics/i);
    expect(within(metrics).getByText("2.50")).toBeInTheDocument();
    expect(within(metrics).getByText("84%")).toBeInTheDocument();
    expect(within(metrics).getByText("68%")).toBeInTheDocument();
  });
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}
