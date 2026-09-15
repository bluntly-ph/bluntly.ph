/**
 * The reader's recent searches, for the typing state of "Screen/Mobile Search"
 * (6852:641): three rows, newest first. Kept on this device only — nothing is
 * sent anywhere — so what comes back out of storage is treated as untrusted.
 */

export const MAX_RECENT_SEARCHES = 3;
export const RECENT_SEARCHES_KEY = "bluntly:recent-searches:v1";

export function rememberSearch(list: readonly string[], query: string): string[] {
  const q = query.trim();
  if (!q) return [...list];
  const key = q.toLowerCase();
  return [q, ...list.filter((item) => item.toLowerCase() !== key)].slice(0, MAX_RECENT_SEARCHES);
}

export function parseRecentSearches(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const value: unknown = JSON.parse(raw);
    if (!Array.isArray(value)) return [];
    return value
      .filter((item): item is string => typeof item === "string" && item.trim().length > 0)
      .slice(0, MAX_RECENT_SEARCHES);
  } catch {
    return [];
  }
}
