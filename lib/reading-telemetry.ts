import type { InteractionKind } from "./reading-telemetry-events";

export const MAX_SESSION_MS = 1_800_000;
const IDLE_MS = 30_000;
const MAX_CHECKPOINTS = 16;

export type ActivityGates = {
  visible: boolean;
  focused: boolean;
  recentlyActive: boolean;
  bodyVisible: boolean;
};

export type ScrollMilestone = 0 | 25 | 50 | 75 | 100;

export type ReadingTelemetryPayload = {
  impression_id: string;
  review_id: string;
  seq: number;
  active_ms: number;
  body_active_ms: number;
  wall_ms: number;
  scroll_pct: ScrollMilestone;
  vote_after_ms: number | null;
  report_after_ms: number | null;
  comment_after_ms: number | null;
  share_after_ms: number | null;
  photo_after_ms: number | null;
  outlink_after_ms: number | null;
};

type InteractionTimings = Record<InteractionKind, number | null>;

const CHECKPOINTS = [10_000, 30_000, 60_000, 120_000] as const;

function finiteNow(nowMs: number): number | null {
  return Number.isFinite(nowMs) ? nowMs : null;
}

function cappedAdd(total: number, delta: number): number {
  return Math.min(MAX_SESSION_MS, total + Math.max(0, delta));
}

export function snapScroll(percent: number): ScrollMilestone {
  if (!Number.isFinite(percent) || percent < 25) return 0;
  if (percent < 50) return 25;
  if (percent < 75) return 50;
  if (percent < 100) return 75;
  return 100;
}

export function nextCheckpoint(activeMs: number, sentThresholds: ReadonlySet<number>): number | null {
  if (!Number.isFinite(activeMs) || activeMs < CHECKPOINTS[0] || activeMs > MAX_SESSION_MS) {
    return null;
  }

  // A caller normally seeds the set with the sequence-zero start checkpoint.
  // Treat it as sent even if an external caller does not, so it cannot create a
  // sixteenth follow-up checkpoint by accident.
  const totalSent = sentThresholds.size + (sentThresholds.has(0) ? 0 : 1);
  if (totalSent >= MAX_CHECKPOINTS) return null;

  for (const threshold of CHECKPOINTS) {
    if (activeMs < threshold) return null;
    if (!sentThresholds.has(threshold)) return threshold;
  }

  for (let threshold = 240_000; threshold <= MAX_SESSION_MS; threshold += 120_000) {
    if (activeMs < threshold) return null;
    if (!sentThresholds.has(threshold)) return threshold;
  }

  return null;
}

export class ReadingAccumulator {
  private activeMs = 0;
  private bodyActiveMs = 0;
  private wallMs = 0;
  private scroll: ScrollMilestone = 0;
  private lastNowMs: number;
  private lastActivityMs: number;
  private readonly startedAtMs: number;
  private readonly interactions: InteractionTimings = {
    vote: null,
    report: null,
    comment: null,
    share: null,
    photo: null,
    outlink: null,
  };

  constructor(startedAtMs: number) {
    const start = finiteNow(startedAtMs) ?? 0;
    this.startedAtMs = start;
    this.lastNowMs = start;
    this.lastActivityMs = start;
  }

  advance(nowMs: number, gates: ActivityGates): void {
    const now = finiteNow(nowMs);
    if (now === null || now <= this.lastNowMs) return;

    const previousNow = this.lastNowMs;
    this.lastNowMs = now;
    this.wallMs = cappedAdd(this.wallMs, now - previousNow);

    const recentlyActive = now - this.lastActivityMs <= IDLE_MS;
    if (!gates.visible || !gates.focused || !gates.recentlyActive || !recentlyActive) return;

    const activeDelta = now - Math.max(previousNow, this.lastActivityMs);
    this.activeMs = cappedAdd(this.activeMs, activeDelta);
    if (gates.bodyVisible) {
      this.bodyActiveMs = cappedAdd(this.bodyActiveMs, activeDelta);
    }
  }

  noteActivity(nowMs: number): void {
    const now = finiteNow(nowMs);
    if (now === null) return;
    this.lastActivityMs = Math.max(this.lastActivityMs, now);
  }

  noteInteraction(kind: InteractionKind, nowMs: number): void {
    if (this.interactions[kind] !== null) return;

    const now = finiteNow(nowMs);
    if (now === null) return;
    this.interactions[kind] = Math.min(MAX_SESSION_MS, Math.max(0, now - this.startedAtMs));
  }

  noteScroll(percent: number): void {
    this.scroll = Math.max(this.scroll, snapScroll(percent)) as ScrollMilestone;
  }

  payload(impressionId: string, reviewId: string, seq: number): ReadingTelemetryPayload {
    return {
      impression_id: impressionId,
      review_id: reviewId,
      seq,
      active_ms: this.activeMs,
      body_active_ms: this.bodyActiveMs,
      wall_ms: this.wallMs,
      scroll_pct: this.scroll,
      vote_after_ms: this.interactions.vote,
      report_after_ms: this.interactions.report,
      comment_after_ms: this.interactions.comment,
      share_after_ms: this.interactions.share,
      photo_after_ms: this.interactions.photo,
      outlink_after_ms: this.interactions.outlink,
    };
  }
}
