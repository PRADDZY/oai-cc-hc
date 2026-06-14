import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import {
  fetchActiveModels,
  fetchHealth,
  fetchLatestProof,
  requestMissionProposal,
} from "./api";
import { guidedScenario, scriptedPolicyProposal } from "./scenario";
import { MissionTheater } from "./MissionTheater";
import type {
  ActiveModelManifest,
  ApprovalDecision,
  DroneState,
  LivePolicyProposal,
  MissionPhase,
  MissionSnapshot,
  ProofPayload,
  ProofSummary,
  WorkerHealth,
} from "./types";
import { useMissionPlayback } from "./useMissionPlayback";
import "./styles.css";

const roleLabels: Record<DroneState["role"], string> = {
  aid_drop: "Aid",
  hold: "Hold",
  relay: "Relay",
  return: "RTB",
  search: "Search",
};

const speedOptions = [0.5, 1, 2] as const;

export function App() {
  const playback = useMissionPlayback();
  const [health, setHealth] = useState<WorkerHealth | null>(null);
  const [proof, setProof] = useState<ProofSummary | null>(null);
  const [activeModels, setActiveModels] = useState<ActiveModelManifest | null>(null);
  const [liveProposal, setLiveProposal] = useState<LivePolicyProposal | null>(null);
  const [proposalStatus, setProposalStatus] = useState<"idle" | "loading" | "live" | "fallback">(
    "idle",
  );
  const proposalRunRef = useRef<number | null>(null);

  useEffect(() => {
    let mounted = true;
    void Promise.all([fetchHealth(), fetchLatestProof(), fetchActiveModels()]).then(
      ([nextHealth, nextProof, models]) => {
        if (!mounted) {
          return;
        }
        const payload = proofPayload(nextProof);
        setHealth(nextHealth);
        setProof(nextProof);
        setActiveModels(models ?? payload?.active_models ?? nextProof?.active_models ?? null);
      },
    );
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (
      playback.currentPhase.id !== "policy-handoff" ||
      proposalRunRef.current === playback.runId
    ) {
      return;
    }

    proposalRunRef.current = playback.runId;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 6000);
    setProposalStatus("loading");
    setLiveProposal(null);

    void requestMissionProposal(
      playback.currentPhase.mission.missionId,
      policyObservation(playback.currentPhase.mission),
      controller.signal,
    ).then((proposal) => {
      if (controller.signal.aborted || proposalRunRef.current !== playback.runId) {
        return;
      }
      if (proposal) {
        setLiveProposal(proposal);
        setProposalStatus("live");
      } else {
        setLiveProposal(scriptedPolicyProposal);
        setProposalStatus("fallback");
      }
    });

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [playback.currentPhase, playback.runId]);

  const proposal = liveProposal ?? scriptedPolicyProposal;
  const heldOutcome = playback.isComplete && playback.approvalDecision === "held";

  return (
    <main className="command-shell" data-phase={playback.currentPhase.id}>
      <div className="ambient-grid" aria-hidden="true" />
      <MissionHeader
        phase={playback.currentPhase}
        phaseIndex={playback.phaseIndex}
        progress={playback.progress}
        elapsedLabel={playback.elapsedLabel}
        health={health}
      />

      <PlaybackControls playback={playback} />

      <section className="command-layout">
        <MissionMap
          phase={playback.currentPhase}
          proposal={proposal}
          approvalDecision={playback.approvalDecision}
          heldOutcome={heldOutcome}
        />
        <aside className="decision-rail">
          <PhasePanel
            phase={playback.currentPhase}
            proposal={proposal}
            proposalStatus={proposalStatus}
            approvalDecision={playback.approvalDecision}
            approvalCountdown={playback.approvalCountdown}
            heldOutcome={heldOutcome}
            onApprove={playback.approve}
            onHold={playback.overrideHold}
          />
          <SwarmRoster drones={playback.currentPhase.mission.drones} />
          <ProofDrawer proof={proof} activeModels={activeModels} health={health} />
        </aside>
      </section>

      <MissionTimeline activeIndex={playback.phaseIndex} />
    </main>
  );
}

