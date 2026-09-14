/**
 * Whether a review shows the public trust badge (completion contract X.2).
 *
 * The API decides — proof (the author's own photo), a recorded moderator
 * decision, and publication — and sends `has_trust_badge`. Every card and page
 * reads it through this one function, and it fails closed: a response without
 * the field shows no badge rather than falling back to the photo-only
 * `verification_status` it replaced.
 */
export function showsTrustBadge(
  review: { has_trust_badge?: boolean | null } | null | undefined,
): boolean {
  return review?.has_trust_badge === true;
}
