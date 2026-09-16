"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSyncExternalStore } from "react";

/**
 * The site's own Back control (BUG-033).
 *
 * QA: "Go to Search, open a trending review, press the site's back button —
 * it returns to Home instead of Search." It did, because every one of these
 * controls was a `<Link>` to a hardcoded destination. A control drawn as an
 * arrow, in the position a back button lives, that always goes somewhere else
 * is worse than no control: it silently loses the reader's place, and the one
 * thing they were trying to keep was where they came from.
 *
 * So it goes back where there is somewhere to go back to, and to
 * `fallbackHref` where there is not — a deep link opened in a fresh tab, a
 * shared URL, a bookmark. Both cases render the same control; only the element
 * differs, and it has to: a real navigation belongs in an anchor so it can be
 * middle-clicked and read by assistive tech as a link, while `history.back()`
 * is a button because it goes somewhere the markup cannot name.
 *
 * WHAT COUNTS AS "SOMEWHERE TO GO BACK TO" is `window.history.length > 1`,
 * read through `useSyncExternalStore` rather than an effect — this project
 * treats `setState` inside an effect as a lint error, and the server has no
 * history object, so the server snapshot is `false` and the first paint is the
 * link. That is the safe way round: a control that navigates somewhere real
 * before hydration, not one that does nothing.
 *
 * It is deliberately NOT a "previous page in this app" tracker. If the reader
 * arrived from a search engine, back returns them to it — which is what a back
 * control means everywhere else on the web, and what the browser's own button
 * would do from the same position.
 */

function subscribe() {
  // `history.length` only changes as a side effect of navigation, and every
  // navigation re-renders this component. There is no event to subscribe to,
  // and inventing a polling loop for a value that cannot change under us
  // would be worse than not subscribing.
  return () => {};
}

function hasHistory() {
  return typeof window !== "undefined" && window.history.length > 1;
}

/** No history on the server: render the link, which works without JavaScript. */
function noHistoryOnTheServer() {
  return false;
}

export function BackControl({
  fallbackHref,
  label = "Back",
  className,
  children,
}: {
  /** Where to go when this tab has no earlier entry. A real route, never "#". */
  fallbackHref: string;
  label?: string;
  className?: string;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const canGoBack = useSyncExternalStore(subscribe, hasHistory, noHistoryOnTheServer);

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
