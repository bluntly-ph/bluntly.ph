import assert from "node:assert/strict";
import test from "node:test";

import loader from "../../lib/supabase-image-loader.ts";

/**
 * The image loader every Supabase-hosted image on the site goes through.
 *
 * QA-001 reported product images as "not loading". They were loading — they
 * were arriving squashed. Supabase's render endpoint defaults to
 * `resize=cover`, and cover with a width but no height does not scale the
 * height at all: a 1801x1800 product photo requested at width 240 came back
 * 240x1800, the full original height crammed into a 240px column. At a 36px
 * thumbnail that is a vertical sliver of a photo, which reads as a broken
 * image. Measured against production on 2026-09-09.
 *
 * A Next.js loader is handed the target WIDTH and nothing else, so the height
 * can never be supplied; `resize=contain` is what makes a width-only request
 * mean "scale to fit this width".
 */

const OBJECT =
  "https://project.supabase.co/storage/v1/object/public/product-images/abc/photo.png";

test("a Supabase object is served through the render endpoint", () => {
  const url = new URL(loader({ src: OBJECT, width: 240 }));
  assert.equal(
    url.pathname,
    "/storage/v1/render/image/public/product-images/abc/photo.png",
  );
});

test("the transform preserves aspect ratio", () => {
  // The whole finding, in one assertion: without this the endpoint keeps the
  // original height and only narrows the width.
  const url = new URL(loader({ src: OBJECT, width: 240 }));
  assert.equal(url.searchParams.get("resize"), "contain");
  assert.equal(url.searchParams.get("width"), "240");
});

test("quality defaults to Next's 75 and is overridable", () => {
  assert.equal(
    new URL(loader({ src: OBJECT, width: 240 })).searchParams.get("quality"),
    "75",
  );
  assert.equal(
    new URL(loader({ src: OBJECT, width: 240, quality: 90 })).searchParams.get("quality"),
    "90",
  );
});

test("a non-Supabase source is returned untouched", () => {
  // A blob: preview of a photo the reviewer just picked, or any future host.
  for (const src of [
    "blob:http://localhost:3000/9f0f-4d",
    "https://cdn.example.test/img/thing.png",
    "/local/asset.png",
  ]) {
    assert.equal(loader({ src, width: 240 }), src);
  }
});

test("an existing query string on the object survives", () => {
  const withQuery = `${OBJECT}?v=2`;
  const url = new URL(loader({ src: withQuery, width: 120 }));
  assert.equal(url.searchParams.get("v"), "2");
  assert.equal(url.searchParams.get("resize"), "contain");
});
