import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useMissionPlayback } from "./useMissionPlayback";

const APPROVAL_PHASE_START_MS = 55_000;

describe("useMissionPlayback", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("autoplays from the first phase and reports progress", () => {
    const { result } = renderHook(() => useMissionPlayback());

    expect(result.current.currentPhase.id).toBe("satellite-intake");
    expect(result.current.phaseIndex).toBe(0);
    expect(result.current.isPlaying).toBe(true);
    expect(result.current.progress).toBe(0);

    act(() => {
      vi.advanceTimersByTime(8_000);
    });

    expect(result.current.currentPhase.id).toBe("flood-belief");
    expect(result.current.phaseIndex).toBe(1);
    expect(result.current.progress).toBeGreaterThan(0);
  });

  it("pauses, resumes, steps forward, and changes playback speed", () => {
    const { result } = renderHook(() => useMissionPlayback());

    act(() => {
      result.current.togglePlayback();
    });
    act(() => {
      vi.advanceTimersByTime(20_000);
    });
    expect(result.current.currentPhase.id).toBe("satellite-intake");

    act(() => {
      result.current.setSpeed(2);
    });
    act(() => {
      result.current.togglePlayback();
    });
    act(() => {
      vi.advanceTimersByTime(4_000);
    });
    expect(result.current.speed).toBe(2);
    expect(result.current.currentPhase.id).toBe("flood-belief");

    act(() => {
      result.current.next();
    });
    expect(result.current.currentPhase.id).toBe("victim-triage");
  });

  it("restarts the run with fresh playback state", () => {
    const { result } = renderHook(() => useMissionPlayback());
    const firstRunId = result.current.runId;

    act(() => {
      vi.advanceTimersByTime(18_000);
      result.current.restart();
    });

    expect(result.current.runId).toBe(firstRunId + 1);
    expect(result.current.currentPhase.id).toBe("satellite-intake");
    expect(result.current.phaseIndex).toBe(0);
    expect(result.current.isPlaying).toBe(true);
    expect(result.current.approvalDecision).toBeNull();
    expect(result.current.progress).toBe(0);
  });

  it("freezes the approval countdown while paused and auto-approves the demo run", () => {
    const { result } = renderHook(() => useMissionPlayback());

    act(() => {
      vi.advanceTimersByTime(APPROVAL_PHASE_START_MS);
    });
    expect(result.current.currentPhase.id).toBe("operator-approval");
    expect(result.current.approvalCountdown).toBe(5);

    act(() => {
      vi.advanceTimersByTime(2_000);
    });
    act(() => {
      result.current.togglePlayback();
    });
    expect(result.current.approvalCountdown).toBe(3);

    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(result.current.approvalCountdown).toBe(3);
    expect(result.current.currentPhase.id).toBe("operator-approval");

    act(() => {
      result.current.togglePlayback();
    });
    act(() => {
      vi.advanceTimersByTime(3_000);
    });
    expect(result.current.approvalDecision).toBe("scripted");
    expect(result.current.currentPhase.id).toBe("aid-delivery");
  });

  it("supports immediate manual approval", () => {
    const { result } = renderHook(() => useMissionPlayback());

    act(() => {
      vi.advanceTimersByTime(APPROVAL_PHASE_START_MS);
    });
    act(() => {
      result.current.approve();
    });

    expect(result.current.approvalDecision).toBe("approved");
    expect(result.current.currentPhase.id).toBe("aid-delivery");
    expect(result.current.isPlaying).toBe(true);
  });

  it("holds safely until Next and resolves without showing aid delivery", () => {
    const { result } = renderHook(() => useMissionPlayback());

    act(() => {
      vi.advanceTimersByTime(APPROVAL_PHASE_START_MS);
    });
    act(() => {
      result.current.overrideHold();
    });

    expect(result.current.approvalDecision).toBe("held");
    expect(result.current.isPlaying).toBe(false);
    expect(result.current.currentPhase.id).toBe("operator-approval");

    act(() => {
      result.current.next();
    });

    expect(result.current.currentPhase.id).toBe("mission-held");
    expect(result.current.isComplete).toBe(true);
    expect(result.current.isPlaying).toBe(false);
    expect(
      result.current.currentPhase.mission.victims.some(
        (victim) => victim.status === "aided",
      ),
    ).toBe(false);
  });

  it("marks the approved final phase complete after its display duration", () => {
    const { result } = renderHook(() => useMissionPlayback());

    act(() => {
      vi.advanceTimersByTime(81_000);
    });

    expect(result.current.currentPhase.id).toBe("mission-complete");
    expect(result.current.isComplete).toBe(true);
    expect(result.current.isPlaying).toBe(false);
    expect(result.current.progress).toBe(1);
  });
});
