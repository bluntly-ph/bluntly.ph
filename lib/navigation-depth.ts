/**
 * How many in-app pages this tab can go back through (BUG-033).
 *
 * `BackControl` needs one fact: is the previous history entry a page of THIS
 * site? The browser will not say — history URLs are not readable — and the
 * obvious proxy is wrong. `history.length > 1` was the first implementation,
 * and the browser test for it failed in the most useful way possible: a fresh
 * tab counts its initial blank entry, so a review opened cold in a new tab
 * reported history, hydrated into a history button, and pressing it would have
 * taken the reader OFF the site to an empty page. That is worse than the bug
 * being fixed, which at least landed somewhere.
 *
 * So this counts what it can actually observe: route changes the app itself
 * made. The first path a document renders is the entry point, with nothing
 * in-app behind it. A later path is one step deeper — unless a `popstate`
 * came first, in which case the reader went back and it is one step shallower.
 *
 * Every uncertainty errs the same way. A full reload resets to zero; a
 * query-only change is not counted; a forward navigation is read as a back.
 * Each of those can only make the count too LOW, which means the control falls
 * back to a real link. Too high is the failure that leaves the site, and none
 * of the approximations here can produce it.
 *
 * Module state rather than React state: it has to survive the page component
 * that reads it being unmounted and replaced on every navigation, and it is
 * read through `useSyncExternalStore`, which this project prefers over
 * `setState` inside an effect.
 */

let depth = 0;
let lastPath: string | null = null;
let poppedSinceLastPath = false;
const listeners = new Set<() => void>();

if (typeof window !== "undefined") {
  window.addEventListener("popstate", () => {
    poppedSinceLastPath = true;
  });
}

function emit() {
  for (const listener of listeners) listener();
}

/** For `useSyncExternalStore`. */
export function subscribeNavigationDepth(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Is there an in-app page behind this one? */
export function canGoBackInApp(): boolean {
  return depth > 0;
}

/** On the server nothing has been navigated; render the fallback link. */
export function canGoBackOnServer(): boolean {
  return false;
}

/**
 * Record that the app is now showing `path`. Called by `NavigationDepthTracker`
 * whenever the pathname changes; safe to call repeatedly with the same path.
 */
export function recordPath(path: string): void {
  if (lastPath === null) {
    lastPath = path;
    poppedSinceLastPath = false;
    return;
  }
  if (path === lastPath) return;

  depth = poppedSinceLastPath ? Math.max(0, depth - 1) : depth + 1;
  poppedSinceLastPath = false;
  lastPath = path;
  emit();
}

/** Test seam: forget everything, as a fresh document would. */
export function resetNavigationDepth(): void {
  depth = 0;
  lastPath = null;
  poppedSinceLastPath = false;
  emit();
}

/** Test seam: mark that the next path change follows a browser back. */
export function markPopstate(): void {
  poppedSinceLastPath = true;
}
