"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSyncExternalStore } from "react";

import {
  canGoBackInApp,
  canGoBackOnServer,
  subscribeNavigationDepth,
} from "@/lib/navigation-depth";

/**
 * The site's own Back control (BUG-033).
 *
 * QA: "Go to Search, open a trending review, press the site's back button —
 * it returns to Home instead of Search." It did, because every one of these
 * controls was a `<Link>` to a hardcoded destination. A control drawn as an
 * arrow, in the position a back button lives, that always goes somewhere else
 * silently loses the reader's place — and their place was the one thing they
 * were trying to keep.
 *
 * So it goes back through history when the previous entry is a page of this
 * site, and to `fallbackHref` when it is not — a deep link opened in a fresh
 * tab, a shared URL, a bookmark. Only the element differs, and it has to: a
 * real destination belongs in an anchor, which can be middle-clicked and is
 * announced as a link, while `router.back()` is a button because it goes
 * somewhere the markup cannot name.
 *
 * "IS THE PREVIOUS ENTRY ON THIS SITE" comes from `lib/navigation-depth`, which
 * counts the app's own route changes. The first version used
 * `window.history.length > 1`, and the browser test for it caught why that is
 * wrong: a fresh tab counts its blank starting entry, so a review opened cold
 * hydrated into a history button that would have taken the reader off the site.
 *
 * The server renders the link. That is the safe way round: before hydration,
 * and for anyone without JavaScript, the control goes somewhere real.
 */
export function BackControl({
  fallbackHref,
  label = "Back",
  className,
  children,
}: {
  /** Where to go when there is no in-app page behind this one. A real route. */
  fallbackHref: string;
  label?: string;
  className?: string;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const canGoBack = useSyncExternalStore(
    subscribeNavigationDepth,
    canGoBackInApp,
    canGoBackOnServer,
  );

  if (!canGoBack) {
    return (
      <Link href={fallbackHref} aria-label={label} className={className}>
        {children}
      </Link>
    );
  }

  return (
    <button type="button" onClick={() => router.back()} aria-label={label} className={className}>
      {children}
    </button>
  );
}

export default BackControl;
