import assert from "node:assert/strict";
import test from "node:test";

import {
  PROFILE_TABS,
  PROFILE_TAB_LABEL,
  profileTabHref,
  readProfileTab,
} from "../../components/profile/profile-tabs-model.ts";

/**
 * The profile's three sections (owner P0.3, 2026-09-16).
 *
 * They share one route and are switched by `?tab=`, so the parser is the whole
 * routing contract: whatever a reader's URL says, a profile has to render one
 * of exactly three sections.
 */

test("the three sections are the three the frames draw", () => {
  assert.deepEqual(PROFILE_TABS, ["reviews", "comments", "stats"]);
  assert.deepEqual(
    PROFILE_TABS.map((t) => PROFILE_TAB_LABEL[t]),
    ["Reviews", "Comments", "Stats"],
  );
});

test("each tab value reads back as itself", () => {
  for (const tab of PROFILE_TABS) {
    assert.equal(readProfileTab(tab), tab);
  }
});

test("anything unrecognised falls back to Reviews rather than failing", () => {
  for (const value of [undefined, "", "Stats", "STATS", "earnings", "../admin", "0", "null"]) {
    assert.equal(readProfileTab(value), "reviews", `for ${JSON.stringify(value)}`);
  }
});

test("a repeated parameter takes the first value", () => {
  assert.equal(readProfileTab(["stats", "comments"]), "stats");
  assert.equal(readProfileTab([]), "reviews");
});

test("Reviews links to the bare route, the others carry the parameter", () => {
  assert.equal(profileTabHref("/profile", "reviews"), "/profile");
  assert.equal(profileTabHref("/profile", "comments"), "/profile?tab=comments");
  assert.equal(profileTabHref("/profile", "stats"), "/profile?tab=stats");
});

test("every link round-trips back to the tab it points at", () => {
  for (const tab of PROFILE_TABS) {
    const href = profileTabHref("/profile", tab);
    const query = href.includes("?") ? href.slice(href.indexOf("?") + 1) : "";
    assert.equal(readProfileTab(new URLSearchParams(query).get("tab") ?? undefined), tab);
  }
});
