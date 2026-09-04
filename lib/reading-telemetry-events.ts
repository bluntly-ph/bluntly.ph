export const TELEMETRY_EVENT = "bluntly:review-interaction";

export type InteractionKind =
  | "vote"
  | "report"
  | "comment"
  | "share"
  | "photo"
  | "outlink";

export type InteractionDetail = {
  reviewId: string;
  kind: InteractionKind;
};

export function markInteraction(reviewId: string, kind: InteractionKind): void {
  if (typeof window === "undefined") return;

  window.dispatchEvent(new CustomEvent<InteractionDetail>(TELEMETRY_EVENT, {
    detail: { reviewId, kind },
  }));
}
