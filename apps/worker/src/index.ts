export interface Env {
  ALLOWED_ORIGIN?: string;
  ARTIFACTS?: R2Bucket;
  DB?: D1Database;
  ENVIRONMENT?: string;
  MISSION_ROOMS?: DurableObjectNamespace;
  MODAL_API_TOKEN?: string;
  MODAL_INFERENCE_URL?: string;
  MODEL_ALIASES?: KVNamespace;
  OBSERVATION_QUEUE?: Queue;
}

const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
};

export class MissionRoom {
  constructor(
    private readonly state: DurableObjectState,
    private readonly env: Env,
  ) {
    void this.env;
  }

  async fetch(request: Request): Promise<Response> {
    const count = Number((await this.state.storage.get("events")) ?? 0) + 1;
    await this.state.storage.put("events", count);
    return json({ status: "ok", events_seen: count, simulation_only: true }, request);
  }
}

export default {
  fetch: handleRequest,
};

export async function handleRequest(request: Request, env: Env): Promise<Response> {
  if (request.method === "OPTIONS") {
    return cors(new Response(null, { status: 204 }), request, env);
  }

  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";

  if (request.method === "GET" && path === "/api/health") {
    return json(
      {
        status: "ok",
        service: "cloudflare-worker",
        modal_configured: Boolean(env.MODAL_INFERENCE_URL),
        simulation_only: true,
      },
      request,
      env,
    );
  }

  if (request.method === "GET" && path === "/api/models/active") {
    const modal = await modalJson(env, "models_active");
    return json(modal ?? fallbackActiveModels(), request, env);
  }

  if (request.method === "GET" && path === "/api/proof/latest") {
    const modal = await modalJson(env, "proof_latest");
    return json(modal ?? fallbackProof(), request, env);
  }

  const proposalMatch = path.match(/^\/api\/missions\/([^/]+)\/proposals$/);
  if (request.method === "POST" && proposalMatch) {
    const body = await safeJson(request);
    const modal = await modalJson(env, "policy_propose", {
      method: "POST",
      body: JSON.stringify({ ...body, mission_id: proposalMatch[1] }),
    });
    return json(modal ?? fallbackProposal(proposalMatch[1]), request, env);
  }

  return json({ error: "not_found", simulation_only: true }, request, env, 404);
}

async function modalJson(
  env: Env,
  path: string,
  init: RequestInit = {},
): Promise<Record<string, unknown> | null> {
  if (!env.MODAL_INFERENCE_URL) {
    return null;
  }
  const base = env.MODAL_INFERENCE_URL.replace(/\/+$/, "");
  const headers = new Headers(init.headers);
  headers.set("content-type", "application/json");
  if (env.MODAL_API_TOKEN) {
    headers.set("authorization", `Bearer ${env.MODAL_API_TOKEN}`);
  }

  try {
    const response = await fetch(`${base}/${path}`, { ...init, headers });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

async function safeJson(request: Request): Promise<Record<string, unknown>> {
  try {
    return (await request.json()) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function json(
  value: unknown,
  request: Request,
  env: Env = {},
  status = 200,
): Response {
  return cors(
    new Response(JSON.stringify(value, null, 2), {
      status,
      headers: JSON_HEADERS,
    }),
    request,
    env,
  );
}

function cors(response: Response, request: Request, env: Env = {}): Response {
  const headers = new Headers(response.headers);
  const origin = request.headers.get("origin");
  const allowed = env.ALLOWED_ORIGIN || "*";
  headers.set("access-control-allow-origin", origin && allowed !== "*" ? allowed : allowed);
  headers.set("access-control-allow-methods", "GET,POST,OPTIONS");
  headers.set("access-control-allow-headers", "content-type,authorization");
  headers.set("vary", "origin");
  return new Response(response.body, { status: response.status, headers });
}

function fallbackActiveModels(): Record<string, unknown> {
  return {
    policy_alias: "production",
    policy_artifact: "swarm-policy-fallback",
    perception_alias: "production",
    perception_artifact: "terramind-s1-fallback",
    promoted_at: new Date(0).toISOString(),
    proof_run_id: "fallback",
    simulation_only: true,
  };
}

function fallbackProof(): Record<string, unknown> {
  return {
    passed: false,
    source: "cloudflare-fallback",
    reason: "Modal proof endpoint unavailable",
    simulation_only: true,
    active_models: fallbackActiveModels(),
    readme_summary: "Fallback proof only; run Modal jobs for submission evidence.",
  };
}

function fallbackProposal(missionId: string): Record<string, unknown> {
  return {
    source: "cloudflare-fallback",
    simulation_only: true,
    proposal: {
      mission_id: missionId,
      drone_id: "drone_0",
      action: "search",
      parameters: { sector: "fallback-search-sector" },
      confidence: 0.52,
    },
    safety: {
      status: "allowed",
      executed_action: "search",
      reason_code: "modal_unavailable_safe_fallback",
      shield_status: true,
    },
  };
}
