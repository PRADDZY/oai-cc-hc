import { describe, expect, it, vi } from "vitest";
import { handleRequest, type Env } from "../src/index";

type JsonObject = Record<string, unknown>;

const env: Env = {
  ALLOWED_ORIGIN: "https://flood-rescue-command-center.pages.dev",
};

describe("Cloudflare Worker gateway", () => {
  it("returns health with simulation boundary", async () => {
    const response = await handleRequest(new Request("https://worker.test/api/health"), env);
    const body = (await response.json()) as JsonObject;

    expect(response.status).toBe(200);
    expect(body.status).toBe("ok");
    expect(body.simulation_only).toBe(true);
  });

  it("falls back to cached proof when Modal is unavailable", async () => {
    const response = await handleRequest(new Request("https://worker.test/api/proof/latest"), env);
    const body = (await response.json()) as JsonObject;

    expect(body.source).toBe("cloudflare-fallback");
    expect(body.simulation_only).toBe(true);
  });

  it("calls Modal for policy proposals when configured", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ simulation_only: true, source: "modal" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const response = await handleRequest(
      new Request("https://worker.test/api/missions/demo/proposals", {
        method: "POST",
        body: JSON.stringify({ world: { confidence: 0.7 } }),
      }),
      { ...env, MODAL_INFERENCE_URL: "https://modal.test", MODAL_API_TOKEN: "secret" },
    );
    const body = (await response.json()) as JsonObject;

    expect(body.source).toBe("modal");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://modal.test/policy_propose",
      expect.objectContaining({
        method: "POST",
      }),
    );
    fetchMock.mockRestore();
  });
});
