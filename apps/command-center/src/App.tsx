import { useEffect, useState } from "react";
import { fetchActiveModels, fetchLatestProof } from "./api";
import { demoMission } from "./demo";
import type { ActiveModelManifest, DroneState, MissionSnapshot, ProofSummary } from "./types";
import "./styles.css";

const roleLabels: Record<DroneState["role"], string> = {
  aid_drop: "Aid Drop",
  hold: "Hold",
  relay: "Relay",
  return: "Return",
  search: "Search",
};

export function App({ mission = demoMission }: { mission?: MissionSnapshot }) {
  const [proof, setProof] = useState<ProofSummary | null>(null);
  const [activeModels, setActiveModels] = useState<ActiveModelManifest | null>(null);

  useEffect(() => {
    let mounted = true;
    void Promise.all([fetchLatestProof(), fetchActiveModels()]).then(([nextProof, models]) => {
      if (!mounted) {
        return;
      }
      setProof(nextProof);
      setActiveModels(models ?? nextProof?.active_models ?? null);
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
          <ProofPanel proof={proof} activeModels={activeModels} />
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
  proof,
  activeModels,
}: {
  proof: ProofSummary | null;
  activeModels: ActiveModelManifest | null;
}) {
  const status = proof?.passed ? "Modal proof gate passed" : "Awaiting Modal proof";
  return (
    <section className="proof-panel" aria-label="Modal training proof">
      <p className="eyebrow">Cloudflare + Modal</p>
      <h2>{status}</h2>
      <p>{proof?.readme_summary ?? "Live gateway will show the latest Modal eval result here."}</p>
      <dl>
        <div>
          <dt>Policy</dt>
          <dd>{activeModels?.policy_artifact ?? "not promoted yet"}</dd>
        </div>
        <div>
          <dt>Perception</dt>
          <dd>{activeModels?.perception_artifact ?? "not promoted yet"}</dd>
        </div>
      </dl>
      <span className="label label-simulated">simulation only</span>
    </section>
  );
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