function MissionHeader({
  phase,
  phaseIndex,
  progress,
  elapsedLabel,
  health,
}: {
  phase: MissionPhase;
  phaseIndex: number;
  progress: number;
  elapsedLabel: string;
  health: WorkerHealth | null;
}) {
  return (
    <header className="mission-header">
      <div className="brand-lockup">
        <div className="brand-mark" aria-hidden="true">
          FR
        </div>
        <div>
          <p className="system-label">Flood Rescue / Mission Control</p>
          <h1>{phase.title}</h1>
          <p className="phase-narrative">{phase.narrative}</p>
        </div>
      </div>
      <div className="mission-telemetry" aria-label="Mission playback telemetry">
        <div>
          <span>Mission time</span>
          <strong>{elapsedLabel}</strong>
        </div>
        <div>
          <span>Phase</span>
          <strong>
            {String(phaseIndex + 1).padStart(2, "0")} / {String(guidedScenario.length).padStart(2, "0")}
          </strong>
        </div>
        <div>
          <span>Link</span>
          <strong className={health?.status === "ok" ? "status-live" : "status-wait"}>
            {health?.status === "ok" ? "ONLINE" : "SYNCING"}
          </strong>
        </div>
      </div>
      <div className="mission-progress" aria-label={`${Math.round(progress * 100)}% complete`}>
        <span style={{ width: `${progress * 100}%` }} />
      </div>
    </header>
  );
}

function PlaybackControls({ playback }: { playback: ReturnType<typeof useMissionPlayback> }) {
  return (
    <nav className="playback-bar" aria-label="Scenario playback controls">
      <div className="playback-state">
        <span className={`pulse-dot ${playback.isPlaying ? "active" : ""}`} />
        <strong>{playback.isComplete ? "MISSION COMPLETE" : playback.isPlaying ? "AUTOPLAY" : "PAUSED"}</strong>
        <span>{playback.currentPhase.kicker}</span>
      </div>
      <div className="control-cluster">
        <button
          type="button"
          className="control-primary"
          onClick={playback.togglePlayback}
          disabled={playback.isComplete}
        >
          {playback.isPlaying ? "Pause" : "Resume"}
        </button>
        <button type="button" onClick={playback.next} disabled={playback.isComplete}>
          Next phase
        </button>
        <button type="button" onClick={playback.restart}>
          Restart
        </button>
        <div className="speed-switch" aria-label="Playback speed">
          {speedOptions.map((speed) => (
            <button
              key={speed}
              type="button"
              className={playback.speed === speed ? "selected" : ""}
              onClick={() => playback.setSpeed(speed)}
              aria-pressed={playback.speed === speed}
            >
              {speed}x
            </button>
          ))}
        </div>
      </div>
    </nav>
  );
}

function MissionMap({
  phase,
  proposal,
  approvalDecision,
  heldOutcome,
}: {
  phase: MissionPhase;
  proposal: LivePolicyProposal;
  approvalDecision: ApprovalDecision;
  heldOutcome: boolean;
}) {
  const mission = phase.mission;
  const displayVictims = mission.victims.map((victim) =>
    heldOutcome && victim.status === "aided" ? { ...victim, status: "confirmed" as const } : victim,
  );

  return (
    <section className="mission-stage" aria-label="Animated flood rescue map">
      <div className="stage-toolbar">
        <div>
          <p className="system-label">{phase.feedLabel}</p>
          <h2>{phase.objective}</h2>
        </div>
        <div className="map-legend" aria-label="Map legend">
          <span><i className="legend-flood" /> flood probability</span>
          <span><i className="legend-victim" /> victim signal</span>
          <span><i className="legend-drone" /> swarm agent</span>
        </div>
      </div>

      <div className="map-viewport">
        <div className="map-terrain" aria-hidden="true" />
        <div className="river river-a" aria-hidden="true" />
        <div className="river river-b" aria-hidden="true" />
        <div className="scan-beam" aria-hidden="true" />
        <div className="map-coordinate x-axis">73.8567 E</div>
        <div className="map-coordinate y-axis">18.5204 N</div>
        <MissionTheater
          phase={phase}
          proposal={proposal}
          approvalDecision={approvalDecision}
          heldOutcome={heldOutcome}
        />

        {mission.floodCells.map((cell, index) => (
          <span
            key={cell.id}
            className="flood-cell"
            style={{
              "--x": cell.x,
              "--y": cell.y,
              "--probability": cell.probability,
              "--reveal-delay": `${index * 90}ms`,
            } as CSSProperties}
            title={`Flood probability ${Math.round(cell.probability * 100)}%`}
          />
        ))}

        <svg className="relay-layer" viewBox="0 0 1200 1200" aria-hidden="true">
          {mission.relayLinks.map(([from, to]) => {
            const start = mission.drones.find((drone) => drone.id === from);
            const end = mission.drones.find((drone) => drone.id === to);
            if (!start || !end) {
              return null;
            }
            return (
              <line
                key={`${from}-${to}`}
                x1={(start.x + 0.5) * 100}
                y1={(start.y + 0.5) * 100}
                x2={(end.x + 0.5) * 100}
                y2={(end.y + 0.5) * 100}
              />
            );
          })}
        </svg>

        {displayVictims.map((victim) => (
          <div
            key={victim.id}
            className={`victim-marker ${victim.status}`}
            style={{ "--x": victim.x, "--y": victim.y } as CSSProperties}
            aria-label={`${victim.id} ${victim.status}`}
          >
            <span className="victim-pulse" />
            <strong>{victim.id.toUpperCase()}</strong>
            <small>{victim.status === "aided" ? "AIDED" : `${Math.round(victim.confidence * 100)}%`}</small>
          </div>
        ))}

        {mission.drones.map((drone) => (
          <div
            key={drone.id}
            className={`drone-marker role-${drone.role}`}
            style={{ "--x": drone.x, "--y": drone.y } as CSSProperties}
            aria-label={`${drone.id} ${roleLabels[drone.role]}`}
          >
            <span className="drone-glyph" />
            <strong>{drone.id.replace("drone_", "D")}</strong>
            <small>{roleLabels[drone.role]}</small>
          </div>
        ))}

        {phase.id === "policy-handoff" && (
          <div className="policy-vector" aria-label="Live policy coordination vector">
            <span>ADVISORY: {proposal.proposal.action.toUpperCase()}</span>
            <div>
              {proposal.proposal.coordination_message.map((value, index) => (
                <i key={index} style={{ height: `${Math.max(value * 100, 8)}%` }} />
              ))}
            </div>
          </div>
        )}

        {approvalDecision === "held" && <div className="hold-overlay">SAFE HOLD ENGAGED</div>}
      </div>

      <footer className="stage-footer">
        <span>SIMULATION REPLAY / SEN1FLOODS11-BASED PERCEPTION</span>
        <span>Grid 12 x 12 / Pune scenario</span>
        <span>Confidence {Math.round(mission.confidence * 100)}%</span>
      </footer>
    </section>
  );
}

