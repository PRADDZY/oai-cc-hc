import { useEffect, useState } from "react";
import { fetchActiveModels, fetchHealth, fetchLatestProof } from "./api";
import { demoMission } from "./demo";
import type {
  ActiveModelManifest,
  DroneState,
  MissionSnapshot,
  ProofPayload,
  ProofSummary,
  WorkerHealth,
} from "./types";
import "./styles.css";

const roleLabels: Record<DroneState["role"], string> = {
  aid_drop: "Aid Drop",
  hold: "Hold",
  relay: "Relay",
  return: "Return",
  search: "Search",
};

export function App({ mission = demoMission }: { mission?: MissionSnapshot }) {
  const [health, setHealth] = useState<WorkerHealth | null>(null);
  const [proof, setProof] = useState<ProofSummary | null>(null);
  const [activeModels, setActiveModels] = useState<ActiveModelManifest | null>(null);

  useEffect(() => {
    let mounted = true;
    void Promise.all([fetchHealth(), fetchLatestProof(), fetchActiveModels()]).then(([nextHealth, nextProof, models]) => {
      if (!mounted) {
        return;
      }
      const payload = proofPayload(nextProof);
      setHealth(nextHealth);
      setProof(nextProof);
      setActiveModels(models ?? payload?.active_models ?? nextProof?.active_models ?? null);
    });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <main className="shell" aria-label="Flood rescue mission command center">
      <section className="hero">
        <div>
          <p className="eyebrow">Simulation-only command center</p>
          <h1>{mission.scenario}</h1>
          <p className="lede">
            Hierarchical swarm coordination with explicit uncertainty, safety
            interventions, and human approval gates.
          </p>
        </div>
        <div className="hero-card" aria-label="Mission confidence">
          <span>World Confidence</span>
          <strong>{Math.round(mission.confidence * 100)}%</strong>
          <small>Simulated decision proposals remain shielded</small>
        </div>
      </section>

      <section className="labels" aria-label="Source labels">
        {mission.sourceLabels.map((label) => (
          <span key={label} className={`label label-${label}`}>
            {label.replace("_", " ")}
          </span>
        ))}
        {mission.simulationOnly && <span className="label label-warning">simulation only</span>}
      </section>

      <section className="grid-layout">
        <MissionMap mission={mission} />
        <aside className="side-panel" aria-label="Swarm status">
          <ProofPanel health={health} proof={proof} activeModels={activeModels} />
          <SafetyPanel mission={mission} />
          <DroneRoster drones={mission.drones} />
        </aside>
      </section>

      <section className="timeline" aria-label="Mission event timeline">
        <h2>Evidence Timeline</h2>
        {mission.events.map((event) => (
          <article key={event.id}>
            <time>{event.time}</time>
            <span className={`label label-${event.label}`}>{event.label.replace("_", " ")}</span>
            <p>{event.message}</p>
          </article>
        ))}
      </section>
    </main>
  );
}

function ProofPanel({
  health,
  proof,
  activeModels,
}: {
  health: WorkerHealth | null;
  proof: ProofSummary | null;
  activeModels: ActiveModelManifest | null;
}) {
  const payload = proofPayload(proof);
  const rlPayload = payload?.proofs?.rl?.payload;
  const perceptionPayload = payload?.proofs?.perception?.payload;
  const releaseGate = rlPayload?.release_gate;
  const passed = Boolean(payload?.passed ?? proof?.passed);
  const status = proof ? (passed ? "Modal proof gate passed" : "Modal proof needs review") : "Connecting to live proof";
  const simulationOnly = Boolean(proof?.simulation_only ?? payload?.active_models?.simulation_only ?? health?.simulation_only);
  return (
    <section className="proof-panel" aria-label="Modal training proof">
      <p className="eyebrow">Cloudflare + Modal</p>
      <h2>{status}</h2>
      <p>{payload?.readme_summary ?? proof?.readme_summary ?? proof?.reason ?? "Live gateway will show the latest Modal eval result here."}</p>
      <div className="live-strip" aria-label="Live deployment status">
        <span className={health?.status === "ok" ? "signal good" : "signal"}>
          Worker {health?.status ?? "checking"}
        </span>
        <span className={health?.modal_configured ? "signal good" : "signal caution"}>
          Modal {health?.modal_configured ? "configured" : "fallback-safe"}
        </span>
        {payload?.modal_app && <span className="signal">{payload.modal_app}</span>}
      </div>
      <dl className="model-list">
        <div>
          <dt>Policy</dt>
          <dd>{activeModels?.policy_artifact ?? "not promoted yet"}</dd>
        </div>
        <div>
          <dt>Perception</dt>
          <dd>{activeModels?.perception_artifact ?? "not promoted yet"}</dd>
        </div>
      </dl>
      <div className="metric-grid" aria-label="Evaluation metrics">
        <Metric label="Lives aided" value={formatMetric(rlPayload?.candidate?.lives_aided_safely_mean)} />
        <Metric label="Rescue rate" value={formatPercent(rlPayload?.candidate?.rescue_rate_mean)} />
        <Metric label="Coverage" value={formatPercent(rlPayload?.candidate?.coverage_mean)} />
        <Metric label="Link continuity" value={formatPercent(rlPayload?.candidate?.communication_continuity_mean)} />
        <Metric label="Safety failures" value={formatInteger(releaseGate?.safety_failures ?? rlPayload?.candidate?.safety_failures)} />
        <Metric label="Perception IoU" value={formatPercent(perceptionPayload?.event_held_out_iou)} />
      </div>
      {releaseGate?.reasons && releaseGate.reasons.length > 0 && (
        <p className="proof-reason">Gate note: {releaseGate.reasons.join("; ")}</p>
      )}
      <span className="label label-simulated">{simulationOnly ? "simulation only" : "live proof"}</span>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function proofPayload(proof: ProofSummary | null): ProofPayload | null {
  if (!proof) {
    return null;
  }
  return proof.payload ?? proof;
}

function formatMetric(value: number | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(2);
}

function formatPercent(value: number | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return `${Math.round(value * 100)}%`;
}

function formatInteger(value: number | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return String(Math.round(value));
}

function MissionMap({ mission }: { mission: MissionSnapshot }) {
  return (
    <section className="map-card" aria-label="Local map fallback">
      <div className="map-header">
        <div>
          <h2>Flood Belief Grid</h2>
          <p>No external map token required for the demo fallback.</p>
        </div>
        <span className="badge">Pune replay</span>
      </div>
      <div className="map-grid">
        {Array.from({ length: 144 }, (_, index) => {
          const x = index % 12;
          const y = Math.floor(index / 12);
          const flood = mission.floodCells.find((cell) => cell.x === x && cell.y === y);
          const victim = mission.victims.find((item) => item.x === x && item.y === y);
          const drone = mission.drones.find((item) => item.x === x && item.y === y);
          return (
            <div
              key={`${x}-${y}`}
              className="cell"
              data-flood={flood ? Math.round(flood.probability * 100) : undefined}
            >
              {flood && <span className="flood" style={{ opacity: flood.probability }} />}
              {victim && <span className={`victim ${victim.status}`} aria-label={`Victim ${victim.id}`} />}
              {drone && <span className={`drone ${drone.role}`} aria-label={`${drone.id} ${drone.role}`} />}
            </div>
          );
        })}
      </div>
      <div className="links" aria-label="Relay links">
        Relay links: {mission.relayLinks.map((pair) => pair.join(" -> ")).join(" | ")}
      </div>
    </section>
  );
}

function SafetyPanel({ mission }: { mission: MissionSnapshot }) {
  return (
    <section className="safety-panel" aria-label="Safety decision">
      <p className="eyebrow">Shield status: {mission.proposedAction.shieldStatus}</p>
      <h2>{mission.proposedAction.summary}</h2>
      <p>Policy confidence: {Math.round(mission.proposedAction.confidence * 100)}%</p>
      <button type="button">Approve after visual confirmation</button>
      <button type="button" className="secondary">
        Override to hold
      </button>
      {mission.proposedAction.requiresHumanApproval && (
        <strong className="approval">Human approval required</strong>
      )}
    </section>
  );
}

function DroneRoster({ drones }: { drones: DroneState[] }) {
  return (
    <section className="drone-roster">
      <h2>Swarm Roster</h2>
      {drones.map((drone) => (
        <article key={drone.id} className="drone-card">
          <div>
            <strong>{drone.id}</strong>
            <span>{roleLabels[drone.role]}</span>
          </div>
          <p>{drone.status}</p>
          <meter min={0} max={100} value={drone.battery}>
            {drone.battery}%
          </meter>
        </article>
      ))}
    </section>
  );
}

export default App;
