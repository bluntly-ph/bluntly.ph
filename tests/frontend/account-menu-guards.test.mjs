import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

/**
 * The account menu's four owner requirements (P0.2, P0.4, P0.5, P0.12,
 * 2026-09-16), guarded at the source.
 *
 * These live in JSX this runner cannot render, and every one of them is a
 * property of the markup rather than of a pure function: a link that must not
 * exist, a control that must really submit, a button that must stay inert. The
 * repository already tests a route's exports this way
 * (`telemetry-route.test.mjs`); this is the same technique pointed at the
 * pieces a refactor would quietly undo.
 */

const read = (path) =>
  readFileSync(new URL(path, import.meta.url), "utf8").replace(/\r/g, "");

const NAV = read("../../components/site/ProfileNavPanel.tsx");
const PROFILE_PAGE = read("../../app/profile/page.tsx");
const GOOGLE = read("../../components/auth/GoogleButton.tsx");

/* ---------------------------------------------- P0.4: only real destinations */

test("the account menu offers nothing that does not exist", () => {
  for (const ghost of ["Bookmarks", "Recent reads", "Recent Reads", "/bookmarks", "/saved"]) {
    assert.ok(
      !NAV.includes(`label: "${ghost}"`) && !NAV.includes(`href: "${ghost}"`),
      `${ghost} is back in the account menu`,
    );
  }
});

test("every menu entry points at a route in the site map", () => {
  const siteMap = read("../../lib/site-map.ts");
  const hrefs = [...NAV.matchAll(/href: "(\/[^"]*)"/g)].map((m) => m[1]);
  assert.ok(hrefs.length >= 8, "the menu lost its entries");
  for (const href of hrefs) {
    assert.ok(siteMap.includes(`path: "${href}"`), `${href} is not a route in lib/site-map.ts`);
  }
});

/* ------------------------------------- P0.12: Moderate, for moderators only */

test("Moderate is in the menu", () => {
  assert.match(NAV, /href: "\/moderate", icon: \w+, label: "Moderate"/);
});

test("Moderate is added only for a moderator or an admin", () => {
  assert.match(NAV, /user\?\.role === "moderator" \|\| user\?\.role === "admin"/);
  // The entry must be appended through that flag, not rendered unconditionally.
  assert.match(NAV, /moderates \? \[\.\.\.ACCOUNT_GROUP, MODERATE_ITEM\] : ACCOUNT_GROUP/);
});

test("hiding the entry is not the boundary — the route guards itself", () => {
  const access = read("../../lib/route-access.ts");
  assert.match(access, /\/moderate/);
});

/* ------------------------------------------ P0.5: log out really logs out */

test("both log-out controls submit the server action, not a link", () => {
  for (const [name, source] of [
    ["the account menu", NAV],
    ["the profile page", PROFILE_PAGE],
  ]) {
    assert.match(source, /<form action=\{logout\}/, `${name} has no log-out form`);
    assert.match(source, /type="submit"/, `${name}'s log out is not a submit`);
    assert.match(
      source,
      /import \{ logout \} from "@\/app\/actions\/auth"/,
      `${name} does not import the real action`,
    );
  }
});

test("the log-out action destroys the session server-side", () => {
  const actions = read("../../app/actions/auth.ts");
  const logout = actions.slice(actions.indexOf("export async function logout"));
  assert.match(logout, /destroySession\(\)/, "logout does not destroy the session");
});

/* ------------------------- P0.2: Continue with Google, disabled and honest */

test("the Google button is disabled and says so to assistive tech", () => {
  assert.match(GOOGLE, /disabled/);
  assert.match(GOOGLE, /aria-disabled="true"/);
});

test("the disabled Google button navigates nowhere", () => {
  // Only the DISABLED branch is under test: the component still holds the real
  // OAuth hand-off for the day the credentials exist, and that branch is
  // reached only when NEXT_PUBLIC_GOOGLE_AUTH is "1". What must not happen is
  // the greyed-out control going somewhere — a sign-in button that navigates
  // while claiming to be off is worse than one that is plainly inert.
  const enabledBranchAt = GOOGLE.indexOf("  return (\n    <Button");
  assert.ok(enabledBranchAt > 0, "the component's two branches are no longer recognisable");
  const disabled = GOOGLE.slice(0, enabledBranchAt);

  assert.ok(!/href=/.test(disabled), "the Google button has an href while disabled");
  assert.ok(
    !/router\.push|window\.location|onClick=/.test(disabled),
    "the disabled Google button navigates",
  );
  assert.match(GOOGLE, /NEXT_PUBLIC_GOOGLE_AUTH/, "the live branch is no longer flag-gated");
});

test("the label is the one the owner asked for", () => {
  assert.match(GOOGLE, /Continue with Google/);
});