function PhasePanel({
  phase,
  proposal,
  proposalStatus,
  approvalDecision,
  approvalCountdown,
  heldOutcome,
  onApprove,
  onHold,
}: {
  phase: MissionPhase;
  proposal: LivePolicyProposal;
  proposalStatus: "idle" | "loading" | "live" | "fallback";
  approvalDecision: ApprovalDecision;
  approvalCountdown: number | null;
  heldOutcome: boolean;
  onApprove: () => void;
  onHold: () => void;
}) {
  const showPolicy = [
    "policy-handoff",
    "safety-review",
    "operator-approval",
    "aid-delivery",
    "mission-complete",
    "mission-held",
  ].includes(phase.id);
  const sourceLabel =
    proposalStatus === "live"
      ? "LIVE MODAL ADVISORY"
      : proposalStatus === "loading"
        ? "REQUESTING MODAL"
        : "RESILIENT SCRIPTED ADVISORY";

  return (
    <section className="phase-panel" aria-live="polite">
      <div className="panel-index">{phase.kicker.slice(0, 2)}</div>
      <p className="system-label">{phase.kicker}</p>
      <h2>{heldOutcome ? "Mission held safely" : phase.title}</h2>
      <p>{heldOutcome ? "Operator hold preserved the victim location and prevented aid execution." : phase.narrative}</p>

      {showPolicy && (
        <div className={`advisory-card status-${proposalStatus}`}>
          <div className="advisory-source">
            <span>{sourceLabel}</span>
            <i className={proposalStatus === "live" ? "live" : ""} />
          </div>
          <strong>{proposal.proposal.action.replace("_", " ").toUpperCase()}</strong>
          <dl>
            <div><dt>Confidence</dt><dd>{Math.round(proposal.proposal.confidence * 100)}%</dd></div>
            <div><dt>Safety</dt><dd>{proposal.safety.status.toUpperCase()}</dd></div>
            <div><dt>Shield</dt><dd>{proposal.safety.shield_status ? "REPORTED ON" : "REPORTED OFF"}</dd></div>
          </dl>
          <small>Advisory simulation output. Guided outcome remains operator-controlled.</small>
        </div>
      )}

      {phase.id === "operator-approval" && (
        <div className="approval-gate">
          <div className="approval-countdown">
            <span>Scripted demo operator</span>
            <strong>{approvalCountdown ?? 0}s</strong>
          </div>
          <button type="button" className="approve-button" onClick={onApprove}>
            Approve rescue route
          </button>
          <button type="button" className="hold-button" onClick={onHold}>
            Override to safe hold
          </button>
          {approvalDecision !== null && (
            <p className="decision-record">Decision recorded: {approvalDecision.replace("-", " ")}</p>
          )}
        </div>
      )}

      <div className="phase-readouts">
        <Metric label="Active drones" value={String(phase.mission.drones.length)} />
        <Metric
          label="Confirmed victims"
          value={String(phase.mission.victims.filter((victim) => victim.status !== "unconfirmed").length)}
        />
        <Metric
          label="Flood cells"
          value={String(phase.mission.floodCells.length)}
        />
        <Metric
          label="Mean battery"
          value={`${Math.round(
            phase.mission.drones.reduce((sum, drone) => sum + drone.battery, 0) /
              Math.max(phase.mission.drones.length, 1),
          )}%`}
        />
      </div>
    </section>
  );
}

