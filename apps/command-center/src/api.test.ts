import { afterEach, describe, expect, it, vi } from "vitest";
import { requestMissionProposal } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("requestMissionProposal", () => {
  it("posts the observation to the encoded mission route and returns a valid proposal", async () => {
    const controller = new AbortController();
    const observation = { world: { flood_probability: 0.82 }, drones: ["drone_0"] };
    const payload = validProposal();
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(payload));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      requestMissionProposal("mission/demo 7", observation, controller.signal),
    ).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/missions/mission%2Fdemo%207/proposals",
      expect.objectContaining({
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(observation),
        signal: controller.signal,
      }),
    );
  });

  it.each(["cloudflare-fallback", "modal-fallback"])(
    "rejects the %s response source",
    async (source) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(jsonResponse({ ...validProposal(), source })),
      );

      await expect(
        requestMissionProposal("demo", {}, new AbortController().signal),
      ).resolves.toBeNull();
    },
  );

  it.each([
    ["missing source", { ...validProposal(), source: undefined }],
    [
      "unknown action",
      {
        ...validProposal(),
        proposal: { ...validProposal().proposal, action: "teleport" },
      },
    ],
    [
      "non-finite confidence",
      {
        ...validProposal(),
        proposal: { ...validProposal().proposal, confidence: Number.NaN },
      },
    ],
    [
      "invalid coordination message",
      {
        ...validProposal(),
        proposal: { ...validProposal().proposal, coordination_message: [0.5, "0.5"] },
      },
    ],
    [
      "missing safety status",
      {
        ...validProposal(),
        safety: { ...validProposal().safety, status: undefined },
      },
    ],
    [
      "invalid executed action",
      {
        ...validProposal(),
        safety: { ...validProposal().safety, executed_action: "teleport" },
      },
    ],
    [
      "missing safety reason",
      {
        ...validProposal(),
        safety: { ...validProposal().safety, reason_code: "" },
      },
    ],
    [
      "invalid shield status",
      {
        ...validProposal(),
        safety: { ...validProposal().safety, shield_status: "yes" },
      },
    ],
  ])("returns null for a malformed response: %s", async (_label, payload) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(payload)));

    await expect(
      requestMissionProposal("demo", {}, new AbortController().signal),
    ).resolves.toBeNull();
  });

  it("returns null for a non-success response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ error: "unavailable" }, 503)));

    await expect(
      requestMissionProposal("demo", {}, new AbortController().signal),
    ).resolves.toBeNull();
  });

  it("returns null when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network unavailable")));

    await expect(
      requestMissionProposal("demo", {}, new AbortController().signal),
    ).resolves.toBeNull();
  });

  it("returns null when the request is aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(validProposal())));

    await expect(requestMissionProposal("demo", {}, controller.signal)).resolves.toBeNull();
  });
});

function validProposal() {
  return {
    source: "trained-modal-policy",
    simulation_only: true,
    proposal: {
      mission_id: "demo",
      drone_id: "drone_0",
      action: "search",
      parameters: { sector: "north" },
      confidence: 0.708678,
      coordination_message: [0.75, 0.25, 0],
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
