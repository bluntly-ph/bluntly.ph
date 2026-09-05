// A narrowly-scoped local fixture backend for e2e/reading-telemetry.spec.ts.
//
// WHY THIS EXISTS. The default Playwright setup (`npm run dev:all`) starts the
// real FastAPI backend against a real Postgres, which this environment does
// not have working locally (no reachable local Postgres; Supabase requires
// network credentials this sandbox does not carry). Task 7 needs a REAL
// review page rendered by the REAL Next.js server and the REAL React
// component tree — not a static mock of the page — so this is a minimal,
// dependency-free HTTP server standing in for the one thing the page
// genuinely cannot render without: `GET /api/v1/reviews/:id/full`.
//
// WHAT IT DOES NOT COVER. Every other server-side call the review page makes
// (`getComments`, `getPricePanel`, `searchReviews`, `getUser` when signed out)
// already catches its own failure and degrades to `[]`/`null` in
// lib/reviews.ts, lib/comments.ts, lib/products.ts, lib/dal.ts — confirmed by
// reading those functions, not assumed. So a 404 for those paths is the
// correct fixture behaviour, not a gap: it exercises the same fallback path
// production takes during a real backend hiccup.
//
// FIXTURE LIMIT, stated plainly: this proves the review page's OWN reading
// lifecycle (mount, visibility, scroll, pagehide, navigation cleanup) against
// real markup and a real browser. It does NOT exercise authenticated
// vote/report/comment success against a real backend contract — those three
// interactions need a signed-in session and a real API behind
// `/api/bff/...`, which is a materially larger fixture (auth, database rows,
// FK integrity) out of scope for this task's six specified scenarios, none of
// which require it. `markInteraction` on the success paths is covered instead
// by direct unit assertions on the client event boundary (Task 6) and by
// reading each component's success branch at review time (this task's
// report).
//
// The two review ids below let the "Related reviews" sidebar link from one to
// the other, which is what the navigation/cleanup scenario clicks through —
// a real in-app `<Link>`, not a synthetic one added for the test.

import { createServer } from "node:http";
import { pathToFileURL } from "node:url";

export const REVIEW_A = "aaaaaaaa-0000-4000-8000-000000000001";
export const REVIEW_B = "bbbbbbbb-0000-4000-8000-000000000002";

const LONG_DISCUSSION = Array.from(
  { length: 40 },
  (_, i) =>
    `Paragraph ${i + 1}. This is filler text long enough to make the review body ` +
    "taller than the viewport, so a real scroll actually moves the read-through " +
    "fraction of the discussion element through several of the five legal " +
    "milestones the client snaps to: zero, twenty-five, fifty, seventy-five, " +
    "and one hundred percent.",
).join("\n\n");

function review(id, { referral = true } = {}) {
  return {
    review: {
      id,
      review_id: null,
      title: `Fixture review ${id.slice(0, 8)}`,
      discussion: LONG_DISCUSSION,
      verdict: "yes_absolutely",
      verdict_explanation: null,
      target_audience: null,
      anti_target_audience: null,
      star_rating: 4,
      pros: null,
      cons: null,
      price_paid: null,
      photo_url: null,
      verification_status: "unverified",
      helpful_votes: 3,
      unhelpful_votes: 0,
      my_vote: null,
      created_at: new Date().toISOString(),
      referral_redirect_url: referral ? "https://example.invalid/buy" : null,
    },
    author: {
      id: "cccccccc-0000-4000-8000-000000000009",
      username: "fixture_author",
      display_name: "Fixture Author",
      avatar_url: null,
      trust_stage: 2,
      trust_level_name: "Verified Buyer",
      reputation_score: "62.00",
    },
    product: {
      id: "dddddddd-0000-4000-8000-000000000009",
      canonical_name: "Fixture Product",
      category: "fixture-category",
      avg_rating: "4.20",
      review_count: 2,
      image_url: null,
    },
    comment_count: 0,
  };
}

const REVIEWS = {
  [REVIEW_A]: review(REVIEW_A),
  [REVIEW_B]: review(REVIEW_B),
};

function json(res, status, body) {
  const text = JSON.stringify(body);
  res.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(text),
  });
  res.end(text);
}

export function startFixtureServer(port) {
  const server = createServer((req, res) => {
    const url = new URL(req.url, "http://localhost");
    const parts = url.pathname.split("/").filter(Boolean);

    // GET /api/v1/reviews/:id/full — the one call the page cannot render without.
    if (req.method === "GET" && parts[0] === "api" && parts[1] === "v1" && parts[2] === "reviews" && parts[4] === "full") {
      const found = REVIEWS[parts[3]];
      if (found) return json(res, 200, found);
      return json(res, 404, { detail: "not found" });
    }

    // GET /api/v1/reviews/:id/comments — empty thread; getComments() catches
    // any non-2xx into `[]` on its own, but answering it directly keeps the
    // page's network log free of noise while the spec asserts on it.
    if (req.method === "GET" && parts[0] === "api" && parts[1] === "v1" && parts[2] === "reviews" && parts[4] === "comments") {
      return json(res, 200, []);
    }

    // GET /api/v1/reviews/feed — used for the "related reviews" sidebar.
    // Returns the OTHER fixture review so the sidebar's Link is real and
    // clickable, which is what the navigation/cleanup scenario depends on.
    if (req.method === "GET" && parts[0] === "api" && parts[1] === "v1" && parts[2] === "reviews" && parts[3] === "feed") {
      return json(res, 200, [REVIEWS[REVIEW_B], REVIEWS[REVIEW_A]]);
    }

    // Everything else (price panel, auth/me, vote/report/comment POSTs, …):
    // 404. Every caller of these in lib/*.ts already catches and degrades;
    // see the file header for exactly which ones and why that is correct.
    return json(res, 404, { detail: "not found" });
  });

  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => resolve(server));
  });
}

// Allow `node e2e/fixtures/reading-telemetry-fixture-server.mjs` directly, for
// Playwright's webServer.command. Compared as file:// URLs rather than a raw
// string template — `process.argv[1]` is a platform path (backslashes on
// Windows) and a naive `file://${...}` prefix never matches there.
if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const port = Number(process.env.FIXTURE_PORT || 8010);
  startFixtureServer(port).then(() => {
    console.log(`reading-telemetry fixture backend listening on :${port}`);
  });
}
