import type { CSSProperties } from "react";

/**
 * Figma's graph paper ("image 15"), drawn in CSS instead of fetched as a PNG.
 *
 * WHY. On production the landing page's LCP element was this decoration: a
 * 350x568 background image at 10% opacity (Lighthouse, mobile, 2026-09-17 —
 * LCP 2.9–3.3 s with a resource-load phase and a failed LCP-discovery insight,
 * because a CSS background is found only after the stylesheet applies). The page
 * waited on the one image nobody is meant to look at. A gradient is not an LCP
 * candidate and costs no request, so LCP falls to the hero's own content.
 *
 * FIDELITY. Measured from public/figma/landing/hero-grid.png (247x401, the
 * frame's export): 1px lines of rgb(197,191,179) on #f5efe3 paper, a 29.2px
 * pitch, the first vertical line at x=13 and the first horizontal at y=8.
 * Every value below is that geometry scaled to the width the paper is drawn at,
 * so the lines land where the PNG put them.
 */
const SOURCE_WIDTH = 247;
const PITCH = 29.2;
const FIRST_X = 13;
const FIRST_Y = 8;
const LINE = "rgb(197, 191, 179)";
const PAPER = "#f5efe3";

const px = (n: number) => `${Number(n.toFixed(2))}px`;

/** Inline style for graph paper whose source image would be drawn `renderedWidth` px wide. */
export function graphPaper(renderedWidth: number): CSSProperties {
  const k = renderedWidth / SOURCE_WIDTH;
  const line = px(Math.max(1, k));
  return {
    backgroundColor: PAPER,
    backgroundImage: `linear-gradient(to right, ${LINE} ${line}, transparent ${line}), linear-gradient(to bottom, ${LINE} ${line}, transparent ${line})`,
    backgroundSize: `${px(PITCH * k)} ${px(PITCH * k)}`,
    backgroundPosition: `${px(FIRST_X * k)} ${px(FIRST_Y * k)}`,
  };
}
