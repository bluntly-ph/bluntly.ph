/**
 * The unread badge and where a notification goes (FR-1 1.6).
 *
 * The badge says nothing at zero — a "0" badge is noise that teaches people to
 * ignore it — and caps at "9+" so it keeps its size. A notification's link is
 * already a same-site path from the API; it is checked again here because it
 * becomes an href, and anything else falls back to the notifications page.
 */

export type NotificationItem = {
  id: string;
  kind: string;
  title: string;
  body: string | null;
  link: string | null;
  read_at: string | null;
  created_at: string;
};

export function badgeLabel(count: number): string | null {
  if (!(count > 0)) return null;
  return count > 9 ? "9+" : String(Math.floor(count));
}

export function notificationHref(link: string | null | undefined): string {
  if (!link || !link.startsWith("/") || link.startsWith("//") || link.includes("\\")) {
    return "/notifications";
  }
  return link;
}
