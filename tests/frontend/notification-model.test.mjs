import assert from "node:assert/strict";
import test from "node:test";

import { badgeLabel, notificationHref } from "../../components/site/notification-model.ts";

/**
 * The unread badge and where a notification goes.
 *
 * The badge says nothing at zero (a "0" badge is noise that trains people to
 * ignore it) and caps at "9+" so it keeps its size. A notification's link is
 * already a same-site path from the API; the client re-checks it anyway,
 * because it becomes an href, and falls back to the notifications page.
 */

test("no badge when nothing is unread", () => {
  assert.equal(badgeLabel(0), null);
  assert.equal(badgeLabel(-1), null);
});

test("the count, capped at 9+", () => {
  assert.equal(badgeLabel(1), "1");
  assert.equal(badgeLabel(9), "9");
  assert.equal(badgeLabel(10), "9+");
  assert.equal(badgeLabel(250), "9+");
});

test("a same-site link is followed", () => {
  assert.equal(notificationHref("/questions/abc"), "/questions/abc");
});

test("anything else falls back to the notifications page", () => {
  assert.equal(notificationHref(null), "/notifications");
  assert.equal(notificationHref("https://evil.example"), "/notifications");
  assert.equal(notificationHref("//evil.example"), "/notifications");
  assert.equal(notificationHref("/\\evil.example"), "/notifications");
});
