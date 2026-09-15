/**
 * Ages the way the design writes them: "3s ago", "5h ago", "3d ago".
 * Shared by the question cards and the question page.
 */
export function relativeTime(iso: string, now: number = Date.now()): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.round(days / 7);
  if (weeks < 52) return `${weeks}w ago`;
  return `${Math.round(weeks / 52)}y ago`;
}

/** "Joined 3 years ago", as the Profile Page frame writes membership age. */
export function joinedLabel(iso: string, now: number = Date.now()): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const months = Math.floor((now - then) / (30.44 * 24 * 3600 * 1000));
  if (months < 1) return "Joined this month";
  if (months < 12) return `Joined ${months} ${months === 1 ? "month" : "months"} ago`;
  const years = Math.floor(months / 12);
  return `Joined ${years} ${years === 1 ? "year" : "years"} ago`;
}
