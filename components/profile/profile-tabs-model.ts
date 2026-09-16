/**
 * Which section of a profile is open, and how to link to the others.
 *
 * Plain functions with no imports, for the same reason
 * `components/admin/review-queue-model.ts` exists: the components around them
 * are JSX the frontend test runner cannot render, so the part that can be got
 * wrong — a hand-edited `?tab=` value, a link that drops the reader somewhere
 * they did not ask for — lives here and is covered directly.
 */

/** The three sections the frames draw: 5446:4328, 5446:6398, 5446:6532. */
export type ProfileTab = "reviews" | "comments" | "stats";

export const PROFILE_TABS: ProfileTab[] = ["reviews", "comments", "stats"];

export const PROFILE_TAB_LABEL: Record<ProfileTab, string> = {
  reviews: "Reviews",
  comments: "Comments",
  stats: "Stats",
};

/**
 * The tab a `?tab=` value asks for.
 *
 * Anything unrecognised — a typo, a stale bookmark, a repeated parameter —
 * reads as Reviews. A profile must render; it must never 404 or blank because
 * someone edited the query string.
 */
export function readProfileTab(value: string | string[] | undefined): ProfileTab {
  const first = Array.isArray(value) ? value[0] : value;
  return first === "comments" || first === "stats" ? first : "reviews";
}

/**
 * Where a tab's link points.
 *
 * Reviews is the bare route, not `?tab=reviews`: it is the default, and a
 * profile URL that people paste to each other should be `/profile`, not
 * `/profile?tab=reviews`.
 */
export function profileTabHref(base: string, tab: ProfileTab): string {
  return tab === "reviews" ? base : `${base}?tab=${tab}`;
}
