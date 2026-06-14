import { describe, expect, it } from "vitest";
import { guidedScenario, scriptedPolicyProposal } from "./scenario";

describe("guided rescue scenario", () => {
  it("defines nine ordered phases lasting 60-90 seconds at normal speed", () => {
    expect(guidedScenario.map((phase) => phase.id)).toEqual([
      "satellite-intake",
      "flood-belief",
      "victim-triage",
      "swarm-launch",
      "policy-handoff",
      "safety-review",
      "operator-approval",
      "aid-delivery",
      "mission-complete",
    ]);

    const totalDuration = guidedScenario.reduce(
      (total, phase) => total + phase.durationMs,
      0,
    );

    expect(totalDuration).toBe(81_000);
    expect(totalDuration).toBeGreaterThanOrEqual(60_000);
    expect(totalDuration).toBeLessThanOrEqual(90_000);
  });

  it("provides integration copy and a complete mission snapshot for every phase", () => {
    for (const phase of guidedScenario) {
      expect(phase.title).not.toBe("");
      expect(phase.kicker).not.toBe("");
      expect(phase.narrative).not.toBe("");
      expect(phase.objective).not.toBe("");
      expect(phase.feedLabel).not.toBe("");
      expect(phase.mission.missionId).toBe("mula-mutha-guided-demo");
      expect(phase.mission.simulationOnly).toBe(true);
      expect(phase.mission.drones).toHaveLength(8);
    }
  });

  it("reveals the disaster state progressively and ends with an aided victim", () => {
    expect(guidedScenario[0].mission.floodCells).toHaveLength(0);
    expect(guidedScenario[1].mission.floodCells.length).toBeGreaterThan(0);
    expect(guidedScenario[2].mission.victims).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "victim_alpha", status: "confirmed" }),
      ]),
    );
    expect(guidedScenario[3].mission.relayLinks.length).toBeGreaterThan(0);
    expect(guidedScenario.at(-1)?.mission.victims).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "victim_alpha", status: "aided" }),
      ]),
    );
  });

  it("exports a clearly labeled scripted advisory fallback", () => {
    expect(scriptedPolicyProposal.source).toBe("scripted-demo-fallback");
    expect(scriptedPolicyProposal.proposal.action).toBe("aid_drop");
    expect(scriptedPolicyProposal.safety.shield_status).toBe(true);
    expect(scriptedPolicyProposal.simulation_only).toBe(true);
  });
});
