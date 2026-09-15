"use client";

import { useEffect } from "react";

import { RECENT_SEARCHES_KEY, parseRecentSearches, rememberSearch } from "./recent-searches-model";

/**
 * Records a search that actually ran — the `?q=` a results page was rendered
 * for — in this device's recent searches. Renders nothing. Storage can be
 * unavailable (private windows, blocked site data); that only costs the list.
 */
export function RememberSearch({ q }: { q: string }) {
  useEffect(() => {
    if (!q.trim()) return;
    try {
      const current = parseRecentSearches(window.localStorage.getItem(RECENT_SEARCHES_KEY));
      window.localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(rememberSearch(current, q)));
    } catch {
      /* no storage: no history */
    }
  }, [q]);
  return null;
}

export default RememberSearch;
