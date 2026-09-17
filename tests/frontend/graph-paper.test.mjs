import assert from "node:assert/strict";
import test from "node:test";

import { graphPaper } from "../../components/ui/graph-paper.ts";

/**
 * The CSS graph paper that replaced Figma's "image 15" PNG. Two promises: it
 * never becomes an image request again (that was the landing page's LCP
 * element), and its lines land where the PNG put them.
 */

test("draws with gradients, never a url() image", () => {
  const style = graphPaper(350);
  assert.match(String(style.backgroundImage), /^linear-gradient/);
  assert.doesNotMatch(String(style.backgroundImage), /url\(/);
});

test("the landing hero's 350px paper keeps the PNG's geometry scaled by 350/247", () => {
  const style = graphPaper(350);
  // 29.2px pitch x 1.417 = 41.38px; first lines at 13 and 8 source px.
  assert.equal(style.backgroundSize, "41.38px 41.38px");
  assert.equal(style.backgroundPosition, "18.42px 11.34px");
});

test("the composer's 390px paper scales the same geometry", () => {
  const style = graphPaper(390);
  assert.equal(style.backgroundSize, "46.11px 46.11px");
  assert.equal(style.backgroundPosition, "20.53px 12.63px");
});

test("lines never go thinner than one CSS pixel", () => {
  assert.match(String(graphPaper(100).backgroundImage), /rgb\(197, 191, 179\) 1px/);
});