function SwarmRoster({ drones }: { drones: DroneState[] }) {
  return (
    <section className="swarm-roster" aria-label="Live swarm roster">
      <div className="rail-heading">
        <h2>Swarm telemetry</h2>
        <span>{drones.length} agents</span>
      </div>
      <div className="roster-grid">
        {drones.map((drone) => (
          <article key={drone.id}>
            <div className={`mini-drone role-${drone.role}`} />
            <div>
              <strong>{drone.id.replace("drone_", "D")}</strong>
              <span>{roleLabels[drone.role]} / {drone.status}</span>
            </div>
            <div className="battery-readout">
              <strong>{drone.battery}%</strong>
              <i style={{ width: `${drone.battery}%` }} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ProofDrawer({
  proof,
  activeModels,
  health,
}: {
  proof: ProofSummary | null;
  activeModels: ActiveModelManifest | null;
  health: WorkerHealth | null;
}) {
  const payload = proofPayload(proof);
  const perception = payload?.proofs?.perception?.payload;
  const rl = payload?.proofs?.rl?.payload;
  const passed = Boolean(payload?.passed ?? proof?.passed);
  return (
    <details className="proof-drawer">
      <summary>
        <span>
          <i className={passed ? "proof-pass" : "proof-wait"} />
          Training & deployment proof
        </span>
        <strong>{passed ? "GATE PASSED" : "CONNECTING"}</strong>
      </summary>
      <div className="proof-content">
        <div className="proof-signals">
          <span>Worker {health?.status ?? "checking"}</span>
          <span>Modal {health?.modal_configured ? "configured" : "fallback-safe"}</span>
        </div>
        <Metric label="Perception IoU" value={formatPercent(perception?.event_held_out_iou)} />
        <Metric label="RL lives aided" value={formatMetric(rl?.candidate?.lives_aided_safely_mean)} />
        <Metric label="Safety failures" value={formatInteger(rl?.release_gate?.safety_failures)} />
        <p><strong>Policy:</strong> {activeModels?.policy_artifact ?? "loading"}</p>
        <p><strong>Perception:</strong> {activeModels?.perception_artifact ?? "loading"}</p>
      </div>
    </details>
  );
}

function MissionTimeline({ activeIndex }: { activeIndex: number }) {
  return (
    <section className="mission-timeline" aria-label="Guided mission timeline">
      {guidedScenario.map((phase, index) => (
        <article
          key={phase.id}
          className={index === activeIndex ? "active" : index < activeIndex ? "complete" : ""}
        >
          <span className="timeline-node">{String(index + 1).padStart(2, "0")}</span>
          <div>
            <strong>{phase.kicker}</strong>
            <p>{phase.objective}</p>
          </div>
        </article>
      ))}
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

function policyObservation(mission: MissionSnapshot): Record<string, unknown> {
  const lead = mission.drones[0];
  return {
    position: [lead?.x ?? 0, lead?.y ?? 0, 1],
    battery: lead?.battery ?? 92,
    known_victims: mission.victims.filter((victim) => victim.status !== "unconfirmed").length,
    flood_cells: mission.floodCells.length,
    rescued_victims: mission.victims.filter((victim) => victim.status === "aided").length,
    link_quality: lead?.linkQuality ?? 0.86,
    action_mask: [1, 1, 0, 1, 1, 1],
  };
}

function formatMetric(value: number | undefined): string {
  return typeof value === "number" && !Number.isNaN(value) ? value.toFixed(2) : "--";
}

function formatPercent(value: number | undefined): string {
  return typeof value === "number" && !Number.isNaN(value) ? `${Math.round(value * 100)}%` : "--";
}

function formatInteger(value: number | undefined): string {
  return typeof value === "number" && !Number.isNaN(value) ? String(Math.round(value)) : "--";
}

export default App;
