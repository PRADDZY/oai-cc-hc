import { useEffect, useState } from "react";
import { guidedScenario, heldMissionPhase } from "./scenario";
import type { ApprovalDecision, MissionPhase, PlaybackSpeed } from "./types";

const tickMs = 250;
const totalDurationMs = guidedScenario.reduce((total, phase) => total + phase.durationMs, 0);
const approvalPhaseId = "operator-approval";
const approvalPhaseIndex = guidedScenario.findIndex((phase) => phase.id === approvalPhaseId);
const approvalPhaseStartMs = phaseStartMs(approvalPhaseIndex);
const approvalPhaseEndMs = approvalPhaseStartMs + guidedScenario[approvalPhaseIndex].durationMs;

export interface MissionPlaybackState {
  currentPhase: MissionPhase;
  phaseIndex: number;
  isPlaying: boolean;
  speed: PlaybackSpeed;
  progress: number;
  runId: number;
  approvalDecision: ApprovalDecision;
  approvalCountdown: number | null;
  isComplete: boolean;
  elapsedLabel: string;
  togglePlayback: () => void;
  next: () => void;
  restart: () => void;
  setSpeed: (speed: PlaybackSpeed) => void;
  approve: () => void;
  overrideHold: () => void;
}

export function useMissionPlayback(): MissionPlaybackState {
  const [elapsedMs, setElapsedMs] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [speed, setPlaybackSpeed] = useState<PlaybackSpeed>(1);
  const [runId, setRunId] = useState(1);
  const [approvalDecision, setApprovalDecision] = useState<ApprovalDecision>(null);
  const [isComplete, setIsComplete] = useState(false);
  const [heldComplete, setHeldComplete] = useState(false);

  const phaseIndex = phaseIndexForElapsed(elapsedMs);
  const currentPhase = heldComplete ? heldMissionPhase : guidedScenario[phaseIndex];
  const effectiveApprovalDecision =
    approvalDecision ?? (!heldComplete && elapsedMs >= approvalPhaseEndMs ? "scripted" : null);
  const approvalCountdown =
    currentPhase.id === approvalPhaseId && effectiveApprovalDecision !== "held"
      ? Math.max(0, Math.ceil((approvalPhaseEndMs - elapsedMs) / 1000))
      : null;
  const progress = isComplete ? 1 : Math.min(elapsedMs / totalDurationMs, 1);

  useEffect(() => {
    if (!isPlaying || isComplete || heldComplete) {
      return;
    }

    const timer = window.setInterval(() => {
      setElapsedMs((current) => Math.min(current + tickMs * speed, totalDurationMs));
    }, tickMs);

    return () => window.clearInterval(timer);
  }, [heldComplete, isComplete, isPlaying, speed]);

  useEffect(() => {
    if (elapsedMs >= approvalPhaseEndMs && approvalDecision === null) {
      setApprovalDecision("scripted");
    }

    if (elapsedMs >= totalDurationMs && !isComplete) {
      setIsComplete(true);
      setIsPlaying(false);
    }
  }, [approvalDecision, elapsedMs, isComplete]);

  function togglePlayback() {
    if (isComplete || effectiveApprovalDecision === "held") {
      return;
    }
    setIsPlaying((current) => !current);
  }

  function next() {
    if (isComplete) {
      return;
    }

    if (currentPhase.id === approvalPhaseId && effectiveApprovalDecision === "held") {
      setHeldComplete(true);
      setIsComplete(true);
      setIsPlaying(false);
      return;
    }

    if (currentPhase.id === approvalPhaseId && effectiveApprovalDecision === null) {
      setApprovalDecision("scripted");
    }

    if (phaseIndex >= guidedScenario.length - 1) {
      setElapsedMs(totalDurationMs);
      setIsComplete(true);
      setIsPlaying(false);
      return;
    }

    setElapsedMs(phaseStartMs(phaseIndex + 1));
    setIsPlaying(true);
  }

  function restart() {
    setElapsedMs(0);
    setIsPlaying(true);
    setRunId((current) => current + 1);
    setApprovalDecision(null);
    setIsComplete(false);
    setHeldComplete(false);
  }

  function approve() {
    if (currentPhase.id !== approvalPhaseId || isComplete) {
      return;
    }
    setApprovalDecision("approved");
    setElapsedMs(phaseStartMs(phaseIndex + 1));
    setIsPlaying(true);
  }

  function overrideHold() {
    if (currentPhase.id !== approvalPhaseId || isComplete) {
      return;
    }
    setApprovalDecision("held");
    setIsPlaying(false);
  }

  return {
    currentPhase,
    phaseIndex,
    isPlaying,
    speed,
    progress,
    runId,
    approvalDecision: effectiveApprovalDecision,
    approvalCountdown,
    isComplete,
    elapsedLabel: formatElapsed(elapsedMs),
    togglePlayback,
    next,
    restart,
    setSpeed: setPlaybackSpeed,
    approve,
    overrideHold,
  };
}

function phaseIndexForElapsed(elapsedMs: number): number {
  let cursor = 0;

  for (let index = 0; index < guidedScenario.length; index += 1) {
    cursor += guidedScenario[index].durationMs;
    if (elapsedMs < cursor) {
      return index;
    }
  }

  return guidedScenario.length - 1;
}

function phaseStartMs(index: number): number {
  return guidedScenario
    .slice(0, Math.max(index, 0))
    .reduce((total, phase) => total + phase.durationMs, 0);
}

function formatElapsed(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}
