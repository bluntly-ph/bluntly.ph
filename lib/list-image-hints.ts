/**
 * How the Nth thumbnail in a list should load.
 *
 * The lists used to mark `priority` on row 0. That assumed row 0 has a photo,
 * and in production most do not: 5 of 38 products carry an image, so row 0 is
 * usually the grey placeholder and the first REAL image is a later row — which
 * then loaded lazily. Lighthouse on production /search (2026-09-17) named that
 * lazy `<img>` as the LCP element and flagged the LCP-discovery insight: the one
 * image the metric waits on was the one the page told the browser to defer.
 *
 * So the rule is about what is on screen, not about index 0:
 *
 *   - rows inside the first `aboveFold` load eagerly — they are visible on
 *     arrival, and deferring a visible image only delays it;
 *   - the first row that actually has an image, if it is inside that window,
 *     also gets `fetchPriority="high"` — the likely LCP element;
 *   - everything below stays lazy, so a long list does not trade page weight
 *     for a metric.
 *
 * `loading` + `fetchPriority` rather than Next's `priority`/`preload`: Next 16
 * deprecated `priority`, and its docs recommend these two over `preload` when
 * more than one image could be the LCP element depending on the viewport
 * (node_modules/next/dist/docs/01-app/03-api-reference/02-components/image.md).
 */
export type ImageHints = {
  loading: "eager" | "lazy";
  fetchPriority: "high" | "auto";
};

export const LAZY: ImageHints = { loading: "lazy", fetchPriority: "auto" };

export function listImageHints(index: number, firstImageIndex: number, aboveFold: number): ImageHints {
  const visible = index < aboveFold;
  return {
    loading: visible ? "eager" : "lazy",
    fetchPriority: visible && index === firstImageIndex ? "high" : "auto",
  };
}

/** Index of the first item with an image, or -1. */
export function firstImageIndex<T>(items: readonly T[], hasImage: (item: T) => boolean): number {
  return items.findIndex(hasImage);
}
